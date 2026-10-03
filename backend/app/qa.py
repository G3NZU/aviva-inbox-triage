"""Free-text questions over the mailbox: transparent retrieval, then a cited answer from Claude Sonnet.

Why: handlers ask things like "Was there any action required for Broker X?".
`retrieve` picks threads with scoring a person can follow — an exact claim
reference beats a company named in a sender's domain, which beats a type the
triage assigned (solicitor, FNOL, fraud…), which beats shared rare words — and
says why each thread matched (no embeddings, D-03). `answer` lets
Sonnet answer only from those threads, citing messages by neutral handles
(M1, M2…; message IDs leak labels, D-07). No valid citation, no answer (D-29).
"""

import math
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app import config, llm, store
from app.models import CLAIM_REF_PATTERN, Citation, Message, QAAnswer, RetrievedThread, Thread, TriageResult
from app.triage import load_prompt

CLAIM_REF_SCORE = 100.0  # an exact claim reference is the strongest evidence of relevance
PARTY_SCORE = 20.0  # per question word found in an outside sender's company domain
TAG_SCORE = 5.0  # per question word naming one of the thread's triage tags (sender type, signal)
WORD = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(  # function words, question filler, and mailbox words every thread shares
    "a about affect affects after all an and any anybody anyone anything are as ask asked at be been by can could "
    "did do does email emails everything for from get had has have how i in involve involves involving is it its "
    "know mail mailbox make me message messages my need needs of on or our please raise raised should so someone "
    "something tell than that the their them there these they this those thread threads to us was we were what "
    "when where which who why will with work would you your".split())
# Personal mail providers and our own domain say nothing about which company wrote.
SKIP_DOMAINS = frozenset({config.INTERNAL_DOMAIN, "gmail.com", "hotmail.co.uk", "outlook.com", "yahoo.co.uk",
                          "btinternet.com", "protonmail.com", "sky.com", "virginmedia.com"})


class QAReply(BaseModel):
    """What the model must return; llm.call_json checks it."""

    answer: str
    citations: list[str]  # message handles such as "M3"
    confidence: float = Field(ge=0.0, le=1.0)
    refused: bool


@dataclass
class Hit:
    """A retrieved thread, its score, and the reasons it matched."""

    thread: Thread
    score: float
    reasons: list[str]


def retrieve(question: str, threads: list[Thread], triage: dict[str, TriageResult], k: int) -> list[Hit]:
    """Score every thread against the question; return up to k, best first, with reasons.

    Threads scoring below QA_MIN_RELATIVE_SCORE × the best score are dropped, so a
    claim-reference question does not drag in threads that merely share a word.
    """
    texts = {t.key: tokens(searchable_text(t, triage.get(t.key))) for t in threads}
    tags = {t.key: tokens(triage_tags(triage.get(t.key))) for t in threads}
    idf = {w: math.log(len(threads) / df) for w, df in _document_frequency(texts.values()).items()}
    refs = set(CLAIM_REF_PATTERN.findall(question.upper()))
    words = [w for w in WORD.findall(question.lower()) if len(w) >= 4 and w not in STOPWORDS]
    hits = [_score(t, texts[t.key], tags[t.key], idf, tokens(question), refs, words) for t in threads]
    hits = sorted((h for h in hits if h.score > 0), key=lambda h: h.score, reverse=True)
    floor = hits[0].score * config.QA_MIN_RELATIVE_SCORE if hits else 0
    return [h for h in hits if h.score >= floor][:k]


def _score(thread: Thread, thread_words: set[str], thread_tags: set[str], idf: dict[str, float],
           question_words: set[str], refs: set[str], party_words: list[str]) -> Hit:
    """Score one thread: claim refs, company domains, triage tags, then shared words weighted by rarity (IDF)."""
    score, reasons = 0.0, []
    for ref in sorted(refs & set(thread.claim_refs)):
        score += CLAIM_REF_SCORE
        reasons.append(f"claim ref {ref}")
    for domain in _company_domains(thread):
        matched = [w for w in party_words if w in domain.split(".")[0]]
        if matched:
            score += PARTY_SCORE * len(matched)
            reasons.append(f"sender domain {domain} matches '{' '.join(matched)}'")
    tagged = sorted(question_words & thread_tags)
    if tagged:
        score += TAG_SCORE * len(tagged)
        reasons.append("triage tags: " + ", ".join(tagged))
    shared = sorted(question_words & thread_words, key=lambda w: -idf[w])
    if shared:
        score += sum(idf[w] for w in shared)
        reasons.append("shared words: " + ", ".join(shared[:6]))
    return Hit(thread, round(score, 2), reasons)


def tokens(text: str) -> set[str]:
    """Distinct lower-case words, minus stop words, lightly stemmed ("flooded" → "flood", "notices" → "notice")."""
    return {_stem(w) for w in WORD.findall(text.lower()) if len(w) > 2 and w not in STOPWORDS}


def _stem(word: str) -> str:
    """Strip one common suffix (-ing, -ed, plural -s) from words long enough to keep a stem."""
    for suffix in ("ing", "ed", "s"):
        if word.endswith(suffix) and len(word) > len(suffix) + 3 and not word.endswith("ss"):
            return word[: -len(suffix)]
    return word


