from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE_URL = "http://localhost:8080"
ACTIVE_STATUSES = {"EAF", "LF", "CASTING", "TAPPING", "CHARGING"}


def request_json(path: str, *, access_token: str | None = None) -> Any:
    headers = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        headers=headers,
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} GET {path}: {body}") from exc


def authenticate() -> str:
    credentials = json.dumps(
        {
            "username": os.getenv("DJANGO_BOOTSTRAP_USERNAME", "OP-4109"),
            "password": os.getenv("DJANGO_BOOTSTRAP_PASSWORD", "Level2Demo-1405"),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{BASE_URL}/api/v1/auth/token",
        data=credentials,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} POST /api/v1/auth/token: {body}") from exc
    access_token = payload.get("access")
    if not isinstance(access_token, str):
        raise RuntimeError("Authentication response did not include an access token")
    return access_token


def main() -> int:
    checks: dict[str, bool] = {}

    health = request_json("/health")
    checks["health_ok"] = health.get("status") == "ok" and health.get("api_version") == "v1"

    access_token = authenticate()
    checks["jwt_authentication"] = bool(access_token)

    meta = request_json("/api/v1/meta", access_token=access_token)
    checks["meta_ok"] = meta.get("api_version") == "v1" and "historian-latest-values" in meta.get("capabilities", [])

    equipment = request_json("/api/v1/equipment", access_token=access_token)
    equipment_codes = {row.get("code") for row in equipment}
    checks["equipment_master"] = {"EAF-01", "LF-01", "CCM-01"}.issubset(equipment_codes)

    grades = request_json("/api/v1/steel-grades", access_token=access_token)
    checks["steel_grade_master"] = any(row.get("code") == "DEMO-ST37" for row in grades)

    heats = request_json("/api/v1/heats?limit=100", access_token=access_token)
    active_heat = next((row for row in heats if row.get("status") in ACTIVE_STATUSES), None)
    checks["active_heat_found"] = active_heat is not None
    if active_heat is None:
        raise RuntimeError("No active heat found; ensure level1-simulator is running")

    heat_no = active_heat["heat_no"]
    encoded_heat = urllib.parse.quote(heat_no, safe="")
    heat = request_json(f"/api/v1/heats/{encoded_heat}", access_token=access_token)
    checks["heat_detail"] = heat.get("heat_no") == heat_no

    overview = request_json(
        f"/api/v1/heats/{encoded_heat}/overview", access_token=access_token
    )
    live_values = overview.get("live_values", [])
    recent_events = overview.get("recent_events", [])
    checks["heat_overview"] = overview.get("heat", {}).get("heat_no") == heat_no
    checks["overview_live_values"] = len(live_values) >= 1
    checks["overview_events"] = len(recent_events) >= 1

    events = request_json(
        f"/api/v1/events?heat_no={urllib.parse.quote(heat_no)}&limit=20",
        access_token=access_token,
    )
    checks["event_query"] = len(events) >= 1 and all(row.get("heat_no") == heat_no for row in events)

    latest = request_json("/api/v1/historian/latest", access_token=access_token)
    checks["historian_latest"] = len(latest) >= 4

    tag_name = live_values[0]["tag_name"] if live_values else latest[0]["tag_name"]
    encoded_tag = urllib.parse.quote(tag_name, safe="")
    samples_response = request_json(
        f"/api/v1/historian/tags/{encoded_tag}/samples?heat_no={urllib.parse.quote(heat_no)}&limit=20",
        access_token=access_token,
    )
    checks["historian_tag_samples"] = (
        samples_response.get("tag", {}).get("tag_name") == tag_name
        and len(samples_response.get("samples", [])) >= 1
    )

    alarms = request_json("/api/v1/alarms?limit=20", access_token=access_token)
    checks["alarm_query"] = isinstance(alarms, list)

    passed = all(checks.values())

    print("LEVEL 2 API SMOKE TEST")
    print("=" * 72)
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    print(f"Heat:   {heat_no}")
    print(f"Status: {active_heat['status']}")
    print(f"Latest historian values: {len(latest)}")
    print(f"Heat live values:        {len(live_values)}")
    print(f"Heat events:             {len(recent_events)}")
    print(f"Tag tested:              {tag_name}")
    print()

    for name, ok in checks.items():
        print(f"  {'OK  ' if ok else 'FAIL'} {name}")

    return 0 if passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
