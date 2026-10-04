import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { getThreads } from "../api";
import AboutData from "../components/AboutData";
import ErrorPanel from "../components/ErrorPanel";
import Explain from "../components/Explain";
import LineFilter from "../components/LineFilter";
import { WorkloadSkeleton } from "../components/Skeleton";
import SummaryCards from "../components/SummaryCards";
import WorkloadList from "../components/WorkloadList";
import { HELP } from "../help";
import { CARD, LINE } from "../labels";
import type { Card, LineOfBusiness, Summary, ThreadRow } from "../types";
import { groupByCard, matches } from "../workload";

/** Load every thread once, and again whenever `reload` changes. Returns the rows (null while loading) or the error. */
function useThreads(reload: number): { rows: ThreadRow[] | null; error: Error | null } {
  const [rows, setRows] = useState<ThreadRow[] | null>(null);
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    let current = true; // ignore a reply that arrives after a newer request
    setError(null);
    getThreads().then((r) => current && setRows(r)).catch((e: Error) => current && setError(e));
    return () => { current = false; };
  }, [reload]);
  return { rows, error };
}

/** "50 threads, most urgent first", or with a filter "11 of 50 threads: P2 · This week, Motor": read out on change. */
function resultText(shown: number, total: number, card: Card | null, line: LineOfBusiness | null): string {
  const what = [card && CARD[card].label, line && LINE[line]].filter(Boolean).join(", ");
  return what ? `${shown} of ${total} threads: ${what}` : `${total} threads, most urgent first`;
}

/**
 * The result line (a live region holding text only) with the clear button beside it, outside the region.
 * Clearing removes the button, so focus moves to the line instead of being lost.
 */
function ResultLine({ shown, total, card, line, onClear }: {
  shown: number; total: number; card: Card | null; line: LineOfBusiness | null; onClear: () => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  return (
    <div ref={box} tabIndex={-1} className="mr-auto flex flex-wrap items-center gap-x-3 text-sm">
      <p role="status" className="text-ink-2">{resultText(shown, total, card, line)}</p>
      {(card || line) && (
        <button type="button" onClick={() => { onClear(); box.current?.focus(); }}
          className="text-accent underline hover:text-accent-strong">
          Clear filters
        </button>
      )}
    </div>
  );
}

/**
 * Said above the cards when the counts would mislead: nothing loaded yet, or some threads not read by the AI
 * (then every "0" means only "none so far"). The run controls under About this data fix both.
 */
function MailboxNotice({ summary }: { summary: Summary }) {
  const unread = summary.counts.untriaged ?? 0;
  if (summary.total_threads > 0 && unread === 0) return null;
  const empty = summary.total_threads === 0;
  return (
    <div className="rounded-lg border border-line border-l-4 border-l-ink-2 bg-surface p-4 text-sm">
      <p className="font-semibold">{empty ? "No emails loaded yet" : `${unread} of ${summary.total_threads} threads not read by the AI yet`}</p>
      <p className="mt-1 text-ink-2">
        {empty
          ? "Choose Re-run triage under About this data to load and read the mailbox (the AI reads every thread, which "
            + "uses paid API calls), or run the pipeline from the command line as the README describes."
          : "The counts below cover only the threads read so far. Choose Re-run triage under About this data to read the rest."}
      </p>
    </div>
  );
}

/**
 * The bar between the cards and the list: what the list holds (with Clear filters), the line-of-business filter
 * and About this data, which opens by itself when the counts need attention and then spans the width. A run's
 * start and report are read out below it. Props: the summary, the result line and the filter (absent until the
 * threads load), the latest run message, and the run handlers.
 */
function Toolbar({ summary, result, filter, report, onStart, onDone }: {
  summary: Summary | null; result: ReactNode; filter: ReactNode; report: string;
  onStart: (message: string) => void; onDone: (message: string) => void;
}) {
  const needsRun = Boolean(summary && (summary.total_threads === 0 || (summary.counts.untriaged ?? 0) > 0));
  return (
    <div className="flex flex-wrap items-center justify-end gap-x-6 gap-y-2">
      {result}
      {filter}
      {summary && <AboutData summary={summary} startOpen={needsRun} onStart={onStart} onDone={onDone} />}
      <p role="status" className="basis-full text-sm font-semibold"><span key={report} className="animate-fade-in">{report}</span></p>
    </div>
  );
}

/**
 * The workload in one view: the count cards (the only priority filter), a toolbar (what the list holds, the
 * line-of-business filter, About this data with the definitions and re-runs), then every thread in sections,
 * most urgent first.
 * Props: the stored summary (null until loaded; it also feeds the help text) and its load error, the handler that
 * opens a thread (given the keys of the threads shown, in screen order, for Previous / Next), and a summary refresh.
 */
export default function Dashboard({ summary, summaryError, onOpen, onRefresh }: {
  summary: Summary | null; summaryError: Error | null; onOpen: (key: string, queue: string[]) => void;
  onRefresh: () => void;
}) {
  const [card, setCard] = useState<Card | null>(null);
  const [line, setLine] = useState<LineOfBusiness | null>(null);
  const [reload, setReload] = useState(0);
  const [report, setReport] = useState("");
  const { rows, error } = useThreads(reload);
  const refresh = () => { setReload((n) => n + 1); onRefresh(); };
  if (error) return <ErrorPanel error={error} onRetry={refresh} />;
  const shown = rows?.filter((row) => matches(row, card, line)) ?? null;
  const loaded = shown !== null && rows!.length > 0;
  const partial = (summary?.counts.untriaged ?? 0) > 0;
  const waitingHelp = summary && <Explain term="Waiting on us">{HELP.waiting(summary)}</Explain>;
  const open = (key: string) => onOpen(key, [...groupByCard(shown ?? []).values()].flat().map((r) => r.key));
  return (
    <div className="space-y-4">
      {!summary && summaryError && <ErrorPanel error={summaryError} onRetry={onRefresh} />}
      {summary && <MailboxNotice summary={summary} />}
      {summary && summary.total_threads > 0 && <SummaryCards counts={summary.counts} chosen={card} partial={partial} onSelect={setCard} />}
      <Toolbar summary={summary} report={report} onStart={setReport} onDone={(message) => { setReport(message); refresh(); }}
        result={loaded && <ResultLine shown={shown.length} total={rows!.length} card={card} line={line}
          onClear={() => { setCard(null); setLine(null); }} />}
        filter={loaded && <LineFilter value={line} onChange={setLine} />} />
      {!rows && <WorkloadSkeleton />}
      {loaded && (
        <div key={`${card}|${line}`} className="animate-fade-in">
          <WorkloadList rows={shown} chosen={card} line={line} partial={partial} waitingHelp={waitingHelp} onOpen={open} />
        </div>
      )}
    </div>
  );
}
