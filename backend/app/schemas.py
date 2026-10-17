"""Pydantic models: Gemini structured-output schemas and API payloads.

Gemini response schemas avoid dict/Any types and defaults that the
structured-output API cannot express.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high"]
DocKind = Literal[
    "claim_form",
    "repair_invoice",
    "damage_photo",
    "police_report",
    "driving_licence",
    "registration_certificate",
    "survey_report",
    "other",
]
Action = Literal["fast_track", "request_info", "investigate"]


# ---------- Reader agent (Gemini output) ----------


class DocSummary(BaseModel):
    index: int = Field(description="0-based index of the document in the order given")
    kind: DocKind
    summary: str = Field(description="One sentence on what this document is")


class LineItem(BaseModel):
    description: str
    amount: float


class Invoice(BaseModel):
    number: Optional[str]
    date: Optional[str] = Field(description="YYYY-MM-DD")
    garage_name: Optional[str]
    garage_gstin: Optional[str]
    garage_phone: Optional[str]
    line_items: list[LineItem]
    subtotal: Optional[float]
    tax: Optional[float]
    total: Optional[float]
    name_on_invoice: Optional[str] = Field(description="Customer name printed on the invoice")
    vehicle_on_invoice: Optional[str] = Field(description="Vehicle registration printed on the invoice")


class PhotoObservation(BaseModel):
    doc_index: int
    damage_areas_visible: list[str] = Field(
        description="Vehicle areas with visible damage, e.g. 'front bumper', 'left headlamp'"
    )
    vehicle_colour: Optional[str]
    severity: Literal["none", "minor", "moderate", "severe"]
    notes: str = Field(description="Anything unusual: watermarks, stock-photo look, mismatched vehicle, old damage")


class ReaderOutput(BaseModel):
    documents: list[DocSummary]
    claimant_name: Optional[str]
    claimant_phone: Optional[str]
    claimant_email: Optional[str]
    bank_account: Optional[str]
    bank_ifsc: Optional[str]
    policy_number: Optional[str]
    vehicle_registration: Optional[str]
    vehicle_make_model: Optional[str]
    vehicle_colour: Optional[str]
    incident_date: Optional[str] = Field(description="YYYY-MM-DD")
    incident_time: Optional[str]
    incident_location: Optional[str]
    incident_description: Optional[str]
    damage_areas_claimed: list[str] = Field(description="Areas the claimant says were damaged")
    claim_amount: Optional[float] = Field(description="Amount claimed in INR")
    filed_date: Optional[str] = Field(description="Date the claim form was signed/filed, YYYY-MM-DD")
    police_report_number: Optional[str]
    invoice: Optional[Invoice]
    photo_observations: list[PhotoObservation]


# ---------- Policy agent (Gemini output) ----------


class ClauseRef(BaseModel):
    clause_id: str = Field(description="Clause number from the policy wording, e.g. '4.2'")
    title: str
    quote: str = Field(description="Short verbatim quote from the clause")
    reason: str = Field(description="Why this clause matters for this claim")


class PolicyOutput(BaseModel):
    covered: bool
    coverage_summary: str
    deductible: Optional[float]
    payable_estimate: Optional[float] = Field(description="Estimated payable amount in INR after deductible/depreciation")
    exclusions_triggered: list[ClauseRef]
    supporting_clauses: list[ClauseRef]
    missing_documents: list[str] = Field(description="Documents the policy requires that were not submitted")


# ---------- Forensics agent (Gemini output) ----------


class ForensicFinding(BaseModel):
    title: str = Field(description="Short headline, e.g. 'Photo shows front damage; claim describes rear impact'")
    severity: Severity
    evidence: str = Field(description="Specific evidence from the documents, quoting values where possible")
    doc_index: Optional[int]


class ForensicsOutput(BaseModel):
    findings: list[ForensicFinding]


# ---------- Verdict agent (Gemini output) ----------


class VerdictOutput(BaseModel):
    summary: str = Field(description="2-3 sentence plain-English assessment for the adjuster")
    key_reasons: list[str] = Field(description="3-5 bullet reasons, most important first")
    next_steps: list[str] = Field(description="Concrete next steps for the adjuster")


# ---------- Stored flag ----------


class Flag(BaseModel):
    id: str
    agent: Literal["reader", "policy", "forensics", "linker", "verdict"]
    code: str
    severity: Severity
    title: str
    evidence: str
    source: Optional[str] = None  # e.g. "doc:1", "clause:4.2", "claim:RS-1043"
    status: Literal["open", "confirmed", "dismissed"] = "open"


# ---------- API payloads ----------


class UploadedDoc(BaseModel):
    path: str  # storage object path, e.g. uploads/<uid>/<id>/invoice.pdf
    name: str
    mime_type: str


class CreateClaimRequest(BaseModel):
    documents: list[UploadedDoc] = Field(min_length=1, max_length=10)
    note: Optional[str] = Field(default=None, max_length=1000)
    sample_pack: Optional[str] = Field(default=None, pattern=r"^[a-z0-9-]{1,40}$")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class FlagFeedbackRequest(BaseModel):
    status: Literal["open", "confirmed", "dismissed"]


class DecisionRequest(BaseModel):
    action: Action | Literal["approve", "reject"]
    note: Optional[str] = Field(default=None, max_length=1000)


class DraftRequest(BaseModel):
    kind: Literal["request_info", "investigation_referral", "approval"]
