"""Run the real pipeline on a few demo claims (isolated, not in queue) and print results."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT.parent)]

from claimgen import render_pack  # noqa: E402
from scenarios import P, demo_claims  # noqa: E402

from app.clients import bucket, db  # noqa: E402
from app.pipeline import initial_stages, run_pipeline  # noqa: E402
from app.rules import norm  # noqa: E402


async def main(ids: list[str]) -> None:
    for pol in P.values():
        await db().collection("policies").document(norm(pol.number).upper()).set(pol.record())
    for s in [x for x in demo_claims() if x.id in ids]:
        out = ROOT / "out" / "packs" / s.id
        docs = []
        for f, mime in render_pack(s, out, ROOT / "images"):
            path = f"smoke/{s.id}/{f}"
            await asyncio.to_thread(bucket().blob(path).upload_from_filename, str(out / f), content_type=mime)
            docs.append({"path": path, "name": f, "mime_type": mime})
        cid = f"smoke-{s.id}"
        await db().collection("claims").document(cid).set({
            "claimNumber": cid, "status": "queued", "inQueue": False, "documents": docs,
            "stages": initial_stages(), "flags": [], "linkKeys": []})
        await run_pipeline(cid)
        d = (await db().collection("claims").document(cid).get()).to_dict()
        print(f"\n=== {cid}: {d['status']} {d.get('error') or ''} {d.get('processingMs')}ms  (expected: {s.label} {s.tells})")
        print({k: (v["status"], v.get("ms"), v.get("error")) for k, v in d["stages"].items()})
        if d["status"] == "ready":
            print("risk:", d["risk"])
            for f in d["flags"]:
                print(f"  [{f['severity']}] {f['code']}: {f['title']} | {f['evidence'][:160]}")
            print("verdict:", d["verdict"]["summary"])
            pa = d["policy"]["assessment"]
            print("policy:", pa["covered"], pa["payable_estimate"], pa["missing_documents"])
            x = d["extracted"]
            print("extracted:", x["claimant_name"], x["incident_date"], x["claim_amount"], (x["invoice"] or {}).get("date"),
                  (x["invoice"] or {}).get("subtotal"), [p["damage_areas_visible"] for p in x["photo_observations"]])
        sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
