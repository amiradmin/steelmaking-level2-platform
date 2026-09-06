# Dockerization

## Objective

Provide a reproducible local runtime that can later be moved to the client-provided server with minimal environmental differences.

## Current container stack

```text
steelmaking-level2-net
└── historian-db
    └── PostgreSQL + TimescaleDB
```

Future milestones can add the backend, Level 1 simulator, frontend, Redis/message broker and observability services to the same Compose project.

## Development startup

```bash
cp .env.example .env
docker compose pull
docker compose up -d
```

## Health check

```bash
docker compose ps
```

The database container includes a `pg_isready` health check.

## Logs

```bash
docker compose logs -f historian-db
```

## Stop

```bash
docker compose down
```

## Clean development reset

```bash
docker compose down -v
docker compose up -d
```

The `-v` form deletes the development database volume and must not be used for production data.

## Configuration

Environment variables are defined through `.env` using `.env.example` as the template:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_PORT`

Production secrets must not be committed to Git.

## Production migration considerations

Once the client server is available, this stack must be reviewed for:

1. Pinned image versions
2. Storage mount/location
3. Backup policy
4. Secrets management
5. Host firewall
6. OT/IT network segmentation
7. Time synchronization
8. Monitoring
9. Resource limits
10. Restart/recovery policy

## Acceptance criteria for this milestone

- Compose file exists in source control
- Environment template exists
- Historian initializes automatically on a clean volume
- Database health can be checked
- Schema and seed scripts are mounted read-only into initialization
- Data remains persistent across ordinary `docker compose down/up`
