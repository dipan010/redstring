"""Health insurance (hospitalisation reimbursement) claims."""

import re
from typing import Optional

from pydantic import BaseModel, Field

from ..rules import flag, names_match, norm, parse_date
from ..schemas import Flag, LineItem
from .common import LineSpec


class HealthDoc(BaseModel):
    index: int
    kind: str = Field(description="claim_form, hospital_bill, discharge_summary, prescription, pharmacy_bill, "
                                  "lab_report, id_proof or other")
    summary: str


class HealthReaderOutput(BaseModel):
    documents: list[HealthDoc]
    claimant_name: Optional[str] = Field(description="Policyholder filing the claim")
    patient_name: Optional[str]
    patient_age: Optional[int]
    relationship_to_policyholder: Optional[str]
    claimant_phone: Optional[str]
    claimant_email: Optional[str]
    bank_account: Optional[str]
    bank_ifsc: Optional[str]
    policy_number: Optional[str]
    hospital_name: Optional[str]
    hospital_registration: Optional[str] = Field(description="Hospital registration or ROHINI ID")
    hospital_city: Optional[str]
    treating_doctor: Optional[str]
    doctor_registration: Optional[str] = Field(description="Medical council registration number")
    admission_date: Optional[str] = Field(description="YYYY-MM-DD")
    discharge_date: Optional[str] = Field(description="YYYY-MM-DD")
    diagnosis: Optional[str] = Field(description="Diagnosis as written on the discharge summary")
    procedure: Optional[str] = Field(description="Surgery or procedure performed, if any")
    accident: Optional[bool] = Field(description="True if the hospitalisation was due to an accident")
    bill_number: Optional[str]
    bill_date: Optional[str] = Field(description="YYYY-MM-DD")
    room_rent_per_day: Optional[float]
    bill_line_items: list[LineItem]
    bill_subtotal: Optional[float]
    bill_total: Optional[float]
    name_on_bill: Optional[str]
    claim_amount: Optional[float] = Field(description="Amount claimed in INR")
    filed_date: Optional[str] = Field(description="Date the claim form was signed, YYYY-MM-DD")


READER_SYSTEM = """You are the Reader agent at an Indian health insurer. You receive a hospitalisation
reimbursement claim: claim form, final hospital bill, discharge summary, prescriptions and reports.
Extract the requested fields exactly as they appear. Use null when a value is absent; do not guess.
Indian documents write dates as DD/MM/YYYY (04/10/2026 is 4 October 2026); return YYYY-MM-DD without
swapping day and month. Amounts are INR numbers without symbols or commas."""

POLICY_SYSTEM = """You are the Policy agent at an Indian health insurer. Using ONLY the policy wording and
schedule provided, decide whether the hospitalisation is covered, which exclusions, limits or waiting
periods apply, the payable amount after limits and co-payment, and which required documents are
missing. Cite clause numbers and quote the wording exactly. Do not invent clauses. Do not apply the fraud
clause or judge honesty: other agents assess inconsistencies and a human adjuster decides."""

FORENSICS_SYSTEM = """You are the Forensics agent in a health-insurance Special Investigation Unit in India.
Look for evidence that a claim is inconsistent or manipulated:
1. Treatment, medicines or tests on the bill that do not fit the diagnosis on the discharge summary.
2. Length of stay or charges far above what the procedure normally needs (e.g. day-care procedures
   billed as multi-day stays, ICU charges with no ICU stay in the discharge summary).
3. Diagnosis or procedure differing between the claim form, bill and discharge summary.
4. Signs of editing: inconsistent fonts, overwritten dates or amounts.
Report only findings supported by specific evidence. Return an empty list if the claim looks clean.
Do not repeat simple arithmetic, date or waiting-period checks; those are handled separately."""

WAITING_24M = ("cataract", "hernia", "knee replacement", "hip replacement", "joint replacement", "kidney stone",
               "gall bladder", "gallbladder", "cholecystectomy", "sinusitis", "prostate")


