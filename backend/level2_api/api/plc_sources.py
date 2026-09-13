"""Read-only PLC source metadata for operator-facing diagnostics."""

from __future__ import annotations

import os
from typing import Any

from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _source(area: str, simulator_host: str) -> dict[str, Any]:
    host_env = os.getenv(f"{area}_PLC_HOST", "").strip()
    explicit_source = os.getenv(f"{area}_PLC_SOURCE", "").strip().lower()

    if explicit_source in {"real", "real_plc", "plant"}:
        is_real = True
    elif explicit_source in {"sim", "simulator", "test"}:
        is_real = False
    else:
        is_real = bool(host_env) and "simulator" not in host_env.lower()

    host = host_env if is_real and host_env else simulator_host
    model = os.getenv(f"{area}_PLC_MODEL", "").strip()
    if not model:
        model = "Siemens S7-400" if is_real else "S7-400 process simulator"

    return {
        "area": area,
        "source": "real" if is_real else "simulator",
        "source_label": "REAL PLC" if is_real else "SIMULATOR",
        "model": model,
        "protocol": "S7 / ISO-on-TCP",
        "host": host,
        "port": _env_int(f"{area}_PLC_PORT", 102),
        "rack": _env_int(f"{area}_PLC_RACK", 0),
        "slot": _env_int(f"{area}_PLC_SLOT", 2),
        "read_only": True,
    }


@api_view(["GET"])
def plc_sources(request: Request) -> Response:
    """Return configured Level-1 source information without exposing credentials."""
    del request
    return Response(
        {
            "sources": {
                "EAF": _source("EAF", "eaf-plc-simulator"),
                "LF": _source("LF", "lf-plc-simulator"),
                "CCM": _source("CCM", "ccm-plc-simulator"),
            }
        }
    )
