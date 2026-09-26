#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-normal}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed or not in PATH." >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: Docker Compose v2 is required." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "Created .env from .env.example"
  else
    echo "ERROR: .env is missing and .env.example was not found." >&2
    exit 1
  fi
fi

case "$MODE" in
  normal)
    COMPOSE=(docker compose --profile plc-test)
    ;;
  multi-sim)
    COMPOSE=(docker compose --profile plc-multi-test)
    ;;
  real-eaf)
    : "${EAF_PLC_HOST:?Set EAF_PLC_HOST before real-eaf startup}"
    : "${S7_ADDRESS_MAP_FILE:?Set S7_ADDRESS_MAP_FILE to a reviewed real PLC DB map before real-eaf startup}"
    if [[ ! -f "$S7_ADDRESS_MAP_FILE" ]]; then
      echo "ERROR: S7_ADDRESS_MAP_FILE does not exist: $S7_ADDRESS_MAP_FILE" >&2
      exit 1
    fi
    COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.real-eaf.yml --profile plc-multi-test)
    ;;
  *)
    echo "Usage: $0 [normal|multi-sim|real-eaf]" >&2
    exit 2
    ;;
esac

echo "Starting Steelmaking Level 2 Platform (mode: $MODE)..."
"${COMPOSE[@]}" up -d --build

echo
"${COMPOSE[@]}" ps

echo
echo "Dashboard: http://localhost:${NGINX_PORT:-80}"
echo "Level 2 API: http://localhost:${LEVEL2_API_PORT:-8080}"
echo "Heat Management: http://localhost:${HEAT_MANAGEMENT_PORT:-9000}"
