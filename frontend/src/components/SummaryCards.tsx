import { CARD, PARTIAL_EMPTY } from "../labels";
import type { Card } from "../types";
import Icon from "./Icon";
import { CARD_ICON, EDGE, MARK } from "./PriorityBadge";

const GROUPS: { label: string; cards: Card[]; grid: string }[] = [
  { label: "Needs action", cards: ["P1", "P2", "review", "P3"], grid: "grid-cols-2 sm:grid-cols-4" },
  { label: "No action", cards: ["archive", "ignore"], grid: "grid-cols-2" },
];

/**
 * One count card: a toggle button (aria-pressed); its name stays the same whether pressed or not. Its left edge
 * has its section header's colour, so the cards double as the list's legend.
 */
function CountCard({ card, count, selected, partial, onSelect }: {
  card: Card; count: number; selected: boolean; partial: boolean; onSelect: (card: Card | null) => void;
}) {
  const words = CARD[card];
  const tone = count === 0 ? "text-ink-3" : card === "P1" ? "text-p1-mark" : "text-ink";
  return (
    <button type="button" aria-pressed={selected} onClick={() => onSelect(selected ? null : card)}
      className={`group flex flex-col rounded-lg border-2 border-l-4 border-line ${EDGE[card]} bg-surface px-3 py-2
        text-left shadow-xs transition-[translate,box-shadow,border-color,background-color] duration-150
        ease-standard hover:shadow-md motion-safe:hover:-translate-y-0.5 active:translate-y-0
        aria-pressed:border-accent aria-pressed:bg-accent-soft`}>
      <span className="flex items-center gap-2">
        <Icon name={CARD_ICON[card]} className={`size-4 shrink-0 ${MARK[card]} group-aria-pressed:hidden`} />
        <Icon name="check" className="hidden size-4 shrink-0 text-accent group-aria-pressed:block" />
        <span className="flex-1 text-sm font-semibold">{words.label}</span>
        <span key={count} className={`animate-fade-in text-2xl font-semibold tabular-nums ${tone}`}>{count}</span>
      </span>
      <span className="text-xs text-ink-2">{count > 0 ? words.hint : partial ? PARTIAL_EMPTY : words.zeroHint}</span>
    </button>
  );
}

/**
 * The workload at a glance and the only priority filter: one card per group, in the list's order, split
 * into "Needs action" and "No action". Clicking a card shows only that group; clicking it again shows all.
 * Props: the stored counts from GET /summary, the chosen card and a setter, and whether some threads are still
 * unread (then a zero is not "none", only "none so far"). What each group means is listed under About this data.
 */
export default function SummaryCards({ counts, chosen, partial, onSelect }: {
  counts: Record<string, number>; chosen: Card | null; partial: boolean; onSelect: (card: Card | null) => void;
}) {
  return (
    <div className="flex flex-wrap gap-x-8 gap-y-3">
      {GROUPS.map((group, i) => (
        <section key={group.label} aria-label={group.label}
          className={i === 0 ? "basis-full lg:basis-0 lg:grow-[4]" : "basis-full sm:basis-1/2 lg:basis-0 lg:grow-[2]"}>
          <h2 className="mb-1.5 text-xs font-semibold text-ink-2">{group.label}</h2>
          <div className={`grid gap-3 ${group.grid}`}>
            {group.cards.map((card) => (
              <CountCard key={card} card={card} count={counts[card] ?? 0} selected={chosen === card} partial={partial}
                onSelect={onSelect} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
