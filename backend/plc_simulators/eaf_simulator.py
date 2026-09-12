from __future__ import annotations

import asyncio
import logging
import math
import os

from common import run_plc_simulator


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ENDPOINT = "opc.tcp://0.0.0.0:4840/eaf/"
NAMESPACE_URI = "urn:steelmaking:plc:eaf"
CYCLE_SECONDS = 240.0
FAULT_MODE = os.getenv("PLC_SIM_FAULT_MODE", "NONE").strip().upper()

INITIAL_VALUES = {
    "EAF.PowerMW": 0.0,
    "EAF.CurrentKA": 0.0,
    "EAF.OxygenFlow": 0.0,
    "EAF.SteelTemperature": 1450.0,
    "EAF.ElectrodePositionPercent": 65.0,
    "EAF.CoolingWaterFlowM3h": 780.0,
    "EAF.TransformerTap": 0,
    "EAF.StageCode": 0,
    "EAF.StageName": "IDLE",
    "EAF.HeatNumber": 1000,
    "EAF.Ready": True,
    "EAF.Running": False,
    "EAF.Fault": False,
    "EAF.AlarmCode": 0,
    "EAF.ArcOn": False,
    "EAF.OxygenOn": False,
    "EAF.BurnerOn": False,
    "EAF.RoofClosed": True,
    "EAF.DoorClosed": True,
    "EAF.HydraulicOK": True,
    "EAF.CoolingWaterOK": True,
    "EAF.TransformerReady": True,
    "EAF.InterlockOK": True,
}


def lerp(start: float, end: float, ratio: float) -> float:
    return start + (end - start) * max(0.0, min(1.0, ratio))


def values(elapsed: float, scan_counter: int) -> dict[str, object]:
    cycle = elapsed % CYCLE_SECONDS
    heat_number = 1000 + int(elapsed // CYCLE_SECONDS)

    if cycle < 15.0:
        stage_code, stage_name = 1, "CHARGE"
        power, current, oxygen = 0.0, 0.0, 0.0
        temp = 1450.0
        arc_on, oxygen_on, burner_on = False, False, False
        roof_closed = False
        transformer_tap = 0
        electrode = 90.0
    elif cycle < 100.0:
        p = (cycle - 15.0) / 85.0
        stage_code, stage_name = 2, "MELTING"
        power = 63.0 + 5.0 * math.sin(elapsed / 4.0)
        current = 46.0 + 3.0 * math.sin(elapsed / 3.2)
        oxygen = 1200.0 + 350.0 * math.sin(elapsed / 8.0)
        temp = lerp(1450.0, 1555.0, p)
        arc_on, oxygen_on, burner_on = True, True, True
        roof_closed = True
        transformer_tap = 14
        electrode = 48.0 + 6.0 * math.sin(elapsed / 5.0)
    elif cycle < 170.0:
        p = (cycle - 100.0) / 70.0
        stage_code, stage_name = 3, "REFINING"
        power = 48.0 + 4.0 * math.sin(elapsed / 5.0)
        current = 38.0 + 2.0 * math.sin(elapsed / 4.0)
        oxygen = 3300.0 + 300.0 * math.sin(elapsed / 7.0)
        temp = lerp(1555.0, 1610.0, p)
        arc_on, oxygen_on, burner_on = True, True, False
        roof_closed = True
        transformer_tap = 10
        electrode = 54.0 + 4.0 * math.sin(elapsed / 6.0)
    elif cycle < 210.0:
        p = (cycle - 170.0) / 40.0
        stage_code, stage_name = 4, "SUPERHEAT"
        power = 39.0 + 3.0 * math.sin(elapsed / 4.5)
        current = 32.0 + 2.0 * math.sin(elapsed / 3.8)
        oxygen = 450.0
        temp = lerp(1610.0, 1640.0, p)
        arc_on, oxygen_on, burner_on = True, False, False
        roof_closed = True
        transformer_tap = 8
        electrode = 58.0
    elif cycle < 235.0:
        stage_code, stage_name = 5, "TAPPING"
        power, current, oxygen = 0.0, 0.0, 0.0
        temp = 1636.0 - 2.0 * math.sin(elapsed / 5.0)
        arc_on, oxygen_on, burner_on = False, False, False
        roof_closed = False
        transformer_tap = 0
        electrode = 95.0
    else:
        stage_code, stage_name = 0, "IDLE"
        power, current, oxygen = 0.0, 0.0, 0.0
        temp = 1450.0
        arc_on, oxygen_on, burner_on = False, False, False
        roof_closed = True
        transformer_tap = 0
        electrode = 90.0

    cooling_flow = 790.0 + 18.0 * math.sin(elapsed / 11.0)
    hydraulic_ok = True
    transformer_ready = True

    if FAULT_MODE == "COOLING_WATER_LOW":
        cooling_flow = 620.0
    elif FAULT_MODE == "HYDRAULIC_FAIL":
        hydraulic_ok = False
    elif FAULT_MODE == "TRANSFORMER_TRIP":
        transformer_ready = False
    elif FAULT_MODE == "ROOF_INTERLOCK":
        roof_closed = False

    cooling_ok = cooling_flow > 700.0
    door_closed = stage_name != "TAPPING"
    interlock_ok = hydraulic_ok and cooling_ok and transformer_ready and (roof_closed or not arc_on)
    fault = not interlock_ok

    if not cooling_ok:
        alarm_code = 101
    elif not hydraulic_ok:
        alarm_code = 102
    elif not transformer_ready:
        alarm_code = 103
    elif arc_on and not roof_closed:
        alarm_code = 104
    else:
        alarm_code = 0

    if not interlock_ok:
        arc_on = False
        power = 0.0
        current = 0.0

    return {
        "EAF.PowerMW": float(max(0.0, power)),
        "EAF.CurrentKA": float(max(0.0, current)),
        "EAF.OxygenFlow": float(max(0.0, oxygen)),
        "EAF.SteelTemperature": float(temp),
        "EAF.ElectrodePositionPercent": float(electrode),
        "EAF.CoolingWaterFlowM3h": float(cooling_flow),
        "EAF.TransformerTap": int(transformer_tap),
        "EAF.StageCode": int(stage_code),
        "EAF.StageName": stage_name,
        "EAF.HeatNumber": int(heat_number),
        "EAF.Ready": bool(interlock_ok and stage_name in {"IDLE", "CHARGE"}),
        "EAF.Running": bool(stage_name != "IDLE"),
        "EAF.Fault": bool(fault),
        "EAF.AlarmCode": int(alarm_code),
        "EAF.ArcOn": bool(arc_on),
        "EAF.OxygenOn": bool(oxygen_on),
        "EAF.BurnerOn": bool(burner_on),
        "EAF.RoofClosed": bool(roof_closed),
        "EAF.DoorClosed": bool(door_closed),
        "EAF.HydraulicOK": bool(hydraulic_ok),
        "EAF.CoolingWaterOK": bool(cooling_ok),
        "EAF.TransformerReady": bool(transformer_ready),
        "EAF.InterlockOK": bool(interlock_ok),
    }


async def main() -> None:
    logging.getLogger("plc-simulator").info("EAF fault mode: %s", FAULT_MODE)
    await run_plc_simulator(
        controller_name="EAF PLC",
        controller_prefix="EAF",
        endpoint=ENDPOINT,
        namespace_uri=NAMESPACE_URI,
        object_node_id="EAF.Process",
        initial_values=INITIAL_VALUES,
        value_factory=values,
    )


if __name__ == "__main__":
    asyncio.run(main())
