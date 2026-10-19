"""Seed the health and property demo worlds as STAGED data (hidden from the live site).

    uv run python scripts/lines_seed.py --images      # generate property photos (once)
    uv run python scripts/lines_seed.py --packs-only  # sample packs -> frontend/public/samples (manifest-lines.json)
    uv run python scripts/lines_seed.py --seed        # history + demo claims, runs the agents on the demo claims
    uv run python scripts/lines_seed.py --release     # flip staged data to live demo data (after promotion)
"""

import argparse
import asyncio
import io
import json
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT.parent)]

import lines_data as L  # noqa: E402

IMAGES = ROOT / "images"
OUT = ROOT / "out" / "lines"
SAMPLES = ROOT.parent.parent / "frontend" / "public" / "samples"
STAGED = {"staged": True, "isDemo": False, "createdBy": "staging"}

QUOTES = {
    "health": {"2.1": ("Cover", "The Company will reimburse reasonable and customary medical expenses incurred on "
                                "hospitalisation of an Insured Person for illness or injury during the Policy Period"),
               "7.1": ("Fraud", "If any claim is fraudulent in any respect ... all benefits under this policy in "
                                "respect of that claim are forfeited.")},
    "property": {"2.1": ("Cover", "The Company will indemnify the Insured against loss of or damage to the Insured "
                                  "Property caused by"),
                 "3.1": ("Deductible", "A deductible of INR 5,000 applies to each claim."),
                 "6.1": ("Fraud", "If any claim is fraudulent in any respect ... all benefits under this policy in "
                                  "respect of that claim are forfeited.")},
}


# ---------------- images and packs ----------------

def generate_images() -> None:
    from google.genai import errors, types
    from PIL import Image

    from app.clients import gemini

    for key, prompt in L.PROPERTY_IMAGES.items():
        path = IMAGES / f"{key}.jpg"
        if path.exists():
            continue
        print(f"image: {key}")
        for attempt in range(8):
            try:
                resp = gemini().models.generate_content(
                    model="gemini-3.1-flash-image", contents=L.PROPERTY_STYLE + prompt,
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"],
                                                       image_config=types.ImageConfig(aspect_ratio="4:3")))
                break
            except errors.ClientError as e:
                if e.code != 429 or attempt == 7:
                    raise
                print(f"  rate limited, retrying in {20 * (attempt + 1)}s")
                time.sleep(20 * (attempt + 1))
        data = next(p.inline_data.data for p in resp.candidates[0].content.parts if p.inline_data)
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((1280, 1280))
        img.save(path, "JPEG", quality=86)


def render_packs() -> None:
    manifest = []
    for s, line in ((L.health_pack(), "health"), (L.property_pack(), "property")):
        out = SAMPLES / s.id
        files = L.render_health(s, out) if line == "health" else L.render_property(s, out, IMAGES)
        manifest.append({"id": s.id, "line": line, "title": s.title, "description": s.pack_description,
                         "files": [f for f, _ in files]})
    # separate manifest: the live site only reads manifest.json, so these stay hidden until release
    (SAMPLES / "manifest-lines.json").write_text(json.dumps(manifest, indent=2))
    print(f"rendered {len(manifest)} line sample packs")


# ---------------- reader-shaped records for history ----------------

def health_extracted(s: L.HealthClaim):
    from app.lines.health import HealthDoc, HealthReaderOutput
    from app.schemas import LineItem
    return HealthReaderOutput(
        documents=[HealthDoc(index=i, kind=k, summary=t) for i, (k, t) in
                   enumerate([("claim_form", "Health claim form"), ("hospital_bill", "Final hospital bill"),
                              ("discharge_summary", "Discharge summary")])],
        claimant_name=s.holder, patient_name=s.patient, patient_age=s.age, relationship_to_policyholder=s.relationship,
        claimant_phone=s.phone, claimant_email=s.email, bank_account=s.bank, bank_ifsc="HDFC0001234",
        policy_number=s.policy_no, hospital_name=s.hospital.name, hospital_registration=s.hospital.reg,
        hospital_city=s.hospital.city, treating_doctor=s.doctor.name, doctor_registration=s.doctor.reg,
        admission_date=s.admission.isoformat(), discharge_date=s.discharge.isoformat(), diagnosis=s.diagnosis,
        procedure=s.procedure or None, accident=s.accident, bill_number=s.bill_no, bill_date=s.bill_date.isoformat(),
        room_rent_per_day=s.room_rent, bill_line_items=[LineItem(description=d, amount=a) for d, a in s.items],
        bill_subtotal=s.subtotal, bill_total=s.total, name_on_bill=s.patient, claim_amount=s.claimed,
        filed_date=s.filed.isoformat())


