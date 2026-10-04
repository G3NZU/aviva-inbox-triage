import type { ReactNode } from "react";
import { formatDateTime } from "../format";
import type { Message } from "../types";
import Icon from "./Icon";

/** A small plain tag on an email: words, never colour alone. */
function Tag({ children, tone = "bg-sunken text-ink-2" }: { children: ReactNode; tone?: string }) {
  return <span className={`rounded px-1.5 py-0.5 text-xs font-semibold ${tone}`}>{children}</span>;
}

/** Who sent it, to whom, when, and the tags that matter (latest, ours, cited, the sender's own flag). */
function Header({ message, latest, cited }: { message: Message; latest: boolean; cited: boolean }) {
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2 text-xs text-ink-2">
        <span className="tabular-nums">{formatDateTime(message.date_sent)}</span>
        {latest && <Tag tone="bg-ink-2 text-surface">Latest email</Tag>}
        {message.from_internal && <Tag>Pinnacle staff</Tag>}
        {cited && <Tag tone="bg-accent-soft text-accent-strong">Cited in the answer</Tag>}
        {message.importance_flag && (
          <span className="text-ink-3">Flagged {message.importance_flag} importance by the sender</span>
        )}
      </div>
      <p className="text-sm [overflow-wrap:anywhere]"><span className="font-semibold">{message.sent_from}</span>
        <span className="text-ink-2"> to {message.sent_to.join(", ")}</span></p>
      {message.sent_cc.length > 0 && <p className="text-xs text-ink-2 [overflow-wrap:anywhere]">Cc {message.sent_cc.join(", ")}</p>}
      <p className="font-semibold">{message.subject}</p>
      {message.attachments.length > 0 && (
        <p className="flex items-center gap-1 text-xs text-ink-2">
          <Icon name="paperclip" className="size-3.5" />
          Attachments (names only): {message.attachments.map((a) => a.filename).join(", ")}
        </p>
      )}
    </div>
  );
}

/**
 * One email. The latest is marked as the current state; Pinnacle's own emails sit on a grey background; an
 * email an answer cited is ringed, tagged and flashed once. In threads of three or more, older emails are
 * folded to one line (date, sender, first words) so the current state is near the top of the page.
 * Props: the message, and whether it is the latest, cited or folded.
 */
export default function MessageCard({ message, latest, cited, folded }: {
  message: Message; latest: boolean; cited: boolean; folded: boolean;
}) {
  const frame = `scroll-mt-4 rounded-lg border p-4 ${message.from_internal ? "bg-canvas" : "bg-surface"} ${
    cited ? "border-accent outline-2 outline-accent animate-flash" : latest ? "border-line border-l-4 border-l-ink-2" : "border-line"}`;
  const body = <p className="mt-3 max-w-prose whitespace-pre-wrap">{message.body}</p>;
  if (folded) {
    return (
      <details id={message.message_id} className={`group ${frame}`}>
        <summary className="flex cursor-pointer list-none items-center gap-2 text-sm [&::-webkit-details-marker]:hidden">
          <Icon name="chevronRight" className="size-4 text-ink-3 group-open:rotate-90 motion-safe:transition-transform" />
          <span className="shrink-0 whitespace-nowrap tabular-nums text-ink-2">{formatDateTime(message.date_sent)}</span>
          <span className="min-w-0 truncate font-semibold">{message.sent_from}</span>
          <span className="min-w-0 truncate text-ink-3">{message.body.slice(0, 120)}</span>
        </summary>
        <div className="mt-3"><Header message={message} latest={latest} cited={cited} />{body}</div>
      </details>
    );
  }
  return (
    <article id={message.message_id} className={frame}>
      <Header message={message} latest={latest} cited={cited} />
      {body}
    </article>
  );
}
