import { percent } from "../format";
import type { QAAnswer } from "../types";
import Icon from "./Icon";

/**
 * "How the sources were found", folded: how the keyword search ranks threads, then each match with the API's
 * reasons and a rounded score. The open workload is always read too, so an answer can rest on it alone.
 * Props: the reply.
 */
export function HowFound({ result }: { result: QAAnswer }) {
  const n = result.retrieved.length;
  if (n === 0) {
    const basis = result.refused ? "" : ": the answer rests on the open workload";
    return <p className="text-sm text-ink-2">No email shares words with your question{basis}.</p>;
  }
  const found = `${n} thread${n === 1 ? "" : "s"} ${result.refused ? "looked at, none answered it" : "matched your question"}`;
  return (
    <details className="group rounded-lg border border-line bg-surface p-4 text-sm">
      <summary className="flex cursor-pointer list-none items-center gap-1 font-semibold [&::-webkit-details-marker]:hidden">
        <Icon name="chevronRight" className="size-4 group-open:rotate-90 motion-safe:transition-transform" />
        How the sources were found: {found}
      </summary>
      <p className="mt-2 text-ink-2">
        A keyword search ranks the threads: a claim reference counts most, then a company name in an email address on the thread,
        then the AI's tags, then shared words. The AI also reads the open workload, in the priority rules' order.
      </p>
      <ol className="mt-2 space-y-1.5">
        {result.retrieved.map((r) => (
          <li key={r.thread_key} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3">
            <span><span className="font-semibold">{r.subject}</span>
              <span className="text-ink-2"> — {r.reasons.join("; ")}</span></span>
            <span className="text-xs text-ink-3 tabular-nums">score {Math.round(r.score)}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}

/**
 * The reply to a question: the AI's answer with its own confidence, or a neutral "No answer given" card showing
 * the stored sentence (a refusal can mean no evidence or an unusable reply, so the title claims neither).
 * Props: the reply.
 */
export default function AnswerCard({ result }: { result: QAAnswer }) {
  if (result.refused) {
    return (
      <div className="rounded-lg border border-line border-l-4 border-l-ink-2 bg-surface p-4">
        <p className="flex items-center gap-2 font-semibold"><Icon name="info" className="size-5 text-ink-2" />No answer given</p>
        <p className="mt-1">{result.answer}</p>
        <p className="mt-2 text-sm text-ink-2">
          If the emails should cover this, try a claim reference (PIN-…), a company name or a sender's email address.
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <p className="font-semibold">AI answer</p>
      <p className="mt-2 max-w-prose whitespace-pre-wrap">{result.answer}</p>
      <p className="mt-3 text-xs text-ink-2 tabular-nums">Confidence {percent(result.confidence)} (the AI's own estimate)</p>
    </div>
  );
}
