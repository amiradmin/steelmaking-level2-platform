from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from snap7 import AsyncClient, util


ADDRESS_RE = re.compile(
    r"^DB(?P<db>\d+)\.(?P<kind>DBD|DBW|DBX)(?P<byte>\d+)(?:\.(?P<bit>[0-7]))?$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only Siemens S7 DB probe for Level 2 commissioning.",
    )
    parser.add_argument("--controller", choices=("EAF", "LF", "CCM"), default="EAF")
    parser.add_argument("--host", default=os.getenv("EAF_PLC_HOST", ""))
    parser.add_argument("--port", type=int, default=int(os.getenv("EAF_PLC_PORT", "102")))
    parser.add_argument("--rack", type=int, default=int(os.getenv("EAF_PLC_RACK", "0")))
    parser.add_argument("--slot", type=int, default=int(os.getenv("EAF_PLC_SLOT", "2")))
    parser.add_argument(
        "--map",
        dest="map_path",
        default=os.getenv("OPCUA_GATEWAY_MAP_PATH", "/app/s7_address_map.json"),
    )
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--limit", type=int, default=12)
    return parser.parse_args()


def type_size(data_type: str) -> int:
    if data_type in {"REAL", "DINT"}:
        return 4
    if data_type == "INT":
        return 2
    if data_type == "BOOL":
        return 1
    raise ValueError(f"Unsupported S7 data type: {data_type}")


def parse_address(address: str) -> tuple[int, int, int | None]:
    match = ADDRESS_RE.match(address)
    if not match:
        raise ValueError(f"Unsupported S7 address: {address}")
    return (
        int(match.group("db")),
        int(match.group("byte")),
        int(match.group("bit")) if match.group("bit") is not None else None,
    )


def decode_value(buffer: bytearray, byte_index: int, bit_index: int | None, data_type: str) -> Any:
    if data_type == "REAL":
        return float(util.get_real(buffer, byte_index))
    if data_type == "INT":
        return int(util.get_int(buffer, byte_index))
    if data_type == "DINT":
        return int(util.get_dint(buffer, byte_index))
    if data_type == "BOOL":
        if bit_index is None:
            raise ValueError("BOOL requires a bit index")
        return bool(util.get_bool(buffer, byte_index, bit_index))
    raise ValueError(f"Unsupported S7 data type: {data_type}")


def db_read_plan(controller_map: dict[str, Any]) -> dict[int, int]:
    plan: dict[int, int] = {}
    for definition in controller_map["tags"].values():
        db_number, byte_index, _ = parse_address(definition["address"])
        end = byte_index + type_size(definition["type"])
        plan[db_number] = max(plan.get(db_number, 0), end)
    return plan


async def main() -> None:
    args = parse_args()
    if not args.host:
        raise SystemExit("ERROR: --host or EAF_PLC_HOST is required")

    mapping = json.loads(Path(args.map_path).read_text(encoding="utf-8"))
    controller_map = mapping[args.controller]

    print("=== READ-ONLY S7 PROBE ===")
    print(f"Controller: {args.controller}")
    print(f"Target:     {args.host}:{args.port}")
    print(f"Rack/Slot:  {args.rack}/{args.slot}")
    print("Mode:       DB READ ONLY (no PLC writes)\n")

    client = AsyncClient()
    try:
        await asyncio.wait_for(
            client.connect(
                args.host,
                args.rack,
                args.slot,
                tcp_port=args.port,
            ),
            timeout=args.timeout,
        )

        buffers: dict[int, bytearray] = {}
        for db_number, size in db_read_plan(controller_map).items():
            buffers[db_number] = await asyncio.wait_for(
                client.db_read(db_number, 0, size),
                timeout=args.timeout,
            )
            print(f"PASS: DB{db_number} readable ({size} bytes)")

        print("\nDecoded sample values:")
        shown = 0
        for tag_name, definition in controller_map["tags"].items():
            if shown >= max(1, args.limit):
                break
            db_number, byte_index, bit_index = parse_address(definition["address"])
            value = decode_value(
                buffers[db_number],
                byte_index,
                bit_index,
                definition["type"],
            )
            print(
                f"  {tag_name:<34} {definition['address']:<15} "
                f"{definition['type']:<5} = {value}"
            )
            shown += 1

        print("\nPASS: S7 PLC connection and configured DB reads succeeded.")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
