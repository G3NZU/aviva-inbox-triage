"""Tests for pipeline idempotency: what is re-triaged, what is skipped, what is audited."""

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import VALID_TRIAGE

from app import config, pipeline, store
from app.models import Thread, TriageRecord, TriageResult


def _message(message_id: str, date_sent: str) -> dict[str, Any]:
    """One raw email in the dataset's shape."""
    return {
        "body": "Please confirm cover.", "subject": "PIN-HOM-533661 - Claim", "sent_from": "broker@example.co.uk",
        "sent_to": ["claims@pinnacle-insurance.co.uk"], "sent_cc": None, "date_sent": date_sent,
        "attachments": None, "importance_flag": None, "message_id": message_id, "thread_id": "thr_hom_x",
    }


def _write_mailbox(path: Path, threads: list[list[dict[str, Any]]]) -> Path:
    """Write a mailbox file with the given threads and return its path."""
    path.write_text(json.dumps({"emails": [{"messages": t} for t in threads]}), encoding="utf-8")
    return path


class FakeTriage:
    """Replaces triage_thread: records which threads were sent to the model; can fail on demand."""

    def __init__(self) -> None:
        """Start with no calls and no failures."""
        self.calls: list[str] = []
        self.fail: set[str] = set()

    def __call__(self, thread: Thread, prompt_version: str | None = None) -> TriageRecord:
        """Return a valid record (or an error record for keys in `fail`) without any API call."""
        self.calls.append(thread.key)
        error = "simulated failure" if thread.key in self.fail else None
        return TriageRecord(result=TriageResult(**VALID_TRIAGE), raw_response="{}", model="claude-haiku-4-5",
                            prompt_version=prompt_version or "?", input_tokens=10, output_tokens=5, error=error)


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[FakeTriage, Path, Path]:
    """A two-thread mailbox, an empty database and a fake triage function."""
    fake = FakeTriage()
    monkeypatch.setattr(pipeline, "triage_thread", fake)
    data = _write_mailbox(tmp_path / "mail.json", [[_message("<a1>", "2026-02-01T09:00:00Z")],
                                                    [_message("<b1>", "2026-02-02T09:00:00Z")]])
    return fake, data, tmp_path / "test.db"


def test_rerun_skips_unchanged_threads_and_force_redoes_all(setup: tuple[FakeTriage, Path, Path]) -> None:
    fake, data, db = setup
    first = pipeline.run_all(data_path=data, db_path=db)
    assert (first.triaged, first.skipped) == (2, 0)
    second = pipeline.run_all(data_path=data, db_path=db)
    assert (second.triaged, second.skipped) == (0, 2)
    forced = pipeline.run_all(force=True, data_path=data, db_path=db)
    assert forced.triaged == 2 and len(fake.calls) == 4


def test_a_new_message_retriages_only_its_thread(setup: tuple[FakeTriage, Path, Path]) -> None:
    fake, data, db = setup
    pipeline.run_all(data_path=data, db_path=db)
    _write_mailbox(data, [[_message("<a1>", "2026-02-01T09:00:00Z"), _message("<a2>", "2026-02-03T09:00:00Z")],
                          [_message("<b1>", "2026-02-02T09:00:00Z")]])
    summary = pipeline.run_all(data_path=data, db_path=db)
    assert (summary.triaged, summary.skipped) == (1, 1)
    assert fake.calls[-1] == fake.calls[0]  # the thread that started with <a1>


def test_failed_triage_is_retried_on_the_next_run(setup: tuple[FakeTriage, Path, Path]) -> None:
    fake, data, db = setup
    pipeline.run_all(data_path=data, db_path=db)
    fake.fail = {fake.calls[0]}
    pipeline.run_all(force=True, data_path=data, db_path=db)
    fake.fail = set()
    summary = pipeline.run_all(data_path=data, db_path=db)
    assert summary.triaged == 1 and fake.calls[-1] == fake.calls[0]


def test_new_prompt_version_retriages_everything(setup: tuple[FakeTriage, Path, Path],
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    fake, data, db = setup
    pipeline.run_all(data_path=data, db_path=db)
    monkeypatch.setattr(config, "TRIAGE_PROMPT_VERSION", config.TRIAGE_PROMPT_VERSION + "_next")
    assert pipeline.run_all(data_path=data, db_path=db).triaged == 2


def test_every_call_and_run_is_in_the_audit_log(setup: tuple[FakeTriage, Path, Path]) -> None:
    _, data, db = setup
    pipeline.run_all(data_path=data, db_path=db)
    conn = store.connect(db)
    events = [row["event"] for row in conn.execute("SELECT event FROM audit_log ORDER BY id")]
    triage = conn.execute("SELECT prompt_version, model, raw_response, created_at FROM triage").fetchall()
    conn.close()
    assert events == ["triage", "triage", "pipeline_run"]
    assert all(row["prompt_version"] == config.TRIAGE_PROMPT_VERSION and row["model"] and row["created_at"]
               for row in triage)
