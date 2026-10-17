"""Seed the demo world into Firestore + Storage and run the agents on demo claims.

    uv run python scripts/seed.py --images     # generate the damage-photo pool with Gemini image generation (once)
    uv run python scripts/seed.py --reset      # wipe claims/policies, re-seed, run pipeline
    uv run python scripts/seed.py --packs-only # just re-render sample packs into frontend/public/samples
"""

import argparse
import asyncio
import io
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from claimgen import CARS, CITIES, Garage, racct, render_pack, rname, rphone, rplate  # noqa: E402
from scenarios import (  # noqa: E402
    CITYAUTO, GLASSPRO, IMAGE_PROMPTS, IMAGE_STYLE, KAVERI, MARINE, P, RING_BANK_A, RING_DUP_INVOICE, SPEEDFIX,
    demo_claims, live_packs,
)

IMAGES = ROOT / "images"
OUT = ROOT / "out"
SAMPLES = ROOT.parent.parent / "frontend" / "public" / "samples"
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gemini-3.1-flash-image")


# ---------------- images ----------------


def generate_images(force: bool = False, only: list[str] | None = None) -> None:
    from google.genai import errors, types
    from PIL import Image

    from app.clients import gemini

    IMAGES.mkdir(exist_ok=True)
    for key, prompt in IMAGE_PROMPTS.items():
        path = IMAGES / f"{key}.jpg"
        if only and key not in only:
            continue
        if path.exists() and not force:
            continue
        print(f"image: {key}")
        for attempt in range(8):
            try:
                resp = gemini().models.generate_content(
                    model=IMAGE_MODEL, contents=IMAGE_STYLE + prompt,
                    config=types.GenerateContentConfig(response_modalities=["IMAGE"],
                                                       image_config=types.ImageConfig(aspect_ratio="4:3")),
                )
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


# ---------------- sample packs (served by Firebase Hosting) ----------------


def render_sample_packs() -> None:
    manifest = []
    for s in live_packs():
        files = render_pack(s, SAMPLES / s.id, IMAGES)
        manifest.append({"id": s.id, "title": s.title, "description": s.description_for_pack,
                         "files": [f for f, _ in files]})
    (SAMPLES / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"rendered {len(manifest)} sample packs -> {SAMPLES}")


# ---------------- history ----------------


def hist_entities(name, phone, email, bank, vehicle, garage: Garage, invoice_no) -> list[dict]:
    from app.agents.linker import entities
    from app.schemas import Invoice, ReaderOutput

    inv = Invoice(number=invoice_no, date=None, garage_name=garage.name, garage_gstin=garage.gstin, garage_phone=None,
                  line_items=[], subtotal=None, tax=None, total=None, name_on_invoice=None, vehicle_on_invoice=None)
    r = ReaderOutput(
        documents=[], claimant_name=name, claimant_phone=phone, claimant_email=email, bank_account=bank,
        bank_ifsc=None, policy_number=None, vehicle_registration=vehicle, vehicle_make_model=None,
        vehicle_colour=None, incident_date=None, incident_time=None, incident_location=None,
        incident_description=None, damage_areas_claimed=[], claim_amount=None, filed_date=None,
        police_report_number=None, invoice=inv, photo_observations=[],
    )
    return entities(r)


def history(rng: random.Random) -> list[dict]:
    """Closed past claims: background for the Linker. A few are confirmed fraud at Speedfix."""
    rows = []
    garages = [CITYAUTO, KAVERI, GLASSPRO, MARINE]
    for i in range(56):
        g = SPEEDFIX if i % 14 == 0 else rng.choice(garages)  # some honest Speedfix business too
        name, phone = rname(rng), rphone(rng)
        rows.append(dict(name=name, phone=phone, email=None, bank=racct(rng), vehicle=rplate(rng), garage=g,
                         invoice=f"{g.name[:3].upper()}-{rng.randint(1000, 9999)}", amount=rng.randint(8, 90) * 1000,
                         days_ago=rng.randint(60, 700), fraud=False, score=rng.choice([0, 0, 6, 6, 15, 21])))
    rows += [
        dict(name="Nitin Bhosale", phone="+91 98221 70345", email=None, bank=RING_BANK_A, vehicle="MH 14 CZ 1190",
             garage=SPEEDFIX, invoice=RING_DUP_INVOICE, amount=74500, days_ago=210, fraud=True, score=88),
        dict(name="Ajay Gaikwad", phone="+91 97633 10982", email=None, bank="300400500611", vehicle="MH 12 LM 4410",
             garage=SPEEDFIX, invoice="SMW/25-26/0388", amount=68200, days_ago=260, fraud=True, score=79),
        dict(name="Swati More", phone="+91 98500 66310", email=None, bank="300400500611", vehicle="MH 14 AA 7781",
             garage=SPEEDFIX, invoice="SMW/25-26/0455", amount=59900, days_ago=190, fraud=True, score=81),
    ]
    now = datetime.now(timezone.utc)
    docs = []
    for n, h in enumerate(rows):
        ents = hist_entities(h["name"], h["phone"], h["email"], h["bank"], h["vehicle"], h["garage"], h["invoice"])
        score = h["score"]
        docs.append({
            "claimNumber": f"RS-{700 + n}",
            "status": "closed",
            "inQueue": False,
            "isDemo": True,
            "fraudConfirmed": h["fraud"],
            "claimantName": h["name"],
            "vehicleRegistration": h["vehicle"],
            "claimAmount": h["amount"],
            "garageName": h["garage"].name,
            "entities": ents,
            "linkKeys": [e["key"] for e in ents],
            "risk": {"score": score, "band": "high" if score >= 60 else "medium" if score >= 25 else "low"},
            "createdAt": now - timedelta(days=h["days_ago"]),
            "outcome": "Repudiated: fraud confirmed by SIU" if h["fraud"] else "Settled",
        })
    return docs


