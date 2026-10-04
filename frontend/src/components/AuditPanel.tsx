import { formatDateTime } from "../format";
import type { AuditEntry, ThreadDetail } from "../types";
import Icon from "./Icon";

/** An audit-log event in plain words: "Read by the AI (prompt triage_v2)". Unknown events show their name. */
function eventText(entry: AuditEntry): string {
  const prompt = entry.detail.prompt_version ? ` (prompt ${String(entry.detail.prompt_version)})` : "";
  if (entry.event === "triage") return `Read by the AI${prompt}`;
  if (entry.event === "triage_error") return `AI reading failed, fallback used${prompt}`;
  return `${entry.event}${prompt}`;
}

/**
 * The audit record, folded by default: exactly what the AI returned and when, the rule codes behind the
 * priority, and every logged event for the thread. Nothing here changes the priority; it is for checking.
 * Props: the thread detail.
 */
export default function AuditPanel({ detail }: { detail: ThreadDetail }) {
  const triage = detail.triage;
  const facts: [string, string][] = triage ? [
    ["Model", triage.model], ["Prompt", triage.prompt_version],
    ["Read at", triage.created_at ? formatDateTime(triage.created_at) : "—"],
    ["Tokens", `${triage.input_tokens} in / ${triage.output_tokens} out`], ["Request ID", triage.request_id ?? "—"],
  ] : [];
  if (triage?.error) facts.push(["Fallback used", triage.error]);
  return (
    <details className="group rounded-lg border border-line bg-surface p-4 text-sm">
      <summary className="flex cursor-pointer list-none items-center gap-1 font-semibold [&::-webkit-details-marker]:hidden">
        <Icon name="chevronRight" className="size-4 group-open:rotate-90 motion-safe:transition-transform" />
        Audit record: rule codes, AI output, history
      </summary>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
        {facts.map(([label, value]) => (
          <div key={label} className="contents"><dt className="text-ink-2">{label}</dt><dd className="break-all">{value}</dd></div>
        ))}
      </dl>
      <p className="mt-3 text-xs font-semibold">Rules fired (codes)</p>
      <ul className="mt-1 space-y-0.5 font-mono text-xs">
        {(detail.priority?.rules_fired ?? []).map((rule, i) => <li key={i}>{rule}</li>)}
      </ul>
      <p className="mt-3 text-xs font-semibold">AI output, exactly as returned</p>
      <pre tabIndex={0} className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-sunken p-2 text-xs">
        {triage?.raw_response || "(none)"}
      </pre>
      <p className="mt-3 text-xs font-semibold">History</p>
      <ul className="mt-1 space-y-0.5 text-xs text-ink-2">
        {detail.audit.map((entry) => (
          <li key={entry.id} className="tabular-nums">{formatDateTime(entry.created_at)} · {eventText(entry)}</li>
        ))}
      </ul>
    </details>
  );
}
