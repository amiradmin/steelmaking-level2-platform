from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


BASE_URL = "http://localhost:8000"


def request_json(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {body}") from exc


def main() -> int:
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    heat_no = f"MT-SMOKE-{suffix}"

    checks: dict[str, bool] = {}

    health = request_json("GET", "/health")
    checks["health_ok"] = health.get("status") == "ok"

    created = request_json(
        "POST",
        "/heats",
        {
            "heat_no": heat_no,
            "grade_code": "DEMO-ST37",
            "grade_revision": 1,
            "planned_weight_t": 80,
            "production_order_id": f"MT-SMOKE-PO-{suffix}",
            "attributes": {"smoke_test": "material_tracking"},
        },
    )
    checks["heat_created"] = created.get("heat_no") == heat_no and created.get("status") == "CREATED"

    additions = [
        {
            "material_code": "DRI",
            "material_name": "Direct Reduced Iron",
            "quantity": 62.5,
            "unit": "t",
            "equipment_code": "EAF-01",
            "batch_no": f"DRI-{suffix}",
            "source_system": "SMOKE_TEST",
            "actor": "material-tracking-smoke-test",
        },
        {
            "material_code": "SCRAP",
            "material_name": "Steel Scrap",
            "quantity": 18.0,
            "unit": "t",
            "equipment_code": "EAF-01",
            "batch_no": f"SCRAP-{suffix}",
            "source_system": "SMOKE_TEST",
            "actor": "material-tracking-smoke-test",
        },
        {
            "material_code": "LIME",
            "material_name": "Lime",
            "quantity": 2.6,
            "unit": "t",
            "equipment_code": "EAF-01",
            "batch_no": f"LIME-{suffix}",
            "source_system": "SMOKE_TEST",
            "actor": "material-tracking-smoke-test",
        },
    ]

    created_items = []
    for item in additions:
        created_items.append(request_json("POST", f"/heats/{heat_no}/materials", item))

    checks["three_additions_created"] = len(created_items) == 3
    checks["equipment_linked"] = all(item.get("equipment_code") == "EAF-01" for item in created_items)

    items_response = request_json("GET", f"/heats/{heat_no}/materials")
    items = items_response.get("items", [])
    checks["three_items_listed"] = len(items) == 3

    summary = request_json("GET", f"/heats/{heat_no}/material-summary")
    materials = {row["material_code"]: row for row in summary.get("materials", [])}
    checks["summary_count"] = summary.get("total_additions") == 3
    checks["dri_total"] = abs(materials.get("DRI", {}).get("total_quantity", 0) - 62.5) < 1e-6
    checks["scrap_total"] = abs(materials.get("SCRAP", {}).get("total_quantity", 0) - 18.0) < 1e-6
    checks["lime_total"] = abs(materials.get("LIME", {}).get("total_quantity", 0) - 2.6) < 1e-6

    timeline = request_json("GET", f"/heats/{heat_no}/timeline")
    material_events = [event for event in timeline.get("events", []) if event.get("event_type") == "MATERIAL_ADDED"]
    checks["audit_events_created"] = len(material_events) == 3

    cancelled = request_json(
        "POST",
        f"/heats/{heat_no}/transition",
        {
            "target_status": "CANCELLED",
            "reason": "Material tracking smoke test completed",
            "actor": "material-tracking-smoke-test",
        },
    )
    checks["test_heat_cancelled"] = cancelled.get("status") == "CANCELLED"

    passed = all(checks.values())

    print("MATERIAL TRACKING SMOKE TEST")
    print("=" * 72)
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    print(f"Heat:   {heat_no}")
    print(f"Items:  {len(items)}")
    print(f"Events: {len(material_events)}")
    print()
    for name, ok in checks.items():
        print(f"  {'OK  ' if ok else 'FAIL'} {name}")

    print("\nMaterial summary:")
    for row in summary.get("materials", []):
        print(
            f"  {row['material_code']:<12} "
            f"{row['total_quantity']:>8.3f} {row['unit']:<6} "
            f"additions={row['additions']}"
        )

    return 0 if passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
