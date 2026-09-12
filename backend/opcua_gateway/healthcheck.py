from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


HEALTH_PATH = Path(os.getenv("OPCUA_GATEWAY_HEALTH_PATH", "/tmp/opcua-gateway-health.json"))
STALE_AFTER_SECONDS = float(os.getenv("OPCUA_GATEWAY_HEALTH_STALE_AFTER_SECONDS", "10"))
REQUIRE_ALL = os.getenv("OPCUA_GATEWAY_REQUIRE_ALL_PLC", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}


def fail(message: str) -> None:
    print(message)
    raise SystemExit(1)


def main() -> None:
    if not HEALTH_PATH.exists():
        fail("health state missing")

    state = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    if not state.get("server_ready"):
        fail("OPC UA server is not ready")

    connected = state.get("connected") or {}
    if REQUIRE_ALL and (not connected or not all(connected.values())):
        fail(f"not all PLCs connected: {connected}")

    last_success_text = state.get("last_success_at")
    if not last_success_text:
        fail("no successful PLC read yet")

    last_success = datetime.fromisoformat(last_success_text)
    age = (datetime.now(timezone.utc) - last_success).total_seconds()
    if age > STALE_AFTER_SECONDS:
        fail(f"PLC data stale: {age:.1f}s")

    print("healthy")


if __name__ == "__main__":
    main()
