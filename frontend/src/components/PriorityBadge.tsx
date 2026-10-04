import { CARD } from "../labels";
import type { Card } from "../types";
import Icon from "./Icon";
import type { IconName } from "./Icon";

/** Each state's icon: a different shape per state, so colour is never the only cue (WCAG 1.4.1). */
export const CARD_ICON: Record<Card, IconName> = {
  P1: "alert", P2: "clock", review: "help", P3: "equal", archive: "info", ignore: "minus", untriaged: "dashed",
};

/** Chip colours from the tokens in index.css. Review's dashed border is part of its encoding. */
const CHIP: Record<Card, string> = {
  P1: "border-p1-line bg-p1-bg text-p1-fg",
  P2: "border-p2-line bg-p2-bg text-p2-fg",
  review: "border-dashed border-review-line bg-review-bg text-review-fg",
  P3: "border-p3-line bg-p3-bg text-p3-fg",
  archive: "border-p4-line bg-p4-bg text-p4-fg",
  ignore: "border-line bg-surface text-ignore-fg",
  untriaged: "border-dashed border-ignore-mark bg-surface text-ink-3",
};

/** Icon colours ("mark" tokens), shared with the cards and section headers. */
export const MARK: Record<Card, string> = {
  P1: "text-p1-mark", P2: "text-p2-mark", review: "text-review-mark", P3: "text-p3-mark",
  archive: "text-p4-mark", ignore: "text-ignore-mark", untriaged: "text-ignore-mark",
};

/** Left-edge colours for the count cards, section headers and the thread's decision band. */
export const EDGE: Record<Card, string> = {
  P1: "border-l-p1-mark", P2: "border-l-p2-mark", review: "border-l-review-mark", P3: "border-l-p3-mark",
  archive: "border-l-p4-mark", ignore: "border-l-ignore-mark", untriaged: "border-l-ignore-mark",
};

/** Section-header fills (the chips' soft fills), so each group's start stands out as the list scrolls. */
export const TINT: Record<Card, string> = {
  P1: "bg-p1-bg", P2: "bg-p2-bg", review: "bg-review-bg", P3: "bg-p3-bg", archive: "bg-p4-bg",
  ignore: "bg-surface", untriaged: "bg-surface",
};

/**
 * A thread's place in the workload as a label, never a button: icon plus words ("P1 · Act today"),
 * or just the code ("P1") when `compact` and the surrounding section already says the words.
 */
export default function PriorityBadge({ card, compact = false }: { card: Card; compact?: boolean }) {
  const words = CARD[card];
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 text-xs
      font-semibold ${CHIP[card]}`}>
      <Icon name={CARD_ICON[card]} className={`size-3.5 ${MARK[card]}`} />
      {compact ? words.compact : words.label}
    </span>
  );
}
