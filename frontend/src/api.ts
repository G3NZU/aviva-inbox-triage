// Typed fetch helpers: one per backend endpoint. The API base URL defaults to the local uvicorn server.
import type { Filters, QAAnswer, RunSummary, Summary, ThreadDetail, ThreadRow } from "./types";

const API_BASE: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** Fetch JSON from the API; throw an Error carrying the API's `detail` message when the call fails. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new Error(`Cannot reach the API at ${API_BASE}. Is uvicorn running?`);
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = typeof body?.detail === "string" ? body.detail : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

/** GET /summary — workload totals and the versions behind them. */
export function getSummary(): Promise<Summary> {
  return request<Summary>("/summary");
}

/** GET /threads — the workload list, filtered on the server, sorted P1 → P4 then oldest first. */
export function getThreads(filters: Filters): Promise<ThreadRow[]> {
  const params = new URLSearchParams();
  for (const [name, value] of Object.entries(filters)) {
    if (value) params.set(name, value);
  }
  return request<ThreadRow[]>(`/threads?${params.toString()}`);
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

/** POST /run — re-run the pipeline; `force` re-triages every thread (slow, costs tokens). */
export function runPipeline(force: boolean): Promise<RunSummary> {
  return request<RunSummary>(`/run?force=${force}`, { method: "POST" });
}
