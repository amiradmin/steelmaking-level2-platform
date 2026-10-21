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
    """Return the latest GOOD physical sample for each tag in one process area.

    When the S7 link drops, the gateway may keep publishing cached OPC UA values
    with BadNoCommunication quality. Those values are useful diagnostically but
    must never be presented as verified live plant process data.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                pt.tag_name,
                pt.engineering_unit,
                e.code AS equipment_code,
                e.area,
                latest.value_double,
                latest.value_text,
                latest.quality::text AS quality,
                latest.ts,
                h.heat_no,
                latest.attributes->>'source_kind' AS source_kind,
                latest.attributes->>'source_endpoint' AS source_endpoint,
                latest.attributes->>'transport' AS transport,
                latest.attributes->>'node_id' AS node_id,
                latest.attributes->>'status_code' AS status_code
            FROM process_tags pt
            JOIN equipment e ON e.id = pt.equipment_id
            JOIN LATERAL (
                SELECT
                    ps.value_double,
                    ps.value_text,
                    ps.quality,
                    ps.ts,
                    ps.heat_id,
                    ps.attributes
                FROM process_samples ps
                WHERE ps.tag_id = pt.id
                  AND ps.attributes->>'source_kind' = %s
                  AND ps.quality = 'GOOD'
                ORDER BY ps.ts DESC
                LIMIT 1
            ) latest ON TRUE
            LEFT JOIN heats h ON h.id = latest.heat_id
            WHERE pt.is_active = TRUE
              AND e.area = %s
            ORDER BY pt.tag_name
            """,
            [REAL_SOURCE_KIND, area],
        )
        return _dictfetchall(cursor)


@api_view(["GET"])
def real_plc_latest(request: Request) -> Response:
    """Return only historian samples verified by successful physical S7 reads."""
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
