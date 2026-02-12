import { canonicalize, type CanonicalObject, type Voxel } from "@voxelviewer/core";
import { BlockRegistry, buildUnknownBlockReport, type UnknownBlockReport } from "@voxelviewer/block-registry";

export interface Diagnostic {
  code: string;
  severity: "warning" | "error";
  message: string;
}

export interface HytaleSniffResult {
  match: boolean;
  confidence: "high" | "medium" | "low";
  reasonCodes: string[];
}

export interface HytaleLoadOptions {
  registry: BlockRegistry;
  sourcePath?: string;
}

export interface HytaleLoadResult {
  format: "hytale";
  valid: boolean;
  canonical?: CanonicalObject;
  metadata: Record<string, string>;
  warnings: Diagnostic[];
  errors: Diagnostic[];
  unknownBlocks: UnknownBlockReport;
}

interface BlockRecordLike {
  x?: number;
  y?: number;
  z?: number;
  id?: number;
  data?: number;
  name?: string;
  block?: string;
  palette?: number;
}

interface RootLike {
  blocks?: BlockRecordLike[];
  voxels?: BlockRecordLike[];
  palette?: string[] | Record<string, string>;
  prefab?: RootLike;
  author?: string;
  creator?: string;
  description?: string;
  desc?: string;
}

export function sniffHytale(input: Uint8Array): HytaleSniffResult {
  const text = Buffer.from(input.subarray(0, Math.min(input.length, 8192))).toString("utf8").trimStart();
  if (!text.startsWith("{") && !text.startsWith("[")) {
    return { match: false, confidence: "high", reasonCodes: ["NOT_JSON"] };
  }
  const lowered = text.toLowerCase();
  const hasHints = lowered.includes("\"blocks\"") || lowered.includes("\"palette\"") || lowered.includes("\"prefab\"");
  return hasHints
    ? { match: true, confidence: "medium", reasonCodes: ["JSON_WITH_PREFAB_HINTS"] }
    : { match: true, confidence: "low", reasonCodes: ["JSON_NO_STRONG_HINTS"] };
}

function normalizeRoot(raw: unknown): RootLike {
  if (!raw || typeof raw !== "object") {
    return {};
  }
  const obj = raw as RootLike;
  if (obj.prefab && typeof obj.prefab === "object") {
    return obj.prefab as RootLike;
  }
  return obj;
}

function paletteLookup(root: RootLike, record: BlockRecordLike): string | undefined {
  if (typeof record.name === "string") return record.name;
  if (typeof record.block === "string") return record.block;
  if (!Number.isInteger(record.palette)) return undefined;

  const p = root.palette;
  if (Array.isArray(p)) {
    const idx = record.palette as number;
    return typeof p[idx] === "string" ? p[idx] : undefined;
  }
  if (p && typeof p === "object") {
    const key = String(record.palette);
    const value = (p as Record<string, string>)[key];
    return typeof value === "string" ? value : undefined;
  }
  return undefined;
}

export function loadHytale(input: Uint8Array, options: HytaleLoadOptions): HytaleLoadResult {
  const warnings: Diagnostic[] = [];
  const errors: Diagnostic[] = [];

  let json: unknown;
  try {
    json = JSON.parse(Buffer.from(input).toString("utf8"));
  } catch (error) {
    errors.push({
      code: "HYTALE_JSON_INVALID",
      severity: "error",
      message: `Invalid JSON: ${(error as Error).message}`
    });
    return {
      format: "hytale",
      valid: false,
      metadata: {},
      warnings,
      errors,
      unknownBlocks: { totalUnknown: 0, entries: [] }
    };
  }

  const root = normalizeRoot(json);
  const blocks = Array.isArray(root.blocks) ? root.blocks : Array.isArray(root.voxels) ? root.voxels : [];
  if (blocks.length === 0) {
    errors.push({
      code: "HYTALE_SCHEMA_MISSING_CORE_FIELD",
      severity: "error",
      message: "No blocks/voxels array detected."
    });
  }

  const voxels: Voxel[] = [];
  const unknownSources: string[] = [];
  const unknownCanonical: string[] = [];

  for (const record of blocks) {
    if (!record || typeof record !== "object") {
      warnings.push({
        code: "HYTALE_BLOCK_RECORD_INVALID",
        severity: "warning",
        message: "Skipping non-object block record."
      });
      continue;
    }

    if (!Number.isInteger(record.x) || !Number.isInteger(record.y) || !Number.isInteger(record.z)) {
      warnings.push({
        code: "HYTALE_BLOCK_RECORD_INVALID",
        severity: "warning",
        message: "Skipping block with non-integer coordinates."
      });
      continue;
    }

    const mappedName = paletteLookup(root, record);
    const resolved = options.registry.resolve({
      namespacedId: mappedName,
      legacyId: Number.isInteger(record.id) ? (record.id as number) : undefined,
      legacyData: Number.isInteger(record.data) ? (record.data as number) : undefined
    });

    voxels.push({
      x: record.x as number,
      y: record.y as number,
      z: record.z as number,
      blockKey: resolved.canonical
    });

    if (resolved.unknown) {
      warnings.push({
        code: "HYTALE_BLOCK_UNKNOWN",
        severity: "warning",
        message: `Unknown block: ${resolved.source}`
      });
      unknownSources.push(resolved.source);
      unknownCanonical.push(resolved.canonical);
    }
  }

  let canonical: CanonicalObject | undefined;
  if (voxels.length > 0) {
    try {
      canonical = canonicalize(voxels, {
        sourcePath: options.sourcePath,
        author: typeof root.author === "string" ? root.author : typeof root.creator === "string" ? root.creator : undefined,
        description: typeof root.description === "string" ? root.description : typeof root.desc === "string" ? root.desc : undefined
      });
    } catch (error) {
      errors.push({
        code: "HYTALE_BLOCK_RECORD_INVALID",
        severity: "error",
        message: `Canonicalization failed: ${(error as Error).message}`
      });
    }
  }

  const metadata: Record<string, string> = {};
  if (typeof root.author === "string") metadata.author = root.author;
  if (typeof root.creator === "string" && !metadata.author) metadata.author = root.creator;
  if (typeof root.description === "string") metadata.description = root.description;
  if (typeof root.desc === "string" && !metadata.description) metadata.description = root.desc;

  return {
    format: "hytale",
    valid: errors.length === 0 && !!canonical,
    canonical,
    metadata,
    warnings,
    errors,
    unknownBlocks: buildUnknownBlockReport(unknownSources, unknownCanonical)
  };
}

