"""Chat model factory and structured-output helpers (Groq)."""

from __future__ import annotations

import json
import time
from typing import TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from .config import Settings

T = TypeVar("T", bound=BaseModel)

# Simple process-wide throttle for Groq free-tier limits
# (default ~30 RPM → ~2s between calls; 8K TPM → smaller batches in config)
_last_llm_call_at: float = 0.0


def create_chat_model(settings: Settings) -> BaseChatModel | None:
    """Return a ChatGroq model when GROQ_API_KEY is set; else None."""
    if not settings.env.groq_api_key:
        return None
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=settings.env.pulse_model,
        api_key=settings.env.groq_api_key,
        temperature=0,
        max_retries=2,
    )


def _throttle(min_interval_seconds: float) -> None:
    """Sleep so successive LLM calls respect requests-per-minute limits."""
    global _last_llm_call_at
    if min_interval_seconds <= 0:
        return
    now = time.monotonic()
    wait = min_interval_seconds - (now - _last_llm_call_at)
    if wait > 0:
        time.sleep(wait)
    _last_llm_call_at = time.monotonic()


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines)
    return text.strip()


def invoke_structured(
    llm: BaseChatModel,
    schema: type[T],
    messages: list[BaseMessage],
    *,
    min_interval_seconds: float = 0.0,
) -> T:
    """Prefer LangChain ``with_structured_output``; fall back to JSON parse.

    Groq ``openai/gpt-oss-120b`` can be finicky with structured output, so the
    JSON fallback keeps the pipeline reliable. Stubbed FakeLLM tests also rely
    on the fallback path. Pass ``min_interval_seconds`` (e.g. 2.5) in live runs
    to respect Groq RPM limits.
    """
    # Unit-test FakeLLM should not sleep
    if getattr(llm, "_llm_type", None) == "fake":
        min_interval_seconds = 0.0

    _throttle(min_interval_seconds)

    try:
        # Prefer json_mode / json_schema when available; ignore failures
        structured = llm.with_structured_output(schema)
        result = structured.invoke(messages)
        if isinstance(result, schema):
            return result
        if isinstance(result, dict):
            return schema.model_validate(result)
    except Exception:
        pass

    _throttle(min_interval_seconds)
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else response
    text = content if isinstance(content, str) else str(content)
    data = json.loads(_strip_fences(text))
    # Allow bare list when schema has a single list field named "assignments"
    if isinstance(data, list) and "assignments" in schema.model_fields:
        data = {"assignments": data}
    return schema.model_validate(data)
