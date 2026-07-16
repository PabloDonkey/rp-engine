#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "${1:-}" == "--skip-db-up" ]]; then
  shift
else
  scripts/db_services.sh up
fi

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
else
  PYTHON_BIN="uv run python"
fi

if [[ "$PYTHON_BIN" == "uv run python" ]]; then
  RP_ENGINE_RUN_POSTGRES_TESTS=1 uv run python -m pytest "$@"
else
  RP_ENGINE_RUN_POSTGRES_TESTS=1 "$PYTHON_BIN" -m pytest "$@"
fi
