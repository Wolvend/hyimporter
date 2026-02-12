import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { extname, resolve } from "node:path";
import { BlockRegistry, readOverridesFromYaml } from "@voxelviewer/block-registry";
import { hashCanonicalObject } from "@voxelviewer/core";
import { loadBo2, sniffBo2 } from "@voxelviewer/loaders-bo2";
import { loadHytale, sniffHytale } from "@voxelviewer/loaders-hytale";
import { loadSchematic, sniffSchematic } from "@voxelviewer/loaders-schematic";
import {
  greedyMesh,
  meshCacheKey,
  renderErrorThumbnailPng,
  renderThumbnailPng,
  thumbCacheKey
} from "@voxelviewer/renderer";
import type { IngestResult, IngestTask, IngestionReport, ObjectFormat, ParseModeUsed } from "./types.js";
import { ensureDir } from "./fs.js";

function sha256(input: Uint8Array): string {
  return createHash("sha256").update(input).digest("hex");
}

function shortPathHash(path: string): string {
  return createHash("sha1").update(path).digest("hex").slice(0, 12);
}

function detectFormat(bytes: Uint8Array, path: string): ObjectFormat {
  const ext = extname(path).toLowerCase();
  const bo2 = sniffBo2(bytes);
  const hytale = sniffHytale(bytes);
  const schematic = sniffSchematic(bytes, path);

  if (bo2.match && bo2.confidence === "high") return "bo2";
  if (schematic.match && schematic.confidence === "high") return "schematic";
  if (hytale.match && hytale.confidence === "high") return "hytale";
  if (ext === ".bo2") return "bo2";
  if (ext === ".schem" || ext === ".schematic" || ext === ".nbt") return "schematic";
  if (ext === ".json" || ext.endsWith(".prefab")) return "hytale";
  if (schematic.match && !bo2.match && !hytale.match) return "schematic";
  if (bo2.match && !hytale.match) return "bo2";
  if (hytale.match && !bo2.match) return "hytale";
  return "unknown";
}

