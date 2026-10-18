"""Full case files for the historical (closed) claims, so every linked claim a judge opens has real
documents and details. Deterministic and offline (no Gemini): these are past claims decided by
adjusters and the SIU, not by the agents. Names, phones, bank accounts, vehicles and invoice numbers
come from seed.history_rows(), so existing link keys and links do not change.

    uv run python scripts/history.py          # enrich the 59 historical claims in place
"""

import asyncio
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT.parent)]

from claimgen import CARS, ClaimSpec, Policy, _header, _rows, render_pack  # noqa: E402
from scenarios import GLASSPRO  # noqa: E402

OUT = ROOT / "out" / "history"

TEMPLATES = {
    "rear": ("Hit from behind by another car in slow traffic.", ["rear bumper"],
             [("Rear bumper replacement", 45), ("Rear bumper painting", 30), ("Labour", 25)]),
    "front": ("Hit a road divider while avoiding a pothole.", ["front bumper", "headlamp"],
              [("Front bumper replacement", 40), ("Headlamp assembly", 30), ("Painting", 15), ("Labour", 15)]),
    "door": ("Another vehicle scraped the side while parked.", ["front left door"],
             [("Door denting", 35), ("Door painting", 40), ("Labour", 25)]),
    "windscreen": ("A stone thrown up by a truck cracked the windscreen.", ["windscreen"],
                   [("Windscreen glass replacement", 80), ("Moulding & sealant", 10), ("Fitting labour", 10)]),
}

FRAUD_CASES = {
    "Nitin Bhosale": dict(
        area="rear",
        description="Car was parked outside home overnight; found the rear damaged by an unknown vehicle.",
        damage=["rear bumper", "boot lid", "rear quarter panel"],
        items=[("Rear bumper replacement", 22), ("Boot lid replacement", 34), ("Quarter panel denting", 16),
               ("Painting (full rear)", 18), ("Labour", 10)],
        findings=[
            ("forensics", "high", "Invoiced parts were never replaced",
             "Physical inspection found the original boot lid and quarter panel still fitted, although invoice "
             "SMW/25-26/0412 bills for both."),
            ("linker", "high", "Settlement account belongs to a third party",
             "Bank account A/c ••8812 is not in the insured's name; the bank confirmed it is operated by an "
             "associate of the repairing garage."),
            ("forensics", "medium", "Pre-existing rust at the damage site",
             "Survey photos show corrosion along the dent edges on the quarter panel, indicating old damage."),
        ],
        siu="Case SIU/2026/031. Garage owner admitted to raising the invoice before any repair. Claim "
            "repudiated under clause 7.1 and reported to the industry fraud repository."),
    "Ajay Gaikwad": dict(
        area="front",
        description="Unknown vehicle hit my parked car at night and drove away.",
        damage=["front bumper", "bonnet", "grille"],
        items=[("Front bumper replacement", 28), ("Bonnet replacement", 36), ("Grille", 12), ("Painting", 14),
               ("Labour", 10)],
        findings=[
            ("forensics", "high", "Damage pattern indicates a staged impact",
             "Horizontal scrape marks and brick residue on the bumper match contact with a wall, not a moving "
             "vehicle as reported."),
            ("forensics", "high", "Repair estimate dated before the incident",
             "Speedfix estimate EST-0388 is dated four days before the reported date of the incident."),
            ("linker", "high", "Settlement account shared with another claimant",
             "A/c ••0611 is also the payout account on claim RS-758 (Swati More)."),
        ],
        siu="Case SIU/2026/024. Garage CCTV showed the vehicle in the workshop before the reported incident. "
            "Claim repudiated under clause 7.1."),
    "Swati More": dict(
        area="door",
        description="Car was hit on the side while parked in a market lane.",
        damage=["front left door", "rear left door"],
        items=[("Front left door replacement", 34), ("Rear left door denting", 22), ("Painting", 30),
               ("Labour", 14)],
        findings=[
            ("forensics", "high", "Photos show a different vehicle",
             "The submitted damage photos show a silver car; the insured vehicle is registered as white."),
            ("linker", "high", "Settlement account shared with another claimant",
             "A/c ••0611 is also the payout account on claim RS-757 (Ajay Gaikwad)."),
            ("policy", "medium", "Vehicle not produced for survey",
             "The insured did not make the vehicle available for inspection within 7 days of two requests "
             "(clause 6.4)."),
        ],
        siu="Case SIU/2026/035. Linked to RS-757 through a shared payout account and the same garage. "
            "Claim repudiated under clause 7.1."),
}

QUOTES = {
    "2.1": ("Own Damage Cover", "The Company will indemnify the Insured against loss of or damage to the Insured "
                                "Vehicle caused by: (a) accidental external means"),
    "3.1": ("Deductible", "A compulsory deductible of INR 1,000 applies to each claim for vehicles up to 1500 cc, "
                          "and INR 2,000 for vehicles above 1500 cc."),
    "7.1": ("Fraud", "If any claim is fraudulent in any respect ... all benefits under this policy in respect of "
                     "that claim are forfeited."),
}


