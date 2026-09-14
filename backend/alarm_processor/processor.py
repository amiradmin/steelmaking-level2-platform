from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("alarm-processor")

DB_HOST = os.getenv("DB_HOST", "historian-db")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "steelmaking_level2")
DB_USER = os.getenv("POSTGRES_USER", "level2")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "level2_dev_password")
POLL_SECONDS = max(0.25, float(os.getenv("ALARM_PROCESSOR_POLL_SECONDS", "1")))
STALE_SECONDS = max(2.0, float(os.getenv("ALARM_PROCESSOR_STALE_SECONDS", "10")))
RECONNECT_SECONDS = max(1.0, float(os.getenv("ALARM_PROCESSOR_RECONNECT_SECONDS", "3")))
SOURCE_SYSTEM = "PLC_ALARM_PROCESSOR"
ACTIVE_STATES = ("ACTIVE_UNACKNOWLEDGED", "ACTIVE_ACKNOWLEDGED")


@dataclass(frozen=True)
class AlarmDefinition:
    severity: str
    message: str


@dataclass(frozen=True)
class EvaluatedAlarm:
    alarm_code: str
    severity: str
    message: str
    observed_at: datetime
    payload: dict[str, Any]


AREA_EQUIPMENT = {
    "EAF": "EAF-01",
    "LF": "LF-01",
    "CCM": "CCM-01",
}

ALARM_CATALOG: dict[tuple[str, int], AlarmDefinition] = {
    ("EAF", 101): AlarmDefinition("HIGH", "EAF cooling water flow is below the safe limit"),
    ("EAF", 102): AlarmDefinition("HIGH", "EAF hydraulic system permissive is not healthy"),
    ("EAF", 103): AlarmDefinition("CRITICAL", "EAF transformer trip / transformer not ready"),
    ("EAF", 104): AlarmDefinition("CRITICAL", "EAF roof interlock is open while arc operation is requested"),
    ("LF", 201): AlarmDefinition("HIGH", "LF cooling water flow is below the safe limit"),
    ("LF", 202): AlarmDefinition("HIGH", "LF argon pressure is below the safe limit"),
    ("LF", 203): AlarmDefinition("CRITICAL", "LF transformer trip / transformer not ready"),
    ("LF", 204): AlarmDefinition("CRITICAL", "LF roof interlock is open while arc operation is requested"),
    ("CCM", 301): AlarmDefinition("CRITICAL", "CCM mold cooling water flow is below the safe limit"),
    ("CCM", 302): AlarmDefinition("HIGH", "CCM mold level is outside the automatic control range"),
    ("CCM", 303): AlarmDefinition("CRITICAL", "CCM emergency-stop safety circuit is not healthy"),
    ("CCM", 304): AlarmDefinition("HIGH", "CCM tundish temperature is above the configured high limit"),
}


def _connect() -> psycopg.Connection[Any]:
    LOGGER.info("Connecting to historian database %s:%s/%s", DB_HOST, DB_PORT, DB_NAME)
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        row_factory=dict_row,
        autocommit=False,
    )


