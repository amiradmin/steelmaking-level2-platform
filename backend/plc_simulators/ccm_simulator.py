from __future__ import annotations

import asyncio
import logging
import math

from common import run_plc_simulator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

ENDPOINT = "opc.tcp://0.0.0.0:4840/ccm/"
NAMESPACE_URI = "urn:steelmaking:plc:ccm"

INITIAL_VALUES = {
    "CCM.CastingSpeed": 2.55,
    "CCM.TundishTemperature": 1545.0,
    "CCM.MoldLevelPercent": 72.0,
    "CCM.StageCode": 1,
    "CCM.Ready": True,
    "CCM.Running": True,
    "CCM.Fault": False,
}


def values(elapsed: float) -> dict[str, object]:
    stage_code = 1 + int(elapsed // 40) % 3
    return {
        "CCM.CastingSpeed": float(2.55 + 0.18 * math.sin(elapsed / 12.0)),
        "CCM.TundishTemperature": float(1545.0 + 6.0 * math.sin(elapsed / 20.0)),
        "CCM.MoldLevelPercent": float(72.0 + 4.0 * math.sin(elapsed / 9.0)),
        "CCM.StageCode": stage_code,
        "CCM.Ready": True,
        "CCM.Running": True,
        "CCM.Fault": False,
    }


async def main() -> None:
    await run_plc_simulator(
        controller_name="CCM PLC",
        endpoint=ENDPOINT,
        namespace_uri=NAMESPACE_URI,
        object_node_id="CCM.Process",
        initial_values=INITIAL_VALUES,
        value_factory=values,
    )


if __name__ == "__main__":
    asyncio.run(main())
