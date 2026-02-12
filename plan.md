# HyImporter Plan (Speed + Determinism)

This repo already ships a safe, deterministic terrain pipeline (WoW `wow.export` -> tiled outputs with strict Y=0..319 + seam validation). The remaining big risk is *Hytale-side import* performance and reliability for large worlds.

This plan prioritizes: no monolithic exports, no per-tile normalization, deterministic tiling, overlap processing, and hard QA fail conditions.

## Current Baseline (Already Implemented)
- Deterministic 512x512 tiling with overlap and seam diff assertions.
- Height fitting into `Y=0..319` using P1/P99 clamp + gamma + margins.
- OBJ tile export for Hytale Creative Tools import.
- Optional `.schematic`/`.bo2` exports for async paste workflows.
- QA reports + smoke tests, including sync vs async tile export parity.
- `Importer_MCP` review + optional VoxelViewer indexing bridge.

## Phase 1: Fast Import Path (Most Important)
Goal: avoid Hytale's broken OBJ converter for big maps and avoid full-volume schematic parsing (`W*H*L` loops).

Deliverables:
- Add a **sparse tile format** designed for terrain:
  - Palette of block IDs.
  - Per-(x,z) **columns** (height + material shells), optionally run-length encoded.
  - Deterministic serialization and a checksum per tile.
- Add a Python exporter for this format:
  - Output lives next to existing tile artifacts.
  - Same tile manifest ordering as OBJ pipeline.
- Create a **HyImporter Hytale mod** (`HyImporterPaster`) that:
  - Reads the sparse tiles and pastes in **chunk-sized async batches** (non-blocking).
  - Supports progress, pause/cancel, and resume from last pasted tile.
  - Uses deterministic ordering to guarantee identical results run-to-run.

Acceptance tests:
- For a small test map, mod paste output matches the existing `.schematic` output hashes (within defined tolerances).
- Paste is resumable and idempotent (re-running does not duplicate/shift).
- No seams across tile borders (tile manifest coordinates honored exactly).

## Phase 2: Incremental Builds (Developer Iteration Speed)
Goal: avoid rebuilding the whole world when tuning parameters.

Deliverables:
- Content-addressed caching per tile keyed by:
  - Input file hashes (height/weights/masks).
  - Relevant config hash.
  - Exporter version string.
- CLI flags:
  - `--tiles i j` (single tile)
  - `--bbox x0 z0 x1 z1` (world-space crop)
  - `--force` (ignore cache)
- “Only changed tiles” export for OBJ/sparse tiles + updated manifest.

Acceptance tests:
- Cache hits do not change outputs (byte-identical artifacts).
- Partial rebuild still passes seam validation vs neighbors (overlap rules preserved).

## Phase 3: Performance Engineering (Without Changing Results)
Goal: speed up heavy passes while preserving determinism.

Targets:
- Hydrology (sink fill / flow / accumulation) and morphological cleanup.
- Meshing and OBJ writing.

Approach:
- Keep algorithms identical; optimize implementations:
  - Optional `numba`/C-extensions for hot loops.
  - Multi-process tile export (already present) with deterministic ordering.
  - Memory caps + streaming writes for large tiles.

Acceptance tests:
- Sync and async modes remain output-equivalent.
- CPU- and memory-bound regressions are caught in smoke/perf tests.

## Phase 4: Beyond WoW (Input Adapter Architecture)
Goal: make HyImporter a general “game world -> Hytale tiles” pipeline without diluting correctness.

Deliverables:
- Input adapter interface:
  - `height + optional weights/masks + placements`
- WoW stays as the first supported adapter (via `wow.export`).
- New adapters can be added without touching core tiling/height-fit/QA logic.

## Tracking
- Shortlist/issue-style breakdown lives in: `docs/v1_roadmap_issue_list.md`
- Multi-platform setup notes: `docs/multi_platform_setup.md`

