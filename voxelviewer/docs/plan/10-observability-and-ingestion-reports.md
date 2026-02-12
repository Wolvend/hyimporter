# Observability and Ingestion Report Plan

## Per-File Ingestion Report

Each ingested file emits a JSON report persisted to disk and linked from SQLite assets.

## Report Fields

```json
{
  "path": "string",
  "formatDetected": "bo2|hytale|unknown",
  "parseMode": "strict|salvage|none",
  "valid": true,
  "sha256": "hex",
  "warnings": [],
  "errors": [],
  "unknownBlocks": [],
  "stats": {
    "blockCount": 0,
    "uniqueBlocks": 0,
    "bounds": {"dx":0,"dy":0,"dz":0}
  },
  "timingMs": {
    "sniff": 0,
    "parse": 0,
    "canonicalize": 0,
    "mesh": 0,
    "thumbnail": 0,
    "dbWrite": 0,
    "total": 0
  },
  "memoryEstimateBytes": 0,
  "toolVersions": {}
}
```

## Logging

- Structured JSON logs from indexer and workers.
- Include correlation IDs per file and per scan session.
- Deterministic error codes with stable text.

## Metrics (basic)

- Files processed per second.
- Parse success/failure ratio by format.
- Cache hit ratio for mesh/thumb.
- Top warnings and errors.

## UI Integration

- Failure dashboard reads these reports for deep inspection.
- Provide open-report action from object detail panel.

