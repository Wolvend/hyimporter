#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-quick}"

if [ ! -d ".venv" ]; then
  echo "Virtual environment missing. Run: bash scripts/wsl_setup.sh"
  exit 1
fi

PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python executable not found in venv: $PYTHON_BIN"
  exit 1
fi

export PYTHONPATH="$ROOT_DIR/src:${PYTHONPATH:-}"

echo "[HyImporter] Running self-test mode: ${MODE}"

case "$MODE" in
  quick)
    # Fast confidence set: determinism + seam safety + pipeline smoke.
    "$PYTHON_BIN" -m pytest -q \
      tests/test_async_tile_export.py \
      tests/test_tiling_seams.py \
      tests/test_pipeline_smoke.py
    ;;
  full)
    "$PYTHON_BIN" -m pytest -q
    ;;
  *)
    echo "Usage: bash scripts/self_test.sh [quick|full]"
    exit 2
    ;;
esac

echo "[HyImporter] Self-test passed (${MODE})."
