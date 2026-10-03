import { useEffect, useState } from "react";
import { getSummary, getThreads, runPipeline } from "../api";
import SummaryCards from "../components/SummaryCards";
import ThreadRow from "../components/ThreadRow";
import { formatDate, formatDateTime } from "../format";
import type { Filters, RunSummary, Summary, ThreadRow as ThreadRowData } from "../types";

const CHIP_GROUPS: { name: keyof Filters; label: string; options: string[] }[] = [
  { name: "bucket", label: "Bucket", options: ["act", "review", "archive", "ignore"] },
  { name: "level", label: "Level", options: ["P1", "P2", "P3", "P4"] },
  { name: "lob", label: "Line", options: ["home", "motor", "liability"] },
];

/** Chip rows for bucket, level and line of business; clicking an active chip clears it. */
function FilterChips({ filters, onChange }: { filters: Filters; onChange: (filters: Filters) => void }) {
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
      {CHIP_GROUPS.map((group) => (
        <div key={group.name} className="flex items-center gap-1">
          <span className="mr-1 text-slate-500">{group.label}:</span>
          {group.options.map((option) => {
            const active = filters[group.name] === option;
            return (
              <button
                key={option}
                onClick={() => onChange({ ...filters, [group.name]: active ? undefined : option })}
                className={`rounded-full border px-2.5 py-0.5 ${
                  active ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white hover:bg-slate-100"
                }`}
              >
                {option}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}

/** Re-run the pipeline from the page (the demo's "run it live"); reports what the run did. */
function RunPanel({ onDone }: { onDone: () => void }) {
  const [force, setForce] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setResult(null);
    try {
      const s: RunSummary = await runPipeline(force);
      setResult(`${s.triaged} triaged, ${s.skipped} unchanged, ${s.fallbacks} sent to review; $${s.cost_usd.toFixed(3)}`);
      onDone();
    } catch (error) {
      setResult(`Run failed: ${(error as Error).message}`);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3 text-sm">
      <button onClick={run} disabled={running}
        className="rounded-md bg-slate-900 px-3 py-1.5 font-medium text-white hover:bg-slate-700 disabled:opacity-50">
        {running ? "Running…" : "Run pipeline"}
      </button>
      <label className="flex items-center gap-1 text-slate-600">
        <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
        re-triage every thread (about 2 min, about $0.18)
      </label>
      {result && <span className="text-slate-600">{result}</span>}
    </div>
  );
}

/** The workload in one view: counts by priority, filters, and every thread sorted P1 → P4, oldest first. */
export default function Dashboard({ onOpen }: { onOpen: (key: string) => void }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [rows, setRows] = useState<ThreadRowData[] | null>(null);
  const [filters, setFilters] = useState<Filters>({});
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    getSummary().then(setSummary).catch((e: Error) => setError(e.message));
  }, [reload]);
  useEffect(() => {
    getThreads(filters).then(setRows).catch((e: Error) => setError(e.message));
  }, [filters, reload]);

  return (
    <div className="space-y-4">
      {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</div>}
      {summary && (
        <p className="text-sm text-slate-600">
          {summary.total_threads} threads as of {formatDate(summary.as_of)} · triage {summary.prompt_versions.join(", ") || "—"} on{" "}
          {summary.models.join(", ") || "—"} · rules {summary.rules_version}
          {summary.last_run && <> · last run {formatDateTime(summary.last_run)}</>}
          {(summary.counts.untriaged ?? 0) > 0 && <> · <strong>{summary.counts.untriaged} not yet triaged</strong></>}
        </p>
      )}
      {summary && <SummaryCards summary={summary} active={filters} onSelect={setFilters} />}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <FilterChips filters={filters} onChange={setFilters} />
        <RunPanel onDone={() => setReload((n) => n + 1)} />
      </div>
      <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
        <table className="w-full text-left">
          <thead className="bg-slate-100 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Priority</th>
              <th className="px-3 py-2">What to do</th>
              <th className="px-3 py-2">Claim</th>
              <th className="px-3 py-2">From</th>
              <th className="px-3 py-2 text-right">Age</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {rows?.map((row) => <ThreadRow key={row.key} row={row} onOpen={onOpen} />)}
          </tbody>
        </table>
        {rows?.length === 0 && (
          <p className="p-6 text-center text-sm text-slate-500">
            No threads match. If the mailbox has not been processed yet, click “Run pipeline”.
          </p>
        )}
      </div>
    </div>
  );
}
