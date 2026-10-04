"""Free-text questions over the mailbox: transparent retrieval, then a cited answer from Claude Sonnet.

Why: handlers ask things like "Was there any action required for Broker X?" or "What should I do first?".
`retrieve` picks threads with scoring a person can follow — an exact claim
reference beats a company named in a domain on the thread, which beats a type the
triage assigned (solicitor, FNOL, fraud…), which beats shared rare words — and
says why each thread matched (no embeddings, D-03). `answer` lets Sonnet answer
only from those threads and the open workload (every thread that needs a person,
in the rules' order, with the rules behind each priority: D-47), citing messages
by neutral handles (M1, M2…; message IDs leak labels, D-07). No valid citation,
no answer (D-29).
"""

import math
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app import config, llm, priority, store
from app.models import CLAIM_REF_PATTERN, Message, PriorityResult, Thread, TriageResult
from app.schemas import Citation, QAAnswer, RetrievedThread
from app.triage import load_prompt

CLAIM_REF_SCORE = 100.0  # an exact claim reference is the strongest evidence of relevance
PARTY_SCORE = 20.0  # per question word naming a word of a company domain on the thread (sender or recipient)
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
        # Whole words, not substrings: "city" must not match steelcity-bodyshop. A word of 5+ letters may
        # also start a domain word, so "bridgegate" finds bridgegatebrokers, where the name runs into the trade.
        names = [n for n in re.split(r"[-\d]+", domain.split(".")[0]) if n]
        matched = [w for w in party_words if any(w == n or (len(w) >= 5 and n.startswith(w)) for n in names)]
        if matched:
            score += PARTY_SCORE * len(matched)
            reasons.append(f"company domain {domain} matches '{' '.join(matched)}'")
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

    Input: the question and an open database connection (threads, triage, priorities, audit log).
    Output: QAAnswer. The model always sees the open workload, so "what should I do first?" works even when
    no email shares its words. The question, what the model was shown, its raw reply and the answer are audited.
    """
    started = time.perf_counter()
    threads, triage = store.load_all_threads(conn), store.load_triage_results(conn)
    priorities = store.load_priorities(conn)
    hits, work = retrieve(question, threads, triage, config.QA_TOP_K), priority.open_work(threads, priorities)
    if hits or work:
        try:
            result, audit = _ask_model(question, hits, *render_context(hits, work, triage, priorities))
        except Exception as exc:  # no key, key rejected, API down: logged, then main.ask answers 502/503
            store.log_event(conn, "ask_error", {"question": question, "error": f"{type(exc).__name__}: {exc}"})
            conn.commit()
            raise
    else:
        result, audit = _refusal("I can't find anything about that in the mailbox.", hits), {}
    store.log_event(conn, "ask", {"question": question, "retrieved": [r.model_dump() for r in result.retrieved],
                                  "workload": [t.key for t in work], **audit,
                                  "answer": result.model_dump(mode="json", exclude={"retrieved"}),
                                  "seconds": round(time.perf_counter() - started, 1)})
    conn.commit()
    return result


def _ask_model(question: str, hits: list[Hit], context: str,
               handles: dict[str, tuple[Thread, Message]]) -> tuple[QAAnswer, dict[str, Any]]:
    """Ask Sonnet over the evidence; map its handles to real messages; enforce "no citation, no answer"."""
    user = (f"Today is {config.AS_OF_DATE:%A %d %B %Y} (the date of the newest email).\n\n"
            f"<question>\n{question}\n</question>\n\n{context}")
    try:
        reply = llm.call_json(config.QA_MODEL, load_prompt(config.QA_PROMPT_VERSION), user,
                              max_tokens=config.QA_MAX_TOKENS, schema=QAReply, **config.QA_OPTIONS)
    except llm.LLMError as exc:
        return _refusal(f"No reliable answer: {exc}.", hits), {"error": str(exc), "raw_response": exc.raw_text}
    parsed = QAReply.model_validate(reply.data)
    cited = [handles[h] for h in dict.fromkeys(c.strip("[] ") for c in parsed.citations) if h in handles]
    citations = [Citation(thread_key=t.key, message_id=m.message_id, subject=m.subject, sent_from=m.sent_from,
                          date_sent=m.date_sent) for t, m in cited]
    if parsed.refused or citations:
        result = QAAnswer(answer=parsed.answer, citations=citations, confidence=parsed.confidence,
                          refused=parsed.refused, retrieved=_retrieved(hits))
    else:
        result = _refusal("I can't back an answer with messages from the mailbox, so I won't guess.", hits)
    audit = {"model": reply.model, "prompt_version": config.QA_PROMPT_VERSION, "request_id": reply.request_id,
             "input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens,
             "raw_response": reply.raw_text}
    return result, audit


def render_context(hits: list[Hit], work: list[Thread], triage: dict[str, TriageResult],
                   priorities: dict[str, PriorityResult]) -> tuple[str, dict[str, tuple[Thread, Message]]]:
    """The model's evidence: the open workload, one line per thread in the rules' order, then the matched
    threads' emails. Each email gets a neutral handle ([M1], [M2]…; no internal IDs); a workload line carries
    its thread's latest. Output: (text, handle → (thread, message)), so cited handles can be mapped back."""
    handles: dict[str, tuple[Thread, Message]] = {}
    blocks = [_thread_block(n, h.thread, triage, priorities, handles) for n, h in enumerate(hits, start=1)]
    lines = [_workload_line(t, triage.get(t.key), priorities.get(t.key), _handle(handles, t, t.current))
             for t in work]
    workload = "\n".join([priority.workload_header(work, priorities), *lines]) if work else "(no open threads)"
    extract = "\n\n".join(blocks) or "(no thread shares words with the question)"
    return f"<workload>\n{workload}\n</workload>\n\n<mailbox_extract>\n{extract}\n</mailbox_extract>", handles