def property_extracted(s: L.PropertyClaim):
    from app.lines.property import PropertyDoc, PropertyReaderOutput
    from app.schemas import LineItem
    return PropertyReaderOutput(
        documents=[PropertyDoc(index=0, kind="claim_form", summary="Home claim form"),
                   PropertyDoc(index=1, kind="contractor_invoice", summary="Contractor invoice")],
        claimant_name=s.holder, claimant_phone=s.phone, claimant_email=s.email, bank_account=s.bank,
        bank_ifsc="ICIC0000331", policy_number=s.policy_no, property_address=s.address, incident_type=s.incident_type,
        incident_date=s.incident.isoformat(), incident_description=s.description, damaged_items=s.damaged,
        police_report_number=s.fir, contractor_name=s.contractor.name, contractor_gstin=s.contractor.gstin,
        invoice_number=s.invoice_no, invoice_date=s.invoice_date.isoformat(), work_address=s.address,
        invoice_line_items=[LineItem(description=d, amount=a) for d, a in s.items], invoice_subtotal=s.subtotal,
        invoice_total=s.total, claim_amount=s.claimed, filed_date=s.filed.isoformat(), photo_observations=[])


def scale(weights: list[tuple[str, int]], target: int) -> list[tuple[str, int]]:
    tw = sum(w for _, w in weights)
    items = [(d, round(target * w / tw / 10) * 10) for d, w in weights]
    items[-1] = (items[-1][0], target - sum(a for _, a in items[:-1]))
    return items


def health_hist_spec(n: int, row: dict, created: datetime) -> L.HealthClaim:
    rng = random.Random(f"h-hist-{n}")
    days = rng.randint(2, 5)
    adm = created.date() - timedelta(days=days + 3)
    weights = [(f"Room rent ({days} days)", 20), ("Doctor visits", 12), ("Medicines and consumables", 22),
               ("Investigations", 12)] + ([("Surgeon and OT charges", 34)] if row["procedure"] else [("Nursing", 6)])
    return L.HealthClaim(
        f"h-hist-{n}", "history", f"FHI-2025-{520000 + n}", row["name"], row["name"], rng.randint(25, 62), "Self",
        row["phone"], f"{row['name'].split()[0].lower()}.h{n}@example.com", row["bank"], row["hospital"], row["doctor"],
        adm, days, row["diagnosis"], row["procedure"], scale(weights, row["amount"]), 4000,
        adm - timedelta(days=rng.randint(400, 900)), 500000, [row["name"]], row["bill"])


def property_hist_spec(n: int, row: dict, created: datetime) -> L.PropertyClaim:
    rng = random.Random(f"p-hist-{n}")
    inc = created.date() - timedelta(days=2)
    weights = {"water_damage": [("Ceiling and wall repair", 50), ("Waterproofing", 30), ("Painting", 20)],
               "fire": [("Rewiring", 35), ("Furniture replacement", 40), ("Soot cleaning and painting", 25)],
               "storm": [("Roof repair", 55), ("Window glass replacement", 25), ("Debris clearing", 20)],
               "flood": [("Wall plaster and painting", 45), ("Door replacement", 30), ("Furniture replacement", 25)]}
    sub = round(row["amount"] / 1.18)
    return L.PropertyClaim(
        f"p-hist-{n}", "history", f"HSP-2025-{720000 + n}", row["name"], row["phone"],
        f"{row['name'].split()[0].lower()}.p{n}@example.com", row["bank"], row["address"], row["incident"], inc,
        row["description"], [w for w, _ in weights[row["incident"]]], row["contractor"], row["invoice"],
        scale(weights[row["incident"]], sub), inc - timedelta(days=rng.randint(300, 900)), 3000000, 700000)


# ---------------- seeding ----------------

async def _upload(paths: list[tuple[str, str]], local: Path, prefix: str) -> list[dict]:
    from app.clients import bucket
    docs = []
    for f, mime in paths:
        p = f"{prefix}/{f}"
        await asyncio.to_thread(bucket().blob(p).upload_from_filename, str(local / f), content_type=mime)
        docs.append({"path": p, "name": f, "mime_type": mime})
    return docs


