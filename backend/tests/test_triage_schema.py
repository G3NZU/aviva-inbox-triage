"""Tests for turning model replies into triage results, with a mocked model (no API calls)."""

import json
from datetime import date
from typing import Callable

import anthropic
import httpx2
import pytest
from conftest import VALID_TRIAGE, FakeClient, fake_response

from app import config, llm
from app.ingest import load_threads
from app.models import Thread, TriageResult
from app.triage import load_prompt, triage_thread

REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


@pytest.fixture(scope="module")
def threads() -> list[Thread]:
    """The real dataset."""
    return load_threads(config.DATA_PATH)


def _assert_fallback(record_result: TriageResult) -> None:
    """The safe fallback: informational, confidence 0, parse_error → the review bucket."""
    assert record_result.category == "informational"
    assert record_result.confidence == 0.0
    assert record_result.signals == ["parse_error"]


def test_valid_reply_becomes_a_triage_result(threads: list[Thread], fake_llm: Callable[..., FakeClient]) -> None:
    client = fake_llm(json.dumps(VALID_TRIAGE))
    record = triage_thread(threads[0])
    assert record.error is None
    assert record.result == TriageResult(**VALID_TRIAGE)
    assert (record.model, record.prompt_version, record.request_id) == (
        "claude-haiku-4-5", config.TRIAGE_PROMPT_VERSION, "req_test")
    assert (record.input_tokens, record.output_tokens) == (1000, 200)
    [request] = client.requests
    assert request["model"] == config.TRIAGE_MODEL and request["extra_body"] == {"temperature": 0}
    assert request["system"] == load_prompt(config.TRIAGE_PROMPT_VERSION)


def test_reply_in_a_code_fence_is_accepted(threads: list[Thread], fake_llm: Callable[..., FakeClient]) -> None:
    fake_llm("```json\n" + json.dumps(VALID_TRIAGE) + "\n```")
    assert triage_thread(threads[0]).error is None


def test_malformed_json_is_retried_once(threads: list[Thread], fake_llm: Callable[..., FakeClient]) -> None:
    client = fake_llm("Sure! Here is my analysis.", json.dumps(VALID_TRIAGE))
    record = triage_thread(threads[0])
    assert record.error is None and record.result.category == "action_required"
    assert len(client.requests) == 2
    assert "rejected: it was not a single JSON object" in client.requests[1]["messages"][0]["content"]
    assert (record.input_tokens, record.output_tokens) == (2000, 400)  # both attempts are counted


def test_malformed_json_twice_falls_back_to_review(threads: list[Thread], fake_llm: Callable[..., FakeClient]) -> None:
    fake_llm("not json", '{"category": "action_required", "broken"')
    record = triage_thread(threads[0])
    _assert_fallback(record.result)
    assert "rejected twice: it was not a single JSON object" in (record.error or "")
    assert record.raw_response == '{"category": "action_required", "broken"'  # kept for the audit trail


def test_schema_error_is_retried_with_the_problem_quoted(threads: list[Thread],
                                                         fake_llm: Callable[..., FakeClient]) -> None:
    # The failure seen in the first live run: an action type placed in the signals list.
    client = fake_llm(json.dumps(VALID_TRIAGE | {"signals": ["review_document"]}), json.dumps(VALID_TRIAGE))
    record = triage_thread(threads[0])
    assert record.error is None and len(client.requests) == 2
    assert "signals.0: 'review_document' is not allowed" in client.requests[1]["messages"][0]["content"]


def test_schema_error_twice_falls_back(threads: list[Thread], fake_llm: Callable[..., FakeClient]) -> None:
    reply = json.dumps({k: v for k, v in VALID_TRIAGE.items() if k != "urgency"})
    client = fake_llm(reply, reply)
    record = triage_thread(threads[0])
    _assert_fallback(record.result)
    assert "urgency: missing" in (record.error or "") and len(client.requests) == 2


def test_refusal_falls_back(threads: list[Thread], fake_llm: Callable[..., FakeClient]) -> None:
    fake_llm(fake_response("", stop_reason="refusal"))
    record = triage_thread(threads[0])
    _assert_fallback(record.result)
    assert "refusal" in (record.error or "")


def test_transient_api_failure_falls_back(threads: list[Thread], fake_llm: Callable[..., FakeClient]) -> None:
    overloaded = anthropic.OverloadedError("overloaded", response=httpx2.Response(529, request=REQUEST), body=None)
    fake_llm(overloaded)
    record = triage_thread(threads[0])
    _assert_fallback(record.result)
    assert "OverloadedError" in (record.error or "")


def test_configuration_error_stops_the_run(threads: list[Thread], fake_llm: Callable[..., FakeClient]) -> None:
    rejected = anthropic.AuthenticationError("bad key", response=httpx2.Response(401, request=REQUEST), body=None)
    fake_llm(rejected)
    with pytest.raises(anthropic.AuthenticationError):
        triage_thread(threads[0])


def test_prompts_never_contain_label_leaks(threads: list[Thread], fake_llm: Callable[..., FakeClient]) -> None:
    client = fake_llm(*[json.dumps(VALID_TRIAGE)] * len(threads))
    for thread in threads:
        triage_thread(thread)
    for thread, request in zip(threads, client.requests):
        sent = request["system"] + request["messages"][0]["content"]
        assert "thr_" not in sent
        assert not any(m.message_id in sent for m in thread.messages)


def test_claim_ref_and_deadline_are_normalised() -> None:
    result = TriageResult(**VALID_TRIAGE | {"claim_ref": "HOM-PL-771932", "deadline_mentioned": "2026-02-20T17:00:00Z"})
    assert result.claim_ref is None  # a policy number is not a claim reference
    assert result.deadline_mentioned == date(2026, 2, 20)
    assert TriageResult(**VALID_TRIAGE | {"signals": ["fnol", "fnol"]}).signals == ["fnol"]


def test_parse_json_object_edge_cases() -> None:
    assert llm.parse_json_object('Here you go: {"a": 1} Thanks!') == {"a": 1}
    assert llm.parse_json_object("[1, 2]") is None
    assert llm.parse_json_object("no braces") is None
    assert llm.parse_json_object("{not: valid}") is None


def test_cost_estimate_uses_model_prices() -> None:
    assert llm.cost_usd("claude-haiku-4-5", 1_000_000, 0) == pytest.approx(1.00)
    assert llm.cost_usd("claude-haiku-4-5-20251001", 0, 1_000_000) == pytest.approx(5.00)
    assert llm.cost_usd("unknown-model", 1000, 1000) == 0.0
