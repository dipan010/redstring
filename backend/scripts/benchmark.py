"""Benchmark on a held-out synthetic set (not the demo claims the prompts were tuned on).

    uv run python scripts/benchmark.py [--n-clean 14] [--seed 7] [--concurrency 3]

Ground truth: each claim is generated clean or with one planted fraud signal.
Alert threshold (fixed before running): risk score >= 20, i.e. anything not "low" risk.
Writes docs/benchmark.json and docs/benchmark.md. Benchmark claims are marked isBenchmark,
so the Linker, queue and Red String graph ignore them.
"""

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from datetime import timedelta
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT.parent)]

from claimgen import ClaimSpec, Policy, racct, rname, rphone  # noqa: E402
from scenarios import CITYAUTO, GLASSPRO, KAVERI, MARINE, RING_BANK_A, RING_DUP_INVOICE, SPEEDFIX, TODAY  # noqa: E402

DOCS = ROOT.parent.parent / "docs"
OUT = ROOT / "out" / "bench"

# Per 1M tokens (input, output incl. thinking), USD. Gemini 3.5 Flash from third-party price trackers (Oct 2026);
# verify against https://cloud.google.com/vertex-ai/generative-ai/pricing before quoting.
PRICES = {"gemini-3.5-flash": (1.50, 9.00), "gemini-2.5-flash": (0.30, 2.50)}
ALERT_AT = 20

# what each photo actually shows (used so clean descriptions match the picture)
VISIBLE = {
    "front_red_hatch": ["front bumper", "bonnet", "grille", "left headlamp"],
    "front_black_suv": ["front bumper", "grille", "right headlamp"],
    "front_silver_hatch": ["front bumper", "left headlamp"],
    "rear_blue_suv": ["rear bumper", "right tail lamp"],
}
GARAGE_CITY = {"Pune": CITYAUTO, "Mumbai": MARINE, "Bengaluru": KAVERI, "Chennai": GLASSPRO}

# image key -> (plate, make/model, cc, colour, area)
IMAGES = {
    "rear_white_sedan": ("MH 12 KT 4471", "Honda City ZX", 1498, "White", "rear"),
    "windscreen_white_suv": ("TN 09 BX 2290", "Tata Nexon XZ+", 1199, "White", "windscreen"),
    "windscreen_white_suv_b": ("TN 09 CK 5512", "Tata Nexon XZ+", 1199, "White", "windscreen"),
    "door_grey_suv": ("KA 03 MN 7812", "Hyundai Creta SX", 1497, "Grey", "door"),
    "front_silver_hatch": ("MH 12 RS 9034", "Maruti Suzuki Swift VXI", 1197, "Silver", "front"),
    "front_red_hatch": ("MH 02 FA 1187", "Hyundai i20 Asta", 1197, "Red", "front"),
    "front_black_suv": ("MH 02 GH 6650", "Mahindra XUV700 AX5", 1997, "Black", "front"),
    "rear_blue_suv": ("MH 14 EV 5520", "Kia Seltos HTX", 1497, "Blue", "rear"),
}
AREA = {
    "rear": ("A car hit me from behind at a traffic signal.", ["rear bumper"],
             [("Rear bumper replacement", 9800), ("Rear bumper painting", 4200), ("Labour", 2500)]),
    "windscreen": ("A stone thrown up by a truck cracked the windscreen on the highway.", ["windscreen"],
                   [("Windscreen glass replacement", 11500), ("Moulding & sealant", 1200), ("Fitting labour", 1500)]),
    "door": ("A reversing SUV scraped hard along the front left door in a parking lot.", ["front left door"],
             [("Front left door denting", 3800), ("Door painting", 5200), ("Labour", 2000)]),
    "front": ("Hit a road divider while avoiding a pothole; front bumper and headlamp damaged.",
              ["front bumper", "headlamp"],
              [("Front bumper replacement", 8900), ("Headlamp assembly", 7400), ("Painting", 3600), ("Labour", 2200)]),
}
TELLS = ["invoice_before_incident", "invoice_arithmetic", "claim_above_invoice", "photo_mismatch",
         "invoice_name_mismatch", "incident_outside_period", "duplicate_invoice", "shared_bank", "old_damage"]
