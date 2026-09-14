from __future__ import annotations

from typing import Any

from django.db import connection
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .rbac import require_app_permission


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
def materials_dashboard(request: Request) -> Response:
    """Return the read-only material and charging record for a selected heat."""
    require_app_permission(request.user, "production.view")
    requested_heat = (request.query_params.get("heat_no") or "").strip()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                h.heat_no,
                h.status::text AS status,
                sg.code AS grade_code,
                h.planned_weight_t,
                h.actual_weight_t,
                h.started_at,
                h.completed_at,
                h.updated_at,
                COUNT(mc.id)::integer AS material_additions,
                COALESCE(SUM(mc.quantity) FILTER (
                    WHERE lower(mc.unit) IN ('t', 'ton', 'tons', 'tonne', 'tonnes')
                ), 0)::double precision AS total_tonnes,
                COALESCE(SUM(mc.quantity) FILTER (
                    WHERE lower(mc.unit) IN ('kg', 'kilogram', 'kilograms')
                ), 0)::double precision AS total_kg
            FROM heats h
            LEFT JOIN steel_grades sg ON sg.id = h.grade_id
            LEFT JOIN material_consumptions mc ON mc.heat_id = h.id
            GROUP BY h.id, sg.code
            ORDER BY
                CASE WHEN h.status NOT IN ('COMPLETED', 'ABORTED', 'CANCELLED') THEN 0 ELSE 1 END,
                h.updated_at DESC
            LIMIT 50
            """
        )
        heats = _dictfetchall(cursor)

        selected_heat: dict[str, Any] | None = None
        selected_no = requested_heat or (str(heats[0]["heat_no"]) if heats else "")
        if selected_no:
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
                    h.completed_at,
                    h.updated_at
                FROM heats h
                LEFT JOIN steel_grades sg ON sg.id = h.grade_id
                WHERE h.heat_no = %s
                LIMIT 1
                """,
                [selected_no],
            )
            selected_heat = _dictfetchone(cursor)

        if selected_heat is None:
            return Response(
                {
                    "generated_at": timezone.now(),
                    "selected_heat": None,
                    "heats": heats,
                    "summary": [],
                    "additions": [],
                    "equipment_totals": [],
                    "source": "MATERIAL_CONSUMPTIONS",
                    "mode": "READ_ONLY",
                }
            )

        heat_id = selected_heat["id"]

        cursor.execute(
            """
            SELECT
                mc.material_code,
                COALESCE(MAX(mc.material_name), mc.material_code) AS material_name,
                mc.unit,
                SUM(mc.quantity)::double precision AS total_quantity,
                COUNT(*)::integer AS additions,
                MIN(mc.addition_time) AS first_addition_at,
                MAX(mc.addition_time) AS last_addition_at
            FROM material_consumptions mc
            WHERE mc.heat_id = %s
            GROUP BY mc.material_code, mc.unit
            ORDER BY SUM(mc.quantity) DESC, mc.material_code
            """,
            [heat_id],
        )
        summary = _dictfetchall(cursor)

        cursor.execute(
            """
            SELECT
                mc.id,
                mc.material_code,
                mc.material_name,
                mc.quantity::double precision AS quantity,
                mc.unit,
                mc.addition_time,
                mc.source_system,
                mc.batch_no,
                mc.attributes,
                e.code AS equipment_code,
                e.area AS equipment_area
            FROM material_consumptions mc
            LEFT JOIN equipment e ON e.id = mc.equipment_id
            WHERE mc.heat_id = %s
            ORDER BY mc.addition_time DESC, mc.created_at DESC
            LIMIT 500
            """,
            [heat_id],
        )
        additions = _dictfetchall(cursor)

        cursor.execute(
            """
            SELECT
                COALESCE(e.code, 'UNASSIGNED') AS equipment_code,
                COALESCE(e.area, 'OTHER') AS area,
                mc.unit,
                SUM(mc.quantity)::double precision AS total_quantity,
                COUNT(*)::integer AS additions
            FROM material_consumptions mc
            LEFT JOIN equipment e ON e.id = mc.equipment_id
            WHERE mc.heat_id = %s
            GROUP BY e.code, e.area, mc.unit
            ORDER BY e.area NULLS LAST, e.code NULLS LAST, mc.unit
            """,
            [heat_id],
        )
        equipment_totals = _dictfetchall(cursor)

    selected_heat.pop("id", None)
    return Response(
        {
            "generated_at": timezone.now(),
            "selected_heat": selected_heat,
            "heats": heats,
            "summary": summary,
            "additions": additions,
            "equipment_totals": equipment_totals,
            "source": "MATERIAL_CONSUMPTIONS",
            "mode": "READ_ONLY",
        }
    )
