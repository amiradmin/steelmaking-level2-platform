#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="normal"
BUILD=0

for arg in "$@"; do
  case "$arg" in
    normal|multi-sim|real-eaf) MODE="$arg" ;;
    --build) BUILD=1 ;;
    -h|--help)
      echo "Usage: $0 [normal|multi-sim|real-eaf] [--build]"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $arg" >&2
      echo "Usage: $0 [normal|multi-sim|real-eaf] [--build]" >&2
      exit 2
      ;;
  esac
done

command -v docker >/dev/null 2>&1 || { echo "ERROR: docker is not installed or not in PATH." >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERROR: Docker Compose v2 is required." >&2; exit 1; }

if [[ ! -f .env ]]; then
  [[ -f .env.example ]] || { echo "ERROR: .env and .env.example are missing." >&2; exit 1; }
  cp .env.example .env
  echo "Created .env from .env.example"
fi

# Load .env into this shell as well as Docker Compose so validation and printed
# ports use the same configuration. The project .env contains shell-safe values.
set -a
# shellcheck disable=SC1091
source .env
set +a

case "$MODE" in
  normal)
    COMPOSE=(docker compose --profile plc-test)
    ;;
  multi-sim)
    COMPOSE=(docker compose --profile plc-multi-test)
    ;;
  real-eaf)
    [[ -n "${EAF_PLC_HOST:-}" ]] || { echo "ERROR: set EAF_PLC_HOST in .env before real-eaf startup." >&2; exit 1; }
    [[ -n "${S7_ADDRESS_MAP_FILE:-}" ]] || { echo "ERROR: set S7_ADDRESS_MAP_FILE in .env to a reviewed real PLC DB map." >&2; exit 1; }
    [[ -f "$S7_ADDRESS_MAP_FILE" ]] || { echo "ERROR: S7_ADDRESS_MAP_FILE does not exist: $S7_ADDRESS_MAP_FILE" >&2; exit 1; }
    case "$(realpath "$S7_ADDRESS_MAP_FILE")" in
      "$(realpath backend/plc_simulators/s7_address_map.json)")
        echo "ERROR: refusing real-eaf startup with the simulation-only S7 address map." >&2
        exit 1
        ;;
    esac
    COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.real-eaf.yml --profile plc-multi-test)
    ;;
esac

UP_ARGS=(up -d)
if (( BUILD )); then
  UP_ARGS+=(--build)
else
  UP_ARGS+=(--no-build)
fi

echo "Starting Steelmaking Level 2 Platform (mode: $MODE, build: $BUILD)..."
if ! "${COMPOSE[@]}" "${UP_ARGS[@]}"; then
  if (( ! BUILD )); then
    echo
    echo "Startup failed without a build. If an image is missing or code changed, run:"
    echo "  $0 $MODE --build"
  fi
  exit 1
fi

echo
"${COMPOSE[@]}" ps

echo
echo "Dashboard:       http://localhost:${NGINX_PORT:-80}"
echo "Level 2 API:     http://localhost:${LEVEL2_API_PORT:-8080}"
echo "Heat Management: http://localhost:${HEAT_MANAGEMENT_PORT:-9000}"
