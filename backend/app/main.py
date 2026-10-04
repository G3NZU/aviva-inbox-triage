"""FastAPI application: the HTTP routes the React frontend (and curl) use.

Why: the API is the only way the UI reads triage results or triggers work, so
each route maps to one screen or action. It recommends only: nothing here
sends, archives or deletes mail (D-06).
"""

import json
import sqlite3
import threading
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict
from datetime import datetime
from typing import Any, Literal

import anthropic
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import config, llm, pipeline, priority, qa, store
from app.models import Bucket, Level, LineOfBusiness, TriageResult
from app.schemas import AuditEntry, Card, Policy, QAAnswer, Summary, ThreadDetail, ThreadRow

app = FastAPI(title="Aviva Inbox Triage", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=config.FRONTEND_ORIGINS,
                   allow_methods=["GET", "POST"], allow_headers=["*"])

RUN_LOCK = threading.Lock()  # held while POST /run is working (see `run`)


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one SQLite connection per request, closed afterwards."""
    conn = store.connect(config.DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the API process is up. Returns {"status": "ok"}."""
    return {"status": "ok"}


@app.get("/summary")
def summary(conn: sqlite3.Connection = Depends(get_db)) -> Summary:
    """Workload totals for the dashboard cards, and when and with what the data was produced."""
    rows = store.load_thread_rows(conn)
    last_run, models, versions, rules = store.run_facts(conn)
    return Summary(total_threads=len(rows), counts=dict(Counter(_card(r) for r in rows)), last_run=last_run,
                   models=models, prompt_versions=versions, rules_versions=rules, as_of=config.AS_OF_DATE,
                   policy=_policy())


def _policy() -> Policy:
    """The rules' thresholds, read from config when the request is served (so help text never copies them)."""
    return Policy(confidence_threshold=config.CONFIDENCE_THRESHOLD, p1_deadline_days=config.P1_DEADLINE_DAYS,
                  p2_deadline_days=config.P2_DEADLINE_DAYS,
                  unanswered_working_days=config.UNANSWERED_WORKING_DAYS)


@app.get("/threads")
def list_threads(bucket: Bucket | None = None, level: Level | None = None, lob: LineOfBusiness | None = None,
                 sort: Literal["priority", "newest"] = "priority",
                 conn: sqlite3.Connection = Depends(get_db)) -> list[ThreadRow]:
    """The workload list, filtered by bucket, level and line of business.

    sort=priority (default): P1 → P4, then oldest first. sort=newest: latest message first.
    """
    rows = [to_thread_row(r) for r in store.load_thread_rows(conn)]
    rows = [r for r in rows if (bucket is None or r.bucket == bucket) and (level is None or r.level == level)
            and (lob is None or r.line_of_business == lob)]
    if sort == "newest":
        return sorted(rows, key=lambda r: r.last_date, reverse=True)
    return sorted(rows, key=lambda r: priority.workload_rank(r.level, r.first_date))


@app.get("/threads/{key}")
def thread_detail(key: str, conn: sqlite3.Connection = Depends(get_db)) -> ThreadDetail:
    """One thread: messages, triage with its audit facts, priority with the rules fired, audit history. 404 if unknown."""
    rows = store.load_thread_rows(conn, key)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No thread with key {key}")
    row = rows[0]
    audit = [AuditEntry(id=a["id"], created_at=a["created_at"], event=a["event"], detail=json.loads(a["detail"]))
             for a in store.load_audit(conn, key)]
    return ThreadDetail(thread=to_thread_row(row), messages=store.load_messages(conn, key),
                        triage=store.load_triage_record(conn, key), priority=store.priority_result(row), audit=audit)


class AskRequest(BaseModel):
    """Body of POST /ask."""

    question: str = Field(min_length=3, max_length=500)


@app.post("/ask")
def ask(request: AskRequest, conn: sqlite3.Connection = Depends(get_db)) -> QAAnswer:
    """Answer a free-text question from the stored mailbox, with cited messages, or refuse.

    Every question is written to the audit log. 503 without a key or when the model is
    unavailable; 502 if the key is rejected.
    """
    try:
        return qa.answer(request.question, conn)
    except llm.MissingAPIKeyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=502, detail="The Anthropic API rejected the key in .env (401).") from None
    except anthropic.APIError as exc:
        raise HTTPException(status_code=503, detail=f"The model is unavailable ({type(exc).__name__}).") from None


@app.post("/run")
def run(force: bool = False) -> dict[str, Any]:
    """Re-run the pipeline (for the demo) and return its summary.

    New or changed threads are triaged and every priority is recomputed; force=true
    re-triages all threads (about 2 minutes and $0.18). 503 without a key, 502 if it is rejected.
    One run at a time: everything lives in one SQLite file, and two overlapping runs would
    both pay to triage the same threads, so a second request gets 409 while one is in progress.
    """
    if not RUN_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A pipeline run is already in progress")
    try:
        return asdict(pipeline.run_all(force=force))
    except llm.MissingAPIKeyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=502, detail="The Anthropic API rejected the key in .env (401).") from None
    finally:
        RUN_LOCK.release()


def to_thread_row(row: sqlite3.Row) -> ThreadRow:
    """Shape one joined database row (see store.load_thread_rows) into a ThreadRow."""
    triage = TriageResult.model_validate_json(row["result"]) if row["result"] else None
    refs = json.loads(row["claim_refs"])
    first = datetime.fromisoformat(row["first_date"])
    rules_fired = json.loads(row["rules_fired"] or "[]")
    return ThreadRow(
        key=row["key"], subject=row["subject"], sender=row["sender"], message_count=row["message_count"],
        first_date=first, last_date=row["last_date"], age_days=(config.AS_OF_DATE - first.date()).days,
        waiting_days=row["waiting_days"],
        claim_ref=refs[0] if refs else (triage.claim_ref if triage else None),
        category=triage.category if triage else None, sender_type=triage.sender_type if triage else None,
        line_of_business=triage.line_of_business if triage else None,
        action_summary=triage.action_summary if triage else "", level=row["level"], bucket=row["bucket"],
        card=_card(row), explanation=row["explanation"] or "", rules_fired=rules_fired,
        reasons=priority.reasons(rules_fired, row["level"]),
    )


def _card(row: sqlite3.Row) -> Card:
    """The dashboard card a thread counts towards: its level in the act bucket, else its bucket."""
    if row["bucket"] is None:
        return "untriaged"
    return row["level"] if row["bucket"] == "act" else row["bucket"]
