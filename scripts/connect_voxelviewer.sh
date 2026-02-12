#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MAP_NAME="${1:-}"
if [ -z "$MAP_NAME" ]; then
  echo "Usage: bash scripts/connect_voxelviewer.sh <map_name> [output_root]"
  exit 2
fi

OUTPUT_ROOT="${2:-/mnt/c/hyimporter/out}"
MAP_OUT_DIR="${OUTPUT_ROOT%/}/${MAP_NAME}"

if [ ! -x ".venv/bin/python" ]; then
  echo "Missing .venv Python. Run setup first."
  exit 1
fi

if [ ! -d "$ROOT_DIR/voxelviewer" ]; then
  echo "Missing voxelviewer workspace at: $ROOT_DIR/voxelviewer"
  exit 1
fi

export PYTHONPATH="$ROOT_DIR/src:${PYTHONPATH:-}"
.venv/bin/python -m hyimporter.importer_mcp \
  --output-dir "$MAP_OUT_DIR" \
  --index-with-voxelviewer \
  --voxelviewer-root "$ROOT_DIR/voxelviewer"

echo "VoxelViewer index connection complete for: $MAP_OUT_DIR"
