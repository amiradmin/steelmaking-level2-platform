"""Authenticated production-facing read model for the live steelmaking flow."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from django.db import connection
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .telemetry import build_dashboard_snapshot


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


SIM_TIME_SCALE = max(0.1, _env_float("PLC_SIM_TIME_SCALE", 60.0))
HEAT_PITCH_MINUTES = max(1.0, _env_float("PLC_SIM_HEAT_PITCH_MINUTES", 70.0))

FLOW = (
    {
        "id": "eaf",
        "area": "EAF",
        "label": "Electric Arc Furnace",
        "equipment": "EAF-01",
        "short_label": "EAF",
        "activities": ("Charge", "Melting", "Refining", "Superheat", "Tapping"),
        "stages": {
            1: ("Charge", 7.0),
            2: ("Melting", 35.0),
            3: ("Refining", 13.0),
            4: ("Superheat", 5.0),
            5: ("Tapping", 5.0),
        },
    },
    {
        "id": "lf",
        "area": "LF",
        "label": "Ladle Furnace",
        "equipment": "LF-01",
        "short_label": "LF",
        "activities": (
            "Ladle received",
            "Heating",
            "Alloying",
            "Argon stirring",
            "Sampling",
            "Ready to cast",
        ),
        "stages": {
            1: ("Ladle received", 3.0),
            2: ("Heating", 17.0),
            3: ("Alloying", 6.0),
            4: ("Argon stirring", 6.0),
            5: ("Sampling", 4.0),
            6: ("Ready to cast", 2.0),
        },
    },
    {
        "id": "ccm",
        "area": "CCM",
        "label": "Continuous Casting",
        "equipment": "CCM-01",
        "short_label": "CCM",
        "activities": ("Prepare", "Start cast", "Steady cast", "End cast"),
        "stages": {
            1: ("Prepare", 5.0),
            2: ("Start cast", 4.0),
            3: ("Steady cast", 42.0),
            4: ("End cast", 4.0),
        },
    },
)


def _active_stage(heat_id: str) -> dict[str, Any] | None:
    """Return the active heat-stage row produced by Level 1 or plant workflow."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                hs.stage,
                hs.started_at,
                e.area,
                e.code AS equipment_code
            FROM heat_stages hs
            LEFT JOIN equipment e ON e.id = hs.equipment_id
            WHERE hs.heat_id = %s::uuid
              AND hs.status = 'ACTIVE'
            ORDER BY hs.started_at DESC
            LIMIT 1
            """,
            [heat_id],
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "stage": row[0],
            "started_at": row[1],
            "area": row[2],
            "equipment_code": row[3],
        }


def _stage_age_seconds(value: Any) -> int | None:
    if not isinstance(value, datetime):
        return None
    return max(0, int((timezone.now() - value).total_seconds()))


def _metric(values: list[dict[str, Any]], tag_name: str) -> dict[str, Any] | None:
    for value in values:
        if value.get("tag_name") == tag_name:
            return {
                "tag_name": tag_name,
                "value": value.get("value_double")
                if value.get("value_double") is not None
                else value.get("value_text"),
                "unit": value.get("engineering_unit"),
                "quality": value.get("quality"),
                "timestamp": value.get("ts"),
            }
    return None


def _numeric_value(values: list[dict[str, Any]], tag_name: str) -> float | None:
    metric = _metric(values, tag_name)
    if metric is None:
        return None
    value = metric.get("value")
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _plc_stage_started_at(tag_name: str, current_code: int) -> datetime | None:
    """Approximate the current PLC stage boundary from historian transitions."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT ps.ts
            FROM process_samples ps
            JOIN process_tags pt ON pt.id = ps.tag_id
            WHERE pt.tag_name = %s
              AND ps.value_double IS NOT NULL
              AND ps.value_double <> %s
            ORDER BY ps.ts DESC
            LIMIT 1
            """,
            [tag_name, float(current_code)],
        )
        row = cursor.fetchone()
        if row is not None and isinstance(row[0], datetime):
            return row[0]

        cursor.execute(
            """
            SELECT MIN(ps.ts)
            FROM process_samples ps
            JOIN process_tags pt ON pt.id = ps.tag_id
            WHERE pt.tag_name = %s
              AND ps.value_double = %s
              AND ps.ts > now() - interval '10 minutes'
            """,
            [tag_name, float(current_code)],
        )
        fallback = cursor.fetchone()
        return fallback[0] if fallback and isinstance(fallback[0], datetime) else None


def _station_state(*, index: int, active_index: int | None) -> str:
    if active_index is None:
        return "standby"
    if index < active_index:
        return "complete"
    if index == active_index:
        return "active"
    if index == active_index + 1:
        return "ready"
    return "standby"


def _current_activity(*, definition: dict[str, Any], active_stage: dict[str, Any] | None) -> str:
    default_activity = str(definition["activities"][1])
    if not active_stage:
        return default_activity
    reported = str(active_stage.get("stage") or "").strip()
    if reported.upper() in {str(definition["area"]), str(definition["id"]).upper()}:
        return default_activity
    return reported.replace("_", " ").title() or default_activity


@api_view(["GET"])
def production_flow(request: Request) -> Response:
    """Expose the operator-safe, real-time EAF-to-CCM production flow."""
    del request
    snapshot = build_dashboard_snapshot(stale_after_seconds=5.0)
    heat = snapshot["active_heat"]
    live_values = snapshot["live_values"]
    active_stage = _active_stage(heat["id"]) if heat else None
    active_area = active_stage.get("area") if active_stage else None
    if active_area is None and heat:
        active_area = {"CASTING": "CCM"}.get(heat["status"], heat["status"])
    active_index = next(
        (index for index, item in enumerate(FLOW) if item["area"] == active_area),
        None,
    )

    metric_names = {
        "EAF": ("EAF.PowerMW", "EAF.SteelTemperature"),
        "LF": ("LF.SteelTemperature", "LF.ArgonFlow"),
        "CCM": ("CCM.CastingSpeed", "CCM.TundishTemperature"),
    }

    stations: list[dict[str, Any]] = []
    pipeline_heats: dict[str, int | None] = {}

    for index, definition in enumerate(FLOW):
        area = str(definition["area"])
        stage_tag = f"{area}.StageCode"
        heat_tag = f"{area}.HeatNumber"
        stage_value = _numeric_value(live_values, stage_tag)
        heat_value = _numeric_value(live_values, heat_tag)
        stage_code = int(stage_value) if stage_value is not None else None
        heat_number = int(heat_value) if heat_value is not None else None
        pipeline_heats[area] = heat_number

        plc_stage = definition["stages"].get(stage_code) if stage_code is not None else None
        if plc_stage is not None:
            current_activity = str(plc_stage[0])
            stage_duration_seconds = int(float(plc_stage[1]) * 60.0)
            stage_started_at = _plc_stage_started_at(stage_tag, stage_code)
            wall_age = _stage_age_seconds(stage_started_at)
            stage_age_seconds = (
                min(stage_duration_seconds, int(wall_age * SIM_TIME_SCALE))
                if wall_age is not None
                else None
            )
            progress = (
                round(min(100.0, stage_age_seconds / stage_duration_seconds * 100.0), 1)
                if stage_age_seconds is not None and stage_duration_seconds > 0
                else None
            )
            state = "active"
        elif stage_code == 0 and stage_value is not None:
            current_activity = None
            stage_duration_seconds = None
            stage_started_at = None
            stage_age_seconds = None
            progress = None
            state = "ready"
        else:
            is_active = index == active_index
            current_activity = (
                _current_activity(definition=definition, active_stage=active_stage)
                if is_active and active_stage
                else definition["activities"][1] if is_active else None
            )
            stage_started_at = (
                active_stage.get("started_at") if is_active and active_stage else None
            )
            stage_age_seconds = (
                _stage_age_seconds(stage_started_at) if is_active and active_stage else None
            )
            stage_duration_seconds = None
            progress = None
            state = _station_state(index=index, active_index=active_index)

        activity_durations_seconds = {
            str(stage_definition[0]): int(float(stage_definition[1]) * 60.0)
            for stage_definition in definition["stages"].values()
        }

        stations.append(
            {
                "id": definition["id"],
                "area": area,
                "label": definition["label"],
                "equipment": definition["equipment"],
                "short_label": definition["short_label"],
                "activities": definition["activities"],
                "activity_durations_seconds": activity_durations_seconds,
                "state": state,
                "current_activity": current_activity,
                "stage_started_at": stage_started_at,
                "stage_age_seconds": stage_age_seconds,
                "stage_duration_seconds": stage_duration_seconds,
                "stage_progress_percent": progress,
                "heat_number": heat_number,
                "metrics": [
                    metric
                    for tag_name in metric_names[area]
                    if (metric := _metric(live_values, tag_name)) is not None
                ],
            }
        )

    return Response(
        {
            "generated_at": timezone.now(),
            "current_heat": heat,
            "active_stage": active_stage,
            "l1_link": snapshot["l1_link"],
            "simulation": {
                "time_scale": SIM_TIME_SCALE,
                "heat_pitch_minutes": HEAT_PITCH_MINUTES,
            },
            "pipeline_heats": pipeline_heats,
            "stations": stations,
        }
    )
