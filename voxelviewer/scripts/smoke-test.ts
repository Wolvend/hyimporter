import { resolve } from "node:path";
import { spawn } from "node:child_process";
import { runScan } from "../packages/indexer/src/scan.js";

async function main(): Promise<void> {
  const summary = await runScan({
    folder: resolve("fixtures"),
    outDb: resolve("data/objects.sqlite"),
    thumbsDir: resolve("data/thumbs"),
    cacheDir: resolve("data/cache"),
    reportsDir: resolve("data/reports"),
    mode: "strict+salvage",
    workers: 1,
    profile: "mc_1_12_legacy",
    thumbSize: 128
  });
  console.log("[smoke] index summary:");
  console.log(JSON.stringify(summary, null, 2));
  console.log("[smoke] launch desktop with:");
  console.log("pnpm desktop -- --db data/objects.sqlite");

  if (process.argv.includes("--open-desktop")) {
    const child = spawn("pnpm", ["desktop", "--", "--db", "data/objects.sqlite"], {
      stdio: "inherit",
      shell: true
    });
    child.on("exit", (code) => process.exit(code ?? 0));
  }
}

main().catch((error) => {
  console.error(`[smoke] failed: ${(error as Error).message}`);
  process.exit(1);
});
