#!/usr/bin/env bash
# Stop and remove the FinAlly container. The named volume (and therefore the
# database) is left untouched. Safe to run even if nothing is running.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

if ! docker info >/dev/null 2>&1; then
  echo "Docker does not appear to be running — nothing to stop."
  exit 0
fi

docker compose down

echo "FinAlly stopped. Your portfolio data is preserved (volume: finally-data)."
