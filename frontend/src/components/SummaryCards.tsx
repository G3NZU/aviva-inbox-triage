import type { Filters, Summary } from "../types";

interface Card {
  id: string; // key in Summary.counts
  title: string;
  hint: string;
  filters: Filters; // what clicking the card shows
  colour: string;
}

const CARDS: Card[] = [
  { id: "P1", title: "P1", hint: "act today", filters: { bucket: "act", level: "P1" }, colour: "border-red-500" },
  { id: "P2", title: "P2", hint: "this week", filters: { bucket: "act", level: "P2" }, colour: "border-amber-500" },
  { id: "P3", title: "P3", hint: "normal", filters: { bucket: "act", level: "P3" }, colour: "border-sky-600" },
  { id: "review", title: "Review", hint: "model unsure: a human checks", filters: { bucket: "review" }, colour: "border-violet-600" },
  { id: "archive", title: "P4 · Archive", hint: "informational, no action", filters: { bucket: "archive" }, colour: "border-slate-400" },
  { id: "ignore", title: "Ignore", hint: "not claims work", filters: { bucket: "ignore" }, colour: "border-slate-200" },
];

/** True when two filter sets select the same threads. */
function sameFilters(a: Filters, b: Filters): boolean {
  return a.bucket === b.bucket && a.level === b.level && a.lob === b.lob;
}

/** The workload at a glance: one card per priority level or bucket; clicking a card filters the list. */
export default function SummaryCards({ summary, active, onSelect }: {
  summary: Summary;
  active: Filters;
  onSelect: (filters: Filters) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {CARDS.map((card) => {
        const selected = sameFilters(active, card.filters);
        return (
          <button
            key={card.id}
            onClick={() => onSelect(selected ? {} : card.filters)}
            className={`rounded-lg border-l-4 bg-white p-3 text-left shadow-sm hover:shadow ${card.colour} ${
              selected ? "ring-2 ring-slate-900" : ""
            }`}
          >
            <div className="text-2xl font-bold">{summary.counts[card.id] ?? 0}</div>
            <div className="text-sm font-semibold">{card.title}</div>
            <div className="text-xs text-slate-500">{card.hint}</div>
          </button>
        );
      })}
    </div>
  );
}
