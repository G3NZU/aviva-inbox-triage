import type { ReactNode } from "react";
import { CARD, LINE, PARTIAL_EMPTY } from "../labels";
import type { Card, LineOfBusiness, ThreadRow as ThreadRowData } from "../types";
import { groupByCard, SECTION_ORDER } from "../workload";
import { ROW_GRID } from "./ThreadRow";
import WorkloadSection from "./WorkloadSection";

/**
 * What an empty section says. The full sentence ("Nothing to act on today.") is only true for the whole inbox,
 * so a line filter gets a scoped one, and unread threads make any "none" provisional.
 */
function emptyText(card: Card, line: LineOfBusiness | null, partial: boolean): string {
  if (partial) return `${PARTIAL_EMPTY}.`;
  return line ? `No ${CARD[card].label} threads for ${LINE[line]}.` : CARD[card].empty;
}

/**
 * The workload as one list of sections, most urgent first (see workload.ts), under column labels. Empty groups
 * are left out (their cards already say 0) unless chosen as the filter, which shows only that section, opened.
 * Props: the rows to show (already filtered), the card and line chosen as filters, whether some threads are
 * unread, the (i) for "Waiting on us", and the open handler.
 */
export default function WorkloadList({ rows, chosen, line, partial, waitingHelp, onOpen }: {
  rows: ThreadRowData[]; chosen: Card | null; line: LineOfBusiness | null; partial: boolean;
  waitingHelp?: ReactNode; onOpen: (key: string) => void;
}) {
  const groups = groupByCard(rows);
  const visible = SECTION_ORDER.filter((card) => (chosen ? card === chosen : groups.get(card)!.length > 0));
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface">
      <h2 className="sr-only">Threads, most urgent first</h2>
      <div className={`${ROW_GRID} items-center border-b border-line bg-sunken px-4 py-2 text-xs font-semibold text-ink-2`}>
        <span>Priority</span>
        <span>What to do, and why</span>
        <span className="hidden lg:block">Claim</span>
        <span className="hidden lg:block">From</span>
        <span className="hidden items-center justify-end gap-1 sm:flex">Waiting on us {waitingHelp}</span>
        <span />
      </div>
      {visible.map((card) => (
        <WorkloadSection key={card} card={card} rows={groups.get(card)!} forceOpen={chosen === card}
          emptyText={emptyText(card, line, partial)} onOpen={onOpen} />
      ))}
      {visible.length === 0 && <p className="px-4 py-3 text-sm text-ink-2">No threads match the line of business chosen.</p>}
    </div>
  );
}
