# CI, Build, and Smoke Test Plan

## CI Stages

1. Install and build:
   - `pnpm install`
   - `pnpm -r build`
2. Lint and typecheck:
   - `pnpm -r lint`
   - `pnpm -r typecheck`
3. Tests:
   - unit tests
   - golden fixtures
   - property tests
   - fuzz smoke budget run
4. Smoke integration:
   - index sample fixture folder into SQLite
   - verify DB row counts and thumbnail outputs

## Smoke Script

```bash
pnpm indexer scan fixtures/corpus --out data/objects.sqlite --thumbs data/thumbs
pnpm desktop --db data/objects.sqlite
```

## Determinism Gate

- Re-run hash generation on same fixtures in CI.
- Compare with expected hash snapshots.
- Fail on drift.

## Artifact Retention

- Persist:
  - SQLite output,
  - sample thumbnails,
  - ingestion report bundle.

- Keep failing run artifacts for debugging parser regressions.

