from __future__ import annotations

from typing import Any

from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response

from .rbac import require_app_permission


def _dictfetchall(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


@api_view(["GET"])
def heat_timeline(request: Request, heat_no: str) -> Response:
    """Return the complete read-only lifecycle evidence for one heat.

    Unlike the compact heat overview, this endpoint intentionally returns the
    complete ordered event history plus persisted heat-stage rows so the UI can
    derive exact stage boundaries from real lifecycle events rather than from
    the heat's current status alone.
    """
    require_app_permission(request.user, "production.view")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, heat_no, status::text AS status, started_at, completed_at, updated_at
            FROM heats
            WHERE heat_no = %s
            """,
            [heat_no],
        )
        row = cursor.fetchone()
        if row is None:
            raise NotFound(detail=f"Heat {heat_no} not found")
        heat_id, _, status, started_at, completed_at, updated_at = row

        cursor.execute(
            """
            SELECT
                hs.stage,
                e.code AS equipment_code,
                hs.status,
                hs.started_at,
                hs.ended_at,
                hs.attributes
            FROM heat_stages hs
            LEFT JOIN equipment e ON e.id = hs.equipment_id
            WHERE hs.heat_id = %s
            ORDER BY hs.started_at, hs.created_at
            """,
            [heat_id],
        )
        stages = _dictfetchall(cursor)

        cursor.execute(
            """
            SELECT
                he.event_type,
                he.source_system,
                he.source_event_id,
                he.area,
                e.code AS equipment_code,
                he.severity,
                he.occurred_at,
                he.payload
            FROM heat_events he
            LEFT JOIN equipment e ON e.id = he.equipment_id
            WHERE he.heat_id = %s
            ORDER BY he.occurred_at, he.created_at
            """,
            [heat_id],
        )
        events = _dictfetchall(cursor)

    return Response(
        {
            "heat_no": heat_no,
            "status": status,
            "started_at": started_at,
            "completed_at": completed_at,
            "updated_at": updated_at,
            "stages": stages,
            "events": events,
            "source": "HEAT_STAGES_AND_LIFECYCLE_EVENTS",
        }
    )
