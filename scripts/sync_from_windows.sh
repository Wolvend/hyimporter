#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: bash scripts/sync_from_windows.sh <map_name> [local_target_dir]"
  exit 1
fi

MAP_NAME="$1"
LOCAL_TARGET="${2:-./data/input}"
SRC="/mnt/c/hyimporter/input/${MAP_NAME}"
DST="${LOCAL_TARGET}/${MAP_NAME}"

if [ ! -d "$SRC" ]; then
  echo "Source map package not found: $SRC"
  exit 1
fi

mkdir -p "$DST"

if command -v rsync >/dev/null 2>&1; then
  rsync -av --delete "$SRC/" "$DST/"
else
  rm -rf "$DST"
  mkdir -p "$DST"
  cp -r "$SRC/"* "$DST/"
fi

echo "Synced map package to $DST"
