"""Tests for the priority rules: each rule alone, the boundaries, the overrides, and fairness."""

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest
from conftest import VALID_TRIAGE

from app.models import Message, Thread, TriageResult
from app.priority import P1_SIGNALS, P2_SIGNALS, compute_priority, working_days_between
from app.triage import fallback

NOW = date(2026, 2, 20)  # a Friday, the as-of date of the dataset


def _message(n: int, sender: str, day: date, importance_flag: str | None) -> Message:
    """One message sent at midnight UTC on `day`."""
    return Message(message_id=f"<m{n}>", sent_from=sender, sent_to=["claims@pinnacle-insurance.co.uk"], sent_cc=[],
                   date_sent=datetime(day.year, day.month, day.day, tzinfo=timezone.utc), subject="S", body="B",
                   attachments=[], importance_flag=importance_flag)


def _thread(first: date = NOW, internal_reply: bool = False, importance_flag: str | None = None) -> Thread:
    """A thread started on `first` by an outside sender; optionally answered by Pinnacle the same day."""
    messages = [_message(1, "broker@example.co.uk", first, importance_flag)]
    if internal_reply:
        messages.append(_message(2, "home.claims@pinnacle-insurance.co.uk", first, None))
    return Thread(messages=messages)


def _triage(**changes: Any) -> TriageResult:
    """A calm action_required triage (no signals, medium urgency and importance), with `changes` applied."""
    calm = {"signals": [], "urgency": "medium", "importance": "medium", "deadline_mentioned": None, "confidence": 0.9}
    return TriageResult(**VALID_TRIAGE | calm | changes)


def test_calm_action_is_p3() -> None:
    p = compute_priority(_triage(), _thread(), NOW)
    assert (p.bucket, p.level) == ("act", "P3")
    assert p.rules_fired == ["p3_default: action required, no urgency rule fired"]


@pytest.mark.parametrize("signal", P1_SIGNALS)
def test_each_p1_signal_alone_gives_p1(signal: str) -> None:
    p = compute_priority(_triage(signals=[signal]), _thread(), NOW)
    assert p.level == "P1" and p.rules_fired == [f"p1_risk_signal: {signal}"]


@pytest.mark.parametrize("signal", P2_SIGNALS)
def test_each_p2_signal_alone_gives_p2(signal: str) -> None:
    p = compute_priority(_triage(signals=[signal]), _thread(), NOW)
    assert p.level == "P2" and p.rules_fired == [f"p2_waiting_signal: {signal}"]


@pytest.mark.parametrize("field", ["urgency", "importance"])
def test_high_urgency_or_high_importance_gives_p2(field: str) -> None:
    p = compute_priority(_triage(**{field: "high"}), _thread(), NOW)
    assert p.level == "P2" and p.rules_fired == [f"p2_{field}_high: {field} is high"]


@pytest.mark.parametrize("offset, level", [(-10, "P1"), (0, "P1"), (2, "P1"), (3, "P2"), (7, "P2"), (8, "P3")])
def test_deadline_boundaries(offset: int, level: str) -> None:
    p = compute_priority(_triage(deadline_mentioned=NOW + timedelta(days=offset)), _thread(), NOW)
    assert p.level == level


def test_unanswered_for_more_than_five_working_days_gives_p2() -> None:
    assert compute_priority(_triage(), _thread(first=date(2026, 2, 12)), NOW).level == "P2"  # 6 working days
    assert compute_priority(_triage(), _thread(first=date(2026, 2, 13)), NOW).level == "P3"  # exactly 5


def test_a_reply_from_us_stops_the_unanswered_rule() -> None:
    assert compute_priority(_triage(), _thread(first=date(2026, 2, 2), internal_reply=True), NOW).level == "P3"


def test_working_days_skip_weekends() -> None:
    assert working_days_between(date(2026, 2, 13), date(2026, 2, 16)) == 1  # Friday -> Monday
    assert working_days_between(NOW, NOW) == 0
    assert working_days_between(date(2026, 2, 2), NOW) == 14


def test_buckets_follow_the_category() -> None:
    info = compute_priority(_triage(category="informational", action_type="none"), _thread(), NOW)
    junk = compute_priority(_triage(category="irrelevant", action_type="none"), _thread(), NOW)
    assert (info.bucket, info.level) == ("archive", "P4")
    assert (junk.bucket, junk.level) == ("ignore", None)


@pytest.mark.parametrize("category", ["action_required", "informational", "irrelevant"])
def test_low_confidence_goes_to_review_whatever_the_category(category: str) -> None:
    unsure = compute_priority(_triage(category=category, confidence=0.59, signals=["injury"]), _thread(), NOW)
    assert (unsure.bucket, unsure.level) == ("review", "P2")
    assert compute_priority(_triage(category=category, confidence=0.6), _thread(), NOW).bucket != "review"


def test_already_resolved_archives_even_with_p1_signals() -> None:
    p = compute_priority(_triage(signals=["complaint", "already_resolved"]), _thread(), NOW)
    assert (p.bucket, p.level, p.rules_fired) == ("archive", "P4", ["override_already_resolved"])


def test_low_confidence_beats_already_resolved() -> None:
    assert compute_priority(_triage(signals=["already_resolved"], confidence=0.3), _thread(), NOW).bucket == "review"


def test_unusable_model_output_goes_to_review() -> None:
    p = compute_priority(fallback("triage_v1", "test").result, _thread(), NOW)
    assert (p.bucket, p.level) == ("review", "P2")


def test_sender_type_never_changes_the_priority() -> None:
    # Fairness: a customer and a solicitor with the same request and stakes get the same priority.
    senders = ["customer", "broker", "solicitor", "repairer_supplier", "loss_adjuster", "internal"]
    results = [compute_priority(_triage(sender_type=s, signals=["repeat_chase"]), _thread(), NOW) for s in senders]
    assert all(r == results[0] for r in results)


def test_importance_flag_never_changes_the_priority() -> None:
    flagged = compute_priority(_triage(), _thread(importance_flag="high"), NOW)
    assert flagged == compute_priority(_triage(), _thread(importance_flag=None), NOW)


def test_explanation_gives_the_deciding_reasons_and_rules_list_everything() -> None:
    p = compute_priority(_triage(signals=["complaint"], urgency="high", deadline_mentioned=NOW - timedelta(days=1)),
                         _thread(), NOW)
    assert p.explanation == "P1, act today: complaint; 2026-02-19 (1 day(s) overdue)."
    assert "p2_urgency_high: urgency is high" in p.rules_fired  # lower-level rules are still recorded
