#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ACTION="${1:-up}"

case "$ACTION" in
  up)
    scripts/compose.sh up -d
    ;;
  down)
    scripts/compose.sh down
    ;;
  reset)
    scripts/compose.sh down -v
    ;;
  logs)
    scripts/compose.sh logs -f
    ;;
  ps)
    scripts/compose.sh ps
    ;;
  *)
    echo "Usage: scripts/db_services.sh [up|down|reset|logs|ps]"
    exit 1
    ;;
esac
