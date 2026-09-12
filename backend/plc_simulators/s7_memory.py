from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from snap7.server import Server
from snap7.type import SrvArea
from snap7 import util


LOGGER = logging.getLogger("plc-simulator.s7")
ADDRESS_RE = re.compile(r"^DB(?P<db>\d+)\.(?P<kind>DBD|DBW|DBX)(?P<byte>\d+)(?:\.(?P<bit>[0-7]))?$")


class S7MemoryMirror:
    """Expose simulator values through S7-style data blocks.

    The addresses come from the project-defined simulation map. They intentionally
    mimic classic S7-300/400 DB addressing for integration tests and can later be
    replaced with the real plant DB map without changing higher-level tag names.
    """

    def __init__(self, controller_prefix: str) -> None:
        self.controller_prefix = controller_prefix
        self.enabled = os.getenv("PLC_SIM_S7_ENABLED", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        self.port = int(os.getenv("PLC_SIM_S7_PORT", "102"))
        self.server: Server | None = None
        self.buffers: dict[int, bytearray] = {}
        self.tag_map: dict[str, dict[str, Any]] = {}

        map_path = Path(__file__).with_name("s7_address_map.json")
        mapping = json.loads(map_path.read_text(encoding="utf-8"))
        controller = mapping[controller_prefix]
        self.tag_map = controller["tags"]

        db_numbers: set[int] = set()
        for definition in self.tag_map.values():
            match = ADDRESS_RE.match(definition["address"])
            if match:
                db_numbers.add(int(match.group("db")))

        for db_number in db_numbers:
            self.buffers[db_number] = bytearray(256)

    def start(self) -> None:
        if not self.enabled:
            LOGGER.info("S7 protocol endpoint disabled for %s", self.controller_prefix)
            return

        server = Server(log=False)
        for db_number, buffer in self.buffers.items():
            server.register_area(SrvArea.DB, db_number, buffer)
        server.start(tcp_port=self.port)
        server.set_cpu_status(8)
        self.server = server
        LOGGER.info(
            "%s S7 server listening on TCP/%s with DBs %s",
            self.controller_prefix,
            self.port,
            sorted(self.buffers),
        )

    def stop(self) -> None:
        if self.server is not None:
            self.server.stop()
            self.server = None

    def set_cpu_mode(self, mode: str) -> None:
        if self.server is None:
            return
        self.server.set_cpu_status(8 if mode == "RUN" else 4)

    def write_many(self, values: dict[str, Any]) -> None:
        if not self.enabled:
            return
        for tag_name, value in values.items():
            definition = self.tag_map.get(tag_name)
            if not definition:
                continue
            self._write(definition["address"], definition["type"], value)

    def _write(self, address: str, data_type: str, value: Any) -> None:
        match = ADDRESS_RE.match(address)
        if not match:
            raise ValueError(f"Unsupported S7 simulation address: {address}")

        db_number = int(match.group("db"))
        byte_index = int(match.group("byte"))
        bit_text = match.group("bit")
        buffer = self.buffers[db_number]

        if data_type == "REAL":
            util.set_real(buffer, byte_index, float(value))
        elif data_type == "INT":
            util.set_int(buffer, byte_index, int(value))
        elif data_type == "DINT":
            util.set_dint(buffer, byte_index, int(value))
        elif data_type == "BOOL":
            if bit_text is None:
                raise ValueError(f"BOOL address requires bit index: {address}")
            util.set_bool(buffer, byte_index, int(bit_text), bool(value))
        else:
            raise ValueError(f"Unsupported S7 simulation type: {data_type}")