async def seed(process: bool) -> None:
    from app.clients import db
    from app.lines.health import entities as h_entities
    from app.lines.property import entities as p_entities
    from app.pipeline import initial_stages, run_pipeline
    from app.rules import band, norm
    from history import siu_report

    client = db()
    async for snap in client.collection("claims").where("staged", "==", True).stream():
        await client.recursive_delete(snap.reference)

    now = datetime.now(timezone.utc)
    hist_ids: list[str] = []
    for line, rows, spec_fn, extract_fn, ent_fn, base in (
            ("health", L.health_history(random.Random(7)), health_hist_spec, health_extracted, h_entities, 800),
            ("property", L.property_history(random.Random(9)), property_hist_spec, property_extracted, p_entities, 900)):
        for n, row in enumerate(rows):
            claim_no = f"RS-{base + n}"
            created = now - timedelta(days=row["days_ago"])
            s = spec_fn(n, row, created)
            out = OUT / "history" / claim_no
            files = L.render_health(s, out) if line == "health" else L.render_property(s, out, IMAGES)
            closed = (s.discharge if line == "health" else s.incident) + timedelta(days=random.Random(claim_no).randint(10, 40))
            if row["fraud"]:
                case = {"findings": row["findings"], "siu": row["siu"]}
                siu_report(claim_no, row["name"], s.hospital.name if line == "health" else s.address, case, closed,
                           out / "siu_report.pdf")
                files.append(("siu_report.pdf", "application/pdf"))
            docs = await _upload(files, out, f"demo/{line}/history/{claim_no}")
            await client.collection("policies").document(norm(s.policy_no).upper()).set(s.policy_record())
            r = extract_fn(s)
            ents = ent_fn(r)
            fraud_clause = "7.1" if line == "health" else "6.1"
            q = QUOTES[line]
            if row["fraud"]:
                flags = [{"id": f"SIU_{i}", "agent": a, "code": "SIU_FINDING", "severity": sv, "title": t,
                          "evidence": e, "source": f"doc:{len(files) - 1}", "status": "confirmed"}
                         for i, (a, sv, t, e) in enumerate(row["findings"])]
                assessment = {"covered": False, "coverage_summary": f"Claim repudiated: fraud confirmed by the SIU, so "
                                                                     f"all benefits are forfeited under clause {fraud_clause}.",
                              "deductible": 0 if line == "health" else 5000, "payable_estimate": 0,
                              "exclusions_triggered": [{"clause_id": fraud_clause, "title": q[fraud_clause][0],
                                                        "quote": q[fraud_clause][1],
                                                        "reason": "Fraud confirmed by the Special Investigation Unit."}],
                              "supporting_clauses": [], "missing_documents": []}
                verdict = {"summary": f"Closed on {closed:%d %b %Y}: repudiated after a Special Investigation Unit "
                                      f"inquiry. {row['siu']}",
                           "key_reasons": [t for _, _, t, _ in row["findings"]],
                           "next_steps": ["Case closed; details shared with the industry fraud repository."]}
                outcome = "Repudiated: fraud confirmed by SIU"
            else:
                flags = []
                ded = 0 if line == "health" else 5000
                paid = max(0, s.claimed - ded - round(s.claimed * 0.04))
                assessment = {"covered": True, "coverage_summary": "Covered loss; policy in force on the date of loss.",
                              "deductible": ded, "payable_estimate": paid, "exclusions_triggered": [],
                              "supporting_clauses": [{"clause_id": "2.1", "title": q["2.1"][0], "quote": q["2.1"][1],
                                                      "reason": "Covered under the policy."}], "missing_documents": []}
                verdict = {"summary": f"Settled on {closed:%d %b %Y}: ₹{paid:,} paid after verification of the "
                                      + ("hospital records." if line == "health" else "damage by a surveyor."),
                           "key_reasons": ["Documents verified", "Policy in force on the date of loss",
                                           "No inconsistencies found"], "next_steps": ["Case closed."]}
                outcome = f"Settled: ₹{paid:,} paid"
            subject = (f"{s.patient} · {s.hospital.name}" if line == "health"
                       else f"{s.incident_type.replace('_', ' ').capitalize()} · {s.address.split(',')[-1].strip()}")
            ref = client.collection("claims").document()
            await ref.set({
                **STAGED, "claimNumber": claim_no, "lineOfBusiness": line, "status": "closed", "inQueue": False,
                "fraudConfirmed": row["fraud"], "claimantName": row["name"], "subject": subject,
                "providerName": s.hospital.name if line == "health" else s.contractor.name,
                "claimAmount": s.claimed, "incidentDate": (s.admission if line == "health" else s.incident).isoformat(),
                "createdAt": created, "closedAt": closed.isoformat(), "outcome": outcome, "documents": docs,
                "extracted": r.model_dump(), "flags": flags, "entities": ents, "linkKeys": [e["key"] for e in ents],
                "policy": {"assessment": assessment, "schedule": s.policy_record()}, "verdict": verdict,
                "risk": {"score": row["score"], "band": band(row["score"])},
            })
            hist_ids.append(ref.id)
    print(f"history: {len(hist_ids)} closed claims")

    demo_ids = []
    for line, specs, base in (("health", L.health_claims(), 2001), ("property", L.property_claims(), 3001)):
        for i, s in enumerate(specs):
            out = OUT / "packs" / s.id
            files = L.render_health(s, out) if line == "health" else L.render_property(s, out, IMAGES)
            docs = await _upload(files, out, f"demo/{line}/{s.id}")
            await client.collection("policies").document(norm(s.policy_no).upper()).set(s.policy_record())
            await client.collection("claims").document(s.id).set({
                **STAGED, "claimNumber": f"RS-{base + i}", "lineOfBusiness": line, "status": "queued", "inQueue": True,
                "createdAt": now - timedelta(minutes=5 * (len(specs) - i)), "documents": docs, "note": None,
                "samplePack": None, "stages": initial_stages(), "flags": [], "linkKeys": [], "label": s.label,
                "tells": s.tells})
            demo_ids.append(s.id)
    for p in (L.health_pack(), L.property_pack()):
        await client.collection("policies").document(norm(p.policy_no).upper()).set(p.policy_record())
    print(f"demo claims: {len(demo_ids)}")

    if process:
        for cid in demo_ids:
            ok = await run_pipeline(cid)
            d = (await client.collection("claims").document(cid).get()).to_dict()
            print(f"  {d['claimNumber']} {cid:20} {d['status']:6} risk={(d.get('risk') or {}).get('score')} "
                  f"flags={[f['code'] for f in d.get('flags', [])]}" + ("" if ok else f" ERROR {d.get('error')}"))
    await link_history(hist_ids)


