"""End-to-end check of the deployed app, as an anonymous demo user would use it.

    uv run python scripts/e2e.py [--submit]    # --submit also uploads the live-ring sample pack
"""

import json
import re
import sys
import time
from pathlib import Path

import httpx

BASE = "https://redstring-511910.web.app"
API = __import__("os").environ.get("API_BASE", BASE)  # e.g. a tagged Cloud Run revision
ENV = Path(__file__).resolve().parents[2] / "frontend" / ".env.local"
KEY = re.search(r"VITE_FIREBASE_API_KEY=(\S+)", ENV.read_text()).group(1)
BUCKET = "redstring-511910.firebasestorage.app"
REF = {"Referer": BASE + "/"}


def main(submit: bool, pack_id: str = "live-ring") -> None:
    c = httpx.Client(timeout=90)
    auth = c.post(f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={KEY}", headers=REF,
                  json={"returnSecureToken": True}).json()
    token, uid = auth["idToken"], auth["localId"]
    H = {"Authorization": f"Bearer {token}"}
    print("signed in anonymously:", uid)

    print("health:", c.get(f"{BASE}/api/health").json())
    net = c.get(f"{BASE}/api/network", headers=H).json()
    kinds = {}
    for n in net["nodes"]:
        kinds[n["type"]] = kinds.get(n["type"], 0) + 1
    print("network nodes:", kinds, "edges:", len(net["edges"]))

    t = time.time()
    r = c.post(f"{BASE}/api/claims/demo-ring-3/chat", headers=H, json={"message": "Why is this claim flagged? Be brief."})
    print(f"chat ({time.time() - t:.1f}s):", r.status_code, r.json().get("answer", r.text)[:400])

    if not submit:
        return
    manifest = c.get(f"{BASE}/samples/manifest.json").json()
    pack = next(p for p in manifest if p["id"] == pack_id)
    docs = []
    for f in pack["files"]:
        data = c.get(f"{BASE}/samples/{pack['id']}/{f}").content
        mime = "application/pdf" if f.endswith(".pdf") else "image/jpeg"
        path = f"uploads/{uid}/e2e/{f}"
        up = c.post(f"https://firebasestorage.googleapis.com/v0/b/{BUCKET}/o", params={"name": path},
                    headers={**H, "Content-Type": mime}, content=data)
        assert up.status_code == 200, up.text
        docs.append({"path": path, "name": f, "mime_type": mime})
    t = time.time()
    created = c.post(f"{API}/api/claims", headers=H, json={"documents": docs, "sample_pack": pack_id, "note": "redstring-selftest"}).json()
    print("submitted:", created)

    # poll via Firestore REST (same data the UI streams with onSnapshot)
    url = f"https://firestore.googleapis.com/v1/projects/redstring-511910/databases/(default)/documents/claims/{created['id']}"
    while time.time() - t < 240:
        doc = c.get(url, headers=H).json()["fields"]
        stages = {k: v["mapValue"]["fields"]["status"]["stringValue"]
                  for k, v in doc["stages"]["mapValue"]["fields"].items()}
        status = doc["status"]["stringValue"]
        print(f"  {time.time() - t:5.1f}s {status:10} {stages}")
        if status in ("ready", "error"):
            break
        time.sleep(4)
    if status == "ready":
        risk = doc["risk"]["mapValue"]["fields"]
        print("risk:", risk["score"].get("integerValue"), risk["actionLabel"]["stringValue"])
        for f in doc["flags"]["arrayValue"].get("values", []):
            ff = f["mapValue"]["fields"]
            print(f"  [{ff['severity']['stringValue']}] {ff['code']['stringValue']}: {ff['title']['stringValue']}")
    else:
        print(json.dumps(doc.get("error"), indent=1))


if __name__ == "__main__":
    main("--submit" in sys.argv, next((a for a in sys.argv[1:] if a.startswith("live-")), "live-ring"))
