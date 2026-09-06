\set ON_ERROR_STOP on

DO $$
DECLARE
    hypertable_count integer;
    equipment_count integer;
    tag_count integer;
    heat_count integer;
BEGIN
    SELECT count(*) INTO hypertable_count
    FROM timescaledb_information.hypertables
    WHERE hypertable_name = 'process_samples';

    IF hypertable_count <> 1 THEN
        RAISE EXCEPTION 'process_samples is not a TimescaleDB hypertable';
    END IF;

    SELECT count(*) INTO equipment_count FROM equipment;
    IF equipment_count < 3 THEN
        RAISE EXCEPTION 'Expected at least 3 equipment seed rows, got %', equipment_count;
    END IF;

    SELECT count(*) INTO tag_count FROM process_tags;
    IF tag_count < 8 THEN
        RAISE EXCEPTION 'Expected at least 8 process tags, got %', tag_count;
    END IF;

    SELECT count(*) INTO heat_count FROM heats WHERE heat_no = 'DEMO-H260001';
    IF heat_count <> 1 THEN
        RAISE EXCEPTION 'Demo heat was not initialized';
    END IF;
END $$;

SELECT
    'historian-smoke-test' AS test_name,
    'PASS' AS result,
    (SELECT count(*) FROM process_samples) AS process_samples,
    (SELECT count(*) FROM heat_events) AS heat_events,
    (SELECT count(*) FROM latest_process_values) AS latest_values;
