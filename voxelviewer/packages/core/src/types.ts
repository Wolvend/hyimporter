export type VoxelKey = string;

export interface Voxel {
  x: number;
  y: number;
  z: number;
  blockKey: VoxelKey;
}

export interface Bounds {
  minX: number;
  minY: number;
  minZ: number;
  maxX: number;
  maxY: number;
  maxZ: number;
  dx: number;
  dy: number;
  dz: number;
}

export interface CanonicalMetadata {
  originalOffset?: { x: number; y: number; z: number };
  sourcePath?: string;
  author?: string;
  description?: string;
  [key: string]: string | number | boolean | null | undefined | { x: number; y: number; z: number };
}

export interface CanonicalObject {
  voxels: Voxel[];
  boundsOriginal: Bounds;
  boundsNormalized: Bounds;
  metadata: CanonicalMetadata;
}

export interface CanonicalHashResult {
  sha256: string;
  canonicalBytes: Uint8Array;
}

export interface DuplicateResolutionResult {
  voxels: Voxel[];
  duplicateCount: number;
}
