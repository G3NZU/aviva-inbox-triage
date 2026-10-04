import { workingDays } from "../format";
import { CARD, decidingText, LINE, SENDER } from "../labels";
import type { ThreadRow as ThreadRowData } from "../types";
import { NO_ACTION } from "../workload";
import Icon from "./Icon";
import PriorityBadge from "./PriorityBadge";

/**
 * Grid shared with the column labels in WorkloadList: chip | what to do | (claim | from) | waiting | chevron.
 * Below 640 px the waiting cell moves into the line under the title, so the title is never squeezed.
 */
export const ROW_GRID = "grid grid-cols-[auto_minmax(0,1fr)_auto] gap-x-3 sm:grid-cols-[auto_minmax(0,1fr)_auto_auto] "
  + "sm:gap-x-4 lg:grid-cols-[6.5rem_minmax(0,1fr)_9.5rem_9rem_8.5rem_1rem]";

/**
 * How long the sender has waited on us, in words. Threads that need no action show a dash (a wait on spam
 * means nothing). The clock and amber appear only when the waiting rule is what set the priority.
 */
function Waiting({ row }: { row: ThreadRowData }) {
  if (row.card === "untriaged") return <span className="text-ink-3"><span className="sr-only">Waiting: not counted yet </span>—</span>;
  if (NO_ACTION.has(row.card)) return <span className="text-ink-3"><span className="sr-only">Waiting: </span>—</span>;
  const decided = row.reasons.some((r) => r.rule === "p2_unanswered" && r.sets_level);
  return (
    <span className={`inline-flex items-center gap-1 ${decided ? "font-semibold text-p2-fg" : row.waiting_days ? "" : "text-ink-3"}`}>
      {decided && <Icon name="clock" className="size-3.5 text-p2-mark" />}
      <span className="sr-only">Waiting on us: </span>{workingDays(row.waiting_days)}
    </span>
  );
}

/**
 * One thread in the workload list. The whole row is one button (stretched over the row), so it opens by
 * click, tap or Enter; its name carries the priority words and the line of business for screen readers (the
 * chip cell that shows them is hidden from them, so each is heard once). Shows what to do, why (the rules
 * that set the priority, in words), the line of business under the chip (nothing until the AI has read the
 * thread), the claim, who it is from and how long they have waited.
 * Props: the row and the handler that opens the thread.
 */
export default function ThreadRow({ row, onOpen }: { row: ThreadRowData; onOpen: (key: string) => void }) {
  const noAction = NO_ACTION.has(row.card);
  const line = row.line_of_business ? LINE[row.line_of_business] : null;
  const meta = `${row.claim_ref ?? "No claim ref"} · ${row.sender_type ? SENDER[row.sender_type] : "Unknown sender"}`;
  return (
    <li className={`relative ${ROW_GRID} items-start border-t border-line px-4 py-3 transition-colors duration-150
      ease-standard hover:bg-sunken has-[:focus-visible]:bg-sunken has-[:focus-visible]:outline-2
      has-[:focus-visible]:-outline-offset-2 has-[:focus-visible]:outline-accent`}>
      <div className="flex flex-col items-start gap-1" aria-hidden="true">
        <PriorityBadge card={row.card} compact />
        {line && <span className="text-xs text-ink-2">{line}</span>}
      </div>
      <div className="min-w-0">
        <button type="button" id={`open-${row.key}`} onClick={() => onOpen(row.key)}
          className={`text-left [overflow-wrap:anywhere] after:absolute after:inset-0 after:content-['']
            focus-visible:outline-hidden ${noAction ? "text-ink-2" : "text-ink"}`}>
          <span className="sr-only">{CARD[row.card].label}{line && `, ${line}`}: </span>
          <span className="line-clamp-2">{row.action_summary || row.subject}</span>
        </button>
        <p className="mt-0.5 text-sm text-ink-2">
          Why: {row.card === "untriaged" ? "not read by the AI yet" : decidingText(row.reasons) || "—"}
        </p>
        <p className="mt-0.5 text-xs text-ink-3 lg:hidden">
          {meta}<span className="sm:hidden"> · <Waiting row={row} /></span>
        </p>
      </div>
      <div className="relative z-10 hidden pt-0.5 text-sm lg:block">
        {row.claim_ref
          ? <span className="select-all"><span className="sr-only">Claim: </span>{row.claim_ref}</span>
          : <span className="text-ink-3">No claim ref</span>}
      </div>
      <div className="hidden pt-0.5 text-sm lg:block">
        <span className="sr-only">From: </span>{row.sender_type ? SENDER[row.sender_type] : "Unknown sender"}
      </div>
      <div className="hidden whitespace-nowrap pt-0.5 text-right text-sm tabular-nums sm:block"><Waiting row={row} /></div>
      <Icon name="chevronRight" className="mt-1 size-4 text-ink-3" />
    </li>
  );
}
