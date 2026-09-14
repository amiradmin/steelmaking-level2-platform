from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response


SYSTEM_MAP_USERNAME = "amiradmin"
CAPTURE_PATH = Path(os.getenv("PLC_PACKET_CAPTURE_PATH", "/capture/plc_packets.json"))


def _limit(request: Request) -> int:
    try:
        return max(1, min(20, int(request.query_params.get("limit", "6"))))
    except ValueError:
        return 6


@api_view(["GET"])
def plc_packets(request: Request) -> Response:
    """Return a small read-only window of recent TCP/102 packets for diagnostics."""
    if request.user.get_username() != SYSTEM_MAP_USERNAME:
        raise PermissionDenied("Raw PLC traffic is restricted to the system administrator.")

    limit = _limit(request)
    try:
        payload: dict[str, Any] = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Response(
            {
                "available": False,
                "capture_mode": "PASSIVE_TCPDUMP_TCP_102",
                "generated_at": None,
                "controllers": {},
            }
        )

    controllers = payload.get("controllers")
    if not isinstance(controllers, dict):
        controllers = {}

    trimmed: dict[str, Any] = {}
    for name in ("EAF", "LF", "CCM"):
        entry = controllers.get(name)
        if not isinstance(entry, dict):
            continue
        packets = entry.get("packets")
        trimmed[name] = {
            "host": entry.get("host"),
            "resolved_ip": entry.get("resolved_ip"),
            "packets": packets[:limit] if isinstance(packets, list) else [],
        }

    return Response(
        {
            "available": True,
            "capture_mode": payload.get("capture_mode", "PASSIVE_TCPDUMP_TCP_102"),
            "generated_at": payload.get("generated_at"),
            "controllers": trimmed,
        }
    )
