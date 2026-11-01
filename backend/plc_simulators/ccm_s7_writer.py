from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import math
import os
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import snap7

from ccm_simulator import values as process_values


LOGGER = logging.getLogger("ccm-rnd-s7-writer")

PROCESS_DB = 300
PROCESS_DB_SIZE = 48
DIAGNOSTIC_DB = 310
DIAGNOSTIC_DB_SIZE = 12
SCAN_SECONDS = max(0.2, float(os.getenv("CCM_RND_SCAN_SECONDS", "1.0")))

# This is the proposed R&D contract documented in
# docs/engineering/CCM_RND_PLC_COMMISSIONING.md. It is not proof that these
# DBs exist or are reserved on the physical CPU.
STAGE_NAMES = {0: "IDLE", 1: "PREPARE", 2: "START_CAST", 3: "STEADY_CAST", 4: "END_CAST"}

STATUS_BITS = (
    ("CCM.Ready", 0),
    ("CCM.Running", 1),
    ("CCM.Fault", 2),
    ("CCM.CastingActive", 3),
    ("CCM.CoolingWaterOK", 4),
    ("CCM.MoldLevelControlOK", 5),
    ("CCM.EmergencyStopOK", 6),
    ("CCM.InterlockOK", 7),
)


def _finite_float(values: dict[str, Any], key: str) -> float:
    value = float(values[key])
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite, got {value!r}")
    return value


def pack_process_db(values: dict[str, Any]) -> bytearray:
    """Pack the proposed R&D DB300 contract in S7 big-endian byte order."""
    data = bytearray(PROCESS_DB_SIZE)
    real_fields = (
        ("CCM.CastingSpeed", 0),
        ("CCM.TundishTemperature", 4),
        ("CCM.MoldLevelPercent", 8),
        ("CCM.TundishWeightTon", 12),
        ("CCM.MoldCoolingWaterFlowM3h", 16),
        ("CCM.MoldCoolingWaterDeltaC", 20),
        ("CCM.SecondaryCoolingFlowM3h", 24),
        ("CCM.OscillationFrequencyCpm", 28),
        ("CCM.StopperPositionPercent", 32),
    )
    for key, offset in real_fields:
        struct.pack_into(">f", data, offset, _finite_float(values, key))

    stage_code = int(values["CCM.StageCode"])
    heat_number = int(values["CCM.HeatNumber"])
    alarm_code = int(values["CCM.AlarmCode"])
    if stage_code not in STAGE_NAMES:
        raise ValueError(f"Unsupported CCM stage code: {stage_code}")
    if not 0 <= heat_number <= 2_147_483_647:
        raise ValueError(f"Heat number is outside DINT range: {heat_number}")
    if not -32_768 <= alarm_code <= 32_767:
        raise ValueError(f"Alarm code is outside INT range: {alarm_code}")

    struct.pack_into(">h", data, 36, stage_code)
    struct.pack_into(">i", data, 40, heat_number)

    status = 0
    for key, bit in STATUS_BITS:
        if bool(values[key]):
            status |= 1 << bit
    data[44] = status
    struct.pack_into(">h", data, 46, alarm_code)
    return data


def pack_diagnostic_db(
    scan_counter: int,
    cycle_time_ms: float,
    *,
    watchdog_ok: bool,
    comms_ok: bool,
    heartbeat: bool,
) -> bytearray:
    data = bytearray(DIAGNOSTIC_DB_SIZE)
    struct.pack_into(">i", data, 0, scan_counter)
    struct.pack_into(">f", data, 4, float(cycle_time_ms))
    data[8] = (
        (1 if watchdog_ok else 0)
        | (2 if comms_ok else 0)
        | (4 if heartbeat else 0)
    )
    return data


def require_write_acknowledgements() -> None:
    expected = "DB300_48_DB310_12_VERIFIED_AND_RESERVED"
    actual = os.getenv("CCM_RND_DB_LAYOUT_ACK", "")
    if actual != expected:
        raise RuntimeError(
            "PLC writes are blocked. First verify that DB300 (48 bytes) and "
            "DB310 (12 bytes) exist, match the documented offsets, and are "
            "dedicated to this R&D generator. Then set "
            f"CCM_RND_DB_LAYOUT_ACK={expected}."
        )


def connect_and_preflight() -> tuple[snap7.Client, bytearray, bytearray]:
    host = os.getenv("CCM_RND_PLC_HOST", "192.168.1.10")
    port = int(os.getenv("CCM_RND_PLC_PORT", "102"))
    rack = int(os.getenv("CCM_RND_PLC_RACK", "0"))
    slot = int(os.getenv("CCM_RND_PLC_SLOT", "3"))

    client = snap7.Client()
    LOGGER.warning(
        "Connecting to R&D PLC %s:%s rack=%s slot=%s for read-only DB preflight",
        host, port, rack, slot,
    )
    client.connect(host, rack, slot, tcp_port=port)

    try:
        process = client.db_read(PROCESS_DB, 0, PROCESS_DB_SIZE)
        diagnostics = client.db_read(DIAGNOSTIC_DB, 0, DIAGNOSTIC_DB_SIZE)
        if len(process) != PROCESS_DB_SIZE or len(diagnostics) != DIAGNOSTIC_DB_SIZE:
            raise RuntimeError("PLC DB preflight returned unexpected block lengths")
    except Exception:
        client.disconnect()
        raise

    LOGGER.warning(
        "Read-only preflight passed: DB%d first %d bytes, DB%d first %d bytes.",
        PROCESS_DB, len(process), DIAGNOSTIC_DB, len(diagnostics),
    )
    return client, bytearray(process), bytearray(diagnostics)