def policy_rules(r: HealthReaderOutput, policy: dict | None) -> list[Flag]:
    out: list[Flag] = []
    if policy is None:
        out.append(flag("policy", "POLICY_NOT_FOUND", "high", "Policy number not found",
                        f"No active policy matches '{r.policy_number or 'none'}'."))
        return out
    adm = parse_date(r.admission_date)
    start, end = parse_date(policy.get("startDate")), parse_date(policy.get("endDate"))
    if adm and start and end:
        if not (start <= adm <= end):
            out.append(flag("policy", "ADMISSION_OUTSIDE_PERIOD", "high", "Admission outside the policy period",
                            f"Admitted {adm}; policy period {start} to {end}.", "clause:2.1"))
        else:
            inception = parse_date(policy.get("inceptionDate")) or start
            days = (adm - inception).days
            if days <= 30 and not r.accident:
                out.append(flag("policy", "INITIAL_WAITING_PERIOD", "high", "Illness within the 30-day waiting period",
                                f"Cover began {inception}; admitted {days} days later for a non-accident illness.", "clause:4.1"))
            treatment = f"{r.diagnosis or ''} {r.procedure or ''}".lower()
            hit = next((w for w in WAITING_24M if w in treatment), None)
            if hit and days < 730:
                out.append(flag("policy", "SPECIFIC_WAITING_PERIOD", "high",
                                "Treatment within the 24-month waiting period",
                                f"'{hit}' is covered only after 24 months of continuous cover; cover began {inception} ({days} days before admission).", "clause:4.2"))
    members = policy.get("members") or []
    if r.patient_name and members and not any(names_match(r.patient_name, m) for m in members):
        out.append(flag("policy", "PATIENT_NOT_INSURED", "high", "Patient is not an insured person",
                        f"Patient '{r.patient_name}' is not among insured members: {', '.join(members)}.", "clause:1.2"))
    si = policy.get("sumInsured")
    if si and r.claim_amount and r.claim_amount > si:
        out.append(flag("policy", "EXCEEDS_SUM_INSURED", "high", "Claim exceeds the sum insured",
                        f"Claimed ₹{r.claim_amount:,.0f} vs sum insured ₹{si:,.0f}.", "clause:1.1"))
    if si and r.room_rent_per_day and r.room_rent_per_day > 0.01 * si * 1.05:
        out.append(flag("policy", "ROOM_RENT_ABOVE_LIMIT", "medium", "Room rent above the policy limit",
                        f"Room rent ₹{r.room_rent_per_day:,.0f}/day vs limit ₹{0.01 * si:,.0f}/day (1% of sum insured).",
                        "clause:3.1"))
    return out


def doc_rules(r: HealthReaderOutput) -> list[Flag]:
    out: list[Flag] = []
    adm, dis, bill, filed = (parse_date(x) for x in (r.admission_date, r.discharge_date, r.bill_date, r.filed_date))
    if adm and dis and dis < adm:
        out.append(flag("forensics", "DISCHARGE_BEFORE_ADMISSION", "high", "Discharge dated before admission",
                        f"Admitted {adm}, discharged {dis}."))
    if bill and adm and bill < adm:
        out.append(flag("forensics", "BILL_BEFORE_ADMISSION", "high", "Hospital bill dated before admission",
                        f"Bill {r.bill_number or ''} dated {bill}, admission {adm}.", "clause:6.3"))
    if r.bill_line_items and r.bill_subtotal:
        s = sum(li.amount for li in r.bill_line_items)
        if abs(s - r.bill_subtotal) > max(10, 0.01 * r.bill_subtotal):
            out.append(flag("forensics", "BILL_ARITHMETIC", "high", "Bill line items don't add up",
                            f"Line items sum to ₹{s:,.0f} but the bill subtotal shows ₹{r.bill_subtotal:,.0f}."))
    if r.bill_total and r.claim_amount and r.claim_amount > r.bill_total * 1.05:
        over = r.claim_amount / r.bill_total - 1
        out.append(flag("forensics", "CLAIM_ABOVE_BILL", "high" if over > 0.2 else "medium",
                        "Amount claimed is higher than the hospital bill",
                        f"Claimed ₹{r.claim_amount:,.0f} vs bill ₹{r.bill_total:,.0f} ({over:.0%} more)."))
    if r.name_on_bill and r.patient_name and not names_match(r.name_on_bill, r.patient_name):
        out.append(flag("forensics", "BILL_NAME_MISMATCH", "medium", "Bill issued to a different person",
                        f"Bill name '{r.name_on_bill}' vs patient '{r.patient_name}'.", "clause:6.3"))
    if dis and filed and (filed - dis).days > 30:
        out.append(flag("forensics", "LATE_SUBMISSION", "low", "Claim submitted late",
                        f"Discharged {dis}, claim filed {filed} ({(filed - dis).days} days later)."))
    return out


def entities(r: HealthReaderOutput) -> list[dict]:
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
    hosp = norm(r.hospital_registration).upper() or norm(r.hospital_name)
    add("hospital", hosp or None, r.hospital_name or r.hospital_registration)
    doc = norm(r.doctor_registration).upper() or norm(r.treating_doctor)
    add("doctor", doc or None, r.treating_doctor or r.doctor_registration)
    if r.bill_number and hosp:
        add("bill", f"{hosp}/{norm(r.bill_number).upper()}", f"{r.hospital_name or ''} #{r.bill_number}")
    return out


def summary(r: HealthReaderOutput) -> dict:
    return {"claimantName": r.claimant_name or r.patient_name, "claimAmount": r.claim_amount,
            "incidentDate": r.admission_date,
            "subject": f"{r.patient_name or 'Patient'} · {r.hospital_name or 'hospital'}",
            "providerName": r.hospital_name}


SPEC = LineSpec(key="health", reader_schema=HealthReaderOutput, reader_system=READER_SYSTEM,
                policy_system=POLICY_SYSTEM, forensics_system=FORENSICS_SYSTEM, policy_rules=policy_rules,
                doc_rules=doc_rules, entities=entities, summary=summary,
                provider_kinds=("hospital", "doctor"), bill_kind="bill")
