"""Submit sample packs to a Cloud Run revision (e.g. the hidden staging tag) and report results.

    API_BASE=https://lines---redstring-api-....run.app uv run python scripts/stage_test.py live-clean live-health-ring
"""
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "frontend" / "public" / "samples"
KEY = re.search(r"VITE_FIREBASE_API_KEY=(\S+)", (ROOT / "frontend" / ".env.local").read_text()).group(1)
SITE = "https://redstring-511910.web.app"
API = os.environ.get("API_BASE", SITE)
BUCKET = "redstring-511910.firebasestorage.app"
PACKS = {p["id"]: p for f in ("manifest.json", "manifest-lines.json") for p in json.loads((SAMPLES / f).read_text())}


def run(pack_id: str) -> str:
    c = httpx.Client(timeout=120)
    a = c.post(f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={KEY}", headers={"Referer": SITE + "/"},
               json={"returnSecureToken": True}).json()
    H, uid = {"Authorization": f"Bearer {a['idToken']}"}, a["localId"]
    p = PACKS[pack_id]
    docs = []
    for f in p["files"]:
        mime = "application/pdf" if f.endswith(".pdf") else "image/jpeg"
        path = f"uploads/{uid}/{pack_id}/{f}"
        r = c.post(f"https://firebasestorage.googleapis.com/v0/b/{BUCKET}/o", params={"name": path},
                   headers={**H, "Content-Type": mime}, content=(SAMPLES / pack_id / f).read_bytes())
        r.raise_for_status()
        docs.append({"path": path, "name": f, "mime_type": mime})
    created = c.post(f"{API}/api/claims", headers=H, json={"documents": docs, "sample_pack": pack_id, "note": "redstring-selftest",
                                                          "line_of_business": p.get("line", "motor")}).json()
    url = f"https://firestore.googleapis.com/v1/projects/redstring-511910/databases/(default)/documents/claims/{created['id']}"
    t = time.time()
    while time.time() - t < 240:
        d = c.get(url, headers=H).json()["fields"]
        if d["status"]["stringValue"] in ("ready", "error"):
            break
        time.sleep(4)
    if d["status"]["stringValue"] != "ready":
        return f"{pack_id}: {d['status']['stringValue']} {d.get('error')}"
    risk = d["risk"]["mapValue"]["fields"]
    flags = [f["mapValue"]["fields"]["code"]["stringValue"] for f in d["flags"]["arrayValue"].get("values", [])]
    staged = d.get("staged", {}).get("booleanValue")
    return (f"{pack_id:20} {created['claimNumber']} {time.time() - t:4.0f}s risk={risk['score'].get('integerValue'):>3} "
            f"{risk['action']['stringValue']:12} staged={staged} flags={flags}")


if __name__ == "__main__":
    with ThreadPoolExecutor(4) as ex:
        for line in ex.map(run, sys.argv[1:]):
            print(line)