def _value_as_number(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    value = row.get("value_double")
    if isinstance(value, (int, float)):
        return float(value)
    text = row.get("value_text")
    if text is None:
        return None
    try:
        return float(str(text).strip())
    except ValueError:
        return None


def _value_as_bool(row: dict[str, Any] | None) -> bool | None:
    number = _value_as_number(row)
    if number is not None:
        return number != 0
    if not row:
        return None
    normalized = str(row.get("value_text") or "").strip().lower()
    if normalized in {"true", "yes", "on", "ok", "ready", "running"}:
        return True
    if normalized in {"false", "no", "off", "bad", "fault"}:
        return False
    return None


def _is_fresh_good(row: dict[str, Any] | None, now: datetime) -> bool:
    if not row or str(row.get("quality") or "").upper() != "GOOD":
        return False
    timestamp = row.get("ts")
    if not isinstance(timestamp, datetime):
        return False
    age_seconds = max(0.0, (now - timestamp).total_seconds())
    return age_seconds <= STALE_SECONDS


def _snapshot(conn: psycopg.Connection[Any], area: str) -> dict[str, dict[str, Any]]:
    tags = [
        f"{area}.AlarmCode",
        f"{area}.Fault",
        f"{area}.InterlockOK",
        f"{area}.HeatNumber",
    ]
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                tag_name,
                value_double,
                value_text,
                quality::text AS quality,
                ts
            FROM latest_process_values
            WHERE tag_name = ANY(%s)
            """,
            [tags],
        )
        return {row["tag_name"]: row for row in cursor.fetchall()}


def _evaluate(area: str, snapshot: dict[str, dict[str, Any]]) -> tuple[bool, EvaluatedAlarm | None]:
    now = datetime.now(timezone.utc)
    alarm_row = snapshot.get(f"{area}.AlarmCode")
    if not _is_fresh_good(alarm_row, now):
        # Never clear an alarm from missing, stale or bad-quality telemetry.
        return False, None

    code_number = _value_as_number(alarm_row)
    numeric_code = int(code_number or 0)
    fault_row = snapshot.get(f"{area}.Fault")
    interlock_row = snapshot.get(f"{area}.InterlockOK")
    heat_row = snapshot.get(f"{area}.HeatNumber")
    fault = _value_as_bool(fault_row) if _is_fresh_good(fault_row, now) else None
    interlock_ok = _value_as_bool(interlock_row) if _is_fresh_good(interlock_row, now) else None
    heat_number_value = _value_as_number(heat_row) if _is_fresh_good(heat_row, now) else None
    heat_number = str(int(heat_number_value)) if heat_number_value is not None else None
    observed_at = alarm_row["ts"]

    payload: dict[str, Any] = {
        "area": area,
        "alarm_code_value": numeric_code,
        "fault": fault,
        "interlock_ok": interlock_ok,
        "heat_number": heat_number,
        "telemetry_quality": alarm_row.get("quality"),
        "alarm_code_tag": f"{area}.AlarmCode",
        "fault_tag": f"{area}.Fault",
        "interlock_tag": f"{area}.InterlockOK",
        "read_only_plc": True,
    }

    if numeric_code > 0:
        definition = ALARM_CATALOG.get(
            (area, numeric_code),
            AlarmDefinition("HIGH", f"{area} PLC reported alarm code {numeric_code}"),
        )
        return True, EvaluatedAlarm(
            alarm_code=f"{area}-{numeric_code}",
            severity=definition.severity,
            message=definition.message,
            observed_at=observed_at,
            payload=payload,
        )

    # Defensive fallbacks for real PLC mappings where a general fault/interlock
    # may be present even before a detailed numeric code is available.
    if interlock_ok is False:
        return True, EvaluatedAlarm(
            alarm_code=f"{area}-INTERLOCK",
            severity="CRITICAL",
            message=f"{area} process interlock is not healthy",
            observed_at=observed_at,
            payload=payload,
        )
    if fault is True:
        return True, EvaluatedAlarm(
            alarm_code=f"{area}-FAULT",
            severity="HIGH",
            message=f"{area} PLC general fault is active",
            observed_at=observed_at,
            payload=payload,
        )

    return True, None


def _equipment_id(conn: psycopg.Connection[Any], equipment_code: str) -> Any | None:
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM equipment WHERE code = %s AND is_active = TRUE", [equipment_code])
        row = cursor.fetchone()
        return row["id"] if row else None


def _heat_id(conn: psycopg.Connection[Any], heat_number: str | None) -> Any | None:
    if not heat_number:
        return None
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM heats WHERE heat_no = %s LIMIT 1", [heat_number])
        row = cursor.fetchone()
        return row["id"] if row else None


def _current_active_alarm(conn: psycopg.Connection[Any], equipment_id: Any) -> dict[str, Any] | None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, alarm_code, source_alarm_id, severity::text AS severity, state::text AS state,
                   heat_id, active_at, payload
            FROM alarms
            WHERE source_system = %s
              AND equipment_id = %s
              AND state IN ('ACTIVE_UNACKNOWLEDGED', 'ACTIVE_ACKNOWLEDGED')
            ORDER BY active_at DESC
            LIMIT 1
            FOR UPDATE
            """,
            [SOURCE_SYSTEM, equipment_id],
        )
        return cursor.fetchone()


def _write_event(
    conn: psycopg.Connection[Any],
    *,
    event_type: str,
    source_event_id: str,
    area: str,
    equipment_id: Any,
    heat_id: Any | None,
    severity: str,
    occurred_at: datetime,
    payload: dict[str, Any],
) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO heat_events (
                event_type, source_system, source_event_id, area, equipment_id,
                heat_id, severity, occurred_at, payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                event_type,
                SOURCE_SYSTEM,
                source_event_id,
                area,
                equipment_id,
                heat_id,
                severity,
                occurred_at,
                Jsonb(payload),
            ],
        )


