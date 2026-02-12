import { fileURLToPath } from "node:url";
import { Worker } from "node:worker_threads";
import type { IngestResult, IngestTask } from "./types.js";

interface PendingTask {
  task: IngestTask;
  resolve: (value: IngestResult) => void;
  reject: (error: unknown) => void;
}

interface WorkerState {
  worker: Worker;
  busy: boolean;
  current?: PendingTask;
}

export class IngestWorkerPool {
  private readonly workers: WorkerState[] = [];
  private readonly queue: PendingTask[] = [];

  public constructor(size: number) {
    const n = Math.max(1, size);
    const herePath = fileURLToPath(import.meta.url);
    const tsRuntime = herePath.endsWith(".ts");
    const workerModule = tsRuntime ? "./workers/ingest-worker.ts" : "./workers/ingest-worker.js";
    const workerUrl = new URL(workerModule, import.meta.url);

    for (let i = 0; i < n; i++) {
      const execArgv = tsRuntime ? [...process.execArgv, "--import", "tsx"] : process.execArgv;
      const worker = new Worker(workerUrl, {
        execArgv
      });
      const state: WorkerState = {
        worker,
        busy: false
      };

      worker.on("message", (message: { ok: boolean; result?: IngestResult; error?: string }) => {
        const current = state.current;
        state.current = undefined;
        state.busy = false;
        if (!current) return;
        if (message.ok && message.result) {
          current.resolve(message.result);
        } else {
          current.reject(new Error(message.error ?? "Worker failure"));
        }
        this.pump();
      });

      worker.on("error", (err) => {
        const current = state.current;
        state.current = undefined;
        state.busy = false;
        if (current) {
          current.reject(err);
        }
        this.pump();
      });

      this.workers.push(state);
    }
  }

  public run(task: IngestTask): Promise<IngestResult> {
    return new Promise<IngestResult>((resolve, reject) => {
      this.queue.push({ task, resolve, reject });
      this.pump();
    });
  }

  private pump(): void {
    for (const state of this.workers) {
      if (state.busy) continue;
      const next = this.queue.shift();
      if (!next) return;
      state.current = next;
      state.busy = true;
      state.worker.postMessage(next.task);
    }
  }

  public async close(): Promise<void> {
    await Promise.all(this.workers.map((w) => w.worker.terminate()));
  }
}
