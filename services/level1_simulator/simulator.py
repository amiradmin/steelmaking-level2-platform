from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("level1-simulator")

DB_HOST: Final = os.getenv("DB_HOST", "historian-db")
DB_PORT: Final = int(os.getenv("DB_PORT", "5432"))
DB_NAME: Final = os.getenv("POSTGRES_DB", "steelmaking_level2")
DB_USER: Final = os.getenv("POSTGRES_USER", "level2")
DB_PASSWORD: Final = os.getenv("POSTGRES_PASSWORD", "level2_dev_password")
SAMPLE_INTERVAL_SECONDS: Final = float(os.getenv("SIM_SAMPLE_INTERVAL_SECONDS", "1"))
PHASE_DURATION_SECONDS: Final = float(os.getenv("SIM_PHASE_DURATION_SECONDS", "60"))
RESTART_DELAY_SECONDS: Final = float(os.getenv("SIM_RESTART_DELAY_SECONDS", "5"))


@dataclass(frozen=True)
class Phase:
    name: str
    heat_status: str
    equipment_code: str
    start_event: str
    complete_event: str


PHASES: Final[tuple[Phase, ...]] = (
    Phase("EAF", "EAF", "EAF-01", "EAF_START", "EAF_COMPLETE"),
    Phase("LF", "LF", "LF-01", "LF_START", "LF_COMPLETE"),
    Phase("CCM", "CASTING", "CCM-01", "CAST_START", "CAST_COMPLETE"),
)

PHASE_TAGS: Final[dict[str, tuple[str, ...]]] = {
    "EAF": (
        "EAF.PowerMW",
        "EAF.CurrentKA",
        "EAF.OxygenFlow",
        "EAF.SteelTemperature",
    ),
    "LF": (
        "LF.SteelTemperature",
        "LF.ArgonFlow",
    ),
    "CCM": (
        "CCM.CastingSpeed",
        "CCM.TundishTemperature",
    ),
}


def connect() -> Connection:
    """Connect to the historian database, retrying while the container starts."""
    while True:
        try:
            conn = psycopg.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                autocommit=True,
                row_factory=dict_row,
            )
            LOGGER.info("Connected to historian database %s:%s/%s", DB_HOST, DB_PORT, DB_NAME)
            return conn
        except psycopg.OperationalError as exc:
            LOGGER.warning("Historian not ready yet: %s", exc)
            time.sleep(2)


def get_equipment_ids(conn: Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT id::text, code FROM equipment WHERE code = ANY(%s)",
        ([phase.equipment_code for phase in PHASES],),
    ).fetchall()
    result = {row["code"]: row["id"] for row in rows}
    missing = {p.equipment_code for p in PHASES} - result.keys()
    if missing:
        raise RuntimeError(f"Missing equipment seed rows: {sorted(missing)}")
    return result


def get_tag_ids(conn: Connection) -> dict[str, str]:
    wanted = [tag for tags in PHASE_TAGS.values() for tag in tags]
    rows = conn.execute(
        "SELECT id::text, tag_name FROM process_tags WHERE tag_name = ANY(%s)",
        (wanted,),
    ).fetchall()
    result = {row["tag_name"]: row["id"] for row in rows}
    missing = set(wanted) - result.keys()
    if missing:
        raise RuntimeError(f"Missing process tag seed rows: {sorted(missing)}")
    return result


