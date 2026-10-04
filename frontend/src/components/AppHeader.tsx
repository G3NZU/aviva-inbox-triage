import type { ReactNode } from "react";
import { useTheme } from "../theme";
import Icon from "./Icon";

export type Tab = "dashboard" | "ask";

const TABS: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "Workload" },
  { id: "ask", label: "Ask the mailbox" },
];

/**
 * The top of every screen, on the coloured header band: what this is, the promise that it only suggests, the
 * as-of date, the two tabs and the "Dark mode" toggle (pressed = dark; its name never changes). A "skip" link
 * (visible when focused) lets keyboard users jump straight to the content. On the band, focus outlines are
 * white: the usual accent outline would vanish against it.
 * Props: the active tab, a handler to switch, and the as-of line (rendered once the summary has loaded).
 */
export default function AppHeader({ tab, onTab, asOf }: { tab: Tab; onTab: (tab: Tab) => void; asOf?: ReactNode }) {
  const [theme, toggleTheme] = useTheme();
  return (
    <header className="bg-header text-header-ink">
      <a href="#main" className="sr-only rounded bg-surface px-3 py-2 text-sm font-semibold text-accent-strong
        focus-visible:outline-header-ink focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-50">
        Skip to the content
      </a>
      <div className="mx-auto flex max-w-page flex-wrap items-end justify-between gap-x-8 gap-y-2 px-4 pt-3 lg:px-6">
        <div className="pb-3">
          <h1 className="text-base font-semibold">Claims inbox triage</h1>
          <p className="text-xs text-header-ink-2">
            Pinnacle Insurance · Suggestions only: nothing is sent, archived or deleted
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-x-6">
          {asOf && <div className="pb-3 text-sm text-header-ink-2">{asOf}</div>}
          <nav aria-label="Screens" className="flex gap-1">
            {TABS.map(({ id, label }) => (
              <button key={id} type="button" onClick={() => onTab(id)} aria-current={tab === id ? "page" : undefined}
                className="border-b-2 border-transparent px-3 pb-2.5 pt-1 text-sm font-semibold text-header-ink-2
                  transition-colors duration-150 ease-standard hover:text-header-ink focus-visible:outline-header-ink
                  aria-[current=page]:border-header-ink aria-[current=page]:text-header-ink">
                {label}
              </button>
            ))}
          </nav>
          <button type="button" aria-pressed={theme === "dark"} onClick={toggleTheme}
            className="mb-2 inline-flex items-center gap-1.5 rounded-md border border-header-ink-2 px-2.5 py-0.5
              text-sm font-semibold text-header-ink-2 transition-colors duration-150 ease-standard
              hover:border-header-ink hover:text-header-ink focus-visible:outline-header-ink
              aria-pressed:border-header-ink aria-pressed:bg-header-ink aria-pressed:text-header">
            <Icon name="moon" className="size-4" />
            Dark mode
          </button>
        </div>
      </div>
    </header>
  );
}
