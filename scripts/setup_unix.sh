#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.10+ and retry."
  exit 1
fi

echo "[1/3] Creating virtual environment (.venv)"
python3 -m venv .venv

echo "[2/3] Installing Python dependencies"
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -r requirements.txt

echo "[3/3] Validation"
.venv/bin/python --version
.venv/bin/python -m pip freeze | head -n 20

echo "Done. Build with:"
echo "  bash scripts/build_world.sh config.yaml"
