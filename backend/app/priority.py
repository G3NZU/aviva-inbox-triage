"""Priority rules: turn a triage result into a bucket and a level, listing every rule that fired.

Why: how much a thread matters to the business is policy, not judgement
(D-01). Each rule is a small named function, so the policy reads like a
checklist, is tested rule by rule, and every priority shows the rules behind
it. No LLM is called here, and no rule reads sender_type or importance_flag:
priority depends on what is asked and what is at stake, not on who asks.

Levels: P1 act today · P2 this week · P3 normal · P4 no action.
Buckets: act · review (a human must check the triage) · archive · ignore.
"""

from collections.abc import Callable
from datetime import date, datetime, timedelta

from app import config
from app.models import Level, PriorityResult, Reason, Thread, TriageResult

# Signals that carry customer harm, legal, regulatory or fraud exposure: act today.
P1_SIGNALS = ("injury", "make_safe_urgent", "legal_threat", "regulatory", "fraud_flag",
              "vulnerable_customer", "complaint")
# Signals that mean someone is waiting on us: act this week.
P2_SIGNALS = ("repeat_chase", "fnol", "payment_or_authority_pending")

LEVEL_MEANING = {"P1": "P1, act today", "P2": "P2, act this week", "P3": "P3, normal priority"}
LEVEL_ORDER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}  # no level (ignored, or not read yet) sorts last


def workload_rank(level: Level | None, first_date: datetime) -> tuple[int, datetime]:
    """Where a thread sits in the workload: the most urgent level first, then the oldest thread first.

    Why: the order of work is policy, so it is defined once, here, and used by the workload list
    (GET /threads) and by Q&A, which hands the model the open work in this order.
    """
    return LEVEL_ORDER.get(level or "", 5), first_date


OPEN_BUCKETS = ("act", "review")  # the buckets that need a person: the open workload
BUCKET_MEANING = {"review": "needs a check: the AI was unsure, so a person decides", "archive": "P4, no action needed",
                  "ignore": "not claims work"}


def open_work(threads: list[Thread], priorities: dict[str, PriorityResult]) -> list[Thread]:
    """The open workload: the threads that need a person (bucket act or review), most urgent first.

    Why: Q&A shows the model this list, so "what should I do first?" is answered in the rules'
    order (workload_rank), never in an order the model invents.
    Inputs: the threads and their stored priorities by key. Output: the open threads, in order.
    """
    work = [t for t in threads if t.key in priorities and priorities[t.key].bucket in OPEN_BUCKETS]
    return sorted(work, key=lambda t: workload_rank(priorities[t.key].level, t.messages[0].date_sent))


def workload_header(work: list[Thread], priorities: dict[str, PriorityResult]) -> str:
    """The size of the open workload in one line for the Q&A model, e.g. "Open threads: 32; P1 (act today): 21.".

    Why: an answer to "what should I focus on?" says how many P1 threads remain. Counting is code's job: the
    model reads the number instead of counting 30-odd lines and perhaps miscounting (D-52).
    Inputs: the open work (from open_work) and the priorities by key. Output: the line.
    """
    p1 = sum(1 for t in work if priorities[t.key].level == "P1")
    return f"Open threads: {len(work)}; P1 (act today): {p1}."


def verdict_line(result: PriorityResult | None, triage: TriageResult | None) -> str:
    """The rules' verdict in one line for the Q&A model: the level, the rules that set it and, for open
    work, the wait and the AI's suggested next step, e.g. "P1, act today | why: p1_risk_signal: complaint |
    waiting on us: 0 working days | next step: …". Answers built on it agree with the workload list.
    """
    if result is None:
        return "not triaged yet"
    why = "; ".join(f"{r.rule}: {r.detail}" if r.detail else r.rule
                    for r in reasons(result.rules_fired, result.level) if r.sets_level)
    label = LEVEL_MEANING.get(result.level or "", "") if result.bucket == "act" else BUCKET_MEANING[result.bucket]
    parts = [label, f"why: {why}"]
    if result.bucket in OPEN_BUCKETS:
        step = (triage.action_summary if triage else "") or "read the emails and decide"
        parts += [f"waiting on us: {result.waiting_days} working days", f"next step: {step}"]
    return " | ".join(parts)


def p1_risk_signals(triage: TriageResult, thread: Thread, now: date) -> list[str]:
    """P1 for each signal of harm, legal, regulatory or fraud exposure."""
    return [f"p1_risk_signal: {s}" for s in triage.signals if s in P1_SIGNALS]


def p1_deadline_due(triage: TriageResult, thread: Thread, now: date) -> list[str]:
    """P1 when a stated deadline is overdue or due within P1_DEADLINE_DAYS of `now`."""
    deadline = triage.deadline_mentioned
    if deadline is None or (deadline - now).days > config.P1_DEADLINE_DAYS:
        return []
    days = (deadline - now).days
    when = f"{-days} day(s) overdue" if days < 0 else f"due in {days} day(s)"
    return [f"p1_deadline_due: {deadline} ({when})"]


def p2_urgency_or_importance(triage: TriageResult, thread: Thread, now: date) -> list[str]:
    """P2 when the model rates urgency (how soon) or importance (how much is at stake) high."""
    return ([f"p2_{name}_high: {name} is high" for name, value in
             (("urgency", triage.urgency), ("importance", triage.importance)) if value == "high"])


def p2_waiting_signals(triage: TriageResult, thread: Thread, now: date) -> list[str]:
    """P2 for each signal that someone is waiting on us: chasing, a new claim, money or authority."""
    return [f"p2_waiting_signal: {s}" for s in triage.signals if s in P2_SIGNALS]


