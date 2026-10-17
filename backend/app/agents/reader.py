"""Reader agent: reads every document in the claim pack (PDFs and photos) and
extracts structured fields with Gemini's multimodal understanding."""

from ..llm import doc_part, generate_json
from ..schemas import ReaderOutput

SYSTEM = """You are the Reader agent in an insurance claims team at an Indian motor insurer.
You receive a claim pack: claim forms, repair invoices, police reports, licences, and damage photos.
Extract the requested fields exactly as they appear. Do not guess; use null when a value is absent.
Dates must be YYYY-MM-DD. Amounts are INR numbers without symbols or commas.
For each damage photo, describe only what is visibly damaged, plus anything unusual
(watermarks, stock-photo look, different vehicle or colour, rust or old damage)."""


async def run(documents: list[dict], note: str | None = None) -> ReaderOutput:
    contents: list = []
    for i, d in enumerate(documents):
        contents.append(f"Document {i}: {d['name']}")
        contents.append(doc_part(d["path"], d["mime_type"]))
    if note:
        contents.append(f"Adjuster note: {note}")
    contents.append("Extract the claim fields from the documents above.")
    return await generate_json(contents, ReaderOutput, SYSTEM)
