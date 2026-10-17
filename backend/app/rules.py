"""Deterministic checks. These are cheap, reproducible and easy to audit; Gemini
covers what rules can't (photos, narrative, document plausibility)."""

import math
import re
from datetime import date

from .schemas import Flag, ReaderOutput

SEVERITY_POINTS = {"low": 6, "medium": 15, "high": 30}
SCORE_SCALE = 60  # evidence points at which the score reaches ~63; each extra flag adds a little less
MEDIUM_AT, HIGH_AT = 20, 60


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def name_tokens(s: str | None) -> set[str]:
    return {t for t in re.split(r"[^a-z]+", (s or "").lower()) if len(t) > 1}


def names_match(a: str | None, b: str | None) -> bool:
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return True  # nothing to compare
    return len(ta & tb) >= min(len(ta), len(tb)) / 2


def plates_match(a: str | None, b: str | None) -> bool:
    """Registration numbers often carry extra text ('MH 02 FA 1187 · Hyundai i20')."""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return True
    return na in nb or nb in na


def flag(agent: str, code: str, severity: str, title: str, evidence: str, source: str | None = None) -> Flag:
    return Flag(id=code, agent=agent, code=code, severity=severity, title=title, evidence=evidence, source=source)  # type: ignore[arg-type]


def policy_rules(r: ReaderOutput, policy: dict | None) -> list[Flag]:
    out: list[Flag] = []
    if policy is None:
        out.append(flag("policy", "POLICY_NOT_FOUND", "high", "Policy number not found",
                        f"No active policy matches '{r.policy_number or 'none'}'."))
        return out

    incident = parse_date(r.incident_date)
    start, end = parse_date(policy.get("startDate")), parse_date(policy.get("endDate"))
    if incident and start and end:
        if not (start <= incident <= end):
            out.append(flag("policy", "INCIDENT_OUTSIDE_PERIOD", "high", "Incident date outside policy period",
                            f"Incident {incident} vs policy period {start} to {end}.", "clause:4.7"))
        elif (incident - start).days <= 30:
            out.append(flag("policy", "EARLY_CLAIM", "medium", "Claim within 30 days of policy start",
                            f"Policy began {start}; incident on {incident} ({(incident - start).days} days later).",
                            "clause:6.5"))
    if policy.get("breakIn"):
        out.append(flag("policy", "BREAK_IN_POLICY", "low", "Policy issued after a break in insurance",
                        "Schedule marks this policy as a break-in renewal.", "clause:6.5"))

    if r.vehicle_registration and policy.get("vehicleRegistration") and \
            not plates_match(r.vehicle_registration, policy["vehicleRegistration"]):
        out.append(flag("policy", "VEHICLE_MISMATCH", "high", "Vehicle not the insured vehicle",
                        f"Claim is for {r.vehicle_registration}; policy covers {policy['vehicleRegistration']}.",
                        "clause:1.4"))
    if not names_match(r.claimant_name, policy.get("holderName")):
        out.append(flag("policy", "HOLDER_MISMATCH", "medium", "Claimant is not the policyholder",
                        f"Claimant '{r.claimant_name}' vs policyholder '{policy.get('holderName')}'."))
    idv = policy.get("idv")
    if idv and r.claim_amount and r.claim_amount > idv:
        out.append(flag("policy", "EXCEEDS_IDV", "high", "Claim exceeds insured value",
                        f"Claimed ₹{r.claim_amount:,.0f} vs IDV ₹{idv:,.0f}.", "clause:2.2"))
    return out


def document_rules(r: ReaderOutput) -> list[Flag]:
    out: list[Flag] = []
    inv = r.invoice
    incident, filed = parse_date(r.incident_date), parse_date(r.filed_date)

    if incident and filed and (filed - incident).days > 2:
        out.append(flag("forensics", "LATE_INTIMATION", "low", "Claim reported late",
                        f"Incident {incident}, claim filed {filed} ({(filed - incident).days} days; policy requires 48 hours).",
                        "clause:6.1"))

    if inv is None:
        return out

    inv_date = parse_date(inv.date)
    if inv_date and incident and inv_date < incident:
        out.append(flag("forensics", "INVOICE_BEFORE_INCIDENT", "high", "Repair invoice dated before the incident",
                        f"Invoice {inv.number or ''} dated {inv_date}, incident on {incident}.", "clause:6.6"))

    if inv.line_items and inv.subtotal:
        s = sum(li.amount for li in inv.line_items)
        if abs(s - inv.subtotal) > max(10, 0.01 * inv.subtotal):
            out.append(flag("forensics", "INVOICE_ARITHMETIC", "high", "Invoice line items don't add up",
                            f"Line items sum to ₹{s:,.0f} but subtotal shows ₹{inv.subtotal:,.0f}."))
    if inv.subtotal and inv.total:
        expected = inv.subtotal + (inv.tax or 0)
        if abs(expected - inv.total) > max(10, 0.01 * inv.total):
            out.append(flag("forensics", "INVOICE_TOTAL", "medium", "Invoice total inconsistent with subtotal + tax",
                            f"Subtotal ₹{inv.subtotal:,.0f} + tax ₹{inv.tax or 0:,.0f} ≠ total ₹{inv.total:,.0f}."))
    if inv.total and r.claim_amount and r.claim_amount > inv.total * 1.05:
        over = r.claim_amount / inv.total - 1
        out.append(flag("forensics", "CLAIM_ABOVE_INVOICE", "high" if over > 0.2 else "medium",
                        "Amount claimed is higher than the invoice",
                        f"Claimed ₹{r.claim_amount:,.0f} vs invoice total ₹{inv.total:,.0f} ({over:.0%} more)."))
    if inv.name_on_invoice and not names_match(inv.name_on_invoice, r.claimant_name):
        out.append(flag("forensics", "INVOICE_NAME_MISMATCH", "medium", "Invoice issued to a different person",
                        f"Invoice name '{inv.name_on_invoice}' vs claimant '{r.claimant_name}'.", "clause:6.6"))
    if inv.vehicle_on_invoice and r.vehicle_registration and \
            not plates_match(inv.vehicle_on_invoice, r.vehicle_registration):
        out.append(flag("forensics", "INVOICE_VEHICLE_MISMATCH", "high", "Invoice is for a different vehicle",
                        f"Invoice vehicle {inv.vehicle_on_invoice} vs claimed vehicle {r.vehicle_registration}.",
                        "clause:6.6"))
    return out


def risk_score(flags: list[Flag]) -> int:
    active = [f for f in flags if f.status != "dismissed"]
    pts = sum(SEVERITY_POINTS[f.severity] for f in active)
    # confirmed flags weigh more: an adjuster has verified them
    pts += sum(SEVERITY_POINTS[f.severity] // 2 for f in active if f.status == "confirmed")
    # Diminishing returns: more evidence always raises the score, but it only nears 100 when overwhelming.
    return round(100 * (1 - math.exp(-pts / SCORE_SCALE)))


def band(score: int) -> str:
    return "high" if score >= HIGH_AT else "medium" if score >= MEDIUM_AT else "low"


def action_for(score: int, missing_docs: list[str]) -> str:
    if score >= HIGH_AT:
        return "investigate"
    if score >= MEDIUM_AT or missing_docs:
        return "request_info"
    return "fast_track"
