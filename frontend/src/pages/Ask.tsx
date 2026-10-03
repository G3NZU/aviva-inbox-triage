import { useState } from "react";
import type { FormEvent } from "react";
import { ask } from "../api";
import CitationChip from "../components/CitationChip";
import type { QAAnswer } from "../types";

const EXAMPLES = [
  "Was there any action required for Bridgegate Brokers?",
  "What is outstanding on PIN-MTR-552301?",
  "Which threads involve a solicitor?",
  "Are there any new claims (FNOL) that haven't been acknowledged?",
  "Did anyone raise a fraud concern?",
  "What did Harper Broking ask us to do?",
];

/** The answer, or a clearly marked refusal, with the cited messages and what the search looked at. */
function AnswerCard({ result, onOpen }: { result: QAAnswer; onOpen: (key: string, messageId: string) => void }) {
  return (
    <div className="space-y-3">
      {result.refused ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4">
          <div className="text-xs font-semibold uppercase text-amber-800">No answer from the mailbox</div>
          <p className="mt-1 text-sm">{result.answer}</p>
        </div>
      ) : (
        <div className="rounded-lg bg-white p-4 shadow-sm">
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{result.answer}</p>
          <div className="mt-3 text-xs text-slate-500">Model confidence {Math.round(result.confidence * 100)}%</div>
        </div>
      )}
      {result.citations.length > 0 && (
        <div>
          <div className="mb-1 text-xs font-semibold text-slate-600">Sources: click to open the message</div>
          <div className="flex flex-wrap gap-2">
            {result.citations.map((c) => <CitationChip key={c.message_id} citation={c} onOpen={onOpen} />)}
          </div>
        </div>
      )}
      <details className="rounded-lg bg-white p-4 text-sm shadow-sm">
        <summary className="cursor-pointer font-semibold">Why these threads? ({result.retrieved.length} searched)</summary>
        <ul className="mt-2 space-y-1 text-xs">
          {result.retrieved.map((r) => (
            <li key={r.thread_key}>
              <span className="font-mono text-slate-500">{r.score.toFixed(1)}</span> {r.subject}
              <span className="text-slate-500"> — {r.reasons.join("; ")}</span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

/** Free-text questions over the mailbox, answered only from cited emails. */
export default function Ask({ onOpen }: { onOpen: (key: string, messageId: string) => void }) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<QAAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(text: string) {
    if (text.trim().length < 3) return;
    setQuestion(text);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await ask(text.trim()));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void submit(question);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <form onSubmit={onSubmit} className="flex gap-2">
        <input value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={500}
          placeholder="Ask about the mailbox, e.g. “Was there any action required for Bridgegate Brokers?”"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" />
        <button type="submit" disabled={loading}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((example) => (
          <button key={example} onClick={() => void submit(example)} disabled={loading}
            className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs hover:bg-slate-100">
            {example}
          </button>
        ))}
      </div>
      {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</div>}
      {result && <AnswerCard result={result} onOpen={onOpen} />}
      <p className="text-xs text-slate-500">
        Answers come only from the emails, each backed by cited messages; with no evidence, the assistant says so.
      </p>
    </div>
  );
}
