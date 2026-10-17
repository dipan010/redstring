"""Thin wrapper around Gemini on Vertex AI: structured JSON output with retries."""

import asyncio
import logging
from contextvars import ContextVar
from typing import TypeVar

from google.genai import errors, types
from pydantic import BaseModel

from .clients import gemini
from .config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

# Token usage of every Gemini call in the current pipeline run (shared with gathered child tasks).
_usage: ContextVar[list | None] = ContextVar("gemini_usage", default=None)


def start_usage() -> list:
    calls: list = []
    _usage.set(calls)
    return calls


def _record(model: str, resp) -> None:
    calls, u = _usage.get(), getattr(resp, "usage_metadata", None)
    if calls is not None and u is not None:
        calls.append({"model": model, "in": u.prompt_token_count or 0, "out": u.candidates_token_count or 0,
                      "think": u.thoughts_token_count or 0})


def summarize_usage(calls: list) -> dict:
    out = {"calls": len(calls), "inputTokens": 0, "outputTokens": 0, "thinkingTokens": 0, "byModel": {}}
    for c in calls:
        out["inputTokens"] += c["in"]
        out["outputTokens"] += c["out"]
        out["thinkingTokens"] += c["think"]
        m = out["byModel"].setdefault(c["model"], {"calls": 0, "in": 0, "out": 0, "think": 0})
        m["calls"] += 1
        m["in"] += c["in"]
        m["out"] += c["out"]
        m["think"] += c["think"]
    return out


def no_em_dash(text: str) -> str:
    """House style: no em dashes in anything we show (Gemini likes them)."""
    return text.replace(" \u2014 ", ", ").replace("\u2014", "-")


def doc_part(path: str, mime_type: str) -> types.Part:
    """A Storage object passed to Gemini by URI (no re-upload of bytes)."""
    return types.Part.from_uri(file_uri=f"gs://{get_settings().storage_bucket}/{path}", mime_type=mime_type)


def thinking(level: str, model: str) -> types.ThinkingConfig:
    """Gemini 3.x takes a thinking level; 2.x takes a token budget."""
    if model.startswith("gemini-2"):
        return types.ThinkingConfig(thinking_budget={"minimal": 0, "low": 1024}.get(level, -1))
    return types.ThinkingConfig(thinking_level=level)


async def generate_json(
    contents: list,
    schema: type[T],
    system: str,
    temperature: float = 0.0,
    attempts: int = 3,
    think: str = "minimal",
) -> T:
    s = get_settings()
    last: Exception | None = None
    # primary model first; on timeout / rate limit / bad output, fall back to the faster model
    models = [s.gemini_model] + [s.gemini_fallback_model] * (attempts - 1)
    for i, model in enumerate(models):
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
            thinking_config=thinking(think, model),
        )
        try:
            resp = await asyncio.wait_for(
                gemini().aio.models.generate_content(model=model, contents=contents, config=config),
                timeout=s.gemini_timeout_s,
            )
            _record(model, resp)
            return schema.model_validate_json(no_em_dash(resp.text or ""))
        except (errors.APIError, ValueError, asyncio.TimeoutError) as e:
            last = e
            log.warning("gemini %s attempt %d/%d failed: %r", model, i + 1, attempts, e)
            await asyncio.sleep(2 * (i + 1))
    raise RuntimeError(f"Gemini call failed after {attempts} attempts: {last!r}")


async def generate_text(contents: list, system: str, temperature: float = 0.3, think: str = "minimal") -> str:
    s = get_settings()
    for model in (s.gemini_model, s.gemini_fallback_model):
        config = types.GenerateContentConfig(system_instruction=system, temperature=temperature,
                                             thinking_config=thinking(think, model))
        try:
            resp = await asyncio.wait_for(
                gemini().aio.models.generate_content(model=model, contents=contents, config=config),
                timeout=s.gemini_timeout_s,
            )
            _record(model, resp)
            return no_em_dash(resp.text or "")
        except (errors.APIError, asyncio.TimeoutError) as e:
            log.warning("gemini %s text call failed: %r", model, e)
    raise RuntimeError("Gemini text call failed")