CITIES = ["Pune", "Mumbai", "Bengaluru", "Chennai"]


def jitter_photo(key: str, dest: Path, rng: random.Random) -> None:
    """Same scene, different bytes: a light crop + exposure change so exact-hash matching doesn't fire."""
    img = Image.open(ROOT / "images" / f"{key}.jpg")
    w, h = img.size
    dx, dy = int(w * rng.uniform(0.01, 0.04)), int(h * rng.uniform(0.01, 0.04))
    img = img.crop((dx, dy, w - dx, h - dy))
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.92, 1.08))
    dest.mkdir(parents=True, exist_ok=True)
    img.save(dest / f"{key}.jpg", "JPEG", quality=rng.randint(80, 92))


def make_claim(i: int, tell: str | None, rng: random.Random) -> tuple[ClaimSpec, Path]:
    key = "old_rust_white_hatch" if tell == "old_damage" else rng.choice(list(IMAGES))
    plate, model, cc, colour, area = IMAGES.get(key, ("MH 14 DT 3021", "Maruti Suzuki Swift VXI", 1197, "White", "rear"))
    desc_area = area
    if tell == "photo_mismatch":
        desc_area = rng.choice([a for a in AREA if a != area and not (a == "windscreen" or area == "windscreen")] or ["rear"])
    if tell == "old_damage":
        desc_area = "rear"
    desc, areas, items = AREA[desc_area]
    if tell == "old_damage":
        desc, areas = "Found the rear quarter panel and bumper damaged by an unknown vehicle this morning.", \
            ["rear quarter panel", "rear bumper"]
    if tell != "photo_mismatch" and key in VISIBLE:
        areas = VISIBLE[key]
        extra = [(f"{a.capitalize()} repair/replacement", 6500) for a in areas if a not in ("front bumper", "rear bumper")]
        items = items[:1] + extra + items[-2:]
    items = [(d, int(a * rng.uniform(0.85, 1.25)) // 10 * 10) for d, a in items]
    city = rng.choice(CITIES)

    name = rname(rng)
    incident = TODAY - timedelta(days=rng.randint(3, 20))
    start = incident - timedelta(days=rng.randint(60, 300))
    if tell == "incident_outside_period":
        start = incident + timedelta(days=rng.randint(5, 40))  # policy didn't exist yet
    policy = Policy(f"PCP-BENCH-{i:04d}", name, plate, model, start, rng.randint(5, 15) * 100000, cc)

    garage = GARAGE_CITY[city]  # repaired in the same city as the incident
    invoice_no = f"{garage.name[:3].upper()}/B/{rng.randint(10000, 99999)}"
    bank = racct(rng)
    if tell == "duplicate_invoice":
        garage, invoice_no = rng.choice([(SPEEDFIX, RING_DUP_INVOICE), (CITYAUTO, "CAC/2026/1182")])
    if tell == "shared_bank":
        bank = rng.choice([RING_BANK_A, "300400500611"])

    s = ClaimSpec(
        id=f"bench-{i:03d}", title="benchmark", policy=policy, claimant=name, phone=rphone(rng),
        email=f"{name.split()[0].lower()}.{i}@example.com", bank_acct=bank, ifsc="HDFC0000001",
        incident=incident, incident_time=f"{rng.randint(7, 21):02d}:{rng.choice(['05', '20', '40'])}",
        location=city, description=desc, damage_areas=areas, garage=garage,
        invoice_no=invoice_no, line_items=items, photos=[key], colour=colour,
        invoice_offset_days=-rng.randint(2, 6) if tell == "invoice_before_incident" else rng.randint(2, 6),
        subtotal_override=(sum(a for _, a in items) + rng.randint(30, 80) * 100) if tell == "invoice_arithmetic" else None,
        invoice_customer=rname(rng) if tell == "invoice_name_mismatch" else None,
        label="fraud" if tell else "clean", tells=[tell] if tell else [],
    )
    if tell == "claim_above_invoice":
        s.amount_claimed = int(s.total * rng.uniform(1.25, 1.5))
    img_dir = OUT / "img" / s.id
    jitter_photo(key, img_dir, rng)
    return s, img_dir


async def run_one(spec: ClaimSpec, img_dir: Path, sem: asyncio.Semaphore) -> dict:
    from claimgen import render_pack

    from app.clients import bucket, db
    from app.pipeline import initial_stages, run_pipeline
    from app.rules import norm

    async with sem:
        await db().collection("policies").document(norm(spec.policy.number).upper()).set(spec.policy.record())
        out = OUT / "packs" / spec.id
        docs = []
        for f, mime in render_pack(spec, out, img_dir):
            path = f"benchmark/{spec.id}/{f}"
            await asyncio.to_thread(bucket().blob(path).upload_from_filename, str(out / f), content_type=mime)
            docs.append({"path": path, "name": f, "mime_type": mime})
        ref = db().collection("claims").document(spec.id)
        await ref.set({"claimNumber": spec.id, "status": "queued", "inQueue": False, "isDemo": False,
                       "isBenchmark": True, "createdBy": "benchmark", "documents": docs,
                       "stages": initial_stages(), "flags": [], "linkKeys": []})
        t = time.monotonic()
        await run_pipeline(spec.id)
        d = (await ref.get()).to_dict()
        print(f"  {spec.id} {spec.label:5} {','.join(spec.tells) or '-':24} -> {d.get('status')} "
              f"risk={(d.get('risk') or {}).get('score')} {time.monotonic() - t:5.1f}s", flush=True)
        return {"id": spec.id, "label": spec.label, "tell": spec.tells[0] if spec.tells else None,
                "status": d.get("status"), "score": (d.get("risk") or {}).get("score"),
                "action": (d.get("risk") or {}).get("action"), "flags": [f["code"] for f in d.get("flags", [])],
                "ms": d.get("processingMs"), "usage": d.get("usage")}


def cost(usage: dict | None) -> float:
    if not usage:
        return 0.0
    total = 0.0
    for model, u in usage["byModel"].items():
        pin, pout = PRICES.get(model, PRICES["gemini-3.5-flash"])
        total += u["in"] / 1e6 * pin + (u["out"] + u["think"]) / 1e6 * pout
    return total


def report(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["status"] == "ready"]
    tp = sum(1 for r in ok if r["label"] == "fraud" and r["score"] >= ALERT_AT)
    fn = sum(1 for r in ok if r["label"] == "fraud" and r["score"] < ALERT_AT)
    fp = sum(1 for r in ok if r["label"] == "clean" and r["score"] >= ALERT_AT)
    tn = sum(1 for r in ok if r["label"] == "clean" and r["score"] < ALERT_AT)
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    per_tell = {}
    for t in TELLS:
        rs = [r for r in ok if r["tell"] == t]
        per_tell[t] = f"{sum(r['score'] >= ALERT_AT for r in rs)}/{len(rs)}"
    ms = sorted(r["ms"] for r in ok if r["ms"])
    costs = [cost(r["usage"]) for r in ok]
    toks = [r["usage"] for r in ok if r["usage"]]
    return {
        "claims": len(rows), "processed": len(ok), "errors": len(rows) - len(ok),
        "alert_threshold": ALERT_AT, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(prec, 3), "recall": round(rec, 3),
        "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0,
        "false_positive_rate": round(fp / (fp + tn), 3) if fp + tn else 0,
        "accuracy": round((tp + tn) / len(ok), 3) if ok else 0,
        "per_tell_recall": per_tell,
        "clean_fast_tracked": f"{sum(r['label'] == 'clean' and r['action'] == 'fast_track' for r in ok)}/"
                              f"{sum(r['label'] == 'clean' for r in ok)}",
        "latency_s": {"p50": round(statistics.median(ms) / 1000, 1), "p95": round(ms[int(0.95 * (len(ms) - 1))] / 1000, 1),
                      "max": round(ms[-1] / 1000, 1)} if ms else None,
        "avg_tokens": {k: round(statistics.mean(u[k] for u in toks)) for k in ("inputTokens", "outputTokens", "thinkingTokens")} if toks else None,
        "avg_gemini_calls": round(statistics.mean(u["calls"] for u in toks), 1) if toks else None,
        "cost_per_claim_usd": round(statistics.mean(costs), 4) if costs else None,
        "fallback_calls": sum(u["byModel"].get("gemini-2.5-flash", {}).get("calls", 0) for u in toks),
    }


def write(summary: dict, rows: list[dict]) -> None:  # noqa: C901
    DOCS.mkdir(exist_ok=True)
    (DOCS / "benchmark.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, default=str))
    s = summary
    lines = [
        "# Redstring benchmark", "",
        f"Held-out synthetic set: {s['claims']} claims generated by `backend/scripts/benchmark.py` "
        "(not the demo claims). Each fraudulent claim carries one planted signal; photos are re-encoded so "
        "exact-hash matching does not apply.", "",
        f"Alert = risk score ≥ {s['alert_threshold']} (medium or high risk). Fixed before running.", "",
        "| Metric | Value |", "|---|---|",
        f"| Precision | {s['precision']:.0%} |", f"| Recall | {s['recall']:.0%} |", f"| F1 | {s['f1']:.2f} |",
        f"| False-positive rate | {s['false_positive_rate']:.0%} |", f"| Accuracy | {s['accuracy']:.0%} |",
        f"| Clean claims fast-tracked | {s['clean_fast_tracked']} |",
        f"| Confusion (TP/FP/TN/FN) | {s['tp']}/{s['fp']}/{s['tn']}/{s['fn']} |",
        f"| Latency p50 / p95 / max | {s['latency_s']['p50']}s / {s['latency_s']['p95']}s / {s['latency_s']['max']}s |",
        f"| Gemini calls per claim | {s['avg_gemini_calls']} |",
        f"| Tokens per claim (in / out / thinking) | {s['avg_tokens']['inputTokens']:,} / {s['avg_tokens']['outputTokens']:,} / {s['avg_tokens']['thinkingTokens']:,} |",
        f"| Model cost per claim | ${s['cost_per_claim_usd']:.4f} |",
        f"| Calls served by fallback model | {s['fallback_calls']} |",
        f"| Processing errors | {s['errors']} |", "",
        "## Recall by fraud signal", "", "| Signal | Detected |", "|---|---|",
        *[f"| {k.replace('_', ' ')} | {v} |" for k, v in s["per_tell_recall"].items()], "",
        "Cost uses per-1M-token prices from third-party trackers (Oct 2026): " + ", ".join(f"{m} ${a} in / ${b} out" for m, (a, b) in PRICES.items()) + ".",
        "",
        "## Method and caveats", "",
        "- Severity weights and prompts were calibrated on a separate set (`--seed 7`); these numbers come from a "
        "freshly generated set (`--seed 11`) that was not used for tuning.",
        "- The set is small (32 claims) and synthetic. Real claims are messier (scans, handwriting, partial packs), "
        "so treat this as a functional check of the pipeline, not a production accuracy estimate.",
        "- Latency is end to end on Cloud Run-equivalent code: 4 Gemini calls (Reader, then Policy and Forensics in "
        "parallel, then Verdict) plus Firestore reads/writes. Calls slower than 25 s fall back to gemini-2.5-flash.",
        "- Score = 100 × (1 − e^(−evidence points / 60)): each flag adds evidence with diminishing returns, "
        "so scores spread out instead of capping at 100.",
        "- Known limitation: Gemini occasionally confuses the vehicle's left and right sides in front-facing photos.",
        "- Reproduce: `cd backend && uv run python scripts/benchmark.py --seed 11`.",
    ]
    (DOCS / "benchmark.md").write_text("\n".join(lines) + "\n")


async def main(n_clean: int, seed: int, concurrency: int) -> None:
    rng = random.Random(seed)
    plan = [None] * n_clean + [t for t in TELLS for _ in range(2)]
    rng.shuffle(plan)
    specs = [make_claim(i, t, rng) for i, t in enumerate(plan)]
    print(f"running {len(specs)} claims ({n_clean} clean, {len(specs) - n_clean} fraud), concurrency {concurrency}")
    sem = asyncio.Semaphore(concurrency)
    rows = await asyncio.gather(*(run_one(s, d, sem) for s, d in specs))
    summary = report(list(rows))
    write(summary, list(rows))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-clean", type=int, default=14)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--concurrency", type=int, default=3)
    a = ap.parse_args()
    asyncio.run(main(a.n_clean, a.seed, a.concurrency))
