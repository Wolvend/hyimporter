import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import { canonicalize } from "@voxelviewer/core";
import { greedyMesh, renderThumbnailPng } from "../src/index.js";

describe("renderer", () => {
  it("greedy mesh emits quads for simple cube", () => {
    const canonical = canonicalize([{ x: 0, y: 0, z: 0, blockKey: "minecraft:stone" }]);
    const quads = greedyMesh(canonical);
    expect(quads.length).toBe(6);
  });

  it("thumbnail rendering is deterministic for same object", () => {
    const canonical = canonicalize([
      { x: 0, y: 0, z: 0, blockKey: "minecraft:stone" },
      { x: 1, y: 0, z: 0, blockKey: "minecraft:dirt" }
    ]);
    const a = renderThumbnailPng(canonical);
    const b = renderThumbnailPng(canonical);
    const ha = createHash("sha256").update(a).digest("hex");
    const hb = createHash("sha256").update(b).digest("hex");
    expect(ha).toBe(hb);
  });
});

