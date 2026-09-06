WITH recent_samples AS (
    SELECT COUNT(*) AS sample_count
    FROM process_samples
    WHERE ts >= now() - interval '30 seconds'
      AND attributes @> '{"simulator": true}'::jsonb
),
recent_events AS (
    SELECT COUNT(*) AS event_count
    FROM heat_events
    WHERE occurred_at >= now() - interval '5 minutes'
      AND source_system = 'SIMULATOR'
),
active_sim_heat AS (
    SELECT COUNT(*) AS heat_count
    FROM heats
    WHERE status IN ('EAF', 'LF', 'CASTING')
      AND attributes @> '{"simulator": true}'::jsonb
)
SELECT
    'level1-simulator-smoke-test' AS test_name,
    CASE
        WHEN rs.sample_count >= 4 AND re.event_count >= 1 AND ah.heat_count >= 1
            THEN 'PASS'
        ELSE 'FAIL'
    END AS result,
    rs.sample_count AS samples_last_30s,
    re.event_count AS simulator_events_last_5m,
    ah.heat_count AS active_simulated_heats
FROM recent_samples rs
CROSS JOIN recent_events re
CROSS JOIN active_sim_heat ah;

SELECT
    lpv.tag_name,
    ROUND(lpv.value_double::numeric, 2) AS value,
    lpv.engineering_unit,
    lpv.quality,
    lpv.ts
FROM latest_process_values lpv
WHERE lpv.tag_name LIKE 'EAF.%'
   OR lpv.tag_name LIKE 'LF.%'
   OR lpv.tag_name LIKE 'CCM.%'
ORDER BY lpv.tag_name;
