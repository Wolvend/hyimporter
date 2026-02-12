import { mkdirSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";

export interface ScannedFile {
  path: string;
  size: number;
  mtimeMs: number;
}

export function ensureDir(path: string): void {
  mkdirSync(path, { recursive: true });
}

export function scanFolderRecursively(root: string): ScannedFile[] {
  const out: ScannedFile[] = [];
  const stack = [resolve(root)];
  while (stack.length > 0) {
    const current = stack.pop()!;
    const entries = readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      const full = resolve(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(full);
      } else if (entry.isFile()) {
        const stat = statSync(full);
        out.push({
          path: full,
          size: stat.size,
          mtimeMs: Math.floor(stat.mtimeMs)
        });
      }
    }
  }
  out.sort((a, b) => a.path.localeCompare(b.path));
  return out;
}

