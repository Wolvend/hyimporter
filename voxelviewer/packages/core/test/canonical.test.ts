import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { canonicalize, hashCanonicalObject, type Voxel } from "../src/index.js";

function toVoxel(x: number, y: number, z: number, blockKey = "minecraft:stone"): Voxel {
  return { x, y, z, blockKey };
}

describe("canonicalize", () => {
  it("normalizes min corner to zero", () => {
    const result = canonicalize([toVoxel(2, 4, 6), toVoxel(10, 9, 7)]);
    expect(result.boundsNormalized.minX).toBe(0);
    expect(result.boundsNormalized.minY).toBe(0);
    expect(result.boundsNormalized.minZ).toBe(0);
  });

  it("is deterministic for hash and voxel order", () => {
    const input = [toVoxel(1, 2, 3), toVoxel(0, 0, 0, "minecraft:dirt"), toVoxel(2, 1, 0, "minecraft:oak_log")];
    const a = canonicalize(input);
    const b = canonicalize([...input].reverse());
    expect(hashCanonicalObject(a).sha256).toBe(hashCanonicalObject(b).sha256);
    expect(a.voxels).toEqual(b.voxels);
  });

  it("property: no voxel outside normalized bounds", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            x: fc.integer({ min: -16, max: 16 }),
            y: fc.integer({ min: -16, max: 16 }),
            z: fc.integer({ min: -16, max: 16 })
          }),
          { minLength: 1, maxLength: 120 }
        ),
        (coords) => {
          const voxels = coords.map((c, idx) => toVoxel(c.x, c.y, c.z, idx % 2 === 0 ? "minecraft:stone" : "minecraft:dirt"));
          const out = canonicalize(voxels);
          for (const v of out.voxels) {
            if (v.x < 0 || v.y < 0 || v.z < 0) return false;
            if (v.x >= out.boundsNormalized.dx || v.y >= out.boundsNormalized.dy || v.z >= out.boundsNormalized.dz) {
              return false;
            }
          }
          return true;
        }
      )
    );
  });
});
