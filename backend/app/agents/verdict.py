"""Verdict agent: a reproducible risk score from the flags, plus a Gemini-written
explanation an adjuster (or auditor) can read in ten seconds."""

import json

from ..config import get_settings
from ..llm import generate_json
from ..rules import action_for, band, risk_score
from ..schemas import Flag, PolicyOutput, ReaderOutput, VerdictOutput

SYSTEM = """You are the Verdict agent for a motor-insurance claims team. Summarise the evidence
for a human adjuster. Be factual and specific, refer to flags by their evidence, and never
accuse the claimant of fraud: describe risk and what to verify. The score and recommended
action are already computed; explain them, don't change them. Never say the claim is approved,
denied or rejected: the adjuster makes that decision."""

ACTION_LABEL = {
    "fast_track": "Fast-track for settlement",
    "request_info": "Request more information",
    "investigate": "Refer to Special Investigation Unit",
}


async def run(r: ReaderOutput, policy: PolicyOutput | None, flags: list[Flag]) -> tuple[dict, VerdictOutput]:
    score = risk_score(flags)
    missing = policy.missing_documents if policy else []
    action = action_for(score, missing)
    risk = {"score": score, "band": band(score), "action": action, "actionLabel": ACTION_LABEL[action]}
    try:
        v = await generate_json(
            [
                "CLAIM:\n" + r.model_dump_json(),
                "POLICY ASSESSMENT:\n" + (policy.model_dump_json() if policy else "Policy not found"),
                "FLAGS:\n" + json.dumps([f.model_dump() for f in flags if f.status != "dismissed"]),
                f"RISK SCORE: {score}/100 ({risk['band']}). RECOMMENDED ACTION: {ACTION_LABEL[action]}.",
            ],
            VerdictOutput,
            SYSTEM,
            temperature=0.2,
            model=get_settings().verdict_model,
        )
    except RuntimeError:
        top = sorted(flags, key=lambda f: -{"high": 3, "medium": 2, "low": 1}[f.severity])[:4]
        v = VerdictOutput(
            summary=f"Risk score {score}/100. {ACTION_LABEL[action]}.",
            key_reasons=[f.title for f in top] or ["No inconsistencies found."],
            next_steps=[ACTION_LABEL[action]],
        )
    return risk, v
