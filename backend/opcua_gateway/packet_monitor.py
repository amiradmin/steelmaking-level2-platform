from __future__ import annotations

import json
import os
import re
import socket
import subprocess
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CAPTURE_PATH = Path(os.getenv("PLC_PACKET_CAPTURE_PATH", "/capture/plc_packets.json"))
RING_SIZE = max(5, min(100, int(os.getenv("PLC_PACKET_RING_SIZE", "30"))))

CONTROLLERS = {
    "EAF": os.getenv("EAF_PLC_HOST", "eaf-plc-simulator").strip() or "eaf-plc-simulator",
    "LF": os.getenv("LF_PLC_HOST", "lf-plc-simulator").strip() or "lf-plc-simulator",
    "CCM": os.getenv("CCM_PLC_HOST", "ccm-plc-simulator").strip() or "ccm-plc-simulator",
}

HEADER_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}\.\d+) "
    r"(?:(?:\S+)\s+(?:In|Out)\s+)?IP "
    r"(?P<src>\d+\.\d+\.\d+\.\d+)\.(?P<src_port>\d+) > "
    r"(?P<dst>\d+\.\d+\.\d+\.\d+)\.(?P<dst_port>\d+):"
)
LENGTH_RE = re.compile(r"\blength (?P<length>\d+)\b")
HEX_RE = re.compile(r"^\s*0x[0-9a-fA-F]+:\s+(?P<hex>(?:[0-9a-fA-F]{4}\s*)+)")


def resolve_hosts() -> dict[str, str]:
    result: dict[str, str] = {}
    for controller, host in CONTROLLERS.items():
        try:
            result[controller] = socket.gethostbyname(host)
        except OSError:
            pass
    return result


def compact_hex(words: list[str]) -> str:
    raw = "".join(words).replace(" ", "")
    return " ".join(raw[index : index + 2].upper() for index in range(0, len(raw), 2))


def persist(packets: dict[str, deque[dict[str, Any]]], resolved: dict[str, str]) -> None:
    CAPTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "capture_mode": "PASSIVE_TCPDUMP_TCP_102",
        "controllers": {
            name: {
                "host": CONTROLLERS[name],
                "resolved_ip": resolved.get(name),
                "packets": list(items),
            }
            for name, items in packets.items()
        },
    }
    temporary = CAPTURE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    temporary.replace(CAPTURE_PATH)


def main() -> None:
    packets = {name: deque(maxlen=RING_SIZE) for name in CONTROLLERS}
    resolved = resolve_hosts()
    sequence = 0
    current: dict[str, Any] | None = None
    hex_words: list[str] = []

    process = subprocess.Popen(
        [
            "tcpdump",
            "-i",
            "any",
            "-nn",
            "-tttt",
            "-s",
            "0",
            "-l",
            "-XX",
            "tcp",
            "port",
            "102",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    if process.stdout is None:
        raise RuntimeError("tcpdump stdout is unavailable")

    def finish_packet() -> None:
        nonlocal current, hex_words, sequence, resolved
        if current is None:
            return
        resolved = resolve_hosts()
        controller = next(
            (
                name
                for name, ip in resolved.items()
                if current["src_ip"] == ip or current["dst_ip"] == ip
            ),
            None,
        )
        if controller is not None:
            sequence += 1
            plc_ip = resolved.get(controller)
            current["sequence"] = sequence
            current["controller"] = controller
            current["direction"] = (
                "PLC_TO_GATEWAY" if current["src_ip"] == plc_ip else "GATEWAY_TO_PLC"
            )
            current["protocol"] = "S7 / ISO-on-TCP"
            current["raw_hex"] = compact_hex(hex_words)
            packets[controller].appendleft(current)
            persist(packets, resolved)
        current = None
        hex_words = []

    for line in process.stdout:
        header = HEADER_RE.match(line)
        if header:
            finish_packet()
            length_match = LENGTH_RE.search(line)
            current = {
                "captured_at": f"{header.group('date')}T{header.group('time')}Z",
                "src_ip": header.group("src"),
                "src_port": int(header.group("src_port")),
                "dst_ip": header.group("dst"),
                "dst_port": int(header.group("dst_port")),
                "payload_length": int(length_match.group("length")) if length_match else 0,
            }
            continue
        hex_match = HEX_RE.match(line)
        if hex_match and current is not None:
            hex_words.append(hex_match.group("hex"))

    finish_packet()


if __name__ == "__main__":
    main()
