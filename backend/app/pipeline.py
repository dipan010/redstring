"""Runs the five agents and streams each stage's status into Firestore, so the
UI can show live progress via onSnapshot."""

import asyncio
import logging
import time

from google.cloud import firestore

from .agents import forensics, linker, policy, reader, verdict
from .clients import db
from .schemas import Flag

log = logging.getLogger(__name__)
STAGES = ["reader", "policy", "forensics", "linker", "verdict"]


def initial_stages() -> dict:
    return {s: {"status": "pending"} for s in STAGES}


async def _stage(ref, name: str, status: str, **extra) -> None:
    await ref.update({f"stages.{name}": {"status": status, "at": firestore.SERVER_TIMESTAMP, **extra}})


async def run_pipeline(claim_id: str) -> None:
    ref = db().collection("claims").document(claim_id)
    snap = await ref.get()
    claim = snap.to_dict()
    docs = claim["documents"]
    t0 = time.monotonic()

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
        r = await timed("reader", reader.run(docs, claim.get("note")))
        await ref.update({
            "extracted": r.model_dump(),
            "claimantName": r.claimant_name,
            "vehicleRegistration": r.vehicle_registration,
            "claimAmount": r.claim_amount,
            "incidentDate": r.incident_date,
        })

        (pol_out, pol_flags, schedule), (_, for_flags), (ents, links, link_flags) = await asyncio.gather(
            timed("policy", policy.run(r)),
            timed("forensics", forensics.run(docs, r)),
            timed("linker", linker.run(claim_id, r, docs, claim.get("samplePack"))),
        )
        flags: list[Flag] = pol_flags + for_flags + link_flags
        risk, v = await timed("verdict", verdict.run(r, pol_out, flags))

        await ref.update({
            "status": "ready",
            "policy": {"assessment": pol_out.model_dump() if pol_out else None, "schedule": schedule},
            "flags": [f.model_dump() for f in flags],
            "entities": ents,
            "linkKeys": [e["key"] for e in ents],
            "links": links,
            "risk": risk,
            "verdict": v.model_dump(),
            "processingMs": int((time.monotonic() - t0) * 1000),
            "processedAt": firestore.SERVER_TIMESTAMP,
        })
    except Exception as e:
        await ref.update({"status": "error", "error": str(e)[:500]})
