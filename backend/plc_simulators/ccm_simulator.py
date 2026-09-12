from __future__ import annotations

import asyncio
import logging
import math
import os

from common import run_plc_simulator


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ENDPOINT = "opc.tcp://0.0.0.0:4840/ccm/"
NAMESPACE_URI = "urn:steelmaking:plc:ccm"
CYCLE_SECONDS = 240.0
FAULT_MODE = os.getenv("PLC_SIM_FAULT_MODE", "NONE").strip().upper()

INITIAL_VALUES = {
    "CCM.CastingSpeed": 0.0,
    "CCM.TundishTemperature": 1548.0,
    "CCM.MoldLevelPercent": 70.0,
    "CCM.TundishWeightTon": 38.0,
    "CCM.MoldCoolingWaterFlowM3h": 920.0,
    "CCM.MoldCoolingWaterDeltaC": 7.5,
    "CCM.SecondaryCoolingFlowM3h": 680.0,
    "CCM.OscillationFrequencyCpm": 0.0,
    "CCM.StopperPositionPercent": 0.0,
    "CCM.StageCode": 0,
    "CCM.StageName": "IDLE",
    "CCM.HeatNumber": 1000,
    "CCM.Ready": True,
    "CCM.Running": False,
    "CCM.Fault": False,
    "CCM.AlarmCode": 0,
    "CCM.CastingActive": False,
    "CCM.CoolingWaterOK": True,
    "CCM.MoldLevelControlOK": True,
    "CCM.EmergencyStopOK": True,
    "CCM.InterlockOK": True,
}


def lerp(start: float, end: float, ratio: float) -> float:
    return start + (end - start) * max(0.0, min(1.0, ratio))


def values(elapsed: float, scan_counter: int) -> dict[str, object]:
    cycle = elapsed % CYCLE_SECONDS
    heat_number = 1000 + int(elapsed // CYCLE_SECONDS)

    if cycle < 20.0:
        stage_code, stage_name = 1, "PREPARE"
        casting_speed = 0.0
        mold_level = 68.0
        tundish_temp = 1548.0
        tundish_weight = 38.0
        oscillation = 0.0
        stopper = 0.0
        casting_active = False
    elif cycle < 50.0:
        p = (cycle - 20.0) / 30.0
        stage_code, stage_name = 2, "START_CAST"
        casting_speed = lerp(0.4, 2.2, p)
        mold_level = 70.0 + 3.0 * math.sin(elapsed / 2.8) * (1.0 - 0.6 * p)
        tundish_temp = lerp(1548.0, 1544.0, p)
        tundish_weight = lerp(38.0, 34.0, p)
        oscillation = 120.0 + 20.0 * p
        stopper = 36.0 + 8.0 * math.sin(elapsed / 4.0)
        casting_active = True
    elif cycle < 210.0:
        p = (cycle - 50.0) / 160.0
        stage_code, stage_name = 3, "STEADY_CAST"
        casting_speed = 2.45 + 0.12 * math.sin(elapsed / 14.0)
        mold_level = 70.0 + 1.2 * math.sin(elapsed / 5.0) + 0.4 * math.sin(elapsed / 1.7)
        tundish_temp = lerp(1544.0, 1536.0, p) + 0.8 * math.sin(elapsed / 18.0)
        tundish_weight = lerp(34.0, 9.0, p)
        oscillation = 145.0 + 4.0 * math.sin(elapsed / 12.0)
        stopper = 42.0 + 5.0 * math.sin(elapsed / 8.0) - 0.35 * (mold_level - 70.0)
        casting_active = True
    elif cycle < 235.0:
        p = (cycle - 210.0) / 25.0
        stage_code, stage_name = 4, "END_CAST"
        casting_speed = lerp(2.2, 0.3, p)
        mold_level = lerp(70.0, 55.0, p)
        tundish_temp = lerp(1536.0, 1532.0, p)
        tundish_weight = lerp(9.0, 2.5, p)
        oscillation = lerp(140.0, 40.0, p)
        stopper = lerp(38.0, 8.0, p)
        casting_active = True
    else:
        stage_code, stage_name = 0, "IDLE"
        casting_speed = 0.0
        mold_level = 55.0
        tundish_temp = 1532.0
        tundish_weight = 2.5
        oscillation = 0.0
        stopper = 0.0
        casting_active = False

    mold_water_flow = 925.0 + 20.0 * math.sin(elapsed / 17.0)
    emergency_stop_ok = True

    if FAULT_MODE == "COOLING_WATER_LOW":
        mold_water_flow = 760.0
    elif FAULT_MODE == "MOLD_LEVEL_HIGH":
        mold_level = 91.0
    elif FAULT_MODE == "MOLD_LEVEL_LOW":
        mold_level = 43.0
    elif FAULT_MODE == "EMERGENCY_STOP":
        emergency_stop_ok = False
    elif FAULT_MODE == "TUNDISH_TEMP_HIGH":
        tundish_temp = 1575.0

    water_delta = 7.2 + 0.8 * casting_speed + 0.3 * math.sin(elapsed / 15.0)
    secondary_flow = 520.0 + 65.0 * casting_speed + 15.0 * math.sin(elapsed / 20.0)

    cooling_ok = mold_water_flow > 840.0
    level_control_ok = 50.0 <= mold_level <= 85.0
    interlock_ok = cooling_ok and level_control_ok and emergency_stop_ok
    fault = not interlock_ok

    if not cooling_ok:
        alarm_code = 301
    elif not level_control_ok:
        alarm_code = 302
    elif not emergency_stop_ok:
        alarm_code = 303
    elif tundish_temp > 1565.0:
        alarm_code = 304
    else:
        alarm_code = 0

    if not interlock_ok:
        casting_speed = 0.0
        casting_active = False

    return {
        "CCM.CastingSpeed": float(max(0.0, casting_speed)),
        "CCM.TundishTemperature": float(tundish_temp),
        "CCM.MoldLevelPercent": float(mold_level),
        "CCM.TundishWeightTon": float(max(0.0, tundish_weight)),
        "CCM.MoldCoolingWaterFlowM3h": float(mold_water_flow),
        "CCM.MoldCoolingWaterDeltaC": float(water_delta),
        "CCM.SecondaryCoolingFlowM3h": float(secondary_flow),
        "CCM.OscillationFrequencyCpm": float(max(0.0, oscillation)),
        "CCM.StopperPositionPercent": float(max(0.0, min(100.0, stopper))),
        "CCM.StageCode": int(stage_code),
        "CCM.StageName": stage_name,
        "CCM.HeatNumber": int(heat_number),
        "CCM.Ready": bool(interlock_ok and stage_name in {"PREPARE", "IDLE"}),
        "CCM.Running": bool(casting_active),
        "CCM.Fault": bool(fault),
        "CCM.AlarmCode": int(alarm_code),
        "CCM.CastingActive": bool(casting_active),
        "CCM.CoolingWaterOK": bool(cooling_ok),
        "CCM.MoldLevelControlOK": bool(level_control_ok),
        "CCM.EmergencyStopOK": bool(emergency_stop_ok),
        "CCM.InterlockOK": bool(interlock_ok),
    }


async def main() -> None:
    logging.getLogger("plc-simulator").info("CCM fault mode: %s", FAULT_MODE)
    await run_plc_simulator(
        controller_name="CCM PLC",
        controller_prefix="CCM",
        endpoint=ENDPOINT,
        namespace_uri=NAMESPACE_URI,
        object_node_id="CCM.Process",
        initial_values=INITIAL_VALUES,
        value_factory=values,
    )


if __name__ == "__main__":
    asyncio.run(main())
