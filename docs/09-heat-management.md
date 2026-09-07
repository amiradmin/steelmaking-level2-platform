# Heat Management Core v0.1

## Purpose

The Heat Management service is the Level 2 production-state authority for heat tracking and lifecycle visibility. It provides a stable API for operator UI, reporting and future Level 3/MES integration.

It does **not** directly command Level 1 actuators, drives, valves or PLC sequences.

## Current responsibilities

- List recent and active heats
- Return complete heat master data
- Return EAF/LF/CCM stage history
- Return chronological heat events
- Return latest live process values associated with a heat
- Create a new heat against an active steel grade
- Apply validated lifecycle transitions
- Audit lifecycle changes in `heat_events`
- Expose health status for deployment monitoring

## Service

Container: `steelmaking-level2-heat-management`

Default host endpoint:

```text
http://localhost:9000
```

Interactive OpenAPI documentation:

```text
http://localhost:9000/docs
```

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service/database health |
| GET | `/heats` | List heats; optional `status` and `limit` |
| GET | `/heats/active` | List non-terminal heats |
| GET | `/heats/{heat_no}` | Heat master/detail |
| GET | `/heats/{heat_no}/timeline` | Heat stages and events |
| GET | `/heats/{heat_no}/live` | Latest process values for that heat |
| POST | `/heats` | Create a Level 2 heat |
| POST | `/heats/{heat_no}/transition` | Apply an audited lifecycle transition |

## Lifecycle states

```text
PLANNED
  ↓
CREATED
  ↓
CHARGING
  ↓
EAF
  ↓
TAPPING
  ↓
LF
  ↓
CASTING
  ↓
COMPLETED
```

`HOLD`, `ABORTED` and `CANCELLED` are supported as exception/terminal states.

## Transition rules

The API rejects invalid transitions with HTTP `409 Conflict`.

Examples:

- `EAF -> TAPPING`: valid
- `TAPPING -> LF`: valid
- `LF -> CASTING`: valid
- `CASTING -> COMPLETED`: valid
- `EAF -> COMPLETED`: invalid
- Any transition from `COMPLETED`: invalid

A successful transition creates a `STATUS_CHANGED` event containing:

- previous state
- target state
- actor
- reason
- timestamp

## Create heat example

```bash
curl -X POST http://localhost:9000/heats \
  -H 'Content-Type: application/json' \
  -d '{
    "heat_no": "L2-DEMO-001",
    "grade_code": "DEMO-ST37",
    "grade_revision": 1,
    "planned_weight_t": 80,
    "production_order_id": "PO-DEMO-001"
  }'
```

## Transition example

```bash
curl -X POST http://localhost:9000/heats/L2-DEMO-001/transition \
  -H 'Content-Type: application/json' \
  -d '{
    "target_status": "EAF",
    "actor": "operator-demo",
    "reason": "Demo transition"
  }'
```

For a heat created through the API, `CREATED -> EAF` is allowed for the current prototype. A plant-specific production workflow can later require `CHARGING` first.

## Local acceptance test

Start/rebuild the platform:

```bash
docker compose up -d --build
```

Verify all containers:

```bash
docker compose ps
```

Run:

```bash
python3 scripts/heat_management_smoke_test.py
```

Acceptance criteria:

- API health returns `ok`
- at least one active heat is visible
- heat detail resolves correctly
- heat timeline contains events
- live process values are available from the simulator/historian
- script exits with `PASS`

## Current boundaries

The current version is a pre-server/local-development implementation. The following are intentionally deferred until plant information/infrastructure is supplied:

- final production-order rules from Level 3/MES
- real PLC event reconciliation
- operator identity/authorization
- plant-specific steel-grade master synchronization
- concurrency rules for multiple EAF/LF/CCM units
- production server deployment
- SAT/commissioning
