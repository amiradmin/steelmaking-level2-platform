from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from django.db import connection
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from .rbac import require_app_permission


REAL_SOURCE_KIND = "REAL_S7"
STALE_AFTER_SECONDS = float(os.getenv("REAL_PLC_STALE_AFTER_SECONDS", "10"))


def _dictfetchall(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _latest_real_values(area: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT ON (ps.tag_id)
                pt.tag_name,
                pt.engineering_unit,
                e.code AS equipment_code,
                e.area,
                ps.value_double,
                ps.value_text,
                ps.quality::text AS quality,
                ps.ts,
                h.heat_no,
                ps.attributes->>'source_kind' AS source_kind,
                ps.attributes->>'source_endpoint' AS source_endpoint,
                ps.attributes->>'transport' AS transport,
                ps.attributes->>'node_id' AS node_id,
                ps.attributes->>'status_code' AS status_code
            FROM process_samples ps
            JOIN process_tags pt ON pt.id = ps.tag_id
            LEFT JOIN equipment e ON e.id = pt.equipment_id
            LEFT JOIN heats h ON h.id = ps.heat_id
            WHERE pt.is_active = TRUE
              AND e.area = %s
              AND ps.attributes->>'source_kind' = %s
            ORDER BY ps.tag_id, ps.ts DESC
            """,
            [area, REAL_SOURCE_KIND],
        )
        return _dictfetchall(cursor)


@api_view(["GET"])
def real_plc_latest(request: Request) -> Response:
    """Return only historian samples explicitly verified as physical S7 reads."""
    require_app_permission(request.user, "historian.view")

    area = (request.query_params.get("area") or "EAF").strip().upper()
    if not area or len(area) > 64:
        raise ValidationError({"area": "Area must be a non-empty value up to 64 characters."})

    values = sorted(_latest_real_values(area), key=lambda item: item["tag_name"])
    timestamps = [value["ts"] for value in values if isinstance(value.get("ts"), datetime)]
    latest_sample_at = max(timestamps, default=None)
    age_seconds = (
        max(0.0, (timezone.now() - latest_sample_at).total_seconds())
        if latest_sample_at is not None
        else None
    )
    source_endpoint = next(
        (value.get("source_endpoint") for value in values if value.get("source_endpoint")),
        None,
    )

    return Response(
        {
            "area": area,
            "source_kind": REAL_SOURCE_KIND,
            "verified": bool(values),
            "fresh": age_seconds is not None and age_seconds <= STALE_AFTER_SECONDS,
            "stale_after_seconds": STALE_AFTER_SECONDS,
            "age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
            "latest_sample_at": latest_sample_at,
            "source_endpoint": source_endpoint,
            "values": values,
        }
    )
