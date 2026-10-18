"""Property (home) claims: fire, flood, water damage, burglary, storm."""

import re
from typing import Optional

from pydantic import BaseModel, Field

from ..rules import flag, names_match, norm, parse_date
from ..schemas import Flag, LineItem, PhotoObservation
from .common import LineSpec


class PropertyDoc(BaseModel):
    index: int
    kind: str = Field(description="claim_form, contractor_invoice, contractor_estimate, police_report, "
                                  "fire_report, damage_photo, purchase_receipt or other")
    summary: str


class PropertyReaderOutput(BaseModel):
    documents: list[PropertyDoc]
    claimant_name: Optional[str]
    claimant_phone: Optional[str]
    claimant_email: Optional[str]
    bank_account: Optional[str]
    bank_ifsc: Optional[str]
    policy_number: Optional[str]
    property_address: Optional[str] = Field(description="Address where the loss happened")
    incident_type: Optional[str] = Field(description="fire, flood, water_damage, burglary, storm, malicious_damage or other")
    incident_date: Optional[str] = Field(description="YYYY-MM-DD")
    incident_description: Optional[str]
    damaged_items: list[str] = Field(description="Rooms, structures or contents the claimant says were damaged or stolen")
    police_report_number: Optional[str]
    contractor_name: Optional[str]
    contractor_gstin: Optional[str]
    invoice_number: Optional[str]
    invoice_date: Optional[str] = Field(description="YYYY-MM-DD")
    work_address: Optional[str] = Field(description="Site address printed on the contractor invoice")
    invoice_line_items: list[LineItem]
    invoice_subtotal: Optional[float]
    invoice_total: Optional[float]
    claim_amount: Optional[float] = Field(description="Amount claimed in INR")
    filed_date: Optional[str] = Field(description="YYYY-MM-DD")
    photo_observations: list[PhotoObservation]


READER_SYSTEM = """You are the Reader agent at an Indian home insurer. You receive a property claim:
claim form, contractor estimate or invoice, police or fire report, purchase receipts and damage photos.
Extract the requested fields exactly as they appear. Use null when a value is absent; do not guess.
Indian documents write dates as DD/MM/YYYY (04/10/2026 is 4 October 2026); return YYYY-MM-DD without
swapping day and month. Amounts are INR numbers without symbols or commas. For each photo, describe only
what is visibly damaged (in damage_areas_visible) and anything unusual in notes (old damage, staging,
a different property). Leave vehicle_colour null."""

POLICY_SYSTEM = """You are the Policy agent at an Indian home insurer. Using ONLY the policy wording and
schedule provided, decide whether the loss is covered, which exclusions apply, the deductible, an
estimated payable amount, and which required documents are missing (for example a police report for
burglary). Cite clause numbers and quote the wording exactly. Do not invent clauses. Do not apply the
fraud clause or judge honesty: other agents assess inconsistencies and a human adjuster decides."""

FORENSICS_SYSTEM = """You are the Forensics agent in a property-insurance Special Investigation Unit in India.
Look for evidence that a claim is inconsistent or manipulated:
1. Do the photos show the damage described (e.g. a fire claim with no soot or charring, water damage
   with dry walls, burglary with no forced entry)?
2. Signs of old or gradual damage (long-term damp, rot, rust) presented as a sudden incident.
3. Contractor invoice items unrelated to the described damage, or prices far above typical Indian rates.
4. The invoice site address differing from the insured property, or documents showing signs of editing.
Report only findings supported by specific evidence. Return an empty list if the claim looks clean.
Do not repeat simple arithmetic or date checks; those are handled separately."""

THEFT = ("burglary", "theft", "malicious")


def _addr(s: str | None) -> str:
    return norm(s)[:40]


def policy_rules(r: PropertyReaderOutput, policy: dict | None) -> list[Flag]:
    out: list[Flag] = []
    if policy is None:
        out.append(flag("policy", "POLICY_NOT_FOUND", "high", "Policy number not found",
                        f"No active policy matches '{r.policy_number or 'none'}'."))
        return out
    inc = parse_date(r.incident_date)
    start, end = parse_date(policy.get("startDate")), parse_date(policy.get("endDate"))
    if inc and start and end:
        if not (start <= inc <= end):
            out.append(flag("policy", "INCIDENT_OUTSIDE_PERIOD", "high", "Incident outside the policy period",
                            f"Incident {inc}; policy period {start} to {end}.", "clause:4.4"))
        else:
            inception = parse_date(policy.get("inceptionDate")) or start
            if (inc - inception).days <= 30:
                out.append(flag("policy", "EARLY_CLAIM", "medium", "Claim within 30 days of policy inception",
                                f"Cover began {inception}; incident {(inc - inception).days} days later.", "clause:5.4"))
    if not names_match(r.claimant_name, policy.get("holderName")):
        out.append(flag("policy", "HOLDER_MISMATCH", "medium", "Claimant is not the policyholder",
                        f"Claimant '{r.claimant_name}' vs policyholder '{policy.get('holderName')}'."))
    insured = policy.get("propertyAddress")
    if insured and r.property_address and _addr(insured)[:20] not in _addr(r.property_address) \
            and _addr(r.property_address)[:20] not in _addr(insured):
        out.append(flag("policy", "ADDRESS_MISMATCH", "high", "Loss address is not the insured property",
                        f"Loss at '{r.property_address}'; insured property is '{insured}'.", "clause:4.5"))
    si = (policy.get("sumInsuredBuilding") or 0) + (policy.get("sumInsuredContents") or 0)
    if si and r.claim_amount and r.claim_amount > si:
        out.append(flag("policy", "EXCEEDS_SUM_INSURED", "high", "Claim exceeds the sum insured",
                        f"Claimed ₹{r.claim_amount:,.0f} vs total sum insured ₹{si:,.0f}."))
    if (r.incident_type or "").lower() in THEFT and not r.police_report_number:
        out.append(flag("policy", "NO_POLICE_REPORT", "high", "No police report for a burglary claim",
                        "A police report (FIR) is mandatory for burglary, theft and malicious damage.", "clause:5.3"))
    return out


