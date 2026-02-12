# Implementation Roadmap

## Phase 1: Repository Bootstrap

- Initialize pnpm workspace and shared TypeScript config.
- Create package/app scaffolds.
- Add baseline lint, test, and build scripts.

## Phase 2: Core Deterministic Model

- Implement canonical voxel types and bounds utilities.
- Implement normalization and canonical sort.
- Implement canonical bytes encoder and SHA-256 hash.
- Add core property tests.

## Phase 3: Loaders

- Build BO2 sniffer and strict parser.
- Add salvage parser with truncation and unknown tag handling.
- Build Hytale tolerant JSON loader.
- Add fixture-based tests for both.

## Phase 4: Block Registry

- Implement profile mappings and YAML override support.
- Add unknown block reporting and placeholder mapping.

## Phase 5: Renderer and Thumbnails

- Implement greedy mesher and material mapping.
- Implement deterministic thumbnail renderer and error thumbnail.
- Add cache-key versioning support.

## Phase 6: Indexer CLI + SQLite

- Implement folder scanning, incremental detection, worker pool.
- Implement DB schema migrations and upsert logic.
- Implement per-file ingestion reports and cache wiring.

## Phase 7: Desktop App

- Build Electron shell and React panes.
- Add list/filter/search UI and metadata panel.
- Add 3D viewer controls and failure dashboard.
- Add export actions (JSON first, `.schem` optional).

## Phase 8: Hardening and CI

- Build corpus harness and fuzz tests.
- Add smoke scripts and CI artifact publishing.
- Add clean-room audit and reference attribution docs.

## Milestone Exit Criteria

- Can index 3000-file dataset without crashes.
- Every file yields DB record and thumbnail path.
- Deterministic hashes and thumbnails across repeat runs.
- UI supports required filters, 3D view, and failure triage.

