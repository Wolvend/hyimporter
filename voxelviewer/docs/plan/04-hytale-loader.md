# Hytale Prefab Loader Plan

## Objectives

- Accept schema variants and partial JSON structures.
- Map to canonical voxels with deterministic results.
- Preserve source metadata fields for filtering in UI.

## Sniff and Parse

- Sniffer checks:
  - JSON shape and key hints (`blocks`, `palette`, `size`, `prefab`).
  - File extension hints (`.json`, `.prefab.json`) are advisory only.

- Parse strategy:
  - JSON parse with safe error capture.
  - Tolerant field lookup by aliases (e.g. `author`, `creator`, `description`, `desc`).
  - Handle blocks as array, sparse map, or palette-indexed storage.

## Mapping to Canonical Voxels

- Convert each record to integer `x,y,z`.
- Resolve block IDs through `block-registry`:
  - namespaced id if present,
  - fallback numeric id/data pair if present.
- Preserve unknown block identities as `unknown:*` keys for placeholder rendering.

## Diagnostics

- `HYTALE_JSON_INVALID`
- `HYTALE_SCHEMA_MISSING_CORE_FIELD`
- `HYTALE_BLOCK_RECORD_INVALID`
- `HYTALE_BLOCK_UNKNOWN`

## Output Contract

```ts
interface HytaleParseResult {
  format: "hytale";
  valid: boolean;
  voxels: Voxel[];
  metadata: Record<string, string>;
  warnings: Diagnostic[];
  errors: Diagnostic[];
}
```

## Salvage Behavior

- Skip malformed block entries and continue.
- If partial structures are valid, keep them.
- If no parseable blocks remain, emit invalid result with diagnostics.

