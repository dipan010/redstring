"""Builds the Red String graph: claims and the entities they share.
Only entities shared by 2+ claims become nodes, so the graph shows connections, not noise."""

from collections import defaultdict

from .clients import db

ENTITY_KINDS = ("phone", "email", "bank", "vehicle", "garage", "invoice", "photo")


async def build_network(limit: int = 600) -> dict:
    claims: dict[str, dict] = {}
    async for snap in db().collection("claims").limit(limit).stream():
        d = snap.to_dict()
        if d.get("linkKeys"):
            claims[snap.id] = d

    holders: dict[str, list[str]] = defaultdict(list)
    labels: dict[str, str] = {}
    for cid, d in claims.items():
        for k in d.get("linkKeys", []):
            holders[k].append(cid)
        for e in d.get("entities") or []:
            labels[e["key"]] = e["label"]

    def risky(cid: str) -> bool:
        d = claims[cid]
        return bool(d.get("fraudConfirmed")) or ((d.get("risk") or {}).get("score") or 0) >= 60

    # Garages are shared by many honest customers; only draw them when they touch risky claims.
    shared = {k: cids for k, cids in holders.items()
              if len(cids) >= 2 and (not k.startswith("garage:") or sum(map(risky, cids)) >= 2)}
    linked_claims = {cid for cids in shared.values() for cid in cids}

    nodes = [
        {
            "id": cid,
            "type": "claim",
            "label": d.get("claimNumber"),
            "claimant": d.get("claimantName"),
            "score": (d.get("risk") or {}).get("score"),
            "fraudConfirmed": bool(d.get("fraudConfirmed")),
            "inQueue": bool(d.get("inQueue")),
        }
        for cid, d in claims.items()
        if cid in linked_claims
    ]
    nodes += [{"id": k, "type": k.split(":", 1)[0], "label": labels.get(k, k.split(":", 1)[1])} for k in shared]
    edges = [{"source": cid, "target": k, "kind": k.split(":", 1)[0]} for k, cids in shared.items() for cid in cids]
    return {"nodes": nodes, "edges": edges}
