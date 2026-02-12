# Core Canonical Voxel Model

## Coordinate and Unit Conventions

- Unit is one block.
- Coordinates are integer `x, y, z`.
- `y` is up.
- Internal orientation is right-handed with deterministic axis naming in all packages.

## Canonical Types

```ts
type VoxelKey = string; // e.g. "minecraft:oak_planks" or "legacy:5:2"

interface Voxel {
  x: number;
  y: number;
  z: number;
  blockKey: VoxelKey;
}

interface Bounds {
  minX: number; minY: number; minZ: number;
  maxX: number; maxY: number; maxZ: number;
  dx: number; dy: number; dz: number;
}

interface CanonicalObject {
  voxels: Voxel[];
  boundsOriginal: Bounds;
  boundsNormalized: Bounds;
  originalOffset: { x: number; y: number; z: number };
  metadata: Record<string, string | number | boolean | null>;
}
```

## Normalization

- Compute original bounds from parsed voxels.
- Compute offset `(minX, minY, minZ)`.
- Produce normalized voxels by subtracting offset.
- Normalized bounds always start at `(0,0,0)`.
- Preserve original offset and original bounds in metadata fields.

## Deterministic Sorting

- Voxel order is **z-major, then y, then x, then blockKey**.
- Comparator:
  1. `z`
  2. `y`
  3. `x`
  4. `blockKey` lexical

## Duplicate Conflict Rule

- When multiple records target the same `(x,y,z)`:
- Deterministic policy: **last valid record in source order wins**.
- Strict mode marks duplicate as error and invalidates parse (unless format explicitly allows overwrite).
- Salvage mode records warning and applies last-write-wins.

## Canonical Byte Encoding for Hashing

- Hash algorithm: SHA-256.
- Byte stream format (versioned):
  1. Magic: `VV01`
  2. Endianness marker: little-endian
  3. Object metadata subset in sorted key order (UTF-8, length-prefixed)
  4. Voxel count (u32)
  5. For each voxel in canonical sorted order:
     - `x` i32
     - `y` i32
     - `z` i32
     - `blockKey` UTF-8 length-prefixed

- Hash is computed over these bytes only.
- Renderer and DB cache keys append tool/version salts separately.

## Invariants

- No voxel outside `boundsNormalized`.
- `boundsNormalized.min*` are always `0`.
- Canonicalization of same input bytes yields same hash and same sorted voxel stream.

