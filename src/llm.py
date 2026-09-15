"""Chat model factory and structured-output helpers (Groq)."""

from __future__ import annotations

import json
import re
import time
from typing import TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from .config import Settings

T = TypeVar("T", bound=BaseModel)

# Process-wide throttle for Groq free-tier RPM (30 req/min)
_last_llm_call_at: float = 0.0

_RATE_LIMIT_RE = re.compile(
    r"try again in (?P<secs>\d+(?:\.\d+)?)\s*s",
    re.IGNORECASE,
)


def create_chat_model(settings: Settings) -> BaseChatModel | None:
    """Return a ChatGroq model when GROQ_API_KEY is set; else None."""
    if not settings.env.groq_api_key:
        return None
    from langchain_groq import ChatGroq

    # Disable SDK auto-retries — we pace calls ourselves (RPM/TPM) and
    # back off explicitly on 429 so rapid retries do not burn the 8K TPM budget.
    return ChatGroq(
        model=settings.env.pulse_model,
        api_key=settings.env.groq_api_key,
        temperature=0,
        max_retries=0,
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


def _is_rate_limit_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    if "rate_limit" in text or "rate limit" in text or "429" in text:
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return status == 429


def _retry_after_seconds(exc: BaseException, attempt: int) -> float:
    """Parse Groq's 'try again in Xs' or fall back to exponential backoff."""
    match = _RATE_LIMIT_RE.search(str(exc))
    if match:
        return float(match.group("secs")) + 0.5
    # 8K TPM window: grow wait, cap at 60s
    return min(60.0, (2**attempt) + 1.0)


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
    rate_limit_retries: int = 6,
) -> T:
    """Prefer LangChain ``with_structured_output``; fall back to JSON parse.

    Groq structured output can be finicky on some models, so the
    JSON fallback keeps the pipeline reliable. Stubbed FakeLLM tests also rely
    on the fallback path. Pass ``min_interval_seconds`` (e.g. 4) in live runs
    to respect Groq RPM/TPM limits; 429s are retried with backoff.
    """
    # Unit-test FakeLLM should not sleep
    if getattr(llm, "_llm_type", None) == "fake":
        min_interval_seconds = 0.0
        rate_limit_retries = 0

    last_exc: BaseException | None = None
    attempts = max(1, rate_limit_retries + 1)

    for attempt in range(attempts):
        _throttle(min_interval_seconds)
        try:
            try:
                structured = llm.with_structured_output(schema)
                result = structured.invoke(messages)
                if isinstance(result, schema):
                    return result
                if isinstance(result, dict):
                    return schema.model_validate(result)
            except Exception as exc:
                if _is_rate_limit_error(exc):
                    raise
                # Structured-output path failed for a non-rate reason — try JSON

            _throttle(min_interval_seconds)
            response = llm.invoke(messages)
            content = response.content if hasattr(response, "content") else response
            text = content if isinstance(content, str) else str(content)
            data = json.loads(_strip_fences(text))
            if isinstance(data, list) and "assignments" in schema.model_fields:
                data = {"assignments": data}
            return schema.model_validate(data)
        except Exception as exc:
            last_exc = exc
            if not _is_rate_limit_error(exc) or attempt >= attempts - 1:
                raise
            time.sleep(_retry_after_seconds(exc, attempt))

    assert last_exc is not None
    raise last_exc
