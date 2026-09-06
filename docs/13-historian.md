# Local Historian - Design & Validation

## Purpose

This deliverable provides a locally runnable historian before the production server or plant network is available. It is intended for schema validation, sample data, dashboard development, integration tests and future Level 1 simulator work.

## Technology

- PostgreSQL
- TimescaleDB extension
- Docker Compose

## Stored data

The historian schema supports:

- Steel grades
- Equipment hierarchy
- Heats and heat stages
- Process tag catalog
- Time-series process samples
- Heat events
- Alarms
- Material consumption

## Start locally

```bash
cp .env.example .env
docker compose up -d
```

Check container health:

```bash
docker compose ps
```

## Connect with psql

```bash
docker compose exec historian-db \
  psql -U level2 -d steelmaking_level2
```

If `.env` credentials are changed, use the configured values instead.

## Verification queries

### Confirm TimescaleDB

```sql
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'timescaledb';
```

### Confirm historian hypertable

```sql
SELECT hypertable_schema, hypertable_name
FROM timescaledb_information.hypertables
WHERE hypertable_name = 'process_samples';
```

### Latest process values

```sql
SELECT *
FROM latest_process_values
ORDER BY tag_name;
```

### Demo heat

```sql
SELECT heat_no, status, planned_weight_t, started_at
FROM heats
ORDER BY created_at DESC;
```

### Heat events

```sql
SELECT
    h.heat_no,
    e.event_type,
    e.occurred_at,
    e.source_system
FROM heat_events e
LEFT JOIN heats h ON h.id = e.heat_id
ORDER BY e.occurred_at DESC;
```

## Reset local data

Development reset destroys the local historian volume and re-runs initialization scripts:

```bash
docker compose down -v
docker compose up -d
```

**Do not use `down -v` on a production environment.**

## Production differences

Before production use, the following require client approval/design:

- Storage sizing
- Retention and compression policies
- Backup and restore
- High availability
- Network/firewall rules
- Authentication and secrets management
- NTP/time synchronization
- Disaster recovery
- Monitoring and alerting

The current implementation intentionally enables no automatic data deletion.
