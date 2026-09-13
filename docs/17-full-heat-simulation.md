# Full Heat Simulation

This document is the quick operational guide for running one complete simulated steel heat from **CHARGE** in the EAF through **END CAST** in the CCM.

The feature lives on the branch:

```bash
feature/plc-simulators
```

## Quick start

From the project directory:

```bash
cd ~/Documents/Presentation/steelmaking-level2-platform
git switch feature/plc-simulators
git pull origin feature/plc-simulators
make full-heat
```

That is the normal command to use for day-to-day testing.

`make full-heat` does the following automatically:

- resets the simulation clock so the heat always starts from `CHARGE`
- starts the EAF, LF, and CCM PLC simulators together
- keeps the same Heat Number synchronized through the complete process
- runs only one complete heat instead of continuously creating new heats
- preserves the existing historian database and Docker volume
- prints the current area, process stage, Heat Number, and progress in the terminal
- completes after the heat reaches `END_CAST`

## Process sequence

The simulated production route is:

```text
CHARGE
  ↓
MELTING
  ↓
REFINING
  ↓
SUPERHEAT
  ↓
TAPPING
  ↓
EAF → LF transfer
  ↓
LADLE_RECEIVED
  ↓
HEATING
  ↓
ALLOYING
  ↓
STIRRING
  ↓
SAMPLE
  ↓
READY_TO_CAST
  ↓
LF → CCM transfer
  ↓
PREPARE
  ↓
START_CAST
  ↓
STEADY_CAST
  ↓
END_CAST
```

The modeled process time for one complete heat is approximately **170 minutes** at real process speed.

## Simulation speed presets

### Recommended demo mode

```bash
make full-heat
```

Default speed: approximately `120x`.

A full 170-minute process therefore completes in about **85 seconds** of wall-clock time.

### Slower demo mode

```bash
make full-heat-60
```

Speed: `60x`.

A complete heat takes about **2 minutes 50 seconds**.

### Real-time mode

```bash
make full-heat-real
```

Speed: `1x`.

The complete simulation takes approximately **170 minutes**.

### Detached mode

```bash
make full-heat-detached
```

Use this when the simulation should start but the terminal should not remain attached to the progress monitor.

## Start a specific Heat Number

To specify the Heat Number manually, run the script directly:

```bash
./scripts/full_heat_demo.sh --speed 120 --heat 260010
```

Example with `60x` speed:

```bash
./scripts/full_heat_demo.sh --speed 60 --heat 260010
```

## Expected terminal output

Typical output will look similar to:

```text
EAF  | CHARGE
Heat 260001 |   2%

EAF  | MELTING
Heat 260001 |  18%

EAF  | REFINING
...

MOVE | EAF -> LF

LF   | HEATING
...

MOVE | LF -> CCM

CCM  | STEADY CAST
...

CCM  | END_CAST
Heat 260001 | 100%

PASS: Heat 260001 completed END CAST.
```

## Production Flow dashboard

While `make full-heat` is running, keep the **Production Flow** page open in the Level 2 frontend.

The dashboard should follow the same Heat through:

```text
EAF → LF → CCM
```

The displayed stage is driven by PLC simulator telemetry (`StageCode` and `HeatNumber`) that is ingested into the historian. The frontend is therefore showing the PLC-driven simulation state rather than running its own independent timer.

## Useful configuration

The main simulation environment variables are:

```bash
PLC_SIM_TIME_SCALE
PLC_SIM_EPOCH_UNIX
PLC_SIM_HEAT_BASE
PLC_SIM_HEAT_PITCH_MINUTES
```

For normal testing, do not set the epoch manually. `full_heat_demo.sh` resets it automatically so the new heat starts from `CHARGE` every time.

## If something looks wrong

First update the branch and rebuild by simply running:

```bash
git pull origin feature/plc-simulators
make full-heat
```

Check the simulator containers with:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

The important simulator containers are:

```text
steelmaking-level2-eaf-plc-simulator
steelmaking-level2-lf-plc-simulator
steelmaking-level2-ccm-plc-simulator
steelmaking-level2-central-opcua
steelmaking-level2-plc-ingestor-central-test
```

To inspect the latest OPC UA values stored in the historian:

```bash
docker compose exec historian-db psql -U level2 -d steelmaking_level2 -c "
SELECT DISTINCT ON (pt.tag_name)
  pt.tag_name,
  COALESCE(ps.value_double::text, ps.value_text) AS value,
  ps.quality,
  ps.ts,
  ps.attributes->>'source' AS source
FROM process_samples ps
JOIN process_tags pt ON pt.id = ps.tag_id
WHERE ps.attributes->>'source' = 'OPCUA'
ORDER BY pt.tag_name, ps.ts DESC;
"
```

## Daily-use command

For normal development and UI testing, remember just this:

```bash
make full-heat
```

It is the preferred one-command path for simulating one complete steel heat from **Charge to End Cast**.
