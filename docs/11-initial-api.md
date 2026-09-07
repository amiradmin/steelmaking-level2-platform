# 11 — Level 2 REST API

## Objective

Provide a stable, versioned REST API for the Level 2 platform. The `level2-api` service is the main application boundary for operator dashboards, reporting, administration, authentication/authorization and future Level 3/MES integration.

## Framework split

The platform intentionally uses two Python web stacks for different responsibilities:

- **Django + Django REST Framework** — `level2-api`, the main platform application and public API.
- **FastAPI** — focused process/domain services such as `heat-management`, simulators and future low-latency calculation/integration services.

This keeps business administration, users, permissions and the main API in Django while retaining FastAPI for small independent services that benefit from a lightweight async-friendly runtime.

## Service

- Container: `steelmaking-level2-api`
- Framework: Django + Django REST Framework
- Production server: Gunicorn
- Local port: `8080`
- API prefix: `/api/v1`
- Django admin: `http://localhost:8080/admin/`
- Swagger: `http://localhost:8080/docs`
- OpenAPI JSON: `http://localhost:8080/openapi.json`
- Health: `GET /health`

The container applies Django migrations before Gunicorn starts. Existing steelmaking tables remain the current plant data model; the first Django migration keeps the existing SQL queries behind a repository layer so the HTTP contract does not change. Domain tables can be moved to Django ORM incrementally in later work packages.

## Endpoints

### Metadata

- `GET /api/v1/meta`

### Heats

- `GET /api/v1/heats`
- `GET /api/v1/heats/{heat_no}`
- `GET /api/v1/heats/{heat_no}/overview`

The overview aggregates Heat master/status, latest process values, material consumption, recent events and active alarms.

### Equipment and steel grades

- `GET /api/v1/equipment`
- `GET /api/v1/steel-grades`

### Events and alarms

- `GET /api/v1/events`
- `GET /api/v1/alarms`

### Historian

- `GET /api/v1/historian/latest`
- `GET /api/v1/historian/tags/{tag_name}/samples`

## Architecture boundary

```text
Operator UI / Reports / Admin / Future Level 3
                     │
                     ▼
        Django + DRF level2-api :8080
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
 PostgreSQL / TimescaleDB   FastAPI services
 plant/read model           heat-management
                            future calculators
                            integration adapters
```

The public URL contract remains `/api/v1/...` during the FastAPI-to-Django migration so dashboards and smoke tests do not require changes.

## Environment

```text
LEVEL2_API_PORT=8080
API_CORS_ORIGINS=*
DJANGO_SECRET_KEY=change-me-in-production
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=*
DB_CONN_MAX_AGE=60
```

Production deployments must replace the development secret and restrict allowed hosts and CORS origins.

## Acceptance criteria

The work package is accepted locally when:

1. `steelmaking-level2-api` starts with Django/DRF and becomes healthy.
2. `/health` reports database connectivity and `api_version=v1`.
3. `/api/v1/meta` reports `framework=django-rest-framework`.
4. Existing EAF/LF/CCM equipment and steel-grade queries remain readable.
5. An active simulated Heat can be retrieved.
6. Heat overview includes live process values and events.
7. Event, alarm and historian queries retain the previous API behavior.
8. Swagger/OpenAPI are available.
9. The existing smoke test passes unchanged.

Automated local verification:

```bash
docker compose up -d --build level2-api
python3 scripts/level2_api_smoke_test.py
```

Expected result:

```text
LEVEL 2 API SMOKE TEST
========================================================================
Result: PASS
```

## Next Django work packages

- Define Django models for master data and transactional Level 2 entities.
- Add users, plant roles and permissions.
- Configure Django Admin for equipment, grades and configuration data.
- Add JWT/SSO authentication for operator/dashboard clients.
- Move orchestration workflows that belong to the main platform into Django services.
- Keep real-time ingestion, simulation and focused calculation microservices in FastAPI.
