from __future__ import annotations

import os

import psycopg


DB_HOST = os.getenv("DB_HOST", "historian-db")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "steelmaking_level2")
DB_USER = os.getenv("POSTGRES_USER", "level2")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "level2_dev_password")

FLOW_TAGS = (
    ("EAF.StageCode", "PLC.EAF.StageCode", "EAF-01", "stage"),
    ("EAF.HeatNumber", "PLC.EAF.HeatNumber", "EAF-01", "heat"),
    ("LF.StageCode", "PLC.LF.StageCode", "LF-01", "stage"),
    ("LF.HeatNumber", "PLC.LF.HeatNumber", "LF-01", "heat"),
    ("CCM.StageCode", "PLC.CCM.StageCode", "CCM-01", "stage"),
    ("CCM.HeatNumber", "PLC.CCM.HeatNumber", "CCM-01", "heat"),
)


def main() -> None:
    """Ensure PLC production-flow tags exist without requiring historian reset."""
    with psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=True,
    ) as conn:
        for tag_name, source_tag, equipment_code, engineering_unit in FLOW_TAGS:
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
                    'DOUBLE',
                    %s,
                    'PERIODIC',
                    1000
                FROM equipment e
                WHERE e.code = %s
                ON CONFLICT (tag_name) DO NOTHING
                """,
                (tag_name, source_tag, engineering_unit, equipment_code),
            )


if __name__ == "__main__":
    main()
