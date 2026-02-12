import { mkdirSync } from "node:fs";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";
import type { IngestResult } from "./types.js";

export type SQLiteDatabase = DatabaseSync;

export interface ObjectRow {
  id: number;
  path: string;
  sha256: string;
  updated_at: string;
}

export function openDb(dbPath: string): SQLiteDatabase {
  mkdirSync(dirname(dbPath), { recursive: true });
  const db = new DatabaseSync(dbPath);
  // Keep DB file self-contained for compatibility with sql.js in Electron.
  db.exec("PRAGMA journal_mode = DELETE;");
  db.exec("PRAGMA synchronous = NORMAL;");
  ensureSchema(db);
  return db;
}

export function ensureSchema(db: SQLiteDatabase): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS objects (
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
      source_mtime_ms INTEGER,
      source_size INTEGER,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS assets (
      object_id INTEGER PRIMARY KEY,
      thumb_path TEXT NOT NULL,
      mesh_cache_path TEXT,
      ingest_report_path TEXT NOT NULL,
      FOREIGN KEY(object_id) REFERENCES objects(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_objects_format ON objects(format);
    CREATE INDEX IF NOT EXISTS idx_objects_valid ON objects(valid);
    CREATE INDEX IF NOT EXISTS idx_objects_sha256 ON objects(sha256);
  `);
}

export function getObjectByPath(db: SQLiteDatabase, path: string): ObjectRow | undefined {
  const stmt = db.prepare(`
    SELECT id, path, sha256, updated_at
    FROM objects
    WHERE path = ?
  `);
  return stmt.get(path) as ObjectRow | undefined;
}

export function upsertIngestResult(
  db: SQLiteDatabase,
  result: IngestResult,
  sourceMtimeMs: number,
  sourceSize: number
): number {
  const now = new Date().toISOString();
  const existing = db
    .prepare(`SELECT id, created_at FROM objects WHERE path = ?`)
    .get(result.path) as { id: number; created_at: string } | undefined;

  if (existing) {
    db.prepare(`
      UPDATE objects
      SET
        format = ?,
        sha256 = ?,
        valid = ?,
        parse_mode = ?,
        dx = ?,
        dy = ?,
        dz = ?,
        block_count = ?,
        unique_blocks = ?,
        unknown_blocks = ?,
        author = ?,
        description = ?,
        warnings_json = ?,
        errors_json = ?,
        source_mtime_ms = ?,
        source_size = ?,
        updated_at = ?
      WHERE id = ?
    `).run(
      result.format,
      result.sha256,
      result.valid ? 1 : 0,
      result.parse_mode,
      result.dx,
      result.dy,
      result.dz,
      result.block_count,
      result.unique_blocks,
      result.unknown_blocks,
      result.author,
      result.description,
      result.warnings_json,
      result.errors_json,
      sourceMtimeMs,
      sourceSize,
      now,
      existing.id
    );

    db.prepare(`
      INSERT INTO assets (object_id, thumb_path, mesh_cache_path, ingest_report_path)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(object_id) DO UPDATE SET
        thumb_path = excluded.thumb_path,
        mesh_cache_path = excluded.mesh_cache_path,
        ingest_report_path = excluded.ingest_report_path
    `).run(existing.id, result.thumb_path, result.mesh_cache_path, result.ingest_report_path);

    return existing.id;
  }

  const res = db.prepare(`
    INSERT INTO objects (
      path, format, sha256, valid, parse_mode, dx, dy, dz, block_count, unique_blocks,
      unknown_blocks, author, description, warnings_json, errors_json, source_mtime_ms,
      source_size, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    result.path,
    result.format,
    result.sha256,
    result.valid ? 1 : 0,
    result.parse_mode,
    result.dx,
    result.dy,
    result.dz,
    result.block_count,
    result.unique_blocks,
    result.unknown_blocks,
    result.author,
    result.description,
    result.warnings_json,
    result.errors_json,
    sourceMtimeMs,
    sourceSize,
    now,
    now
  ) as { lastInsertRowid?: number };

  const objectId = Number(res?.lastInsertRowid ?? 0);
  db.prepare(`
    INSERT INTO assets (object_id, thumb_path, mesh_cache_path, ingest_report_path)
    VALUES (?, ?, ?, ?)
  `).run(objectId, result.thumb_path, result.mesh_cache_path, result.ingest_report_path);

  return objectId;
}

export function listAllObjectPaths(db: SQLiteDatabase): string[] {
  const rows = db.prepare("SELECT path FROM objects").all() as Array<{ path: string }>;
  return rows.map((r) => r.path);
}

export function deleteByPaths(db: SQLiteDatabase, paths: string[]): number {
  if (paths.length === 0) return 0;
  const del = db.prepare("DELETE FROM objects WHERE path = ?");
  let deleted = 0;
  db.exec("BEGIN");
  try {
    for (const p of paths) {
      const info = del.run(p) as { changes?: number };
      deleted += Number(info?.changes ?? 0);
    }
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
  return deleted;
}
