#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

export PYTHONPATH="$ROOT_DIR/src:${PYTHONPATH:-}"
exec python "$ROOT_DIR/scripts/mcp_server.py"
