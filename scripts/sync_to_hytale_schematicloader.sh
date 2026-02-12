#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MAP_NAME="${1:-}"
if [ -z "$MAP_NAME" ]; then
  echo "Usage: bash scripts/sync_to_hytale_schematicloader.sh <map_name> [output_root] [world_name]"
  echo "Example:"
  echo "  bash scripts/sync_to_hytale_schematicloader.sh my_zone /mnt/c/hyimporter/out woof"
  exit 2
fi

OUTPUT_ROOT="${2:-/mnt/c/hyimporter/out}"
WORLD_NAME="${3:-woof}"

PS="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
if [ ! -x "$PS" ]; then
  echo "Missing powershell.exe at: $PS"
  echo "Run the PowerShell script directly from Windows instead:"
  echo "  scripts/sync_to_hytale_schematicloader.ps1"
  exit 1
fi

OUT_WIN="$(wslpath -w "$OUTPUT_ROOT")"

"$PS" -NoProfile -ExecutionPolicy Bypass -File "$ROOT_DIR/scripts/sync_to_hytale_schematicloader.ps1" \
  -MapName "$MAP_NAME" \
  -OutputRoot "$OUT_WIN" \
  -WorldName "$WORLD_NAME"

