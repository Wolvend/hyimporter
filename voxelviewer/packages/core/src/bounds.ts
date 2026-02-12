import type { Bounds, Voxel } from "./types.js";

export function assertIntegerCoords(voxels: Voxel[]): void {
  for (const v of voxels) {
    if (!Number.isInteger(v.x) || !Number.isInteger(v.y) || !Number.isInteger(v.z)) {
      throw new Error(`Non-integer voxel coordinate detected: ${JSON.stringify(v)}`);
    }
  }
}

export function computeBounds(voxels: Voxel[]): Bounds {
  if (voxels.length === 0) {
    return {
      minX: 0,
      minY: 0,
      minZ: 0,
      maxX: -1,
      maxY: -1,
      maxZ: -1,
      dx: 0,
      dy: 0,
      dz: 0
    };
  }

  let minX = voxels[0]!.x;
  let minY = voxels[0]!.y;
  let minZ = voxels[0]!.z;
  let maxX = voxels[0]!.x;
  let maxY = voxels[0]!.y;
  let maxZ = voxels[0]!.z;

  for (let i = 1; i < voxels.length; i++) {
    const v = voxels[i]!;
    if (v.x < minX) minX = v.x;
    if (v.y < minY) minY = v.y;
    if (v.z < minZ) minZ = v.z;
    if (v.x > maxX) maxX = v.x;
    if (v.y > maxY) maxY = v.y;
    if (v.z > maxZ) maxZ = v.z;
  }

  return {
    minX,
    minY,
    minZ,
    maxX,
    maxY,
    maxZ,
    dx: maxX - minX + 1,
    dy: maxY - minY + 1,
    dz: maxZ - minZ + 1
  };
}

export function voxelCoordKey(x: number, y: number, z: number): string {
  return `${x},${y},${z}`;
}

