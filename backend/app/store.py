"""SQLite persistence: the schema, saves and loads, and the append-only audit log.

Why: one local file (D-04) holds the mailbox, the latest triage of every
thread with the model's raw output, and an audit log of every LLM call and
pipeline run — real tables a reviewer can query with any SQLite client.
"""

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app import config
from app.models import Attachment, Message, PriorityResult, Thread, TriageRecord, TriageResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    key             TEXT PRIMARY KEY,   -- label-free key (models.Thread.key)
    subject         TEXT NOT NULL,
    first_date      TEXT NOT NULL,
    last_date       TEXT NOT NULL,
    last_message_id TEXT NOT NULL,      -- the current state
    message_count   INTEGER NOT NULL,
    claim_refs      TEXT NOT NULL,      -- JSON list, regex-extracted
    participants    TEXT NOT NULL       -- JSON list
);
CREATE TABLE IF NOT EXISTS messages (
    message_id      TEXT PRIMARY KEY,
    thread_key      TEXT NOT NULL REFERENCES threads(key),
    position        INTEGER NOT NULL,   -- 1 = oldest
    date_sent       TEXT NOT NULL,
    sent_from       TEXT NOT NULL,
    sent_to         TEXT NOT NULL,      -- JSON list
    sent_cc         TEXT NOT NULL,      -- JSON list
    subject         TEXT NOT NULL,
    body            TEXT NOT NULL,
    attachments     TEXT NOT NULL,      -- JSON list of {filename, filesize, filetype}
    importance_flag TEXT                -- sender-set: display only (D-12)
);
CREATE TABLE IF NOT EXISTS triage (     -- the latest LLM judgement per thread
    thread_key      TEXT PRIMARY KEY REFERENCES threads(key),
    category        TEXT NOT NULL,
    confidence      REAL NOT NULL,
    result          TEXT NOT NULL,      -- the full TriageResult as JSON
    raw_response    TEXT NOT NULL,      -- the model's reply, verbatim
    error           TEXT,               -- why the fallback was used, if it was
    model           TEXT NOT NULL,
    prompt_version  TEXT NOT NULL,
    request_id      TEXT,
    input_tokens    INTEGER NOT NULL,
    output_tokens   INTEGER NOT NULL,
    last_message_id TEXT NOT NULL,      -- the thread state this result judged
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS priority (   -- the rules' verdict per thread, recomputed every run
    thread_key      TEXT PRIMARY KEY REFERENCES threads(key),
    level           TEXT,               -- P1..P4; NULL when ignored
    bucket          TEXT NOT NULL,      -- act | review | archive | ignore
    rules_fired     TEXT NOT NULL,      -- JSON list of "rule: reason"
    explanation     TEXT NOT NULL,
    rules_version   TEXT NOT NULL,      -- config.PRIORITY_RULES_VERSION
    as_of           TEXT NOT NULL,      -- the "today" the rules used
    computed_at     TEXT NOT NULL,
    waiting_days    INTEGER NOT NULL    -- working days the latest outside sender has waited; 0 if we wrote last
);
CREATE TABLE IF NOT EXISTS audit_log (  -- append-only: never updated or deleted
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL,
    event           TEXT NOT NULL,      -- triage | triage_error | pipeline_run | ask | ask_error
    thread_key      TEXT,
    detail          TEXT NOT NULL       -- JSON
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    """Open the database (default config.DB_PATH, read at call time), creating tables and columns if needed.

    check_same_thread=False lets the API open a connection in one worker
    thread and use it in another; each request still gets its own connection.
    """
    conn = sqlite3.connect(path or config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _add_missing_columns(conn)
    return conn


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    """Bring a database file made by an earlier version up to the current schema.

    Why: `priority.waiting_days` arrived with rules_v2, and CREATE TABLE IF NOT EXISTS leaves an
    existing table as it was. The triage results in that file were paid for, so the column is
    added in place rather than rebuilding the file; the next pipeline run fills it in.
    It always tries the ALTER and ignores "duplicate column": checking first and then altering
    would race when several API requests open an old file at the same moment.
    """
    try:
        conn.execute("ALTER TABLE priority ADD COLUMN waiting_days INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc):
            raise


def save_threads(conn: sqlite3.Connection, threads: list[Thread]) -> None:
    """Upsert every thread and its messages; saving the same mailbox twice changes nothing."""
    for t in threads:
        conn.execute(
            """INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET subject = excluded.subject, first_date = excluded.first_date,
                   last_date = excluded.last_date, last_message_id = excluded.last_message_id,
                   message_count = excluded.message_count, claim_refs = excluded.claim_refs,
                   participants = excluded.participants""",
            (t.key, t.subject, t.messages[0].date_sent.isoformat(), t.current.date_sent.isoformat(),
             t.current.message_id, len(t.messages), json.dumps(t.claim_refs), json.dumps(t.participants)),
        )
        for position, m in enumerate(t.messages, start=1):
            conn.execute(
                "INSERT OR REPLACE INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (m.message_id, t.key, position, m.date_sent.isoformat(), m.sent_from, json.dumps(m.sent_to),
                 json.dumps(m.sent_cc), m.subject, m.body,
                 json.dumps([a.model_dump() for a in m.attachments]), m.importance_flag),
            )


def triage_state(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    """Per thread key: prompt version, judged message and error of its stored triage (for skip decisions)."""
    rows = conn.execute("SELECT thread_key, prompt_version, last_message_id, error FROM triage")
    return {row["thread_key"]: row for row in rows}


def save_triage(conn: sqlite3.Connection, thread: Thread, record: TriageRecord) -> None:
    """Store the latest triage of a thread and append the call, in full, to the audit log."""
    r = record.result
    conn.execute(
        """INSERT OR REPLACE INTO triage (thread_key, category, confidence, result, raw_response, error, model,
               prompt_version, request_id, input_tokens, output_tokens, last_message_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (thread.key, r.category, r.confidence, r.model_dump_json(), record.raw_response, record.error,
         record.model, record.prompt_version, record.request_id, record.input_tokens, record.output_tokens,
         thread.current.message_id, now_iso()),
    )
    detail = record.model_dump(mode="json") | {"judged_message_id": thread.current.message_id}
    log_event(conn, "triage_error" if record.error else "triage", detail, thread.key)


def load_triage_results(conn: sqlite3.Connection) -> dict[str, TriageResult]:
    """Every stored triage result, by thread key (input to the priority rules)."""
    rows = conn.execute("SELECT thread_key, result FROM triage")
    return {row["thread_key"]: TriageResult.model_validate_json(row["result"]) for row in rows}


def save_priority(conn: sqlite3.Connection, thread_key: str, priority: PriorityResult, as_of: date) -> None:
    """Store the rules' verdict for a thread, with the rules version and as-of date that reproduce it."""
    conn.execute(
        """INSERT OR REPLACE INTO priority (thread_key, level, bucket, rules_fired, explanation, rules_version,
               as_of, computed_at, waiting_days) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (thread_key, priority.level, priority.bucket, json.dumps(priority.rules_fired), priority.explanation,
         config.PRIORITY_RULES_VERSION, as_of.isoformat(), now_iso(), priority.waiting_days),
    )


# `sender` is the latest outside sender (the party waiting on us); Pinnacle's own only if nobody else wrote.
THREAD_ROWS_SQL = """
SELECT th.*, t.result, p.level, p.bucket, p.explanation, p.rules_fired,
       COALESCE(p.waiting_days, 0) AS waiting_days,
       COALESCE((SELECT sent_from FROM messages m WHERE m.thread_key = th.key AND lower(m.sent_from) NOT LIKE ?
                 ORDER BY position DESC LIMIT 1),
                (SELECT sent_from FROM messages m WHERE m.thread_key = th.key ORDER BY position DESC LIMIT 1)) AS sender
FROM threads th
LEFT JOIN triage t ON t.thread_key = th.key
LEFT JOIN priority p ON p.thread_key = th.key
"""


def load_thread_rows(conn: sqlite3.Connection, key: str | None = None) -> list[sqlite3.Row]:
    """Each thread joined with its triage result, priority and outside sender (only `key` when given)."""
    internal = f"%@{config.INTERNAL_DOMAIN}"
    if key is None:
        return conn.execute(THREAD_ROWS_SQL, (internal,)).fetchall()
    return conn.execute(THREAD_ROWS_SQL + " WHERE th.key = ?", (internal, key)).fetchall()


def priority_result(row: sqlite3.Row) -> PriorityResult | None:
    """A row's stored priority (columns level, bucket, rules_fired, explanation, waiting_days); None if never set."""
    return None if row["bucket"] is None else PriorityResult(
        level=row["level"], bucket=row["bucket"], rules_fired=json.loads(row["rules_fired"]),
        explanation=row["explanation"], waiting_days=row["waiting_days"])


def load_priorities(conn: sqlite3.Connection) -> dict[str, PriorityResult]:
    """Every stored priority, by thread key (Q&A shows the model the open work and why it is ranked so)."""
    rows = conn.execute("SELECT thread_key, level, bucket, rules_fired, explanation, waiting_days FROM priority")
    return {row["thread_key"]: result for row in rows if (result := priority_result(row))}


def load_messages(conn: sqlite3.Connection, key: str) -> list[Message]:
    """A thread's messages, oldest first, rebuilt as Message objects."""
    rows = conn.execute("SELECT * FROM messages WHERE thread_key = ? ORDER BY position", (key,))
    return [_message(r) for r in rows]


def load_all_threads(conn: sqlite3.Connection) -> list[Thread]:
    """Every stored thread rebuilt from its messages (what Q&A searches: exactly what was ingested)."""
    by_key: dict[str, list[Message]] = {}
    for r in conn.execute("SELECT * FROM messages ORDER BY thread_key, position"):
        by_key.setdefault(r["thread_key"], []).append(_message(r))
    return [Thread(messages=messages) for messages in by_key.values()]


def _message(r: sqlite3.Row) -> Message:
    """One `messages` row as a Message (JSON columns decoded)."""
    return Message(message_id=r["message_id"], sent_from=r["sent_from"], sent_to=json.loads(r["sent_to"]),
                   sent_cc=json.loads(r["sent_cc"]), date_sent=r["date_sent"], subject=r["subject"],
                   body=r["body"], importance_flag=r["importance_flag"],
                   attachments=[Attachment(**a) for a in json.loads(r["attachments"])])


def load_triage_record(conn: sqlite3.Connection, key: str) -> TriageRecord | None:
    """A thread's stored triage with its audit facts (raw reply, model, prompt version, time), if any."""
    r = conn.execute("SELECT * FROM triage WHERE thread_key = ?", (key,)).fetchone()
    if r is None:
        return None
    return TriageRecord(result=TriageResult.model_validate_json(r["result"]), raw_response=r["raw_response"],
                        model=r["model"], prompt_version=r["prompt_version"], request_id=r["request_id"],
                        input_tokens=r["input_tokens"], output_tokens=r["output_tokens"], error=r["error"],
                        created_at=r["created_at"])


def load_audit(conn: sqlite3.Connection, key: str) -> list[sqlite3.Row]:
    """Every audit-log row for a thread, oldest first."""
    return conn.execute("SELECT * FROM audit_log WHERE thread_key = ? ORDER BY id", (key,)).fetchall()


def run_facts(conn: sqlite3.Connection) -> tuple[str | None, list[str], list[str], list[str]]:
    """When the pipeline last ran; the models and prompt versions behind the stored triage; the rules
    versions behind the stored priorities (read from the rows, so an older file shows what produced it)."""
    last = conn.execute("SELECT max(created_at) FROM audit_log WHERE event = 'pipeline_run'").fetchone()[0]
    models = [r[0] for r in conn.execute("SELECT DISTINCT model FROM triage ORDER BY model")]
    versions = [r[0] for r in conn.execute("SELECT DISTINCT prompt_version FROM triage ORDER BY prompt_version")]
    rules = [r[0] for r in conn.execute("SELECT DISTINCT rules_version FROM priority ORDER BY rules_version")]
    return last, models, versions, rules


def log_event(conn: sqlite3.Connection, event: str, detail: dict[str, Any], thread_key: str | None = None) -> None:
    """Append one row to the audit log. Rows are never updated or deleted."""
    conn.execute(
        "INSERT INTO audit_log (created_at, event, thread_key, detail) VALUES (?, ?, ?, ?)",
        (now_iso(), event, thread_key, json.dumps(detail, default=str)),
    )


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string (seconds precision) for created_at columns."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
