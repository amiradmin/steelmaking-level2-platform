from __future__ import annotations

import asyncio
import logging
import math

from common import run_plc_simulator


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

ENDPOINT = "opc.tcp://0.0.0.0:4840/lf/"
NAMESPACE_URI = "urn:steelmaking:plc:lf"
CYCLE_SECONDS = 180.0

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
    "LF.HeatNumber": 1000,
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
    cycle = elapsed % CYCLE_SECONDS
    heat_number = 1000 + int(elapsed // CYCLE_SECONDS)

    if cycle < 15.0:
        stage_code, stage_name = 1, "LADLE_RECEIVED"
        temp = 1565.0
        power, current, argon = 0.0, 0.0, 35.0
        arc_on, argon_on = False, True
        electrode = 90.0
    elif cycle < 90.0:
        p = (cycle - 15.0) / 75.0
        stage_code, stage_name = 2, "HEATING"
        temp = lerp(1565.0, 1602.0, p)
        power = 20.0 + 2.5 * math.sin(elapsed / 5.0)
        current = 24.0 + 1.8 * math.sin(elapsed / 4.0)
        argon = 75.0 + 10.0 * math.sin(elapsed / 8.0)
        arc_on, argon_on = True, True
        electrode = 52.0 + 5.0 * math.sin(elapsed / 5.5)
    elif cycle < 140.0:
        p = (cycle - 90.0) / 50.0
        stage_code, stage_name = 3, "STIRRING"
        temp = lerp(1602.0, 1596.0, p)
        power, current = 0.0, 0.0
        argon = 145.0 + 18.0 * math.sin(elapsed / 6.0)
        arc_on, argon_on = False, True
        electrode = 90.0
    elif cycle < 165.0:
        stage_code, stage_name = 4, "SAMPLE"
        temp = 1595.0 + 1.5 * math.sin(elapsed / 7.0)
        power, current = 0.0, 0.0
        argon = 45.0
        arc_on, argon_on = False, True
        electrode = 90.0
    else:
        stage_code, stage_name = 5, "COMPLETE"
        temp = 1594.0
        power, current, argon = 0.0, 0.0, 0.0
        arc_on, argon_on = False, False
        electrode = 95.0

    cooling_flow = 415.0 + 12.0 * math.sin(elapsed / 13.0)
    ladle_weight = 145.0 - 1.5 * max(0.0, min(1.0, cycle / CYCLE_SECONDS))
    cooling_ok = cooling_flow > 360.0
    argon_pressure_ok = True
    transformer_ready = True
    roof_closed = stage_name not in {"LADLE_RECEIVED", "COMPLETE"}
    interlock_ok = cooling_ok and argon_pressure_ok and transformer_ready and (roof_closed or not arc_on)
    fault = not interlock_ok
    alarm_code = 201 if not cooling_ok else 202 if not argon_pressure_ok else 203 if not transformer_ready else 0

    return {
        "LF.SteelTemperature": float(temp),
        "LF.ArgonFlow": float(max(0.0, argon)),
        "LF.PowerMW": float(max(0.0, power)),
        "LF.CurrentKA": float(max(0.0, current)),
        "LF.ElectrodePositionPercent": float(electrode),
        "LF.CoolingWaterFlowM3h": float(cooling_flow),
        "LF.LadleWeightTon": float(ladle_weight),
        "LF.StageCode": int(stage_code),
        "LF.StageName": stage_name,
        "LF.HeatNumber": int(heat_number),
        "LF.Ready": bool(interlock_ok and stage_name in {"LADLE_RECEIVED", "COMPLETE"}),
        "LF.Running": bool(stage_name not in {"COMPLETE"}),
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
