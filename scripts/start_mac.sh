#!/usr/bin/env bash
# Build (if needed) and launch the FinAlly container. Safe to run more than
# once — docker compose up is idempotent, and re-running just reattaches to
# (or recreates, if --build was passed) the existing service.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

PORT="${FINALLY_PORT:-8000}"
URL="http://localhost:${PORT}"
BUILD_FLAG=""
OPEN_BROWSER=1

for arg in "$@"; do
  case "$arg" in
    --build) BUILD_FLAG="--build" ;;
    --no-open) OPEN_BROWSER=0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

if ! docker info >/dev/null 2>&1; then
  echo "Docker does not appear to be running. Start Docker Desktop and try again." >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "No .env file found — copy .env.example to .env to enable live AI chat"
  echo "and/or real market data. The app will still start and work fine without it"
  echo "(simulator market data, chat disabled unless LLM_MOCK=true)."
  echo
fi

echo "Starting FinAlly..."
docker compose up -d $BUILD_FLAG

echo -n "Waiting for the app to become healthy"
for _ in $(seq 1 60); do
  status="$(docker inspect --format='{{.State.Health.Status}}' finally 2>/dev/null || echo "starting")"
  if [ "$status" = "healthy" ]; then
    echo
    break
  fi
  echo -n "."
  sleep 1
done
echo

echo "FinAlly is running at ${URL}"

if [ "$OPEN_BROWSER" = "1" ]; then
  if command -v open >/dev/null 2>&1; then
    open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL"
  fi
fi
