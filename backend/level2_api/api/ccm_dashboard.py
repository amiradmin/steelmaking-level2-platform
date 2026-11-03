from __future__ import annotations

from typing import Any

from django.db import connection
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .rbac import require_app_permission


TREND_TAGS = (
    "CCM.CastingSpeed",
    "CCM.TundishTemperature",
    "CCM.MoldLevelPercent",
    "CCM.TundishWeightTon",
)


def _dictfetchall(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _dictfetchone(cursor: Any) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row, strict=True))


@api_view(["GET"])
def ccm_dashboard(request: Request) -> Response:
    """Return the read-only live operating picture for CCM-01."""
    require_app_permission(request.user, "production.view")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT code, name, area, equipment_type, metadata
            FROM equipment
            WHERE area = 'CCM' AND is_active = TRUE
            ORDER BY code
            LIMIT 1
            """
        )
        equipment = _dictfetchone(cursor)

        cursor.execute(
            """
            SELECT
                h.id,
                h.heat_no,
                h.status::text AS status,
                sg.code AS grade_code,
                h.planned_weight_t,
                h.actual_weight_t,
                h.started_at,
                h.updated_at
            FROM heats h
            LEFT JOIN steel_grades sg ON sg.id = h.grade_id
            WHERE h.status IN ('CASTING', 'HOLD')
            ORDER BY h.updated_at DESC, h.created_at DESC
            LIMIT 1
            """
        )
        active_heat = _dictfetchone(cursor)

        cursor.execute(
            """
            SELECT
                pt.tag_name,
                pt.source_system,
                pt.source_tag,
                pt.engineering_unit,
                latest.value_double,
                latest.value_text,
                latest.quality::text AS quality,
                latest.ts,
                h.heat_no
            FROM process_tags pt
            LEFT JOIN equipment e ON e.id = pt.equipment_id
            CROSS JOIN LATERAL (
                SELECT ps.heat_id, ps.value_double, ps.value_text, ps.quality, ps.ts
                FROM process_samples ps
                WHERE ps.tag_id = pt.id
                ORDER BY ps.ts DESC
                LIMIT 1
            ) latest
            LEFT JOIN heats h ON h.id = latest.heat_id
            WHERE pt.is_active = TRUE
              AND (e.area = 'CCM' OR pt.tag_name LIKE 'CCM.%')
            ORDER BY pt.tag_name
            """
        )
        values = _dictfetchall(cursor)

        cursor.execute(
            """
            SELECT
                pt.tag_name,
                pt.engineering_unit,
                recent.ts,
                recent.value_double,
                recent.value_text,
                recent.quality::text AS quality
            FROM process_tags pt
            CROSS JOIN LATERAL (
                SELECT ps.ts, ps.value_double, ps.value_text, ps.quality
                FROM process_samples ps
                WHERE ps.tag_id = pt.id
                  AND ps.ts >= now() - interval '60 minutes'
                ORDER BY ps.ts DESC
                LIMIT 120
            ) recent
            WHERE pt.tag_name = ANY(%s)
            ORDER BY pt.tag_name, recent.ts
            """,
            [list(TREND_TAGS)],
        )
        trends = _dictfetchall(cursor)

        cursor.execute(
            """
            SELECT
                he.event_type,
                he.source_system,
                he.area,
                e.code AS equipment_code,
                he.severity,
                he.occurred_at,
                he.payload,
                h.heat_no
            FROM heat_events he
            LEFT JOIN equipment e ON e.id = he.equipment_id
            LEFT JOIN heats h ON h.id = he.heat_id
            WHERE he.area = 'CCM' OR e.area = 'CCM'
            ORDER BY he.occurred_at DESC
            LIMIT 30
            """
        )
        events = _dictfetchall(cursor)

        cursor.execute(
            """
            SELECT
                a.alarm_code,
                a.severity::text AS severity,
                a.state::text AS state,
                a.message,
                a.active_at,
                a.cleared_at,
                e.code AS equipment_code,
                h.heat_no
            FROM alarms a
            LEFT JOIN equipment e ON e.id = a.equipment_id
            LEFT JOIN heats h ON h.id = a.heat_id
            WHERE e.area = 'CCM'
              AND a.state IN ('ACTIVE_UNACKNOWLEDGED', 'ACTIVE_ACKNOWLEDGED')
            ORDER BY a.active_at DESC
            LIMIT 20
            """
        )
        alarms = _dictfetchall(cursor)

    return Response(
        {
            "generated_at": timezone.now(),
            "equipment": equipment,
            "active_heat": active_heat,
            "values": values,
            "trends": trends,
            "events": events,
            "alarms": alarms,
            "mode": "READ_ONLY",
        }
    )
