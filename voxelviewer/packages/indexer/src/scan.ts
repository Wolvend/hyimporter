import { cpus } from "node:os";
import { resolve } from "node:path";
import { openDb, deleteByPaths, listAllObjectPaths, upsertIngestResult } from "./db.js";
import { ensureDir, scanFolderRecursively } from "./fs.js";
import { createCachedSkipResult, ingestFile } from "./ingest.js";
import type { IngestResult, IngestTask, ObjectFormat, ParseModeUsed } from "./types.js";
import { IngestWorkerPool } from "./worker-pool.js";

export interface ScanOptions {
  folder: string;
  outDb: string;
  thumbsDir: string;
  cacheDir: string;
  reportsDir: string;
  mode: "strict" | "salvage" | "strict+salvage";
  workers: number;
  profile: "mc_1_12_legacy" | "mc_1_16_namespaced";
  overridesPath?: string;
  thumbSize: number;
  debugProjections?: boolean;
}

interface ExistingRecord {
  id: number;
  path: string;
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
  source_mtime_ms: number | null;
  source_size: number | null;
  thumb_path: string;
  mesh_cache_path: string | null;
  ingest_report_path: string;
}

function getExisting(db: ReturnType<typeof openDb>, path: string): ExistingRecord | undefined {
  return db
    .prepare(`
      SELECT
        o.id, o.path, o.format, o.sha256, o.valid, o.parse_mode, o.dx, o.dy, o.dz, o.block_count,
        o.unique_blocks, o.unknown_blocks, o.author, o.description, o.warnings_json, o.errors_json,
        o.source_mtime_ms, o.source_size,
        a.thumb_path, a.mesh_cache_path, a.ingest_report_path
      FROM objects o
      LEFT JOIN assets a ON a.object_id = o.id
      WHERE o.path = ?
    `)
    .get(path) as ExistingRecord | undefined;
}

export interface ScanSummary {
  scanned: number;
  processed: number;
  cached: number;
  removed: number;
  invalid: number;
}

export async function runScan(options: ScanOptions): Promise<ScanSummary> {
  ensureDir(resolve(options.thumbsDir));
  ensureDir(resolve(options.cacheDir));
  ensureDir(resolve(options.reportsDir));
  const db = openDb(resolve(options.outDb));

  const files = scanFolderRecursively(resolve(options.folder));
  const filePaths = new Set(files.map((f) => f.path));
  const allDbPaths = listAllObjectPaths(db);
  const removedPaths = allDbPaths.filter((p) => !filePaths.has(p));
  const removed = deleteByPaths(db, removedPaths);

  const tasks: IngestTask[] = [];
  const results: Array<{ result: IngestResult; mtimeMs: number; size: number }> = [];
  let cached = 0;

  for (const file of files) {
    const existing = getExisting(db, file.path);
    if (
      existing &&
      existing.source_mtime_ms === file.mtimeMs &&
      existing.source_size === file.size
    ) {
      const result = createCachedSkipResult(file.path, existing, resolve(options.reportsDir));
      results.push({ result, mtimeMs: file.mtimeMs, size: file.size });
      cached++;
      continue;
    }

    tasks.push({
      path: file.path,
      mode: options.mode,
      profile: options.profile,
      overridesPath: options.overridesPath,
      thumbsDir: resolve(options.thumbsDir),
      cacheDir: resolve(options.cacheDir),
      reportsDir: resolve(options.reportsDir),
      thumbSize: options.thumbSize,
      debugProjections: options.debugProjections
    });
  }

  const workerCount =
    Number.isFinite(options.workers) && options.workers > 0
      ? options.workers
      : Math.max(1, cpus().length - 1);

  if (tasks.length > 0) {
    if (workerCount <= 1) {
      for (const task of tasks) {
        const idx = files.findIndex((f) => f.path === task.path);
        const meta = files[idx]!;
        const result = ingestFile(task);
        results.push({ result, mtimeMs: meta.mtimeMs, size: meta.size });
      }
    } else {
      let pool: IngestWorkerPool | null = null;
      try {
        pool = new IngestWorkerPool(workerCount);
        const byPath = new Map(files.map((f) => [f.path, f]));
        const outputs = await Promise.all(
          tasks.map(async (task) => {
            try {
              const result = await pool!.run(task);
              const meta = byPath.get(task.path);
              return { result, mtimeMs: meta?.mtimeMs ?? 0, size: meta?.size ?? 0 };
            } catch {
              const fallback = ingestFile(task);
              const meta = byPath.get(task.path);
              return { result: fallback, mtimeMs: meta?.mtimeMs ?? 0, size: meta?.size ?? 0 };
            }
          })
        );
        results.push(...outputs);
      } catch {
        const byPath = new Map(files.map((f) => [f.path, f]));
        for (const task of tasks) {
          const fallback = ingestFile(task);
          const meta = byPath.get(task.path);
          results.push({ result: fallback, mtimeMs: meta?.mtimeMs ?? 0, size: meta?.size ?? 0 });
        }
      } finally {
        if (pool) {
          await pool.close();
        }
      }
    }
  }

  db.exec("BEGIN");
  try {
    for (const item of results) {
      upsertIngestResult(db, item.result, item.mtimeMs, item.size);
    }
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }

  const invalid = results.filter((r) => !r.result.valid).length;
  const summary: ScanSummary = {
    scanned: files.length,
    processed: tasks.length,
    cached,
    removed,
    invalid
  };
  db.close();
  return summary;
}
