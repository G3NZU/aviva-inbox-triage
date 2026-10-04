import { useEffect, useRef, useState } from "react";
import { getThread } from "../api";
import AiReading from "../components/AiReading";
import AuditPanel from "../components/AuditPanel";
import DecisionBand from "../components/DecisionBand";
import ErrorPanel from "../components/ErrorPanel";
import Explain from "../components/Explain";
import MessageCard from "../components/MessageCard";
import PriorityBadge from "../components/PriorityBadge";
import { ThreadSkeleton } from "../components/Skeleton";
import ThreadNav from "../components/ThreadNav";
import WhyPanel from "../components/WhyPanel";
import { formatShortDay } from "../format";
import { HELP } from "../help";
import type { HelpFacts } from "../help";
import { LINE } from "../labels";
import type { ThreadDetail } from "../types";

/**
 * Load one thread. The previous thread stays on screen (dimmed) while the next loads, so Previous / Next does
 * not flash; a reply that arrives after a newer request is ignored. Returns the detail, loading, error, retry.
 */
function useThread(key: string) {
  const [detail, setDetail] = useState<ThreadDetail | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let current = true;
    setError(null);
    getThread(key).then((d) => current && setDetail(d)).catch((e: Error) => current && setError(e));
    return () => { current = false; };
  }, [key, attempt]);
  const loading = !error && detail?.thread.key !== key;
  return { detail, loading, error, retry: () => setAttempt((n) => n + 1) };
}

/** Move focus to the thread's heading (for screen readers and keyboard users) and, if opened from an answer,
 *  scroll to the cited email; smooth scrolling only when the user has not asked for reduced motion. */
function useArrivalFocus(detail: ThreadDetail | null, focusMessageId?: string) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!detail) return;
    heading.current?.focus({ preventScroll: Boolean(focusMessageId) });
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (focusMessageId) {
      document.getElementById(focusMessageId)?.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
    }
  }, [detail, focusMessageId]);
  return heading;
}

/** "PIN-HOM-501772 · Home · 2 emails, Sun 1 Feb to Mon 2 Feb" — the thread's identity at a glance. */
function metaLine(detail: ThreadDetail): string {
  const { thread, messages, triage } = detail;
  const line = triage ? LINE[triage.result.line_of_business] : "Not read yet";
  const span = `${messages.length} email${messages.length === 1 ? "" : "s"}, ${formatShortDay(thread.first_date)}`
    + (messages.length > 1 ? ` to ${formatShortDay(thread.last_date)}` : "");
  return `${thread.claim_ref ?? "No claim ref"} · ${line} · ${span}`;
}

/** The emails, oldest first; in long threads the older ones fold to one line (never the latest or a cited one). */
function Emails({ detail, focusMessageId }: { detail: ThreadDetail; focusMessageId?: string }) {
  const last = detail.messages.length - 1;
  return (
    <section aria-labelledby="emails-heading" className="space-y-3">
      <h3 id="emails-heading" className="text-sm font-semibold">Emails ({detail.messages.length})</h3>
      {detail.messages.map((m, i) => (
        <MessageCard key={m.message_id} message={m} latest={i === last} cited={m.message_id === focusMessageId}
          folded={detail.messages.length >= 3 && i !== last && m.message_id !== focusMessageId} />
      ))}
    </section>
  );
}

/**
 * One thread, in the order a handler decides: the suggested next step and how pressing it is; why it has its
 * priority (set by the rules); the emails (the evidence); how the AI read it; then the audit record.
 * Props: the thread key, the cited message to land on (from Ask), the Back label, the list for Previous / Next,
 * the help facts from GET /summary, and the handlers.
 */
export default function ThreadView({ threadKey, focusMessageId, backLabel, queue, facts, onBack, onGo }: {
  threadKey: string; focusMessageId?: string; backLabel: string; queue?: string[]; facts: HelpFacts | null;
  onBack: () => void; onGo: (key: string) => void;
}) {
  const { detail, loading, error, retry } = useThread(threadKey);
  const heading = useArrivalFocus(detail, focusMessageId);
  const nav = <ThreadNav backLabel={backLabel} queue={queue} current={threadKey} onBack={onBack} onGo={onGo} />;
  if (error) return <div className="space-y-4">{nav}<ErrorPanel error={error} onRetry={retry} /></div>;
  if (!detail) return <div className="space-y-4" aria-busy="true">{nav}<ThreadSkeleton /></div>;
  const waitingHelp = facts && <Explain term="Waiting on us">{HELP.waiting(facts)}</Explain>;
  return (
    <div className="space-y-4">
      {nav}
      <div key={detail.thread.key} aria-busy={loading}
        className={`animate-enter space-y-4 motion-reduce:animate-fade-in ${loading ? "opacity-60 transition-opacity" : ""}`}>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <PriorityBadge card={detail.thread.card} />
            <h2 ref={heading} tabIndex={-1} className="text-xl font-semibold">{detail.thread.subject}</h2>
          </div>
          <p className="mt-1 text-sm text-ink-2 tabular-nums">{metaLine(detail)}</p>
        </div>
        <DecisionBand detail={detail} waitingHelp={waitingHelp} />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_24rem] lg:grid-rows-[auto_auto_1fr] lg:items-start">
          <div className="lg:col-start-2 lg:row-start-1">
            <WhyPanel row={detail.thread} />
          </div>
          <div className="lg:col-start-1 lg:row-span-3 lg:row-start-1">
            <Emails detail={detail} focusMessageId={focusMessageId} />
          </div>
          <div className="lg:col-start-2"><AiReading detail={detail} facts={facts} /></div>
          <div className="lg:col-start-2"><AuditPanel detail={detail} /></div>
        </div>
      </div>
    </div>
  );
}