def doc_rules(r: PropertyReaderOutput) -> list[Flag]:
    out: list[Flag] = []
    inc, inv, filed = (parse_date(x) for x in (r.incident_date, r.invoice_date, r.filed_date))
    if inv and inc and inv < inc:
        out.append(flag("forensics", "INVOICE_BEFORE_INCIDENT", "high", "Contractor invoice dated before the incident",
                        f"Invoice {r.invoice_number or ''} dated {inv}, incident on {inc}.", "clause:5.5"))
    if r.invoice_line_items and r.invoice_subtotal:
        s = sum(li.amount for li in r.invoice_line_items)
        if abs(s - r.invoice_subtotal) > max(10, 0.01 * r.invoice_subtotal):
            out.append(flag("forensics", "INVOICE_ARITHMETIC", "high", "Invoice line items don't add up",
                            f"Line items sum to ₹{s:,.0f} but the subtotal shows ₹{r.invoice_subtotal:,.0f}."))
    if r.invoice_total and r.claim_amount and r.claim_amount > r.invoice_total * 1.05:
        over = r.claim_amount / r.invoice_total - 1
        out.append(flag("forensics", "CLAIM_ABOVE_INVOICE", "high" if over > 0.2 else "medium",
                        "Amount claimed is higher than the invoice",
                        f"Claimed ₹{r.claim_amount:,.0f} vs invoice ₹{r.invoice_total:,.0f} ({over:.0%} more)."))
    if r.work_address and r.property_address and _addr(r.work_address)[:20] not in _addr(r.property_address) \
            and _addr(r.property_address)[:20] not in _addr(r.work_address):
        out.append(flag("forensics", "INVOICE_SITE_MISMATCH", "high", "Invoice is for work at a different address",
                        f"Invoice site '{r.work_address}' vs loss address '{r.property_address}'.", "clause:5.5"))
    if inc and filed and (filed - inc).days > 7:
        out.append(flag("forensics", "LATE_INTIMATION", "low", "Claim reported late",
                        f"Incident {inc}, claim filed {filed} ({(filed - inc).days} days; policy requires 7).", "clause:5.1"))
    return out


def entities(r: PropertyReaderOutput) -> list[dict]:
    out: list[dict] = []

    def add(kind, value, label=None):
        if value and all(e["key"] != f"{kind}:{value}" for e in out):
            out.append({"kind": kind, "key": f"{kind}:{value}", "label": label or value})

    if r.claimant_phone:
        d = re.sub(r"\D", "", r.claimant_phone)[-10:]
        add("phone", d if len(d) == 10 else None, r.claimant_phone)
    if r.claimant_email:
        add("email", r.claimant_email.strip().lower())
    if r.bank_account:
        add("bank", re.sub(r"\D", "", r.bank_account) or None, f"A/c ••{r.bank_account[-4:]}")
    con = norm(r.contractor_gstin).upper() or norm(r.contractor_name)
    add("contractor", con or None, r.contractor_name or r.contractor_gstin)
    if r.invoice_number and con:
        add("invoice", f"{con}/{norm(r.invoice_number).upper()}", f"{r.contractor_name or ''} #{r.invoice_number}")
    if r.property_address:
        add("address", _addr(r.property_address) or None, r.property_address)
    return out


def summary(r: PropertyReaderOutput) -> dict:
    kind = (r.incident_type or "loss").replace("_", " ")
    return {"claimantName": r.claimant_name, "claimAmount": r.claim_amount, "incidentDate": r.incident_date,
            "subject": f"{kind.capitalize()} · {(r.property_address or '').split(',')[-1].strip() or 'home'}",
            "providerName": r.contractor_name}


SPEC = LineSpec(key="property", reader_schema=PropertyReaderOutput, reader_system=READER_SYSTEM,
                policy_system=POLICY_SYSTEM, forensics_system=FORENSICS_SYSTEM, policy_rules=policy_rules,
                doc_rules=doc_rules, entities=entities, summary=summary,
                provider_kinds=("contractor",), bill_kind="invoice")