def siu_report(claim_no: str, name: str, vehicle: str, case: dict, closed: date, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = _header(c, "SPECIAL INVESTIGATION UNIT: CASE SUMMARY", "Redstring Demo General Insurance · Confidential")
    y = _rows(c, y - 4, [("Claim", claim_no), ("Insured", name), ("Vehicle", vehicle),
                         ("Closed on", closed.strftime("%d/%m/%Y")), ("Outcome", "Repudiated: fraud confirmed")])
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y - 6, "Findings")
    y = _rows(c, y - 24, [(f"{i}. {t}", e) for i, (_, _, t, e) in enumerate(case["findings"], 1)], col=70 * mm)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y - 6, "Conclusion")
    _rows(c, y - 24, [("Summary", case["siu"])], col=30 * mm)
    c.showPage()
    c.save()


def build(n: int, row: dict, created, policy_no: str) -> tuple[ClaimSpec, dict, list[tuple[str, str]]]:
    rng = random.Random(f"hist-{n}")
    claim_no = f"RS-{700 + n}"
    case = FRAUD_CASES.get(row["name"])
    make, cc = rng.choice(CARS)
    city = row["garage"].address.rsplit(",", 1)[-1].strip().split()[0]  # incident in the garage's city
    if case:
        area, desc, damage, weights = case["area"], case["description"], case["damage"], case["items"]
    else:
        area = "windscreen" if row["garage"] is GLASSPRO else rng.choice(["rear", "front", "door"])
        desc, damage, weights = TEMPLATES[area]
    subtotal = round(row["amount"] / 1.18)
    total_w = sum(w for _, w in weights)
    items = [(d, round(subtotal * w / total_w / 10) * 10) for d, w in weights]
    items[-1] = (items[-1][0], subtotal - sum(a for _, a in items[:-1]))
    filed = created.date()
    incident = filed - timedelta(days=rng.randint(1, 2))
    policy = Policy(policy_no, row["name"], row["vehicle"], make, incident - timedelta(days=rng.randint(90, 330)),
                    rng.randint(4, 14) * 100000, cc)
    spec = ClaimSpec(
        id=claim_no, title="history", policy=policy, claimant=row["name"], phone=row["phone"],
        email=f"{row['name'].split()[0].lower()}.{n}@example.com", bank_acct=row["bank"], ifsc="SBIN0000001",
        incident=incident, incident_time=f"{rng.randint(7, 22):02d}:{rng.choice(['10', '25', '40', '55'])}",
        location=f"{city}", description=desc, damage_areas=damage, garage=row["garage"],
        invoice_no=row["invoice"], line_items=items, filed_offset_days=(filed - incident).days,
        invoice_offset_days=rng.randint(4, 9), label="fraud" if case else "clean",
    )
    closed = incident + timedelta(days=rng.randint(18, 45) if case else rng.randint(7, 20))
    deductible = 1000 if cc <= 1500 else 2000
    paid = max(0, spec.total - deductible - round(spec.subtotal * rng.uniform(0.03, 0.08)))
    extra = [("siu_report.pdf", "application/pdf")] if case else []
    return spec, dict(case=case, closed=closed, deductible=deductible, paid=paid, claim_no=claim_no), extra


