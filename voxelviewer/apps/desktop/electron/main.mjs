import { app, BrowserWindow, ipcMain } from "electron";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import initSqlJs from "sql.js";
import { BlockRegistry } from "@voxelviewer/block-registry";
import { loadBo2 } from "@voxelviewer/loaders-bo2";
import { loadHytale } from "@voxelviewer/loaders-hytale";
import { loadSchematic } from "@voxelviewer/loaders-schematic";

const require = createRequire(import.meta.url);
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const DEBUG_LOG_LIMIT = 1000;
let debugLogSeq = 1;
const debugLogs = [];
/** @type {BrowserWindow | null} */
let mainWindow = null;

function formatLogValue(value) {
  if (typeof value === "string") return value;
  if (value instanceof Error) return `${value.name}: ${value.message}`;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function pushDebugLog(entry) {
  const normalized = {
    id: debugLogSeq++,
    timestamp: new Date().toISOString(),
    level: entry?.level ?? "info",
    source: entry?.source ?? "main",
    message: entry?.message ? String(entry.message) : ""
  };
  debugLogs.push(normalized);
  if (debugLogs.length > DEBUG_LOG_LIMIT) {
    debugLogs.splice(0, debugLogs.length - DEBUG_LOG_LIMIT);
  }
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("debug:log", normalized);
  }
}

function logMain(level, ...args) {
  pushDebugLog({
    level,
    source: "main",
    message: args.map((arg) => formatLogValue(arg)).join(" ")
  });
}

const baseConsole = {
  log: console.log.bind(console),
  info: console.info.bind(console),
  warn: console.warn.bind(console),
  error: console.error.bind(console)
};
console.log = (...args) => {
  baseConsole.log(...args);
  logMain("info", ...args);
};
console.info = (...args) => {
  baseConsole.info(...args);
  logMain("info", ...args);
};
console.warn = (...args) => {
  baseConsole.warn(...args);
  logMain("warn", ...args);
};
console.error = (...args) => {
  baseConsole.error(...args);
  logMain("error", ...args);
};

const profileDir = resolve(__dirname, "../../data/.electron-profile");
const sessionDir = resolve(profileDir, "session");
const diskCacheDir = resolve(profileDir, "chromium-cache");
mkdirSync(profileDir, { recursive: true });
mkdirSync(sessionDir, { recursive: true });
mkdirSync(diskCacheDir, { recursive: true });
app.setPath("userData", profileDir);
app.setPath("sessionData", sessionDir);
app.commandLine.appendSwitch("disk-cache-dir", diskCacheDir);

const hasLock = app.requestSingleInstanceLock();
if (!hasLock) {
  app.quit();
  process.exit(0);
}

function getDbPath() {
  const defaults = [
    resolve(__dirname, "../../data/objects.sqlite"),
    resolve(__dirname, "../../../data/objects.sqlite"),
    resolve(__dirname, "../../../../data/objects.sqlite"),
    resolve(process.cwd(), "data/objects.sqlite"),
    resolve(process.cwd(), "../data/objects.sqlite"),
    resolve(process.cwd(), "../../data/objects.sqlite")
  ];
  const idx = process.argv.findIndex((x) => x === "--db");
  if (idx >= 0 && process.argv[idx + 1]) {
    const raw = String(process.argv[idx + 1]);
    const asResolved = resolve(raw);
    if (existsSync(asResolved)) return asResolved;
    const variants = [
      resolve(__dirname, raw),
      resolve(__dirname, "../", raw),
      resolve(__dirname, "../../", raw),
      resolve(__dirname, "../../../", raw),
      resolve(process.cwd(), raw)
    ];
    for (const candidate of variants) {
      if (existsSync(candidate)) return candidate;
    }
    return asResolved;
  }
  for (const candidate of defaults) {
    if (existsSync(candidate)) return candidate;
  }
  return defaults[0];
}

