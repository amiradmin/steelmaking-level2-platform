from __future__ import annotations

import asyncio
import logging
import math
import time

from asyncua import Server, ua


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("opcua-simulator")

ENDPOINT = "opc.tcp://0.0.0.0:4840/steelmaking/"
NAMESPACE_URI = "urn:steelmaking:level2:test"


async def main() -> None:
    server = Server()
    await server.init()
    server.set_endpoint(ENDPOINT)
    server.set_server_name("Steelmaking Level 2 OPC UA Test Server")

    namespace_index = await server.register_namespace(NAMESPACE_URI)
    process = await server.nodes.objects.add_object(
        ua.NodeId("Steelmaking.Process", namespace_index),
        "Steelmaking Process",
    )

    definitions = {
        "EAF.PowerMW": 55.0,
        "EAF.CurrentKA": 41.0,
        "EAF.OxygenFlow": 3100.0,
        "EAF.SteelTemperature": 1580.0,
        "LF.SteelTemperature": 1590.0,
        "LF.ArgonFlow": 120.0,
        "CCM.CastingSpeed": 2.55,
        "CCM.TundishTemperature": 1545.0,
    }

    nodes = {}
    for tag_name, initial_value in definitions.items():
        node = await process.add_variable(
            ua.NodeId(tag_name, namespace_index),
            tag_name,
            initial_value,
        )
        nodes[tag_name] = node

    LOGGER.info("OPC UA test server listening on %s", ENDPOINT)
    LOGGER.info("Namespace index: %s", namespace_index)
    for tag_name in nodes:
        LOGGER.info("%s -> ns=%s;s=%s", tag_name, namespace_index, tag_name)

    async with server:
        while True:
            t = time.monotonic()
            values = {
                "EAF.PowerMW": 55.0 + 5.0 * math.sin(t / 8.0),
                "EAF.CurrentKA": 41.0 + 3.0 * math.sin(t / 6.0),
                "EAF.OxygenFlow": 3100.0 + 220.0 * math.sin(t / 10.0),
                "EAF.SteelTemperature": 1580.0 + 18.0 * math.sin(t / 30.0),
                "LF.SteelTemperature": 1590.0 + 8.0 * math.sin(t / 24.0),
                "LF.ArgonFlow": 120.0 + 25.0 * math.sin(t / 7.0),
                "CCM.CastingSpeed": 2.55 + 0.18 * math.sin(t / 12.0),
                "CCM.TundishTemperature": 1545.0 + 6.0 * math.sin(t / 20.0),
            }

            for tag_name, value in values.items():
                await nodes[tag_name].write_value(float(value))

            await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(main())
