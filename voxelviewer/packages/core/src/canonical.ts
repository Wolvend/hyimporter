import type { CanonicalMetadata, CanonicalObject, DuplicateResolutionResult, Voxel } from "./types.js";
import { assertIntegerCoords, computeBounds, voxelCoordKey } from "./bounds.js";

export type DuplicateStrategy = "last-write-wins" | "first-write-wins";

export function resolveDuplicates(
  voxels: Voxel[],
  strategy: DuplicateStrategy = "last-write-wins"
): DuplicateResolutionResult {
  if (voxels.length === 0) {
    return { voxels: [], duplicateCount: 0 };
  }

  const seen = new Map<string, Voxel>();
  let duplicateCount = 0;

  if (strategy === "first-write-wins") {
    for (const voxel of voxels) {
      const key = voxelCoordKey(voxel.x, voxel.y, voxel.z);
      if (seen.has(key)) {
        duplicateCount++;
        continue;
      }
      seen.set(key, voxel);
    }
  } else {
    for (const voxel of voxels) {
      const key = voxelCoordKey(voxel.x, voxel.y, voxel.z);
      if (seen.has(key)) {
        duplicateCount++;
      }
      seen.set(key, voxel);
    }
  }

  return { voxels: [...seen.values()], duplicateCount };
}

export function canonicalVoxelCompare(a: Voxel, b: Voxel): number {
  // z-major, then y, then x, then blockKey
  if (a.z !== b.z) return a.z - b.z;
  if (a.y !== b.y) return a.y - b.y;
  if (a.x !== b.x) return a.x - b.x;
  if (a.blockKey < b.blockKey) return -1;
  if (a.blockKey > b.blockKey) return 1;
  return 0;
}

export function sortCanonicalVoxels(voxels: Voxel[]): Voxel[] {
  return [...voxels].sort(canonicalVoxelCompare);
}

export function normalizeVoxels(voxels: Voxel[]): { normalized: Voxel[]; offset: { x: number; y: number; z: number } } {
  const originalBounds = computeBounds(voxels);
  const offset = {
    x: originalBounds.minX,
    y: originalBounds.minY,
    z: originalBounds.minZ
  };

  const normalized = voxels.map((v) => ({
    x: v.x - offset.x,
    y: v.y - offset.y,
    z: v.z - offset.z,
    blockKey: v.blockKey
  }));

  return { normalized, offset };
}

export function canonicalize(
  voxelsInput: Voxel[],
  metadata: CanonicalMetadata = {},
  duplicateStrategy: DuplicateStrategy = "last-write-wins"
): CanonicalObject {
  assertIntegerCoords(voxelsInput);
  const deduped = resolveDuplicates(voxelsInput, duplicateStrategy);
  const boundsOriginal = computeBounds(deduped.voxels);
  const { normalized, offset } = normalizeVoxels(deduped.voxels);
  const sortedNormalized = sortCanonicalVoxels(normalized);
  const boundsNormalized = computeBounds(sortedNormalized);

  if (sortedNormalized.length > 0) {
    if (boundsNormalized.minX !== 0 || boundsNormalized.minY !== 0 || boundsNormalized.minZ !== 0) {
      throw new Error("Normalization invariant failed: min bounds must be (0,0,0)");
    }
  }

  return {
    voxels: sortedNormalized,
    boundsOriginal,
    boundsNormalized,
    metadata: {
      ...metadata,
      originalOffset: offset
    }
  };
}

