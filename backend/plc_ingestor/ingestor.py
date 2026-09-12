from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

import psycopg
from asyncua import Client
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


logging.basicConfig(
    level=os.getenv("PLC_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("plc-ingestor")

DB_HOST: Final = os.getenv("DB_HOST", "historian-db")
DB_PORT: Final = int(os.getenv("DB_PORT", "5432"))
DB_NAME: Final = os.getenv("POSTGRES_DB", "steelmaking_level2")
DB_USER: Final = os.getenv("POSTGRES_USER", "level2")
DB_PASSWORD: Final = os.getenv("POSTGRES_PASSWORD", "level2_dev_password")

OPCUA_ENDPOINT: Final = os.getenv("PLC_OPCUA_ENDPOINT", "opc.tcp://host.docker.internal:4840")
OPCUA_USERNAME: Final = os.getenv("PLC_OPCUA_USERNAME", "").strip()
OPCUA_PASSWORD: Final = os.getenv("PLC_OPCUA_PASSWORD", "")
POLL_INTERVAL_SECONDS: Final = float(os.getenv("PLC_POLL_INTERVAL_SECONDS", "1"))
RECONNECT_DELAY_SECONDS: Final = float(os.getenv("PLC_RECONNECT_DELAY_SECONDS", "5"))
NODE_MAP_RAW: Final = os.getenv("PLC_NODE_MAP_JSON", "{}").strip()
HEALTH_FILE: Final = Path(os.getenv("PLC_HEALTH_FILE", "/tmp/plc-ingestor-health.json"))


class ConfigurationError(RuntimeError):
    """Raised when PLC ingestion configuration is incomplete or invalid."""


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


def normalize_timestamp(value: datetime | None) -> datetime:
    """Normalize an OPC UA timestamp to timezone-aware UTC."""
    if value is None:
        return utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def write_health(state: str, detail: str, *, last_success_at: datetime | None = None) -> None:
    """Publish a tiny local health document consumed by the Docker healthcheck."""
    payload = {
        "state": state,
        "detail": detail,
        "updated_at": utc_now().isoformat(),
        "last_success_at": last_success_at.isoformat() if last_success_at else None,
    }
    try:
        HEALTH_FILE.write_text(json.dumps(payload), encoding="utf-8")
    except OSError as exc:
        LOGGER.warning("Unable to write health file %s: %s", HEALTH_FILE, exc)


def load_node_map() -> dict[str, str]:
    """Return the logical Level 2 tag -> OPC UA node-id mapping from JSON."""
    try:
        raw = json.loads(NODE_MAP_RAW or "{}")
    except json.JSONDecodeError as exc:
        raise ConfigurationError("PLC_NODE_MAP_JSON is not valid JSON") from exc

    if not isinstance(raw, dict):
        raise ConfigurationError("PLC_NODE_MAP_JSON must be a JSON object")

    node_map = {
        str(tag_name).strip(): str(node_id).strip()
        for tag_name, node_id in raw.items()
        if str(tag_name).strip() and str(node_id).strip()
    }
    if not node_map:
        raise ConfigurationError(
            "PLC_NODE_MAP_JSON is empty. Map existing process_tags to OPC UA node ids before starting the PLC profile."
        )
    return node_map


def connect_db() -> Connection:
    """Open an autocommit connection to the historian database."""
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=True,
        row_factory=dict_row,
    )


def resolve_tag_ids(conn: Connection, node_map: dict[str, str]) -> dict[str, str]:
    """Resolve configured logical tags to seeded historian tag UUIDs."""
    rows = conn.execute(
        "SELECT id::text, tag_name FROM process_tags WHERE tag_name = ANY(%s) AND is_active = TRUE",
        (list(node_map),),
    ).fetchall()
    result = {row["tag_name"]: row["id"] for row in rows}
    missing = set(node_map) - result.keys()
    if missing:
        raise ConfigurationError(
            f"PLC mapping references unknown process_tags: {sorted(missing)}"
        )
    return result


def active_heat_id(conn: Connection) -> str | None:
    """Return the most recently updated production heat, if one is active."""
    row = conn.execute(
        """
        SELECT id::text
        FROM heats
        WHERE status NOT IN ('COMPLETED', 'ABORTED', 'CANCELLED')
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 1
        """
    ).fetchone()
    return row["id"] if row else None


def normalize_value(value: Any) -> tuple[float | None, str | None]:
    """Convert common PLC scalar values into the historian's numeric/text columns."""
    if isinstance(value, bool):
        return (1.0 if value else 0.0), None
    if isinstance(value, (int, float)):
        return float(value), None
    if value is None:
        return None, None
    return None, str(value)


def opc_quality(status_code: Any) -> str:
    """Map an OPC UA StatusCode to the historian data_quality enum."""
    if status_code is None:
        return "UNKNOWN"
    try:
        if status_code.is_good():
            return "GOOD"
        if status_code.is_uncertain():
            return "UNCERTAIN"
        if status_code.is_bad():
            return "BAD"
    except Exception:
        return "UNKNOWN"
    return "UNKNOWN"


def write_sample(
    conn: Connection,
    *,
    tag_id: str,
    heat_id: str | None,
    tag_name: str,
    node_id: str,
    value: Any,
    ts: datetime,
    quality: str,
    status_code: str,
) -> None:
    """Persist one OPC UA DataValue into TimescaleDB."""
    value_double, value_text = normalize_value(value)
    if value_double is None and value_text is None:
        LOGGER.warning("Skipping null value for %s (%s)", tag_name, node_id)
        return

    conn.execute(
        """
        INSERT INTO process_samples (
            ts,
            tag_id,
            heat_id,
            value_double,
            value_text,
            quality,
            attributes
        )
        VALUES (%s, %s::uuid, %s::uuid, %s, %s, %s::data_quality, %s::jsonb)
        """,
        (
            ts,
            tag_id,
            heat_id,
            value_double,
            value_text,
            quality,
            Jsonb(
                {
                    "source": "OPCUA",
                    "node_id": node_id,
                    "status_code": status_code,
                }
            ),
        ),
    )


async def run_session(conn: Connection, node_map: dict[str, str], tag_ids: dict[str, str]) -> None:
    """Connect to the OPC UA endpoint and poll configured nodes until the link drops."""
    client = Client(url=OPCUA_ENDPOINT, timeout=10)
    if OPCUA_USERNAME:
        client.set_user(OPCUA_USERNAME)
        client.set_password(OPCUA_PASSWORD)

    write_health("connecting", f"Connecting to {OPCUA_ENDPOINT}")
    async with client:
        nodes = {tag_name: client.get_node(node_id) for tag_name, node_id in node_map.items()}
        LOGGER.info("Connected to OPC UA server %s with %d mapped tags", OPCUA_ENDPOINT, len(nodes))

        while True:
            heat_id = active_heat_id(conn)
            successful_reads = 0
            cycle_success_at: datetime | None = None

            for tag_name, node in nodes.items():
                node_id = node_map[tag_name]
                try:
                    data_value = await node.read_data_value()
                    value = data_value.Value.Value if data_value.Value is not None else None
                    ts = normalize_timestamp(data_value.SourceTimestamp or data_value.ServerTimestamp)
                    quality = opc_quality(data_value.StatusCode)
                    status_code = str(data_value.StatusCode) if data_value.StatusCode is not None else "Unknown"
                    write_sample(
                        conn,
                        tag_id=tag_ids[tag_name],
                        heat_id=heat_id,
                        tag_name=tag_name,
                        node_id=node_id,
                        value=value,
                        ts=ts,
                        quality=quality,
                        status_code=status_code,
                    )
                    successful_reads += 1
                    cycle_success_at = utc_now()
                except Exception as exc:
                    LOGGER.warning("Read failed for %s (%s): %s", tag_name, node_id, exc)

            if successful_reads == 0:
                raise RuntimeError("No OPC UA tag could be read in the current polling cycle")

            write_health(
                "live",
                f"OPC UA connected; {successful_reads}/{len(nodes)} tags read",
                last_success_at=cycle_success_at,
            )
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def run() -> None:
    """Reconnect forever so transient PLC or historian outages self-heal."""
    node_map = load_node_map()
    write_health("starting", f"Configured {len(node_map)} OPC UA tags")

    while True:
        conn: Connection | None = None
        try:
            conn = connect_db()
            tag_ids = resolve_tag_ids(conn, node_map)
            await run_session(conn, node_map, tag_ids)
        except ConfigurationError:
            raise
        except Exception as exc:
            LOGGER.exception("PLC ingestion session failed: %s", exc)
            write_health("disconnected", str(exc))
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except ConfigurationError as exc:
        write_health("configuration_error", str(exc))
        LOGGER.error("Configuration error: %s", exc)
        raise SystemExit(2) from exc
