# Material Tracking Acceptance Checklist

Acceptance evidence for work-plan item 10.

- [ ] `steelmaking-level2-heat-management` is healthy after rebuild.
- [ ] `POST /heats/{heat_no}/materials` returns HTTP 201.
- [ ] DRI addition is persisted.
- [ ] Scrap addition is persisted.
- [ ] Lime addition is persisted.
- [ ] `GET /heats/{heat_no}/materials` returns all additions.
- [ ] `GET /heats/{heat_no}/material-summary` returns correct totals.
- [ ] Three `MATERIAL_ADDED` events are visible in the heat timeline.
- [ ] Smoke-test heat is moved to `CANCELLED` after verification.
- [ ] `python3 scripts/material_tracking_smoke_test.py` returns `Result: PASS`.

The local PASS output should be retained as FAT/pre-commissioning evidence until plant integration is available.
