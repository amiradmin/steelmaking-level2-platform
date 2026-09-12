# PLC Process Simulators

This directory contains three isolated process simulators representing the three production PLC domains used by the Steelmaking Level 2 platform:

- EAF PLC — Siemens S7-400 role
- LF PLC — Siemens S7-400 role
- CCM PLC — Siemens S7-400 role

Each simulator runs in its own Docker container and currently exposes an independent OPC UA endpoint for integration development.

> Important: these services simulate the process/tag behavior of S7-400-controlled equipment. They are not yet binary S7 protocol emulators. The next architecture phase will add a central OPC UA server/gateway in front of the three simulator domains so Level 2 has one production-style OPC endpoint.

## Endpoints

| Simulator | Host endpoint | Container endpoint |
| --- | --- | --- |
| EAF | `opc.tcp://localhost:4842/eaf/` | `opc.tcp://eaf-plc-simulator:4840/eaf/` |
| LF | `opc.tcp://localhost:4843/lf/` | `opc.tcp://lf-plc-simulator:4840/lf/` |
| CCM | `opc.tcp://localhost:4844/ccm/` | `opc.tcp://ccm-plc-simulator:4840/ccm/` |

## Tag domains

### EAF

- `EAF.PowerMW`
- `EAF.CurrentKA`
- `EAF.OxygenFlow`
- `EAF.SteelTemperature`
- `EAF.StageCode`
- `EAF.Ready`
- `EAF.Running`
- `EAF.Fault`

### LF

- `LF.SteelTemperature`
- `LF.ArgonFlow`
- `LF.StageCode`
- `LF.Ready`
- `LF.Running`
- `LF.Fault`

### CCM

- `CCM.CastingSpeed`
- `CCM.TundishTemperature`
- `CCM.MoldLevelPercent`
- `CCM.StageCode`
- `CCM.Ready`
- `CCM.Running`
- `CCM.Fault`

## Run

Build the shared simulator image:

```bash
docker compose --profile plc-multi-test build \
  --build-arg PIP_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple \
  eaf-plc-simulator
```

Start all three simulators:

```bash
docker compose --profile plc-multi-test up -d \
  eaf-plc-simulator lf-plc-simulator ccm-plc-simulator
```

Inspect them:

```bash
docker compose --profile plc-multi-test ps
```

The next phase is the central OPC UA aggregation server.
