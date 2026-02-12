import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { BlockRegistry } from "../packages/block-registry/src/index.js";
import { hashCanonicalObject } from "../packages/core/src/index.js";
import { loadBo2 } from "../packages/loaders-bo2/src/index.js";
import { loadHytale } from "../packages/loaders-hytale/src/index.js";
import { loadSchematic } from "../packages/loaders-schematic/src/index.js";

type ExpectedMap = Record<string, string | number>;

function listFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isFile())
    .map((e) => join(dir, e.name))
    .sort((a, b) => a.localeCompare(b));
}

function loadExpected(path: string): ExpectedMap {
  try {
    return JSON.parse(readFileSync(path, "utf8")) as ExpectedMap;
  } catch {
    return {};
  }
}

function saveExpected(path: string, data: ExpectedMap): void {
  writeFileSync(path, JSON.stringify(data, null, 2), "utf8");
}

function mutate(input: Uint8Array): Uint8Array {
  if (input.length === 0) return new Uint8Array([0]);
  const out = new Uint8Array(input);
  const idx = Math.floor(Math.random() * out.length);
  out[idx] = (out[idx]! + 17) & 0xff;
  if (Math.random() < 0.3) {
    return out.subarray(0, Math.max(1, Math.floor(out.length * 0.8)));
  }
  return out;
}

const update = process.argv.includes("--update");
const registry = new BlockRegistry("mc_1_12_legacy");

const root = resolve(".");
const bo2Dir = join(root, "fixtures/bo2/golden");
const hytaleDir = join(root, "fixtures/hytale/golden");
const schematicDir = join(root, "fixtures/schematic/golden");

const expectedHashPath = join(root, "fixtures/expected/hashes.json");
const expectedBoundsPath = join(root, "fixtures/expected/bounds.json");
const expectedCountsPath = join(root, "fixtures/expected/counts.json");

const expectedHashes = loadExpected(expectedHashPath);
const expectedBounds = loadExpected(expectedBoundsPath);
const expectedCounts = loadExpected(expectedCountsPath);

let failures = 0;
let baselinesAdded = 0;
for (const path of [...listFiles(bo2Dir), ...listFiles(hytaleDir), ...listFiles(schematicDir)]) {
  const rel = path.replace(`${root}\\`, "").replace(/\\/g, "/");
  const bytes = readFileSync(path);
  const out = path.endsWith(".bo2")
    ? loadBo2(bytes, { mode: "strict+salvage", registry, sourcePath: path })
    : path.endsWith(".schem") || path.endsWith(".schematic")
      ? loadSchematic(bytes, { mode: "strict+salvage", registry, sourcePath: path })
      : loadHytale(bytes, { registry, sourcePath: path });

  if (!out.valid || !out.canonical) {
    console.error(`[compat] ${rel} is invalid unexpectedly`);
    failures++;
    continue;
  }
  const hash = hashCanonicalObject(out.canonical).sha256;
  const bounds = `${out.canonical.boundsNormalized.dx}x${out.canonical.boundsNormalized.dy}x${out.canonical.boundsNormalized.dz}`;
  const count = out.canonical.voxels.length;

  if (update) {
    expectedHashes[rel] = hash;
    expectedBounds[rel] = bounds;
    expectedCounts[rel] = count;
  } else {
    if (expectedHashes[rel] === undefined) {
      expectedHashes[rel] = hash;
      baselinesAdded++;
    } else if (expectedHashes[rel] !== hash) {
      console.error(`[compat] hash mismatch ${rel}: expected=${expectedHashes[rel]} actual=${hash}`);
      failures++;
    }
    if (expectedBounds[rel] === undefined) {
      expectedBounds[rel] = bounds;
      baselinesAdded++;
    } else if (expectedBounds[rel] !== bounds) {
      console.error(`[compat] bounds mismatch ${rel}: expected=${expectedBounds[rel]} actual=${bounds}`);
      failures++;
    }
    if (expectedCounts[rel] === undefined) {
      expectedCounts[rel] = count;
      baselinesAdded++;
    } else if (Number(expectedCounts[rel]) !== count) {
      console.error(`[compat] count mismatch ${rel}: expected=${expectedCounts[rel]} actual=${count}`);
      failures++;
    }
  }
}

if (update) {
  saveExpected(expectedHashPath, expectedHashes);
  saveExpected(expectedBoundsPath, expectedBounds);
  saveExpected(expectedCountsPath, expectedCounts);
  console.log("[compat] expected snapshots updated.");
} else if (baselinesAdded > 0) {
  saveExpected(expectedHashPath, expectedHashes);
  saveExpected(expectedBoundsPath, expectedBounds);
  saveExpected(expectedCountsPath, expectedCounts);
  console.log(`[compat] bootstrapped ${baselinesAdded} missing baseline entries.`);
}

for (let i = 0; i < 200; i++) {
  const random = new Uint8Array(128);
  for (let j = 0; j < random.length; j++) random[j] = Math.floor(Math.random() * 256);
  try {
    loadBo2(random, { mode: "strict+salvage", registry, sourcePath: `fuzz:${i}` });
    loadHytale(random, { registry, sourcePath: `fuzz:${i}` });
  } catch (error) {
    console.error(`[fuzz] unexpected crash on random bytes: ${(error as Error).message}`);
    failures++;
    break;
  }
}

for (const path of listFiles(bo2Dir)) {
  const bytes = readFileSync(path);
  for (let i = 0; i < 25; i++) {
    const mutated = mutate(bytes);
    try {
      loadBo2(mutated, { mode: "strict+salvage", registry, sourcePath: `${path}#mut${i}` });
    } catch (error) {
      console.error(`[fuzz] mutation crash ${path}: ${(error as Error).message}`);
      failures++;
      break;
    }
  }
}

if (failures > 0) {
  console.error(`[compat] failures=${failures}`);
  process.exit(1);
}

console.log("[compat] OK");
