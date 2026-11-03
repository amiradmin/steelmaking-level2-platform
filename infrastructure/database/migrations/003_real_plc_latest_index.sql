-- Apply once to an existing TimescaleDB installation.
-- This partial index makes the REAL_S7 + GOOD latest-per-tag lookup selective.
-- transaction_per_chunk avoids holding a write-blocking lock across the full
-- process_samples hypertable while each chunk's index is built.
--
-- Run from the repository root:
--   docker compose exec -T historian-db sh -lc \
--     'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
--     < infrastructure/database/migrations/003_real_plc_latest_index.sql
--
-- Verify after completion:
--   SELECT indexrelid::regclass, indisvalid
--   FROM pg_index
--   WHERE indexrelid = 'ix_process_samples_real_s7_latest'::regclass;

CREATE INDEX IF NOT EXISTS ix_process_samples_real_s7_latest
    ON process_samples (tag_id, ts DESC)
    WITH (timescaledb.transaction_per_chunk)
    WHERE quality = 'GOOD'
      AND attributes ->> 'source_kind' = 'REAL_S7';
