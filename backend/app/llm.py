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


async def generate_json(
    contents: list,
    schema: type[T],
    system: str,
    temperature: float = 0.0,
    attempts: int = 3,
) -> T:
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=temperature,
    )
    last: Exception | None = None
    for i in range(attempts):
        try:
            resp = await gemini().aio.models.generate_content(
                model=get_settings().gemini_model, contents=contents, config=config
            )
            if resp.parsed is not None:
                return resp.parsed  # type: ignore[return-value]
            return schema.model_validate_json(resp.text or "")
        except (errors.APIError, ValueError) as e:
            last = e
            log.warning("gemini attempt %d/%d failed: %s", i + 1, attempts, e)
            await asyncio.sleep(1.5 * (i + 1))
    raise RuntimeError(f"Gemini call failed after {attempts} attempts: {last}")


async def generate_text(contents: list, system: str, temperature: float = 0.3) -> str:
    config = types.GenerateContentConfig(system_instruction=system, temperature=temperature)
    resp = await gemini().aio.models.generate_content(
        model=get_settings().gemini_model, contents=contents, config=config
    )
    return resp.text or ""
