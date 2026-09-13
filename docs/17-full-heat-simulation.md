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
- builds required Docker images one at a time to avoid parallel PyPI download failures
- retries an individual Docker image build up to three times
- uses a shared BuildKit pip cache for the PLC simulator, OPC UA gateway, and PLC ingestor images
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

A full 170-minute process therefore completes in about **85 seconds** of wall-clock time after the containers have started.

### Fast restart after the images are already built

After one successful build, use:

```bash
make full-heat-fast
```

This skips Docker image builds, reuses the existing images, resets the synchronized simulation epoch, recreates the PLC path, and starts a new Heat from `CHARGE`.

Use `make full-heat` again after pulling code changes that affect Docker images or Python/frontend source code.

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

To start a specific Heat using already-built Docker images:

```bash
./scripts/full_heat_demo.sh --speed 120 --heat 260010 --skip-build
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

CCM  | END CAST
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

`full_heat_demo.sh` also sets `COMPOSE_PARALLEL_LIMIT=1` by default so Docker Compose builds do not download Python dependencies concurrently.

## If something looks wrong

First update the branch and run the standard command:

```bash
git pull origin feature/plc-simulators
make full-heat
```

### PyPI / cryptography build errors

If Docker reports an error similar to:

```text
Could not find a version that satisfies the requirement cryptography>42.0.0
```

while another PLC image succeeds, this normally indicates intermittent package-index access from Docker rather than an application-code error.

The current full-heat runner mitigates this by:

- pinning `asyncua`, `cryptography`, and `python-dateutil`
- building Docker services serially
- retrying each build up to three times
- sharing a locked BuildKit pip cache across the PLC-related images

Pull the latest branch and retry:

```bash
git pull origin feature/plc-simulators
make full-heat
```

Once the images have built successfully, use this for subsequent Heat simulations:

```bash
make full-heat-fast
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

## Daily-use commands

After pulling code changes or when Docker images need rebuilding:

```bash
make full-heat
```

After the images have already been built successfully and you only want to simulate another complete Heat:

```bash
make full-heat-fast
```

These are the preferred paths for simulating one complete steel heat from **Charge to End Cast**.
