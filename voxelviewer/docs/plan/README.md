# VoxelViewer Planning Index

This folder defines the implementation plan for a clean-room, deterministic, testable monorepo.

## Goals

- Ingest and preview around 3000 voxel objects from BO2 and Hytale prefab files.
- Be robust against malformed files via strict and salvage parse modes.
- Be deterministic across runs: canonical hashes, normalized bounds, and thumbnail output stability.
- Keep UX inspired by Cubical patterns without reusing Cubical source.

## Document Map

- `00-clean-room-and-compatibility.md`: rules for clean-room development and compatibility checks.
- `01-monorepo-architecture.md`: workspace layout, package boundaries, dependency direction.
- `02-core-canonical-voxel-model.md`: canonical voxel schema, normalization, sorting, hashing.
- `03-bo2-loader-strict-salvage.md`: BO2 sniffing and strict/salvage parser behavior.
- `04-hytale-loader.md`: tolerant Hytale prefab loading and canonical mapping.
- `05-block-registry-and-mapping.md`: block profile mapping, overrides, unknown block behavior.
- `06-renderer-mesher-thumbnails.md`: meshing, render pipeline, deterministic thumbnails.
- `07-indexer-cli-and-sqlite.md`: CLI, SQLite schema, cache, incremental indexing.
- `08-desktop-app-ux-and-failure-dashboard.md`: Electron/React UI requirements and flows.
- `09-testing-corpus-fuzz-properties.md`: fixture corpus, fuzzing, and property tests.
- `10-observability-and-ingestion-reports.md`: structured logs and ingestion report schema.
- `11-ci-build-and-smoke.md`: CI pipeline, smoke tests, reproducibility checks.
- `12-implementation-roadmap.md`: execution phases and milestones.

