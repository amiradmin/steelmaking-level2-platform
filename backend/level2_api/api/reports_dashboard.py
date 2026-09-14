from __future__ import annotations

from statistics import mean
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


def _safe_mean(values: list[float]) -> float | None:
    clean = [value for value in values if value is not None]
    return float(mean(clean)) if clean else None


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


@api_view(["GET"])
def reports_dashboard(request: Request) -> Response:
    """Return read-only, heat-level operational analytics from Level 2 records."""
    require_app_permission(request.user, "reports.view")

    try:
        limit = int(request.query_params.get("limit", "24"))
    except ValueError:
        limit = 24
    limit = max(5, min(limit, 50))
    requested_heat = (request.query_params.get("heat_no") or "").strip()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                h.id::text AS heat_id,
                h.heat_no,
                h.status::text AS status,
                sg.code AS grade_code,
                h.planned_weight_t::double precision AS planned_weight_t,
                h.actual_weight_t::double precision AS actual_weight_t,
                h.started_at,
                h.completed_at,
                h.updated_at,
                CASE
                    WHEN h.started_at IS NULL THEN NULL
                    ELSE EXTRACT(EPOCH FROM (COALESCE(h.completed_at, now()) - h.started_at)) / 60.0
                END::double precision AS cycle_minutes,
                COALESCE(stages.eaf_minutes, 0)::double precision AS eaf_minutes,
                COALESCE(stages.lf_minutes, 0)::double precision AS lf_minutes,
                COALESCE(stages.ccm_minutes, 0)::double precision AS ccm_minutes,
                COALESCE(materials.material_tonnes_equiv, 0)::double precision AS material_tonnes_equiv,
                COALESCE(materials.material_additions, 0)::integer AS material_additions,
                COALESCE(alarms.alarm_count, 0)::integer AS alarm_count,
                COALESCE(alarms.high_alarm_count, 0)::integer AS high_alarm_count,
                COALESCE(samples.total_samples, 0)::bigint AS total_samples,
                COALESCE(samples.good_samples, 0)::bigint AS good_samples,
                power.avg_eaf_power_mw::double precision AS avg_eaf_power_mw
            FROM heats h
            LEFT JOIN steel_grades sg ON sg.id = h.grade_id
            LEFT JOIN LATERAL (
                SELECT
                    COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(hs.ended_at, now()) - hs.started_at)) / 60.0)
                        FILTER (WHERE upper(hs.stage) = 'EAF'), 0) AS eaf_minutes,
                    COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(hs.ended_at, now()) - hs.started_at)) / 60.0)
                        FILTER (WHERE upper(hs.stage) = 'LF'), 0) AS lf_minutes,
                    COALESCE(SUM(EXTRACT(EPOCH FROM (COALESCE(hs.ended_at, now()) - hs.started_at)) / 60.0)
                        FILTER (WHERE upper(hs.stage) IN ('CCM', 'CASTING')), 0) AS ccm_minutes
                FROM heat_stages hs
                WHERE hs.heat_id = h.id
            ) stages ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    COALESCE(SUM(
                        CASE
                            WHEN lower(mc.unit) IN ('t', 'ton', 'tons', 'tonne', 'tonnes') THEN mc.quantity::double precision
                            WHEN lower(mc.unit) IN ('kg', 'kilogram', 'kilograms') THEN mc.quantity::double precision / 1000.0
                            ELSE 0
                        END
                    ), 0) AS material_tonnes_equiv,
                    COUNT(*) AS material_additions
                FROM material_consumptions mc
                WHERE mc.heat_id = h.id
            ) materials ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) AS alarm_count,
                    COUNT(*) FILTER (WHERE a.severity::text IN ('HIGH', 'CRITICAL')) AS high_alarm_count
                FROM alarms a
                WHERE a.heat_id = h.id
            ) alarms ON TRUE
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) AS total_samples,
                    COUNT(*) FILTER (WHERE ps.quality::text = 'GOOD') AS good_samples
                FROM process_samples ps
                WHERE ps.heat_id = h.id
            ) samples ON TRUE
            LEFT JOIN LATERAL (
                SELECT AVG(ps.value_double) AS avg_eaf_power_mw
                FROM process_samples ps
                JOIN process_tags pt ON pt.id = ps.tag_id
                WHERE ps.heat_id = h.id
                  AND pt.tag_name = 'EAF.PowerMW'
                  AND ps.quality::text = 'GOOD'
                  AND ps.value_double IS NOT NULL
            ) power ON TRUE
            ORDER BY
                CASE WHEN h.status NOT IN ('COMPLETED', 'ABORTED', 'CANCELLED') THEN 0 ELSE 1 END,
                COALESCE(h.updated_at, h.created_at) DESC
            LIMIT %s
            """,
            [limit],
        )
        heat_rows = _dictfetchall(cursor)

        heat_id_by_no: dict[str, str] = {}
        for row in heat_rows:
            heat_id = str(row["heat_id"])
            heat_no = str(row["heat_no"])
            heat_id_by_no[heat_no] = heat_id

            eaf_minutes = _as_float(row.get("eaf_minutes")) or 0.0
            avg_power_mw = _as_float(row.get("avg_eaf_power_mw"))
            energy_mwh = avg_power_mw * (eaf_minutes / 60.0) if avg_power_mw is not None and eaf_minutes > 0 else None
            weight_t = _as_float(row.get("actual_weight_t")) or _as_float(row.get("planned_weight_t"))
            specific_energy = energy_mwh * 1000.0 / weight_t if energy_mwh is not None and weight_t and weight_t > 0 else None
            total_samples = int(row.get("total_samples") or 0)
            good_samples = int(row.get("good_samples") or 0)

            row["eaf_energy_mwh_est"] = energy_mwh
            row["specific_energy_kwh_t_est"] = specific_energy
            row["good_quality_pct"] = (good_samples * 100.0 / total_samples) if total_samples else None
            row.pop("heat_id", None)

        selected_no = requested_heat if requested_heat in heat_id_by_no else (str(heat_rows[0]["heat_no"]) if heat_rows else "")
        selected_heat = next((row for row in heat_rows if row["heat_no"] == selected_no), None)
        selected_heat_id = heat_id_by_no.get(selected_no)

        stage_breakdown: list[dict[str, Any]] = []
        top_materials: list[dict[str, Any]] = []
        alarm_severity: list[dict[str, Any]] = []

        if selected_heat_id:
            cursor.execute(
                """
                SELECT
                    hs.stage,
                    COALESCE(e.code, 'UNASSIGNED') AS equipment_code,
                    hs.status,
                    hs.started_at,
                    hs.ended_at,
                    (EXTRACT(EPOCH FROM (COALESCE(hs.ended_at, now()) - hs.started_at)) / 60.0)::double precision AS duration_minutes
                FROM heat_stages hs
                LEFT JOIN equipment e ON e.id = hs.equipment_id
                WHERE hs.heat_id = %s::uuid
                ORDER BY hs.started_at
                """,
                [selected_heat_id],
            )
            stage_breakdown = _dictfetchall(cursor)

            cursor.execute(
                """
                SELECT
                    mc.material_code,
                    COALESCE(MAX(mc.material_name), mc.material_code) AS material_name,
                    COUNT(*)::integer AS additions,
                    SUM(
                        CASE
                            WHEN lower(mc.unit) IN ('t', 'ton', 'tons', 'tonne', 'tonnes') THEN mc.quantity::double precision
                            WHEN lower(mc.unit) IN ('kg', 'kilogram', 'kilograms') THEN mc.quantity::double precision / 1000.0
                            ELSE 0
                        END
                    )::double precision AS tonnes_equivalent
                FROM material_consumptions mc
                WHERE mc.heat_id = %s::uuid
                GROUP BY mc.material_code
                ORDER BY tonnes_equivalent DESC, mc.material_code
                LIMIT 12
                """,
                [selected_heat_id],
            )
            top_materials = _dictfetchall(cursor)

            cursor.execute(
                """
                SELECT a.severity::text AS severity, COUNT(*)::integer AS count
                FROM alarms a
                WHERE a.heat_id = %s::uuid
                GROUP BY a.severity
                ORDER BY CASE a.severity::text
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH' THEN 2
                    WHEN 'WARNING' THEN 3
                    ELSE 4
                END
                """,
                [selected_heat_id],
            )
            alarm_severity = _dictfetchall(cursor)

    completed_rows = [row for row in heat_rows if row["status"] == "COMPLETED"]
    cycle_values = [float(row["cycle_minutes"]) for row in completed_rows if row.get("cycle_minutes") is not None]
    eaf_values = [float(row["eaf_minutes"]) for row in heat_rows if float(row.get("eaf_minutes") or 0) > 0]
    lf_values = [float(row["lf_minutes"]) for row in heat_rows if float(row.get("lf_minutes") or 0) > 0]
    ccm_values = [float(row["ccm_minutes"]) for row in heat_rows if float(row.get("ccm_minutes") or 0) > 0]
    specific_values = [float(row["specific_energy_kwh_t_est"]) for row in heat_rows if row.get("specific_energy_kwh_t_est") is not None]
    quality_values = [float(row["good_quality_pct"]) for row in heat_rows if row.get("good_quality_pct") is not None]

    summary = {
        "heat_count": len(heat_rows),
        "completed_heats": len(completed_rows),
        "avg_cycle_minutes": _safe_mean(cycle_values),
        "avg_eaf_minutes": _safe_mean(eaf_values),
        "avg_lf_minutes": _safe_mean(lf_values),
        "avg_ccm_minutes": _safe_mean(ccm_values),
        "avg_specific_energy_kwh_t_est": _safe_mean(specific_values),
        "total_material_tonnes_equiv": float(sum(float(row.get("material_tonnes_equiv") or 0) for row in heat_rows)),
        "total_alarms": int(sum(int(row.get("alarm_count") or 0) for row in heat_rows)),
        "high_alarms": int(sum(int(row.get("high_alarm_count") or 0) for row in heat_rows)),
        "avg_good_quality_pct": _safe_mean(quality_values),
    }

    return Response(
        {
            "generated_at": timezone.now(),
            "limit": limit,
            "summary": summary,
            "heats": heat_rows,
            "selected_heat": selected_heat,
            "stage_breakdown": stage_breakdown,
            "top_materials": top_materials,
            "alarm_severity": alarm_severity,
            "energy_method": "ESTIMATE: average GOOD EAF.PowerMW samples multiplied by recorded EAF stage duration",
            "source": "LEVEL2_HISTORIAN",
            "mode": "READ_ONLY",
        }
    )
