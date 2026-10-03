"""Shared test helpers: a fake Anthropic client, so no test ever calls the API."""

import inspect
from types import SimpleNamespace
from typing import Any, Callable

import anthropic
import pytest

from app import llm

# The real SDK signature: the fake rejects any argument the real client would reject.
CREATE_SIGNATURE = inspect.signature(anthropic.resources.messages.Messages.create)

VALID_TRIAGE: dict[str, Any] = {
    "category": "action_required",
    "action_type": "respond",
    "action_summary": "Confirm cover and excess to the broker for PIN-HOM-533661.",
    "claim_ref": "PIN-HOM-533661",
    "line_of_business": "home",
    "sender_type": "broker",
    "urgency": "medium",
    "importance": "medium",
    "deadline_mentioned": None,
    "signals": ["repeat_chase"],
    "confidence": 0.9,
    "reasoning": "The broker has asked twice for cover confirmation and nobody has replied.",
}


def fake_response(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    """Build an object shaped like an SDK Message with one text block and usage figures."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
        model="claude-haiku-4-5",
        _request_id="req_test",
    )


class FakeClient:
    """Stands in for anthropic.Anthropic: replays queued replies and records every request."""

    def __init__(self, replies: list[Any]) -> None:
        """replies, in order: reply texts, prebuilt responses, or exceptions to raise."""
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []
        self.messages = self  # so code under test can call client.messages.create(...)

    def create(self, **request: Any) -> SimpleNamespace:
        """Check the arguments against the real SDK, record the request, return (or raise) the next reply."""
        CREATE_SIGNATURE.bind(None, **request)  # TypeError for an argument the SDK does not accept
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return fake_response(reply) if isinstance(reply, str) else reply


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> Callable[..., FakeClient]:
    """Return a function that installs a FakeClient, with the given replies, as the SDK client."""

    def install(*replies: Any) -> FakeClient:
        """Make llm.get_client return a FakeClient that replays `replies`; return it for inspection."""
        client = FakeClient(list(replies))
        monkeypatch.setattr(llm, "get_client", lambda: client)
        return client

    return install
