import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { _electron as electron } from "playwright";

async function main(): Promise<void> {
  mkdirSync(resolve("data/playwright"), { recursive: true });
  const dbPath = resolve("data/objects.sqlite");
  const appEntry = resolve("apps/desktop/electron/main.mjs");
  const rendererEntry = resolve("apps/desktop/dist/renderer/index.html");

  if (!existsSync(rendererEntry)) {
    throw new Error("Desktop renderer bundle missing. Run: corepack pnpm --filter @voxelviewer/desktop run build");
  }

  const appRequire = createRequire(pathToFileURL(resolve("apps/desktop/package.json")).href);
  const electronBinary = appRequire("electron");

  const app = await electron.launch({
    executablePath: electronBinary,
    args: [appEntry, "--db", dbPath]
  });

  const page = await app.firstWindow();
  await page.waitForSelector("text=Objects", { timeout: 60000 });
  await page.waitForSelector(".object-row", { timeout: 60000 });

  await page.fill("input[placeholder*='Search']", "simple");
  await page.waitForTimeout(400);
  await page.click(".object-row");
  await page.waitForSelector(".viewport-host canvas", { timeout: 60000 });
  await page.click("button:has-text('Show Failure Dashboard')");
  await page.waitForSelector(".failure-dash table tbody tr", { timeout: 60000 });

  const objectCount = await page.locator(".object-row").count();
  const failureCount = await page.locator(".failure-dash table tbody tr").count();
  const selectedPath = await page.locator(".right-pane .kv").first().innerText();

  const screenshotPath = resolve("data/playwright/desktop-ui-smoke.png");
  await page.screenshot({ path: screenshotPath, fullPage: true });

  const summary = {
    objectCount,
    failureCount,
    selectedPath,
    screenshotPath,
    timestamp: new Date().toISOString()
  };
  writeFileSync(resolve("data/playwright/ui-smoke-summary.json"), JSON.stringify(summary, null, 2), "utf8");

  await app.close();
  console.log("[ui-smoke] OK");
  console.log(JSON.stringify(summary, null, 2));
}

main().catch((error) => {
  console.error(`[ui-smoke] failed: ${(error as Error).message}`);
  process.exit(1);
});
