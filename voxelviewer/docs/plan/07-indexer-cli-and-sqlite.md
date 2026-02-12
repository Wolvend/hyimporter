# Indexer CLI and SQLite Plan

## CLI Commands

- `scan <folder>`: full or incremental ingest.
- `rescan <folder>`: force reparse and rerender.
- `doctor`: validate DB consistency and missing assets.
- `smoke <folder>`: run short ingest + sample query.

## Primary CLI Example

```bash
pnpm indexer scan <folder> \
  --out data/objects.sqlite \
  --thumbs data/thumbs \
  --cache data/cache \
  --workers 8 \
  --mode strict+salvage
```

## SQLite Schema (initial)

```sql
CREATE TABLE objects (
  id INTEGER PRIMARY KEY,
  path TEXT NOT NULL UNIQUE,
  format TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  valid INTEGER NOT NULL,
  parse_mode TEXT NOT NULL,
  dx INTEGER NOT NULL,
  dy INTEGER NOT NULL,
  dz INTEGER NOT NULL,
  block_count INTEGER NOT NULL,
  unique_blocks INTEGER NOT NULL,
  unknown_blocks INTEGER NOT NULL,
  author TEXT,
  description TEXT,
  warnings_json TEXT NOT NULL,
  errors_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE assets (
  object_id INTEGER PRIMARY KEY,
  thumb_path TEXT NOT NULL,
  mesh_cache_path TEXT,
  ingest_report_path TEXT NOT NULL,
  FOREIGN KEY(object_id) REFERENCES objects(id) ON DELETE CASCADE
);
```

## Incremental Indexing

- Snapshot file metadata (`path`, `size`, `mtime`, quick hash).
- Detect:
  - added files,
  - changed files,
  - removed files.
- Removed files are soft-marked missing or deleted per CLI flag.
- For unchanged content hash, skip parse/mesh/thumb and keep cache.

## Worker Pool

- Use process-backed worker pool for parse + mesh + thumb tasks.
- Main thread handles filesystem scan and DB writes.
- Workers output deterministic task result envelopes.
- Max workers configurable; defaults to physical cores - 1.

## Failure Handling

- Any file must create/retain object record.
- Invalid files:
  - `valid = 0`
  - diagnostics in `errors_json`
  - error thumbnail path in assets.

## Unknown Blocks Persistence

- Store summary count in `objects.unknown_blocks`.
- Persist detailed unknown list in `warnings_json` or optional sidecar JSON file.

