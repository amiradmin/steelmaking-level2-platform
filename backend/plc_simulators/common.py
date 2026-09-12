from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Mapping
from typing import Any

from asyncua import Server, ua


LOGGER = logging.getLogger("plc-simulator")

TagValues = Mapping[str, Any]
ValueFactory = Callable[[float], TagValues]


async def run_plc_simulator(
    *,
    controller_name: str,
    endpoint: str,
    namespace_uri: str,
    object_node_id: str,
    initial_values: TagValues,
    value_factory: ValueFactory,
    update_interval_seconds: float = 1.0,
) -> None:
    """Run one isolated process simulator representing an S7-400 controller."""
    server = Server()
    await server.init()
    server.set_endpoint(endpoint)
    server.set_server_name(f"{controller_name} S7-400 Process Simulator")

    namespace_index = await server.register_namespace(namespace_uri)
    process = await server.nodes.objects.add_object(
        ua.NodeId(object_node_id, namespace_index),
        f"{controller_name} Process",
    )

    nodes: dict[str, Any] = {}
    for tag_name, initial_value in initial_values.items():
        node = await process.add_variable(
            ua.NodeId(tag_name, namespace_index),
            tag_name,
            initial_value,
        )
        nodes[tag_name] = node

    LOGGER.info("%s simulator listening on %s", controller_name, endpoint)
    LOGGER.info("Namespace index: %s", namespace_index)
    for tag_name in nodes:
        LOGGER.info("%s -> ns=%s;s=%s", tag_name, namespace_index, tag_name)

    async with server:
        while True:
            elapsed = time.monotonic()
            values = value_factory(elapsed)

            for tag_name, value in values.items():
                node = nodes.get(tag_name)
                if node is None:
                    LOGGER.warning("Ignoring undefined simulator tag %s", tag_name)
                    continue
                await node.write_value(value)

            await asyncio.sleep(update_interval_seconds)