const dbPath = getDbPath();
// eslint-disable-next-line no-console
console.log(`[desktop] dbPath=${dbPath} exists=${existsSync(dbPath)}`);
const SQL = await initSqlJs({
  locateFile: () => require.resolve("sql.js/dist/sql-wasm.wasm")
});

const db = existsSync(dbPath) ? new SQL.Database(readFileSync(dbPath)) : new SQL.Database();

function runAll(sql, params = []) {
  const stmt = db.prepare(sql);
  stmt.bind(params);
  const rows = [];
  while (stmt.step()) {
    rows.push(stmt.getAsObject());
  }
  stmt.free();
  return rows;
}

function runOne(sql, params = []) {
  const rows = runAll(sql, params);
  return rows.length > 0 ? rows[0] : null;
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1600,
    height: 920,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: join(__dirname, "preload.cjs")
    }
  });
  mainWindow = win;
  pushDebugLog({
    level: "info",
    source: "main",
    message: "Created main window."
  });

  const indexHtml = resolve(__dirname, "../dist/renderer/index.html");
  win.webContents.on("did-fail-load", (_event, code, desc, url) => {
    // Keep startup failures visible in terminal for automated smoke runs.
    // eslint-disable-next-line no-console
    console.error(`[desktop] did-fail-load code=${code} desc=${desc} url=${url}`);
  });
  win.webContents.on("render-process-gone", (_event, details) => {
    // eslint-disable-next-line no-console
    console.error(`[desktop] render-process-gone reason=${details.reason}`);
  });
  win.on("closed", () => {
    mainWindow = null;
  });
  win.loadFile(indexHtml);
}

app.on("second-instance", (_event, argv) => {
  const wantsReboot = Array.isArray(argv) && argv.includes("--reboot");
  if (wantsReboot) {
    if (!mainWindow) {
      createWindow();
      return;
    }
    // Graceful reboot: keep single-process lock and just reload/focus active window.
    mainWindow.reload();
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    mainWindow.focus();
    return;
  }
  if (!mainWindow) return;
  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }
  mainWindow.focus();
});

ipcMain.handle("objects:list", (_event, filters) => {
  const where = [];
  const params = [];
  if (filters?.search) {
    where.push("(o.path LIKE ? OR IFNULL(o.author,'') LIKE ? OR IFNULL(o.description,'') LIKE ?)");
    const s = `%${String(filters.search)}%`;
    params.push(s, s, s);
  }
  if (filters?.format && filters.format !== "all") {
    where.push("o.format = ?");
    params.push(String(filters.format));
  }
  if (typeof filters?.valid === "boolean") {
    where.push("o.valid = ?");
    params.push(filters.valid ? 1 : 0);
  }
  if (typeof filters?.unknownMin === "number") {
    where.push("o.unknown_blocks >= ?");
    params.push(Number(filters.unknownMin));
  }
  if (typeof filters?.dxMin === "number") {
    where.push("o.dx >= ?");
    params.push(Number(filters.dxMin));
  }
  if (typeof filters?.dxMax === "number") {
    where.push("o.dx <= ?");
    params.push(Number(filters.dxMax));
  }
  if (typeof filters?.dyMin === "number") {
    where.push("o.dy >= ?");
    params.push(Number(filters.dyMin));
  }
  if (typeof filters?.dyMax === "number") {
    where.push("o.dy <= ?");
    params.push(Number(filters.dyMax));
  }
  if (typeof filters?.dzMin === "number") {
    where.push("o.dz >= ?");
    params.push(Number(filters.dzMin));
  }
  if (typeof filters?.dzMax === "number") {
    where.push("o.dz <= ?");
    params.push(Number(filters.dzMax));
  }
  if (typeof filters?.blockMin === "number") {
    where.push("o.block_count >= ?");
    params.push(Number(filters.blockMin));
  }
  if (typeof filters?.blockMax === "number") {
    where.push("o.block_count <= ?");
    params.push(Number(filters.blockMax));
  }
  const sql = `
    SELECT
      o.id, o.path, o.format, o.valid, o.dx, o.dy, o.dz, o.block_count, o.unknown_blocks,
      o.author, o.description, o.parse_mode, o.warnings_json, o.errors_json,
      a.thumb_path, a.mesh_cache_path, a.ingest_report_path
    FROM objects o
    LEFT JOIN assets a ON a.object_id = o.id
    ${where.length > 0 ? `WHERE ${where.join(" AND ")}` : ""}
    ORDER BY o.updated_at DESC, o.path ASC
    LIMIT 20000
  `;
  return runAll(sql, params);
});

