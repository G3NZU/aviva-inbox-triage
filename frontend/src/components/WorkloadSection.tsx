import { useId, useState } from "react";
import { CARD } from "../labels";
import type { Card, ThreadRow as ThreadRowData } from "../types";
import { NO_ACTION } from "../workload";
import Icon from "./Icon";
import { CARD_ICON, EDGE, MARK, TINT } from "./PriorityBadge";
import ThreadRow from "./ThreadRow";

/**
 * One group of the workload: a header (icon, name, count) and its threads in the API's order, or one
 * sentence when it is empty. The no-action groups start folded behind a Show button.
 * Props: the card, its rows, whether to force it open (when its card is the chosen filter), the sentence to
 * show when empty, and the open handler.
 */
export default function WorkloadSection({ card, rows, forceOpen, emptyText, onOpen }: {
  card: Card; rows: ThreadRowData[]; forceOpen: boolean; emptyText: string; onOpen: (key: string) => void;
}) {
  const foldable = NO_ACTION.has(card) && rows.length > 0;
  const [open, setOpen] = useState(false);
  const shown = !foldable || open || forceOpen;
  const listId = useId();
  const words = CARD[card];
  return (
    <section aria-labelledby={`${listId}-h`} className="border-t border-line first:border-t-0">
      <div className={`flex flex-wrap items-center gap-x-2 gap-y-1 border-l-4 px-4 py-2.5 ${EDGE[card]} ${TINT[card]}`}>
        <Icon name={CARD_ICON[card]} className={`size-4 ${MARK[card]}`} />
        <h3 id={`${listId}-h`} className="font-semibold">
          {words.label} <span className="font-normal text-ink-2 tabular-nums">· {rows.length}</span>
        </h3>
        {foldable && !forceOpen && (
          <button type="button" aria-expanded={shown} aria-controls={listId} onClick={() => setOpen(!open)}
            className="group ml-auto inline-flex min-h-6 items-center gap-1 rounded px-2 text-sm
              text-accent hover:text-accent-strong hover:underline">
            {shown ? "Hide" : `Show ${rows.length}`}
            <Icon name="chevronDown" className="size-4 group-aria-expanded:rotate-180 motion-safe:transition-transform" />
          </button>
        )}
      </div>
      {rows.length === 0
        ? <p className="border-t border-line px-4 py-3 text-sm text-ink-2">{emptyText}</p>
        : (
          <ol id={listId} hidden={!shown}>
            {rows.map((row) => <ThreadRow key={row.key} row={row} onOpen={onOpen} />)}
          </ol>
        )}
    </section>
  );
}
