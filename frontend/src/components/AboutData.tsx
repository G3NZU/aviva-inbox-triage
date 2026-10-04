import { useEffect, useRef, useState } from "react";
import { ApiError, runPipeline } from "../api";
import { formatDateTime } from "../format";
import { CARD_HELP, HELP } from "../help";
import { CARD } from "../labels";
import type { RunSummary, Summary } from "../types";
import { SECTION_ORDER } from "../workload";
import Icon from "./Icon";

/** What a finished run did, from the API's RunSummary (every number is the API's). */
function runReport(s: RunSummary): string {
  return `Done: ${s.triaged} thread${s.triaged === 1 ? "" : "s"} read by the AI, ${s.skipped} unchanged, `
    + `${s.fallbacks} sent to Needs a check. Cost $${s.cost_usd.toFixed(3)}.`;
}

/** Why a run failed, in words; 409 means another run holds the lock. */
function runFailure(error: Error): string {
  if (error instanceof ApiError && error.status === 409) return "A run is already in progress. Try again when it finishes.";
  return `The run failed: ${error.message}`;
}

/** After the confirmation box closes without a run, put focus back on the link that opened it. */
function useFocusBack(confirming: boolean, running: boolean) {
  const opener = useRef<HTMLButtonElement>(null);
  const wasConfirming = useRef(false);
  useEffect(() => {
    if (wasConfirming.current && !confirming && !running) opener.current?.focus();
    wasConfirming.current = confirming;
  }, [confirming, running]);
  return opener;
}

/**
 * Re-run controls. A normal run reads only new or changed threads; re-reading every thread is a paid
 * action, so it asks for an inline confirmation first (focus moves to its safe choice, Cancel). While a run
 * lasts (it can take minutes) the button shows static text, never a spinner. Props: the thread total, and
 * handlers for the start (so the status line announces it) and the report.
 */
function RunControls({ total, onStart, onDone }: {
  total: number; onStart: (message: string) => void; onDone: (message: string) => void;
}) {
  const [running, setRunning] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const opener = useFocusBack(confirming, running);
  const runButton = useRef<HTMLButtonElement>(null);

  async function run(force: boolean) {
    setConfirming(false);
    setRunning(true);
    onStart(force ? "Re-reading all threads…" : "Re-running triage…");
    if (force) requestAnimationFrame(() => runButton.current?.focus()); // the confirm box is gone: keep focus nearby
    try {
      onDone(runReport(await runPipeline(force)));
    } catch (error) {
      onDone(runFailure(error as Error));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="mt-3 border-t border-line pt-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <button ref={runButton} type="button" onClick={() => { if (!running) void run(false); }} aria-disabled={running}
          className="rounded-md border border-line-strong bg-surface px-3 py-1.5 font-semibold hover:bg-sunken
            aria-disabled:text-ink-3">
          {running ? "Re-running… you can keep using the list" : "Re-run triage"}
        </button>
        <span className="text-ink-2">Reads new or changed threads; unchanged ones are not sent to the AI.</span>
      </div>
      {!running && !confirming && (
        <button ref={opener} type="button" onClick={() => setConfirming(true)}
          className="mt-2 text-accent underline hover:text-accent-strong">
          Re-read all threads…
        </button>
      )}
      {confirming && <ConfirmRereadAll total={total} onConfirm={() => void run(true)} onCancel={() => setConfirming(false)} />}
    </div>
  );
}

/** The second step before a paid full re-read: the warning, read out with the confirm button; focus starts on Cancel. */
function ConfirmRereadAll({ total, onConfirm, onCancel }: { total: number; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="mt-2 rounded-md border border-line bg-canvas p-3">
      <p id="reread-warning">
        Re-read all {total} threads? The AI reads every thread again. It takes a few minutes and uses paid API calls.
      </p>
      <div className="mt-2 flex gap-2">
        <button type="button" onClick={onConfirm} aria-describedby="reread-warning"
          className="rounded-md bg-ink px-3 py-1.5 font-semibold text-surface hover:bg-ink-2">Re-read all {total}</button>
        <button type="button" onClick={onCancel} autoFocus
          className="rounded-md border border-line-strong px-3 py-1.5 font-semibold hover:bg-sunken">Cancel</button>
      </div>
    </div>
  );
}

/**
 * What each group means, said once for the whole app: the priority rules (code, not the AI) put every thread in
 * one group. Then the as-of date and the sender's flag. Every threshold quoted comes from GET /summary.
 */
function Definitions({ summary }: { summary: Summary }) {
  return (
    <div>
      <p className="font-semibold">How the workload is sorted</p>
      <p className="mt-1 text-ink-2">The priority rules, not the AI, put each thread in one group:</p>
      <dl className="mt-2 space-y-1.5">
        {SECTION_ORDER.filter((card) => card !== "untriaged").map((card) => (
          <div key={card}>
            <dt className="inline font-semibold">{CARD[card].label}: </dt>
            <dd className="inline">{CARD_HELP[card](summary)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-ink-2">{HELP.asOf(summary)} {HELP.senderFlag(summary)}</p>
    </div>
  );
}

/**
 * "About this data": how the workload is sorted (the definitions, said once), where the numbers come from
 * (models, prompt and rules versions, last run) and the re-run controls, folded away so they never compete
 * with the work. Props: the summary, whether to start open (when the mailbox is empty or some threads are unread), and handlers that
 * receive the run's start and report (shown outside, so they stay visible).
 */
export default function AboutData({ summary, startOpen, onStart, onDone }: {
  summary: Summary; startOpen: boolean; onStart: (message: string) => void; onDone: (message: string) => void;
}) {
  const [openAtStart] = useState(startOpen); // a run that empties the unread list must not fold the panel shut
  const untriaged = summary.counts.untriaged ?? 0;
  const facts: [string, string][] = [
    ["Read by", `${summary.models.join(", ") || "—"}, prompt ${summary.prompt_versions.join(", ") || "—"}`],
    ["Priority rules", summary.rules_versions.join(", ") || "—"],
    ["Last run", summary.last_run ? formatDateTime(summary.last_run) : "Never"],
  ];
  if (untriaged > 0) facts.push(["Not read yet", `${untriaged} thread${untriaged === 1 ? "" : "s"}: re-run triage`]);
  return (
    <details open={openAtStart || undefined} className="group text-sm open:basis-full">
      <summary className="ml-auto flex min-h-6 w-fit cursor-pointer list-none items-center gap-1 rounded px-1
        text-accent hover:text-accent-strong [&::-webkit-details-marker]:hidden">
        About this data
        <Icon name="chevronDown" className="size-4 group-open:rotate-180 motion-safe:transition-transform" />
      </summary>
      <div className="mt-2 grid gap-x-8 gap-y-4 rounded-lg border border-line bg-surface p-4 lg:grid-cols-[3fr_2fr]">
        <Definitions summary={summary} />
        <div>
          <p className="font-semibold">Where the numbers come from</p>
          <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
            {facts.map(([label, value]) => (
              <div key={label} className="contents"><dt className="text-ink-2">{label}</dt><dd>{value}</dd></div>
            ))}
          </dl>
          <RunControls total={summary.total_threads} onStart={onStart} onDone={onDone} />
        </div>
      </div>
    </details>
  );
}
