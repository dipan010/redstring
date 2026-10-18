"""Shared engine for non-motor lines of business (health, property).

The motor pipeline stays exactly as it was; app.pipeline hands any claim whose lineOfBusiness is not
"motor" to run_line(). Each line supplies its own schemas, prompts, wording and rules through a
LineSpec, and reuses the same Gemini wrapper, verdict scoring and photo hashing.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel

from ..agents import verdict
from ..agents.linker import photo_entities
from ..agents.policy import find_policy, wording
from ..clients import db
from ..llm import doc_part, generate_json, start_usage, summarize_usage
from ..rules import flag, names_match
from ..schemas import Flag, ForensicsOutput, PolicyOutput

log = logging.getLogger(__name__)

KIND_LABELS = {"phone": "Phone", "email": "Email", "bank": "Bank account", "photo": "Photo",
               "hospital": "Hospital", "doctor": "Doctor", "bill": "Bill no.",
               "contractor": "Contractor", "address": "Address", "invoice": "Invoice no."}


@dataclass
class LineSpec:
    key: str                                   # "health" | "property"
    reader_schema: type[BaseModel]
    reader_system: str
    policy_system: str
    forensics_system: str
    policy_rules: Callable                     # (reader_output, policy_record | None) -> list[Flag]
    doc_rules: Callable                        # (reader_output) -> list[Flag]
    entities: Callable                         # (reader_output) -> list[dict]
    summary: Callable                          # (reader_output) -> dict of top-level claim fields
    provider_kinds: tuple[str, ...]            # shared by many honest customers (hospital, contractor...)
    bill_kind: str                             # "bill" or "invoice": duplicate-document key
    personal_kinds: tuple[str, ...] = ("bank", "phone", "email")
    provider_label: dict = field(default_factory=dict)


async def read(spec: LineSpec, documents: list[dict], note: str | None):
    contents: list = []
    for i, d in enumerate(documents):
        contents.append(f"Document {i}: {d['name']}")
        contents.append(doc_part(d["path"], d["mime_type"]))
    if note:
        contents.append(f"Adjuster note: {note}")
    contents.append("Extract the claim fields from the documents above.")
    return await generate_json(contents, spec.reader_schema, spec.reader_system)


async def check_policy(spec: LineSpec, r) -> tuple[PolicyOutput | None, list[Flag], dict | None]:
    policy = await find_policy(getattr(r, "policy_number", None))
    flags = spec.policy_rules(r, policy)
    if policy is None:
        return None, flags, None
    out = await generate_json(
        ["POLICY WORDING:\n" + wording(policy.get("product", "")),
         "POLICY SCHEDULE:\n" + json.dumps(policy, default=str, indent=2),
         "CLAIM (extracted):\n" + r.model_dump_json(indent=2),
         "Assess coverage for this claim."],
        PolicyOutput, spec.policy_system)
    for c in out.exclusions_triggered:
        flags.append(Flag(id=f"EXCLUSION_{c.clause_id}", agent="policy", code="EXCLUSION", severity="high",
                          title=f"Exclusion {c.clause_id}: {c.title}", evidence=f"“{c.quote}” {c.reason}",
                          source=f"clause:{c.clause_id}"))
    if out.missing_documents:
        flags.append(Flag(id="MISSING_DOCS", agent="policy", code="MISSING_DOCS", severity="low",
                          title="Required documents missing", evidence=", ".join(out.missing_documents)))
    return out, flags, policy


async def forensics(spec: LineSpec, documents: list[dict], r) -> list[Flag]:
    flags = spec.doc_rules(r)
    contents: list = []
    for i, d in enumerate(documents):
        contents.append(f"Document {i}: {d['name']}")
        contents.append(doc_part(d["path"], d["mime_type"]))
    contents.append("EXTRACTED CLAIM FIELDS:\n" + r.model_dump_json(indent=2))
    if flags:
        contents.append("ALREADY FLAGGED BY RULES (do not repeat these):\n" + "\n".join(f"- {f.title}" for f in flags))
    contents.append("Review this claim for inconsistencies.")
    out = await generate_json(contents, ForensicsOutput, spec.forensics_system)
    downgrade = {"high": "medium", "medium": "low", "low": "low"}
    for i, f in enumerate(out.findings):
        sev = f.severity if f.confidence == "high" else downgrade[f.severity]
        flags.append(Flag(id=f"AI_FORENSIC_{i}", agent="forensics", code="AI_FORENSIC", severity=sev,
                          title=f.title, evidence=f.evidence,
                          source=f"doc:{f.doc_index}" if f.doc_index is not None else None))
    return flags


async def link(spec: LineSpec, claim_id: str, claim: dict, r, documents: list[dict]):
    ents = spec.entities(r) + await photo_entities(documents)
    keys = [e["key"] for e in ents][:30]
    if not keys:
        return ents, [], []
    staged = bool(claim.get("staged"))
    others: dict[str, dict] = {}
    q = db().collection("claims").where(filter=FieldFilter("linkKeys", "array_contains_any", keys)).limit(200)
    async for snap in q.stream():
        d = snap.to_dict()
        if snap.id == claim_id or d.get("isBenchmark"):
            continue
        if d.get("staged") and not staged:
            continue  # never link live claims to unreleased data
        if claim.get("samplePack") and d.get("samplePack") == claim.get("samplePack"):
            continue
        others[snap.id] = d

    links = []
    for cid, d in others.items():
        shared = sorted(set(keys) & set(d.get("linkKeys", [])))
        links.append({"claimId": cid, "claimNumber": d.get("claimNumber"), "claimantName": d.get("claimantName"),
                      "riskScore": (d.get("risk") or {}).get("score"), "fraudConfirmed": bool(d.get("fraudConfirmed")),
                      "shared": [{"key": k, "kind": k.split(":", 1)[0]} for k in shared]})

    by_kind: dict[str, list[dict]] = defaultdict(list)
    for l in links:
        for s in l["shared"]:
            by_kind[s["kind"]].append(l)

    def refs(ls):
        return ", ".join(sorted({l["claimNumber"] or l["claimId"] for l in ls})[:6])

    name = getattr(r, "claimant_name", None)
    flags: list[Flag] = []
    for kind in spec.personal_kinds:
        foreign = [l for l in by_kind.get(kind, []) if not names_match(l["claimantName"], name)]
        if foreign:
            flags.append(flag("linker", f"SHARED_{kind.upper()}", "high" if kind == "bank" else "medium",
                              f"{KIND_LABELS[kind]} shared with {len(foreign)} other claimant(s)",
                              f"Same {KIND_LABELS[kind].lower()} appears on claims {refs(foreign)} filed by different people.",
                              f"claims:{refs(foreign)}"))
    if by_kind.get(spec.bill_kind):
        flags.append(flag("linker", "DUPLICATE_BILL", "high", f"{KIND_LABELS[spec.bill_kind]} already used in another claim",
                          f"The same {KIND_LABELS[spec.bill_kind].lower()} appears on {refs(by_kind[spec.bill_kind])}.",
                          f"claims:{refs(by_kind[spec.bill_kind])}"))
    if by_kind.get("photo"):
        flags.append(flag("linker", "PHOTO_REUSED", "high", "Damage photo already used in another claim",
                          f"An identical photo was submitted with {refs(by_kind['photo'])}.", f"claims:{refs(by_kind['photo'])}"))
    for kind in spec.provider_kinds:
        fraud = [l for l in by_kind.get(kind, []) if l["fraudConfirmed"]]
        if fraud:
            label = KIND_LABELS[kind]
            flags.append(flag("linker", f"{kind.upper()}_FRAUD_HISTORY", "high",
                              f"{label} linked to {len(fraud)} confirmed fraud case(s)",
                              f"Confirmed fraud involving this {label.lower()}: {refs(fraud)}.", f"claims:{refs(fraud)}"))
    ring = [l for l in links if set(spec.provider_kinds) & {s["kind"] for s in l["shared"]}
            and set(spec.personal_kinds) & {s["kind"] for s in l["shared"]}]
    if len(ring) >= 2:
        flags.append(flag("linker", "POSSIBLE_RING", "high", f"Possible fraud ring ({len(ring) + 1} claims)",
                          f"This claim shares a provider and personal identifiers with {refs(ring)}.", f"claims:{refs(ring)}"))
    return ents, links, flags


async def _stage(ref, name: str, status: str, **extra) -> None:
    await ref.update({f"stages.{name}": {"status": status, "at": firestore.SERVER_TIMESTAMP, **extra}})


async def run_line(spec: LineSpec, claim_id: str) -> bool:
    from ..pipeline import initial_stages

    ref = db().collection("claims").document(claim_id)
    claim = (await ref.get()).to_dict()
    docs = claim["documents"]
    t0 = time.monotonic()
    usage = start_usage()

    async def timed(name: str, coro):
        await _stage(ref, name, "running")
        s = time.monotonic()
        try:
            res = await coro
        except Exception as e:
            log.exception("stage %s failed for %s", name, claim_id)
            await _stage(ref, name, "error", error=str(e)[:300])
            raise
        await _stage(ref, name, "done", ms=int((time.monotonic() - s) * 1000))
        return res

    try:
        await ref.update({"status": "processing", "stages": initial_stages(), "error": None})
        r = await timed("reader", read(spec, docs, claim.get("note")))
        await ref.update({"extracted": r.model_dump(), **spec.summary(r)})
        (pol_out, pol_flags, schedule), for_flags, (ents, links, link_flags) = await asyncio.gather(
            timed("policy", check_policy(spec, r)),
            timed("forensics", forensics(spec, docs, r)),
            timed("linker", link(spec, claim_id, claim, r, docs)),
        )
        flags = pol_flags + for_flags + link_flags
        risk, v = await timed("verdict", verdict.run(r, pol_out, flags))
        await ref.update({
            "status": "ready",
            "policy": {"assessment": pol_out.model_dump() if pol_out else None, "schedule": schedule},
            "flags": [f.model_dump() for f in flags], "entities": ents, "linkKeys": [e["key"] for e in ents],
            "links": links, "risk": risk, "verdict": v.model_dump(),
            "processingMs": int((time.monotonic() - t0) * 1000), "usage": summarize_usage(usage),
            "processedAt": firestore.SERVER_TIMESTAMP,
        })
        return True
    except Exception as e:
        await ref.update({"status": "error", "error": str(e)[:500]})
        return False
