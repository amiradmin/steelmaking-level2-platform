INSERT INTO equipment (code, name, area, equipment_type)
VALUES
    ('EAF-01', 'Electric Arc Furnace 01', 'EAF', 'EAF'),
    ('LF-01', 'Ladle Furnace 01', 'LF', 'LF'),
    ('CCM-01', 'Continuous Casting Machine 01', 'CCM', 'CCM')
ON CONFLICT (code) DO NOTHING;

INSERT INTO steel_grades (code, name, revision)
VALUES ('DEMO-ST37', 'Demo ST37', 1)
ON CONFLICT (code, revision) DO NOTHING;

INSERT INTO process_tags (
    tag_name,
    source_tag,
    source_system,
    equipment_id,
    data_type,
    engineering_unit,
    sampling_mode,
    expected_period_ms
)
SELECT
    v.tag_name,
    v.source_tag,
    'SIMULATOR',
    e.id,
    'DOUBLE',
    v.unit,
    'PERIODIC',
    1000
FROM (
    VALUES
        ('EAF.PowerMW', 'SIM.EAF.PowerMW', 'EAF-01', 'MW'),
        ('EAF.CurrentKA', 'SIM.EAF.CurrentKA', 'EAF-01', 'kA'),
        ('EAF.OxygenFlow', 'SIM.EAF.OxygenFlow', 'EAF-01', 'Nm3/h'),
        ('EAF.SteelTemperature', 'SIM.EAF.SteelTemperature', 'EAF-01', 'degC'),
        ('LF.SteelTemperature', 'SIM.LF.SteelTemperature', 'LF-01', 'degC'),
        ('LF.ArgonFlow', 'SIM.LF.ArgonFlow', 'LF-01', 'NL/min'),
        ('CCM.CastingSpeed', 'SIM.CCM.CastingSpeed', 'CCM-01', 'm/min'),
        ('CCM.TundishTemperature', 'SIM.CCM.TundishTemperature', 'CCM-01', 'degC')
) AS v(tag_name, source_tag, equipment_code, unit)
JOIN equipment e ON e.code = v.equipment_code
ON CONFLICT (tag_name) DO NOTHING;

INSERT INTO heats (
    heat_no,
    grade_id,
    status,
    planned_weight_t,
    actual_weight_t,
    production_order_id,
    planned_sequence,
    started_at,
    attributes
)
SELECT
    'DEMO-H260001',
    sg.id,
    'EAF',
    80.0,
    NULL,
    'DEMO-PO-001',
    1,
    now() - interval '20 minutes',
    '{"demo": true}'::jsonb
FROM steel_grades sg
WHERE sg.code = 'DEMO-ST37' AND sg.revision = 1
ON CONFLICT (heat_no) DO NOTHING;

INSERT INTO process_samples (ts, tag_id, heat_id, value_double, quality, attributes)
SELECT
    now() - interval '10 seconds',
    pt.id,
    h.id,
    CASE pt.tag_name
        WHEN 'EAF.PowerMW' THEN 58.2
        WHEN 'EAF.CurrentKA' THEN 41.3
        WHEN 'EAF.OxygenFlow' THEN 3210.0
        WHEN 'EAF.SteelTemperature' THEN 1582.0
        ELSE 0.0
    END,
    'GOOD',
    '{"demo": true}'::jsonb
FROM process_tags pt
CROSS JOIN heats h
WHERE h.heat_no = 'DEMO-H260001'
  AND pt.tag_name IN (
      'EAF.PowerMW',
      'EAF.CurrentKA',
      'EAF.OxygenFlow',
      'EAF.SteelTemperature'
  );

INSERT INTO heat_events (
    event_type,
    source_system,
    source_event_id,
    area,
    equipment_id,
    heat_id,
    severity,
    occurred_at,
    payload
)
SELECT
    'POWER_ON',
    'SIMULATOR',
    'DEMO-EVENT-POWER-ON-001',
    'EAF',
    e.id,
    h.id,
    'INFO',
    now() - interval '15 minutes',
    '{"demo": true}'::jsonb
FROM equipment e
CROSS JOIN heats h
WHERE e.code = 'EAF-01' AND h.heat_no = 'DEMO-H260001'
ON CONFLICT DO NOTHING;