async def enrich() -> None:
    from seed import history_rows

    from app.clients import bucket, db
    from app.rules import band, norm

    rows = history_rows(random.Random(42))
    client = db()
    by_no = {}
    async for snap in client.collection("claims").where("inQueue", "==", False).stream():
        d = snap.to_dict()
        if d.get("claimNumber", "").startswith("RS-7"):
            by_no[d["claimNumber"]] = (snap.reference, d)
    assert len(by_no) == len(rows), (len(by_no), len(rows))

    # all claims, for computing each historical claim's links (same rules as the Linker)
    everyone = {}
    async for snap in client.collection("claims").stream():
        d = snap.to_dict()
        if d.get("linkKeys") and d.get("isDemo"):  # only the shared demo world, never evaluators' own claims
            everyone[snap.id] = d
    holders = defaultdict(set)
    for cid, d in everyone.items():
        for k in d["linkKeys"]:
            holders[k].add(cid)

    for n, row in enumerate(rows):
        claim_no = f"RS-{700 + n}"
        ref, current = by_no[claim_no]
        assert current["claimantName"] == row["name"], (claim_no, current["claimantName"], row["name"])
        policy_no = f"PCP-2025-{610000 + n}"
        spec, meta, extra = build(n, row, current["createdAt"], policy_no)
        case = meta["case"]

        out = OUT / claim_no
        files = render_pack(spec, out, ROOT / "images") + extra
        if case:
            siu_report(claim_no, row["name"], row["vehicle"], case, meta["closed"], out / "siu_report.pdf")
        docs = []
        for f, mime in files:
            path = f"demo/history/{claim_no}/{f}"
            await asyncio.to_thread(bucket().blob(path).upload_from_filename, str(out / f), content_type=mime)
            docs.append({"path": path, "name": f, "mime_type": mime})
        await client.collection("policies").document(norm(policy_no).upper()).set(spec.policy.record())

        extracted = {
            "claimant_name": row["name"], "claimant_phone": row["phone"], "claimant_email": spec.email,
            "bank_account": row["bank"], "bank_ifsc": spec.ifsc, "policy_number": policy_no,
            "vehicle_registration": row["vehicle"], "vehicle_make_model": spec.policy.make_model,
            "vehicle_colour": spec.colour, "incident_date": spec.incident.isoformat(),
            "incident_time": spec.incident_time, "incident_location": spec.location,
            "incident_description": spec.description, "damage_areas_claimed": spec.damage_areas,
            "claim_amount": spec.total, "filed_date": spec.filed.isoformat(), "police_report_number": None,
            "invoice": {"number": row["invoice"], "date": spec.invoice_date.isoformat(),
                        "garage_name": row["garage"].name, "garage_gstin": row["garage"].gstin,
                        "garage_phone": row["garage"].phone,
                        "line_items": [{"description": d, "amount": a} for d, a in spec.line_items],
                        "subtotal": spec.subtotal, "tax": spec.tax, "total": spec.total,
                        "name_on_invoice": row["name"], "vehicle_on_invoice": row["vehicle"]},
            "photo_observations": [],
        }
        closed = meta["closed"].strftime("%d %b %Y")
        if case:
            flags = [{"id": f"SIU_{i}", "agent": a, "code": "SIU_FINDING", "severity": s, "title": t,
                      "evidence": e, "source": "doc:3", "status": "confirmed"}
                     for i, (a, s, t, e) in enumerate(case["findings"])]
            assessment = {"covered": False,
                          "coverage_summary": "Claim repudiated: the SIU confirmed the claim was fraudulent, so all "
                                              "benefits for it are forfeited under clause 7.1.",
                          "deductible": meta["deductible"], "payable_estimate": 0,
                          "exclusions_triggered": [{"clause_id": "7.1", "title": QUOTES["7.1"][0],
                                                    "quote": QUOTES["7.1"][1],
                                                    "reason": "Fraud confirmed by the Special Investigation Unit."}],
                          "supporting_clauses": [], "missing_documents": []}
            verdict = {"summary": f"Closed on {closed}: repudiated after a Special Investigation Unit inquiry. "
                                  + case["siu"],
                       "key_reasons": [t for _, _, t, _ in case["findings"]],
                       "next_steps": ["Case closed; details shared with the industry fraud repository (clause 7.2)."]}
            outcome = "Repudiated: fraud confirmed by SIU"
        else:
            flags = []
            assessment = {"covered": True,
                          "coverage_summary": "Accidental damage covered under own damage cover; policy in force on "
                                              "the incident date.",
                          "deductible": meta["deductible"], "payable_estimate": meta["paid"],
                          "exclusions_triggered": [],
                          "supporting_clauses": [{"clause_id": k, "title": QUOTES[k][0], "quote": QUOTES[k][1],
                                                  "reason": r} for k, r in
                                                 [("2.1", "Damage from accidental external means."),
                                                  ("3.1", "Compulsory deductible applied.")]],
                          "missing_documents": []}
            verdict = {"summary": f"Settled on {closed}: ₹{meta['paid']:,} paid to the insured after the "
                                  f"₹{meta['deductible']:,} deductible and depreciation on parts. The survey found "
                                  "the damage consistent with the reported incident.",
                       "key_reasons": ["Damage consistent with the reported incident",
                                       "Invoice verified with the garage", "Policy in force on the incident date"],
                       "next_steps": ["Case closed."]}
            outcome = f"Settled: ₹{meta['paid']:,} paid"

        links = []
        for other in sorted({o for k in current["linkKeys"] for o in holders[k]} - {ref.id}):
            od = everyone[other]
            shared = sorted(set(current["linkKeys"]) & set(od["linkKeys"]))
            links.append({"claimId": other, "claimNumber": od.get("claimNumber"),
                          "claimantName": od.get("claimantName"),
                          "riskScore": (od.get("risk") or {}).get("score"),
                          "fraudConfirmed": bool(od.get("fraudConfirmed")),
                          "shared": [{"key": k, "kind": k.split(":", 1)[0]} for k in shared]})

        score = (current.get("risk") or {}).get("score", 0)
        await ref.update({
            "documents": docs, "extracted": extracted, "flags": flags, "links": links,
            "policy": {"assessment": assessment, "schedule": spec.policy.record()},
            "verdict": verdict, "outcome": outcome, "closedAt": meta["closed"].isoformat(),
            "incidentDate": spec.incident.isoformat(), "claimAmount": spec.total,
            "risk": {"score": score, "band": band(score)},
        })
    print(f"enriched {len(rows)} historical claims")


if __name__ == "__main__":
    asyncio.run(enrich())
