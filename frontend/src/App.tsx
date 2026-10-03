import { useState } from "react";
import Ask from "./pages/Ask";
import Dashboard from "./pages/Dashboard";
import ThreadView from "./pages/ThreadView";

type Tab = "dashboard" | "ask";
type View = { page: Tab } | { page: "thread"; key: string; focus?: string; from: Tab };

/**
 * The app shell and its "router": a state switch between the workload, the Ask page and a thread.
 * Workload and Ask stay mounted (just hidden), so filters and the last answer survive opening a thread.
 */
export default function App() {
  const [view, setView] = useState<View>({ page: "dashboard" });
  const tab: Tab = view.page === "thread" ? view.from : view.page;
  const tabClass = (name: Tab) =>
    `rounded-md px-3 py-1.5 text-sm font-medium ${tab === name ? "bg-white text-slate-900" : "text-slate-300 hover:text-white"}`;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="bg-slate-900 text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div>
            <h1 className="text-lg font-semibold">Inbox triage</h1>
            <p className="text-xs text-slate-400">Pinnacle Insurance claims inbox · recommendations only</p>
          </div>
          <nav className="flex gap-2">
            <button className={tabClass("dashboard")} onClick={() => setView({ page: "dashboard" })}>Workload</button>
            <button className={tabClass("ask")} onClick={() => setView({ page: "ask" })}>Ask the mailbox</button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl p-4">
        <div className={view.page === "dashboard" ? "" : "hidden"}>
          <Dashboard onOpen={(key) => setView({ page: "thread", key, from: "dashboard" })} />
        </div>
        <div className={view.page === "ask" ? "" : "hidden"}>
          <Ask onOpen={(key, focus) => setView({ page: "thread", key, focus, from: "ask" })} />
        </div>
        {view.page === "thread" && (
          <ThreadView threadKey={view.key} focusMessageId={view.focus} onBack={() => setView({ page: view.from })} />
        )}
      </main>
    </div>
  );
}
