from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from asyncua import Server, ua
from snap7 import AsyncClient, util


logging.basicConfig(
    level=os.getenv("OPCUA_GATEWAY_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("central-opcua-gateway")

ADDRESS_RE = re.compile(
    r"^DB(?P<db>\d+)\.(?P<kind>DBD|DBW|DBX)(?P<byte>\d+)(?:\.(?P<bit>[0-7]))?$"
)
ENDPOINT = os.getenv("OPCUA_GATEWAY_ENDPOINT", "opc.tcp://0.0.0.0:4840/steelmaking/")
NAMESPACE_URI = "urn:steelmaking:level2:central-opcua"
POLL_SECONDS = float(os.getenv("OPCUA_GATEWAY_POLL_SECONDS", "0.5"))
RECONNECT_SECONDS = float(os.getenv("OPCUA_GATEWAY_RECONNECT_SECONDS", "2"))
HEALTH_PATH = Path(os.getenv("OPCUA_GATEWAY_HEALTH_PATH", "/tmp/opcua-gateway-health.json"))
MAP_PATH = Path(os.getenv("OPCUA_GATEWAY_MAP_PATH", "/app/s7_address_map.json"))


@dataclass(frozen=True)
class PlcConfig:
    name: str
    host: str
    port: int
    rack: int
    slot: int


def plc_config(name: str, default_host: str) -> PlcConfig:
    prefix = f"{name}_PLC_"
    return PlcConfig(
        name=name,
        host=os.getenv(f"{prefix}HOST", default_host),
        port=int(os.getenv(f"{prefix}PORT", "102")),
        rack=int(os.getenv(f"{prefix}RACK", "0")),
        slot=int(os.getenv(f"{prefix}SLOT", "2")),
    )


PLC_CONFIGS = {
    "EAF": plc_config("EAF", "eaf-plc-simulator"),
    "LF": plc_config("LF", "lf-plc-simulator"),
    "CCM": plc_config("CCM", "ccm-plc-simulator"),
}


def type_size(data_type: str) -> int:
    if data_type in {"REAL", "DINT"}:
        return 4
    if data_type == "INT":
        return 2
    if data_type == "BOOL":
        return 1
    raise ValueError(f"Unsupported S7 data type: {data_type}")


def parse_address(address: str) -> tuple[int, str, int, int | None]:
    match = ADDRESS_RE.match(address)
    if not match:
        raise ValueError(f"Unsupported S7 address: {address}")
    return (
        int(match.group("db")),
        match.group("kind"),
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


def initial_value(data_type: str) -> Any:
    if data_type == "REAL":
        return 0.0
    if data_type in {"INT", "DINT"}:
        return 0
    if data_type == "BOOL":
        return False
    raise ValueError(f"Unsupported S7 data type: {data_type}")


def load_map() -> dict[str, Any]:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def db_read_plan(controller_map: dict[str, Any]) -> dict[int, int]:
    plan: dict[int, int] = {}
    for definition in controller_map["tags"].values():
        db_number, _kind, byte_index, _bit_index = parse_address(definition["address"])
        end = byte_index + type_size(definition["type"])
        plan[db_number] = max(plan.get(db_number, 0), end)
    return plan


async def read_controller_snapshot(
    client: AsyncClient,
    controller_map: dict[str, Any],
) -> dict[str, Any]:
    buffers: dict[int, bytearray] = {}
    for db_number, size in db_read_plan(controller_map).items():
        buffers[db_number] = await client.db_read(db_number, 0, size)

    values: dict[str, Any] = {}
    for tag_name, definition in controller_map["tags"].items():
        db_number, _kind, byte_index, bit_index = parse_address(definition["address"])
        values[tag_name] = decode_value(
            buffers[db_number],
            byte_index,
            bit_index,
            definition["type"],
        )
    return values


async def write_datavalue(node: Any, value: Any, status: int) -> None:
    now = datetime.now(timezone.utc)
    await node.write_value(
        ua.DataValue(
            ua.Variant(value),
            StatusCode=ua.StatusCode(status),
            SourceTimestamp=now,
            ServerTimestamp=now,
        )
    )


class HealthState:
    def __init__(self) -> None:
        self.connected = {name: False for name in PLC_CONFIGS}
        self.last_success_at: str | None = None
        self.server_ready = False
        self._lock = asyncio.Lock()

    async def persist(self) -> None:
        async with self._lock:
            payload = {
                "server_ready": self.server_ready,
                "connected": dict(self.connected),
                "last_success_at": self.last_success_at,
            }
            tmp = HEALTH_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(HEALTH_PATH)


async def poll_plc(
    config: PlcConfig,
    controller_map: dict[str, Any],
    nodes: dict[str, Any],
    connected_node: Any,
    health: HealthState,
) -> None:
    last_values = {
        tag_name: initial_value(definition["type"])
        for tag_name, definition in controller_map["tags"].items()
    }

    while True:
        client = AsyncClient()
        try:
            LOGGER.info(
                "Connecting to %s S7 endpoint %s:%s rack=%s slot=%s",
                config.name,
                config.host,
                config.port,
                config.rack,
                config.slot,
            )
            await client.connect(
                config.host,
                config.rack,
                config.slot,
                tcp_port=config.port,
            )
            health.connected[config.name] = True
            await connected_node.write_value(True)
            await health.persist()
            LOGGER.info("Connected to %s S7 PLC", config.name)

            while True:
                values = await read_controller_snapshot(client, controller_map)
                last_values.update(values)
                for tag_name, value in values.items():
                    await write_datavalue(nodes[tag_name], value, ua.StatusCodes.Good)

                health.connected[config.name] = True
                health.last_success_at = datetime.now(timezone.utc).isoformat()
                await connected_node.write_value(True)
                await health.persist()
                await asyncio.sleep(POLL_SECONDS)

        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("%s S7 polling failed", config.name)
            health.connected[config.name] = False
            await connected_node.write_value(False)
            for tag_name, value in last_values.items():
                try:
                    await write_datavalue(
                        nodes[tag_name],
                        value,
                        ua.StatusCodes.BadNoCommunication,
                    )
                except Exception:
                    LOGGER.exception("Failed to mark %s as bad quality", tag_name)
            await health.persist()
            await asyncio.sleep(RECONNECT_SECONDS)
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass


async def main() -> None:
    mapping = load_map()

    server = Server()
    await server.init()
    server.set_endpoint(ENDPOINT)
    server.set_server_name("Steelmaking Level 2 Central OPC UA Server")
    namespace_index = await server.register_namespace(NAMESPACE_URI)

    root = await server.nodes.objects.add_object(
        ua.NodeId("Steelmaking.Level2", namespace_index),
        "Steelmaking Level 2",
    )

    controller_nodes: dict[str, dict[str, Any]] = {}
    connected_nodes: dict[str, Any] = {}

    for controller_name in PLC_CONFIGS:
        controller_map = mapping[controller_name]
        obj = await root.add_object(
            ua.NodeId(f"{controller_name}.Process", namespace_index),
            f"{controller_name} Process",
        )
        controller_nodes[controller_name] = {}

        for tag_name, definition in controller_map["tags"].items():
            node = await obj.add_variable(
                ua.NodeId(tag_name, namespace_index),
                tag_name,
                initial_value(definition["type"]),
            )
            controller_nodes[controller_name][tag_name] = node

        connected_nodes[controller_name] = await obj.add_variable(
            ua.NodeId(f"Gateway.{controller_name}.Connected", namespace_index),
            f"{controller_name} Connected",
            False,
        )

    health = HealthState()
    health.server_ready = True
    await health.persist()

    LOGGER.info("Central OPC UA server listening on %s", ENDPOINT)
    LOGGER.info("Namespace index: %s", namespace_index)
    for controller_name, config in PLC_CONFIGS.items():
        LOGGER.info(
            "%s source: %s:%s rack=%s slot=%s",
            controller_name,
            config.host,
            config.port,
            config.rack,
            config.slot,
        )

    async with server:
        tasks = [
            asyncio.create_task(
                poll_plc(
                    PLC_CONFIGS[controller_name],
                    mapping[controller_name],
                    controller_nodes[controller_name],
                    connected_nodes[controller_name],
                    health,
                ),
                name=f"poll-{controller_name.lower()}",
            )
            for controller_name in PLC_CONFIGS
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
