# Testing, Corpus, Fuzz, and Property Plan

## Fixture Layout

```text
fixtures/
├─ bo2/golden/
├─ hytale/golden/
├─ corpus/real-world/
├─ fuzz-seeds/
└─ expected/
   ├─ hashes.json
   ├─ bounds.json
   └─ counts.json
```

## Golden Fixture Tests

- For each fixture:
  - parse using target mode,
  - canonicalize,
  - verify expected hash,
  - verify bounds and block counts.

- Keep expected data versioned and review changes explicitly.

## Fuzz and Mutation Tests

- Random byte files for BO2 sniffer/parser.
- Mutate real fixtures by truncation, byte flips, section duplication.
- Invariant: parser never crashes process.
- Expected result is valid parse or structured failure, never uncaught exception.

## Property-Based Tests

- Canonicalization invariants:
  - normalized min bounds are zero,
  - no voxel outside bounds,
  - hash is deterministic across repeated runs,
  - sort order always stable.

- Duplicate handling invariants:
  - salvage mode deterministic last-write-wins.

## Corpus Harness

- Command: `pnpm test:compat`.
- Produces summary:
  - total files,
  - valid/invalid counts,
  - top error codes,
  - parse-mode distribution.

## Regression Gates

- CI fails if:
  - deterministic hash drift occurs on golden fixtures,
  - crash detected in fuzz harness,
  - key parser error rates regress beyond tolerance.

