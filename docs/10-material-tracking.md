# Material Tracking v0.1

## Purpose

Material Tracking records material additions against a specific steelmaking heat and preserves enough context for production reporting, traceability, consumption KPIs and later Level 1/Level 3 reconciliation.

This milestone is intentionally deployable on the local pre-server environment and uses the existing `material_consumptions` table. No new database migration is required for an already initialized development volume.

## Scope

The v0.1 implementation supports:

- heat-linked material addition records
- EAF/LF/CCM equipment linkage when an equipment code is known
- material code and descriptive name
- quantity and engineering unit
- batch/lot number
- addition timestamp
- source-system identity
- actor and extensible JSON attributes
- detailed material-consumption history by heat
- optional material-code filtering
- aggregated material summary by material and unit
- audit event generation for each material addition

## API

### Add material

`POST /heats/{heat_no}/materials`

Example request:

```json
{
  "material_code": "DRI",
  "material_name": "Direct Reduced Iron",
  "quantity": 62.5,
  "unit": "t",
  "equipment_code": "EAF-01",
  "batch_no": "DRI-BATCH-001",
  "source_system": "LEVEL2_MATERIAL_TRACKING",
  "actor": "operator-01"
}
```

Each successful addition also creates a `MATERIAL_ADDED` event in `heat_events`.

### List heat materials

`GET /heats/{heat_no}/materials`

Optional query parameters:

- `material_code`
- `limit`

### Material summary

`GET /heats/{heat_no}/material-summary`

The response groups consumption by `material_code` and `unit` and returns:

- total quantity
- number of additions
- first addition time
- last addition time
- overall addition count for the heat

## Initial material coverage

The data model is generic and can already represent typical steelmaking materials including:

- DRI
- Scrap
- Lime
- Dolomite
- Carbon
- Ferro Manganese
- Ferro Silicon
- Ferro Chrome
- Aluminum
- Fluxes and other plant-defined materials

No hard-coded material catalog is imposed in v0.1 because the authoritative plant material master is expected to come from the client/Level 3 interface in a later integration phase.

## Auditability

A material addition creates both:

1. a durable row in `material_consumptions`
2. a `MATERIAL_ADDED` row in `heat_events`

The event payload includes material code, quantity, unit, batch number, equipment and actor so the operation can be reconstructed from the heat timeline.

## Acceptance test

After updating and rebuilding the local environment:

```bash
git pull origin main
docker compose up -d --build
python3 scripts/material_tracking_smoke_test.py
```

The smoke test:

1. verifies Heat Management health
2. creates an isolated test heat
3. records DRI, Scrap and Lime additions
4. verifies detailed material rows
5. verifies aggregated quantities
6. verifies three `MATERIAL_ADDED` audit events
7. cancels the test heat so it does not interfere with the live simulator

Expected result:

```text
MATERIAL TRACKING SMOKE TEST
========================================================================
Result: PASS
...
  OK   three_additions_created
  OK   summary_count
  OK   audit_events_created
  OK   test_heat_cancelled
```

## Production boundary

This milestone does not yet include:

- authoritative material master synchronization from Level 3/MES
- silo/bin/weighing-system reconciliation
- automatic Level 1 material-event ingestion
- inventory balance
- supplier/lot quality linkage
- recipe-vs-actual variance
- unit-conversion master data

Those functions require plant interface specifications and/or client master data and are later integration work.

## Deliverable status

**Work-plan item 10 — Material Tracking: implemented for local Level 2 development and ready for smoke-test acceptance.**
