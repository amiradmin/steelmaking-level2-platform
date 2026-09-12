from __future__ import annotations

import asyncio
import logging
import math

from common import run_plc_simulator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

ENDPOINT = "opc.tcp://0.0.0.0:4840/lf/"
NAMESPACE_URI = "urn:steelmaking:plc:lf"

INITIAL_VALUES = {
    "LF.SteelTemperature": 1590.0,
    "LF.ArgonFlow": 120.0,
    "LF.StageCode": 1,
    "LF.Ready": True,
    "LF.Running": True,
    "LF.Fault": False,
}


def values(elapsed: float) -> dict[str, object]:
    stage_code = 1 + int(elapsed // 35) % 3
    return {
        "LF.SteelTemperature": float(1590.0 + 8.0 * math.sin(elapsed / 24.0)),
        "LF.ArgonFlow": float(120.0 + 25.0 * math.sin(elapsed / 7.0)),
        "LF.StageCode": stage_code,
        "LF.Ready": True,
        "LF.Running": True,
        "LF.Fault": False,
    }


async def main() -> None:
    await run_plc_simulator(
        controller_name="LF PLC",
        endpoint=ENDPOINT,
        namespace_uri=NAMESPACE_URI,
        object_node_id="LF.Process",
        initial_values=INITIAL_VALUES,
        value_factory=values,
    )


if __name__ == "__main__":
    asyncio.run(main())
