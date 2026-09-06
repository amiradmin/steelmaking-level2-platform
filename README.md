# Steelmaking Level 2 Platform

Industrial Level 2 automation and production management platform for steelmaking operations, designed around **EAF → LF → CCM** process flow.

## Scope

This repository starts with the pre-server engineering and platform foundation that can be developed and validated locally before production infrastructure is available:

- System architecture
- Level 1 / Level 2 / Level 3 interface architecture
- Database and historian design
- Heat/Event/Alarm model
- Local TimescaleDB historian
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
│  Heat Management                     │
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

## Current milestone

The initial milestone covers work that does **not** require the production server or live plant connection:

1. System architecture
2. L1/L2/L3 interface architecture
3. Database architecture
4. Event model
5. Local historian
6. Dockerization

## Repository structure

```text
docs/                   Engineering and interface specifications
infrastructure/          Docker and database infrastructure
  database/              PostgreSQL/TimescaleDB schema and seed data
  docker/                Container configuration
src/                     Application source code (next milestone)
tests/                   Automated tests (next milestone)
```

## Local historian

The local development environment uses PostgreSQL with TimescaleDB for process historian data.

```bash
cp .env.example .env
docker compose up -d
```

Default services:

- PostgreSQL / TimescaleDB: `localhost:5432`

## Production note

The current environment is intentionally local and containerized. Production deployment, real PLC connectivity, final tag mapping, MES integration, SAT and commissioning depend on infrastructure and interface information supplied by the client.

## Status

**Phase: Pre-server engineering foundation**
