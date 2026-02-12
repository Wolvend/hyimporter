export type ObjectFormat = "bo2" | "hytale" | "schematic" | "unknown";
export type ParseModeUsed = "strict" | "salvage" | "none";

export interface IngestTask {
  path: string;
  mode: "strict" | "salvage" | "strict+salvage";
  profile: "mc_1_12_legacy" | "mc_1_16_namespaced";
  overridesPath?: string;
  thumbsDir: string;
  cacheDir: string;
  reportsDir: string;
  thumbSize: number;
  debugProjections?: boolean;
}

export interface IngestResult {
  path: string;
  format: ObjectFormat;
  sha256: string;
  valid: boolean;
  parse_mode: ParseModeUsed;
  dx: number;
  dy: number;
  dz: number;
  block_count: number;
  unique_blocks: number;
  unknown_blocks: number;
  author: string | null;
  description: string | null;
  warnings_json: string;
  errors_json: string;
  thumb_path: string;
  mesh_cache_path: string | null;
  ingest_report_path: string;
}

export interface IngestionReport {
  path: string;
  formatDetected: ObjectFormat;
  parseMode: ParseModeUsed;
  valid: boolean;
  sha256: string;
  warnings: unknown[];
  errors: unknown[];
  unknownBlocks: unknown;
  stats: {
    blockCount: number;
    uniqueBlocks: number;
    bounds: { dx: number; dy: number; dz: number };
  };
  timingMs: {
    sniff: number;
    parse: number;
    canonicalize: number;
    mesh: number;
    thumbnail: number;
    dbWrite: number;
    total: number;
  };
  memoryEstimateBytes: number;
  toolVersions: Record<string, string>;
}
