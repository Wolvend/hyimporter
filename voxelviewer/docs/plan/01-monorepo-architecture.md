# Monorepo Architecture (pnpm + TypeScript)

## Target Layout

```text
.
├─ apps/
│  └─ desktop/
├─ packages/
│  ├─ core/
│  ├─ loaders-bo2/
│  ├─ loaders-hytale/
│  ├─ block-registry/
│  ├─ renderer/
│  └─ indexer/
├─ fixtures/
│  ├─ bo2/
│  ├─ hytale/
│  ├─ corpus/
│  └─ fuzz-seeds/
├─ docs/
│  └─ plan/
├─ pnpm-workspace.yaml
├─ package.json
└─ tsconfig.base.json
```

## Package Responsibilities

- `packages/core`: canonical voxel types, bounds, normalization, canonical byte encoding, SHA-256 hashing.
- `packages/loaders-bo2`: BO2 sniffer, strict parser, salvage parser, parse diagnostics.
- `packages/loaders-hytale`: schema-tolerant JSON loader and mapping to canonical voxels.
- `packages/block-registry`: legacy and namespaced block mapping plus YAML overrides.
- `packages/renderer`: greedy mesher, deterministic thumbnail rendering, viewport scene helpers.
- `packages/indexer`: CLI for scan/index/cache, worker orchestration, SQLite read/write.
- `apps/desktop`: Electron shell + React UI for browsing, filtering, viewing, and failure dashboard.

## Dependency Direction

- `core` has no package dependencies in this monorepo.
- `loaders-*` depend on `core` and `block-registry`.
- `renderer` depends on `core`.
- `indexer` depends on `core`, `loaders-*`, `block-registry`, `renderer`.
- `desktop` depends on `core` types and reads persisted data from SQLite outputs.

## Determinism Strategy

- Define stable canonicalization and stable sorting in `core`.
- Keep parse warnings/errors stable by using ordered error codes.
- Run thumbnail renderer with fixed camera, fixed lighting, fixed render settings.
- Use content hash plus renderer/version hash for cache keys.

## Workspace Scripts (planned)

```json
{
  "scripts": {
    "build": "pnpm -r build",
    "test": "pnpm -r test",
    "lint": "pnpm -r lint",
    "indexer": "pnpm --filter @voxelviewer/indexer",
    "desktop": "pnpm --filter @voxelviewer/desktop dev",
    "smoke": "pnpm --filter @voxelviewer/indexer smoke"
  }
}
```

## ADRs to Create During Build

- ADR-001: canonical sort order and bytes format.
- ADR-002: salvage conflict policy for duplicate voxels.
- ADR-003: renderer camera and lighting constants.
- ADR-004: worker pool model and cache key policy.

