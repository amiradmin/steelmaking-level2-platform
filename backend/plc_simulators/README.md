# PLC Process Simulators

This directory contains three isolated process simulators representing the three production PLC domains used by the Steelmaking Level 2 platform:

- EAF PLC — Siemens S7-400 role
- LF PLC — Siemens S7-400 role
- CCM PLC — Siemens S7-400 role

Each simulator runs in its own Docker container.

The simulators now model more than simple changing values. They include:

- cyclic PLC-style scan execution
- CPU RUN / STOP state
- scan counter and cycle-time diagnostics
- watchdog, heartbeat and communication status
- stage-dependent process values
- equipment permissives and interlocks
- alarm codes and fault states
- heat numbers and process stages
- classic S7-style Data Block memory
- an S7 protocol endpoint on TCP/102 inside each container
- an OPC UA endpoint retained for diagnostics and development

> These are integration-grade S7-400-style simulators, not bit-exact Siemens firmware or STEP 7 emulators. The DB addresses are project-defined simulation addresses and must be replaced with the real plant PLC DB map when that information is available.

## Interfaces

| Simulator | OPC UA host endpoint | S7 host port | Container S7 port |
| --- | --- | --- | --- |
| EAF | `opc.tcp://localhost:4842/eaf/` | `1102` | `102` |
| LF | `opc.tcp://localhost:4843/lf/` | `1103` | `102` |
| CCM | `opc.tcp://localhost:4844/ccm/` | `1104` | `102` |

The intended production-style test path is:

```text
EAF/LF/CCM S7 simulator
        -> Central OPC UA Server / Gateway
        -> PLC Ingestor
        -> Historian
        -> Level 2 API
        -> Dashboard
```

## Process model

### EAF

The EAF simulator cycles through:

`CHARGE -> MELTING -> REFINING -> SUPERHEAT -> TAPPING -> IDLE`

Representative signals include power, current, oxygen flow, steel temperature, electrode position, transformer tap, cooling water, arc state, roof/door state, interlocks and alarms.

### LF

The LF simulator cycles through:

`LADLE_RECEIVED -> HEATING -> STIRRING -> SAMPLE -> COMPLETE`

Representative signals include steel temperature, argon flow, power/current, electrode position, ladle weight, cooling water, roof state, transformer status, argon pressure, interlocks and alarms.

### CCM

The CCM simulator cycles through:

`PREPARE -> START_CAST -> STEADY_CAST -> END_CAST -> IDLE`

Representative signals include casting speed, tundish temperature/weight, mold level, stopper position, oscillation frequency, mold cooling water and secondary cooling flow, interlocks and alarms.

## S7-style DB map

See:

```text
s7_address_map.json
```

The simulation map currently uses:

- EAF process DB: `DB100`
- EAF diagnostics DB: `DB110`
- LF process DB: `DB200`
- LF diagnostics DB: `DB210`
- CCM process DB: `DB300`
- CCM diagnostics DB: `DB310`

## Fault injection

Fault modes are configured per container and applied after restart.

EAF examples:

- `COOLING_WATER_LOW`
- `HYDRAULIC_FAIL`
- `TRANSFORMER_TRIP`
- `ROOF_INTERLOCK`

LF examples:

- `COOLING_WATER_LOW`
- `ARGON_PRESSURE_LOW`
- `TRANSFORMER_TRIP`
- `ROOF_INTERLOCK`

CCM examples:

- `COOLING_WATER_LOW`
- `MOLD_LEVEL_HIGH`
- `MOLD_LEVEL_LOW`
- `EMERGENCY_STOP`
- `TUNDISH_TEMP_HIGH`

CPU mode may be set to `RUN` or `STOP`.

## Run

Build the shared simulator image:

```bash
docker compose --profile plc-multi-test build \
  --build-arg PIP_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple \
  eaf-plc-simulator
```

Start all three simulators:

```bash
docker compose --profile plc-multi-test up -d --force-recreate \
  eaf-plc-simulator lf-plc-simulator ccm-plc-simulator
```

Inspect them:

```bash
docker compose --profile plc-multi-test ps
```

The next phase is the central OPC UA aggregation server/gateway, which will read these PLC-like S7 endpoints and present one unified OPC UA namespace to Level 2.
