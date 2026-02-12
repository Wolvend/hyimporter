import { describe, expect, it } from "vitest";
import { BlockRegistry } from "@voxelviewer/block-registry";
import { loadHytale, sniffHytale } from "../src/index.js";

const registry = new BlockRegistry("mc_1_16_namespaced");

describe("sniffHytale", () => {
  it("identifies json prefabs", () => {
    const res = sniffHytale(Buffer.from("{\"blocks\":[]}", "utf8"));
    expect(res.match).toBe(true);
  });
});

describe("loadHytale", () => {
  it("loads palette-backed voxels", () => {
    const json = {
      palette: ["minecraft:stone", "minecraft:dirt"],
      blocks: [
        { x: 0, y: 0, z: 0, palette: 0 },
        { x: 1, y: 0, z: 0, palette: 1 }
      ],
      author: "fixture"
    };
    const out = loadHytale(Buffer.from(JSON.stringify(json), "utf8"), { registry });
    expect(out.valid).toBe(true);
    expect(out.canonical?.voxels.length).toBe(2);
    expect(out.metadata.author).toBe("fixture");
  });
});

