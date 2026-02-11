#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/5] Updating apt package index"
sudo apt-get update -y

echo "[2/5] Installing required system packages"
sudo apt-get install -y \
  python3 python3-venv python3-pip \
  git git-lfs \
  build-essential pkg-config \
  imagemagick ffmpeg unzip p7zip-full jq \
  gdal-bin python3-gdal libgdal-dev

git lfs install || true

echo "[3/5] Creating virtual environment"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

echo "[4/5] Validation checks"
python --version
python -m pip freeze | head -n 20

if [ -d /mnt/c ]; then
  echo "OK: /mnt/c is accessible"
else
  echo "ERROR: /mnt/c is not accessible from WSL"
  exit 1
fi

echo "Disk space (/mnt/c):"
df -h /mnt/c || true

echo "[5/5] Done"
echo "Activate env with: source .venv/bin/activate"
