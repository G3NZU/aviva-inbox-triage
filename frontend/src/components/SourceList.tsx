import { formatDateTime } from "../format";
import type { Citation } from "../types";
import Icon from "./Icon";

/**
 * The emails an answer rests on, as full-width links: subject, then who sent it and when (so near-identical
 * subjects can be told apart). Opening one shows its thread with that email highlighted; each row has an id
 * so focus can return to it afterwards. Props: the citations and the handler that opens a thread at a message.
 */
export default function SourceList({ citations, onOpen }: {
  citations: Citation[]; onOpen: (threadKey: string, messageId: string) => void;
}) {
  return (
    <div>
      <p className="text-sm font-semibold">Sources ({citations.length})</p>
      <ul className="mt-2 divide-y divide-line rounded-lg border border-line bg-surface">
        {citations.map((c) => {
          const when = c.date_sent ? formatDateTime(c.date_sent) : "";
          return (
            <li key={c.message_id}>
              <button type="button" id={`source-${c.message_id}`} onClick={() => onOpen(c.thread_key, c.message_id)}
                aria-label={`Open email: ${c.subject}${c.sent_from ? `, from ${c.sent_from}` : ""}${when ? `, ${when}` : ""}`}
                className="group flex w-full items-start gap-3 px-4 py-2.5 text-left transition-colors duration-150
                  ease-standard hover:bg-sunken">
                <Icon name="arrowRight" className="mt-1 size-4 text-accent" />
                <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">
                  <span className="block font-semibold text-accent-strong group-hover:underline">{c.subject}</span>
                  <span className="block text-xs text-ink-2">{[c.sent_from, when].filter(Boolean).join(" · ")}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
