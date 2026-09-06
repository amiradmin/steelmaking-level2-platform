# Level 1 Simulator

## Purpose

The Level 1 Simulator provides a reproducible local source of steelmaking process data before access to the plant PLC/DCS network is available.

It is intended for development, integration testing, FAT preparation, historian validation, UI development, and demonstration of the Level 2 platform.

## Simulated Process Route

The current simulator runs a simplified heat lifecycle:

```text
EAF -> LF -> CCM -> Completed
```

After one heat completes, a new simulated heat is created automatically and the cycle continues.

## Simulated Equipment

- `EAF-01` - Electric Arc Furnace
- `LF-01` - Ladle Furnace
- `CCM-01` - Continuous Casting Machine

## Simulated Tags

### EAF

- `EAF.PowerMW`
- `EAF.CurrentKA`
- `EAF.OxygenFlow`
- `EAF.SteelTemperature`

### LF

- `LF.SteelTemperature`
- `LF.ArgonFlow`

### CCM

- `CCM.CastingSpeed`
- `CCM.TundishTemperature`

Values are intentionally bounded within plausible demo ranges and are not process-model predictions or guaranteed plant operating limits.

## Events

The simulator records lifecycle events in `heat_events`, including:

- `EAF_START`
- `EAF_COMPLETE`
- `LF_START`
- `LF_COMPLETE`
- `CAST_START`
- `CAST_COMPLETE`

It also records stage history in `heat_stages`.

## Runtime Configuration

The following values can be configured in `.env`:

```env
SIM_SAMPLE_INTERVAL_SECONDS=1
SIM_PHASE_DURATION_SECONDS=60
SIM_RESTART_DELAY_SECONDS=5
SIM_LOG_LEVEL=INFO
```

With the default values, each EAF/LF/CCM phase lasts approximately 60 seconds and active process tags are sampled once per second.

## Startup

```bash
cp .env.example .env
docker compose up -d --build
```

Check services:

```bash
docker compose ps
```

Follow simulator output:

```bash
docker compose logs -f level1-simulator
```

## Verification

After the simulator has been running for several seconds:

```bash
docker compose exec -T historian-db \
  psql -U level2 -d steelmaking_level2 \
  < infrastructure/database/simulator_smoke_test.sql
```

Expected result:

```text
level1-simulator-smoke-test | PASS
```

The second query prints the latest EAF/LF/CCM values stored in the historian.

## Scope Boundary

This simulator does not replace the actual Level 1 interface. The following are still client/site dependencies:

- actual PLC/DCS tag list
- PLC addresses / OPC UA NodeIds
- data types and scaling
- event handshakes
- timestamps and sequence rules
- network/firewall configuration
- write-back/setpoint approval rules
- final safety and interlock ownership

The simulator must therefore be treated as an engineering and FAT tool, not as a representation of final plant control logic.