def searchable_text(thread: Thread, triage: TriageResult | None) -> str:
    """Subjects, bodies and attachment names, plus the triage's action summary (its words help recall)."""
    parts = [f"{m.subject}\n{m.body}\n{' '.join(a.filename for a in m.attachments)}" for m in thread.messages]
    if triage:
        parts.append(triage.action_summary)
    return "\n".join(parts)


def triage_tags(triage: TriageResult | None) -> str:
    """The thread's sender type and signals as words ("legal_threat" → "legal threat").

    The category is left out: "action required" in a question would otherwise boost every action thread.
    """
    if triage is None:
        return ""
    return " ".join([triage.sender_type, *triage.signals]).replace("_", " ")


def _document_frequency(token_sets: Any) -> dict[str, int]:
    """In how many threads each word appears (for IDF: rarer words count more)."""
    counts: dict[str, int] = {}
    for words in token_sets:
        for w in words:
            counts[w] = counts.get(w, 0) + 1
    return counts


def _company_domains(thread: Thread) -> list[str]:
    """Distinct sender and recipient domains on the thread, minus our own and personal mail providers."""
    domains = dict.fromkeys(address.split("@")[-1] for address in thread.participants)
    return [d for d in domains if d not in SKIP_DOMAINS]


def answer(question: str, conn: sqlite3.Connection) -> QAAnswer:
    """Answer a handler's question from the mailbox, citing messages; refuse when there is no evidence.

    Input: the question and an open database connection (threads, triage, audit log).
    Output: QAAnswer. Every question, what was retrieved, the raw reply and the answer go to the audit log.
    """
    started = time.perf_counter()
    hits = retrieve(question, store.load_all_threads(conn), store.load_triage_results(conn), config.QA_TOP_K)
    if hits:
        result, audit = _ask_model(question, hits)
    else:
        result, audit = _refusal("I can't find anything about that in the mailbox.", hits), {}
    retrieved = [r.model_dump() for r in result.retrieved]
    store.log_event(conn, "ask", {"question": question, "retrieved": retrieved, **audit,
                                  "answer": result.model_dump(mode="json", exclude={"retrieved"}),
                                  "seconds": round(time.perf_counter() - started, 1)})
    conn.commit()
    return result


def _ask_model(question: str, hits: list[Hit]) -> tuple[QAAnswer, dict[str, Any]]:
    """Ask Sonnet over the retrieved threads; map its handles to real messages; enforce "no citation, no answer"."""
    context, handles = render_context(hits)
    user = (f"Today is {config.AS_OF_DATE:%A %d %B %Y} (the date of the newest email).\n\n"
            f"<question>\n{question}\n</question>\n\n<mailbox_extract>\n{context}\n</mailbox_extract>")
    try:
        reply = llm.call_json(config.QA_MODEL, load_prompt(config.QA_PROMPT_VERSION), user,
                              max_tokens=config.QA_MAX_TOKENS, schema=QAReply, **config.QA_OPTIONS)
    except llm.LLMError as exc:
        return _refusal(f"No reliable answer: {exc}.", hits), {"error": str(exc), "raw_response": exc.raw_text}
    parsed = QAReply.model_validate(reply.data)
    cited = [handles[h] for h in dict.fromkeys(c.strip("[] ") for c in parsed.citations) if h in handles]
    citations = [Citation(thread_key=t.key, message_id=m.message_id, subject=m.subject) for t, m in cited]
    if parsed.refused or citations:
        result = QAAnswer(answer=parsed.answer, citations=citations, confidence=parsed.confidence,
                          refused=parsed.refused, retrieved=_retrieved(hits))
    else:
        result = _refusal("I can't back an answer with messages from the mailbox, so I won't guess.", hits)
    audit = {"model": reply.model, "prompt_version": config.QA_PROMPT_VERSION, "request_id": reply.request_id,
             "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens,
             "raw_response": reply.raw_text}
    return result, audit


def render_context(hits: list[Hit]) -> tuple[str, dict[str, tuple[Thread, Message]]]:
    """The retrieved threads as text for the model, each message labelled [M1], [M2]… (no internal IDs).

    Output: (text, handle → (thread, message)) so cited handles can be mapped back.
    """
    handles: dict[str, tuple[Thread, Message]] = {}
    blocks = []
    for number, hit in enumerate(hits, start=1):
        lines = [f"<thread>\nThread {number}: {hit.thread.subject}"]
        for m in hit.thread.messages:
            handle = f"M{len(handles) + 1}"
            handles[handle] = (hit.thread, m)
            sender = f"{m.sent_from}{' (internal)' if m.from_internal else ''}"
            lines.append(f"[{handle}] {m.date_sent:%a %Y-%m-%d %H:%M} | From: {sender} | To: {', '.join(m.sent_to)} "
                         f"| Subject: {m.subject}")
            if m.attachments:
                lines.append("Attachments: " + ", ".join(a.filename for a in m.attachments))
            lines.append(m.body.strip())
        blocks.append("\n".join([*lines, "</thread>"]))
    return "\n\n".join(blocks), handles


def _retrieved(hits: list[Hit]) -> list[RetrievedThread]:
    """The search results as shown to the handler."""
    return [RetrievedThread(thread_key=h.thread.key, subject=h.thread.subject, score=h.score, reasons=h.reasons)
            for h in hits]


def _refusal(message: str, hits: list[Hit]) -> QAAnswer:
    """A refused answer: no claim is made, but the handler still sees what the search looked at."""
    return QAAnswer(answer=message, citations=[], confidence=0.0, refused=True, retrieved=_retrieved(hits))
