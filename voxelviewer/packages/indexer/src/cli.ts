#!/usr/bin/env node
import minimist from "minimist";
import { resolve } from "node:path";
import { runScan } from "./scan.js";

function printHelp(): void {
  console.log(`VoxelViewer Indexer

Usage:
  pnpm indexer scan <folder> --out data/objects.sqlite --thumbs data/thumbs
  pnpm indexer smoke

Options:
  --out <path>             SQLite output file (default: data/objects.sqlite)
  --thumbs <dir>           Thumbnail directory (default: data/thumbs)
  --cache <dir>            Mesh cache directory (default: data/cache)
  --reports <dir>          Ingestion report directory (default: data/reports)
  --mode <mode>            strict | salvage | strict+salvage (default: strict+salvage)
  --workers <n>            Worker count (default: CPU-1)
  --profile <name>         mc_1_12_legacy | mc_1_16_namespaced (default: mc_1_12_legacy)
  --overrides <file>       YAML mapping overrides
  --thumb-size <n>         Thumbnail dimension in px (default: 256)
  --debug-projections      Render front/top/side debug thumbnails
`);
}

async function run(): Promise<void> {
  const argv = minimist(process.argv.slice(2), {
    boolean: ["debug-projections"],
    string: ["out", "thumbs", "cache", "reports", "mode", "profile", "overrides"],
    default: {
      out: "data/objects.sqlite",
      thumbs: "data/thumbs",
      cache: "data/cache",
      reports: "data/reports",
      mode: "strict+salvage",
      profile: "mc_1_12_legacy",
      "thumb-size": 256
    }
  });

  const command = argv._[0];
  if (!command || command === "help" || command === "--help" || command === "-h") {
    printHelp();
    return;
  }

  if (command === "smoke") {
    const summary = await runScan({
      folder: resolve("fixtures/corpus"),
      outDb: resolve(argv.out),
      thumbsDir: resolve(argv.thumbs),
      cacheDir: resolve(argv.cache),
      reportsDir: resolve(argv.reports),
      mode: argv.mode as "strict" | "salvage" | "strict+salvage",
      workers: Number(argv.workers ?? 1),
      profile: argv.profile as "mc_1_12_legacy" | "mc_1_16_namespaced",
      overridesPath: argv.overrides ? resolve(argv.overrides) : undefined,
      thumbSize: Number(argv["thumb-size"] ?? 256),
      debugProjections: Boolean(argv["debug-projections"])
    });
    console.log(JSON.stringify(summary, null, 2));
    return;
  }

  if (command !== "scan") {
    throw new Error(`Unknown command: ${String(command)}`);
  }

  const folder = argv._[1];
  if (!folder) {
    throw new Error("Missing folder argument.");
  }

  const summary = await runScan({
    folder: resolve(String(folder)),
    outDb: resolve(argv.out),
    thumbsDir: resolve(argv.thumbs),
    cacheDir: resolve(argv.cache),
    reportsDir: resolve(argv.reports),
    mode: argv.mode as "strict" | "salvage" | "strict+salvage",
    workers: Number(argv.workers ?? 0),
    profile: argv.profile as "mc_1_12_legacy" | "mc_1_16_namespaced",
    overridesPath: argv.overrides ? resolve(argv.overrides) : undefined,
    thumbSize: Number(argv["thumb-size"] ?? 256),
    debugProjections: Boolean(argv["debug-projections"])
  });

  console.log(JSON.stringify(summary, null, 2));
}

run().catch((error) => {
  console.error(`[indexer] ${String((error as Error).message)}`);
  if (error && typeof error === "object" && "stack" in (error as { stack?: unknown })) {
    const stack = (error as { stack?: unknown }).stack;
    if (typeof stack === "string" && stack.trim()) {
      console.error(stack);
    }
  }
  process.exit(1);
});
