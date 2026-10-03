import { Fragment, useEffect, useState } from "react";
import { getThread } from "../api";
import PriorityBadge from "../components/PriorityBadge";
import { formatDate, formatDateTime, humanise } from "../format";
import type { Message, ThreadDetail, TriageRecord } from "../types";

/** One email: header, attachments and body; the latest and any cited message are highlighted. */
function MessageCard({ message, latest, focused }: { message: Message; latest: boolean; focused: boolean }) {
  const internal = message.from_internal;
  const border = focused ? "border-amber-400 ring-2 ring-amber-300" : latest ? "border-sky-500" : "border-slate-200";
  return (
    <article id={message.message_id} className={`rounded-lg border-2 p-4 ${border} ${internal ? "bg-slate-50" : "bg-white"}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span>{formatDateTime(message.date_sent)}</span>
        {latest && <span className="rounded bg-sky-100 px-1.5 font-semibold text-sky-800">latest: current state</span>}
        {internal && <span className="rounded bg-slate-200 px-1.5">Pinnacle (internal)</span>}
        {message.importance_flag && <span className="rounded bg-slate-100 px-1.5">sender flag: {message.importance_flag} (not used)</span>}
      </div>
      <div className="text-sm"><strong>{message.sent_from}</strong> → {message.sent_to.join(", ")}</div>
      {message.sent_cc.length > 0 && <div className="text-xs text-slate-500">cc {message.sent_cc.join(", ")}</div>}
      <div className="mt-1 font-semibold">{message.subject}</div>
      {message.attachments.length > 0 && (
        <div className="mt-1 text-xs text-slate-500">📎 {message.attachments.map((a) => a.filename).join(", ")}</div>
      )}
      <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{message.body}</p>
    </article>
  );
}

/** The model's raw output and the facts that reproduce it, plus every audit-log event for the thread. */
function AuditPanel({ triage, detail }: { triage: TriageRecord; detail: ThreadDetail }) {
  return (
    <details className="rounded-lg bg-white p-4 text-sm shadow-sm">
      <summary className="cursor-pointer font-semibold">Audit record</summary>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        <dt className="text-slate-500">Model</dt><dd>{triage.model}</dd>
        <dt className="text-slate-500">Prompt</dt><dd>{triage.prompt_version}</dd>
        <dt className="text-slate-500">Judged at</dt><dd>{triage.created_at ? formatDateTime(triage.created_at) : "—"}</dd>
        <dt className="text-slate-500">Tokens</dt><dd>{triage.input_tokens} in / {triage.output_tokens} out</dd>
        <dt className="text-slate-500">Request</dt><dd className="break-all">{triage.request_id ?? "—"}</dd>
        {triage.error && <><dt className="text-slate-500">Fallback</dt><dd className="text-red-700">{triage.error}</dd></>}
      </dl>
      <div className="mt-3 text-xs font-semibold">Raw model output</div>
      <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-slate-900 p-2 text-xs text-slate-100">
        {triage.raw_response || "(none)"}
      </pre>
      <div className="mt-3 text-xs font-semibold">History</div>
      <ul className="mt-1 space-y-0.5 text-xs text-slate-600">
        {detail.audit.map((entry) => (
          <li key={entry.id}>
            #{entry.id} {formatDateTime(entry.created_at)} · {entry.event} · {String(entry.detail.prompt_version ?? "")}
          </li>
        ))}
      </ul>
    </details>
  );
}

/** The recommendation: priority with its reasons, then the triage fields and the model's reasoning. */
function TriagePanel({ detail }: { detail: ThreadDetail }) {
  const { priority, triage } = detail;
  if (!triage || !priority) return <div className="rounded-lg bg-white p-4 text-sm shadow-sm">Not triaged yet.</div>;
  const r = triage.result;
  const fields: [string, string][] = [
    ["Category", humanise(r.category)], ["Action", humanise(r.action_type)], ["Claim", r.claim_ref ?? "—"],
    ["Line", r.line_of_business], ["Sender", humanise(r.sender_type)], ["Urgency", r.urgency],
    ["Importance", r.importance], ["Deadline", r.deadline_mentioned ? formatDate(r.deadline_mentioned) : "—"],
    ["Confidence", `${Math.round(r.confidence * 100)}%`],
  ];
  return (
    <div className="space-y-4">
      <section className="rounded-lg bg-white p-4 shadow-sm">
        <div className="flex items-center gap-2"><PriorityBadge level={priority.level} bucket={priority.bucket} />
          <span className="text-sm font-semibold">{priority.explanation}</span></div>
        {r.action_summary && <p className="mt-3 text-sm"><strong>Recommended:</strong> {r.action_summary}</p>}
        <ul className="mt-3 space-y-0.5 font-mono text-xs text-slate-600">
          {priority.rules_fired.map((rule) => <li key={rule}>{rule}</li>)}
        </ul>
        <p className="mt-3 text-xs text-slate-500">A recommendation only: nothing is sent, archived or deleted automatically.</p>
      </section>
      <section className="rounded-lg bg-white p-4 shadow-sm">
        <h3 className="mb-2 text-sm font-semibold">Triage ({triage.prompt_version})</h3>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          {fields.map(([label, value]) => (
            <Fragment key={label}><dt className="text-slate-500">{label}</dt><dd>{value}</dd></Fragment>
          ))}
        </dl>
        <div className="mt-2 flex flex-wrap gap-1">
          {r.signals.map((s) => <span key={s} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{humanise(s)}</span>)}
        </div>
        <p className="mt-3 text-sm text-slate-700">{r.reasoning}</p>
      </section>
      <AuditPanel triage={triage} detail={detail} />
    </div>
  );
}

/** One thread: messages oldest first (latest highlighted) beside the recommendation and its audit trail. */
export default function ThreadView({ threadKey, focusMessageId, onBack }: {
  threadKey: string;
  focusMessageId?: string;
  onBack: () => void;
}) {
  const [detail, setDetail] = useState<ThreadDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDetail(null);
    getThread(threadKey).then(setDetail).catch((e: Error) => setError(e.message));
  }, [threadKey]);
  useEffect(() => {
    if (detail && focusMessageId) {
      document.getElementById(focusMessageId)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [detail, focusMessageId]);

  if (error) return <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">{error}</div>;
  if (!detail) return <p className="text-sm text-slate-500">Loading…</p>;
  const last = detail.messages.length - 1;
  return (
    <div className="space-y-4">
      <button onClick={onBack} className="text-sm text-sky-700 hover:underline">← Back</button>
      <h2 className="text-xl font-semibold">{detail.thread.subject}</h2>
      <div className="grid gap-4 lg:grid-cols-[1fr_400px]">
        <div className="space-y-3">
          {detail.messages.map((m, i) => (
            <MessageCard key={m.message_id} message={m} latest={i === last} focused={m.message_id === focusMessageId} />
          ))}
        </div>
        <TriagePanel detail={detail} />
      </div>
    </div>
  );
}
