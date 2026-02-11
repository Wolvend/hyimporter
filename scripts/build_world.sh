#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CFG="${1:-config.yaml}"
if [ "$#" -gt 0 ]; then
  shift
fi

if [ ! -f "$CFG" ]; then
  echo "Config file not found: $CFG"
  echo "Create one from config/config.example.yaml"
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Virtual environment missing. Run bash scripts/wsl_setup.sh first."
  exit 1
fi

source .venv/bin/activate
export PYTHONPATH="$ROOT_DIR/src:${PYTHONPATH:-}"
python -m hyimporter.build --config "$CFG" "$@"
