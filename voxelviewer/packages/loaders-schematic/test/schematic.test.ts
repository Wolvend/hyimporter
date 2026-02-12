import { describe, expect, it } from "vitest";
import { gzipSync } from "node:zlib";
import { BlockRegistry } from "@voxelviewer/block-registry";
import { loadSchematic, sniffSchematic } from "../src/index.js";

function u16be(v: number): number[] {
  return [(v >>> 8) & 0xff, v & 0xff];
}

function i16be(v: number): number[] {
  const n = v & 0xffff;
  return [(n >>> 8) & 0xff, n & 0xff];
}

function i32be(v: number): number[] {
  const n = v >>> 0;
  return [(n >>> 24) & 0xff, (n >>> 16) & 0xff, (n >>> 8) & 0xff, n & 0xff];
}

function str(s: string): number[] {
  const b = Buffer.from(s, "utf8");
  return [...u16be(b.length), ...b];
}

function nbtRoot(compoundPayload: number[]): Uint8Array {
  const bytes = [10, 0, 0, ...compoundPayload, 0];
  return Uint8Array.from(bytes);
}

function shortTag(name: string, value: number): number[] {
  return [2, ...str(name), ...i16be(value)];
}

function intTag(name: string, value: number): number[] {
  return [3, ...str(name), ...i32be(value)];
}

function byteArrayTag(name: string, value: number[]): number[] {
  return [7, ...str(name), ...i32be(value.length), ...value.map((v) => v & 0xff)];
}

function compoundTag(name: string, payload: number[]): number[] {
  return [10, ...str(name), ...payload, 0];
}

function makeMceditFixture(): Uint8Array {
  const payload = [
    ...shortTag("Width", 2),
    ...shortTag("Height", 1),
    ...shortTag("Length", 1),
    ...byteArrayTag("Blocks", [1, 3]),
    ...byteArrayTag("Data", [0, 0])
  ];
  return nbtRoot(payload);
}

function encodeVarint(v: number): number[] {
  const out: number[] = [];
  let n = v >>> 0;
  while (true) {
    if ((n & ~0x7f) === 0) {
      out.push(n);
      break;
    }
    out.push((n & 0x7f) | 0x80);
    n >>>= 7;
  }
  return out;
}

function makeSpongeFixture(): Uint8Array {
  const palette = [
    ...intTag("minecraft:stone", 0),
    ...intTag("minecraft:dirt", 1)
  ];
  const blockData = [...encodeVarint(0), ...encodeVarint(1)];
  const payload = [
    ...shortTag("Width", 2),
    ...shortTag("Height", 1),
    ...shortTag("Length", 1),
    ...compoundTag("Palette", palette),
    ...byteArrayTag("BlockData", blockData)
  ];
  return nbtRoot(payload);
}

const registry = new BlockRegistry("mc_1_12_legacy");

describe("sniffSchematic", () => {
  it("matches by extension and magic", () => {
    const data = makeMceditFixture();
    const sniff = sniffSchematic(gzipSync(data), "sample.schematic");
    expect(sniff.match).toBe(true);
  });
});

describe("loadSchematic", () => {
  it("loads MCEdit schematic", () => {
    const bytes = gzipSync(makeMceditFixture());
    const out = loadSchematic(bytes, { mode: "strict+salvage", registry, sourcePath: "fixture.schematic" });
    expect(out.valid).toBe(true);
    expect(out.variant).toBe("mcedit");
    expect(out.canonical?.voxels.length).toBe(2);
  });

  it("loads Sponge schem", () => {
    const bytes = gzipSync(makeSpongeFixture());
    const out = loadSchematic(bytes, { mode: "strict+salvage", registry, sourcePath: "fixture.schem" });
    expect(out.valid).toBe(true);
    expect(out.variant).toBe("sponge");
    expect(out.canonical?.voxels.length).toBe(2);
  });
});

