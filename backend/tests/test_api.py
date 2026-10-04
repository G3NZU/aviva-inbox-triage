"""Tests for the API routes against a temporary database filled by the real pipeline (model mocked)."""

from pathlib import Path
from collections import Counter
from typing import Any

import pytest
from conftest import VALID_TRIAGE
from fastapi.testclient import TestClient

from app import config, main, pipeline, store
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
    assert body["rules_versions"] == [config.PRIORITY_RULES_VERSION]


def test_summary_reports_the_policy_from_config(client: TestClient) -> None:
    assert client.get("/summary").json()["policy"] == {
        "confidence_threshold": config.CONFIDENCE_THRESHOLD, "p1_deadline_days": config.P1_DEADLINE_DAYS,
        "p2_deadline_days": config.P2_DEADLINE_DAYS, "unanswered_working_days": config.UNANSWERED_WORKING_DAYS}


def test_summary_policy_is_read_when_the_request_is_served(client: TestClient,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "UNANSWERED_WORKING_DAYS", 3)  # not frozen at import time
    assert client.get("/summary").json()["policy"]["unanswered_working_days"] == 3


def test_every_row_names_the_card_it_counts_towards(client: TestClient) -> None:
    rows = client.get("/threads").json()
    assert Counter(r["card"] for r in rows) == client.get("/summary").json()["counts"]


def test_row_reasons_rebuild_rules_fired_and_name_what_set_the_level(client: TestClient) -> None:
    for row in client.get("/threads").json():
        rebuilt = [f"{r['rule']}: {r['detail']}" if r["detail"] else r["rule"] for r in row["reasons"]]
        assert rebuilt == row["rules_fired"]
        assert any(r["sets_level"] for r in row["reasons"])


def test_summary_reports_the_rules_stored_with_the_priorities_not_the_config(client: TestClient) -> None:
    conn = store.connect()  # e.g. a file made by older rules and not yet re-run
    conn.execute("UPDATE priority SET rules_version = 'rules_v0' WHERE thread_key = 'tf293bf62'")
    conn.commit()
    conn.close()
    assert client.get("/summary").json()["rules_versions"] == ["rules_v0", config.PRIORITY_RULES_VERSION]


def test_threads_are_sorted_p1_first_then_oldest(client: TestClient) -> None:
    rows = client.get("/threads").json()
    assert len(rows) == 50 and rows[-1]["bucket"] == "ignore"
    p1_dates = [r["first_date"] for r in rows if r["level"] == "P1"]
    assert p1_dates == sorted(p1_dates)
    assert rows[0]["rules_fired"] == ["p1_risk_signal: complaint"]  # oldest P1: we wrote last, so no p2_unanswered
    assert rows[0]["sender"] == "p.andj.howard@virginmedia.com"  # the customer, not our own complaints team
    assert rows[0]["explanation"] == "P1, act today: complaint."


def test_rows_show_how_long_the_latest_outside_sender_has_waited(client: TestClient) -> None:
    rows = client.get("/threads").json()
    drain = next(r for r in rows if r["key"] == "tf293bf62")  # PIN-HOM-508377: the adjuster wrote last, Mon 9 Feb
    assert drain["waiting_days"] == 9
    assert "p2_unanswered: waiting on us for 9 working days" in drain["rules_fired"]
    assert rows[0]["waiting_days"] == 0  # the oldest P1: we wrote last
    detail = client.get("/threads/tf293bf62").json()
    assert detail["priority"]["waiting_days"] == detail["thread"]["waiting_days"] == 9


def test_a_thread_with_no_priority_yet_shows_no_wait(client: TestClient) -> None:
    conn = store.connect()  # as after a run stopped before the priorities were computed
    conn.execute("DELETE FROM priority WHERE thread_key = 'tf293bf62'")
    conn.commit()
    conn.close()
    row = next(r for r in client.get("/threads").json() if r["key"] == "tf293bf62")
    assert (row["bucket"], row["waiting_days"]) == (None, 0)
    assert client.get("/threads/tf293bf62").json()["priority"] is None


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
    assert detail["priority"]["waiting_days"] == 0  # the oldest P1: we wrote last
    assert [a["event"] for a in detail["audit"]] == ["triage"]


def test_unknown_thread_is_404(client: TestClient) -> None:
    assert client.get("/threads/tnotreal").status_code == 404


def test_run_reports_what_it_did(client: TestClient) -> None:
    body = client.post("/run").json()
    assert (body["triaged"], body["skipped"]) == (0, 50)  # nothing changed since the fixture's run


def test_a_second_run_while_one_is_in_progress_is_refused(client: TestClient) -> None:
    assert main.RUN_LOCK.acquire(blocking=False)  # stands in for a run already in progress
    try:
        response = client.post("/run")
    finally:
        main.RUN_LOCK.release()
    assert response.status_code == 409 and response.json()["detail"] == "A pipeline run is already in progress"
    assert client.post("/run").status_code == 200  # the lock is free again once that run ends


def test_ask_returns_a_cited_answer(client: TestClient, fake_llm: Any) -> None:
    fake_llm('{"answer": "Yes.", "citations": ["M1"], "confidence": 0.9, "refused": false}')
    body = client.post("/ask", json={"question": "Was there any action required for Bridgegate Brokers?"}).json()
    assert body["refused"] is False and body["citations"][0]["thread_key"] and body["retrieved"]
    assert body["citations"][0]["sent_from"] and body["citations"][0]["date_sent"]  # sender and date shown


def test_ask_rejects_an_empty_question(client: TestClient) -> None:
    assert client.post("/ask", json={"question": ""}).status_code == 422
