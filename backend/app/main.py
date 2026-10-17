"""Redstring API (Cloud Run). Served behind Firebase Hosting at /api/**."""

import json
import logging
import time
from collections import defaultdict, deque

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from firebase_admin import auth as fb_auth
from google.cloud import firestore

from .agents.verdict import ACTION_LABEL
from .clients import db, firebase_app
from .config import get_settings
from .llm import generate_text
from .network import build_network
from .pipeline import initial_stages, run_pipeline
from .rules import action_for, band, risk_score
from .schemas import (
    ChatRequest,
    CreateClaimRequest,
    DecisionRequest,
    DraftRequest,
    Flag,
    FlagFeedbackRequest,
)

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Redstring API", docs_url="/api/docs", openapi_url="/api/openapi.json")


# ---------- auth & limits ----------


async def current_user(authorization: str = Header(default="")) -> str:
    if get_settings().auth_disabled:
        return "local-dev"
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    try:
        decoded = await run_in_threadpool(fb_auth.verify_id_token, authorization[7:], firebase_app())
    except Exception:
        raise HTTPException(401, "Invalid token")
    return decoded["uid"]


_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(bucket: str, uid: str, per_hour: int) -> None:
    q, now = _hits[f"{bucket}:{uid}"], time.time()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= per_hour:
        raise HTTPException(429, "Rate limit reached for this demo account. Please try again later.")
    q.append(now)


async def get_claim(claim_id: str) -> tuple[firestore.AsyncDocumentReference, dict]:
    ref = db().collection("claims").document(claim_id)
    snap = await ref.get()
    if not snap.exists:
        raise HTTPException(404, "Claim not found")
    return ref, snap.to_dict()


@firestore.async_transactional
async def _next_number(tx, ref) -> int:
    snap = await ref.get(transaction=tx)
    n = (snap.to_dict() or {}).get("claims", 1000) + 1 if snap.exists else 1001
    tx.set(ref, {"claims": n}, merge=True)
    return n


# ---------- routes ----------


@app.get("/api/health")
async def health():
    return {"ok": True, "model": get_settings().gemini_model}


@app.post("/api/claims")
async def create_claim(body: CreateClaimRequest, bg: BackgroundTasks, uid: str = Depends(current_user)):
    rate_limit("claims", uid, get_settings().claims_per_user_per_hour)
    for d in body.documents:
        if not d.path.startswith(f"uploads/{uid}/"):
            raise HTTPException(400, "Documents must be uploaded to your own folder")
    n = await _next_number(db().transaction(), db().collection("meta").document("counters"))
    ref = db().collection("claims").document()
    await ref.set({
        "claimNumber": f"RS-{n}",
        "status": "queued",
        "inQueue": True,
        "isDemo": False,
        "createdBy": uid,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "documents": [d.model_dump() for d in body.documents],
        "note": body.note,
        "samplePack": body.sample_pack,
        "stages": initial_stages(),
        "flags": [],
        "linkKeys": [],
    })
    bg.add_task(run_pipeline, ref.id)
    return {"id": ref.id, "claimNumber": f"RS-{n}"}


@app.post("/api/claims/{claim_id}/rerun")
async def rerun(claim_id: str, bg: BackgroundTasks, uid: str = Depends(current_user)):
    rate_limit("claims", uid, get_settings().claims_per_user_per_hour)
    ref, claim = await get_claim(claim_id)
    if claim.get("status") in ("queued", "processing"):
        raise HTTPException(409, "Claim is already being processed")
    bg.add_task(run_pipeline, claim_id)
    return {"ok": True}


async def _rescore(ref, claim: dict, flags: list[dict]) -> dict:
    parsed = [Flag.model_validate(f) for f in flags]
    score = risk_score(parsed)
    missing = ((claim.get("policy") or {}).get("assessment") or {}).get("missing_documents") or []
    action = action_for(score, missing)
    risk = {**(claim.get("risk") or {}), "score": score, "band": band(score), "action": action,
            "actionLabel": ACTION_LABEL[action]}
    await ref.update({"flags": flags, "risk": risk})
    return risk


