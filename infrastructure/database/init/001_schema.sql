CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$ BEGIN
    CREATE TYPE heat_status AS ENUM (
        'PLANNED', 'CREATED', 'CHARGING', 'EAF', 'TAPPING',
        'LF', 'CASTING', 'HOLD', 'COMPLETED', 'ABORTED', 'CANCELLED'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE data_quality AS ENUM ('GOOD', 'UNCERTAIN', 'BAD', 'STALE', 'UNKNOWN');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE alarm_severity AS ENUM ('INFO', 'WARNING', 'HIGH', 'CRITICAL');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE alarm_state AS ENUM (
        'ACTIVE_UNACKNOWLEDGED',
        'ACTIVE_ACKNOWLEDGED',
        'CLEARED_UNACKNOWLEDGED',
        'CLEARED_ACKNOWLEDGED'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS steel_grades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(64) NOT NULL,
    name VARCHAR(255),
    revision INTEGER NOT NULL DEFAULT 1,
    specification JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (code, revision)
);

CREATE TABLE IF NOT EXISTS equipment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(128) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    area VARCHAR(64) NOT NULL,
    equipment_type VARCHAR(64) NOT NULL,
    parent_id UUID REFERENCES equipment(id) ON DELETE SET NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS heats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    heat_no VARCHAR(64) NOT NULL UNIQUE,
    grade_id UUID REFERENCES steel_grades(id) ON DELETE RESTRICT,
    status heat_status NOT NULL DEFAULT 'CREATED',
    planned_weight_t NUMERIC(12,3),
    actual_weight_t NUMERIC(12,3),
    production_order_id VARCHAR(128),
    planned_sequence INTEGER,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_heats_status ON heats(status);
CREATE INDEX IF NOT EXISTS ix_heats_created_at ON heats(created_at DESC);

CREATE TABLE IF NOT EXISTS heat_stages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    heat_id UUID NOT NULL REFERENCES heats(id) ON DELETE CASCADE,
    stage VARCHAR(64) NOT NULL,
    equipment_id UUID REFERENCES equipment(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_heat_stages_heat_time ON heat_stages(heat_id, started_at DESC);

CREATE TABLE IF NOT EXISTS process_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tag_name VARCHAR(255) NOT NULL UNIQUE,
    source_tag VARCHAR(512),
    source_system VARCHAR(64) NOT NULL DEFAULT 'LEVEL1',
    equipment_id UUID REFERENCES equipment(id) ON DELETE SET NULL,
    data_type VARCHAR(32) NOT NULL DEFAULT 'DOUBLE',
    engineering_unit VARCHAR(64),
    sampling_mode VARCHAR(32) NOT NULL DEFAULT 'COV',
    expected_period_ms INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_process_tags_equipment ON process_tags(equipment_id);

CREATE TABLE IF NOT EXISTS process_samples (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    tag_id UUID NOT NULL REFERENCES process_tags(id) ON DELETE RESTRICT,
    heat_id UUID REFERENCES heats(id) ON DELETE SET NULL,
    value_double DOUBLE PRECISION,
    value_text TEXT,
    quality data_quality NOT NULL DEFAULT 'GOOD',
    source_sequence BIGINT,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (id, ts),
    CHECK (value_double IS NOT NULL OR value_text IS NOT NULL)
);

SELECT create_hypertable('process_samples', 'ts', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS ix_process_samples_tag_ts
    ON process_samples(tag_id, ts DESC);
CREATE INDEX IF NOT EXISTS ix_process_samples_heat_ts
    ON process_samples(heat_id, ts DESC)
    WHERE heat_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_process_samples_quality_ts
    ON process_samples(quality, ts DESC);

CREATE TABLE IF NOT EXISTS heat_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(128) NOT NULL,
    source_system VARCHAR(64) NOT NULL,
    source_event_id VARCHAR(255),
    area VARCHAR(64),
    equipment_id UUID REFERENCES equipment(id) ON DELETE SET NULL,
    heat_id UUID REFERENCES heats(id) ON DELETE SET NULL,
    severity VARCHAR(32) NOT NULL DEFAULT 'INFO',
    occurred_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    correlation_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_heat_events_source_event
    ON heat_events(source_system, source_event_id)
    WHERE source_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_heat_events_heat_time
    ON heat_events(heat_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_heat_events_type_time
    ON heat_events(event_type, occurred_at DESC);

CREATE TABLE IF NOT EXISTS alarms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alarm_code VARCHAR(128) NOT NULL,
    source_system VARCHAR(64) NOT NULL,
    source_alarm_id VARCHAR(255),
    equipment_id UUID REFERENCES equipment(id) ON DELETE SET NULL,
    heat_id UUID REFERENCES heats(id) ON DELETE SET NULL,
    severity alarm_severity NOT NULL,
    state alarm_state NOT NULL DEFAULT 'ACTIVE_UNACKNOWLEDGED',
    message TEXT,
    active_at TIMESTAMPTZ NOT NULL,
    cleared_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(128),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_alarms_source_id
    ON alarms(source_system, source_alarm_id)
    WHERE source_alarm_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_alarms_active
    ON alarms(state, severity, active_at DESC);
CREATE INDEX IF NOT EXISTS ix_alarms_heat
    ON alarms(heat_id, active_at DESC);

CREATE TABLE IF NOT EXISTS material_consumptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    heat_id UUID NOT NULL REFERENCES heats(id) ON DELETE CASCADE,
    equipment_id UUID REFERENCES equipment(id) ON DELETE SET NULL,
    material_code VARCHAR(128) NOT NULL,
    material_name VARCHAR(255),
    quantity NUMERIC(16,4) NOT NULL,
    unit VARCHAR(32) NOT NULL,
    addition_time TIMESTAMPTZ NOT NULL,
    source_system VARCHAR(64) NOT NULL DEFAULT 'LEVEL1',
    batch_no VARCHAR(128),
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_material_consumptions_heat
    ON material_consumptions(heat_id, addition_time);

CREATE OR REPLACE VIEW latest_process_values AS
SELECT DISTINCT ON (ps.tag_id)
    ps.tag_id,
    pt.tag_name,
    pt.engineering_unit,
    ps.ts,
    ps.ingested_at,
    ps.heat_id,
    ps.value_double,
    ps.value_text,
    ps.quality
FROM process_samples ps
JOIN process_tags pt ON pt.id = ps.tag_id
ORDER BY ps.tag_id, ps.ts DESC;

CREATE OR REPLACE VIEW active_heats AS
SELECT *
FROM heats
WHERE status NOT IN ('COMPLETED', 'ABORTED', 'CANCELLED');
