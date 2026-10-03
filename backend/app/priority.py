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
from datetime import date, timedelta

from app import config
from app.models import PriorityResult, Thread, TriageResult

# Signals that carry customer harm, legal, regulatory or fraud exposure: act today.
P1_SIGNALS = ("injury", "make_safe_urgent", "legal_threat", "regulatory", "fraud_flag",
              "vulnerable_customer", "complaint")
# Signals that mean someone is waiting on us: act this week.
P2_SIGNALS = ("repeat_chase", "fnol", "payment_or_authority_pending")

LEVEL_MEANING = {"P1": "P1, act today", "P2": "P2, act this week", "P3": "P3, normal priority"}


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
    """P2 when the thread is older than UNANSWERED_WORKING_DAYS and nobody at Pinnacle has replied."""
    age = working_days_between(thread.messages[0].date_sent.date(), now)
    replied = any(m.from_internal for m in thread.messages[1:])
    if replied or age <= config.UNANSWERED_WORKING_DAYS:
        return []
    return [f"p2_unanswered: no reply from us in {age} working days"]


# Evaluated in order for action_required threads; the highest level that fires wins.
LEVEL_RULES: list[Callable[[TriageResult, Thread, date], list[str]]] = [
    p1_risk_signals, p1_deadline_due,
    p2_urgency_or_importance, p2_waiting_signals, p2_deadline_this_week, p2_unanswered,
]


def compute_priority(triage: TriageResult, thread: Thread, now: date) -> PriorityResult:
    """Apply the rules to one thread.

    Inputs: the triage result, the thread (for age and replies), and `now`
    (config.AS_OF_DATE in this demo: the date of the newest email).
    Output: PriorityResult with bucket, level, the rules that fired and a one-line explanation.
    Order: low confidence → review (even "resolved": an uncertain call is checked by a human);
    then already_resolved → archive; then the category; then the level rules.
    """
    if triage.confidence < config.CONFIDENCE_THRESHOLD:
        rule = f"override_low_confidence: {triage.confidence:.2f} < {config.CONFIDENCE_THRESHOLD}"
        return PriorityResult(level="P2", bucket="review", rules_fired=[rule],
                              explanation="Needs human review: the model is not confident about this thread.")
    if "already_resolved" in triage.signals:
        return PriorityResult(level="P4", bucket="archive", rules_fired=["override_already_resolved"],
                              explanation="P4, no action: the latest message shows the matter is resolved.")
    if triage.category == "irrelevant":
        return PriorityResult(level=None, bucket="ignore", rules_fired=["bucket_ignore: irrelevant"],
                              explanation="Ignore: not part of the claims workload.")
    if triage.category == "informational":
        return PriorityResult(level="P4", bucket="archive", rules_fired=["bucket_archive: informational"],
                              explanation="P4, no action: informational, can be archived.")
    return _action_priority(triage, thread, now)


def _action_priority(triage: TriageResult, thread: Thread, now: date) -> PriorityResult:
    """Level an action_required thread: P1 if any P1 rule fired, else P2 if any P2 rule, else P3."""
    fired = [entry for rule in LEVEL_RULES for entry in rule(triage, thread, now)]
    level = next((lvl for lvl in ("P1", "P2") if any(f.startswith(lvl.lower()) for f in fired)), "P3")
    if level == "P3":
        fired.append("p3_default: action required, no urgency rule fired")
    reasons = [f.split(": ", 1)[1] for f in fired if f.startswith(level.lower())]
    return PriorityResult(level=level, bucket="act", rules_fired=fired,
                          explanation=f"{LEVEL_MEANING[level]}: {'; '.join(reasons)}.")


def working_days_between(start: date, end: date) -> int:
    """Count Mon–Fri days after `start` up to and including `end` (UK bank holidays are ignored)."""
    days = (start + timedelta(days=n) for n in range(1, (end - start).days + 1))
    return sum(1 for d in days if d.weekday() < 5)
