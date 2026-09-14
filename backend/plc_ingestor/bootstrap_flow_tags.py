from __future__ import annotations

import os

import psycopg


DB_HOST = os.getenv("DB_HOST", "historian-db")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "steelmaking_level2")
DB_USER = os.getenv("POSTGRES_USER", "level2")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "level2_dev_password")

# Logical Level 2 tags required by the production flow and equipment dashboards.
# The central OPC UA gateway exposes these node ids from the read-only S7 map.
FLOW_TAGS = (
    ("EAF.PowerMW", "PLC.EAF.PowerMW", "EAF-01", "DOUBLE", "MW"),
    ("EAF.CurrentKA", "PLC.EAF.CurrentKA", "EAF-01", "DOUBLE", "kA"),
    ("EAF.OxygenFlow", "PLC.EAF.OxygenFlow", "EAF-01", "DOUBLE", "Nm3/h"),
    ("EAF.SteelTemperature", "PLC.EAF.SteelTemperature", "EAF-01", "DOUBLE", "degC"),
    ("EAF.ElectrodePositionPercent", "PLC.EAF.ElectrodePositionPercent", "EAF-01", "DOUBLE", "%"),
    ("EAF.CoolingWaterFlowM3h", "PLC.EAF.CoolingWaterFlowM3h", "EAF-01", "DOUBLE", "m3/h"),
    ("EAF.TransformerTap", "PLC.EAF.TransformerTap", "EAF-01", "INTEGER", "tap"),
    ("EAF.StageCode", "PLC.EAF.StageCode", "EAF-01", "INTEGER", "stage"),
    ("EAF.HeatNumber", "PLC.EAF.HeatNumber", "EAF-01", "INTEGER", "heat"),
    ("EAF.Ready", "PLC.EAF.Ready", "EAF-01", "BOOLEAN", None),
    ("EAF.Running", "PLC.EAF.Running", "EAF-01", "BOOLEAN", None),
    ("EAF.Fault", "PLC.EAF.Fault", "EAF-01", "BOOLEAN", None),
    ("EAF.AlarmCode", "PLC.EAF.AlarmCode", "EAF-01", "INTEGER", None),
    ("EAF.ArcOn", "PLC.EAF.ArcOn", "EAF-01", "BOOLEAN", None),
    ("EAF.OxygenOn", "PLC.EAF.OxygenOn", "EAF-01", "BOOLEAN", None),
    ("EAF.BurnerOn", "PLC.EAF.BurnerOn", "EAF-01", "BOOLEAN", None),
    ("EAF.RoofClosed", "PLC.EAF.RoofClosed", "EAF-01", "BOOLEAN", None),
    ("EAF.DoorClosed", "PLC.EAF.DoorClosed", "EAF-01", "BOOLEAN", None),
    ("EAF.HydraulicOK", "PLC.EAF.HydraulicOK", "EAF-01", "BOOLEAN", None),
    ("EAF.CoolingWaterOK", "PLC.EAF.CoolingWaterOK", "EAF-01", "BOOLEAN", None),
    ("EAF.TransformerReady", "PLC.EAF.TransformerReady", "EAF-01", "BOOLEAN", None),
    ("EAF.InterlockOK", "PLC.EAF.InterlockOK", "EAF-01", "BOOLEAN", None),
    ("EAF.PLC.ScanCounter", "PLC.EAF.PLC.ScanCounter", "EAF-01", "INTEGER", "count"),
    ("EAF.PLC.CycleTimeMs", "PLC.EAF.PLC.CycleTimeMs", "EAF-01", "DOUBLE", "ms"),
    ("EAF.PLC.WatchdogOK", "PLC.EAF.PLC.WatchdogOK", "EAF-01", "BOOLEAN", None),
    ("EAF.PLC.CommsOK", "PLC.EAF.PLC.CommsOK", "EAF-01", "BOOLEAN", None),
    ("EAF.PLC.Heartbeat", "PLC.EAF.PLC.Heartbeat", "EAF-01", "BOOLEAN", None),

    ("LF.SteelTemperature", "PLC.LF.SteelTemperature", "LF-01", "DOUBLE", "degC"),
    ("LF.ArgonFlow", "PLC.LF.ArgonFlow", "LF-01", "DOUBLE", "NL/min"),
    ("LF.PowerMW", "PLC.LF.PowerMW", "LF-01", "DOUBLE", "MW"),
    ("LF.CurrentKA", "PLC.LF.CurrentKA", "LF-01", "DOUBLE", "kA"),
    ("LF.ElectrodePositionPercent", "PLC.LF.ElectrodePositionPercent", "LF-01", "DOUBLE", "%"),
    ("LF.CoolingWaterFlowM3h", "PLC.LF.CoolingWaterFlowM3h", "LF-01", "DOUBLE", "m3/h"),
    ("LF.LadleWeightTon", "PLC.LF.LadleWeightTon", "LF-01", "DOUBLE", "t"),
    ("LF.StageCode", "PLC.LF.StageCode", "LF-01", "INTEGER", "stage"),
    ("LF.HeatNumber", "PLC.LF.HeatNumber", "LF-01", "INTEGER", "heat"),
    ("LF.Ready", "PLC.LF.Ready", "LF-01", "BOOLEAN", None),
    ("LF.Running", "PLC.LF.Running", "LF-01", "BOOLEAN", None),
    ("LF.Fault", "PLC.LF.Fault", "LF-01", "BOOLEAN", None),
    ("LF.AlarmCode", "PLC.LF.AlarmCode", "LF-01", "INTEGER", None),
    ("LF.ArcOn", "PLC.LF.ArcOn", "LF-01", "BOOLEAN", None),
    ("LF.ArgonOn", "PLC.LF.ArgonOn", "LF-01", "BOOLEAN", None),
    ("LF.RoofClosed", "PLC.LF.RoofClosed", "LF-01", "BOOLEAN", None),
    ("LF.CoolingWaterOK", "PLC.LF.CoolingWaterOK", "LF-01", "BOOLEAN", None),
    ("LF.ArgonPressureOK", "PLC.LF.ArgonPressureOK", "LF-01", "BOOLEAN", None),
    ("LF.TransformerReady", "PLC.LF.TransformerReady", "LF-01", "BOOLEAN", None),
    ("LF.InterlockOK", "PLC.LF.InterlockOK", "LF-01", "BOOLEAN", None),
    ("LF.PLC.ScanCounter", "PLC.LF.PLC.ScanCounter", "LF-01", "INTEGER", "count"),
    ("LF.PLC.CycleTimeMs", "PLC.LF.PLC.CycleTimeMs", "LF-01", "DOUBLE", "ms"),
    ("LF.PLC.WatchdogOK", "PLC.LF.PLC.WatchdogOK", "LF-01", "BOOLEAN", None),
    ("LF.PLC.CommsOK", "PLC.LF.PLC.CommsOK", "LF-01", "BOOLEAN", None),
    ("LF.PLC.Heartbeat", "PLC.LF.PLC.Heartbeat", "LF-01", "BOOLEAN", None),

    ("CCM.StageCode", "PLC.CCM.StageCode", "CCM-01", "INTEGER", "stage"),
    ("CCM.HeatNumber", "PLC.CCM.HeatNumber", "CCM-01", "INTEGER", "heat"),
)


def main() -> None:
    """Ensure PLC dashboard tags exist without requiring a historian reset."""
    with psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=True,
    ) as conn:
        for tag_name, source_tag, equipment_code, data_type, engineering_unit in FLOW_TAGS:
            conn.execute(
                """
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
                    %s,
                    %s,
                    'PLC',
                    e.id,
                    %s,
                    %s,
                    'PERIODIC',
                    1000
                FROM equipment e
                WHERE e.code = %s
                ON CONFLICT (tag_name) DO NOTHING
                """,
                (tag_name, source_tag, data_type, engineering_unit, equipment_code),
            )


if __name__ == "__main__":
    main()