async def redo(ids: list[str]) -> None:
    """Re-render, re-upload and re-run selected staged demo claims in place."""
    from app.clients import db
    from app.pipeline import run_pipeline
    client = db()
    specs = {s.id: ("health", s) for s in L.health_claims()} | {s.id: ("property", s) for s in L.property_claims()}
    for cid in ids:
        line, s = specs[cid]
        out = OUT / "packs" / s.id
        files = L.render_health(s, out) if line == "health" else L.render_property(s, out, IMAGES)
        docs = await _upload(files, out, f"demo/{line}/{s.id}")
        await client.collection("claims").document(cid).update({"documents": docs})
        await run_pipeline(cid)
        d = (await client.collection("claims").document(cid).get()).to_dict()
        print(f"  {d['claimNumber']} {cid:20} {d['status']:6} risk={(d.get('risk') or {}).get('score')} "
              f"action={(d.get('risk') or {}).get('action')} flags={[f['code'] for f in d.get('flags', [])]}")


async def link_history(hist_ids: list[str]) -> None:
    """Links for closed claims, computed among the staged world (same rules as the Linker)."""
    from app.clients import db
    client = db()
    world = {}
    async for snap in client.collection("claims").where("staged", "==", True).stream():
        d = snap.to_dict()
        if d.get("linkKeys"):
            world[snap.id] = d
    holders = defaultdict(set)
    for cid, d in world.items():
        for k in d["linkKeys"]:
            holders[k].add(cid)
    for hid in hist_ids:
        me = world[hid]
        links = []
        for other in sorted({o for k in me["linkKeys"] for o in holders[k]} - {hid}):
            od = world[other]
            shared = sorted(set(me["linkKeys"]) & set(od["linkKeys"]))
            links.append({"claimId": other, "claimNumber": od.get("claimNumber"), "claimantName": od.get("claimantName"),
                          "riskScore": (od.get("risk") or {}).get("score"), "fraudConfirmed": bool(od.get("fraudConfirmed")),
                          "shared": [{"key": k, "kind": k.split(":", 1)[0]} for k in shared]})
        await client.collection("claims").document(hid).update({"links": links})
    print(f"linked {len(hist_ids)} closed claims")


async def release() -> None:
    """After promotion: staged health/property data becomes regular demo data."""
    from google.cloud import firestore

    from app.clients import db
    n = removed = 0
    async for snap in db().collection("claims").where("staged", "==", True).stream():
        if (snap.to_dict() or {}).get("stagingTest"):
            await db().recursive_delete(snap.reference)  # test submissions made through the staging revision
            removed += 1
            continue
        await snap.reference.update({"staged": firestore.DELETE_FIELD, "isDemo": True, "createdBy": "seed"})
        n += 1
    print(f"released {n} claims, removed {removed} staging test claims")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", action="store_true")
    ap.add_argument("--packs-only", action="store_true")
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--no-process", action="store_true")
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--redo", nargs="*")
    a = ap.parse_args()
    if a.images:
        generate_images()
    render_packs()
    if a.redo:
        asyncio.run(redo(a.redo))
    elif a.release:
        asyncio.run(release())
    elif a.seed:
        asyncio.run(seed(process=not a.no_process))


if __name__ == "__main__":
    main()
