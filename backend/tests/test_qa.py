"""Tests for Q&A: retrieval on the real mailbox, and answers with a mocked model (no API calls)."""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Callable

import pytest
from conftest import VALID_TRIAGE, FakeClient

from app import config, llm, pipeline, store
from app.ingest import load_threads
from app.models import Thread, TriageRecord, TriageResult
from app.priority import open_work
from app.qa import answer, retrieve, tokens

BRIDGEGATE = "Was there any action required for Bridgegate Brokers?"


def _reply(**fields: Any) -> str:
    """A model reply in the QAReply shape, with defaults."""
    return json.dumps({"answer": "Bridgegate Brokers asked for cover and excess.", "citations": ["M1"],
                       "confidence": 0.9, "refused": False} | fields)


@pytest.fixture(scope="module")
def threads() -> list[Thread]:
    """The real mailbox."""
    return load_threads()


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[sqlite3.Connection]:
    """A temporary database holding the real 50 threads, triaged by a fake (no API call)."""
    monkeypatch.setattr(pipeline, "triage_thread", lambda thread, version=None: TriageRecord(
        result=TriageResult(**VALID_TRIAGE), raw_response="{}", model="fake", prompt_version="test"))
    db = tmp_path / "qa.db"
    pipeline.run_all(db_path=db)
    connection = store.connect(db)
    yield connection
    connection.close()


def test_claim_ref_question_finds_exactly_its_threads(threads: list[Thread]) -> None:
    hits = retrieve("What is outstanding on PIN-MTR-552301?", threads, {}, 12)
    assert len(hits) == 2 and all("claim ref PIN-MTR-552301" in h.reasons for h in hits)


def test_company_name_matches_the_sender_domain(threads: list[Thread]) -> None:
    hits = retrieve(BRIDGEGATE, threads, {}, 12)
    assert hits[0].thread.subject.startswith("PIN-HOM-533661")
    assert any("bridgegatebrokers.co.uk" in reason for reason in hits[0].reasons)


def test_company_names_match_whole_domain_words_not_substrings(threads: list[Thread]) -> None:
    city = retrieve("Anything from the city?", threads, {}, 12)  # once matched steelcity-bodyshop and citydeli-leeds
    assert not any(reason.startswith("company domain") for hit in city for reason in hit.reasons)
    drainage = retrieve("What did Rapid Drainage send?", threads, {}, 12)  # hyphens split the domain into words
    assert "company domain rapid-drainage.co.uk matches 'rapid drainage'" in drainage[0].reasons


def test_triage_tags_find_a_type_the_text_never_names(threads: list[Thread]) -> None:
    caledonia = next(t for t in threads if "771045" in t.subject)  # Caledonia Law never writes "solicitor"
    tagged = {caledonia.key: TriageResult(**VALID_TRIAGE | {"sender_type": "solicitor"})}
    hits = retrieve("Which threads involve a solicitor?", threads, tagged, 12)
    assert any(h.thread.key == caledonia.key and "triage tags: solicitor" in h.reasons for h in hits)


def test_unrelated_question_finds_nothing(threads: list[Thread]) -> None:
    assert retrieve("xyzzy plugh", threads, {}, 12) == []


def test_tokens_drop_filler_and_stem_lightly() -> None:
    assert tokens("Is there anything about flooded vehicles or notices?") == {"flood", "vehicle", "notice"}


def test_answer_maps_handles_to_real_messages_and_sends_no_ids(conn: sqlite3.Connection,
                                                               fake_llm: Callable[..., FakeClient]) -> None:
    client = fake_llm(_reply(citations=["M1", "[M2]", "M99"]))  # M99 does not exist: dropped
    result = answer(BRIDGEGATE, conn)
    bridgegate = next(t for t in store.load_all_threads(conn) if t.subject.startswith("PIN-HOM-533661"))
    assert not result.refused
    assert [c.message_id for c in result.citations] == [m.message_id for m in bridgegate.messages]
    assert [(c.sent_from, c.date_sent) for c in result.citations] == [(m.sent_from, m.date_sent)
                                                                       for m in bridgegate.messages]
    request = client.requests[0]
    assert request["model"] == config.QA_MODEL and "extra_body" not in request  # no temperature for Sonnet
    sent = request["system"] + request["messages"][0]["content"]
    assert "thr_" not in sent and "@mail.pinnacle-insurance.co.uk>" not in sent  # handles only, no IDs
    assert "<workload>" in sent and "Priority: P2, act this week | why: p2_waiting_signal: repeat_chase" in sent


def test_an_answer_without_a_valid_citation_becomes_a_refusal(conn: sqlite3.Connection,
                                                              fake_llm: Callable[..., FakeClient]) -> None:
    fake_llm(_reply(answer="Probably yes.", citations=["M99"]))
    result = answer(BRIDGEGATE, conn)
    assert result.refused and result.citations == [] and "won't guess" in result.answer


def test_the_model_can_refuse(conn: sqlite3.Connection, fake_llm: Callable[..., FakeClient]) -> None:
    fake_llm(_reply(answer="I can't find anything about Zenith Brokers in the mailbox.", citations=[],
                    refused=True))
    result = answer("What did Zenith Brokers ask us to do?", conn)
    assert result.refused and "Zenith" in result.answer and result.retrieved


def test_a_question_no_email_matches_still_gets_the_open_workload(conn: sqlite3.Connection,
                                                                  fake_llm: Callable[..., FakeClient]) -> None:
    client = fake_llm(_reply(answer="Start with the oldest thread.", citations=["M1"]))
    result = answer("xyzzy plugh", conn)  # no email shares a word with it: only the workload can answer
    first = open_work(store.load_all_threads(conn), store.load_priorities(conn))[0]
    assert not result.refused and result.retrieved == []
    assert [c.message_id for c in result.citations] == [first.current.message_id]  # M1: the top line's latest email
    sent = client.requests[0]["messages"][0]["content"]
    assert "(no thread shares words with the question)" in sent
    assert "<workload>\nOpen threads: " in sent  # the counts come first, so the model never counts lines itself


def test_an_empty_mailbox_refuses_without_calling_the_model(tmp_path: Path,
                                                            fake_llm: Callable[..., FakeClient]) -> None:
    client = fake_llm()
    empty = store.connect(tmp_path / "empty.db")
    result = answer("What should I do first?", empty)
    empty.close()
    assert result.refused and client.requests == []


def test_every_question_is_audited(conn: sqlite3.Connection, fake_llm: Callable[..., FakeClient]) -> None:
    fake_llm(_reply())
    answer(BRIDGEGATE, conn)
    detail = json.loads(conn.execute("SELECT detail FROM audit_log WHERE event = 'ask'").fetchone()["detail"])
    assert detail["question"] == BRIDGEGATE and detail["retrieved"] and detail["raw_response"] and detail["workload"]
    assert detail["prompt_version"] == config.QA_PROMPT_VERSION and detail["answer"]["citations"]


def test_a_failed_question_is_audited_too(conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_key() -> None:
        raise llm.MissingAPIKeyError("ANTHROPIC_API_KEY is not set")
    monkeypatch.setattr(llm, "get_client", no_key)
    with pytest.raises(llm.MissingAPIKeyError):  # main.ask turns it into a 503
        answer(BRIDGEGATE, conn)
    detail = json.loads(conn.execute("SELECT detail FROM audit_log WHERE event = 'ask_error'").fetchone()["detail"])
    assert detail["question"] == BRIDGEGATE and "MissingAPIKeyError" in detail["error"]
