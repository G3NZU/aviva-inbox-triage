import { useRef, useState } from "react";
import type { FormEvent, RefObject } from "react";
import { ask } from "../api";
import AnswerCard, { HowFound } from "../components/AnswerCard";
import AskIntro from "../components/AskIntro";
import ErrorPanel from "../components/ErrorPanel";
import SourceList from "../components/SourceList";
import type { QAAnswer } from "../types";

const MIN_LENGTH = 3; // the API rejects shorter questions (AskRequest in backend/app/main.py)

/** Send a question and track the reply: the question asked, the answer, whether it is pending, any error. */
function useQuestion() {
  const [asked, setAsked] = useState("");
  const [result, setResult] = useState<QAAnswer | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  async function send(text: string) {
    setAsked(text);
    setPending(true);
    setError(null);
    setResult(null);
    try {
      setResult(await ask(text));
    } catch (e) {
      setError(e as Error);
    } finally {
      setPending(false);
    }
  }
  return { asked, result, pending, error, send };
}

/** What a screen reader hears as the question goes out and the reply arrives. */
function statusText(pending: boolean, result: QAAnswer | null): string {
  if (pending) return "Searching the mailbox and writing an answer with its sources.";
  if (!result) return "";
  const n = result.citations.length;
  return result.refused ? "No answer given." : `Answer ready, ${n} source${n === 1 ? "" : "s"}.`;
}

/** A calm placeholder in the answer's shape while the reply is on its way (it pulses only if motion is allowed). */
function Waiting() {
  return (
    <div aria-hidden="true" className="space-y-2 rounded-lg border border-line bg-surface p-4">
      {["w-11/12", "w-full", "w-2/3"].map((w) => <div key={w} className={`h-3 rounded bg-sunken motion-safe:animate-pulse ${w}`} />)}
    </div>
  );
}

/**
 * The question box: a visible label, the input and the Ask button, a too-short error (an alert) and the helper
 * text. The input stays editable while an answer is pending. Props: the value and its setter, the input's ref,
 * whether the last submit was too short or is pending, the thread total, and the submit handler.
 */
function QuestionForm({ question, setQuestion, input, tooShort, pending, total, onSubmit }: {
  question: string; setQuestion: (text: string) => void; input: RefObject<HTMLInputElement | null>;
  tooShort: boolean; pending: boolean; total: number | null; onSubmit: (event: FormEvent) => void;
}) {
  return (
    <form onSubmit={onSubmit} noValidate className="space-y-1.5">
      <label htmlFor="question" className="block text-sm font-semibold">Ask a question about the mailbox</label>
      <div className="flex gap-2">
        <input ref={input} id="question" value={question} maxLength={500} onChange={(e) => setQuestion(e.target.value)}
          aria-describedby={tooShort ? "question-help question-error" : "question-help"} aria-invalid={tooShort || undefined}
          placeholder="e.g. What is outstanding on PIN-MTR-552301?"
          className="min-w-0 flex-1 rounded-md border border-line-strong bg-surface px-3 py-2 placeholder:text-ink-3" />
        <button type="submit" aria-disabled={pending}
          className="rounded-md bg-accent px-4 py-2 font-semibold text-on-accent hover:bg-accent-strong aria-disabled:bg-ink-3">
          {pending ? "Asking…" : "Ask"}
        </button>
      </div>
      <p id="question-error" role="alert" className="text-sm text-p1-fg">{tooShort ? `Type at least ${MIN_LENGTH} characters.` : ""}</p>
      <p id="question-help" className="text-sm text-ink-2">
        Answers use only the {total ?? "stored"} threads in this mailbox and the priority rules, and cite their emails.
        It can't read attachments or take any action. Every question is logged.
      </p>
    </form>
  );
}

/**
 * Free-text questions over the mailbox, answered only from cited emails and the rules' workload. Says in one
 * line what it can and cannot do, offers examples, keeps the question in the box, shows an honest wait, then
 * the answer beside its sources on wide screens (or a clear no).
 * Props: the handler that opens a thread at a cited message, and the thread total from GET /summary.
 */
export default function Ask({ onOpen, total }: {
  onOpen: (key: string, messageId: string) => void; total: number | null;
}) {
  const [question, setQuestion] = useState("");
  const [tooShort, setTooShort] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const { asked, result, pending, error, send } = useQuestion();
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    setTooShort(text.length < MIN_LENGTH);
    if (text.length < MIN_LENGTH) input.current?.focus(); // the input then reads out its error
    else if (!pending) void send(text);
  }
  const fill = (example: string) => { setQuestion(example); setTooShort(false); input.current?.focus(); };
  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <h2 className="mx-auto max-w-3xl text-xl font-semibold">Ask the mailbox</h2>
      <div className="mx-auto max-w-3xl space-y-3">
        <QuestionForm question={question} setQuestion={setQuestion} input={input} tooShort={tooShort} pending={pending}
          total={total} onSubmit={onSubmit} />
        <AskIntro onExample={fill} />
      </div>
      <p role="status" className="sr-only">{statusText(pending, result)}</p>
      {asked && (
        <section aria-labelledby="asked-heading" aria-busy={pending} className="max-w-5xl space-y-3">
          <h3 id="asked-heading" className="font-semibold">You asked: {asked}</h3>
          {pending && <><p className="text-sm text-ink-2">Searching the mailbox and writing an answer with its sources…</p><Waiting /></>}
          {error && <ErrorPanel error={error} onRetry={() => void send(asked)} />}
          {result && (
            <div key={asked} className="grid animate-enter gap-4 motion-reduce:animate-fade-in
              lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start">
              <AnswerCard result={result} />
              <div className="space-y-4">
                {result.citations.length > 0 && <SourceList citations={result.citations} onOpen={onOpen} />}
                <HowFound result={result} />
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
