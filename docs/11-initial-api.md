# 11 — Initial Level 2 REST API

## Objective

Provide a stable, versioned REST read API for Level 2 consumers such as the operator dashboard, reporting tools and future Level 3/MES integration adapters.

The public API is implemented as a dedicated `level2-api` service. Domain write operations remain in the Heat Management service so process-state mutation is not mixed with historian and reporting reads.

## Service

- Container: `steelmaking-level2-api`
- Local port: `8080`
- API prefix: `/api/v1`
- Swagger: `http://localhost:8080/docs`
- OpenAPI JSON: `http://localhost:8080/openapi.json`
- Health: `GET /health`

## Endpoints

### Metadata

- `GET /api/v1/meta`

Returns API version, process flow and supported capabilities.

### Heats

- `GET /api/v1/heats`
- `GET /api/v1/heats/{heat_no}`
- `GET /api/v1/heats/{heat_no}/overview`

The overview endpoint aggregates:

- Heat master/status
- Latest process values
- Material consumption summary
- Recent heat events
- Active alarms

### Equipment master

- `GET /api/v1/equipment`
- Optional filter: `area=EAF|LF|CCM`

### Steel-grade master

- `GET /api/v1/steel-grades`

### Events

- `GET /api/v1/events`

Filters:

- `heat_no`
- `event_type`
- `source_system`
- `limit`

### Alarms

- `GET /api/v1/alarms`

Filters:

- `state`
- `severity`
- `heat_no`
- `limit`

### Historian latest values

- `GET /api/v1/historian/latest`

Filters:

- `area`
- `equipment_code`
- `quality`

### Historian tag samples

- `GET /api/v1/historian/tags/{tag_name}/samples`

Filters:

- `start`
- `end`
- `heat_no`
- `limit`

## Architecture boundary

```text
Dashboard / Reports / Future L3 Adapter
                 │
                 ▼
          Public Level2 API :8080
                 │
        ┌────────┴────────┐
        ▼                 ▼
 Historian/Read DB   Domain services
 PostgreSQL/         Heat Management
 TimescaleDB         :8000
```

The v0.1 public API is intentionally read-oriented. Mutation of production state remains behind domain-specific services. This reduces accidental coupling between dashboard/reporting clients and process-state changes.

## CORS

Local CORS origins are configured by:

```text
API_CORS_ORIGINS=*
```

For production, this must be restricted to approved dashboard/application origins.

## Acceptance criteria

The work package is accepted locally when:

1. `steelmaking-level2-api` is healthy.
2. `/health` reports database connectivity.
3. `/api/v1/meta` reports API version `v1`.
4. EAF/LF/CCM equipment master is readable.
5. Steel-grade master is readable.
6. An active simulated Heat can be retrieved.
7. Heat overview includes live process values and events.
8. Event query returns Heat-linked events.
9. Historian latest-value query returns live tags.
10. Historian tag-sample query returns time-series samples.
11. Alarm query responds successfully, including an empty list when there are no alarms.

Automated local verification:

```bash
python3 scripts/level2_api_smoke_test.py
```

Expected result:

```text
LEVEL 2 API SMOKE TEST
========================================================================
Result: PASS
```

## Client/site dependencies still pending

This milestone does not include:

- Authentication/SSO
- TLS termination and production reverse proxy
- Final production CORS policy
- Plant network/firewall configuration
- Level 3/MES write adapters
- Real PLC tag validation
- Production server deployment
- SAT/commissioning

Those items remain part of later site-integration and production deployment phases.
