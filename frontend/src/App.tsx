import { useCallback, useEffect, useState } from "react";
import { getSummary } from "./api";
import AppHeader from "./components/AppHeader";
import type { Tab } from "./components/AppHeader";
import { formatDayDate } from "./format";
import Ask from "./pages/Ask";
import Dashboard from "./pages/Dashboard";
import ThreadView from "./pages/ThreadView";
import type { Summary } from "./types";

/** Which screen is showing. A thread remembers where it was opened from, the list for Previous / Next, and the
 *  cited message to land on when it came from an answer. */
type View = { page: Tab } | { page: "thread"; key: string; focus?: string; from: Tab; queue?: string[] };

/**
 * Load GET /summary (counts, versions, as-of date, thresholds); `refresh` loads it again after a re-run.
 * A failed reload keeps the last good summary; the error is returned for the workload to show.
 */
function useSummary(): { summary: Summary | null; error: Error | null; refresh: () => void } {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const refresh = useCallback(() => {
    setError(null);
    getSummary().then(setSummary).catch((e: Error) => setError(e));
  }, []);
  useEffect(refresh, [refresh]);
  return { summary, error, refresh };
}

/**
 * After going back, put focus on the row or source that opened the thread, so keyboard users keep their place.
 * If that row sits in a folded group, focus the group's Show button instead (a hidden row cannot take focus).
 */
function useReturnFocus(view: View): (id: string) => void {
  const [target, setTarget] = useState<string | null>(null);
  useEffect(() => {
    if (target && view.page !== "thread") {
      const row = document.getElementById(target);
      const folded = row?.closest<HTMLElement>("[hidden]");
      const showButton = folded && document.querySelector<HTMLElement>(`[aria-controls="${folded.id}"]`);
      (showButton || row)?.focus();
      setTarget(null);
    }
  }, [view, target]);
  return setTarget;
}

/**
 * The app shell and its "router": a state switch between the workload, the Ask page and a thread.
 * Workload and Ask stay mounted (just hidden), so filters and the last answer survive opening a thread.
 */
export default function App() {
  const [view, setView] = useState<View>({ page: "dashboard" });
  const { summary, error: summaryError, refresh } = useSummary();
  const returnFocusTo = useReturnFocus(view);
  const tab: Tab = view.page === "thread" ? view.from : view.page;
  const asOf = summary && <span className="tabular-nums">As of {formatDayDate(summary.as_of)}</span>;
  const back = () => {
    if (view.page !== "thread") return;
    returnFocusTo(view.from === "dashboard" ? `open-${view.key}` : `source-${view.focus}`);
    setView({ page: view.from });
  };

  return (
    <div className="min-h-screen">
      <AppHeader tab={tab} onTab={(page) => setView({ page })} asOf={asOf} />
      <main id="main" className="mx-auto max-w-page px-4 py-5 lg:px-6">
        <div className={view.page === "dashboard" ? "animate-fade-in" : "hidden"}>
          <Dashboard summary={summary} summaryError={summaryError} onRefresh={refresh}
            onOpen={(key, queue) => setView({ page: "thread", key, from: "dashboard", queue })} />
        </div>
        <div className={view.page === "ask" ? "animate-fade-in" : "hidden"}>
          <Ask total={summary?.total_threads ?? null}
            onOpen={(key, focus) => setView({ page: "thread", key, focus, from: "ask" })} />
        </div>
        {view.page === "thread" && (
          <ThreadView threadKey={view.key} focusMessageId={view.focus} queue={view.queue} facts={summary}
            backLabel={view.from === "dashboard" ? "Back to workload" : "Back to answer"} onBack={back}
            onGo={(key) => setView({ ...view, key })} />
        )}
      </main>
    </div>
  );
}
