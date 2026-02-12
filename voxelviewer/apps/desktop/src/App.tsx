import { useEffect, useMemo, useState } from "react";
import { VoxelViewport } from "./VoxelViewport";

type ObjectRow = {
  id: number;
  path: string;
  format: "bo2" | "hytale" | "schematic" | "unknown";
  valid: number;
  dx: number;
  dy: number;
  dz: number;
  block_count: number;
  unknown_blocks: number;
  author: string | null;
  description: string | null;
  parse_mode: string;
  warnings_json: string;
  errors_json: string;
  thumb_path: string;
  mesh_cache_path: string | null;
  ingest_report_path: string;
};

type Filters = {
  search: string;
  format: "all" | "bo2" | "hytale" | "schematic";
  validOnly: "all" | "valid" | "invalid";
  unknownMin: number;
  dxMin?: number;
  dxMax?: number;
  dyMin?: number;
  dyMax?: number;
  dzMin?: number;
  dzMax?: number;
  blockMin?: number;
  blockMax?: number;
};

function parseJsonSafe(value: string): unknown[] {
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function readStoredTheme(): "dark" | "light" {
  try {
    const stored = window.localStorage.getItem("voxelviewer.theme");
    if (stored === "dark" || stored === "light") {
      return stored;
    }
  } catch {
    // Ignore storage access errors.
  }
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "dark" ? "dark" : "light";
}

export function App(): JSX.Element {
  const [rows, setRows] = useState<ObjectRow[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<ObjectRow | null>(null);
  const [meshData, setMeshData] = useState<{ quads: any[] } | null>(null);
  const [report, setReport] = useState<any>(null);
  const [showFailures, setShowFailures] = useState(false);
  const [failures, setFailures] = useState<any[]>([]);
  const [showDebugLogs, setShowDebugLogs] = useState(false);
  const [debugLogs, setDebugLogs] = useState<DebugLogEntry[]>([]);
  const [darkMode, setDarkMode] = useState<boolean>(() => readStoredTheme() === "dark");
  const [filters, setFilters] = useState<Filters>({
    search: "",
    format: "all",
    validOnly: "all",
    unknownMin: 0,
    dxMin: undefined,
    dxMax: undefined,
    dyMin: undefined,
    dyMax: undefined,
    dzMin: undefined,
    dzMax: undefined,
    blockMin: undefined,
    blockMax: undefined
  });

  useEffect(() => {
    const theme = darkMode ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", theme);
    try {
      window.localStorage.setItem("voxelviewer.theme", theme);
    } catch {
      // Ignore localStorage failures in restricted runtimes.
    }
  }, [darkMode]);

  useEffect(() => {
    let unsubscribe: (() => void) | null = null;
    let disposed = false;
    const loadInitialLogs = async () => {
      try {
        const initial = await window.voxelApi.getDebugLogs();
        if (!disposed) {
          setDebugLogs(initial);
        }
      } catch (error) {
        window.voxelApi.reportDebugLog("error", {
          scope: "debug:getDebugLogs",
          error: String(error)
        });
      }
      unsubscribe = window.voxelApi.onDebugLog((entry) => {
        setDebugLogs((prev) => {
          const next = [...prev, entry];
          if (next.length > 1000) {
            return next.slice(next.length - 1000);
          }
          return next;
        });
      });
    };
    void loadInitialLogs();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.shiftKey && event.code === "KeyL") {
        event.preventDefault();
        setShowDebugLogs((value) => !value);
      }
    };
    window.addEventListener("keydown", onKeyDown);

    return () => {
      disposed = true;
      window.removeEventListener("keydown", onKeyDown);
      if (unsubscribe) {
        unsubscribe();
      }
    };
  }, []);

  const loadObjects = async () => {
    const valid =
      filters.validOnly === "all" ? undefined : filters.validOnly === "valid" ? true : false;
    const data = await window.voxelApi.listObjects({
      search: filters.search,
      format: filters.format,
      valid,
      unknownMin: filters.unknownMin,
      dxMin: filters.dxMin,
      dxMax: filters.dxMax,
      dyMin: filters.dyMin,
      dyMax: filters.dyMax,
      dzMin: filters.dzMin,
      dzMax: filters.dzMax,
      blockMin: filters.blockMin,
      blockMax: filters.blockMax
    });
    setRows(data as ObjectRow[]);
    if (data.length > 0 && selectedId == null) {
      setSelectedId((data[0] as ObjectRow).id);
    }
  };

  useEffect(() => {
    void loadObjects();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    filters.search,
    filters.format,
    filters.validOnly,
    filters.unknownMin,
    filters.dxMin,
    filters.dxMax,
    filters.dyMin,
    filters.dyMax,
    filters.dzMin,
    filters.dzMax,
    filters.blockMin,
    filters.blockMax
  ]);

  useEffect(() => {
    if (selectedId == null) return;
    void (async () => {
      const detail = (await window.voxelApi.getObjectDetail(selectedId)) as ObjectRow;
      setSelectedDetail(detail);
      if (detail?.mesh_cache_path) {
        const mesh = await window.voxelApi.readMesh(detail.mesh_cache_path);
        setMeshData(mesh);
      } else {
        setMeshData(null);
      }
      if (detail?.ingest_report_path) {
        const rep = await window.voxelApi.readReport(detail.ingest_report_path);
        setReport(rep);
      } else {
        setReport(null);
      }
    })();
  }, [selectedId]);

  const selectedWarnings = useMemo(
    () => (selectedDetail ? parseJsonSafe(selectedDetail.warnings_json) : []),
    [selectedDetail]
  );
  const selectedErrors = useMemo(
    () => (selectedDetail ? parseJsonSafe(selectedDetail.errors_json) : []),
    [selectedDetail]
  );

  const onShowFailures = async () => {
    const next = !showFailures;
    setShowFailures(next);
    if (next) {
      const data = await window.voxelApi.getFailureDashboard();
      setFailures(data);
    }
  };

  const onClearDebugLogs = async () => {
    await window.voxelApi.clearDebugLogs();
    const logs = await window.voxelApi.getDebugLogs();
    setDebugLogs(logs);
  };

  return (
    <div className="layout">
      <aside className="pane left-pane">
        <h2>Objects</h2>
        <div className="filters">
          <input
            placeholder="Search path, author, description"
            value={filters.search}
            onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
          />
          <select
            value={filters.format}
            onChange={(e) => setFilters((f) => ({ ...f, format: e.target.value as Filters["format"] }))}
          >
            <option value="all">All formats</option>
            <option value="bo2">BO2</option>
            <option value="schematic">Schematic/Schem</option>
            <option value="hytale">Hytale</option>
          </select>
          <select
            value={filters.validOnly}
            onChange={(e) => setFilters((f) => ({ ...f, validOnly: e.target.value as Filters["validOnly"] }))}
          >
            <option value="all">All validity</option>
            <option value="valid">Valid only</option>
            <option value="invalid">Invalid only</option>
          </select>
          <label>
            Unknown &gt;=
            <input
              type="number"
              min={0}
              value={filters.unknownMin}
              onChange={(e) => setFilters((f) => ({ ...f, unknownMin: Number(e.target.value || 0) }))}
            />
          </label>
          <div className="range-grid">
            <label>
              dx min
              <input
                type="number"
                value={filters.dxMin ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, dxMin: e.target.value ? Number(e.target.value) : undefined }))}
              />
            </label>
            <label>
              dx max
              <input
                type="number"
                value={filters.dxMax ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, dxMax: e.target.value ? Number(e.target.value) : undefined }))}
              />
            </label>
            <label>
              dy min
              <input
                type="number"
                value={filters.dyMin ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, dyMin: e.target.value ? Number(e.target.value) : undefined }))}
              />
            </label>
            <label>
              dy max
              <input
                type="number"
                value={filters.dyMax ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, dyMax: e.target.value ? Number(e.target.value) : undefined }))}
              />
            </label>
            <label>
              dz min
              <input
                type="number"
                value={filters.dzMin ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, dzMin: e.target.value ? Number(e.target.value) : undefined }))}
              />
            </label>
            <label>
              dz max
              <input
                type="number"
                value={filters.dzMax ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, dzMax: e.target.value ? Number(e.target.value) : undefined }))}
              />
            </label>
            <label>
              blocks min
              <input
                type="number"
                value={filters.blockMin ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, blockMin: e.target.value ? Number(e.target.value) : undefined }))}
              />
            </label>
            <label>
              blocks max
              <input
                type="number"
                value={filters.blockMax ?? ""}
                onChange={(e) => setFilters((f) => ({ ...f, blockMax: e.target.value ? Number(e.target.value) : undefined }))}
              />
            </label>
          </div>
          <div className="button-row">
            <button onClick={() => void loadObjects()}>Refresh</button>
            <button onClick={() => void onShowFailures()}>
              {showFailures ? "Hide Failure Dashboard" : "Show Failure Dashboard"}
            </button>
            <button onClick={() => setDarkMode((value) => !value)}>
              {darkMode ? "Light mode" : "Dark mode"}
            </button>
          </div>
        </div>

        <div className="object-list">
          {rows.map((row) => (
            <div
              key={row.id}
              className={`object-row ${selectedId === row.id ? "selected" : ""}`}
              onClick={() => setSelectedId(row.id)}
            >
              <img
                src={`file:///${row.thumb_path.replace(/\\/g, "/")}`}
                alt="thumbnail"
                width={64}
                height={64}
              />
              <div className="object-row-text">
                <div className="path">{row.path}</div>
                <div className="meta">
                  {row.format} | {row.dx}x{row.dy}x{row.dz} | blocks {row.block_count}
                </div>
                <div className="meta">
                  valid={row.valid ? "yes" : "no"} | unknown={row.unknown_blocks}
                </div>
              </div>
            </div>
          ))}
        </div>
      </aside>

      <main className="pane main-pane">
        <h2>3D View</h2>
        <VoxelViewport meshData={meshData} />
        <div className="controls-help">
          WASD move, Q/E vertical, drag mouse to look, Shift to speed up.
          {" "}Press Ctrl+Shift+L for debug logs.
        </div>

        {showFailures && (
          <section className="failure-dash">
            <h3>Failure Dashboard</h3>
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Unknown</th>
                  <th>Path</th>
                </tr>
              </thead>
              <tbody>
                {failures.map((f) => (
                  <tr key={f.id} onClick={() => setSelectedId(f.id)}>
                    <td>{f.errorType}</td>
                    <td>{f.unknown_blocks}</td>
                    <td>{f.path}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </main>

      <aside className="pane right-pane">
        <h2>Metadata</h2>
        {!selectedDetail && <div>No selection.</div>}
        {selectedDetail && (
          <>
            <div className="kv"><strong>Path:</strong> {selectedDetail.path}</div>
            <div className="kv"><strong>Format:</strong> {selectedDetail.format}</div>
            <div className="kv"><strong>Parse mode:</strong> {selectedDetail.parse_mode}</div>
            <div className="kv"><strong>Bounds:</strong> {selectedDetail.dx}x{selectedDetail.dy}x{selectedDetail.dz}</div>
            <div className="kv"><strong>Block count:</strong> {selectedDetail.block_count}</div>
            <div className="kv"><strong>Unknown blocks:</strong> {selectedDetail.unknown_blocks}</div>
            <div className="kv"><strong>Author:</strong> {selectedDetail.author ?? "-"}</div>
            <div className="kv"><strong>Description:</strong> {selectedDetail.description ?? "-"}</div>
            <div className="button-row">
              <button
                onClick={async () => {
                  const out = window.prompt("Export normalized voxel JSON path:", "data/export.json");
                  if (!out) return;
                  await window.voxelApi.exportVoxelJson(selectedDetail.id, out);
                }}
              >
                Export JSON voxel list
              </button>
              <button disabled title="Optional future milestone">
                Export .schem (optional)
              </button>
            </div>
            <h3>Warnings</h3>
            <pre>{JSON.stringify(selectedWarnings, null, 2)}</pre>
            <h3>Errors</h3>
            <pre>{JSON.stringify(selectedErrors, null, 2)}</pre>
            <h3>Unknown Blocks</h3>
            <pre>{JSON.stringify(report?.unknownBlocks ?? { totalUnknown: 0, entries: [] }, null, 2)}</pre>
            <h3>Ingestion Report</h3>
            <pre>{report ? JSON.stringify(report, null, 2) : "No report loaded."}</pre>
          </>
        )}
      </aside>

      {showDebugLogs && (
        <section className="debug-log-panel" aria-label="Debug log panel">
          <div className="debug-log-header">
            <strong>Debug Log</strong>
            <span>{debugLogs.length} entries</span>
            <div className="button-row">
              <button onClick={() => void onClearDebugLogs()}>Clear</button>
              <button onClick={() => setShowDebugLogs(false)}>Close</button>
            </div>
          </div>
          <div className="debug-log-body">
            {debugLogs.length === 0 && <div className="debug-log-empty">No logs.</div>}
            {debugLogs.slice(-400).map((entry) => (
              <div key={`${entry.id}-${entry.timestamp}`} className={`debug-log-line level-${entry.level}`}>
                <span className="debug-log-time">{entry.timestamp.slice(11, 23)}</span>
                <span className="debug-log-level">[{entry.level.toUpperCase()}]</span>
                <span className="debug-log-source">[{entry.source}]</span>
                <span className="debug-log-message">{entry.message}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
