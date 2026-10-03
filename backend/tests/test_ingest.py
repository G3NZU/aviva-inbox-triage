"""Tests for loading threads and for the model view (ordering, current state, no label leaks)."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app import config
from app.ingest import load_threads, thread_for_model
from app.models import Message, Thread


def _msg(message_id: str, date_sent: str, body: str = "Hello", **overrides: Any) -> dict[str, Any]:
    """Build one raw email in the dataset's shape (nulls where the dataset has nulls)."""
    raw = {
        "body": body,
        "subject": "Subject",
        "sent_from": "broker@example.co.uk",
        "sent_to": ["claims@pinnacle-insurance.co.uk"],
        "sent_cc": None,
        "date_sent": date_sent,
        "attachments": None,
        "importance_flag": None,
        "message_id": message_id,
        "thread_id": "thr_irr_test_01",
    }
    return {**raw, **overrides}


def _load_one(tmp_path: Path, messages: list[dict[str, Any]]) -> Thread:
    """Write a one-thread mailbox file and load it back through `load_threads`."""
    path = tmp_path / "mailbox.json"
    path.write_text(json.dumps({"emails": [{"messages": messages}]}), encoding="utf-8")
    [thread] = load_threads(path)
    return thread


@pytest.fixture(scope="module")
def real_threads() -> list[Thread]:
    """The real dataset, loaded once for the module."""
    return load_threads(config.DATA_PATH)


def test_dataset_has_50_threads_and_95_messages(real_threads: list[Thread]) -> None:
    assert len(real_threads) == 50
    assert sum(len(t.messages) for t in real_threads) == 95


def test_messages_are_sorted_and_latest_is_current(tmp_path: Path) -> None:
    thread = _load_one(
        tmp_path,
        [_msg("<b>", "2026-02-03T09:00:00Z", body="second"), _msg("<a>", "2026-02-01T09:00:00Z", body="first")],
    )
    assert [m.body for m in thread.messages] == ["first", "second"]
    assert thread.current.message_id == "<b>"
    assert thread.subject == "Subject"


def test_every_real_thread_is_oldest_first(real_threads: list[Thread]) -> None:
    for thread in real_threads:
        dates = [m.date_sent for m in thread.messages]
        assert dates == sorted(dates)
        assert thread.current.date_sent == max(dates)


def test_claim_refs_come_from_subjects_and_bodies(tmp_path: Path) -> None:
    thread = _load_one(
        tmp_path,
        [
            _msg("<a>", "2026-02-01T09:00:00Z", body="See PIN-MTR-552301 and PIN-HOM-12345 (too short)."),
            _msg("<b>", "2026-02-02T09:00:00Z", body="Again PIN-MTR-552301", subject="RE: PIN-LIA-744552"),
        ],
    )
    assert thread.claim_refs == ["PIN-LIA-744552", "PIN-MTR-552301"]


def test_nulls_become_empty_lists_and_participants_are_deduplicated(tmp_path: Path) -> None:
    thread = _load_one(
        tmp_path,
        [
            _msg("<a>", "2026-02-01T09:00:00Z"),
            _msg("<b>", "2026-02-02T09:00:00Z", sent_from="Claims@Pinnacle-Insurance.co.uk", sent_cc=["x@y.com"]),
        ],
    )
    assert thread.messages[0].sent_cc == [] and thread.messages[0].attachments == []
    assert thread.participants == ["broker@example.co.uk", "claims@pinnacle-insurance.co.uk", "x@y.com"]


def test_thread_id_is_dropped_on_load() -> None:
    assert "thread_id" not in Message.model_fields


def test_thread_id_never_reaches_the_model_view(real_threads: list[Thread]) -> None:
    assert "thr_" in config.DATA_PATH.read_text(encoding="utf-8")  # the leak exists in the source...
    for thread in real_threads:
        assert "thr_" not in thread_for_model(thread)  # ...but never in what the model reads


def test_message_ids_never_reach_the_model_view(real_threads: list[Thread]) -> None:
    for thread in real_threads:
        view = thread_for_model(thread)
        assert not any(m.message_id in view for m in thread.messages)


def test_thread_keys_are_unique_stable_and_label_free(real_threads: list[Thread]) -> None:
    keys = [t.key for t in real_threads]
    assert len(set(keys)) == len(keys)
    assert all(re.fullmatch(r"t[0-9a-f]{8}", k) for k in keys)  # hex cannot spell hom/irr/info/...
    assert keys == [t.key for t in load_threads(config.DATA_PATH)]


def test_model_view_shows_content_marks_latest_and_internal(tmp_path: Path) -> None:
    attachment = {"filename": "Claim_Form.pdf", "filesize": 1, "filetype": "application/pdf"}
    thread = _load_one(
        tmp_path,
        [
            _msg("<a>", "2026-02-02T10:48:00Z", body="Please confirm cover.", attachments=[attachment]),
            _msg("<b>", "2026-02-02T12:00:00Z", body="We will.", sent_from="home.claims@pinnacle-insurance.co.uk",
                 importance_flag="high"),
        ],
    )
    view = thread_for_model(thread)
    assert "Date: Mon 2026-02-02 10:48 UTC" in view
    assert "From: broker@example.co.uk\n" in view
    assert "From: home.claims@pinnacle-insurance.co.uk (internal)" in view
    assert "Attachments: Claim_Form.pdf" in view
    assert "Please confirm cover." in view and "--- Message 2 of 2 (latest) ---" in view
    assert "importance" not in view.lower() and "high" not in view  # the sender-set flag is never rendered
