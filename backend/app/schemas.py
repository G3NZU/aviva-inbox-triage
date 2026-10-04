"""The API's response shapes: what each route returns (mirrored in frontend/src/types.ts).

Why: the domain models (app/models.py) describe emails, triage and priorities;
these describe what the HTTP API sends to the UI. Keeping them apart keeps each
file to one job, and makes every field the UI can show easy to find.
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models import (Bucket, Category, Level, LineOfBusiness, Message, PriorityResult, Reason, SenderType,
                        TriageRecord)

# The dashboard card a thread counts towards (main._card): its level in the act bucket, else its bucket.
Card = Literal["P1", "P2", "P3", "review", "archive", "ignore", "untriaged"]


class ThreadRow(BaseModel):
    """One line of the workload list (GET /threads); also the header of a thread's detail."""

    key: str
    subject: str
    sender: str  # latest outside sender (who is waiting on us); Pinnacle's own if nobody else wrote
    message_count: int
    first_date: datetime
    last_date: datetime
    age_days: int  # calendar days from the first message to config.AS_OF_DATE
    waiting_days: int  # from the stored priority (priority.waiting_days); 0 before the first priority
    claim_ref: str | None  # regex-extracted first, else the model's
    category: Category | None  # None until triaged
    sender_type: SenderType | None
    line_of_business: LineOfBusiness | None
    action_summary: str
    level: Level | None
    bucket: Bucket | None
    card: Card  # one definition shared with GET /summary's counts
    explanation: str
    rules_fired: list[str]
    reasons: list[Reason]  # rules_fired split into rule and detail, marking the ones that set the level


class AuditEntry(BaseModel):
    """One row of the append-only audit log."""

    id: int
    created_at: datetime
    event: str
    detail: dict[str, Any]


class ThreadDetail(BaseModel):
    """Everything about one thread (GET /threads/{key}): messages, triage and its audit facts, priority, history."""

    thread: ThreadRow
    messages: list[Message]  # oldest first; message_id is shown to people, never to the model
    triage: TriageRecord | None
    priority: PriorityResult | None
    audit: list[AuditEntry]


class Policy(BaseModel):
    """The thresholds the priority rules use (from config.py), so help text can quote them."""

    confidence_threshold: float  # below this a human reviews the thread
    p1_deadline_days: int  # a deadline overdue or due within this many days -> P1
    p2_deadline_days: int  # due within this many days -> P2
    unanswered_working_days: int  # waiting on us longer than this -> P2


class Summary(BaseModel):
    """Workload totals for the dashboard cards (GET /summary)."""

    total_threads: int
    counts: dict[str, int]  # P1, P2, P3 (act bucket), review, archive (= P4), ignore, untriaged
    last_run: datetime | None
    models: list[str]  # models behind the stored triage
    prompt_versions: list[str]
    rules_versions: list[str]  # rules behind the stored priorities (the next run brings them up to date)
    as_of: date
    policy: Policy


class Citation(BaseModel):
    """A message an answer relies on: the handler can open it in the thread view."""

    thread_key: str
    message_id: str
    subject: str
    sent_from: str  # who sent it and when, so near-identical subjects can be told apart
    date_sent: datetime


class RetrievedThread(BaseModel):
    """A thread the Q&A search picked, with the reasons it matched (shown to the handler)."""

    thread_key: str
    subject: str
    score: float
    reasons: list[str]


class QAAnswer(BaseModel):
    """The reply to a free-text question (POST /ask): an answer grounded in cited messages, or a refusal."""

    answer: str
    citations: list[Citation]
    confidence: float = Field(ge=0.0, le=1.0)
    refused: bool  # True when the mailbox holds no evidence for an answer
    retrieved: list[RetrievedThread]  # what the search found, so the handler can check its basis
