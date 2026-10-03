"""Tests for the API routes against a temporary database filled by the real pipeline (model mocked)."""

from pathlib import Path
from typing import Any

import pytest
from conftest import VALID_TRIAGE
from fastapi.testclient import TestClient

from app import config, pipeline
from app.main import app
from app.models import Thread, TriageRecord, TriageResult


def _fake_triage(thread: Thread, prompt_version: str | None = None) -> TriageRecord:
    """Stand-in for the model: irrelevant for one sender's mail, a P1-worthy complaint for the rest."""
    junk = "dpd.co.uk" in thread.current.sent_from
    result = VALID_TRIAGE | ({"category": "irrelevant", "action_type": "none", "signals": []} if junk
                             else {"signals": ["complaint"]})
    return TriageRecord(result=TriageResult(**result), raw_response="{}", model="claude-haiku-4-5",
                        prompt_version=prompt_version or "test")


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A TestClient over a fresh database holding the real 50 threads, triaged by the fake."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "api.db")
    monkeypatch.setattr(pipeline, "triage_thread", _fake_triage)
    pipeline.run_all()
    return TestClient(app)


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_summary_counts_every_thread(client: TestClient) -> None:
    body: dict[str, Any] = client.get("/summary").json()
    assert body["total_threads"] == 50
    assert body["counts"] == {"P1": 49, "ignore": 1}
    assert body["models"] == ["claude-haiku-4-5"] and body["last_run"] is not None


def test_threads_are_sorted_p1_first_then_oldest(client: TestClient) -> None:
    rows = client.get("/threads").json()
    assert len(rows) == 50 and rows[-1]["bucket"] == "ignore"
    p1_dates = [r["first_date"] for r in rows if r["level"] == "P1"]
    assert p1_dates == sorted(p1_dates)
    assert rows[0]["rules_fired"] == ["p1_risk_signal: complaint"]  # oldest P1: we replied, so no p2_unanswered
    assert rows[0]["sender"] == "p.andj.howard@virginmedia.com"  # the customer, not our own complaints team
    assert rows[0]["explanation"] == "P1, act today: complaint."


def test_threads_can_be_filtered(client: TestClient) -> None:
    assert [r["bucket"] for r in client.get("/threads", params={"bucket": "ignore"}).json()] == ["ignore"]
    assert client.get("/threads", params={"level": "P3"}).json() == []
    assert client.get("/threads", params={"bucket": "nonsense"}).status_code == 422


def test_thread_detail_has_messages_triage_priority_and_audit(client: TestClient) -> None:
    key = client.get("/threads").json()[0]["key"]
    detail = client.get(f"/threads/{key}").json()
    assert detail["thread"]["key"] == key and detail["messages"]
    assert detail["triage"]["prompt_version"] == config.TRIAGE_PROMPT_VERSION
    assert detail["priority"]["level"] == "P1"
    assert [a["event"] for a in detail["audit"]] == ["triage"]


def test_unknown_thread_is_404(client: TestClient) -> None:
    assert client.get("/threads/tnotreal").status_code == 404


def test_run_reports_what_it_did(client: TestClient) -> None:
    body = client.post("/run").json()
    assert (body["triaged"], body["skipped"]) == (0, 50)  # nothing changed since the fixture's run


def test_ask_returns_a_cited_answer(client: TestClient, fake_llm: Any) -> None:
    fake_llm('{"answer": "Yes.", "citations": ["M1"], "confidence": 0.9, "refused": false}')
    body = client.post("/ask", json={"question": "Was there any action required for Bridgegate Brokers?"}).json()
    assert body["refused"] is False and body["citations"][0]["thread_key"] and body["retrieved"]


def test_ask_rejects_an_empty_question(client: TestClient) -> None:
    assert client.post("/ask", json={"question": ""}).status_code == 422