ipcMain.handle("objects:detail", (_event, id) => {
  const row = runOne(
    `
    SELECT o.*, a.thumb_path, a.mesh_cache_path, a.ingest_report_path
    FROM objects o
    LEFT JOIN assets a ON a.object_id = o.id
    WHERE o.id = ?
  `,
    [Number(id)]
  );
  return row ?? null;
});

ipcMain.handle("objects:readMesh", (_event, meshPath) => {
  if (!meshPath) return null;
  const raw = readFileSync(String(meshPath), "utf8");
  return JSON.parse(raw);
});

ipcMain.handle("objects:readReport", (_event, reportPath) => {
  const raw = readFileSync(String(reportPath), "utf8");
  return JSON.parse(raw);
});

ipcMain.handle("objects:failureDashboard", () => {
  const rows = runAll(`
    SELECT o.id, o.path, o.format, o.valid, o.unknown_blocks, o.errors_json, o.warnings_json, a.thumb_path
    FROM objects o
    LEFT JOIN assets a ON a.object_id = o.id
    WHERE o.valid = 0 OR o.unknown_blocks > 0
    ORDER BY o.valid ASC, o.unknown_blocks DESC, o.path ASC
    LIMIT 20000
  `);

  return rows.map((row) => {
    let errorType = "none";
    try {
      const errors = JSON.parse(row.errors_json ?? "[]");
      if (Array.isArray(errors) && errors.length > 0 && errors[0]?.code) {
        errorType = String(errors[0].code);
      }
    } catch {
      errorType = "json_parse_error";
    }
    return {
      ...row,
      errorType
    };
  });
});

ipcMain.handle("objects:exportVoxelJson", (_event, payload) => {
  const id = Number(payload?.id);
  const outPath = resolve(String(payload?.outPath));
  const row = runOne("SELECT path, format FROM objects WHERE id = ?", [id]);
  if (!row) {
    throw new Error(`Object ${id} not found`);
  }

  const bytes = readFileSync(row.path);
  const registry = new BlockRegistry("mc_1_12_legacy");
  let canonical = null;
  if (row.format === "bo2") {
    const out = loadBo2(bytes, { mode: "strict+salvage", registry, sourcePath: row.path });
    canonical = out.canonical ?? null;
  } else if (row.format === "schematic") {
    const out = loadSchematic(bytes, { mode: "strict+salvage", registry, sourcePath: row.path });
    canonical = out.canonical ?? null;
  } else if (row.format === "hytale") {
    const out = loadHytale(bytes, { registry, sourcePath: row.path });
    canonical = out.canonical ?? null;
  }
  if (!canonical) {
    throw new Error("Object is invalid and cannot be exported.");
  }
  writeFileSync(outPath, JSON.stringify(canonical.voxels, null, 2), "utf8");
  return { ok: true, outPath };
});

ipcMain.handle("debug:getLogs", () => {
  return debugLogs.slice();
});

ipcMain.handle("debug:clearLogs", () => {
  debugLogs.length = 0;
  pushDebugLog({
    level: "info",
    source: "main",
    message: "Debug logs cleared."
  });
  return { ok: true };
});

ipcMain.on("debug:rendererLog", (_event, payload) => {
  pushDebugLog({
    level: payload?.level ?? "info",
    source: "renderer",
    message: payload?.message ? String(payload.message) : ""
  });
});

app.whenReady().then(createWindow);
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
app.on("before-quit", () => {
  db.close();
});
