# HyImporter V1 Roadmap Issue List

This roadmap converts "Crafting Azeroth"-style lessons into concrete, implementation-ready work for HyImporter.

Context:
- HyImporter is WoW-first today.
- The architecture should expand to additional source formats.
- Determinism and safety guarantees are non-negotiable.

Non-negotiable constraints for every ticket:
- No per-tile height normalization.
- No per-tile independent scaling.
- Height remains in `[0..319]`.
- Tile core size remains `512`, with overlap.
- Seam max diff remains `0` unless a ticket explicitly changes policy.

## Milestone 1: WoW Production Hardening

### HI-101: Material Mapping Database (Versioned)
Goal: Replace ad hoc layer mapping with versioned, auditable material mappings.

Scope:
- Define mapping schema in `config/material_mappings/`.
- Add mapping version + checksum to output metadata.
- Add fallback behavior when unknown source layers appear.

Acceptance criteria:
- Build succeeds with a named mapping version.
- `summary.json` includes mapping version.
- Unknown layers are reported as warnings with counts.
- Existing deterministic tests still pass.

Dependencies:
- None.

### HI-102: Mapping QA Report
Goal: Make mapping quality measurable.

Scope:
- Add material confusion report (source layer -> chosen semantic label).
- Add coverage thresholds and warning triggers.
- Add "high-risk terrain zones" summary (cliffs/beaches/snowline transitions).

Acceptance criteria:
- New QA JSON block is emitted.
- Warnings are emitted when configured thresholds are violated.
- Report is deterministic for identical inputs.

Dependencies:
- HI-101.

### HI-103: Import Stability Mode (Layered Delivery)
Goal: Reduce in-game importer failures on large, complex data.

Scope:
- Add optional staged delivery modes:
  - `base_only`
  - `base_then_shells`
  - `material_batches`
- Emit ordered import plan in runbook.

Acceptance criteria:
- Runbook includes deterministic ordered steps.
- Tile manifest includes stage ordering columns.
- Existing default mode remains backward-compatible.

Dependencies:
- None.

## Milestone 2: Scale Operations

### HI-201: Batch Import Orchestration Manifest
Goal: Make huge world imports operationally manageable.

Scope:
- Add machine-readable import queue file:
  - tile id
  - stage
  - source file path
  - target world coordinates
- Add retry-safe status columns (`pending`, `imported`, `failed`).

Acceptance criteria:
- Manifest can resume without reordering completed work.
- Queue ordering is deterministic.
- Runbook references queue workflow.

Dependencies:
- HI-103.

### HI-202: Large-World Guardrails
Goal: Prevent accidental "monolithic export" or unusable tile volumes.

Scope:
- Extend safety warnings with:
  - projected total import time
  - heavy tile hotspots
  - warning tiers (`info`, `warn`, `hard_warn`)
- Add optional hard-stop flag when tile complexity exceeds limits.

Acceptance criteria:
- New guardrail metrics appear in `summary.json`.
- Config flag can enforce hard-stop behavior.
- Existing behavior unchanged by default.

Dependencies:
- None.

### HI-203: Performance + Cache Layer
Goal: Make repeated builds fast and predictable.

Scope:
- Add deterministic cache keys for expensive intermediate outputs.
- Cache invalidates on:
  - config hash
  - input file hash
  - mapping version
- Add cache hit/miss stats to QA summary.

Acceptance criteria:
- Re-running unchanged build uses cache.
- Any input/config change invalidates affected cache entries.
- Output bytes remain identical with/without cache.

Dependencies:
- HI-101.

## Milestone 3: Multi-Source Platform Expansion

### HI-301: Source Adapter SDK
Goal: Formalize adapters so WoW is one source among many.

Scope:
- Define adapter contract:
  - probe
  - load_height
  - load_weights
  - load_masks
  - load_colormap
  - load_metadata
- Register adapters via explicit names.

Acceptance criteria:
- WoW adapter conforms to contract.
- At least one generic adapter exists (heightmap pack).
- CLI can select adapter explicitly.

Dependencies:
- None.

### HI-302: Canonical Staging Format
Goal: Decouple ingestion from build.

Scope:
- Add optional ingest command writing canonical staging package.
- Build command can consume canonical staging package directly.

Acceptance criteria:
- Ingest -> Build path matches direct build results.
- Sync/async parity still holds.
- QA outputs remain deterministic.

Dependencies:
- HI-301.

### HI-303: Cross-Source Validation Suite
Goal: Ensure new adapters do not regress core guarantees.

Scope:
- Add adapter fixture packs (small deterministic datasets).
- Add matrix tests across adapters for:
  - height bounds
  - seam safety
  - deterministic tile ordering

Acceptance criteria:
- CI passes adapter matrix.
- Any adapter violating core guarantees fails CI.

Dependencies:
- HI-301, HI-302.

## Milestone 4: Release Readiness

### HI-401: CI Matrix + Artifact QA
Goal: Verify behavior across Windows, Linux, and macOS.

Scope:
- GitHub Actions matrix:
  - windows-latest
  - ubuntu-latest
  - macos-latest
- Run unit + smoke tests.
- Publish QA artifacts for smoke runs.

Acceptance criteria:
- CI green on all platforms.
- QA artifacts uploaded per platform.

Dependencies:
- None.

### HI-402: Backward Compatibility Contract
Goal: Prevent accidental breaking changes for current users.

Scope:
- Define compatibility policy for:
  - config keys
  - output file naming
  - runbook/manifest schema
- Add migration notes for any changed field.

Acceptance criteria:
- Policy doc exists and is linked from README.
- Breaking changes require explicit version bump and migration notes.

Dependencies:
- None.

## Recommended Execution Order

1. HI-101
2. HI-102
3. HI-103
4. HI-201
5. HI-202
6. HI-203
7. HI-301
8. HI-302
9. HI-303
10. HI-401
11. HI-402

## Definition of Done for V1

V1 is complete when:
- WoW production workflow is stable for large imports.
- Import process is resumable and deterministic.
- Adapter architecture supports at least WoW + one generic source.
- CI verifies guarantees on all supported OSes.
- QA reports are sufficient to detect scale, seam, and mapping risks before import.
