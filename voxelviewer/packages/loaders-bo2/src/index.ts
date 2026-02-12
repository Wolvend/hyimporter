import { canonicalize, type CanonicalObject, type Voxel } from "@voxelviewer/core";
import { BlockRegistry, buildUnknownBlockReport, type UnknownBlockReport } from "@voxelviewer/block-registry";

export type DiagnosticSeverity = "warning" | "error";

export interface Diagnostic {
  code: string;
  severity: DiagnosticSeverity;
  message: string;
  line?: number;
}

export interface Bo2SniffResult {
  match: boolean;
  confidence: "high" | "medium" | "low";
  reasonCodes: string[];
}

export type Bo2ParseMode = "strict" | "salvage" | "strict+salvage";

export interface Bo2LoadOptions {
  mode?: Bo2ParseMode;
  registry: BlockRegistry;
  sourcePath?: string;
}

export interface Bo2LoadResult {
  format: "bo2";
  valid: boolean;
  parseMode: "strict" | "salvage";
  canonical?: CanonicalObject;
  tags: Record<string, string>;
  warnings: Diagnostic[];
  errors: Diagnostic[];
  unknownBlocks: UnknownBlockReport;
}

interface MutableParseState {
  tags: Record<string, string>;
  voxels: Voxel[];
  warnings: Diagnostic[];
  errors: Diagnostic[];
  unknownSources: string[];
  unknownCanonical: string[];
}

const KNOWN_META_KEYS = new Set([
  "author",
  "description",
  "randomrotation",
  "tree",
  "spawnonblocktype",
  "collisionpercentage",
  "dig",
  "rarity",
  "rotateautobranches",
  "collisionblocktype"
]);

function addDiagnostic(target: MutableParseState, diag: Diagnostic): void {
  if (diag.severity === "error") target.errors.push(diag);
  else target.warnings.push(diag);
}

function isMostlyText(input: Uint8Array): boolean {
  if (input.length === 0) return true;
  let printable = 0;
  const max = Math.min(input.length, 4096);
  for (let i = 0; i < max; i++) {
    const c = input[i]!;
    if (c === 9 || c === 10 || c === 13 || (c >= 32 && c <= 126)) printable++;
  }
  return printable / max > 0.85;
}

export function sniffBo2(input: Uint8Array): Bo2SniffResult {
  const prefix = Buffer.from(input.subarray(0, 32)).toString("utf8").trimStart();
  const loweredPrefix = prefix.toLowerCase();
  if (prefix.startsWith("{") || (prefix.startsWith("[") && !loweredPrefix.startsWith("[meta]") && !loweredPrefix.startsWith("[data]"))) {
    return { match: false, confidence: "high", reasonCodes: ["JSON_SIG"] };
  }
  if (input.length >= 2 && input[0] === 0x50 && input[1] === 0x4b) {
    return { match: false, confidence: "high", reasonCodes: ["ZIP_SIG"] };
  }
  const text = Buffer.from(input.subarray(0, Math.min(input.length, 65536))).toString("utf8").toLowerCase();
  const hasMeta = text.includes("[meta]");
  const hasData = text.includes("[data]");
  if (hasMeta && hasData) {
    return { match: true, confidence: "high", reasonCodes: ["META_AND_DATA_MARKERS"] };
  }
  if (hasData || hasMeta) {
    return { match: true, confidence: "medium", reasonCodes: ["PARTIAL_SECTION_MARKERS"] };
  }
  if (!isMostlyText(input)) {
    return { match: false, confidence: "high", reasonCodes: ["BINARY_NO_MARKERS"] };
  }
  return { match: false, confidence: "low", reasonCodes: ["NO_MARKERS"] };
}

function parseBlockToken(tokenRaw: string, registry: BlockRegistry): { blockKey: string; unknown: boolean; source: string } {
  const token = tokenRaw.trim();
  if (!token) {
    return { blockKey: "unknown:empty", unknown: true, source: "empty" };
  }

  const namespacedMatch = token.match(/^([a-z0-9_.-]+:[a-z0-9_./-]+)(?:\[.*\])?$/i);
  if (namespacedMatch) {
    const resolved = registry.resolve({ namespacedId: namespacedMatch[1] });
    return { blockKey: resolved.canonical, unknown: resolved.unknown, source: resolved.source };
  }

  const legacyMatch = token.match(/^(\d+)(?:[:.](\d+))?$/);
  if (legacyMatch) {
    const id = Number(legacyMatch[1]);
    const data = legacyMatch[2] ? Number(legacyMatch[2]) : 0;
    const resolved = registry.resolve({ legacyId: id, legacyData: data });
    return { blockKey: resolved.canonical, unknown: resolved.unknown, source: resolved.source };
  }

  const fallback = registry.resolve({ namespacedId: token.toLowerCase() });
  return { blockKey: fallback.canonical, unknown: fallback.unknown, source: fallback.source };
}

