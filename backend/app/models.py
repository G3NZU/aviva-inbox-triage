"""Pydantic models shared by the backend.

Why: one typed definition of each object that every module and the API agree
on, validated at the boundary where untrusted data (the mailbox file, later
the LLM's output) comes in.
"""

import hashlib
import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, field_validator

from app import config

CLAIM_REF_PATTERN = re.compile(r"PIN-[A-Z]{3}-\d{6}")

Category = Literal["action_required", "informational", "irrelevant"]
ActionType = Literal[
    "respond", "approve_authorise", "investigate", "chase_third_party",
    "open_new_claim", "review_document", "escalate", "none",
]
SenderType = Literal[
    "customer", "broker", "repairer_supplier", "solicitor", "loss_adjuster", "internal", "automated", "unknown",
]
Signal = Literal[
    "fnol", "injury", "make_safe_urgent", "complaint", "legal_threat", "regulatory", "fraud_flag",
    "vulnerable_customer", "repeat_chase", "payment_or_authority_pending", "already_resolved",
    "parse_error",  # set by the code, never by the model: the reply was unusable
]
Rating = Literal["high", "medium", "low"]
LineOfBusiness = Literal["home", "motor", "liability", "unknown"]
Level = Literal["P1", "P2", "P3", "P4"]  # P1 today · P2 this week · P3 normal · P4 no action
Bucket = Literal["act", "review", "archive", "ignore"]


class Attachment(BaseModel):
    """Attachment metadata. The dataset has names, sizes and types, never content."""

    filename: str
    filesize: int
    filetype: str


class Message(BaseModel):
    """One email.

    There is deliberately no `thread_id` field: the source thread IDs leak the
    category label (`thr_irr_...`), so they are dropped on load (D-07).
    """

    message_id: str
    sent_from: str
    sent_to: list[str]
    sent_cc: list[str]
    date_sent: datetime
    subject: str
    body: str
    attachments: list[Attachment]
    importance_flag: str | None = None  # sender-set; shown to the handler, never used to decide

    @field_validator("sent_cc", "attachments", mode="before")
    @classmethod
    def _none_to_empty(cls, value: object) -> object:
        """Turn JSON null into an empty list, so callers never have to check for None."""
        return [] if value is None else value

    @computed_field  # also sent to the frontend, so "is this us?" has one definition
    @property
    def from_internal(self) -> bool:
        """True when Pinnacle staff sent it (sender on config.INTERNAL_DOMAIN): "us", not "them"."""
        return self.sent_from.lower().endswith("@" + config.INTERNAL_DOMAIN)


class Thread(BaseModel):
    """An email thread: messages oldest first; the latest one is the current state."""

    messages: list[Message]

    @field_validator("messages")
    @classmethod
    def _sort_oldest_first(cls, messages: list[Message]) -> list[Message]:
        """Sort by send time (stable, so ties keep file order). An empty thread is invalid."""
        if not messages:
            raise ValueError("a thread needs at least one message")
        return sorted(messages, key=lambda m: m.date_sent)

    @property
    def key(self) -> str:
        """Stable ID that cannot leak the label: 't' + 8 hex chars of SHA-256 of the first message_id."""
        digest = hashlib.sha256(self.messages[0].message_id.encode("utf-8")).hexdigest()
        return f"t{digest[:8]}"

    @property
    def current(self) -> Message:
        """The latest message. It defines what, if anything, is still outstanding."""
        return self.messages[-1]

    @property
    def subject(self) -> str:
        """The thread's topic: the first message's subject."""
        return self.messages[0].subject

    @property
    def claim_refs(self) -> list[str]:
        """Claim references (PIN-XXX-nnnnnn) found in any subject or body; sorted, no duplicates."""
        text = "\n".join(f"{m.subject}\n{m.body}" for m in self.messages)
        return sorted(set(CLAIM_REF_PATTERN.findall(text)))

    @property
    def participants(self) -> list[str]:
        """Every address on the thread (from, to, cc), lower-cased, in order of first appearance."""
        addresses = (a.lower() for m in self.messages for a in [m.sent_from, *m.sent_to, *m.sent_cc])
        return list(dict.fromkeys(addresses))


class TriageResult(BaseModel):
    """The LLM's judgement on one thread.

    The model reports what the thread is and what it asks for; it does not set
    the priority — the rules in priority.py do (D-01).
    """

    category: Category
    action_type: ActionType
    action_summary: str  # one imperative sentence; "" when there is no action
    claim_ref: str | None
    line_of_business: LineOfBusiness
    sender_type: SenderType
    urgency: Rating  # how soon action is needed
    importance: Rating  # how much is at stake: money, customer harm, legal, regulatory
    deadline_mentioned: date | None
    signals: list[Signal]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str

    @field_validator("claim_ref", mode="before")
    @classmethod
    def _claim_ref_or_none(cls, value: object) -> object:
        """Keep only a well-formed claim reference; anything else (e.g. a policy number) becomes None."""
        if isinstance(value, str) and CLAIM_REF_PATTERN.fullmatch(value.strip()):
            return value.strip()
        return None

    @field_validator("deadline_mentioned", mode="before")
    @classmethod
    def _date_part_only(cls, value: object) -> object:
        """Accept "2026-02-20T17:00" as 2026-02-20 and "" as no deadline (lenient on format, not content)."""
        if isinstance(value, str):
            return value[:10] or None
        return value

    @field_validator("signals")
    @classmethod
    def _unique_signals(cls, signals: list[str]) -> list[str]:
        """Drop repeated signals, keeping the model's order."""
        return list(dict.fromkeys(signals))


class TriageRecord(BaseModel):
    """A triage result plus the audit facts stored with it (see store.save_triage)."""

    result: TriageResult
    raw_response: str  # the model's reply, verbatim ("" if there was none)
    model: str
    prompt_version: str
    request_id: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None  # why the fallback result was used, if it was
    created_at: datetime | None = None  # set when loaded from the database


class PriorityResult(BaseModel):
    """The rules' verdict on one thread: where it goes, how soon, and every rule behind it (D-01)."""

    level: Level | None  # None when ignored
    bucket: Bucket
    rules_fired: list[str]  # "rule_name: reason", in evaluation order
    explanation: str  # one sentence for the handler


# --- API response shapes (mirrored in frontend/src/types.ts) ------------------


class ThreadRow(BaseModel):
    """One line of the workload list (GET /threads); also the header of a thread's detail."""

    key: str
    subject: str
    sender: str  # latest outside sender (who is waiting on us); Pinnacle's own if nobody else wrote
    message_count: int
    first_date: datetime
    last_date: datetime
    age_days: int  # calendar days from the first message to config.AS_OF_DATE
    claim_ref: str | None  # regex-extracted first, else the model's
    category: Category | None  # None until triaged
    sender_type: SenderType | None
    line_of_business: LineOfBusiness | None
    action_summary: str
    level: Level | None
    bucket: Bucket | None
    explanation: str
    rules_fired: list[str]


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


class Summary(BaseModel):
    """Workload totals for the dashboard cards (GET /summary)."""

    total_threads: int
    counts: dict[str, int]  # P1, P2, P3 (act bucket), review, archive (= P4), ignore, untriaged
    last_run: datetime | None
    models: list[str]  # models behind the stored triage
    prompt_versions: list[str]
    rules_version: str
    as_of: date


class Citation(BaseModel):
    """A message an answer relies on: the handler can open it in the thread view."""

    thread_key: str
    message_id: str
    subject: str


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
