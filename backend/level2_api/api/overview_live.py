"""Historian-driven read model for the operations overview dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db import connection
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .production_flow import (
    FLOW,
    SIM_TIME_SCALE,
    _current_run_started_at,
    _latest_nonzero_stage_code,
    _plc_stage_started_at,
)
from .telemetry import build_dashboard_snapshot


TREND_TAGS = (
    "EAF.SteelTemperature",
    "EAF.PowerMW",
    "EAF.OxygenFlow",
    "LF.SteelTemperature",
    "LF.ArgonFlow",
    "CCM.TundishTemperature",
    "CCM.CastingSpeed",
)


def _numeric(values: list[dict[str, Any]], tag_name: str) -> float | None:
    for item in values:
        if item.get("tag_name") != tag_name:
            continue
        value = item.get("value_double")
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _quality(values: list[dict[str, Any]], tag_name: str) -> str | None:
    for item in values:
        if item.get("tag_name") == tag_name:
            value = item.get("quality")
            return str(value) if value is not None else None
    return None


def _process_heat_number(values: list[dict[str, Any]], active_area: str | None) -> int | None:
    areas = [active_area] if active_area else []
    areas.extend(area for area in ("EAF", "LF", "CCM") if area not in areas)
    for area in areas:
        if area is None:
            continue
        value = _numeric(values, f"{area}.HeatNumber")
        if value is not None and value > 0:
            return int(value)
    return None


def _stage_snapshot(
    live_values: list[dict[str, Any]],
    run_started_at: datetime | None,
) -> tuple[list[dict[str, Any]], str | None]:
    stations: list[dict[str, Any]] = []
    active_area: str | None = None

    for definition in FLOW:
        area = str(definition["area"])
        tag_name = f"{area}.StageCode"
        raw_code = _numeric(live_values, tag_name)
        stage_code = int(raw_code) if raw_code is not None else 0
        stage_definition = definition["stages"].get(stage_code)
        final_stage_code = max(definition["stages"])
        last_nonzero = _latest_nonzero_stage_code(tag_name, run_started_at)

        stage_name: str | None = None
        progress: float | None = None
        elapsed_seconds: int | None = None
        planned_seconds: int | None = None
        state = "standby"

        if stage_definition is not None:
            active_area = active_area or area
            stage_name = str(stage_definition[0])
            planned_seconds = int(float(stage_definition[1]) * 60.0)
            started_at = _plc_stage_started_at(tag_name, stage_code, run_started_at)
            if isinstance(started_at, datetime):
                wall_seconds = max(0.0, (timezone.now() - started_at).total_seconds())
                elapsed_seconds = min(planned_seconds, int(wall_seconds * SIM_TIME_SCALE))
                if planned_seconds > 0:
                    progress = round(min(100.0, elapsed_seconds / planned_seconds * 100.0), 1)
            state = "active"
        elif run_started_at is not None and last_nonzero == final_stage_code:
            stage_name = str(definition["stages"][final_stage_code][0])
            progress = 100.0
            state = "complete"
        elif run_started_at is not None:
            state = "ready"

        stations.append(
            {
                "area": area,
                "equipment": definition["equipment"],
                "stage_code": stage_code,
                "stage_name": stage_name,
                "state": state,
                "progress_percent": progress,
                "elapsed_seconds": elapsed_seconds,
                "planned_seconds": planned_seconds,
            }
        )

    return stations, active_area


def _tap_to_tap_minutes() -> float | None:
    """Return the latest completed EAF tap-to-tap interval from stage transitions."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH stage_samples AS (
                SELECT
                    ps.ts,
                    ps.value_double,
                    LAG(ps.value_double) OVER (ORDER BY ps.ts) AS previous_value
                FROM process_samples ps
                JOIN process_tags pt ON pt.id = ps.tag_id
                WHERE pt.tag_name = 'EAF.StageCode'
                  AND ps.value_double IS NOT NULL
                  AND ps.ts > now() - interval '24 hours'
            ), tap_starts AS (
                SELECT ts
                FROM stage_samples
                WHERE value_double = 5
                  AND COALESCE(previous_value, -1) <> 5
                ORDER BY ts DESC
                LIMIT 2
            )
            SELECT ts FROM tap_starts ORDER BY ts DESC
            """
        )
        rows = cursor.fetchall()

    if len(rows) < 2:
        return None
    latest, previous = rows[0][0], rows[1][0]
    if not isinstance(latest, datetime) or not isinstance(previous, datetime):
        return None
    minutes = (latest - previous).total_seconds() * SIM_TIME_SCALE / 60.0
    return round(max(0.0, minutes), 1)


def _integrated_eaf_energy_kwh(
    heat_id: str | None,
    run_started_at: datetime | None,
) -> float | None:
    if heat_id is None or run_started_at is None:
        return None

    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH samples AS (
                SELECT
                    ps.ts,
                    ps.value_double,
                    LEAD(ps.ts) OVER (ORDER BY ps.ts) AS next_ts
                FROM process_samples ps
                JOIN process_tags pt ON pt.id = ps.tag_id
                WHERE pt.tag_name = 'EAF.PowerMW'
                  AND ps.heat_id = %s::uuid
                  AND ps.value_double IS NOT NULL
                  AND ps.quality = 'GOOD'
                  AND ps.ts >= %s
            )
            SELECT SUM(
                GREATEST(value_double, 0)
                * LEAST(
                    5.0,
                    GREATEST(
                        0.0,
                        EXTRACT(EPOCH FROM (COALESCE(next_ts, now()) - ts))
                    )
                )
                / 3600.0
                * 1000.0
            )
            FROM samples
            """,
            [heat_id, run_started_at],
        )
        row = cursor.fetchone()

    if not row or row[0] is None:
        return None
    return round(float(row[0]) * SIM_TIME_SCALE, 1)


