"""Non-motor lines of business. Motor claims never come through here."""

from .common import run_line
from .health import SPEC as HEALTH
from .property import SPEC as PROPERTY

LINES = {"health": HEALTH, "property": PROPERTY}


async def run(line: str, claim_id: str) -> bool:
    return await run_line(LINES[line], claim_id)
