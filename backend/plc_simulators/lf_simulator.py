from __future__ import annotations

import asyncio
import logging
import math
import os

from common import run_plc_simulator
from production_timeline import schedule, stage, timeline_state


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ENDPOINT = "opc.tcp://0.0.0.0:4840/lf/"
NAMESPACE_URI = "urn:steelmaking:plc:lf"
FAULT_MODE = os.getenv("PLC_SIM_FAULT_MODE", "NONE").strip().upper()

SCHEDULE = schedule(
    "LF",
    71.0,
    (
        stage("LF", 1, "LADLE_RECEIVED", 3.0),
        stage("LF", 2, "HEATING", 17.0),
        stage("LF", 3, "ALLOYING", 6.0),
        stage("LF", 4, "STIRRING", 6.0),
        stage("LF", 5, "SAMPLE", 4.0),
        stage("LF", 6, "READY_TO_CAST", 2.0),
    ),
)

INITIAL_VALUES = {
    "LF.SteelTemperature": 1565.0,
    "LF.ArgonFlow": 0.0,
    "LF.PowerMW": 0.0,
    "LF.CurrentKA": 0.0,
    "LF.ElectrodePositionPercent": 90.0,
    "LF.CoolingWaterFlowM3h": 410.0,
    "LF.LadleWeightTon": 145.0,
    "LF.StageCode": 0,
    "LF.StageName": "IDLE",
    "LF.HeatNumber": 260001,
    "LF.Ready": True,
    "LF.Running": False,
    "LF.Fault": False,
    "LF.AlarmCode": 0,
    "LF.ArcOn": False,
    "LF.ArgonOn": False,
    "LF.RoofClosed": True,
    "LF.CoolingWaterOK": True,
    "LF.ArgonPressureOK": True,
    "LF.TransformerReady": True,
    "LF.InterlockOK": True,
}


def lerp(start: float, end: float, ratio: float) -> float:
    return start + (end - start) * max(0.0, min(1.0, ratio))


def values(elapsed: float, scan_counter: int) -> dict[str, object]:
    del scan_counter
    state = timeline_state(SCHEDULE)
    stage_name = state.stage_name
    p = state.stage_progress

    if stage_name == "LADLE_RECEIVED":
        temp = 1565.0
        power, current, argon = 0.0, 0.0, 35.0
        arc_on, argon_on = False, True
        electrode = 90.0
    elif stage_name == "HEATING":
        temp = lerp(1565.0, 1602.0, p)
        power = 20.0 + 2.5 * math.sin(elapsed / 5.0)
        current = 24.0 + 1.8 * math.sin(elapsed / 4.0)
        argon = 75.0 + 10.0 * math.sin(elapsed / 8.0)
        arc_on, argon_on = True, True
        electrode = 52.0 + 5.0 * math.sin(elapsed / 5.5)
    elif stage_name == "ALLOYING":
        temp = lerp(1602.0, 1599.0, p)
        power, current = 0.0, 0.0
        argon = 95.0 + 8.0 * math.sin(elapsed / 7.0)
        arc_on, argon_on = False, True
        electrode = 90.0
    elif stage_name == "STIRRING":
        temp = lerp(1599.0, 1596.0, p)
        power, current = 0.0, 0.0
        argon = 145.0 + 18.0 * math.sin(elapsed / 6.0)
        arc_on, argon_on = False, True
        electrode = 90.0
    elif stage_name == "SAMPLE":
        temp = 1595.0 + 1.5 * math.sin(elapsed / 7.0)
        power, current = 0.0, 0.0
        argon = 45.0
        arc_on, argon_on = False, True
        electrode = 90.0
    elif stage_name == "READY_TO_CAST":
        temp = 1594.0
        power, current, argon = 0.0, 0.0, 0.0
        arc_on, argon_on = False, False
        electrode = 95.0
    else:
        temp = 1565.0
        power, current, argon = 0.0, 0.0, 0.0
        arc_on, argon_on = False, False
        electrode = 95.0

    cooling_flow = 415.0 + 12.0 * math.sin(elapsed / 13.0)
    area_progress = min(1.0, state.area_elapsed_seconds / max(SCHEDULE.active_seconds, 1.0))
    ladle_weight = 145.0 - 1.5 * area_progress
    argon_pressure_ok = True
    transformer_ready = True

    if FAULT_MODE == "COOLING_WATER_LOW":
        cooling_flow = 320.0
    elif FAULT_MODE == "ARGON_PRESSURE_LOW":
        argon_pressure_ok = False
        argon = min(argon, 10.0)
    elif FAULT_MODE == "TRANSFORMER_TRIP":
        transformer_ready = False

    cooling_ok = cooling_flow > 360.0
    roof_closed = stage_name not in {"LADLE_RECEIVED", "READY_TO_CAST", "IDLE"}
    if FAULT_MODE == "ROOF_INTERLOCK":
        roof_closed = False

    interlock_ok = cooling_ok and argon_pressure_ok and transformer_ready and (roof_closed or not arc_on)
    fault = not interlock_ok

    if not cooling_ok:
        alarm_code = 201
    elif not argon_pressure_ok:
        alarm_code = 202
    elif not transformer_ready:
        alarm_code = 203
    elif arc_on and not roof_closed:
        alarm_code = 204
    else:
        alarm_code = 0

    if not interlock_ok:
        arc_on = False
        power = 0.0
        current = 0.0

    return {
        "LF.SteelTemperature": float(temp),
        "LF.ArgonFlow": float(max(0.0, argon)),
        "LF.PowerMW": float(max(0.0, power)),
        "LF.CurrentKA": float(max(0.0, current)),
        "LF.ElectrodePositionPercent": float(electrode),
        "LF.CoolingWaterFlowM3h": float(cooling_flow),
        "LF.LadleWeightTon": float(ladle_weight),
        "LF.StageCode": int(state.stage_code),
        "LF.StageName": stage_name,
        "LF.HeatNumber": int(state.heat_number),
        "LF.Ready": bool(interlock_ok and (not state.active or stage_name == "READY_TO_CAST")),
        "LF.Running": bool(state.active),
        "LF.Fault": bool(fault),
        "LF.AlarmCode": int(alarm_code),
        "LF.ArcOn": bool(arc_on),
        "LF.ArgonOn": bool(argon_on),
        "LF.RoofClosed": bool(roof_closed),
        "LF.CoolingWaterOK": bool(cooling_ok),
        "LF.ArgonPressureOK": bool(argon_pressure_ok),
        "LF.TransformerReady": bool(transformer_ready),
        "LF.InterlockOK": bool(interlock_ok),
    }


async def main() -> None:
    logging.getLogger("plc-simulator").info("LF fault mode: %s", FAULT_MODE)
    await run_plc_simulator(
        controller_name="LF PLC",
        controller_prefix="LF",
        endpoint=ENDPOINT,
        namespace_uri=NAMESPACE_URI,
        object_node_id="LF.Process",
        initial_values=INITIAL_VALUES,
        value_factory=values,
    )


if __name__ == "__main__":
    asyncio.run(main())