export function ingestFile(task: IngestTask): IngestResult {
  const t0 = Date.now();
  ensureDir(task.thumbsDir);
  ensureDir(task.cacheDir);
  ensureDir(task.reportsDir);

  const timing: IngestionReport["timingMs"] = {
    sniff: 0,
    parse: 0,
    canonicalize: 0,
    mesh: 0,
    thumbnail: 0,
    dbWrite: 0,
    total: 0
  };

  const bytes = readFileSync(task.path);
  const rawSha = sha256(bytes);

  const sniffStart = Date.now();
  const format = detectFormat(bytes, task.path);
  timing.sniff = Date.now() - sniffStart;

  const overrides = task.overridesPath ? readOverridesFromYaml(task.overridesPath) : undefined;
  const registry = new BlockRegistry(task.profile, overrides);

  let parseMode: ParseModeUsed = "none";
  let valid = false;
  let warnings: unknown[] = [];
  let errors: unknown[] = [];
  let unknownBlocks: unknown = { totalUnknown: 0, entries: [] };
  let author: string | null = null;
  let description: string | null = null;
  let dx = 0;
  let dy = 0;
  let dz = 0;
  let blockCount = 0;
  let uniqueBlocks = 0;
  let canonicalSha = rawSha;
  let meshPath: string | null = null;
  let thumbPath = resolve(task.thumbsDir, `error-${rawSha.slice(0, 16)}.png`);

  const parseStart = Date.now();
  if (format === "bo2") {
    const bo2 = loadBo2(bytes, {
      mode: task.mode,
      registry,
      sourcePath: task.path
    });
    parseMode = bo2.parseMode;
    valid = bo2.valid;
    warnings = bo2.warnings;
    errors = bo2.errors;
    unknownBlocks = bo2.unknownBlocks;
    author = bo2.tags.author ?? null;
    description = bo2.tags.description ?? null;

    if (bo2.canonical) {
      const canStart = Date.now();
      const hashRes = hashCanonicalObject(bo2.canonical);
      timing.canonicalize = Date.now() - canStart;
      canonicalSha = hashRes.sha256;
      dx = bo2.canonical.boundsNormalized.dx;
      dy = bo2.canonical.boundsNormalized.dy;
      dz = bo2.canonical.boundsNormalized.dz;
      blockCount = bo2.canonical.voxels.length;
      uniqueBlocks = new Set(bo2.canonical.voxels.map((v) => v.blockKey)).size;

      const meshStart = Date.now();
      const meshKey = meshCacheKey(canonicalSha, "renderer_v1", registry.getProfileName());
      meshPath = resolve(task.cacheDir, `${meshKey}.mesh.json`);
      if (!existsSync(meshPath)) {
        const quads = greedyMesh(bo2.canonical);
        writeFileSync(meshPath, JSON.stringify({ canonicalSha, quads }));
      }
      timing.mesh = Date.now() - meshStart;

      const thumbStart = Date.now();
      const thumbKey = thumbCacheKey(meshKey, `size=${task.thumbSize}`, "renderer_v1");
      thumbPath = resolve(task.thumbsDir, `${thumbKey}.png`);
      if (!existsSync(thumbPath)) {
        const png = renderThumbnailPng(bo2.canonical, { width: task.thumbSize, height: task.thumbSize });
        writeFileSync(thumbPath, png);
      }
      if (task.debugProjections) {
        const base = thumbPath.replace(/\.png$/i, "");
        const front = renderThumbnailPng(bo2.canonical, {
          width: task.thumbSize,
          height: task.thumbSize,
          yawDeg: 0,
          pitchDeg: 0
        });
        const top = renderThumbnailPng(bo2.canonical, {
          width: task.thumbSize,
          height: task.thumbSize,
          yawDeg: 0,
          pitchDeg: 89
        });
        const side = renderThumbnailPng(bo2.canonical, {
          width: task.thumbSize,
          height: task.thumbSize,
          yawDeg: 90,
          pitchDeg: 0
        });
        writeFileSync(`${base}-front.png`, front);
        writeFileSync(`${base}-top.png`, top);
        writeFileSync(`${base}-side.png`, side);
      }
      timing.thumbnail = Date.now() - thumbStart;
    }
  } else if (format === "hytale") {
    const hytale = loadHytale(bytes, {
      registry,
      sourcePath: task.path
    });
    parseMode = hytale.valid ? "salvage" : "none";
    valid = hytale.valid;
    warnings = hytale.warnings;
    errors = hytale.errors;
    unknownBlocks = hytale.unknownBlocks;
    author = hytale.metadata.author ?? null;
    description = hytale.metadata.description ?? null;

    if (hytale.canonical) {
      const canStart = Date.now();
      const hashRes = hashCanonicalObject(hytale.canonical);
      timing.canonicalize = Date.now() - canStart;
      canonicalSha = hashRes.sha256;
      dx = hytale.canonical.boundsNormalized.dx;
      dy = hytale.canonical.boundsNormalized.dy;
      dz = hytale.canonical.boundsNormalized.dz;
      blockCount = hytale.canonical.voxels.length;
      uniqueBlocks = new Set(hytale.canonical.voxels.map((v) => v.blockKey)).size;

      const meshStart = Date.now();
      const meshKey = meshCacheKey(canonicalSha, "renderer_v1", registry.getProfileName());
      meshPath = resolve(task.cacheDir, `${meshKey}.mesh.json`);
      if (!existsSync(meshPath)) {
        const quads = greedyMesh(hytale.canonical);
        writeFileSync(meshPath, JSON.stringify({ canonicalSha, quads }));
      }
      timing.mesh = Date.now() - meshStart;

      const thumbStart = Date.now();
      const thumbKey = thumbCacheKey(meshKey, `size=${task.thumbSize}`, "renderer_v1");
      thumbPath = resolve(task.thumbsDir, `${thumbKey}.png`);
      if (!existsSync(thumbPath)) {
        const png = renderThumbnailPng(hytale.canonical, { width: task.thumbSize, height: task.thumbSize });
        writeFileSync(thumbPath, png);
      }
      if (task.debugProjections) {
        const base = thumbPath.replace(/\.png$/i, "");
        const front = renderThumbnailPng(hytale.canonical, {
          width: task.thumbSize,
          height: task.thumbSize,
          yawDeg: 0,
          pitchDeg: 0
        });
        const top = renderThumbnailPng(hytale.canonical, {
          width: task.thumbSize,
          height: task.thumbSize,
          yawDeg: 0,
          pitchDeg: 89
        });
        const side = renderThumbnailPng(hytale.canonical, {
          width: task.thumbSize,
          height: task.thumbSize,
          yawDeg: 90,
          pitchDeg: 0
        });
        writeFileSync(`${base}-front.png`, front);
        writeFileSync(`${base}-top.png`, top);
        writeFileSync(`${base}-side.png`, side);
      }
      timing.thumbnail = Date.now() - thumbStart;
    }
  } else if (format === "schematic") {
    const schematic = loadSchematic(bytes, {
      mode: task.mode,
      registry,
      sourcePath: task.path
    });
    parseMode = schematic.parseMode;
    valid = schematic.valid;
    warnings = schematic.warnings;
    errors = schematic.errors;
    unknownBlocks = schematic.unknownBlocks;
    author = schematic.metadata.author ?? null;
    description = schematic.metadata.description ?? null;

    if (schematic.canonical) {
      const canStart = Date.now();
      const hashRes = hashCanonicalObject(schematic.canonical);
      timing.canonicalize = Date.now() - canStart;
      canonicalSha = hashRes.sha256;
      dx = schematic.canonical.boundsNormalized.dx;
      dy = schematic.canonical.boundsNormalized.dy;
      dz = schematic.canonical.boundsNormalized.dz;
      blockCount = schematic.canonical.voxels.length;
      uniqueBlocks = new Set(schematic.canonical.voxels.map((v) => v.blockKey)).size;

      const meshStart = Date.now();
      const meshKey = meshCacheKey(canonicalSha, "renderer_v1", registry.getProfileName());
      meshPath = resolve(task.cacheDir, `${meshKey}.mesh.json`);
      if (!existsSync(meshPath)) {
        const quads = greedyMesh(schematic.canonical);
        writeFileSync(meshPath, JSON.stringify({ canonicalSha, quads }));
      }
      timing.mesh = Date.now() - meshStart;

      const thumbStart = Date.now();
      const thumbKey = thumbCacheKey(meshKey, `size=${task.thumbSize}`, "renderer_v1");
      thumbPath = resolve(task.thumbsDir, `${thumbKey}.png`);
      if (!existsSync(thumbPath)) {
        const png = renderThumbnailPng(schematic.canonical, { width: task.thumbSize, height: task.thumbSize });
        writeFileSync(thumbPath, png);
      }
      if (task.debugProjections) {
        const base = thumbPath.replace(/\.png$/i, "");
        const front = renderThumbnailPng(schematic.canonical, {
          width: task.thumbSize,
          height: task.thumbSize,
          yawDeg: 0,
          pitchDeg: 0
        });
        const top = renderThumbnailPng(schematic.canonical, {
          width: task.thumbSize,
          height: task.thumbSize,
          yawDeg: 0,
          pitchDeg: 89
        });
        const side = renderThumbnailPng(schematic.canonical, {
          width: task.thumbSize,
          height: task.thumbSize,
          yawDeg: 90,
          pitchDeg: 0
        });
        writeFileSync(`${base}-front.png`, front);
        writeFileSync(`${base}-top.png`, top);
        writeFileSync(`${base}-side.png`, side);
      }
      timing.thumbnail = Date.now() - thumbStart;
    }
  } else {
    parseMode = "none";
    valid = false;
    errors = [{ code: "FORMAT_UNKNOWN", severity: "error", message: "Unsupported or misnamed file format." }];
  }
  timing.parse = Date.now() - parseStart;

  if (!valid || !existsSync(thumbPath)) {
    const errorCode =
      (errors[0] && typeof errors[0] === "object" && "code" in (errors[0] as Record<string, unknown>)
        ? String((errors[0] as Record<string, unknown>).code)
        : "INVALID_OBJECT");
    if (!existsSync(thumbPath)) {
      const errorPng = renderErrorThumbnailPng(errorCode, { width: task.thumbSize, height: task.thumbSize });
      writeFileSync(thumbPath, errorPng);
    }
  }

  const report: IngestionReport = {
    path: task.path,
    formatDetected: format,
    parseMode,
    valid,
    sha256: canonicalSha,
    warnings,
    errors,
    unknownBlocks,
    stats: {
      blockCount,
      uniqueBlocks,
      bounds: { dx, dy, dz }
    },
    timingMs: {
      ...timing,
      total: Date.now() - t0
    },
    memoryEstimateBytes: blockCount * 40,
    toolVersions: {
      indexer: "0.1.0",
      renderer: "0.1.0",
      node: process.version
    }
  };

  const reportPath = resolve(task.reportsDir, `${rawSha}-${shortPathHash(task.path)}.json`);
  writeFileSync(reportPath, JSON.stringify(report, null, 2), "utf8");

  const unknownCount =
    unknownBlocks && typeof unknownBlocks === "object" && "totalUnknown" in (unknownBlocks as Record<string, unknown>)
      ? Number((unknownBlocks as { totalUnknown?: number }).totalUnknown ?? 0)
      : 0;

  return {
    path: task.path,
    format,
    sha256: canonicalSha,
    valid,
    parse_mode: parseMode,
    dx,
    dy,
    dz,
    block_count: blockCount,
    unique_blocks: uniqueBlocks,
    unknown_blocks: unknownCount,
    author,
    description,
    warnings_json: JSON.stringify(warnings),
    errors_json: JSON.stringify(errors),
    thumb_path: thumbPath,
    mesh_cache_path: meshPath,
    ingest_report_path: reportPath
  };
}

