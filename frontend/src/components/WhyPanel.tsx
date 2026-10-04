import { CARD, ruleText } from "../labels";
import type { Reason, ThreadRow } from "../types";
import Icon from "./Icon";
import { CARD_ICON, MARK } from "./PriorityBadge";

/** A list of reasons in words, each with the state's icon when it decided the priority. */
function ReasonList({ reasons, row }: { reasons: Reason[]; row: ThreadRow }) {
  return (
    <ul className="mt-1 space-y-1">
      {reasons.map((reason, i) => (
        <li key={i} className="flex items-start gap-2">
          {reason.sets_level && <Icon name={CARD_ICON[row.card]} className={`mt-0.5 size-4 ${MARK[row.card]}`} />}
          <span>{ruleText(reason)}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * "Why it is P1 · Act today": the priority rules that set it, in words, then the ones that matched at a lower
 * level. Which is which comes from the API (Reason.sets_level). Props: the thread row (card and reasons).
 */
export default function WhyPanel({ row }: { row: ThreadRow }) {
  if (row.reasons.length === 0) return null; // not read yet: the decision band says so
  const deciding = row.reasons.filter((r) => r.sets_level);
  const alsoTrue = row.reasons.filter((r) => !r.sets_level);
  return (
    <section aria-labelledby="why-heading" className="rounded-lg border border-line bg-surface p-4 text-sm">
      <h3 id="why-heading" className="font-semibold">Why it is {CARD[row.card].label}</h3>
      {deciding.length > 0 && (
        <div className="mt-2">
          <p className="text-ink-2">Set by the priority rules:</p>
          <ReasonList reasons={deciding} row={row} />
        </div>
      )}
      {alsoTrue.length > 0 && (
        <div className="mt-3 text-ink-2">
          <p>Also true, but it did not change the priority:</p>
          <ReasonList reasons={alsoTrue} row={row} />
        </div>
      )}
    </section>
  );
}