def p2_deadline_this_week(triage: TriageResult, thread: Thread, now: date) -> list[str]:
    """P2 when a stated deadline falls after the P1 window but within P2_DEADLINE_DAYS."""
    deadline = triage.deadline_mentioned
    if deadline is None or not config.P1_DEADLINE_DAYS < (deadline - now).days <= config.P2_DEADLINE_DAYS:
        return []
    return [f"p2_deadline_this_week: {deadline} (due in {(deadline - now).days} days)"]


def p2_unanswered(triage: TriageResult, thread: Thread, now: date) -> list[str]:
    """P2 when the latest message came from outside Pinnacle more than UNANSWERED_WORKING_DAYS ago."""
    waited = waiting_days(thread, now)
    if waited <= config.UNANSWERED_WORKING_DAYS:
        return []
    return [f"p2_unanswered: waiting on us for {waited} working days"]


# Evaluated in order for action_required threads; the highest level that fires wins. Each rule takes
# (triage, thread, now) and returns "name: detail" entries ([] when it does not fire); the p1_/p2_ prefix
# of the name is the level it sets (_action_priority and _sets_level rely on it).
LEVEL_RULES: list[Callable[[TriageResult, Thread, date], list[str]]] = [
    p1_risk_signals, p1_deadline_due,
    p2_urgency_or_importance, p2_waiting_signals, p2_deadline_this_week, p2_unanswered,
]


def compute_priority(triage: TriageResult, thread: Thread, now: date) -> PriorityResult:
    """Apply the rules to one thread.

    Inputs: the triage result, the thread (for who wrote last, and when), and `now`
    (config.AS_OF_DATE in this demo: the date of the newest email).
    Output: PriorityResult with bucket, level, the rules that fired, a one-line explanation and,
    for every bucket, the working days the latest outside sender has been waiting on us.
    Order: low confidence → review (even "resolved": an uncertain call is checked by a human);
    then already_resolved → archive; then the category; then the level rules.
    """
    waited = waiting_days(thread, now)
    if triage.confidence < config.CONFIDENCE_THRESHOLD:
        rule = f"override_low_confidence: {triage.confidence:.2f} < {config.CONFIDENCE_THRESHOLD}"
        return PriorityResult(level="P2", bucket="review", rules_fired=[rule], waiting_days=waited,
                              explanation="Needs human review: the model is not confident about this thread.")
    if "already_resolved" in triage.signals:
        return PriorityResult(level="P4", bucket="archive", rules_fired=["override_already_resolved"],
                              waiting_days=waited,
                              explanation="P4, no action: the latest message shows the matter is resolved.")
    if triage.category == "irrelevant":
        return PriorityResult(level=None, bucket="ignore", rules_fired=["bucket_ignore: irrelevant"],
                              waiting_days=waited, explanation="Ignore: not part of the claims workload.")
    if triage.category == "informational":
        return PriorityResult(level="P4", bucket="archive", rules_fired=["bucket_archive: informational"],
                              waiting_days=waited, explanation="P4, no action: informational, can be archived.")
    return _action_priority(triage, thread, now, waited)


def _action_priority(triage: TriageResult, thread: Thread, now: date, waited: int) -> PriorityResult:
    """Level an action_required thread: P1 if any P1 rule fired, else P2 if any P2 rule, else P3."""
    fired = [entry for rule in LEVEL_RULES for entry in rule(triage, thread, now)]
    level = next((lvl for lvl in ("P1", "P2") if any(f.startswith(lvl.lower()) for f in fired)), "P3")
    if level == "P3":
        fired.append("p3_default: action required, no urgency rule fired")
    deciding = [r.detail for r in reasons(fired, level) if r.sets_level]
    return PriorityResult(level=level, bucket="act", rules_fired=fired, waiting_days=waited,
                          explanation=f"{LEVEL_MEANING[level]}: {'; '.join(deciding)}.")


def reasons(rules_fired: list[str], level: Level | None) -> list[Reason]:
    """Split each "rule: detail" entry and mark the rules that set the level.

    Why: the UI shows "why" in plain words, and which rules decided a priority is policy, so it
    is worked out here, next to the rules, not in the browser. A p1_/p2_/p3_ rule sets the level
    when its prefix matches the level; overrides and bucket rules always set it.
    Inputs: a stored rules_fired list and its level. Output: one Reason per entry, in order.
    """
    split = [(entry.split(": ", 1) + [""])[:2] for entry in rules_fired]
    return [Reason(rule=rule, detail=detail, sets_level=_sets_level(rule, level)) for rule, detail in split]


def _sets_level(rule: str, level: Level | None) -> bool:
    """True when a level rule matches the level (p1_ for P1 ...), or for any override or bucket rule."""
    prefix = rule.split("_", 1)[0]
    return prefix == (level or "").lower() if prefix in ("p1", "p2", "p3") else True


def waiting_since(thread: Thread) -> date | None:
    """The date someone outside Pinnacle has been waiting on us since, or None if nobody is.

    Why: who wrote last decides whose move it is. If the latest message came from outside,
    the clock runs from that message, even when we replied earlier in the thread; if we sent
    it, the next move is theirs. (A holding reply from us therefore stops the clock: the
    category and the deadline rules still cover the promise it makes.)
    Input: the thread. Output: the latest message's date, or None when Pinnacle sent it.
    """
    return None if thread.current.from_internal else thread.current.date_sent.date()


def waiting_days(thread: Thread, now: date) -> int:
    """Working days from waiting_since(thread) to `now`; 0 when nobody is waiting on us."""
    since = waiting_since(thread)
    return working_days_between(since, now) if since else 0


def working_days_between(start: date, end: date) -> int:
    """Count Mon–Fri days after `start` up to and including `end` (UK bank holidays are ignored)."""
    days = (start + timedelta(days=n) for n in range(1, (end - start).days + 1))
    return sum(1 for d in days if d.weekday() < 5)
