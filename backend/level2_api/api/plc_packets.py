from __future__ import annotations

import json
import os
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .rbac import require_app_permission

CAPTURE_PATH = Path(os.getenv("PLC_PACKET_CAPTURE_PATH", "/capture/plc_packets.json"))
REAL_PLC_PROBE_TTL_SECONDS = max(
    2.0,
    float(os.getenv("REAL_PLC_PROBE_TTL_SECONDS", "3")),
)
_REAL_PROBE_LOCK = threading.Lock()
_REAL_PROBE_CACHE: dict[str, Any] = {"at": 0.0, "entry": None}


def _limit(request: Request) -> int:
    try:
        return max(1, min(20, int(request.query_params.get("limit", "6"))))
    except ValueError:
        return 6


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _hex(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def _cotp_connection_request(rack: int, slot: int) -> bytes:
    """Build the standard ISO-on-TCP COTP connect request used by S7 clients.

    This is a session-negotiation frame only. It does not address PLC memory and
    cannot write process values.
    """
    remote_tsap_low = ((rack & 0x07) << 5) | (slot & 0x1F)
    cotp = bytes(
        [
            0x11,
            0xE0,
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0xC1,
            0x02,
            0x01,
            0x00,
            0xC2,
            0x02,
            0x01,
            remote_tsap_low,
            0xC0,
            0x01,
            0x0A,
        ]
    )
    length = len(cotp) + 4
    return bytes([0x03, 0x00, (length >> 8) & 0xFF, length & 0xFF]) + cotp


def _s7_setup_communication() -> bytes:
    """Build an S7 Setup Communication job.

    The request only negotiates PDU/session parameters. It contains no read or
    write variable item and therefore performs no PLC memory access.
    """
    return bytes.fromhex(
        "03 00 00 19 "
        "02 F0 80 "
        "32 01 00 00 00 01 00 08 00 00 "
        "F0 00 00 01 00 01 01 E0"
    )


def _packet(
    *,
    sequence: int,
    captured_at: str,
    plc_host: str,
    plc_port: int,
    local_ip: str,
    local_port: int,
    raw: bytes,
    phase: str,
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "captured_at": captured_at,
        "controller": "REAL",
        "direction": "PLC_TO_GATEWAY",
        "src_ip": plc_host,
        "src_port": plc_port,
        "dst_ip": local_ip,
        "dst_port": local_port,
        "payload_length": len(raw),
        "protocol": "S7 / ISO-on-TCP",
        "phase": phase,
        "raw_hex": _hex(raw),
    }


def _probe_real_plc() -> dict[str, Any]:
    """Capture real PLC responses to a read-only S7 session negotiation.

    The probe sends only COTP Connect and S7 Setup Communication. It never sends
    Read Var, Write Var, control, force, start, stop, or memory-write requests.
    """
    host = os.getenv("REAL_PLC_HOST", "192.168.1.10").strip() or "192.168.1.10"
    port = _env_int("REAL_PLC_PORT", 102)
    rack = _env_int("REAL_PLC_RACK", 0)
    slot = _env_int("REAL_PLC_SLOT", 3)
    timeout = max(0.5, float(os.getenv("REAL_PLC_PROBE_TIMEOUT_SECONDS", "1.5")))

    packets: list[dict[str, Any]] = []
    error: str | None = None
    local_ip = "—"
    local_port = 0

    try:
        with socket.create_connection((host, port), timeout=timeout) as client:
            client.settimeout(timeout)
            local_ip, local_port = client.getsockname()[:2]

            client.sendall(_cotp_connection_request(rack, slot))
            cotp_response = client.recv(4096)
            if cotp_response:
                packets.append(
                    _packet(
                        sequence=1,
                        captured_at=datetime.now(timezone.utc).isoformat(),
                        plc_host=host,
                        plc_port=port,
                        local_ip=str(local_ip),
                        local_port=int(local_port),
                        raw=cotp_response,
                        phase="COTP_CONNECT_CONFIRM",
                    )
                )

            client.sendall(_s7_setup_communication())
            setup_response = client.recv(4096)
            if setup_response:
                packets.append(
                    _packet(
                        sequence=2,
                        captured_at=datetime.now(timezone.utc).isoformat(),
                        plc_host=host,
                        plc_port=port,
                        local_ip=str(local_ip),
                        local_port=int(local_port),
                        raw=setup_response,
                        phase="S7_SETUP_COMM_ACK",
                    )
                )
    except OSError as exc:
        error = f"{type(exc).__name__}: {exc}"

    packets.reverse()  # newest response first, matching the passive capture list
    return {
        "host": host,
        "resolved_ip": host,
        "rack": rack,
        "slot": slot,
        "read_only": True,
        "probe_mode": "READ_ONLY_S7_SESSION_NEGOTIATION",
        "error": error,
        "packets": packets,
    }


def _real_plc_entry() -> dict[str, Any]:
    now = time.monotonic()
    with _REAL_PROBE_LOCK:
        cached = _REAL_PROBE_CACHE.get("entry")
        cached_at = float(_REAL_PROBE_CACHE.get("at", 0.0))
        if isinstance(cached, dict) and now - cached_at < REAL_PLC_PROBE_TTL_SECONDS:
            return cached

        entry = _probe_real_plc()
        _REAL_PROBE_CACHE["at"] = time.monotonic()
        _REAL_PROBE_CACHE["entry"] = entry
        return entry


@api_view(["GET"])
def plc_packets(request: Request) -> Response:
    """Return a small read-only window of recent TCP/102 packets for diagnostics."""
    require_app_permission(request.user, "plc.diagnostics")

    limit = _limit(request)
    payload: dict[str, Any] = {}
    try:
        payload = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}

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

    real_entry = _real_plc_entry()
    real_packets = real_entry.get("packets")
    trimmed["REAL"] = {
        **real_entry,
        "packets": real_packets[:limit] if isinstance(real_packets, list) else [],
    }

    generated_at = datetime.now(timezone.utc).isoformat()
    return Response(
        {
            "available": bool(trimmed),
            "capture_mode": "PASSIVE_SIMULATORS_PLUS_READ_ONLY_REAL_PLC_S7_PROBE",
            "generated_at": generated_at,
            "controllers": trimmed,
        }
    )