export function createCachedSkipResult(
  path: string,
  existing: {
    format: ObjectFormat;
    sha256: string;
    valid: number;
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
  },
  reportsDir: string
): IngestResult {
  const reportPath = resolve(reportsDir, `${shortPathHash(path)}-cached.json`);
  const report: IngestionReport = {
    path,
    formatDetected: existing.format,
    parseMode: existing.parse_mode,
    valid: !!existing.valid,
    sha256: existing.sha256,
    warnings: [],
    errors: [],
    unknownBlocks: { totalUnknown: existing.unknown_blocks, entries: [] },
    stats: {
      blockCount: existing.block_count,
      uniqueBlocks: existing.unique_blocks,
      bounds: { dx: existing.dx, dy: existing.dy, dz: existing.dz }
    },
    timingMs: {
      sniff: 0,
      parse: 0,
      canonicalize: 0,
      mesh: 0,
      thumbnail: 0,
      dbWrite: 0,
      total: 0
    },
    memoryEstimateBytes: 0,
    toolVersions: { indexer: "0.1.0", cache: "hit" }
  };
  writeFileSync(reportPath, JSON.stringify(report, null, 2), "utf8");

  return {
    path,
    format: existing.format,
    sha256: existing.sha256,
    valid: !!existing.valid,
    parse_mode: existing.parse_mode,
    dx: existing.dx,
    dy: existing.dy,
    dz: existing.dz,
    block_count: existing.block_count,
    unique_blocks: existing.unique_blocks,
    unknown_blocks: existing.unknown_blocks,
    author: existing.author,
    description: existing.description,
    warnings_json: existing.warnings_json,
    errors_json: existing.errors_json,
    thumb_path: existing.thumb_path,
    mesh_cache_path: existing.mesh_cache_path,
    ingest_report_path: reportPath
  };
}
