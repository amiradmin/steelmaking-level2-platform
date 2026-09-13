#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SPEED=120
HEAT_NUMBER=260001
FOLLOW=1
BUILD_IMAGES=1
START_DELAY_SECONDS=30

usage() {
  cat <<'EOF'
Usage: ./scripts/full_heat_demo.sh [options]

Run exactly one synchronized steelmaking heat from CHARGE to END_CAST.

Options:
  --speed N       Simulation speed multiplier (default: 120)
  --heat N        PLC heat number (default: 260001)
  --detach        Start the heat and return immediately
  --skip-build    Reuse existing Docker images without rebuilding
  -h, --help      Show this help

Examples:
  ./scripts/full_heat_demo.sh
  ./scripts/full_heat_demo.sh --speed 60 --heat 260010
  ./scripts/full_heat_demo.sh --speed 1 --detach
  ./scripts/full_heat_demo.sh --skip-build
EOF
}

while (($#)); do
  case "$1" in
    --speed)
      SPEED="${2:-}"
      shift 2
      ;;
    --heat)
      HEAT_NUMBER="${2:-}"
      shift 2
      ;;
    --detach)
      FOLLOW=0
      shift
      ;;
    --skip-build)
      BUILD_IMAGES=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "$SPEED" =~ ^[1-9][0-9]*$ ]]; then
  echo "--speed must be a positive integer." >&2
  exit 2
fi
if ! [[ "$HEAT_NUMBER" =~ ^[1-9][0-9]*$ ]]; then
  echo "--heat must be a positive integer." >&2
  exit 2
fi

TOTAL_SIM_SECONDS=10200
EXPECTED_WALL_SECONDS=$(( (TOTAL_SIM_SECONDS + SPEED - 1) / SPEED ))

export PLC_SIM_TIME_SCALE="$SPEED"
export PLC_SIM_HEAT_BASE="$HEAT_NUMBER"
export PLC_SIM_HEAT_PITCH_MINUTES=70

# The first PLC startup is a warm-up phase. A far-future epoch keeps every PLC
# at StageCode=0 while the gateway and ingestor establish their connections.
WARMUP_EPOCH=$(( $(date +%s) + 3600 ))
export PLC_SIM_EPOCH_UNIX="$WARMUP_EPOCH"

# Avoid simultaneous dependency downloads from multiple Compose builds.
export COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"

COMPOSE=(
  docker compose
  -f docker-compose.yml
  -f docker-compose.full-heat.yml
  --profile plc-multi-test
)

printf '\n=== Full Heat Demo ===\n'
printf 'Heat:        %s\n' "$HEAT_NUMBER"
printf 'Speed:       %sx\n' "$SPEED"
printf 'Process:     170 simulated minutes\n'
printf 'Run time:    ~%s seconds after telemetry warm-up\n' "$EXPECTED_WALL_SECONDS"
printf 'Start:       CHARGE\n'
printf 'Finish:      END_CAST\n\n'

build_service() {
  local service="$1"
  local attempt

  for attempt in 1 2 3; do
    printf 'Building %-28s attempt %d/3...\n' "$service" "$attempt"
    if "${COMPOSE[@]}" build "$service"; then
      return 0
    fi

    if (( attempt < 3 )); then
      printf 'Build failed for %s; retrying in 5 seconds...\n' "$service" >&2
      sleep 5
    fi
  done

  printf 'ERROR: Docker build failed for %s after 3 attempts.\n' "$service" >&2
  return 1
}

container_state() {
  local container="$1"
  docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || true
}

container_health() {
  local container="$1"
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
    "$container" 2>/dev/null || true
}

wait_for_plc_path() {
  local deadline=$(( SECONDS + 90 ))
  local central_health
  local ingestor_state

  printf 'Waiting for OPC UA gateway and historian ingestor to become ready...\n'
  while (( SECONDS < deadline )); do
    central_health="$(container_health steelmaking-level2-central-opcua)"
    ingestor_state="$(container_state steelmaking-level2-plc-ingestor-central-test)"

    if [[ "$central_health" == "healthy" && "$ingestor_state" == "running" ]]; then
      # The ingestor polls once per second. Give it a few cycles to publish the
      # idle StageCode=0 values into the historian before the real heat starts.
      sleep 4
      printf 'PLC telemetry path is ready.\n'
      return 0
    fi
    sleep 1
  done

  printf 'ERROR: PLC telemetry path did not become ready within 90 seconds.\n' >&2
  return 1
}

if (( BUILD_IMAGES == 1 )); then
  printf 'Building required images serially to keep dependency access stable...\n\n'

  build_service central-opcua-server
  build_service eaf-plc-simulator
  build_service plc-ingestor-central-test
  build_service heat-management
  build_service level2-api
  build_service frontend

  printf '\nAll required images are ready.\n\n'
