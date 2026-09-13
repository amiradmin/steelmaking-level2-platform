from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterable


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class StageDefinition:
    code: int
    name: str
    duration_seconds: float


@dataclass(frozen=True)
class AreaSchedule:
    area: str
    offset_seconds: float
    stages: tuple[StageDefinition, ...]

    @property
    def active_seconds(self) -> float:
        return sum(stage.duration_seconds for stage in self.stages)


@dataclass(frozen=True)
class TimelineState:
    heat_number: int
    stage_code: int
    stage_name: str
    stage_elapsed_seconds: float
    stage_duration_seconds: float
    stage_progress: float
    area_elapsed_seconds: float
    active: bool


SIMULATION_EPOCH_UNIX = _env_float("PLC_SIM_EPOCH_UNIX", 1788220800.0)
SIMULATION_SPEED = max(0.1, _env_float("PLC_SIM_TIME_SCALE", 60.0))
HEAT_PITCH_SECONDS = max(60.0, _env_float("PLC_SIM_HEAT_PITCH_MINUTES", 70.0) * 60.0)
HEAT_BASE = _env_int("PLC_SIM_HEAT_BASE", 260001)
SINGLE_HEAT_MODE = _env_bool("PLC_SIM_SINGLE_HEAT", False)


def stage(area: str, code: int, name: str, default_minutes: float) -> StageDefinition:
    del area
    minutes = max(0.1, default_minutes)
    return StageDefinition(code=code, name=name, duration_seconds=minutes * 60.0)


def schedule(area: str, offset_minutes: float, stages: Iterable[StageDefinition]) -> AreaSchedule:
    result = AreaSchedule(area=area, offset_seconds=offset_minutes * 60.0, stages=tuple(stages))
    if result.active_seconds > HEAT_PITCH_SECONDS:
        raise ValueError(
            f"{area} active duration ({result.active_seconds:.0f}s) exceeds heat pitch "
            f"({HEAT_PITCH_SECONDS:.0f}s)"
        )
    return result


def simulated_elapsed_seconds(now_unix: float | None = None) -> float:
    now = time.time() if now_unix is None else now_unix
    return max(0.0, now - SIMULATION_EPOCH_UNIX) * SIMULATION_SPEED


def _idle_state() -> TimelineState:
    return TimelineState(
        heat_number=HEAT_BASE,
        stage_code=0,
        stage_name="IDLE",
        stage_elapsed_seconds=0.0,
        stage_duration_seconds=0.0,
        stage_progress=0.0,
        area_elapsed_seconds=0.0,
        active=False,
    )


def timeline_state(area_schedule: AreaSchedule, *, now_unix: float | None = None) -> TimelineState:
    now = time.time() if now_unix is None else now_unix

    # Keep every PLC explicitly idle until the synchronized epoch arrives.
    # This allows the OPC UA gateway, ingestor, and historian to become healthy
    # before CHARGE starts, so high-speed demos do not skip early stages.
    if now < SIMULATION_EPOCH_UNIX:
        return _idle_state()

    simulated = simulated_elapsed_seconds(now)
    relative = simulated - area_schedule.offset_seconds

    if relative < 0:
        return _idle_state()

    if SINGLE_HEAT_MODE:
        # A full-heat demo must never roll over to the next heat. Each PLC waits
        # in IDLE after its part of the selected heat has completed.
        heat_index = 0
        local = relative
    else:
        heat_index = int(relative // HEAT_PITCH_SECONDS)
        local = relative - heat_index * HEAT_PITCH_SECONDS

    heat_number = HEAT_BASE + heat_index

    cursor = 0.0
    for definition in area_schedule.stages:
        stage_end = cursor + definition.duration_seconds
        if local < stage_end:
            elapsed = max(0.0, local - cursor)
            duration = definition.duration_seconds
            return TimelineState(
                heat_number=heat_number,
                stage_code=definition.code,
                stage_name=definition.name,
                stage_elapsed_seconds=elapsed,
                stage_duration_seconds=duration,
                stage_progress=min(1.0, elapsed / duration),
                area_elapsed_seconds=local,
                active=True,
            )
        cursor = stage_end

    return TimelineState(
        heat_number=heat_number,
        stage_code=0,
        stage_name="IDLE",
        stage_elapsed_seconds=max(0.0, local - cursor),
        stage_duration_seconds=(
            0.0 if SINGLE_HEAT_MODE else max(0.0, HEAT_PITCH_SECONDS - cursor)
        ),
        stage_progress=0.0,
        area_elapsed_seconds=local,
        active=False,
    )