def _charged_tonnes(heat_id: str | None) -> float | None:
    if heat_id is None:
        return None
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT SUM(
                CASE
                    WHEN lower(unit) IN ('t', 'ton', 'tons', 'tonne', 'tonnes') THEN quantity
                    WHEN lower(unit) IN ('kg', 'kilogram', 'kilograms') THEN quantity / 1000.0
                    ELSE 0
                END
            )
            FROM material_consumptions
            WHERE heat_id = %s::uuid
            """,
            [heat_id],
        )
        row = cursor.fetchone()
    if not row or row[0] is None or float(row[0]) <= 0:
        return None
    return round(float(row[0]), 3)


def _trend(window_seconds: float) -> dict[str, list[dict[str, Any]]]:
    end = timezone.now()
    start = end - timedelta(seconds=window_seconds)
    bucket_seconds = max(1.0, window_seconds / 240.0)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                pt.tag_name,
                date_bin(make_interval(secs => %s), ps.ts, timestamptz '2001-01-01 00:00:00+00') AS bucket,
                AVG(ps.value_double)::double precision AS value
            FROM process_samples ps
            JOIN process_tags pt ON pt.id = ps.tag_id
            WHERE pt.tag_name = ANY(%s)
              AND ps.value_double IS NOT NULL
              AND ps.quality = 'GOOD'
              AND ps.ts >= %s
              AND ps.ts <= %s
            GROUP BY pt.tag_name, bucket
            ORDER BY bucket ASC, pt.tag_name ASC
            """,
            [bucket_seconds, list(TREND_TAGS), start, end],
        )
        rows = cursor.fetchall()

    result: dict[str, list[dict[str, Any]]] = {tag: [] for tag in TREND_TAGS}
    for tag_name, bucket, value in rows:
        result.setdefault(str(tag_name), []).append(
            {"ts": bucket, "value": float(value)}
        )
    return result


