from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import connection
from django.utils import timezone


ACTIVE_HEAT_STATUSES = ("CHARGING", "EAF", "TAPPING", "LF", "CASTING")


def _dictfetchall(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _dictfetchone(cursor: Any) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row, strict=True))


def _current_heat() -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                h.id::text AS id,
                h.heat_no,
                h.status::text AS status,
                sg.code AS grade_code,
                h.planned_weight_t::double precision AS planned_weight_t,
                h.actual_weight_t::double precision AS actual_weight_t,
                h.started_at,
                h.updated_at
            FROM heats h
            LEFT JOIN steel_grades sg ON sg.id = h.grade_id
            WHERE h.status::text = ANY(%s)
            ORDER BY h.updated_at DESC, h.created_at DESC
            LIMIT 1
            """,
            [list(ACTIVE_HEAT_STATUSES)],
        )
        return _dictfetchone(cursor)


def _live_values(heat_id: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT ON (ps.tag_id)
                pt.tag_name,
                e.code AS equipment_code,
                e.area,
                pt.engineering_unit,
                ps.value_double,
                ps.value_text,
                ps.quality::text AS quality,
                ps.ts
            FROM process_samples ps
            JOIN process_tags pt ON pt.id = ps.tag_id
            LEFT JOIN equipment e ON e.id = pt.equipment_id
            WHERE ps.heat_id = %s::uuid
            ORDER BY ps.tag_id, ps.ts DESC
            """,
            [heat_id],
        )
        return _dictfetchall(cursor)


def _active_alarms(heat_id: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                a.alarm_code,
                a.severity::text AS severity,
                a.state::text AS state,
                a.message,
                e.code AS equipment_code,
                a.active_at,
                a.acknowledged_at
            FROM alarms a
            LEFT JOIN equipment e ON e.id = a.equipment_id
            WHERE a.heat_id = %s::uuid
              AND a.state IN ('ACTIVE_UNACKNOWLEDGED', 'ACTIVE_ACKNOWLEDGED')
            ORDER BY a.active_at DESC
            LIMIT 50
            """,
            [heat_id],
        )
        return _dictfetchall(cursor)


def _recent_events(heat_id: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                he.event_type,
                he.source_system,
                he.area,
                he.severity,
                e.code AS equipment_code,
                he.occurred_at
            FROM heat_events he
            LEFT JOIN equipment e ON e.id = he.equipment_id
            WHERE he.heat_id = %s::uuid
            ORDER BY he.occurred_at DESC
            LIMIT 20
            """,
            [heat_id],
        )
        return _dictfetchall(cursor)


def _link_health(
    values: list[dict[str, Any]],
    *,
    stale_after_seconds: float,
) -> dict[str, Any]:
    timestamps = [value.get("ts") for value in values if isinstance(value.get("ts"), datetime)]
    latest_sample_at = max(timestamps, default=None)
    if latest_sample_at is None:
        return {
            "online": False,
            "age_seconds": None,
            "last_sample_at": None,
        }

    age_seconds = max(0.0, (timezone.now() - latest_sample_at).total_seconds())
    return {
        "online": age_seconds <= stale_after_seconds,
        "age_seconds": round(age_seconds, 3),
        "last_sample_at": latest_sample_at,
    }


def build_dashboard_snapshot(*, stale_after_seconds: float) -> dict[str, Any]:
    """Return one realtime dashboard snapshot from the Level 2 historian.

    The websocket layer intentionally reads from the historian rather than from
    the Level 1 simulator directly. A future OPC UA/PLC gateway can therefore
    replace the simulator without changing the dashboard contract.
    """

    heat = _current_heat()
    if heat is None:
        return {
            "server_time": timezone.now(),
            "active_heat": None,
            "live_values": [],
            "active_alarms": [],
            "recent_events": [],
            "l1_link": {
                "online": False,
                "age_seconds": None,
                "last_sample_at": None,
            },
        }

    heat_id = heat["id"]
    live_values = _live_values(heat_id)
    return {
        "server_time": timezone.now(),
        "active_heat": heat,
        "live_values": live_values,
        "active_alarms": _active_alarms(heat_id),
        "recent_events": _recent_events(heat_id),
        "l1_link": _link_health(
            live_values,
            stale_after_seconds=stale_after_seconds,
        ),
    }
