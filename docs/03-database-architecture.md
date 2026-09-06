# Database Architecture

## 1. Goals

The Level 2 data platform must support both:

1. **Transactional production data** such as heats, equipment, material consumption, process stages and alarms.
2. **High-volume time-series process data** such as temperature, power, flow, pressure, speed and other Level 1 tags.

The initial local implementation uses PostgreSQL with TimescaleDB.

## 2. Logical model

```text
steel_grades
     │
     │ 1
     ▼
   heats ────────────────┐
     │                   │
     │ 1                 │
     ├────< heat_stages  │
     │                   │
     ├────< heat_events  │
     │                   │
     ├────< alarms       │
     │                   │
     ├────< material_consumptions
     │                   │
     └────< process_samples >──── process_tags

 equipment ─────< process_tags
 equipment ─────< heat_events
 equipment ─────< alarms
```

## 3. Core entities

### `steel_grades`
Master data for grade definitions.

Key fields:
- `id`
- `code`
- `name`
- `revision`
- `is_active`

### `heats`
Primary production traceability entity.

Key fields:
- `id`
- `heat_no`
- `grade_id`
- `status`
- `planned_weight_t`
- `actual_weight_t`
- `created_at`
- `started_at`
- `completed_at`

### `equipment`
Plant hierarchy/equipment registry.

Examples:
- EAF-01
- LF-01
- CCM-01
- CCM-01-STRAND-1

### `heat_stages`
Tracks lifecycle stages of a heat.

Examples:
- CHARGING
- EAF
- TAPPING
- LF
- CASTING
- COMPLETED

### `process_tags`
Normalized Level 1 tag catalog.

Key fields:
- `tag_name`
- `source_tag`
- `equipment_id`
- `data_type`
- `engineering_unit`
- `sampling_mode`
- `expected_period_ms`
- `is_active`

### `process_samples`
High-frequency historian table/hypertable.

Key fields:
- `ts`
- `ingested_at`
- `tag_id`
- `heat_id`
- `value_double`
- `value_text`
- `quality`

### `heat_events`
Normalized business/process event stream.

Key fields:
- `event_type`
- `source`
- `source_event_id`
- `occurred_at`
- `ingested_at`
- `heat_id`
- `equipment_id`
- `payload`

### `alarms`
Alarm lifecycle and acknowledgement data.

Key fields:
- `alarm_code`
- `severity`
- `state`
- `active_at`
- `cleared_at`
- `acknowledged_at`
- `heat_id`
- `equipment_id`

### `material_consumptions`
Actual or planned material additions by heat.

Key fields:
- `heat_id`
- `material_code`
- `quantity`
- `unit`
- `addition_time`
- `source`

## 4. Historian strategy

`process_samples` is designed as a TimescaleDB hypertable partitioned by time. Indexes are optimized for common Level 2 queries:

- One tag over a time range
- All relevant process values for one heat
- Equipment values around an event
- Latest value for a tag

## 5. Data retention

Retention policy must be agreed with the client. Initial development stores all local data. Production decisions should consider:

- Raw process sample retention
- Aggregated 1-minute / 10-minute / hourly retention
- Regulatory and quality traceability needs
- Backup capacity
- Long-term archive location

No destructive retention policy is enabled in the initial schema.

## 6. Traceability rules

1. `heat_no` is unique.
2. Source timestamps are preserved.
3. Historian values may be linked to a heat when the active heat is resolved.
4. Events store raw/extended attributes in JSONB while critical searchable fields remain relational.
5. External source IDs should be retained to support deduplication/idempotency.

## 7. Data dictionary status

The executable schema in `infrastructure/database/init/001_schema.sql` is the initial machine-readable implementation of this architecture. It is intentionally extensible; final chemistry, recipe, product genealogy and Level 3 entities will be added in later milestones.