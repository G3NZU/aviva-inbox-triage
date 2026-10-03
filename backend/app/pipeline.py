"""Batch pipeline: ingest → triage → priority → store. Idempotent.

Why: one entry point — this CLI, and later POST /run — brings the database up
to date with the mailbox. A thread is re-triaged only when it is new, has a
new latest message, was judged with another prompt version, or its last
attempt failed; so re-running is cheap and nothing usable is paid for twice.
"""

import argparse
import logging
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import anthropic

from app import config, llm, store
from app.ingest import load_threads
from app.models import Thread
from app.priority import compute_priority
from app.triage import triage_thread

log = logging.getLogger("app.pipeline")  # not __name__: under `python -m` that is "__main__"


@dataclass
class RunSummary:
    """What one pipeline run did; printed by the CLI and stored in the audit log."""

    threads: int = 0
    triaged: int = 0
    skipped: int = 0
    fallbacks: int = 0  # unusable model output or transient API failure → human review
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    priorities: dict[str, int] = field(default_factory=dict)  # P1/P2/P3 (act), review, archive, ignore


def run_all(force: bool = False, data_path: Path | None = None, db_path: Path | None = None) -> RunSummary:
    """Load the mailbox, triage what needs it, store everything and log the run.

    Inputs: force=True re-triages every thread; paths default to config (read at call time, so tests
    can point them elsewhere).
    Output: RunSummary. Raises on configuration errors (missing or rejected API key);
    threads finished before the error stay saved (one commit per thread).
    """
    threads = load_threads(data_path)
    conn = store.connect(db_path)
    try:
        store.save_threads(conn, threads)
        conn.commit()  # ingestion never depends on the LLM being reachable
        previous = store.triage_state(conn)
        todo = [t for t in threads if force or needs_triage(t, previous.get(t.key))]
        summary = RunSummary(threads=len(threads), skipped=len(threads) - len(todo))
        for number, thread in enumerate(todo, start=1):
            _triage_one(conn, thread, summary, f"[{number}/{len(todo)}]")
        summary.priorities = prioritise_all(conn, threads, config.AS_OF_DATE)
        store.log_event(conn, "pipeline_run", asdict(summary) | {
            "force": force, "rules_version": config.PRIORITY_RULES_VERSION, "as_of": config.AS_OF_DATE})
        conn.commit()
        return summary
    finally:
        conn.close()


def needs_triage(thread: Thread, previous: sqlite3.Row | None) -> bool:
    """True unless a stored triage already judged this thread's latest message, with this prompt, successfully."""
    return (
        previous is None
        or previous["prompt_version"] != config.TRIAGE_PROMPT_VERSION
        or previous["last_message_id"] != thread.current.message_id
        or previous["error"] is not None
    )


def _triage_one(conn: sqlite3.Connection, thread: Thread, summary: RunSummary, label: str) -> None:
    """Triage one thread, store it, commit, and add its tokens and cost to the run summary."""
    record = triage_thread(thread, config.TRIAGE_PROMPT_VERSION)
    store.save_triage(conn, thread, record)
    conn.commit()  # progress survives an interrupted run
    summary.triaged += 1
    summary.fallbacks += record.error is not None
    summary.input_tokens += record.input_tokens
    summary.output_tokens += record.output_tokens
    summary.cost_usd += llm.cost_usd(record.model, record.input_tokens, record.output_tokens)
    r = record.result
    log.info("%s %s %-15s conf %.2f  %s", label, thread.key, r.category, r.confidence, thread.subject[:70])


def prioritise_all(conn: sqlite3.Connection, threads: list[Thread], now: date) -> dict[str, int]:
    """Recompute and store every triaged thread's priority (cheap and deterministic); return the counts.

    Counts use the level for the act bucket (P1/P2/P3) and the bucket name otherwise.
    A thread with no triage yet (a run stopped early) gets no priority.
    """
    results = store.load_triage_results(conn)
    counts: Counter[str] = Counter()
    for thread in threads:
        if thread.key in results:
            priority = compute_priority(results[thread.key], thread, now)
            store.save_priority(conn, thread.key, priority, now)
            counts[priority.level if priority.bucket == "act" else priority.bucket] += 1
    return dict(sorted(counts.items()))


def main() -> None:
    """CLI: `python -m app.pipeline [--force]`. Prints one line per triaged thread and a summary."""
    parser = argparse.ArgumentParser(description="Triage the mailbox and store the results.")
    parser.add_argument("--force", action="store_true", help="re-triage every thread, even unchanged ones")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger("app").setLevel(logging.INFO)
    try:
        s = run_all(force=args.force)
    except llm.MissingAPIKeyError as exc:
        raise SystemExit(f"Error: {exc}") from None
    except anthropic.AuthenticationError:
        raise SystemExit("Error: the API key was rejected (HTTP 401). Check ANTHROPIC_API_KEY in .env.") from None
    print(f"{s.threads} threads: {s.triaged} triaged, {s.skipped} unchanged, {s.fallbacks} sent to review "
          f"as unusable. Tokens in/out {s.input_tokens}/{s.output_tokens}, estimated cost ${s.cost_usd:.4f}.")
    print("Priorities: " + ", ".join(f"{name} {count}" for name, count in s.priorities.items()))


if __name__ == "__main__":
    main()
