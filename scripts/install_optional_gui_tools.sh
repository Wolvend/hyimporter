#!/usr/bin/env bash
set -euo pipefail

if [ -z "${WAYLAND_DISPLAY:-}" ] && [ -z "${DISPLAY:-}" ]; then
  echo "WSLg not detected."
  echo "Install optional tools on Windows if desired: QGIS, CloudCompare, Blender."
  echo "Pipeline does not require GUI tools."
  exit 0
fi

echo "WSLg detected. Installing optional tools if available."
sudo apt-get update -y

# CloudCompare
if apt-cache show cloudcompare >/dev/null 2>&1; then
  sudo apt-get install -y cloudcompare || true
else
  echo "cloudcompare package not found in current apt sources"
fi

# QGIS (simple apt attempt)
if apt-cache show qgis >/dev/null 2>&1; then
  sudo apt-get install -y qgis || true
else
  echo "qgis package not found in current apt sources"
  echo "Use official qgis.org repository if needed"
fi

# Blender
if apt-cache show blender >/dev/null 2>&1; then
  sudo apt-get install -y blender || true
elif command -v snap >/dev/null 2>&1; then
  sudo snap install blender --classic || true
else
  echo "Blender not available via apt and snap not present"
  echo "Download tarball manually from blender.org if needed"
fi

echo "Optional GUI tool install attempt complete"