def _recent_heats() -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                h.heat_no,
                h.status::text AS status,
                sg.code AS grade_code,
                h.planned_weight_t::double precision,
                h.actual_weight_t::double precision,
                h.started_at,
                h.completed_at,
                MAX(ps.value_double) FILTER (WHERE pt.tag_name = 'EAF.SteelTemperature')::double precision AS peak_eaf_temperature
            FROM heats h
            LEFT JOIN steel_grades sg ON sg.id = h.grade_id
            LEFT JOIN process_samples ps ON ps.heat_id = h.id
            LEFT JOIN process_tags pt ON pt.id = ps.tag_id
            GROUP BY h.id, h.heat_no, h.status, sg.code, h.planned_weight_t, h.actual_weight_t, h.started_at, h.completed_at
            ORDER BY h.created_at DESC
            LIMIT 6
            """
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


@api_view(["GET"])
def overview_live(request: Request) -> Response:
    """Return only measured or historian-derived values for the Overview page."""
    del request
    snapshot = build_dashboard_snapshot(stale_after_seconds=5.0)
    heat = snapshot.get("active_heat")
    live_values = snapshot.get("live_values") or []
    run_started_at = _current_run_started_at()
    stations, active_area = _stage_snapshot(live_values, run_started_at)
    process_heat_number = _process_heat_number(live_values, active_area)

    heat_id = str(heat["id"]) if isinstance(heat, dict) and heat.get("id") else None
    planned_weight = float(heat["planned_weight_t"]) if isinstance(heat, dict) and heat.get("planned_weight_t") is not None else None
    actual_weight = float(heat["actual_weight_t"]) if isinstance(heat, dict) and heat.get("actual_weight_t") is not None else None
    reference_weight = actual_weight if actual_weight and actual_weight > 0 else planned_weight
    reference_weight_source = "actual_weight_t" if actual_weight and actual_weight > 0 else "planned_weight_t" if planned_weight and planned_weight > 0 else None

    energy_kwh = _integrated_eaf_energy_kwh(heat_id, run_started_at)
    specific_energy = (
        round(energy_kwh / reference_weight, 1)
        if energy_kwh is not None and reference_weight is not None and reference_weight > 0
        else None
    )

    charged_tonnes = _charged_tonnes(heat_id)
    yield_percent = (
        round(actual_weight / charged_tonnes * 100.0, 2)
        if actual_weight is not None and charged_tonnes is not None and charged_tonnes > 0
        else None
    )

    temperature_tag = {
        "EAF": "EAF.SteelTemperature",
        "LF": "LF.SteelTemperature",
        "CCM": "CCM.TundishTemperature",
    }.get(active_area or "", "EAF.SteelTemperature")

    simulated_window_seconds = 3600.0
    wall_window_seconds = max(30.0, simulated_window_seconds / max(0.1, SIM_TIME_SCALE))

    current_eaf_elapsed_minutes = None
    if run_started_at is not None:
        current_eaf_elapsed_minutes = round(
            max(0.0, (timezone.now() - run_started_at).total_seconds()) * SIM_TIME_SCALE / 60.0,
            1,
        )

    return Response(
        {
            "generated_at": timezone.now(),
            "l1_link": snapshot.get("l1_link"),
            "heat": heat,
            "process_heat_number": process_heat_number,
            "active_area": active_area,
            "stations": stations,
            "temperature": {
                "tag_name": temperature_tag,
                "value": _numeric(live_values, temperature_tag),
                "quality": _quality(live_values, temperature_tag),
            },
            "latest": {
                "EAF.PowerMW": _numeric(live_values, "EAF.PowerMW"),
                "EAF.CurrentKA": _numeric(live_values, "EAF.CurrentKA"),
                "EAF.OxygenFlow": _numeric(live_values, "EAF.OxygenFlow"),
                "EAF.SteelTemperature": _numeric(live_values, "EAF.SteelTemperature"),
                "LF.SteelTemperature": _numeric(live_values, "LF.SteelTemperature"),
                "LF.ArgonFlow": _numeric(live_values, "LF.ArgonFlow"),
                "CCM.CastingSpeed": _numeric(live_values, "CCM.CastingSpeed"),
                "CCM.TundishTemperature": _numeric(live_values, "CCM.TundishTemperature"),
            },
            "kpis": {
                "tap_to_tap_minutes": _tap_to_tap_minutes(),
                "current_eaf_elapsed_minutes": current_eaf_elapsed_minutes,
                "eaf_energy_kwh": energy_kwh,
                "specific_energy_kwh_t": specific_energy,
                "reference_weight_t": reference_weight,
                "reference_weight_source": reference_weight_source,
                "charged_weight_t": charged_tonnes,
                "actual_weight_t": actual_weight,
                "yield_percent": yield_percent,
                "active_alarm_count": len(snapshot.get("active_alarms") or []),
                "critical_alarm_count": sum(
                    1
                    for alarm in snapshot.get("active_alarms") or []
                    if str(alarm.get("severity", "")).upper() in {"CRITICAL", "HIGH"}
                ),
            },
            "trend": {
                "simulated_minutes": 60,
                "wall_window_seconds": wall_window_seconds,
                "series": _trend(wall_window_seconds),
            },
            "recent_heats": _recent_heats(),
        }
    )
