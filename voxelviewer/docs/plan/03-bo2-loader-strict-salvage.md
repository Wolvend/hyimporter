# BO2 Loader Plan (Strict + Salvage)

## Objectives

- Detect real BO2 files even when extension is wrong.
- Parse as much real-world data as possible without crashes.
- Emit deterministic diagnostics and always produce index output.

## Sniffer (Fast Detection)

- Input: file bytes.
- Steps:
  1. Check for BO2 section markers (`[META]`, `[DATA]`) in expected text/binary framing.
  2. Validate minimal structural signature: metadata-like key/value records plus data region indicator.
  3. Reject known non-BO2 signatures early (JSON leading `{`, gzip headers, NBT signatures, zip).

- Output:
  - `match: true/false`
  - `confidence: high/medium/low`
  - `reasonCodes: string[]`

## Parser Modes

## Strict Mode

- Enforce spec-defined tag sequence and payload sizes.
- Unknown tags are errors.
- Invalid/truncated block data is fatal.
- Duplicate voxel coordinates are fatal.
- Result may be `invalid` with full error list.

## Salvage Mode

- Unknown tags are skipped safely using size cursor logic.
- Unknown tag payload sizes handled by guarded forward scan with sync markers.
- Truncated data section: parse complete records only, stop on partial tail.
- Invalid block record: skip record, log warning code.
- Duplicate coordinates: last valid record wins, log warning.

## Error/Warning Taxonomy

- `BO2_SIG_MISMATCH`
- `BO2_META_TAG_UNKNOWN`
- `BO2_META_TAG_TRUNCATED`
- `BO2_DATA_TRUNCATED`
- `BO2_BLOCK_RECORD_INVALID`
- `BO2_DUPLICATE_VOXEL`
- `BO2_FATAL_PARSE_ERROR`

Each diagnostic includes:

- `code`
- `severity`
- `offsetStart`
- `offsetEnd`
- `message`

## Parsing Output Contract

```ts
interface Bo2ParseResult {
  format: "bo2";
  mode: "strict" | "salvage";
  valid: boolean;
  voxels: Voxel[];
  tags: Record<string, string>;
  warnings: Diagnostic[];
  errors: Diagnostic[];
}
```

## Attribution and Licensing

- Add reference links to TerrainControl/OpenTerrainGenerator BO2 spec and reader behavior docs.
- Preserve license notices where required in `THIRD_PARTY_REFERENCES.md`.
- No direct code copying from reference implementations.

## Fallback Behavior

- If strict fails, auto-run salvage unless disabled.
- If salvage yields zero usable voxels, emit invalid object record with error thumbnail.
- Indexer never drops the file silently.

