"""Load the mailbox file into threads, and render the only view of a thread the LLM sees.

Why: one place turns raw JSON into validated, sorted threads, and one place
decides exactly what the model is allowed to read. The model view leaves out
every field that leaks the label (thread_id, message_id) and the sender-set
importance flag (D-07, D-12).
"""

import json
from datetime import timezone
from pathlib import Path
from typing import Any

from app import config
from app.models import Message, Thread


def load_threads(path: Path | None = None) -> list[Thread]:
    """Read the mailbox JSON and return one Thread per entry, in file order.

    Input: a file shaped {"emails": [{"messages": [...]}, ...]} (default config.DATA_PATH, read at call time).
    Output: validated threads, messages sorted oldest first, thread_id dropped.
    """
    raw = json.loads(Path(path or config.DATA_PATH).read_text(encoding="utf-8"))
    return [Thread(messages=[_parse_message(m) for m in entry["messages"]]) for entry in raw["emails"]]


def _parse_message(raw: dict[str, Any]) -> Message:
    """Validate one raw email after dropping `thread_id`, which leaks the category label (D-07)."""
    fields = {name: value for name, value in raw.items() if name != "thread_id"}
    return Message.model_validate(fields)


def thread_for_model(thread: Thread) -> str:
    """Render a thread as plain text for the triage model.

    Why: this is the only email text the model sees, so it is the single place
    that guarantees nothing leaks the label.
    Includes per message: date with weekday (to resolve "Friday", "tomorrow"),
    sender (tagged when internal), recipients, subject, attachment names, body.
    Excludes: thread_id, message_id, importance_flag.
    Output: one string, oldest message first, the latest marked "(latest)".
    """
    total = len(thread.messages)
    header = f"Email thread with {total} message(s), oldest first. The last message is the current state."
    rendered = [_render_message(m, i, total) for i, m in enumerate(thread.messages, start=1)]
    return "\n\n".join([header, *rendered])


def _render_message(message: Message, position: int, total: int) -> str:
    """Render one message for `thread_for_model` (see there for what is included and why)."""
    latest = " (latest)" if position == total else ""
    sent = message.date_sent.astimezone(timezone.utc)
    lines = [
        f"--- Message {position} of {total}{latest} ---",
        f"Date: {sent:%a %Y-%m-%d %H:%M} UTC",
        f"From: {message.sent_from}{' (internal)' if message.from_internal else ''}",
        f"To: {', '.join(message.sent_to)}",
    ]
    if message.sent_cc:
        lines.append(f"Cc: {', '.join(message.sent_cc)}")
    lines.append(f"Subject: {message.subject}")
    if message.attachments:
        lines.append("Attachments: " + ", ".join(a.filename for a in message.attachments))
    return "\n".join([*lines, "", message.body.strip()])


def main() -> None:
    """Print a one-line profile of the mailbox (`python -m app.ingest`): a quick check that loading works."""
    threads = load_threads()
    messages = sum(len(t.messages) for t in threads)
    single = sum(1 for t in threads if len(t.messages) == 1)
    refs = {ref for t in threads for ref in t.claim_refs}
    print(f"{len(threads)} threads / {messages} messages; {single} single-message threads; {len(refs)} claim refs")


if __name__ == "__main__":
    main()
