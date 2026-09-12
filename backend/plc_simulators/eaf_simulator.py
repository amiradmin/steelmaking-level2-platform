from __future__ import annotations

import asyncio
import logging
import math

from common import run_plc_simulator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

ENDPOINT = "opc.tcp://0.0.0.0:4840/eaf/"
NAMESPACE_URI = "urn:steelmaking:plc:eaf"

INITIAL_VALUES = {
    "EAF.PowerMW": 55.0,
    "EAF.CurrentKA": 41.0,
    "EAF.OxygenFlow": 3100.0,
    "EAF.SteelTemperature": 1580.0,
    "EAF.StageCode": 1,
    "EAF.Ready": True,
    "EAF.Running": True,
    "EAF.Fault": False,
}


def values(elapsed: float) -> dict[str, object]:
    stage_code = 1 + int(elapsed // 30) % 4
    return {
        "EAF.PowerMW": float(55.0 + 5.0 * math.sin(elapsed / 8.0)),
        "EAF.CurrentKA": float(41.0 + 3.0 * math.sin(elapsed / 6.0)),
        "EAF.OxygenFlow": float(3100.0 + 220.0 * math.sin(elapsed / 10.0)),
        "EAF.SteelTemperature": float(1580.0 + 18.0 * math.sin(elapsed / 30.0)),
        "EAF.StageCode": stage_code,
        "EAF.Ready": True,
        "EAF.Running": True,
        "EAF.Fault": False,
    }


async def main() -> None:
    await run_plc_simulator(
        controller_name="EAF PLC",
        endpoint=ENDPOINT,
        namespace_uri=NAMESPACE_URI,
        object_node_id="EAF.Process",
        initial_values=INITIAL_VALUES,
        value_factory=values,
    )


if __name__ == "__main__":
    asyncio.run(main())