else
  printf 'Skipping Docker image build and reusing existing images.\n\n'
fi

# Keep persistent application services and historian data intact.
"${COMPOSE[@]}" up -d --no-build \
  historian-db \
  heat-management \
  level2-api \
  frontend \
  nginx

# Nginx resolves Docker service names when its config is loaded. Restart it
# after application services are healthy so recreated upstream IPs are resolved.
"${COMPOSE[@]}" restart nginx

# Phase 1: recreate the complete PLC telemetry path with an epoch far in the
# future. The simulator code keeps all three controllers IDLE during this phase.
"${COMPOSE[@]}" up -d --no-build --force-recreate \
  eaf-plc-simulator \
  lf-plc-simulator \
  ccm-plc-simulator \
  central-opcua-server \
  plc-ingestor-central-test

wait_for_plc_path

# Phase 2: arm only the three PLC simulators with the real synchronized epoch.
# The gateway and ingestor remain running, so early EAF/LF stages cannot be lost
# during their comparatively slow startup.
SIM_EPOCH=$(( $(date +%s) + START_DELAY_SECONDS ))
export PLC_SIM_EPOCH_UNIX="$SIM_EPOCH"

"${COMPOSE[@]}" up -d --no-build --force-recreate \
  eaf-plc-simulator \
  lf-plc-simulator \
  ccm-plc-simulator

remaining=$(( SIM_EPOCH - $(date +%s) ))
if (( remaining < 5 )); then
  printf 'ERROR: PLC simulator restart consumed the start safety window. Run the demo again.\n' >&2
  exit 1
fi

printf '\nFull heat armed. Production Flow: http://localhost/\n'
printf 'Historian volume was preserved.\n'
printf 'CHARGE starts in approximately %s seconds.\n' "$remaining"

if (( FOLLOW == 0 )); then
  exit 0
fi

while (( $(date +%s) < SIM_EPOCH )); do
  remaining=$(( SIM_EPOCH - $(date +%s) ))
  printf '\rHeat %s armed | CHARGE starts in %2ds' "$HEAT_NUMBER" "$remaining"
  sleep 1
done
printf '\r%-70s\r' ' '

stage_for_seconds() {
  local s="$1"
  if (( s < 420 )); then echo "EAF  | CHARGE"
  elif (( s < 2520 )); then echo "EAF  | MELTING"
  elif (( s < 3300 )); then echo "EAF  | REFINING"
  elif (( s < 3600 )); then echo "EAF  | SUPERHEAT"
  elif (( s < 3900 )); then echo "EAF  | TAPPING"
  elif (( s < 4260 )); then echo "MOVE | EAF -> LF"
  elif (( s < 4440 )); then echo "LF   | LADLE RECEIVED"
  elif (( s < 5460 )); then echo "LF   | HEATING"
  elif (( s < 5820 )); then echo "LF   | ALLOYING"
  elif (( s < 6180 )); then echo "LF   | ARGON STIRRING"
  elif (( s < 6420 )); then echo "LF   | SAMPLING"
  elif (( s < 6540 )); then echo "LF   | READY TO CAST"
  elif (( s < 6900 )); then echo "MOVE | LF -> CCM"
  elif (( s < 7200 )); then echo "CCM  | PREPARE"
  elif (( s < 7440 )); then echo "CCM  | START CAST"
  elif (( s < 9960 )); then echo "CCM  | STEADY CAST"
  elif (( s < 10200 )); then echo "CCM  | END CAST"
  else echo "DONE | END CAST COMPLETE"
  fi
}

last_stage=""
while true; do
  now="$(date +%s)"
  wall_elapsed=$(( now - SIM_EPOCH ))
  (( wall_elapsed < 0 )) && wall_elapsed=0
  sim_elapsed=$(( wall_elapsed * SPEED ))
  (( sim_elapsed > TOTAL_SIM_SECONDS )) && sim_elapsed=$TOTAL_SIM_SECONDS

  stage="$(stage_for_seconds "$sim_elapsed")"
  progress=$(( sim_elapsed * 100 / TOTAL_SIM_SECONDS ))
  sim_minutes=$(( sim_elapsed / 60 ))
  sim_seconds=$(( sim_elapsed % 60 ))

  if [[ "$stage" != "$last_stage" ]]; then
    [[ -n "$last_stage" ]] && printf '\n'
    printf '%s\n' "$stage"
    last_stage="$stage"
  fi

  printf '\rHeat %s | %3d%% | simulated %03dm %02ds / 170m' \
    "$HEAT_NUMBER" "$progress" "$sim_minutes" "$sim_seconds"

  if (( sim_elapsed >= TOTAL_SIM_SECONDS )); then
    printf '\n\nPASS: Heat %s completed END CAST.\n' "$HEAT_NUMBER"
    printf 'Production Flow remains available at http://localhost/\n'
    break
  fi
  sleep 1
done
