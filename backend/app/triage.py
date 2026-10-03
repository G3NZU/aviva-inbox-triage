"""Triage one thread with Claude Haiku: build the prompt, call the model, validate the reply.

Why: the LLM's job is judgement (D-01) — what the thread is and what it asks
for. This module turns a Thread into a validated TriageResult, or into a safe
fallback that sends the thread to human review when the model's output is
unusable. Either way it returns the audit facts to store with the result.
"""

import logging

import anthropic

from app import config, llm
from app.ingest import thread_for_model
from app.models import Thread, TriageRecord, TriageResult

log = logging.getLogger(__name__)


def load_prompt(version: str) -> str:
    """Return the text of a versioned prompt file: app/prompts/<version>.md."""
    return (config.PROMPTS_DIR / f"{version}.md").read_text(encoding="utf-8")


def build_user_message(thread: Thread) -> str:
    """Wrap the model view of a thread in <thread> tags; the prompt treats tagged text as data."""
    return f"<thread>\n{thread_for_model(thread)}\n</thread>\n\nReturn the JSON object for this thread."


def triage_thread(thread: Thread, prompt_version: str | None = None) -> TriageRecord:
    """Classify one thread with the triage model.

    Input: a Thread, and the prompt version to use (None = config's current one).
    Output: a TriageRecord. A reply that stays unusable after the one retry
    (refusal, no JSON, wrong schema) or a transient API failure does not raise:
    it yields the fallback result (confidence 0, signal parse_error), which the
    priority rules send to human review. Configuration errors (missing or
    rejected key, bad model) do raise.
    """
    prompt_version = prompt_version or config.TRIAGE_PROMPT_VERSION
    system, user = load_prompt(prompt_version), build_user_message(thread)
    try:
        reply = llm.call_json(config.TRIAGE_MODEL, system, user, max_tokens=config.TRIAGE_MAX_TOKENS,
                              schema=TriageResult, **config.TRIAGE_OPTIONS)
    except llm.LLMError as exc:
        return fallback(prompt_version, str(exc), exc.raw_text, exc.input_tokens, exc.output_tokens)
    except anthropic.APIError as exc:
        if not _is_transient(exc):
            raise
        return fallback(prompt_version, f"API unavailable ({type(exc).__name__})")
    result = TriageResult.model_validate(reply.data)  # cannot fail: call_json checked the schema
    return TriageRecord(result=result, raw_response=reply.raw_text, model=reply.model,
                        prompt_version=prompt_version, request_id=reply.request_id,
                        input_tokens=reply.input_tokens, output_tokens=reply.output_tokens)


def fallback(prompt_version: str, reason: str, raw_response: str = "",
             input_tokens: int = 0, output_tokens: int = 0) -> TriageRecord:
    """Build the safe record used when the model's output is unusable.

    Why: never guess. Confidence 0 sends the thread to the human-review bucket
    (D-05); the reason and any raw reply are kept for the audit trail.
    """
    log.warning("triage fallback: %s", reason)
    result = TriageResult(
        category="informational", action_type="none", action_summary="", claim_ref=None,
        line_of_business="unknown", sender_type="unknown", urgency="low", importance="low",
        deadline_mentioned=None, signals=["parse_error"], confidence=0.0,
        reasoning=f"Automatic triage failed: {reason}. A human must review this thread.",
    )
    return TriageRecord(result=result, raw_response=raw_response, model=config.TRIAGE_MODEL,
                        prompt_version=prompt_version, input_tokens=input_tokens,
                        output_tokens=output_tokens, error=reason)


def _is_transient(exc: anthropic.APIError) -> bool:
    """True for failures worth retrying on the next run (network, 429, 5xx); False for setup errors (4xx)."""
    if isinstance(exc, anthropic.APIConnectionError):
        return True
    status = getattr(exc, "status_code", 0)
    return status == 429 or status >= 500