def get_or_create_active_heat(conn: Connection) -> dict[str, str]:
    row = conn.execute(
        """
        SELECT id::text, heat_no, status::text
        FROM heats
        WHERE status IN ('EAF', 'LF', 'CASTING')
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row:
        return row
    return create_next_heat(conn)


def create_next_heat(conn: Connection) -> dict[str, str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    heat_no = f"SIM-H{timestamp}"
    row = conn.execute(
        """
        INSERT INTO heats (
            heat_no,
            grade_id,
            status,
            planned_weight_t,
            production_order_id,
            started_at,
            attributes
        )
        SELECT
            %s,
            id,
            'EAF',
            80.0,
            %s,
            now(),
            '{"simulator": true}'::jsonb
        FROM steel_grades
        WHERE code = 'DEMO-ST37' AND revision = 1
        RETURNING id::text, heat_no, status::text
        """,
        (heat_no, f"SIM-PO-{timestamp}"),
    ).fetchone()
    if not row:
        raise RuntimeError("DEMO-ST37 steel grade is missing; run database seed scripts")
    LOGGER.info("Created new simulated heat %s", heat_no)
    return row


def phase_index_for_status(status: str) -> int:
    for index, phase in enumerate(PHASES):
        if phase.heat_status == status:
            return index
    return 0


def event_id(heat_no: str, event_type: str) -> str:
    return f"SIM-{heat_no}-{event_type}-{time.time_ns()}"


def insert_event(
    conn: Connection,
    *,
    heat_id: str,
    heat_no: str,
    phase: Phase,
    equipment_id: str,
    event_type: str,
) -> None:
    conn.execute(
        """
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
        VALUES (%s, 'SIMULATOR', %s, %s, %s::uuid, %s::uuid, 'INFO', now(), %s::jsonb)
        """,
        (
            event_type,
            event_id(heat_no, event_type),
            phase.name,
            equipment_id,
            heat_id,
            f'{{"simulator": true, "phase": "{phase.name}"}}',
        ),
    )


def start_stage(
    conn: Connection,
    *,
    heat_id: str,
    heat_no: str,
    phase: Phase,
    equipment_id: str,
) -> None:
    conn.execute(
        "UPDATE heats SET status = %s::heat_status, updated_at = now() WHERE id = %s::uuid",
        (phase.heat_status, heat_id),
    )
    conn.execute(
        """
        INSERT INTO heat_stages (heat_id, stage, equipment_id, started_at, status, attributes)
        VALUES (%s::uuid, %s, %s::uuid, now(), 'ACTIVE', '{"simulator": true}'::jsonb)
        """,
        (heat_id, phase.name, equipment_id),
    )
    insert_event(
        conn,
        heat_id=heat_id,
        heat_no=heat_no,
        phase=phase,
        equipment_id=equipment_id,
        event_type=phase.start_event,
    )
    LOGGER.info("Heat %s entered %s", heat_no, phase.name)


def complete_stage(
    conn: Connection,
    *,
    heat_id: str,
    heat_no: str,
    phase: Phase,
    equipment_id: str,
) -> None:
    conn.execute(
        """
        UPDATE heat_stages
        SET ended_at = now(), status = 'COMPLETED'
        WHERE id = (
            SELECT id
            FROM heat_stages
            WHERE heat_id = %s::uuid AND stage = %s AND status = 'ACTIVE'
            ORDER BY started_at DESC
            LIMIT 1
        )
        """,
        (heat_id, phase.name),
    )
    insert_event(
        conn,
        heat_id=heat_id,
        heat_no=heat_no,
        phase=phase,
        equipment_id=equipment_id,
        event_type=phase.complete_event,
    )


def sample_values(phase_name: str, progress: float) -> dict[str, float]:
    progress = max(0.0, min(progress, 1.0))
    if phase_name == "EAF":
        return {
            "EAF.PowerMW": random.uniform(48.0, 62.0),
            "EAF.CurrentKA": random.uniform(36.0, 46.0),
            "EAF.OxygenFlow": random.uniform(2700.0, 3500.0),
            "EAF.SteelTemperature": 1450.0 + (170.0 * progress) + random.uniform(-4.0, 4.0),
        }
    if phase_name == "LF":
        return {
            "LF.SteelTemperature": 1575.0 + (30.0 * progress) + random.uniform(-3.0, 3.0),
            "LF.ArgonFlow": random.uniform(85.0, 170.0),
        }
    return {
        "CCM.CastingSpeed": random.uniform(2.35, 2.85),
        "CCM.TundishTemperature": 1550.0 - (10.0 * progress) + random.uniform(-2.5, 2.5),
    }


def write_samples(
    conn: Connection,
    *,
    heat_id: str,
    tag_ids: dict[str, str],
    phase_name: str,
    progress: float,
) -> None:
    values = sample_values(phase_name, progress)
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        for tag_name, value in values.items():
            cur.execute(
                """
                INSERT INTO process_samples (
                    ts,
                    tag_id,
                    heat_id,
                    value_double,
                    quality,
                    attributes
                )
                VALUES (%s, %s::uuid, %s::uuid, %s, 'GOOD', '{"simulator": true}'::jsonb)
                """,
                (now, tag_ids[tag_name], heat_id, value),
            )


def complete_heat(conn: Connection, heat_id: str, heat_no: str) -> None:
    conn.execute(
        """
        UPDATE heats
        SET status = 'COMPLETED',
            actual_weight_t = COALESCE(actual_weight_t, 79.2),
            completed_at = now(),
            updated_at = now()
        WHERE id = %s::uuid
        """,
        (heat_id,),
    )
    LOGGER.info("Heat %s completed", heat_no)


def run() -> None:
    conn = connect()
    equipment_ids = get_equipment_ids(conn)
    tag_ids = get_tag_ids(conn)

    while True:
        try:
            heat = get_or_create_active_heat(conn)
            heat_id = heat["id"]
            heat_no = heat["heat_no"]
            start_index = phase_index_for_status(heat["status"])

            for phase in PHASES[start_index:]:
                equipment_id = equipment_ids[phase.equipment_code]
                start_stage(
                    conn,
                    heat_id=heat_id,
                    heat_no=heat_no,
                    phase=phase,
                    equipment_id=equipment_id,
                )
                phase_started = time.monotonic()

                while True:
                    elapsed = time.monotonic() - phase_started
                    progress = elapsed / PHASE_DURATION_SECONDS
                    write_samples(
                        conn,
                        heat_id=heat_id,
                        tag_ids=tag_ids,
                        phase_name=phase.name,
                        progress=progress,
                    )
                    if elapsed >= PHASE_DURATION_SECONDS:
                        break
                    time.sleep(SAMPLE_INTERVAL_SECONDS)

                complete_stage(
                    conn,
                    heat_id=heat_id,
                    heat_no=heat_no,
                    phase=phase,
                    equipment_id=equipment_id,
                )

            complete_heat(conn, heat_id, heat_no)
            time.sleep(RESTART_DELAY_SECONDS)
        except (psycopg.Error, RuntimeError) as exc:
            LOGGER.exception("Simulator cycle failed: %s", exc)
            try:
                conn.close()
            except Exception:
                pass
            time.sleep(2)
            conn = connect()
            equipment_ids = get_equipment_ids(conn)
            tag_ids = get_tag_ids(conn)


if __name__ == "__main__":
    run()
