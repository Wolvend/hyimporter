const { contextBridge, ipcRenderer } = require("electron");

function normalizeMessage(value) {
  if (typeof value === "string") return value;
  if (value instanceof Error) return `${value.name}: ${value.message}`;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function reportRendererLog(level, message) {
  ipcRenderer.send("debug:rendererLog", {
    level,
    message: normalizeMessage(message)
  });
}

window.addEventListener("error", (event) => {
  const detail = {
    message: event.message,
    file: event.filename,
    line: event.lineno,
    column: event.colno
  };
  reportRendererLog("error", detail);
});

window.addEventListener("unhandledrejection", (event) => {
  reportRendererLog("error", {
    type: "unhandledrejection",
    reason: normalizeMessage(event.reason)
  });
});

contextBridge.exposeInMainWorld("voxelApi", {
  listObjects: (filters) => ipcRenderer.invoke("objects:list", filters),
  getObjectDetail: (id) => ipcRenderer.invoke("objects:detail", id),
  readMesh: (meshPath) => ipcRenderer.invoke("objects:readMesh", meshPath),
  readReport: (reportPath) => ipcRenderer.invoke("objects:readReport", reportPath),
  getFailureDashboard: () => ipcRenderer.invoke("objects:failureDashboard"),
  exportVoxelJson: (id, outPath) => ipcRenderer.invoke("objects:exportVoxelJson", { id, outPath }),
  getDebugLogs: () => ipcRenderer.invoke("debug:getLogs"),
  clearDebugLogs: () => ipcRenderer.invoke("debug:clearLogs"),
  reportDebugLog: (level, message) => reportRendererLog(level, message),
  onDebugLog: (handler) => {
    const wrapped = (_event, entry) => handler(entry);
    ipcRenderer.on("debug:log", wrapped);
    return () => ipcRenderer.removeListener("debug:log", wrapped);
  }
});
