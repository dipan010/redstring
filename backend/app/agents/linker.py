"""Linker agent: connects this claim to every other claim that shares an entity
(phone, email, bank account, vehicle, garage, invoice). These are the red strings."""

import asyncio
import hashlib
import re
from collections import defaultdict

from google.cloud.firestore_v1.base_query import FieldFilter

from ..clients import bucket, db
from ..rules import flag, names_match, norm
from ..schemas import Flag, ReaderOutput

ENTITY_LABELS = {
    "phone": "Phone",
    "email": "Email",
    "bank": "Bank account",
    "vehicle": "Vehicle",
    "garage": "Garage",
    "invoice": "Invoice no.",
    "photo": "Photo",
}


def entities(r: ReaderOutput) -> list[dict]:
    """Normalised entities -> stored on the claim and used as Firestore link keys."""
    out: list[dict] = []

    def add(kind: str, value: str | None, label: str | None = None) -> None:
        if value:
            key = f"{kind}:{value}"
            if all(e["key"] != key for e in out):
                out.append({"kind": kind, "key": key, "label": label or value})

    if r.claimant_phone:
        digits = re.sub(r"\D", "", r.claimant_phone)[-10:]
        add("phone", digits if len(digits) == 10 else None, r.claimant_phone)
    if r.claimant_email:
        add("email", r.claimant_email.strip().lower())
    if r.bank_account:
        add("bank", re.sub(r"\D", "", r.bank_account) or None, f"A/c ••{r.bank_account[-4:]}")
    if r.vehicle_registration:
        add("vehicle", norm(r.vehicle_registration).upper(), r.vehicle_registration)
    inv = r.invoice
    if inv:
        garage_id = norm(inv.garage_gstin).upper() or norm(inv.garage_name)
        add("garage", garage_id or None, inv.garage_name or inv.garage_gstin)
        if inv.number and garage_id:
            add("invoice", f"{garage_id}/{norm(inv.number).upper()}", f"{inv.garage_name or ''} #{inv.number}")
    return out


def _photo_hash(path: str) -> str:
    return hashlib.sha256(bucket().blob(path).download_as_bytes()).hexdigest()[:20]


async def photo_entities(documents: list[dict]) -> list[dict]:
    """Exact-duplicate detection for damage photos reused across claims."""
    photos = [(i, d) for i, d in enumerate(documents) if d["mime_type"].startswith("image/")]
    hashes = await asyncio.gather(*(asyncio.to_thread(_photo_hash, d["path"]) for _, d in photos))
    return [{"kind": "photo", "key": f"photo:{h}", "label": f"Photo doc:{i}"} for (i, _), h in zip(photos, hashes)]


async def run(claim_id: str, r: ReaderOutput, documents: list[dict], sample_pack: str | None = None
              ) -> tuple[list[dict], list[dict], list[Flag]]:
    ents = entities(r) + await photo_entities(documents)
    keys = [e["key"] for e in ents][:30]
    if not keys:
        return ents, [], []

    q = db().collection("claims").where(filter=FieldFilter("linkKeys", "array_contains_any", keys)).limit(200)
    shared: dict[str, list[str]] = defaultdict(list)  # other claim id -> shared keys
    others: dict[str, dict] = {}
    async for snap in q.stream():
        if snap.id == claim_id:
            continue
        d = snap.to_dict()
        if d.get("isBenchmark"):
            continue
        if sample_pack and d.get("samplePack") == sample_pack:
            continue  # another evaluator ran the same sample pack; not a real link
        others[snap.id] = d
        shared[snap.id] = sorted(set(keys) & set(d.get("linkKeys", [])))

    links = [
        {
            "claimId": cid,
            "claimNumber": others[cid].get("claimNumber"),
            "claimantName": others[cid].get("claimantName"),
            "riskScore": (others[cid].get("risk") or {}).get("score"),
            "fraudConfirmed": bool(others[cid].get("fraudConfirmed")),
            "shared": [{"key": k, "kind": k.split(":", 1)[0]} for k in ks],
        }
        for cid, ks in shared.items()
    ]

    flags: list[Flag] = []
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for link in links:
        for s in link["shared"]:
            by_kind[s["kind"]].append(link)

    def refs(ls: list[dict]) -> str:
        return ", ".join(sorted({l["claimNumber"] or l["claimId"] for l in ls})[:6])

    for kind in ("bank", "phone", "email"):
        foreign = [l for l in by_kind.get(kind, []) if not names_match(l["claimantName"], r.claimant_name)]
        if foreign:
            sev = "high" if kind == "bank" else "medium"
            flags.append(flag("linker", f"SHARED_{kind.upper()}", sev,
                              f"{ENTITY_LABELS[kind]} shared with {len(foreign)} other claimant(s)",
                              f"Same {ENTITY_LABELS[kind].lower()} appears on claims {refs(foreign)} "
                              f"filed by different people.", f"claims:{refs(foreign)}"))

    if by_kind.get("invoice"):
        flags.append(flag("linker", "DUPLICATE_INVOICE", "high", "Invoice already used in another claim",
                          f"The same garage invoice number appears on {refs(by_kind['invoice'])}.",
                          f"claims:{refs(by_kind['invoice'])}"))

    if by_kind.get("photo"):
        flags.append(flag("linker", "PHOTO_REUSED", "high", "Damage photo already used in another claim",
                          f"An identical photo was submitted with {refs(by_kind['photo'])}.",
                          f"claims:{refs(by_kind['photo'])}"))

    if len(by_kind.get("vehicle", [])) >= 2:
        flags.append(flag("linker", "REPEAT_VEHICLE", "medium", "Repeated claims on the same vehicle",
                          f"{len(by_kind['vehicle'])} other claims on this vehicle: {refs(by_kind['vehicle'])}."))

    garage_links = by_kind.get("garage", [])
    fraud_at_garage = [l for l in garage_links if l["fraudConfirmed"]]
    if fraud_at_garage:
        flags.append(flag("linker", "GARAGE_FRAUD_HISTORY", "high",
                          f"Garage linked to {len(fraud_at_garage)} confirmed fraud case(s)",
                          f"Confirmed fraud at this garage: {refs(fraud_at_garage)}.",
                          f"claims:{refs(fraud_at_garage)}"))

    # A ring: several claims that share the garage AND a personal identifier.
    ring = [l for l in links if {"garage"} & {s["kind"] for s in l["shared"]}
            and {"bank", "phone", "email"} & {s["kind"] for s in l["shared"]}]
    if len(ring) >= 2:
        flags.append(flag("linker", "POSSIBLE_RING", "high", f"Possible fraud ring ({len(ring) + 1} claims)",
                          f"This claim shares a garage and personal identifiers with {refs(ring)}.",
                          f"claims:{refs(ring)}"))
    return ents, links, flags
