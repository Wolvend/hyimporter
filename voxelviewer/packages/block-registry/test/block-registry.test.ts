import { describe, expect, it } from "vitest";
import { BlockRegistry } from "../src/index.js";

describe("BlockRegistry", () => {
  it("maps known legacy ids", () => {
    const reg = new BlockRegistry("mc_1_12_legacy");
    const out = reg.resolve({ legacyId: 1, legacyData: 0 });
    expect(out.unknown).toBe(false);
    expect(out.canonical).toBe("minecraft:stone");
  });

  it("keeps unknown blocks with placeholder keys", () => {
    const reg = new BlockRegistry("mc_1_16_namespaced");
    const out = reg.resolve({ namespacedId: "mod:unknown_block" });
    expect(out.unknown).toBe(true);
    expect(out.canonical.startsWith("unknown:")).toBe(true);
  });
});

