from __future__ import annotations

import json
import os
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


BASE_URL = os.getenv("HEAT_MANAGEMENT_URL", "http://127.0.0.1:8000")


def get_json(path: str):
    with urlopen(f"{BASE_URL}{path}", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_active_heat(timeout_seconds: int = 15):
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            heats = get_json("/heats/active")
            if heats:
                return heats[0]
        except (URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
        time.sleep(1)
    if last_error:
        raise RuntimeError(f"Heat Management API did not become ready: {last_error}") from last_error
    raise RuntimeError("No active heat found before timeout")


def main() -> int:
    try:
        health = get_json("/health")
        active = wait_for_active_heat()
        heat_no = active["heat_no"]
        detail = get_json(f"/heats/{heat_no}")
        timeline = get_json(f"/heats/{heat_no}/timeline")
        live = get_json(f"/heats/{heat_no}/live")

        checks = {
            "health_ok": health.get("status") == "ok",
            "active_heat_found": bool(heat_no),
            "detail_matches": detail.get("heat_no") == heat_no,
            "timeline_has_events": len(timeline.get("events", [])) >= 1,
            "live_values_available": len(live.get("values", [])) >= 2,
        }
        passed = all(checks.values())

        print("HEAT MANAGEMENT SMOKE TEST")
        print("=" * 72)
        print(f"Result: {'PASS' if passed else 'FAIL'}")
        print(f"Heat:   {heat_no}")
        print(f"Status: {detail.get('status')}")
        print(f"Events: {len(timeline.get('events', []))}")
        print(f"Live values: {len(live.get('values', []))}")
        for name, ok in checks.items():
            print(f"  {'OK' if ok else 'FAIL':4} {name}")

        if live.get("values"):
            print("\nLatest process values:")
            for item in live["values"]:
                value = item.get("value_double")
                if value is None:
                    value = item.get("value_text")
                print(
                    f"  {item['tag_name']:<28} {str(value):>10} "
                    f"{item.get('engineering_unit') or '':<10} {item['quality']}"
                )
        return 0 if passed else 1
    except Exception as exc:
        print(f"Heat Management smoke test ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
