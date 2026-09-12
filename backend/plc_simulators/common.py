from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Callable, Mapping
from typing import Any

from asyncua import Server, ua

from s7_memory import S7MemoryMirror


LOGGER = logging.getLogger("plc-simulator")

TagValues = Mapping[str, Any]
ValueFactory = Callable[[float, int], TagValues]


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def cpu_mode() -> str:
    value = os.getenv("PLC_SIM_CPU_MODE", "RUN").strip().upper()
    return value if value in {"RUN", "STOP"} else "RUN"


async def run_plc_simulator(
    *,
    controller_name: str,
    controller_prefix: str,
    endpoint: str,
    namespace_uri: str,
    object_node_id: str,
    initial_values: TagValues,
    value_factory: ValueFactory,
    scan_interval_seconds: float | None = None,
) -> None:
    """Run one isolated process simulator representing an S7-400-style controller.

    Each simulator has two integration faces:
    - S7 classic data-block memory on TCP/102, used to mimic an S7-400 PLC.
    - OPC UA, retained as a diagnostic/development view during the transition.

    The model reproduces cyclic execution, RUN/STOP state, DB-style memory,
    process interlocks and basic diagnostics. It is not a bit-exact Siemens CPU or
    STEP 7 firmware emulator.
    """
    logging.getLogger("asyncua").setLevel(logging.WARNING)

    scan_interval = scan_interval_seconds or env_float("PLC_SIM_SCAN_SECONDS", 0.1)
    scan_interval = max(scan_interval, 0.02)
    initial_cpu_mode = cpu_mode()

    s7_mirror = S7MemoryMirror(controller_prefix)
    s7_mirror.start()

    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name(f"{controller_name} S7-400 Process Simulator")

    namespace_index = await server.register_namespace(namespace_uri)
    process = await server.nodes.objects.add_object(
        ua.NodeId(object_node_id, namespace_index),
        f"{controller_name} Process",
    )

    diagnostics: dict[str, Any] = {
        f"{controller_prefix}.PLC.CpuModeCode": 2 if initial_cpu_mode == "RUN" else 0,
        f"{controller_prefix}.PLC.CpuMode": initial_cpu_mode,
        f"{controller_prefix}.PLC.ScanCounter": 0,
        f"{controller_prefix}.PLC.CycleTimeMs": 0.0,
        f"{controller_prefix}.PLC.WatchdogOK": True,
        f"{controller_prefix}.PLC.CommsOK": True,
        f"{controller_prefix}.PLC.Heartbeat": False,
        f"{controller_prefix}.PLC.Simulated": True,
    }

    nodes: dict[str, Any] = {}
    for tag_name, initial_value in {**initial_values, **diagnostics}.items():
        node = await process.add_variable(
            ua.NodeId(tag_name, namespace_index),
            tag_name,
            initial_value,
        )
        nodes[tag_name] = node

    s7_mirror.write_many({**dict(initial_values), **diagnostics})

    LOGGER.info("%s OPC UA diagnostic endpoint: %s", controller_name, endpoint)
    LOGGER.info("PLC-style scan interval: %.1f ms", scan_interval * 1000.0)
    LOGGER.info("CPU mode: %s", initial_cpu_mode)
    LOGGER.info("Namespace index: %s", namespace_index)
    for tag_name in nodes:
        LOGGER.info("%s -> ns=%s;s=%s", tag_name, namespace_index, tag_name)

    started = time.monotonic()
    scan_counter = 0

    try:
        async with server:
            while True:
                scan_started = time.perf_counter()
                elapsed = time.monotonic() - started
                scan_counter += 1
                mode = cpu_mode()
                process_values: dict[str, Any] = {}

                if mode == "RUN":
                    process_values = dict(value_factory(elapsed, scan_counter))
                    for tag_name, value in process_values.items():
                        node = nodes.get(tag_name)
                        if node is None:
                            LOGGER.warning("Ignoring undefined simulator tag %s", tag_name)
                            continue
                        await node.write_value(value)

                cycle_time_ms = (time.perf_counter() - scan_started) * 1000.0
                watchdog_ok = cycle_time_ms <= scan_interval * 2000.0
                heartbeat = bool((scan_counter // 5) % 2)

                diagnostic_values: dict[str, Any] = {
                    f"{controller_prefix}.PLC.CpuModeCode": 2 if mode == "RUN" else 0,
                    f"{controller_prefix}.PLC.CpuMode": mode,
                    f"{controller_prefix}.PLC.ScanCounter": scan_counter,
                    f"{controller_prefix}.PLC.CycleTimeMs": float(cycle_time_ms),
                    f"{controller_prefix}.PLC.WatchdogOK": bool(watchdog_ok),
                    f"{controller_prefix}.PLC.CommsOK": True,
                    f"{controller_prefix}.PLC.Heartbeat": heartbeat,
                    f"{controller_prefix}.PLC.Simulated": True,
                }

                for tag_name, value in diagnostic_values.items():
                    await nodes[tag_name].write_value(value)

                s7_mirror.set_cpu_mode(mode)
                s7_mirror.write_many({**process_values, **diagnostic_values})

                remaining = scan_interval - (time.perf_counter() - scan_started)
                await asyncio.sleep(max(0.0, remaining))
    finally:
        s7_mirror.stop()