def _thread_block(number: int, thread: Thread, triage: dict[str, TriageResult],
                  priorities: dict[str, PriorityResult], handles: dict[str, tuple[Thread, Message]]) -> str:
    """One matched thread for the model: its subject, the rules' verdict, then every email under its handle."""
    lines = [f"<thread>\nThread {number}: {thread.subject}",
             f"Priority: {priority.verdict_line(priorities.get(thread.key), triage.get(thread.key))}"]
    for m in thread.messages:
        sender = f"{m.sent_from}{' (internal)' if m.from_internal else ''}"
        lines.append(f"[{_handle(handles, thread, m)}] {m.date_sent:%a %Y-%m-%d %H:%M} | From: {sender} "
                     f"| To: {', '.join(m.sent_to)} | Subject: {m.subject}")
        if m.attachments:
            lines.append("Attachments: " + ", ".join(a.filename for a in m.attachments))
        lines.append(m.body.strip())
    return "\n".join([*lines, "</thread>"])


def _workload_line(thread: Thread, triage: TriageResult | None, prio: PriorityResult | None, handle: str) -> str:
    """One open thread as the workload lists it: claim, line of business, who waits, subject, the rules' verdict."""
    claim = thread.claim_refs[0] if thread.claim_refs else (triage and triage.claim_ref) or "no claim ref"
    sender = next((m.sent_from for m in reversed(thread.messages) if not m.from_internal), thread.current.sent_from)
    line = triage.line_of_business if triage else "unknown"
    return f"[{handle}] {claim} | {line} | from {sender} | {thread.subject} | {priority.verdict_line(prio, triage)}"


def _handle(handles: dict[str, tuple[Thread, Message]], thread: Thread, message: Message) -> str:
    """The message's handle (M1, M2…): the one it already has, or the next free one."""
    for handle, (_, known) in handles.items():
        if known.message_id == message.message_id:
            return handle
    handles[f"M{len(handles) + 1}"] = (thread, message)
    return f"M{len(handles)}"


def _retrieved(hits: list[Hit]) -> list[RetrievedThread]:
    """The search results as shown to the handler."""
    return [RetrievedThread(thread_key=h.thread.key, subject=h.thread.subject, score=h.score, reasons=h.reasons)
            for h in hits]


def _refusal(message: str, hits: list[Hit]) -> QAAnswer:
    """A refused answer: no claim is made, but the handler still sees what the search looked at."""
    return QAAnswer(answer=message, citations=[], confidence=0.0, refused=True, retrieved=_retrieved(hits))