def _clear_alarm(
    conn: psycopg.Connection[Any],
    *,
    active: dict[str, Any],
    area: str,
    equipment_id: Any,
    cleared_at: datetime,
    reason: str,
) -> None:
    target_state = (
        "CLEARED_ACKNOWLEDGED"
        if active["state"] == "ACTIVE_ACKNOWLEDGED"
        else "CLEARED_UNACKNOWLEDGED"
    )
    clear_payload = {
        "clear_reason": reason,
        "cleared_by": SOURCE_SYSTEM,
        "cleared_observed_at": cleared_at.isoformat(),
        "read_only_plc": True,
    }
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE alarms
            SET state = %s,
                cleared_at = %s,
                updated_at = now(),
                payload = payload || %s
            WHERE id = %s
            """,
            [target_state, cleared_at, Jsonb(clear_payload), active["id"]],
        )

    source_alarm_id = active.get("source_alarm_id") or str(active["id"])
    _write_event(
        conn,
        event_type="ALARM_CLEARED",
        source_event_id=f"{source_alarm_id}:clear",
        area=area,
        equipment_id=equipment_id,
        heat_id=active.get("heat_id"),
        severity=active["severity"],
        occurred_at=cleared_at,
        payload={
            "alarm_code": active["alarm_code"],
            "reason": reason,
            "read_only_plc": True,
        },
    )
    LOGGER.info("CLEARED %s on %s (%s)", active["alarm_code"], area, reason)


def _activate_alarm(
    conn: psycopg.Connection[Any],
    *,
    signal: EvaluatedAlarm,
    area: str,
    equipment_code: str,
    equipment_id: Any,
    heat_id: Any | None,
) -> None:
    source_alarm_id = f"{equipment_code}:{signal.alarm_code}:{uuid.uuid4().hex}"
    payload = dict(signal.payload)
    payload["last_observed_at"] = signal.observed_at.isoformat()

    with conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO alarms (
                alarm_code, source_system, source_alarm_id, equipment_id, heat_id,
                severity, state, message, active_at, payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE_UNACKNOWLEDGED', %s, %s, %s)
            RETURNING id
            """,
            [
                signal.alarm_code,
                SOURCE_SYSTEM,
                source_alarm_id,
                equipment_id,
                heat_id,
                signal.severity,
                signal.message,
                signal.observed_at,
                Jsonb(payload),
            ],
        )
        cursor.fetchone()

    _write_event(
        conn,
        event_type="ALARM_ACTIVATED",
        source_event_id=f"{source_alarm_id}:active",
        area=area,
        equipment_id=equipment_id,
        heat_id=heat_id,
        severity=signal.severity,
        occurred_at=signal.observed_at,
        payload={
            "alarm_code": signal.alarm_code,
            "message": signal.message,
            **signal.payload,
        },
    )
    LOGGER.warning("ACTIVE %s %s on %s: %s", signal.severity, signal.alarm_code, area, signal.message)


def _refresh_active_alarm(
    conn: psycopg.Connection[Any],
    *,
    active: dict[str, Any],
    signal: EvaluatedAlarm,
    heat_id: Any | None,
) -> None:
    update_payload = {
        "last_observed_at": signal.observed_at.isoformat(),
        "last_snapshot": signal.payload,
    }
    with conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE alarms
            SET severity = %s,
                message = %s,
                heat_id = COALESCE(%s, heat_id),
                updated_at = now(),
                payload = payload || %s
            WHERE id = %s
            """,
            [signal.severity, signal.message, heat_id, Jsonb(update_payload), active["id"]],
        )


def _process_area(conn: psycopg.Connection[Any], area: str) -> None:
    equipment_code = AREA_EQUIPMENT[area]
    equipment_id = _equipment_id(conn, equipment_code)
    if equipment_id is None:
        LOGGER.warning("Equipment %s not found; skipping %s alarm processing", equipment_code, area)
        return

    snapshot = _snapshot(conn, area)
    authoritative, signal = _evaluate(area, snapshot)
    if not authoritative:
        LOGGER.debug("Skipping %s: AlarmCode is missing, stale or not GOOD", area)
        return

    active = _current_active_alarm(conn, equipment_id)
    clear_time = datetime.now(timezone.utc)

    if signal is None:
        if active is not None:
            _clear_alarm(
                conn,
                active=active,
                area=area,
                equipment_id=equipment_id,
                cleared_at=clear_time,
                reason="PLC alarm code returned to zero and permissives are healthy",
            )
        return

    heat_number = signal.payload.get("heat_number")
    heat_id = _heat_id(conn, str(heat_number) if heat_number else None)

    if active is not None and active["alarm_code"] == signal.alarm_code:
        _refresh_active_alarm(conn, active=active, signal=signal, heat_id=heat_id)
        return

    if active is not None:
        _clear_alarm(
            conn,
            active=active,
            area=area,
            equipment_id=equipment_id,
            cleared_at=signal.observed_at,
            reason=f"Superseded by {signal.alarm_code}",
        )

    _activate_alarm(
        conn,
        signal=signal,
        area=area,
        equipment_code=equipment_code,
        equipment_id=equipment_id,
        heat_id=heat_id,
    )


def _run_connected(conn: psycopg.Connection[Any]) -> None:
    LOGGER.info(
        "Alarm processor started: areas=%s poll=%.2fs stale=%.1fs PLC boundary=READ_ONLY",
        ",".join(AREA_EQUIPMENT),
        POLL_SECONDS,
        STALE_SECONDS,
    )
    while True:
        cycle_started = time.monotonic()
        for area in AREA_EQUIPMENT:
            try:
                _process_area(conn, area)
                conn.commit()
            except psycopg.Error:
                conn.rollback()
                raise
            except Exception:
                conn.rollback()
                LOGGER.exception("Unexpected error while processing %s", area)
        elapsed = time.monotonic() - cycle_started
        time.sleep(max(0.05, POLL_SECONDS - elapsed))


def main() -> None:
    while True:
        conn: psycopg.Connection[Any] | None = None
        try:
            conn = _connect()
            _run_connected(conn)
        except KeyboardInterrupt:
            LOGGER.info("Alarm processor stopped")
            return
        except psycopg.Error as exc:
            LOGGER.error("Database connection lost: %s; reconnecting in %.1fs", exc, RECONNECT_SECONDS)
            time.sleep(RECONNECT_SECONDS)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
