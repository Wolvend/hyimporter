import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { writeFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { ingestFile } from "../src/ingest.js";

describe("ingestFile", () => {
  it("never crashes on random bytes and returns invalid result", () => {
    const base = mkdtempSync(join(tmpdir(), "vv-ingest-"));
    const source = join(base, "bad.bo2");
    writeFileSync(source, Buffer.from([0x00, 0xff, 0x13, 0x37, 0x88]));

    const result = ingestFile({
      path: source,
      mode: "strict+salvage",
      profile: "mc_1_12_legacy",
      thumbsDir: join(base, "thumbs"),
      cacheDir: join(base, "cache"),
      reportsDir: join(base, "reports"),
      thumbSize: 64
    });

    expect(result.valid).toBe(false);
    expect(result.errors_json.length).toBeGreaterThan(0);
  });
});

