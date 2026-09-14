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
                lpv.tag_name,
                pt.source_system,
                pt.source_tag,
                lpv.engineering_unit,
                lpv.value_double,
                lpv.value_text,
                lpv.quality::text AS quality,
                lpv.ts,
                h.heat_no
            FROM latest_process_values lpv
            JOIN process_tags pt ON pt.id = lpv.tag_id
            LEFT JOIN equipment e ON e.id = pt.equipment_id
            LEFT JOIN heats h ON h.id = lpv.heat_id
            WHERE pt.is_active = TRUE
              AND (e.area = 'CCM' OR lpv.tag_name LIKE 'CCM.%')
            ORDER BY lpv.tag_name
            """
        )
        values = _dictfetchall(cursor)

        cursor.execute(
            """
            WITH ranked AS (
                SELECT
                    pt.tag_name,
                    pt.engineering_unit,
                    ps.ts,
                    ps.value_double,
                    ps.value_text,
                    ps.quality::text AS quality,
                    ROW_NUMBER() OVER (
                        PARTITION BY pt.tag_name
                        ORDER BY ps.ts DESC
                    ) AS rn
                FROM process_samples ps
                JOIN process_tags pt ON pt.id = ps.tag_id
                WHERE pt.tag_name = ANY(%s)
                  AND ps.ts >= now() - interval '60 minutes'
            )
            SELECT tag_name, engineering_unit, ts, value_double, value_text, quality
            FROM ranked
            WHERE rn <= 120
            ORDER BY tag_name, ts
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
