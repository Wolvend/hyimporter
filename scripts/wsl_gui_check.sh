#!/usr/bin/env bash
set -euo pipefail

echo "Checking WSL GUI support"

if [ -n "${WAYLAND_DISPLAY:-}" ] || [ -n "${DISPLAY:-}" ]; then
  echo "WSLg/GUI appears available"
  echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-<empty>}"
  echo "DISPLAY=${DISPLAY:-<empty>}"
  exit 0
fi

echo "No GUI display variables detected in this shell"
echo "Optional GUI tools (QGIS, CloudCompare, Blender) are NOT required for this pipeline."
echo "If you want GUI inspection tools, install them on Windows instead."
