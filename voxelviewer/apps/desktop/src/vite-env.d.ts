/// <reference types="vite/client" />

declare global {
  type DebugLogEntry = {
    id: number;
    timestamp: string;
    level: "info" | "warn" | "error";
    source: "main" | "renderer";
    message: string;
  };

  interface Window {
    voxelApi: {
      listObjects(filters: Record<string, unknown>): Promise<any[]>;
      getObjectDetail(id: number): Promise<any>;
      readMesh(meshPath: string): Promise<any>;
      readReport(reportPath: string): Promise<any>;
      getFailureDashboard(): Promise<any[]>;
      exportVoxelJson(id: number, outPath: string): Promise<{ ok: boolean; outPath: string }>;
      getDebugLogs(): Promise<DebugLogEntry[]>;
      clearDebugLogs(): Promise<{ ok: boolean }>;
      reportDebugLog(level: "info" | "warn" | "error", message: unknown): void;
      onDebugLog(handler: (entry: DebugLogEntry) => void): () => void;
    };
  }
}

export {};
