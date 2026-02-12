# HyImporter (Cross-Platform Pipeline)

A reproducible terrain pipeline that converts WoW exports (from wow.export on Windows) into seam-safe OBJ tiles for Hytale import, with a strict vertical budget of Y=0..319.

HyImporter is currently WoW-focused (via wow.export input packages), but the core architecture is source-agnostic and intended to support additional game/world export formats in future releases.

Supported runtime platforms:
- Windows (PowerShell)
- WSL/Linux (bash)
- macOS (bash)

Source workflow right now:
- Export tool: wow.export Windows GUI (required for WoW extraction)
- Import target: Hytale Creative Tools OBJ import
- Recommended for large worlds: async schematic paste using `cc.invic_SchematicLoader`

## Windows-only tasks (must be done on Windows)
1. Install and run wow.export GUI, and export map data.
2. Import generated OBJ tiles into Hytale using Creative Tools -> Import OBJ.

Everything else in this repo runs on any supported platform.

## Directory layout (required)
Recommended shared folder layout:

C:\\hyimporter\\
  input\\
    <map_name>\\   (Windows writes here)
  out\\            (pipeline writes here)

Examples:
- Windows: `C:\hyimporter\input`, `C:\hyimporter\out`
- WSL: `/mnt/c/hyimporter/input`, `/mnt/c/hyimporter/out`
- macOS/Linux: `$HOME/hyimporter/input`, `$HOME/hyimporter/out`

## Repo layout
- HyImporter/
- README.md
- requirements.txt
- config/
- scripts/
- docs/
- src/hyimporter/
- tests/

## Quick start
### Windows (PowerShell)
1. Clone repo.
2. Setup env:
   - `powershell -ExecutionPolicy Bypass -File scripts/setup_windows.ps1`
3. Create config:
   - `Copy-Item config/config.example.yaml config.yaml`
4. Edit `config.yaml`:
   - `project.map_name`
   - `paths.input_root` and `paths.output_root`
5. Build:
   - `powershell -ExecutionPolicy Bypass -File scripts/build_world.ps1 -Config config.yaml`

### WSL/Linux/macOS (bash)
1. Clone repo.
2. Setup env:
   - `bash scripts/setup_unix.sh`
   - WSL-only full system setup: `bash scripts/wsl_setup.sh`
3. Create config:
   - `cp config/config.example.yaml config.yaml`
4. Edit `config.yaml`:
   - `project.map_name`
   - `paths.input_root` and `paths.output_root`
5. Build:
   - `bash scripts/build_world.sh config.yaml`

## Expected inputs
The pipeline reads:

<input_root>/<map_name>/
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

<output_root>/<map_name>/
  tiles/tile_<i>_<j>.obj
  tiles/tile_<i>_<j>__<material>.obj
  tiles/tile_<i>_<j>.schematic
  tiles/tile_<i>_<j>.bo2
  tiles/tile_<i>_<j>.meta.json
  runbook/hytale_import_runbook.md
  runbook/tile_manifest.csv
  qa/summary.json
  qa/importer_mcp_review.json
  qa/importer_mcp_review.md
  qa/*.png

## Build command
Primary CLI (all platforms):
python -m hyimporter.build --config config.yaml

Wrapper (bash):
bash scripts/build_world.sh config.yaml

Wrapper (PowerShell):
powershell -ExecutionPolicy Bypass -File scripts/build_world.ps1 -Config config.yaml

8-bit override (unsafe; explicit only):
bash scripts/build_world.sh config.yaml --allow-8bit-height

Deterministic async controls:
- Default is async tile export with deterministic manifest ordering (`runtime.async_tile_export: true`).
- Force sync mode: `bash scripts/build_world.sh config.yaml --sync-tiles`
- Pin workers: `bash scripts/build_world.sh config.yaml --tile-workers 8`

## Async Schematic Import (Recommended For Big Worlds)
If Hytale's OBJ converter/import freezes on big meshes, use the SchematicLoader mod to paste tiles in async batches.

1. Build with schematics enabled:
   - `outputs.export_schematic: true`
   - Keep `outputs.schematic_full_volume: false` (surface-only)
2. Sync tiles into your Hytale save:
   - Windows:
     - `powershell -ExecutionPolicy Bypass -File scripts/sync_to_hytale_schematicloader.ps1 -MapName <map_name> -WorldName <WorldName>`
   - WSL:
     - `bash scripts/sync_to_hytale_schematicloader.sh <map_name> /mnt/c/hyimporter/out <WorldName>`
3. Restart the world/server, then in game:
   - `/schem list`
   - `/schem load <tile_file_name>`
   - `/schem paste`

Importer_MCP post-build review:
- Enabled by default on `python -m hyimporter.build`.
- Skip it: `--skip-importer-mcp`
- Fail on quality: `--importer-mcp-fail-on needs_review` or `--importer-mcp-fail-on fail`

## VoxelViewer connection
`voxelviewer/` can be used as a foundational GUI/indexer for generated tile assets.

Bridge scripts:
- Bash: `bash scripts/connect_voxelviewer.sh <map_name> [output_root]`
- PowerShell:
  - `powershell -ExecutionPolicy Bypass -File scripts/connect_voxelviewer.ps1 -MapName <map_name> [-OutputRoot C:/hyimporter/out]`

These commands run the Importer_MCP quality review, then index tiles into VoxelViewer.

## Validation / self-test
Use this to verify "worked vs broken" deterministically:

- Quick confidence suite:
  - `bash scripts/self_test.sh quick`
- Full suite:
  - `bash scripts/self_test.sh full`
- Windows full suite:
  - `.\.venv\Scripts\python.exe -m pytest -q`

The quick suite verifies:
- height bounds remain inside `[0..319]`
- seam max diff stays `0`
- sync and async tile export produce equivalent deterministic results

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
- Default roots are OS-aware and can be overridden with:
  - `HYIMPORTER_BASE_DIR`
  - `HYIMPORTER_INPUT_ROOT`
  - `HYIMPORTER_OUTPUT_ROOT`

## Roadmap
The highest-impact next step is a faster, more reliable Hytale-side import path (sparse tiles + async paste mod) so large worlds do not depend on Hytale's OBJ importer.

See: `plan.md`

## Docs
- Importer_MCP entry file: `Importer_MCP`
- Plan (speed + determinism): `plan.md`
- Windows export workflow: docs/windows_wowexport_runbook.md
- Hytale import workflow: docs/hytale_import_runbook.md
- Multi-platform setup: docs/multi_platform_setup.md
- V1 roadmap issue list: docs/v1_roadmap_issue_list.md
- Common fixes: docs/troubleshooting.md