def save_db_backup(process: bytearray, diagnostics: bytearray) -> Path:
    """Persist the exact DB ranges that this writer may later overwrite."""
    backup_dir = Path(os.getenv("CCM_RND_BACKUP_DIR", "/backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": {
            "host": os.getenv("CCM_RND_PLC_HOST", "192.168.1.10"),
            "port": int(os.getenv("CCM_RND_PLC_PORT", "102")),
            "rack": int(os.getenv("CCM_RND_PLC_RACK", "0")),
            "slot": int(os.getenv("CCM_RND_PLC_SLOT", "3")),
        },
        "note": "Raw pre-write DB byte ranges only; this is not a STEP 7 station or program backup.",
        "dbs": {
            str(PROCESS_DB): {
                "read_length": len(process),
                "hex": process.hex(),
                "base64": base64.b64encode(process).decode("ascii"),
                "sha256": hashlib.sha256(process).hexdigest(),
            },
            str(DIAGNOSTIC_DB): {
                "read_length": len(diagnostics),
                "hex": diagnostics.hex(),
                "base64": base64.b64encode(diagnostics).decode("ascii"),
                "sha256": hashlib.sha256(diagnostics).hexdigest(),
            },
        },
    }
    target = backup_dir / f"ccm-rnd-prewrite-{timestamp}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    LOGGER.warning("Pre-write DB backup saved to %s", target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate CCM R&D process values on Ubuntu; optionally write dedicated S7 DBs."
    )
    parser.add_argument(
        "--enable-plc-writes",
        action="store_true",
        help="Arm DB300/DB310 writes; requires the exact DB layout acknowledgement in the environment.",
    )
    parser.add_argument(
        "--backup-only",
        action="store_true",
        help="Read DB300/DB310 and save their raw bytes locally; performs no PLC writes.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Generate one sample and exit (dry-run unless --enable-plc-writes is also supplied).",
    )
    args = parser.parse_args()

    if args.enable_plc_writes:
        parser.error(
            "physical writes are disabled in the PLC-native architecture: "
            "FB300 owns DB300 and FB310 owns DB310. Use Snap7 read-only "
            "verification after the Siemens SCL application has been safely "
            "compiled and commissioned."
        )

    if args.backup_only and (args.enable_plc_writes or args.once):
        parser.error("--backup-only cannot be combined with --enable-plc-writes or --once")

    logging.basicConfig(
        level=os.getenv("CCM_RND_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    write_enabled = args.enable_plc_writes
    client: snap7.Client | None = None
    if args.backup_only:
        client, process_backup, diagnostic_backup = connect_and_preflight()
        try:
            save_db_backup(process_backup, diagnostic_backup)
        finally:
            client.disconnect()
        LOGGER.warning("Backup-only operation complete; no PLC writes were performed.")
        return 0

    if write_enabled:
        require_write_acknowledgements()
        client, process_backup, diagnostic_backup = connect_and_preflight()
        # A persistent pre-write backup is mandatory. If this fails, execution
        # stops before the first DB write.
        save_db_backup(process_backup, diagnostic_backup)
    else:
        LOGGER.warning(
            "DRY-RUN MODE: no PLC connection and no writes. "
            "Use --enable-plc-writes only after DB300/DB310 are independently verified and reserved."
        )

    started = time.monotonic()
    scan_counter = 0
    heartbeat = False

    try:
        while True:
            tick_started = time.perf_counter()
            elapsed = time.monotonic() - started
            scan_counter += 1
            if scan_counter % 5 == 0:
                heartbeat = not heartbeat

            sample = process_values(elapsed, scan_counter)
            cycle_time_ms = (time.perf_counter() - tick_started) * 1000.0
            watchdog_ok = cycle_time_ms <= SCAN_SECONDS * 1000.0
            process_buffer = pack_process_db(sample)
            diagnostic_buffer = pack_diagnostic_db(
                scan_counter,
                cycle_time_ms,
                watchdog_ok=watchdog_ok,
                comms_ok=write_enabled,
                heartbeat=heartbeat,
            )

            if client is not None:
                # Deliberately restricted to the two dedicated DB ranges.
                client.db_write(PROCESS_DB, 0, process_buffer)
                client.db_write(DIAGNOSTIC_DB, 0, diagnostic_buffer)

            if scan_counter == 1 or scan_counter % 10 == 0 or args.once:
                LOGGER.info(
                    "mode=%s stage=%s heat=%s speed=%.3f mold=%.2f%% "
                    "tundish=%.1ft alarm=%s scan=%s",
                    "PLC_WRITE" if write_enabled else "DRY_RUN",
                    sample["CCM.StageName"],
                    sample["CCM.HeatNumber"],
                    sample["CCM.CastingSpeed"],
                    sample["CCM.MoldLevelPercent"],
                    sample["CCM.TundishWeightTon"],
                    sample["CCM.AlarmCode"],
                    scan_counter,
                )

            if args.once:
                return 0

            remaining = SCAN_SECONDS - (time.perf_counter() - tick_started)
            time.sleep(max(0.0, remaining))
    finally:
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                LOGGER.exception("Error while disconnecting from S7 PLC")


if __name__ == "__main__":
    raise SystemExit(main())
