import type { Citation } from "../types";

/** A message an answer cites: click to open its thread with that message highlighted. */
export default function CitationChip({ citation, onOpen }: {
  citation: Citation;
  onOpen: (threadKey: string, messageId: string) => void;
}) {
  return (
    <button
      onClick={() => onOpen(citation.thread_key, citation.message_id)}
      className="rounded-full border border-sky-300 bg-sky-50 px-3 py-1 text-left text-xs text-sky-900 hover:bg-sky-100"
    >
      {citation.subject}
    </button>
  );
}
