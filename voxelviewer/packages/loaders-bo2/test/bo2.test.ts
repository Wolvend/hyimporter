import { describe, expect, it } from "vitest";
import { BlockRegistry } from "@voxelviewer/block-registry";
import { loadBo2, sniffBo2 } from "../src/index.js";

const registry = new BlockRegistry("mc_1_12_legacy");

describe("sniffBo2", () => {
  it("detects valid markers", () => {
    const buf = Buffer.from("[META]\nauthor=test\n[DATA]\n0,0,0:1.0\n", "utf8");
    const result = sniffBo2(buf);
    expect(result.match).toBe(true);
    expect(result.confidence).toBe("high");
  });
});

describe("loadBo2", () => {
  it("parses strict valid input", () => {
    const input = Buffer.from("[META]\nauthor=test\n[DATA]\n0,0,0:1.0\n1,0,0:minecraft:dirt\n", "utf8");
    const out = loadBo2(input, { registry, mode: "strict" });
    expect(out.valid).toBe(true);
    expect(out.parseMode).toBe("strict");
    expect(out.canonical?.voxels.length).toBe(2);
  });

  it("falls back to salvage for malformed strict input", () => {
    const input = Buffer.from("[META]\nauthor=test\n[DATA]\n0,0,0:1.0\nbroken-line\n0,0,0:3.0\n", "utf8");
    const out = loadBo2(input, { registry, mode: "strict+salvage" });
    expect(out.parseMode).toBe("salvage");
    expect(out.valid).toBe(true);
    expect(out.canonical?.voxels.length).toBe(1);
  });
});

