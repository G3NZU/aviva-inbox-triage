import type { ReactNode } from "react";
import { percent } from "../format";
import type { HelpFacts } from "../help";
import { ACTION, CATEGORY, LINE, RATING, SENDER, SIGNALS } from "../labels";
import type { ThreadDetail } from "../types";

/** One labelled fact. */
function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-ink-2">{label}</dt>
      <dd>{children}</dd>
    </>
  );
}

/**
 * "The AI's reading": what the model reported about the thread, kept apart from the rules that set the
 * priority. Confidence is shown with the threshold below which a person checks (from the API's policy).
 * Props: the thread detail, and the help facts (null until GET /summary has loaded).
 */
export default function AiReading({ detail, facts }: { detail: ThreadDetail; facts: HelpFacts | null }) {
  const triage = detail.triage;
  if (!triage) return <p className="rounded-lg border border-line bg-surface p-4 text-sm">The AI has not read this thread yet.</p>;
  const r = triage.result;
  // The fallback's fields are placeholders, not a reading: show only its reason ("Automatic triage failed: …").
  if (triage.error) return <p className="rounded-lg border border-line bg-surface p-4 text-sm">{r.reasoning}</p>;
  return (
    <section aria-labelledby="ai-heading" className="rounded-lg border border-line bg-surface p-4 text-sm">
      <h3 id="ai-heading" className="font-semibold">The AI's reading</h3>
      <dl className="mt-2 grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-1.5">
        <Fact label="What it is">{CATEGORY[r.category]}</Fact>
        <Fact label="Action type">{ACTION[r.action_type]}</Fact>
        <Fact label="Line of business">{LINE[r.line_of_business]}</Fact>
        <Fact label="Sender">{SENDER[r.sender_type]}</Fact>
        <Fact label="How soon">{RATING[r.urgency]}</Fact>
        <Fact label="What's at stake">{RATING[r.importance]}</Fact>
        <Fact label="What it spotted">
          <span className="flex flex-wrap gap-1">
            {r.signals.length === 0 && <span className="text-ink-3">Nothing</span>}
            {r.signals.map((s) => <span key={s} className="rounded bg-sunken px-1.5 py-0.5 text-xs">{SIGNALS[s].label}</span>)}
          </span>
        </Fact>
        <Fact label="Confidence">
          <span className="tabular-nums">{percent(r.confidence)}</span>
          {facts && <span className="text-ink-2"> · Needs a check below {percent(facts.policy.confidence_threshold)}</span>}
          {detail.thread.card === "review" && <span className="ml-2 rounded bg-review-bg px-1.5 text-xs text-review-fg">Sent to Needs a check</span>}
        </Fact>
      </dl>
      <p className="mt-3 font-semibold">The AI's note</p>
      <p className="mt-1">{r.reasoning}</p>
    </section>
  );
}
