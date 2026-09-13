"""Authenticated production-facing read model for the live steelmaking flow."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import connection
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .telemetry import build_dashboard_snapshot


FLOW = (
    {
        "id": "eaf",
        "area": "EAF",
        "label": "Electric Arc Furnace",
        "equipment": "EAF-01",
        "short_label": "EAF",
        "activities": ("Charge", "Melting", "Refining", "Tapping"),
    },
    {
        "id": "lf",
        "area": "LF",
        "label": "Ladle Furnace",
        "equipment": "LF-01",
        "short_label": "LF",
        "activities": ("Ladle received", "Heating", "Argon stirring", "Sampling"),
    },
    {
        "id": "ccm",
        "area": "CCM",
        "label": "Continuous Casting",
        "equipment": "CCM-01",
        "short_label": "CCM",
        "activities": ("Prepare", "Start cast", "Steady cast", "End cast"),
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
                "value": value.get("value_double") if value.get("value_double") is not None else value.get("value_text"),
                "unit": value.get("engineering_unit"),
                "quality": value.get("quality"),
                "timestamp": value.get("ts"),
            }
    return None


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
    """Convert high-level workflow stages to an operator-friendly activity label."""
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
    active_index = next((index for index, item in enumerate(FLOW) if item["area"] == active_area), None)

    metric_names = {
        "EAF": ("EAF.PowerMW", "EAF.SteelTemperature"),
        "LF": ("LF.SteelTemperature", "LF.ArgonFlow"),
        "CCM": ("CCM.CastingSpeed", "CCM.TundishTemperature"),
    }
    stations = []
    for index, definition in enumerate(FLOW):
        is_active = index == active_index
        stations.append(
            {
                **definition,
                "state": _station_state(index=index, active_index=active_index),
                "current_activity": (
                    _current_activity(definition=definition, active_stage=active_stage)
                    if is_active and active_stage
                    else definition["activities"][1] if is_active else None
                ),
                "stage_started_at": active_stage.get("started_at") if is_active and active_stage else None,
                "stage_age_seconds": _stage_age_seconds(active_stage.get("started_at")) if is_active and active_stage else None,
                "metrics": [
                    metric
                    for tag_name in metric_names[definition["area"]]
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
            "stations": stations,
        }
    )
