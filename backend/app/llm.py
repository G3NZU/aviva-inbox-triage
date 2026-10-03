"""Thin wrapper around the Anthropic SDK: send a prompt, get back a checked JSON object.

Why: every LLM call in the app goes through `call_json`, so JSON parsing,
schema checks, the one retry, refusal handling and token accounting live in
one place, and tests replace one seam (`get_client`) instead of the network.
Transport failures (429, 5xx, timeouts, dropped connections) are retried by
the SDK itself (`max_retries`); this module adds one retry for a bad reply.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

from app import config

log = logging.getLogger(__name__)


@dataclass
class LLMResult:
    """A successful call: the parsed object plus the facts the audit trail records."""

    data: dict[str, Any]  # already checked against the schema, when one was given
    raw_text: str
    model: str  # the model that actually answered (from the response)
    request_id: str | None
    input_tokens: int  # summed over both attempts
    output_tokens: int
    attempts: int


class LLMError(Exception):
    """The model refused, or its reply was still unusable after the retry."""

    def __init__(self, reason: str, raw_text: str, input_tokens: int, output_tokens: int) -> None:
        """Keep the raw reply and the tokens spent, so a failure is still audited and costed."""
        super().__init__(reason)
        self.raw_text = raw_text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class MissingAPIKeyError(RuntimeError):
    """ANTHROPIC_API_KEY is not set, so no real call can be made."""


_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    """Return the SDK client, creating it on first use (importing this module needs no key).

    Raises MissingAPIKeyError with setup instructions when the key is absent.
    """
    global _client
    if _client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise MissingAPIKeyError("ANTHROPIC_API_KEY is not set: copy .env.example to .env and add your key.")
        _client = anthropic.Anthropic(timeout=60.0, max_retries=3)
    return _client


def call_json(model: str, system: str, user: str, *, max_tokens: int,
              schema: type[BaseModel] | None = None, **options: Any) -> LLMResult:
    """Send one system + user prompt and return the reply as a checked JSON object.

    Inputs: model ID, system prompt, user message, max_tokens; optionally a
    Pydantic `schema` the object must satisfy; model-specific request options
    (e.g. extra_body for Haiku's temperature, output_config for Sonnet).
    A reply that is not one JSON object, or fails the schema, is retried once
    with a note quoting the problem (D-21).
    Output: LLMResult (parsed object, raw text, model, request ID, tokens).
    Raises: LLMError on a refusal or a second unusable reply; SDK errors for
    API failures the SDK's own retries could not clear.
    """
    tokens_in = tokens_out = 0
    content, text, problem = user, "", ""
    for attempt in (1, 2):
        response = get_client().messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": content}], **options,
        )
        tokens_in += response.usage.input_tokens
        tokens_out += response.usage.output_tokens
        text = "".join(block.text for block in response.content if block.type == "text")
        log.debug("llm %s attempt=%d stop=%s", model, attempt, response.stop_reason)
        if response.stop_reason == "refusal":
            raise LLMError("the model declined to answer (refusal)", text, tokens_in, tokens_out)
        data, problem = check_reply(text, schema)
        if data is not None:
            request_id = getattr(response, "_request_id", None)
            return LLMResult(data, text, response.model, request_id, tokens_in, tokens_out, attempt)
        content = f"{user}\n\nYour previous reply was rejected: {problem}. Reply with only the corrected JSON object."
    raise LLMError(f"the reply was rejected twice: {problem}", text, tokens_in, tokens_out)


def check_reply(text: str, schema: type[BaseModel] | None) -> tuple[dict[str, Any] | None, str]:
    """Parse a reply and check it against the schema.

    Output: (data, "") when usable, else (None, a short description of the problem).
    """
    data = parse_json_object(text)
    if data is None:
        return None, "it was not a single JSON object"
    if schema is not None:
        try:
            schema.model_validate(data)
        except ValidationError as exc:
            return None, describe_errors(exc)
    return data, ""


def parse_json_object(text: str) -> dict[str, Any] | None:
    """Return the JSON object inside a model reply, or None if there is none.

    Tolerates a ```json fence or a stray sentence around the object; anything
    that is not a JSON object (a list, a number, broken JSON) gives None.
    """
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def describe_errors(exc: ValidationError, limit: int = 3) -> str:
    """Summarise schema errors in one line the model can act on.

    e.g. "signals.0: 'review_document' is not allowed (allowed: 'fnol', 'injury', ...)".
    """
    parts = []
    for error in exc.errors()[:limit]:
        where = ".".join(str(part) for part in error["loc"])
        if error["type"] == "missing":
            parts.append(f"{where}: missing")
            continue
        allowed = error.get("ctx", {}).get("expected")
        hint = f" (allowed: {allowed})" if allowed else ""
        parts.append(f"{where}: {error['input']!r} is not allowed{hint}")
    return "; ".join(parts)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate the cost of a call from config.PRICE_PER_MTOK (0.0 for an unknown model).

    Matches by prefix, because the API may report a dated model ID (e.g. "claude-haiku-4-5-2025…").
    """
    prices = (p for name, p in config.PRICE_PER_MTOK.items() if model.startswith(name))
    price_in, price_out = next(prices, (0.0, 0.0))
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000
