# Steelmaking Level 2 Platform

Industrial Level 2 automation and production management platform for steelmaking operations, designed around **EAF → LF → CCM** process flow.

## Scope

This repository provides a pre-server engineering and executable platform foundation that can be developed and validated locally before production infrastructure is available:

- System architecture
- Level 1 / Level 2 / Level 3 interface architecture
- Database and historian design
- Heat/Event/Alarm model
- Local TimescaleDB historian
- Live EAF/LF/CCM Level 1 simulator
- Heat Management Core API
- Dockerized local development environment

## Architecture

```text
Level 3 / MES / ERP
        │
        │ REST / DB / Message Interface
        ▼
┌──────────────────────────────────────┐
│              LEVEL 2                 │
│                                      │
│  Heat Management API                 │
│  Event & Alarm Model                 │
│  Process Data / Historian            │
│  EAF / LF / CCM Services             │
│  KPI & Reporting                     │
└─────────────────┬────────────────────┘
                  │
                  │ OPC UA / S7 / TCP
                  ▼
          Level 1 Gateway
                  │
                  ▼
             PLC / DCS
```

For local development, the PLC/DCS side is currently represented by a Dockerized Level 1 simulator that generates live EAF/LF/CCM process samples and heat events.

## Current implemented baseline

1. System architecture
2. L1/L2/L3 interface architecture
3. Database architecture
4. Heat/Event/Alarm model
5. Local historian
6. Dockerization
7. Live Level 1 EAF/LF/CCM simulator
8. Heat Management Core v0.1

## Repository structure

```text
backend/                         Backend services
  heat_management/              FastAPI Heat Management service
  level1_simulator/             Live EAF/LF/CCM process simulator
  level2_api/                   Django Level 2 API
frontend/                        React/Vite operator interface
infrastructure/                  Database and reverse-proxy configuration
docs/                            Engineering and interface specifications
scripts/                         Local acceptance and smoke tests
legacy/frontend/                 Archived initial frontend scaffold
```

## Local startup

```bash
cp .env.example .env
docker compose up -d --build
```

Default services:

- PostgreSQL / TimescaleDB: `localhost:5432`
- Heat Management API: `http://localhost:9000`
- OpenAPI/Swagger: `http://localhost:9000/docs`
- Level 1 simulator: internal Docker service writing live samples to the historian

Verify containers:

```bash
docker compose ps
```

## Acceptance tests

Historian:

```bash
docker compose exec -T historian-db \
  psql -U level2 -d steelmaking_level2 \
  < infrastructure/database/smoke_test.sql
```

Level 1 simulator:

```bash
docker compose exec -T historian-db \
  psql -U level2 -d steelmaking_level2 \
  < infrastructure/database/simulator_smoke_test.sql
```

Heat Management API:

```bash
python3 scripts/heat_management_smoke_test.py
```

## Production note

The current environment is intentionally local and containerized. Production deployment, real PLC connectivity, final tag mapping, MES integration, authentication/authorization, SAT and commissioning depend on infrastructure and interface information supplied by the client.

## Status

**Phase: Pre-server engineering foundation + executable Level 2 core prototype**
