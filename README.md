# HyImporter (WSL Pipeline)

A reproducible terrain pipeline that converts WoW exports (from wow.export on Windows) into seam-safe OBJ tiles for Hytale import, with a strict vertical budget of Y=0..319.

HyImporter is currently WoW-focused (via wow.export input packages), but the core architecture is source-agnostic and intended to support additional game/world export formats in future releases.

This repo is designed for:
- Host OS: Windows (WoW installed on Windows drive)
- Compute OS: WSL2 Ubuntu (all processing and QA)
- Export tool: wow.export Windows GUI (required)
- Import target: Hytale Creative Tools OBJ import

## Windows-only tasks (must be done on Windows)
1. Install and run wow.export GUI, and export map data.
2. Import generated OBJ tiles into Hytale using Creative Tools -> Import OBJ.

Everything else in this repo runs in WSL.

## Directory layout (required)
Use this shared folder layout so Windows and WSL see the same data:

C:\\hyimporter\\
  input\\
    <map_name>\\   (Windows writes here)
  out\\            (WSL writes here)

WSL view:
- /mnt/c/hyimporter/input
- /mnt/c/hyimporter/out

## Repo layout
- HyImporter/
- README.md
- requirements.txt
- config/
- scripts/
- docs/
- src/hyimporter/
- tests/

## Quick start (WSL)
1. Clone this repo into WSL-accessible storage.
2. Run setup: bash scripts/wsl_setup.sh
3. Copy config and edit map name: cp config/config.example.yaml config.yaml
4. Run build: bash scripts/build_world.sh config.yaml
5. Check outputs:
   - /mnt/c/hyimporter/out/<map_name>/tiles
   - /mnt/c/hyimporter/out/<map_name>/qa/summary.json
   - /mnt/c/hyimporter/out/<map_name>/runbook/hytale_import_runbook.md

## Expected inputs
The pipeline reads:

/mnt/c/hyimporter/input/<map_name>/
  height/height.png            (prefer 16-bit)
  weights/*.png                (optional, recommended)
  weightmaps/*.png             (optional alias)
  masks/*.png                  (optional)
  color/colormap.png           (optional)
  anchors/landmarks.csv        (optional)
  objects/*.json|csv           (optional)
  placements/*.json|csv        (optional)

## Outputs
The pipeline writes:

/mnt/c/hyimporter/out/<map_name>/
  tiles/tile_<i>_<j>.obj
  tiles/tile_<i>_<j>__<material>.obj
  tiles/tile_<i>_<j>.schematic
  tiles/tile_<i>_<j>.bo2
  tiles/tile_<i>_<j>.meta.json
  runbook/hytale_import_runbook.md
  runbook/tile_manifest.csv
  qa/summary.json
  qa/*.png

## Build command
Primary CLI:
python -m hyimporter.build --config config.yaml

Wrapper:
bash scripts/build_world.sh config.yaml

8-bit override (unsafe; explicit only):
bash scripts/build_world.sh config.yaml --allow-8bit-height

Deterministic async controls:
- Default is async tile export with deterministic manifest ordering (`runtime.async_tile_export: true`).
- Force sync mode: `bash scripts/build_world.sh config.yaml --sync-tiles`
- Pin workers: `bash scripts/build_world.sh config.yaml --tile-workers 8`

## Defaults tuned for comprehensive terrain at 320 high
- Clamp percentiles: [1, 99]
- Gamma: 0.85
- Margins: bottom 12, top 24
- Sea level Y: 96
- Snowline Y: 220
- Cliff hysteresis: s_high=2.2, s_low=1.6
- Beach band: dy=6
- Noise macro: amp 6, wavelength 256
- Noise micro: amp 2, wavelength 32
- Min island area: 32
- Majority filter radius: 1 (3x3)
- Tile size: 512, overlap: 16

All parameters are configurable in YAML.

## Notes
- No WoW CASC parsing is implemented here. Use wow.export on Windows.
- The pipeline avoids per-tile normalization and runs seam-safe overlap processing.
- Material transfer is semantic (weights + gates), not RGB-per-voxel by default.
- 8-bit heightmaps are rejected by default and require explicit override flag.
- Seam differences > 0 fail the build.
- `.schematic` and `.bo2` tile outputs are configurable in `outputs.*` config.

## Docs
- Windows export workflow: docs/windows_wowexport_runbook.md
- Hytale import workflow: docs/hytale_import_runbook.md
- Common fixes: docs/troubleshooting.md
