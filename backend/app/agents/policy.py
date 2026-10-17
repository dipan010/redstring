"""Policy agent: checks the claim against the policy schedule (rules) and the
policy wording (Gemini, long-context), citing clause numbers."""

import json
from functools import lru_cache
from pathlib import Path

from ..clients import db
from ..llm import generate_json
from ..rules import norm, policy_rules
from ..schemas import Flag, PolicyOutput, ReaderOutput

WORDING_DIR = Path(__file__).resolve().parent.parent / "policies"

SYSTEM = """You are the Policy agent at an Indian motor insurer. Using ONLY the policy wording
and schedule provided, decide whether the claim is covered, which exclusions apply, the
deductible, an estimated payable amount (apply deductible and depreciation where the invoice
allows), and which required documents are missing. Cite clause numbers and quote the wording
exactly. Do not invent clauses."""


@lru_cache
def wording(product: str) -> str:
    path = WORDING_DIR / f"{product}.md"
    return path.read_text() if path.exists() else (WORDING_DIR / "private_car_package.md").read_text()


async def find_policy(policy_number: str | None) -> dict | None:
    if not policy_number:
        return None
    snap = await db().collection("policies").document(norm(policy_number).upper()).get()
    return snap.to_dict() if snap.exists else None


async def run(r: ReaderOutput) -> tuple[PolicyOutput | None, list[Flag], dict | None]:
    policy = await find_policy(r.policy_number)
    flags = policy_rules(r, policy)
    if policy is None:
        return None, flags, None

    out = await generate_json(
        [
            "POLICY WORDING:\n" + wording(policy.get("product", "private_car_package")),
            "POLICY SCHEDULE:\n" + json.dumps(policy, default=str, indent=2),
            "CLAIM (extracted):\n" + r.model_dump_json(indent=2),
            "Assess coverage for this claim.",
        ],
        PolicyOutput,
        SYSTEM,
    )
    for c in out.exclusions_triggered:
        flags.append(Flag(id=f"EXCLUSION_{c.clause_id}", agent="policy", code="EXCLUSION", severity="high",
                          title=f"Exclusion {c.clause_id}: {c.title}", evidence=f"“{c.quote}” — {c.reason}",
                          source=f"clause:{c.clause_id}"))
    if out.missing_documents:
        flags.append(Flag(id="MISSING_DOCS", agent="policy", code="MISSING_DOCS", severity="low",
                          title="Required documents missing", evidence=", ".join(out.missing_documents),
                          source="clause:6.2"))
    return out, flags, policy
