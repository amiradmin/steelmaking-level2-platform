"""Live service and telemetry-flow observability for the operations console."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response


FRESH_AFTER_SECONDS = 5.0
SYSTEM_MAP_USERNAME = "amiradmin"


def _iso(value: Any) -> str | None:
    """Return an ISO-8601 timestamp when the database supplied one."""
    return value.isoformat() if isinstance(value, datetime) else None


def _age_seconds(value: Any) -> float | None:
    """Return age in seconds for a timezone-aware database timestamp."""
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return max(0.0, round((datetime.now(timezone.utc) - value).total_seconds(), 2))


def _status_from_timestamp(value: Any) -> str:
    age = _age_seconds(value)
    if age is None:
        return "offline"
    if age <= FRESH_AFTER_SECONDS:
        return "online"
    if age <= FRESH_AFTER_SECONDS * 3:
        return "degraded"
    return "offline"


def _service_health(url: str) -> bool:
    """Perform a small bounded health probe over the internal Compose network."""
    try:
        with urlopen(url, timeout=1.5) as response:  # nosec B310 - fixed internal URLs
            return 200 <= response.status < 300
    except (OSError, URLError):
        return False


def _latest_controller_samples() -> dict[str, dict[str, Any]]:
    """Return current sample freshness for EAF, LF and CCM logical tags."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                CASE
                    WHEN pt.tag_name LIKE 'EAF.%%' THEN 'eaf'
                    WHEN pt.tag_name LIKE 'LF.%%' THEN 'lf'
                    WHEN pt.tag_name LIKE 'CCM.%%' THEN 'ccm'
                END AS controller,
                MAX(ps.ts) AS last_sample_at,
                COUNT(*) FILTER (
                    WHERE ps.ts >= NOW() - (%s * INTERVAL '1 second')
                ) AS samples_last_window
            FROM process_samples ps
            JOIN process_tags pt ON pt.id = ps.tag_id
            WHERE pt.tag_name LIKE 'EAF.%%'
               OR pt.tag_name LIKE 'LF.%%'
               OR pt.tag_name LIKE 'CCM.%%'
            GROUP BY 1
            """,
            [FRESH_AFTER_SECONDS],
        )
        rows = cursor.fetchall()

    result = {"eaf": {}, "lf": {}, "ccm": {}}
    for controller, last_sample_at, sample_count in rows:
        result[str(controller)] = {
            "last_sample_at": last_sample_at,
            "samples_last_window": int(sample_count),
        }
    return result


def _latest_opcua_sample() -> datetime | None:
    """Find the latest sample normalized by the OPC-UA ingestor, if enabled."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT MAX(ts)
            FROM process_samples
            WHERE attributes ->> 'source' = 'OPCUA'
            """
        )
        row = cursor.fetchone()
    return row[0] if row else None


def _node(
    identifier: str,
    label: str,
    role: str,
    status: str,
    detail: str,
    last_activity: Any = None,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "label": label,
        "role": role,
        "status": status,
        "detail": detail,
        "last_activity": _iso(last_activity),
        "age_seconds": _age_seconds(last_activity),
    }


@api_view(["GET"])
def live_system_map(request: Request) -> Response:
    """Expose service health and real telemetry movement for the live map page."""
    if request.user.get_username() != SYSTEM_MAP_USERNAME:
        raise PermissionDenied("The live system map is restricted to the system administrator.")

    controllers = _latest_controller_samples()
    opcua_last_sample = _latest_opcua_sample()
    heat_management_online = _service_health("http://heat-management:9000/health")

    controller_nodes = []
    for controller_id, label in (("eaf", "EAF PLC / S7-400"), ("lf", "LF PLC / S7-400"), ("ccm", "CCM PLC / S7-400")):
        telemetry = controllers[controller_id]
        last_sample = telemetry.get("last_sample_at")
        sample_count = telemetry.get("samples_last_window", 0)
        controller_nodes.append(
            _node(
                controller_id,
                label,
                "Level 1 controller",
                _status_from_timestamp(last_sample),
                f"{sample_count} samples in the last {int(FRESH_AFTER_SECONDS)} s",
                last_sample,
            )
        )

    opcua_status = _status_from_timestamp(opcua_last_sample)
    nodes = [
        *controller_nodes,
        _node(
            "opcua-gateway",
            "Central OPC UA Gateway",
            "Protocol aggregation",
            opcua_status,
            "Central namespace and PLC tag mapping",
            opcua_last_sample,
        ),
        _node(
            "plc-ingestor",
            "PLC Ingestor",
            "Telemetry normalization",
            opcua_status,
            "Last successful OPC-UA historian write",
            opcua_last_sample,
        ),
        _node(
            "historian",
            "Historian DB",
            "TimescaleDB",
            "online",
            "Database query is reachable",
        ),
        _node(
            "heat-management",
            "Heat Management",
            "Process lifecycle service",
            "online" if heat_management_online else "offline",
            "Internal /health probe",
        ),
        _node(
            "level2-api",
            "Level 2 API",
            "Django REST + WebSocket",
            "online",
            "This live status response is being served",
        ),
        _node(
            "nginx",
            "Nginx Gateway",
            "Reverse proxy",
            "online",
            "The browser reached the API through the application gateway",
        ),
        _node(
            "operator-console",
            "Operator Console",
            "React live dashboard",
            "online",
            "Current authenticated browser session",
        ),
    ]

    return Response(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "fresh_after_seconds": FRESH_AFTER_SECONDS,
            "nodes": nodes,
            "flows": [
                {"from": controller_id, "to": "opcua-gateway", "status": controllers[controller_id] and _status_from_timestamp(controllers[controller_id].get("last_sample_at")) or "offline", "label": "PLC telemetry"}
                for controller_id in ("eaf", "lf", "ccm")
            ]
            + [
                {"from": "opcua-gateway", "to": "plc-ingestor", "status": opcua_status, "label": "OPC UA"},
                {"from": "plc-ingestor", "to": "historian", "status": opcua_status, "label": "normalized samples"},
                {"from": "historian", "to": "heat-management", "status": "online" if heat_management_online else "offline", "label": "heat events"},
                {"from": "historian", "to": "level2-api", "status": "online", "label": "read models"},
                {"from": "level2-api", "to": "nginx", "status": "online", "label": "REST / WebSocket"},
                {"from": "nginx", "to": "operator-console", "status": "online", "label": "live UI"},
            ],
        }
    )