@app.post("/api/claims/{claim_id}/flags/{flag_id}")
async def flag_feedback(claim_id: str, flag_id: str, body: FlagFeedbackRequest, uid: str = Depends(current_user)):
    ref, claim = await get_claim(claim_id)
    flags = claim.get("flags", [])
    for f in flags:
        if f["id"] == flag_id:
            f["status"] = body.status
            f["reviewedBy"] = uid
            break
    else:
        raise HTTPException(404, "Flag not found")
    risk = await _rescore(ref, claim, flags)
    await ref.collection("audit").add({"type": "flag", "flagId": flag_id, "status": body.status, "by": uid,
                                       "at": firestore.SERVER_TIMESTAMP})
    return {"risk": risk}


@app.post("/api/claims/{claim_id}/decision")
async def decision(claim_id: str, body: DecisionRequest, uid: str = Depends(current_user)):
    ref, _ = await get_claim(claim_id)
    d = {"action": body.action, "note": body.note, "by": uid, "at": firestore.SERVER_TIMESTAMP}
    await ref.update({"decision": d})
    await ref.collection("audit").add({"type": "decision", **d})
    return {"ok": True}


CHAT_SYSTEM = """You are Redstring, an assistant for insurance claim adjusters. Answer questions
about the claim using only the claim record provided (extracted fields, policy assessment,
flags with evidence, linked claims, risk score). Cite flags and policy clause numbers. If the
record doesn't contain the answer, say so. Be concise. Never state that the claimant committed
fraud; describe risk and evidence."""


def _claim_context(claim: dict) -> str:
    keep = {k: claim.get(k) for k in ("claimNumber", "extracted", "policy", "flags", "links", "risk", "verdict",
                                      "decision")}
    return json.dumps(keep, default=str)


@app.post("/api/claims/{claim_id}/chat")
async def chat(claim_id: str, body: ChatRequest, uid: str = Depends(current_user)):
    rate_limit("chat", uid, get_settings().chat_per_user_per_hour)
    ref, claim = await get_claim(claim_id)
    msgs = ref.collection("chats").document(uid).collection("messages")
    recent = msgs.order_by("at", direction=firestore.Query.DESCENDING).limit(20)
    history = [s.to_dict() async for s in recent.stream()][::-1]
    contents = ["CLAIM RECORD:\n" + _claim_context(claim)]
    for m in history:
        contents.append(f"{m['role'].upper()}: {m['text']}")
    contents.append(f"USER: {body.message}")
    await msgs.add({"role": "user", "text": body.message, "at": firestore.SERVER_TIMESTAMP})
    try:
        answer = await generate_text(contents, CHAT_SYSTEM)
    except Exception:
        answer = "Sorry, I couldn't reach the model just now. Please try again in a moment."
    await msgs.add({"role": "assistant", "text": answer, "at": firestore.SERVER_TIMESTAMP})
    return {"answer": answer}


DRAFT_PROMPTS = {
    "request_info": "Draft a polite email to the claimant requesting the missing documents and clarifications "
                    "needed to process the claim. Don't mention suspected fraud.",
    "investigation_referral": "Draft an internal referral memo to the Special Investigation Unit summarising the "
                              "risk flags, linked claims and evidence, with recommended checks.",
    "approval": "Draft an email to the claimant confirming the claim is approved, with the estimated payable "
                "amount and deductible.",
}


@app.post("/api/claims/{claim_id}/draft")
async def draft(claim_id: str, body: DraftRequest, uid: str = Depends(current_user)):
    rate_limit("chat", uid, get_settings().chat_per_user_per_hour)
    _, claim = await get_claim(claim_id)
    text = await generate_text(
        ["CLAIM RECORD:\n" + _claim_context(claim), DRAFT_PROMPTS[body.kind] +
         " Sign off as 'Claims Team, Redstring Demo General Insurance'. Plain text, no markdown."],
        "You write clear, professional insurance correspondence.",
    )
    return {"text": text}


@app.get("/api/network")
async def network(uid: str = Depends(current_user)):
    return await build_network()
