"""Thin wrapper around Gemini on Vertex AI: structured JSON output with retries."""

import asyncio
import logging
from typing import TypeVar

from google.genai import errors, types
from pydantic import BaseModel

from .clients import gemini
from .config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


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
            if resp.parsed is not None:
                return resp.parsed  # type: ignore[return-value]
            return schema.model_validate_json(resp.text or "")
        except (errors.APIError, ValueError, asyncio.TimeoutError) as e:
            last = e
            log.warning("gemini %s attempt %d/%d failed: %r", model, i + 1, attempts, e)
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
            return resp.text or ""
        except (errors.APIError, asyncio.TimeoutError) as e:
            log.warning("gemini %s text call failed: %r", model, e)
    raise RuntimeError("Gemini text call failed")
