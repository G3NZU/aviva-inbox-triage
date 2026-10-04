// Typed fetch helpers: one per backend endpoint. The API base URL defaults to the local uvicorn server.
import type { QAAnswer, RunSummary, Summary, ThreadDetail, ThreadRow } from "./types";

const API_BASE: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/**
 * A failed API call. `kind` says what went wrong in plain terms (the API could not be reached, or it
 * answered with an error); `message` keeps the technical detail from the API for the curious.
 */
export class ApiError extends Error {
  kind: "network" | "http";
  status: number | null;

  constructor(kind: "network" | "http", message: string, status: number | null = null) {
    super(message);
    this.kind = kind;
    this.status = status;
  }
}

/** Fetch JSON from the API; throw an ApiError carrying the API's `detail` message when the call fails. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError("network", `Cannot reach the API at ${API_BASE}.`);
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = typeof body?.detail === "string" ? body.detail : `HTTP ${response.status}`;
    throw new ApiError("http", detail, response.status);
  }
  return (await response.json()) as T;
}

/** GET /summary — workload totals and the versions behind them. */
export function getSummary(): Promise<Summary> {
  return request<Summary>("/summary");
}

/** GET /threads — every thread, sorted P1 → P4 then oldest first (the page filters them itself). */
export function getThreads(): Promise<ThreadRow[]> {
  return request<ThreadRow[]>("/threads");
}

/** GET /threads/{key} — one thread with its messages, triage, priority and audit trail. */
export function getThread(key: string): Promise<ThreadDetail> {
  return request<ThreadDetail>(`/threads/${encodeURIComponent(key)}`);
}

/** POST /ask — a free-text question; the answer cites messages or is a refusal. */
export function ask(question: string): Promise<QAAnswer> {
  return request<QAAnswer>("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

/** POST /run — re-run the pipeline; `force` re-triages every thread (slow, uses paid API calls). */
export function runPipeline(force: boolean): Promise<RunSummary> {
  return request<RunSummary>(`/run?force=${force}`, { method: "POST" });
}