function parseStrict(input: Uint8Array, options: Bo2LoadOptions): Bo2LoadResult {
  const state: MutableParseState = {
    tags: {},
    voxels: [],
    warnings: [],
    errors: [],
    unknownSources: [],
    unknownCanonical: []
  };

  if (!isMostlyText(input)) {
    state.errors.push({ code: "BO2_TEXT_DECODE_FAILED", severity: "error", message: "Input is not parseable as text BO2." });
    return finalize("strict", state, options);
  }

  const text = Buffer.from(input).toString("utf8");
  const lines = text.split(/\r?\n/);
  let section: "meta" | "data" | "none" = "none";
  let sawMeta = false;
  let sawData = false;
  const coordSet = new Set<string>();

  for (let i = 0; i < lines.length; i++) {
    const lineNo = i + 1;
    const raw = lines[i] ?? "";
    const line = raw.trim();
    if (!line || line.startsWith("#") || line.startsWith("//")) continue;
    const sectionMatch = line.match(/^\[(meta|data)\]$/i);
    if (sectionMatch) {
      section = sectionMatch[1]!.toLowerCase() === "meta" ? "meta" : "data";
      if (section === "meta") sawMeta = true;
      if (section === "data") sawData = true;
      continue;
    }

    if (section === "meta") {
      const kv = line.match(/^([A-Za-z0-9_.-]+)\s*=\s*(.*)$/);
      if (!kv) {
        addDiagnostic(state, {
          code: "BO2_META_LINE_INVALID",
          severity: "error",
          message: `Invalid [META] line: "${line}"`,
          line: lineNo
        });
        continue;
      }
      const key = kv[1]!.trim().toLowerCase();
      const value = kv[2]!.trim();
      if (!KNOWN_META_KEYS.has(key)) {
        addDiagnostic(state, {
          code: "BO2_META_TAG_UNKNOWN",
          severity: "error",
          message: `Unknown metadata key "${key}" in strict mode.`,
          line: lineNo
        });
      }
      state.tags[key] = value;
      continue;
    }

    if (section === "data") {
      const data = line.match(/^(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*:\s*(.+)$/);
      if (!data) {
        addDiagnostic(state, {
          code: "BO2_BLOCK_RECORD_INVALID",
          severity: "error",
          message: `Invalid [DATA] record "${line}".`,
          line: lineNo
        });
        continue;
      }
      const x = Number(data[1]);
      const y = Number(data[2]);
      const z = Number(data[3]);
      const blockRaw = data[4]!.trim();
      const coordKey = `${x},${y},${z}`;
      if (coordSet.has(coordKey)) {
        addDiagnostic(state, {
          code: "BO2_DUPLICATE_VOXEL",
          severity: "error",
          message: `Duplicate voxel coordinate ${coordKey} in strict mode.`,
          line: lineNo
        });
        continue;
      }

      const resolved = parseBlockToken(blockRaw, options.registry);
      coordSet.add(coordKey);
      state.voxels.push({ x, y, z, blockKey: resolved.blockKey });
      if (resolved.unknown) {
        state.unknownSources.push(resolved.source);
        state.unknownCanonical.push(resolved.blockKey);
      }
      continue;
    }

    addDiagnostic(state, {
      code: "BO2_SECTION_MISSING",
      severity: "error",
      message: `Line outside section: "${line}"`,
      line: lineNo
    });
  }

  if (!sawMeta || !sawData) {
    addDiagnostic(state, {
      code: "BO2_SIG_MISMATCH",
      severity: "error",
      message: "BO2 must include [META] and [DATA] sections."
    });
  }

  return finalize("strict", state, options);
}

function parseSalvage(input: Uint8Array, options: Bo2LoadOptions): Bo2LoadResult {
  const state: MutableParseState = {
    tags: {},
    voxels: [],
    warnings: [],
    errors: [],
    unknownSources: [],
    unknownCanonical: []
  };

  const text = Buffer.from(input).toString("utf8");
  const lines = text.split(/\r?\n/);
  let section: "meta" | "data" | "none" = "none";

  for (let i = 0; i < lines.length; i++) {
    const lineNo = i + 1;
    const raw = lines[i] ?? "";
    const line = raw.trim();
    if (!line || line.startsWith("#") || line.startsWith("//")) continue;

    const sectionMatch = line.match(/^\[(meta|data)\]$/i);
    if (sectionMatch) {
      section = sectionMatch[1]!.toLowerCase() === "meta" ? "meta" : "data";
      continue;
    }

    if (section === "meta") {
      const kv = line.match(/^([A-Za-z0-9_.-]+)\s*=\s*(.*)$/);
      if (!kv) {
        addDiagnostic(state, {
          code: "BO2_META_TAG_UNKNOWN",
          severity: "warning",
          message: `Skipping malformed meta line "${line}".`,
          line: lineNo
        });
        continue;
      }
      state.tags[kv[1]!.toLowerCase()] = kv[2]!.trim();
      continue;
    }

    if (section === "data") {
      const data = line.match(/^(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*:\s*(.+)$/);
      if (!data) {
        addDiagnostic(state, {
          code: "BO2_BLOCK_RECORD_INVALID",
          severity: "warning",
          message: `Skipping invalid data record "${line}".`,
          line: lineNo
        });
        continue;
      }

      const x = Number(data[1]);
      const y = Number(data[2]);
      const z = Number(data[3]);
      const blockRaw = data[4]!.trim();
      const resolved = parseBlockToken(blockRaw, options.registry);
      state.voxels.push({ x, y, z, blockKey: resolved.blockKey });
      if (resolved.unknown) {
        state.unknownSources.push(resolved.source);
        state.unknownCanonical.push(resolved.blockKey);
      }
      continue;
    }

    addDiagnostic(state, {
      code: "BO2_SECTION_UNKNOWN_BYTES",
      severity: "warning",
      message: "Skipping bytes outside known section.",
      line: lineNo
    });
  }

  return finalize("salvage", state, options);
}

function finalize(parseMode: "strict" | "salvage", state: MutableParseState, options: Bo2LoadOptions): Bo2LoadResult {
  const unknownBlocks = buildUnknownBlockReport(state.unknownSources, state.unknownCanonical);
  let canonical: CanonicalObject | undefined;
  let valid = state.errors.length === 0 && state.voxels.length > 0;
  if (parseMode === "salvage" && state.voxels.length > 0) {
    try {
      canonical = canonicalize(state.voxels, {
        sourcePath: options.sourcePath,
        author: state.tags.author,
        description: state.tags.description
      });
      valid = true;
    } catch (error) {
      state.errors.push({
        code: "BO2_FATAL_PARSE_ERROR",
        severity: "error",
        message: `Canonicalization failed: ${(error as Error).message}`
      });
      valid = false;
    }
  } else if (parseMode === "strict" && valid) {
    try {
      canonical = canonicalize(state.voxels, {
        sourcePath: options.sourcePath,
        author: state.tags.author,
        description: state.tags.description
      });
    } catch (error) {
      state.errors.push({
        code: "BO2_FATAL_PARSE_ERROR",
        severity: "error",
        message: `Canonicalization failed: ${(error as Error).message}`
      });
      valid = false;
    }
  }

  return {
    format: "bo2",
    valid,
    parseMode,
    canonical,
    tags: state.tags,
    warnings: state.warnings,
    errors: state.errors,
    unknownBlocks
  };
}

export function loadBo2(input: Uint8Array, options: Bo2LoadOptions): Bo2LoadResult {
  const mode = options.mode ?? "strict+salvage";

  if (mode === "strict") {
    return parseStrict(input, options);
  }

  if (mode === "salvage") {
    return parseSalvage(input, options);
  }

  const strictResult = parseStrict(input, options);
  if (strictResult.valid) return strictResult;
  const salvageResult = parseSalvage(input, options);
  if (salvageResult.errors.length === 0 && strictResult.errors.length > 0) {
    salvageResult.warnings.unshift(
      ...strictResult.errors.map((e) => ({
        code: `STRICT_FALLBACK_${e.code}`,
        severity: "warning" as const,
        message: e.message,
        line: e.line
      }))
    );
  }
  return salvageResult;
}