# ---------------- main seed ----------------


async def seed(process: bool) -> None:
    from app.clients import bucket, db
    from app.pipeline import initial_stages, run_pipeline
    from app.rules import norm

    client = db()
    print("resetting collections…")
    for col in ("claims", "policies", "meta"):
        await client.recursive_delete(client.collection(col))

    for pol in P.values():
        await client.collection("policies").document(norm(pol.number).upper()).set(pol.record())
    print(f"policies: {len(P)}")

    hist = history(random.Random(42))
    batch = client.batch()
    for h in hist:
        batch.set(client.collection("claims").document(), h)
    await batch.commit()
    print(f"historical claims: {len(hist)}")

    now = datetime.now(timezone.utc)
    ids = []
    specs = demo_claims()
    for i, s in enumerate(specs):
        files = render_pack(s, OUT / "packs" / s.id, IMAGES)
        docs = []
        for fname, mime in files:
            path = f"demo/{s.id}/{fname}"
            await asyncio.to_thread(bucket().blob(path).upload_from_filename, str(OUT / "packs" / s.id / fname),
                                    content_type=mime)
            docs.append({"path": path, "name": fname, "mime_type": mime})
        ref = client.collection("claims").document(s.id)
        await ref.set({
            "claimNumber": f"RS-{1001 + i}", "status": "queued", "inQueue": True, "isDemo": True,
            "createdBy": "seed", "createdAt": now - timedelta(minutes=10 * (len(specs) - i)),
            "documents": docs, "note": None, "samplePack": None, "stages": initial_stages(),
            "flags": [], "linkKeys": [], "label": s.label, "tells": s.tells,
        })
        ids.append(s.id)
    await client.collection("meta").document("counters").set({"claims": 1000 + len(specs)})
    print(f"demo claims: {len(ids)}")

    if not process:
        return
    for cid in ids:
        print(f"pipeline: {cid}")
        await run_pipeline(cid)
    # second pass so earlier ring members also see the later ones
    for cid in [c for c in ids if c.startswith("demo-ring")]:
        print(f"pipeline (pass 2): {cid}")
        await run_pipeline(cid)
    async for snap in client.collection("claims").where("isDemo", "==", True).where("inQueue", "==", True).stream():
        d = snap.to_dict()
        print(f"  {d['claimNumber']:8} {snap.id:24} {d.get('status'):10} risk={(d.get('risk') or {}).get('score')}"
              f"  flags={[f['code'] for f in d.get('flags', [])]}")


async def redo(ids: list[str]) -> None:
    """Re-render, re-upload and re-run selected demo claims without wiping anything."""
    from app.clients import bucket
    from app.pipeline import run_pipeline

    for s in [x for x in demo_claims() if x.id in ids]:
        out = OUT / "packs" / s.id
        for fname, mime in render_pack(s, out, IMAGES):
            await asyncio.to_thread(bucket().blob(f"demo/{s.id}/{fname}").upload_from_filename, str(out / fname),
                                    content_type=mime)
        print(f"pipeline: {s.id}")
        await run_pipeline(s.id)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", action="store_true", help="generate missing photos with Gemini")
    ap.add_argument("--force-images", action="store_true")
    ap.add_argument("--only", nargs="*", help="regenerate only these image keys")
    ap.add_argument("--packs-only", action="store_true")
    ap.add_argument("--reset", action="store_true", help="wipe and re-seed Firestore/Storage")
    ap.add_argument("--no-process", action="store_true", help="seed without running the agents")
    ap.add_argument("--redo", nargs="*", help="re-run these demo claim ids in place")
    a = ap.parse_args()
    if a.images or a.force_images:
        generate_images(force=a.force_images, only=a.only)
    render_sample_packs()
    if a.packs_only:
        return
    if a.redo:
        asyncio.run(redo(a.redo))
        return
    if a.reset:
        asyncio.run(seed(process=not a.no_process))


if __name__ == "__main__":
    main()
