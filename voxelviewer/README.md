# VoxelViewer (Clean-Room)

Clean-room monorepo for indexing and previewing voxel objects from Minecraft OTG/TerrainControl `.bo2`, Minecraft `.schematic`/`.schem`, and Hytale prefab JSON files.

The implementation is deterministic-first:

- canonical voxel normalization and sort
- stable SHA-256 canonical hashes
- strict + salvage parsing modes for BO2
- structured per-file ingestion reports
- deterministic thumbnail generation

## Monorepo Structure

- `packages/core`: canonical voxel model, bounds, normalization, canonical bytes/hash
- `packages/loaders-bo2`: BO2 sniffer + strict/salvage parser
- `packages/loaders-hytale`: schema-tolerant Hytale JSON loader
- `packages/loaders-schematic`: `.schematic` + `.schem` NBT loader with strict/salvage modes
- `packages/block-registry`: legacy/namespaced block mapping with YAML overrides
- `packages/renderer`: greedy mesher + deterministic thumbnail renderer
- `packages/indexer`: SQLite indexer CLI with worker pool + cache
- `apps/desktop`: Electron + React browser and 3D viewer

## Build and Run

```bash
pnpm install
pnpm -r build
pnpm indexer scan <folder> --out data/objects.sqlite --thumbs data/thumbs
pnpm desktop -- --db data/objects.sqlite
```

## Indexer CLI

```bash
pnpm indexer scan <folder> \
  --out data/objects.sqlite \
  --thumbs data/thumbs \
  --cache data/cache \
  --reports data/reports \
  --workers 8 \
  --mode strict+salvage \
  --profile mc_1_12_legacy
```

## Tests

```bash
pnpm test
pnpm test:compat
pnpm smoke
```

## Clean-Room Policy

- No code is copied from `SchematicWebViewer`.
- `SchematicWebViewer` is reference-only for behavior checks.
- BO2 behavior references must include attribution and license notes.

See planning docs in `docs/plan/` for architecture and implementation details.
