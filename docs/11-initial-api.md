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

All `/api/v1` operational endpoints require `Authorization: Bearer <access-token>`.
The health endpoint remains public for container orchestration.

### Authentication

- `POST /api/v1/auth/token` — obtain access and refresh tokens
- `POST /api/v1/auth/token/refresh` — renew an expired access token
- `POST /api/v1/auth/token/verify` — verify a token
- `GET /api/v1/auth/me` — return the authenticated operator

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
JWT_ACCESS_MINUTES=15
JWT_REFRESH_HOURS=12
DJANGO_BOOTSTRAP_USERNAME=OP-4109
DJANGO_BOOTSTRAP_PASSWORD=Level2Demo-1405
DJANGO_BOOTSTRAP_DISPLAY_NAME=Shift Operator
```

The container creates the bootstrap operator only when it does not already exist; it never resets an
existing password during restart. Production deployments must replace the development credentials and
secret, and restrict allowed hosts and CORS origins.

## Acceptance criteria

The work package is accepted locally when:

1. `steelmaking-level2-api` starts with Django/DRF and becomes healthy.
2. `/health` reports database connectivity and `api_version=v1`.
3. Valid operator credentials return an access/refresh JWT pair.
4. Anonymous operational API requests return `401`, while authenticated requests succeed.
5. `/api/v1/meta` reports `framework=django-rest-framework`.
6. Existing EAF/LF/CCM equipment and steel-grade queries remain readable.
7. An active simulated Heat can be retrieved.
8. Heat overview includes live process values and events.
9. Event, alarm and historian queries retain the previous API behavior.
10. Swagger/OpenAPI are available.
11. The JWT-aware smoke test passes.

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
- Add plant-specific roles and object-level permissions.
- Configure Django Admin for equipment, grades and configuration data.
- Add SSO as an optional enterprise identity provider alongside JWT.
- Move orchestration workflows that belong to the main platform into Django services.
- Keep real-time ingestion, simulation and focused calculation microservices in FastAPI.
