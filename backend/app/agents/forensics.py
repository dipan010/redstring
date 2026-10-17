"""Forensics agent: deterministic document checks plus Gemini multimodal review
(photo vs. narrative, signs of editing, invoice plausibility)."""

from ..llm import doc_part, generate_json
from ..rules import document_rules
from ..schemas import Flag, ForensicsOutput, ReaderOutput

SYSTEM = """You are the Forensics agent in a motor-insurance Special Investigation Unit in India.
Look for evidence that a claim is inconsistent or manipulated. Check:
1. Do the damage photos match the described incident and the damage areas claimed?
   (e.g. rear-end collision but photos show front damage; different vehicle colour/model)
2. Signs of old or pre-existing damage (rust, dirt in dents, faded paint at breaks).
3. Documents showing signs of editing: inconsistent fonts, misaligned numbers, overwritten dates.
4. Invoice plausibility: parts unrelated to the described damage, or prices far above
   typical Indian market rates for that vehicle.
5. Narrative inconsistencies between documents.
Dates on Indian documents are DD/MM/YYYY. "Left" and "right" mean the vehicle's own sides
(driver's perspective). In a photo taken from in front of the car, the car's left side appears on the
viewer's right. Only flag a side mismatch when the photo angle makes the side unambiguous.
Report only findings supported by specific evidence. Return an empty list if the claim looks clean.
Do not repeat simple arithmetic or date checks; those are handled separately."""


async def run(documents: list[dict], r: ReaderOutput) -> tuple[ForensicsOutput, list[Flag]]:
    flags = document_rules(r)
    contents: list = []
    for i, d in enumerate(documents):
        contents.append(f"Document {i}: {d['name']}")
        contents.append(doc_part(d["path"], d["mime_type"]))
    contents.append("EXTRACTED CLAIM FIELDS:\n" + r.model_dump_json(indent=2))
    if flags:
        contents.append("ALREADY FLAGGED BY RULES (do not repeat these):\n" + "\n".join(f"- {f.title}" for f in flags))
    contents.append("Review this claim for inconsistencies.")
    out = await generate_json(contents, ForensicsOutput, SYSTEM)
    downgrade = {"high": "medium", "medium": "low", "low": "low"}
    for i, f in enumerate(out.findings):
        severity = f.severity if f.confidence == "high" else downgrade[f.severity]
        flags.append(Flag(id=f"AI_FORENSIC_{i}", agent="forensics", code="AI_FORENSIC", severity=severity,
                          title=f.title, evidence=f.evidence,
                          source=f"doc:{f.doc_index}" if f.doc_index is not None else None))
    return out, flags
