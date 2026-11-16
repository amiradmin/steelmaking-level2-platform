BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='10s';
WITH expected AS (
            SELECT
                h.heat_no,
                h.status::text AS status,
                sg.code AS grade_code,
                h.planned_weight_t::double precision,
                h.actual_weight_t::double precision,
                h.started_at,
                h.completed_at,
                MAX(ps.value_double) FILTER (WHERE pt.tag_name = 'EAF.SteelTemperature')::double precision AS peak_eaf_temperature
            FROM (SELECT * FROM heats ORDER BY created_at DESC LIMIT 6) h
            LEFT JOIN steel_grades sg ON sg.id = h.grade_id
            LEFT JOIN process_samples ps ON ps.heat_id = h.id
            LEFT JOIN process_tags pt ON pt.id = ps.tag_id
            GROUP BY h.created_at, h.id, h.heat_no, h.status, sg.code, h.planned_weight_t, h.actual_weight_t, h.started_at, h.completed_at
            ORDER BY h.created_at DESC
            LIMIT 6
            ), actual AS (
            SELECT
                h.heat_no,
                h.status::text AS status,
                sg.code AS grade_code,
                h.planned_weight_t::double precision,
                h.actual_weight_t::double precision,
                h.started_at,
                h.completed_at,
                temperature.peak_eaf_temperature::double precision AS peak_eaf_temperature
            FROM (
                SELECT * FROM heats ORDER BY created_at DESC LIMIT 6
            ) h
            LEFT JOIN steel_grades sg ON sg.id = h.grade_id
            LEFT JOIN LATERAL (
                SELECT MAX(ps.value_double) AS peak_eaf_temperature
                FROM process_samples ps
                WHERE ps.heat_id = h.id
                  AND ps.tag_id = (SELECT id FROM process_tags WHERE tag_name = 'EAF.SteelTemperature')
            ) temperature ON TRUE
            ORDER BY h.created_at DESC
            ) SELECT count(*) AS differing_rows FROM ((SELECT * FROM expected EXCEPT ALL SELECT * FROM actual) UNION ALL (SELECT * FROM actual EXCEPT ALL SELECT * FROM expected)) difference;
ROLLBACK;
