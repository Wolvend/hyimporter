import { parentPort } from "node:worker_threads";
import { ingestFile } from "../ingest.js";
import type { IngestTask } from "../types.js";

if (!parentPort) {
  throw new Error("ingest-worker must run in worker context");
}

parentPort.on("message", (task: IngestTask) => {
  try {
    const result = ingestFile(task);
    parentPort?.postMessage({ ok: true, result });
  } catch (error) {
    parentPort?.postMessage({
      ok: false,
      error: (error as Error).message
    });
  }
});

