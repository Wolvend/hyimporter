import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";

function findArg(flag: string): string | undefined {
  const index = process.argv.findIndex((item) => item === flag);
  if (index >= 0 && process.argv[index + 1]) {
    return String(process.argv[index + 1]);
  }
  return undefined;
}

function run(command: string, args: string[], cwd: string): Promise<void> {
  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(command, args, {
      cwd,
      stdio: "inherit",
      shell: false
    });
    child.on("exit", (code) => {
      if (code === 0) {
        resolvePromise();
        return;
      }
      rejectPromise(new Error(`${command} ${args.join(" ")} failed with exit code ${code ?? -1}`));
    });
    child.on("error", rejectPromise);
  });
}

async function runDesktopBuild(root: string): Promise<void> {
  if (process.platform === "win32") {
    await run("cmd.exe", ["/d", "/s", "/c", "corepack pnpm --filter @voxelviewer/desktop run build"], root);
    return;
  }
  await run("corepack", ["pnpm", "--filter", "@voxelviewer/desktop", "run", "build"], root);
}

async function main(): Promise<void> {
  const root = resolve(process.cwd());
  const dbArg = findArg("--db");
  const dbPath = resolve(root, dbArg ?? "data/objects.sqlite");
  const appEntry = resolve(root, "apps/desktop/electron/main.mjs");

  await runDesktopBuild(root);

  const appRequire = createRequire(pathToFileURL(resolve(root, "apps/desktop/package.json")).href);
  const electronBinary = appRequire("electron");
  const child = spawn(electronBinary, [appEntry, "--reboot", "--db", dbPath], {
    cwd: root,
    detached: true,
    stdio: "ignore"
  });
  child.unref();
  console.log(`[desktop:open] launched pid=${child.pid} db=${dbPath}`);
}

main().catch((error) => {
  console.error(`[desktop:open] failed: ${(error as Error).message}`);
  process.exit(1);
});
