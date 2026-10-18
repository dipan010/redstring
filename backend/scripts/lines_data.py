"""Demo world for the health and property lines: policies, PDFs, demo claims, closed history.
All people, hospitals, contractors and numbers are fictional."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from claimgen import INSURER, W, H, _header, _rows, _wrap, rname, rphone, racct

TODAY = date(2026, 10, 19)


def term(inception: date, on: date) -> tuple[date, date]:
    """Annual renewals since inception: the policy year that contains `on`."""
    years = max(0, (on - inception).days // 365)
    start = inception + timedelta(days=365 * years)
    return start, start + timedelta(days=364)


def d(days_ago: int) -> date:
    return TODAY - timedelta(days=days_ago)


# ---------------- providers ----------------

@dataclass
class Hospital:
    name: str
    reg: str
    city: str
    address: str
    phone: str


@dataclass
class Doctor:
    name: str
    reg: str
    specialty: str


@dataclass
class Contractor:
    name: str
    gstin: str
    phone: str
    address: str


LOTUS = Hospital("Lotus Multispeciality Hospital", "MH-PUN-HOSP-2014-0831", "Pune", "Karve Road, Pune 411004", "+91 20 6730 1100")
AROGYA = Hospital("Arogya Care Hospital", "TN-CHN-HOSP-2009-0412", "Chennai", "Mount Road, Chennai 600006", "+91 44 4220 7700")
SANJEEVANI = Hospital("Sanjeevani Multispeciality Hospital", "MH-PUN-HOSP-2019-1177", "Pune", "Nashik Phata, Pune 411034", "+91 20 2712 4455")
KAVYA = Hospital("Kavya Ortho & Spine Centre", "KA-BLR-HOSP-2016-0290", "Bengaluru", "Indiranagar, Bengaluru 560038", "+91 80 4110 3300")
CITYCARE = Hospital("CityCare General Hospital", "MH-MUM-HOSP-2011-0655", "Mumbai", "Andheri East, Mumbai 400069", "+91 22 6620 8800")

DR_JOSHI = Doctor("Dr. Ashwin Joshi", "MMC-2008-31452", "General Surgery")
DR_IYER = Doctor("Dr. Lakshmi Iyer", "TNMC-2012-55120", "Internal Medicine")
DR_KALE = Doctor("Dr. Rajesh Kale", "MMC-2011-48213", "General Medicine")
DR_RAO = Doctor("Dr. Vinod Rao", "KMC-2010-27744", "Orthopaedics")
DR_SHAH = Doctor("Dr. Meena Shah", "MMC-2009-40091", "Internal Medicine")

PRIME = Contractor("Prime Home Repairs", "29AAGFP5521K1Z6", "+91 80 4555 2210", "HSR Layout, Bengaluru 560102")
FIRESAFE = Contractor("SafeRestore Interiors", "27AAKCS7790L1Z2", "+91 22 6245 9900", "Goregaon West, Mumbai 400104")
QUICKFIX = Contractor("QuickFix Home Restorations", "27AABFQ3318M1Z9", "+91 20 4011 6622", "Pimpri, Pune 411018")
BUILDRIGHT = Contractor("BuildRight Civil Works", "33AADFB9012N1Z4", "+91 44 4300 1188", "Velachery, Chennai 600042")

# Shared identifiers inside the rings
H_RING_BANK = "710045226618"
H_RING_PHONE = "+91 98605 33417"
P_RING_BANK = "620011873304"
P_RING_PHONE = "+91 97661 20984"


# ---------------- specs ----------------

@dataclass
class HealthClaim:
    id: str
    title: str
    policy_no: str
    holder: str
    patient: str
    age: int
    relationship: str
    phone: str
    email: str
    bank: str
    hospital: Hospital
    doctor: Doctor
    admission: date
    days: int
    diagnosis: str
    procedure: str
    items: list[tuple[str, int]]
    room_rent: int
    policy_start: date
    sum_insured: int
    members: list[str]
    bill_no: str
    accident: bool = False
    bill_offset: int = 0            # bill date relative to discharge
    subtotal_override: int | None = None
    amount_claimed: int | None = None
    name_on_bill: str | None = None
    discharge_diagnosis: str | None = None   # differs from claim form if set
    label: str = "clean"
    tells: list[str] = field(default_factory=list)
    pack_description: str = ""

    @property
    def discharge(self) -> date:
        return self.admission + timedelta(days=self.days)

    @property
    def bill_date(self) -> date:
        return self.discharge + timedelta(days=self.bill_offset)

    @property
    def subtotal(self) -> int:
        return self.subtotal_override or sum(a for _, a in self.items)

    @property
    def total(self) -> int:
        return self.subtotal  # hospital services are GST exempt

    @property
    def claimed(self) -> int:
        return self.amount_claimed or self.total

    @property
    def filed(self) -> date:
        return self.discharge + timedelta(days=3)

    def policy_record(self) -> dict:
        start, end = term(self.policy_start, self.admission)
        return {"policyNumber": self.policy_no, "holderName": self.holder, "members": self.members,
                "inceptionDate": self.policy_start.isoformat(), "startDate": start.isoformat(), "endDate": end.isoformat(),
                "sumInsured": self.sum_insured, "product": "health_indemnity", "roomRentLimitPerDay": self.sum_insured // 100}


@dataclass
class PropertyClaim:
    id: str
    title: str
    policy_no: str
    holder: str
    phone: str
    email: str
    bank: str
    address: str
    incident_type: str
    incident: date
    description: str
    damaged: list[str]
    contractor: Contractor
    invoice_no: str
    items: list[tuple[str, int]]
    policy_start: date
    si_building: int
    si_contents: int
    photos: list[str] = field(default_factory=list)
    fir: str | None = None
    work_address: str | None = None          # invoice site address, defaults to the insured address
    loss_address: str | None = None          # address on the claim form, defaults to the insured address
    invoice_offset: int = 5
    filed_offset: int = 2
    amount_claimed: int | None = None
    subtotal_override: int | None = None
    label: str = "clean"
    tells: list[str] = field(default_factory=list)
    pack_description: str = ""

    @property
    def invoice_date(self) -> date:
        return self.incident + timedelta(days=self.invoice_offset)

    @property
    def filed(self) -> date:
        return self.incident + timedelta(days=self.filed_offset)

    @property
    def subtotal(self) -> int:
        return self.subtotal_override or sum(a for _, a in self.items)

    @property
    def tax(self) -> int:
        return round(self.subtotal * 0.18)

    @property
    def total(self) -> int:
        return self.subtotal + self.tax

    @property
    def claimed(self) -> int:
        return self.amount_claimed or self.total

    def policy_record(self) -> dict:
        start, end = term(self.policy_start, self.incident)
        return {"policyNumber": self.policy_no, "holderName": self.holder, "propertyAddress": self.address,
                "inceptionDate": self.policy_start.isoformat(), "startDate": start.isoformat(), "endDate": end.isoformat(),
                "sumInsuredBuilding": self.si_building, "sumInsuredContents": self.si_contents, "product": "home_shield",
                "deductible": 5000}


# ---------------- PDFs ----------------

def _sign(c, name, when, y):
    c.setFont("Helvetica", 8.5)
    c.drawString(18 * mm, y - 6, "I declare that the information above is true and complete to the best of my knowledge.")
    c.setFont("Helvetica-Oblique", 11)
    c.drawString(18 * mm, y - 30, name)
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, y - 42, f"Signature          Date: {when.strftime('%d/%m/%Y')}")


def _table(c, y, items, money_label="Amount (INR)"):
    c.setFillColor(colors.HexColor("#eef0f4"))
    c.rect(18 * mm, y - 4, W - 36 * mm, 16, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(20 * mm, y, "#")
    c.drawString(28 * mm, y, "Description")
    c.drawRightString(W - 20 * mm, y, money_label)
    c.setFont("Helvetica", 9.5)
    for i, (desc, amt) in enumerate(items, 1):
        y -= 16
        c.drawString(20 * mm, y, str(i))
        c.drawString(28 * mm, y, desc)
        c.drawRightString(W - 20 * mm, y, f"{amt:,.2f}")
    return y


def health_claim_form(s: HealthClaim, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = _header(c, "HEALTH CLAIM FORM: REIMBURSEMENT", f"{INSURER} · Family Health Indemnity Policy")
    y = _rows(c, y - 4, [
        ("Policy number", s.policy_no), ("Policyholder", s.holder), ("Patient", s.patient),
        ("Age / relationship", f"{s.age} / {s.relationship}"), ("Mobile", s.phone), ("Email", s.email),
        ("Hospital", f"{s.hospital.name}, {s.hospital.city}"), ("Treating doctor", s.doctor.name),
        ("Date of admission", s.admission.strftime("%d/%m/%Y")), ("Date of discharge", s.discharge.strftime("%d/%m/%Y")),
        ("Diagnosis", s.diagnosis), ("Procedure", s.procedure or "None"),
        ("Due to an accident?", "Yes" if s.accident else "No"),
        ("Amount claimed (INR)", f"{s.claimed:,}"), ("Bank account", s.bank), ("IFSC", "HDFC0001234"),
    ])
    _sign(c, s.holder, s.filed, y)
    c.showPage()
    c.save()


def hospital_bill(s: HealthClaim, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    h = s.hospital
    c.setFont("Helvetica-Bold", 15)
    c.drawString(18 * mm, H - 22 * mm, h.name.upper())
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, H - 28 * mm, h.address)
    c.drawString(18 * mm, H - 33 * mm, f"Ph: {h.phone}   Reg. No: {h.reg}")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(W - 18 * mm, H - 22 * mm, "FINAL BILL")
    c.setFont("Helvetica", 9.5)
    c.drawRightString(W - 18 * mm, H - 28 * mm, f"Bill No: {s.bill_no}")
    c.drawRightString(W - 18 * mm, H - 33 * mm, f"Date: {s.bill_date.strftime('%d/%m/%Y')}")
    c.line(18 * mm, H - 38 * mm, W - 18 * mm, H - 38 * mm)
    y = _rows(c, H - 48 * mm, [
        ("Patient", s.name_on_bill or s.patient), ("Admitted", s.admission.strftime("%d/%m/%Y")),
        ("Discharged", s.discharge.strftime("%d/%m/%Y")), ("Consultant", f"{s.doctor.name} ({s.doctor.reg})"),
    ], col=30 * mm)
    y = _table(c, y - 6, s.items)
    y -= 10
    c.line(110 * mm, y, W - 18 * mm, y)
    for k, v in [("Sub-total", s.subtotal), ("GST", 0), ("NET PAYABLE", s.total)]:
        y -= 16
        c.setFont("Helvetica-Bold" if k == "NET PAYABLE" else "Helvetica", 10)
        c.drawString(112 * mm, y, k)
        c.drawRightString(W - 20 * mm, y, f"{v:,.2f}")
    c.setFont("Helvetica", 8.5)
    c.drawString(18 * mm, 30 * mm, "Healthcare services are exempt from GST. This is a computer generated bill.")
    c.drawString(18 * mm, 24 * mm, f"For {h.name} (Billing department)")
    c.showPage()
    c.save()


def discharge_summary(s: HealthClaim, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = _header(c, "DISCHARGE SUMMARY", f"{s.hospital.name} · {s.hospital.city}")
    course = (f"Patient admitted with complaints consistent with {(s.discharge_diagnosis or s.diagnosis).lower()}. "
              + (f"Underwent {s.procedure.lower()} under anaesthesia. Post-operative course uneventful. " if s.procedure else
                 "Managed conservatively with IV fluids and medication. ")
              + "Vitals stable at discharge.")
    _rows(c, y - 4, [
        ("Patient", f"{s.patient}, {s.age} years"), ("Admission", s.admission.strftime("%d/%m/%Y")),
        ("Discharge", s.discharge.strftime("%d/%m/%Y")), ("Final diagnosis", s.discharge_diagnosis or s.diagnosis),
        ("Procedure", s.procedure or "None"), ("Course in hospital", course),
        ("Advice", "Review in OPD after 7 days. Continue medication as prescribed."),
        ("Treating doctor", f"{s.doctor.name}, {s.doctor.specialty}, Reg. {s.doctor.reg}"),
    ])
    c.showPage()
    c.save()


def prescriptions_and_reports(s: HealthClaim, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = _header(c, "PRESCRIPTION AND PHARMACY", f"{s.doctor.name}, {s.doctor.specialty} · Reg. {s.doctor.reg} · {s.hospital.name}")
    meds = ("Inj. Ceftriaxone 1 g IV twice daily; Tab. Pantoprazole 40 mg once daily; Tab. Paracetamol 650 mg SOS"
            if not s.procedure else
            "Inj. Cefuroxime 1.5 g IV twice daily; Inj. Tramadol 50 mg SOS; Tab. Pantoprazole 40 mg once daily")
    _rows(c, y - 4, [("Patient", f"{s.patient}, {s.age} years"), ("Date", s.admission.strftime("%d/%m/%Y")),
                     ("Diagnosis", s.discharge_diagnosis or s.diagnosis), ("Rx", meds),
                     ("On discharge", "Tab. Paracetamol 650 mg SOS for 5 days; review after 7 days")])
    c.showPage()
    # pharmacy bill adds up to the hospital bill's medicines line
    med_total = next((a for dsc, a in s.items if "medicine" in dsc.lower()), 0)
    names = ["Injectable antibiotics", "IV fluids and cannula sets", "Oral medicines and analgesics"]
    parts = [round(med_total * w / 10) * 10 for w in (0.5, 0.3)]
    parts.append(med_total - sum(parts))
    y = _header(c, "PHARMACY BILL", f"In-house pharmacy · {s.hospital.name}")
    y = _rows(c, y - 4, [("Patient", s.patient), ("Period", f"{s.admission:%d/%m/%Y} to {s.discharge:%d/%m/%Y}")])
    y = _table(c, y - 6, list(zip(names, parts)))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(112 * mm, y - 18, "TOTAL")
    c.drawRightString(W - 20 * mm, y - 18, f"{med_total:,.2f}")
    c.showPage()
    dx = (s.discharge_diagnosis or s.diagnosis).lower()
    if "dengue" in dx:
        labs = [("Haemoglobin", "13.4 g/dL (12.0 to 15.5)"), ("Total WBC count", "3,200 /cumm (4,000 to 11,000)"),
                ("Platelet count", "68,000 /cumm (1.5 to 4.5 lakh)"), ("NS1 antigen", "Positive")]
    elif "append" in dx:
        labs = [("Haemoglobin", "14.1 g/dL (13.0 to 17.0)"), ("Total WBC count", "14,600 /cumm (4,000 to 11,000)"),
                ("Neutrophils", "84% (40 to 75)"), ("Ultrasound abdomen", "Inflamed appendix, 9 mm")]
    else:
        labs = [("Haemoglobin", "12.9 g/dL (13.0 to 17.0)"), ("Total WBC count", "11,800 /cumm (4,000 to 11,000)"),
                ("Platelet count", "1.9 lakh /cumm (1.5 to 4.5 lakh)"), ("Serum creatinine", "0.9 mg/dL (0.7 to 1.3)")]
    y = _header(c, "INVESTIGATION REPORT", f"Pathology department · {s.hospital.name}")
    _rows(c, y - 4, [("Patient", f"{s.patient}, {s.age} years"), ("Sample date", s.admission.strftime("%d/%m/%Y")),
                     *labs, ("Remarks", "Reported by the consultant pathologist.")])
    c.showPage()
    c.save()


def property_claim_form(s: PropertyClaim, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = _header(c, "HOME CLAIM FORM", f"{INSURER} · Home Shield Policy")
    y = _rows(c, y - 4, [
        ("Policy number", s.policy_no), ("Name of insured", s.holder), ("Mobile", s.phone), ("Email", s.email),
        ("Address of loss", s.loss_address or s.address), ("Type of incident", s.incident_type.replace("_", " ").capitalize()),
        ("Date of incident", s.incident.strftime("%d/%m/%Y")), ("Description", s.description),
        ("Damaged / stolen", ", ".join(s.damaged)), ("Police report (FIR) no.", s.fir or "Not filed"),
        ("Repair contractor", s.contractor.name), ("Amount claimed (INR)", f"{s.claimed:,}"),
        ("Bank account", s.bank), ("IFSC", "ICIC0000331"),
    ])
    _sign(c, s.holder, s.filed, y)
    c.showPage()
    c.save()


def contractor_invoice(s: PropertyClaim, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    k = s.contractor
    c.setFont("Helvetica-Bold", 15)
    c.drawString(18 * mm, H - 22 * mm, k.name.upper())
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, H - 28 * mm, k.address)
    c.drawString(18 * mm, H - 33 * mm, f"Ph: {k.phone}   GSTIN: {k.gstin}")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(W - 18 * mm, H - 22 * mm, "TAX INVOICE")
    c.setFont("Helvetica", 9.5)
    c.drawRightString(W - 18 * mm, H - 28 * mm, f"Invoice No: {s.invoice_no}")
    c.drawRightString(W - 18 * mm, H - 33 * mm, f"Date: {s.invoice_date.strftime('%d/%m/%Y')}")
    c.line(18 * mm, H - 38 * mm, W - 18 * mm, H - 38 * mm)
    y = _rows(c, H - 48 * mm, [("Billed to", s.holder), ("Site address", s.work_address or s.address)], col=30 * mm)
    y = _table(c, y - 6, s.items)
    y -= 10
    c.line(110 * mm, y, W - 18 * mm, y)
    for lbl, v in [("Sub-total", s.subtotal), ("GST @ 18%", s.tax), ("TOTAL", s.total)]:
        y -= 16
        c.setFont("Helvetica-Bold" if lbl == "TOTAL" else "Helvetica", 10)
        c.drawString(112 * mm, y, lbl)
        c.drawRightString(W - 20 * mm, y, f"{v:,.2f}")
    c.setFont("Helvetica", 8.5)
    c.drawString(18 * mm, 24 * mm, f"For {k.name} (Authorised signatory)")
    c.showPage()
    c.save()


def police_report(s: PropertyClaim, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = _header(c, "FIRST INFORMATION REPORT (extract)", "Police Station (specimen for demo)")
    _rows(c, y - 4, [("FIR no.", s.fir or ""), ("Date of report", s.filed.strftime("%d/%m/%Y")),
                     ("Complainant", s.holder), ("Place of occurrence", s.loss_address or s.address),
                     ("Brief facts", s.description), ("Property reported", ", ".join(s.damaged))])
    c.showPage()
    c.save()


def render_health(s: HealthClaim, out: Path) -> list[tuple[str, str]]:
    out.mkdir(parents=True, exist_ok=True)
    health_claim_form(s, out / "claim_form.pdf")
    hospital_bill(s, out / "hospital_bill.pdf")
    discharge_summary(s, out / "discharge_summary.pdf")
    prescriptions_and_reports(s, out / "prescriptions_and_reports.pdf")
    return [("claim_form.pdf", "application/pdf"), ("hospital_bill.pdf", "application/pdf"),
            ("discharge_summary.pdf", "application/pdf"), ("prescriptions_and_reports.pdf", "application/pdf")]


def render_property(s: PropertyClaim, out: Path, image_dir: Path) -> list[tuple[str, str]]:
    out.mkdir(parents=True, exist_ok=True)
    files = []
    property_claim_form(s, out / "claim_form.pdf")
    files.append(("claim_form.pdf", "application/pdf"))
    contractor_invoice(s, out / "contractor_invoice.pdf")
    files.append(("contractor_invoice.pdf", "application/pdf"))
    if s.fir:
        police_report(s, out / "police_report.pdf")
        files.append(("police_report.pdf", "application/pdf"))
    for i, key in enumerate(s.photos, 1):
        src = image_dir / f"{key}.jpg"
        if src.exists():
            (out / f"photo_{i}.jpg").write_bytes(src.read_bytes())
            files.append((f"photo_{i}.jpg", "image/jpeg"))
    return files


# ---------------- property photos (generated once with Gemini image) ----------------

PROPERTY_IMAGES = {
    "water_ceiling": "an Indian apartment living room a few hours after a pipe burst in the flat above: a fresh wet "
                     "grey patch on an otherwise clean white ceiling, water still dripping, a few freshly fallen plaster "
                     "pieces and a puddle on the tiled floor, a bucket catching drips; no mould, no old brown stains",
    "kitchen_fire": "an Indian apartment kitchen after a small fire: blackened wall tiles above the stove, melted "
                    "plastic exhaust hood, soot on the ceiling, burnt wooden cabinet doors",
    "burgled_room": "an Indian bedroom after a burglary: a forced-open steel almirah with a bent door, clothes and "
                    "drawers thrown on the floor, a broken window grill",
    "storm_roof": "the concrete terrace of an Indian house after a storm: a collapsed metal sheet shed roof, a plain "
                  "unbranded grey water tank with a broken lid, fallen tree branches and debris",
    "flood_ground": "the ground floor of an Indian house after flooding: muddy water line on the walls at knee "
                    "height, swollen wooden door, damaged sofa and wet floor",
}
PROPERTY_STYLE = ("Realistic smartphone photo taken by a homeowner for an insurance claim, daylight, the damage "
                  "clearly visible, no people, no visible text, no signage, no house numbers, no watermark. Subject: ")


# ---------------- demo claims ----------------

def health_claims() -> list[HealthClaim]:
    return [
        HealthClaim("demo-h-appendix", "Emergency appendectomy", "FHI-2026-500101", "Rohit Kulkarni", "Rohit Kulkarni", 34,
                    "Self", "+91 98220 11873", "rohit.k@example.com", "501122334455", LOTUS, DR_JOSHI, d(14), 3,
                    "Acute appendicitis", "Laparoscopic appendectomy",
                    [("Room rent (3 days @ 4,500)", 13500), ("Surgeon fees", 32000), ("Anaesthetist fees", 9000),
                     ("Operation theatre charges", 18000), ("Medicines and consumables", 14200), ("Investigations", 6300)],
                    4500, d(700), 500000, ["Rohit Kulkarni", "Sneha Kulkarni"], "LMH/26/10/0442", label="clean"),
        HealthClaim("demo-h-dengue", "Dengue admission", "FHI-2026-500102", "Priyanka Raman", "Arjun Raman", 9, "Son",
                    "+91 98840 77120", "priyanka.r@example.com", "602233445566", AROGYA, DR_IYER, d(10), 3,
                    "Dengue fever with thrombocytopenia", "",
                    [("Room rent (3 days @ 3,000)", 9000), ("Physician visits", 6000), ("Medicines and IV fluids", 11800),
                     ("Platelet count and investigations", 8200), ("Nursing charges", 3000)],
                    3000, d(420), 400000, ["Priyanka Raman", "Suresh Raman", "Arjun Raman"], "ACH/2026/7781", label="clean"),
        HealthClaim("demo-h-knee", "Knee replacement eight months into policy", "FHI-2026-500103", "Gopal Menon", "Gopal Menon",
                    58, "Self", "+91 99001 45230", "gopal.menon@example.com", "703344556677", KAVYA, DR_RAO, d(18), 5,
                    "Osteoarthritis of right knee", "Total knee replacement (right)",
                    [("Deluxe room (5 days @ 9,500)", 47500), ("Surgeon fees", 85000), ("Implant (knee prosthesis)", 145000),
                     ("Operation theatre charges", 42000), ("Medicines and consumables", 28500), ("Physiotherapy", 9000)],
                    9500, d(245), 500000, ["Gopal Menon", "Radha Menon"], "KOS/26/1188",
                    label="fraud", tells=["specific_waiting_period", "room_rent_above_limit"]),
        HealthClaim("demo-h-inflated", "Viral fever billed with ICU and MRI", "FHI-2026-500104", "Faisal Qureshi", "Faisal Qureshi",
                    41, "Self", "+91 98190 60321", "faisal.q@example.com", "804455667788", CITYCARE, DR_SHAH, d(9), 4,
                    "Viral fever", "",
                    [("ICU charges (3 days @ 18,000)", 54000), ("Room rent (1 day @ 5,000)", 5000), ("MRI brain", 14500),
                     ("Physician visits", 8000), ("Medicines", 21000), ("Investigations", 12500)],
                    5000, d(500), 500000, ["Faisal Qureshi", "Nazia Qureshi"], "CCG/26/55210",
                    subtotal_override=131000, amount_claimed=152000, discharge_diagnosis="Acute viral fever, stable",
                    label="fraud", tells=["treatment_mismatch", "bill_arithmetic", "claim_above_bill"]),
        HealthClaim("demo-h-ring", "Fever admission at Sanjeevani", "FHI-2026-500105", "Ganesh Pawar", "Ganesh Pawar", 37, "Self",
                    H_RING_PHONE, "ganesh.p.81@example.com", H_RING_BANK, SANJEEVANI, DR_KALE, d(21), 4,
                    "Acute gastroenteritis", "",
                    [("Room rent (4 days @ 4,000)", 16000), ("Physician visits", 9600), ("Medicines and IV fluids", 24800),
                     ("Investigations", 11400), ("Nursing charges", 4800)],
                    4000, d(380), 500000, ["Ganesh Pawar", "Asha Pawar"], "SMH/26/0917",
                    label="fraud", tells=["ring", "hospital_fraud_history"]),
    ]


def health_pack() -> HealthClaim:
    return HealthClaim("live-health-ring", "Fresh claim from Sanjeevani Multispeciality", "FHI-2026-500106", "Deepak Shinde",
                       "Deepak Shinde", 44, "Self", H_RING_PHONE, "deepak.shinde.77@example.com", H_RING_BANK, SANJEEVANI,
                       DR_KALE, d(5), 4, "Acute gastroenteritis", "",
                       [("Room rent (4 days @ 4,000)", 16000), ("Physician visits", 9600), ("Medicines and IV fluids", 25600),
                        ("Investigations", 11900), ("Nursing charges", 4800)],
                       4000, d(310), 500000, ["Deepak Shinde"], "SMH/26/1042", label="fraud", tells=["ring"],
                       pack_description="A routine-looking admission. Watch the Linker connect the hospital, doctor and bank account.")


def property_claims() -> list[PropertyClaim]:
    return [
        PropertyClaim("demo-p-pipe", "Burst pipe in living room", "HSP-2026-700201", "Ananya Bhat", "+91 99860 23145",
                      "ananya.bhat@example.com", "510099887766", "Flat 402, Palm Grove Apartments, HSR Layout, Bengaluru 560102",
                      "water_damage", d(12), "A pipe in the flat above burst overnight; water came through our living room ceiling.",
                      ["living room ceiling", "wall paint", "sofa"], PRIME, "PHR/26/0391",
                      [("Ceiling plaster repair", 18500), ("False ceiling board replacement", 12000),
                       ("Wall putty and painting", 16500), ("Sofa upholstery cleaning", 6000)], d(400), 3000000, 800000, ["water_ceiling"], label="clean"),
        PropertyClaim("demo-p-fire", "Small kitchen fire", "HSP-2026-700202", "Karan Malhotra", "+91 98200 44782",
                      "karan.m@example.com", "620088776655", "Flat 11B, Sea Breeze Towers, Goregaon West, Mumbai 400104",
                      "fire", d(9), "An oil fire on the stove spread to the exhaust hood and cabinets before we put it out.",
                      ["kitchen cabinets", "exhaust hood", "wall tiles"], FIRESAFE, "SRI/2026/1180",
                      [("Kitchen cabinet replacement", 32000), ("Exhaust hood (chimney)", 14500), ("Wall tile replacement", 15000),
                       ("Soot cleaning and painting", 10500)], d(300), 4500000, 1000000, ["kitchen_fire"], fir=None, label="clean"),
        PropertyClaim("demo-p-burglary", "Burglary claim with no police report", "HSP-2026-700203", "Imran Siddiqui",
                      "+91 98190 87412", "imran.s@example.com", "730077665544", "House 18, Lake View Colony, Velachery, Chennai 600042",
                      "burglary", d(8), "Came back from a wedding and found the almirah broken open; jewellery and a laptop are missing.",
                      ["gold jewellery", "laptop", "almirah"], BUILDRIGHT, "BCW/26/2207",
                      [("Almirah replacement", 18000), ("Window grill repair", 9500), ("Door lock replacement", 6500)],
                      d(16), 2500000, 1500000, ["burgled_room"], amount_claimed=385000,
                      label="fraud", tells=["no_police_report", "early_claim", "claim_above_invoice"]),
        PropertyClaim("demo-p-address", "Invoice for a different address", "HSP-2026-700204", "Neha Kapoor", "+91 99300 11876",
                      "neha.kapoor@example.com", "840066554433", "Flat 7, Green Acres, Baner Road, Pune 411045",
                      "storm", d(11), "A storm blew off the terrace shed roof and broke the water tank lid.",
                      ["terrace shed roof", "water tank"], PRIME, "PHR/26/0412",
                      [("Metal sheet roof replacement", 54000), ("Water tank lid", 6500), ("Debris clearing", 8000)],
                      d(380), 3500000, 700000, ["storm_roof"], work_address="Villa 22, Prestige Lakeside, Whitefield, Bengaluru 560066",
                      invoice_offset=-3, label="fraud", tells=["invoice_site_mismatch", "invoice_before_incident"]),
        PropertyClaim("demo-p-ring", "Flood damage repaired by QuickFix", "HSP-2026-700205", "Sachin More", P_RING_PHONE,
                      "sachin.more.86@example.com", P_RING_BANK, "Row House 5, Sai Nagar, Pimpri, Pune 411018",
                      "flood", d(20), "Heavy rain flooded the ground floor up to knee height overnight.",
                      ["ground floor walls", "main door", "sofa set"], QUICKFIX, "QHR/26/0533",
                      [("Wall plaster and painting (ground floor)", 42000), ("Main door replacement", 28500),
                       ("Sofa set replacement", 36000), ("Electrical rewiring", 19500)],
                      d(350), 2800000, 600000, ["flood_ground"], label="fraud", tells=["ring", "contractor_fraud_history"]),
    ]


def property_pack() -> PropertyClaim:
    return PropertyClaim("live-property-ring", "Fresh claim repaired by QuickFix", "HSP-2026-700206", "Vaibhav Jadhav",
                         P_RING_PHONE, "vaibhav.jadhav.90@example.com", P_RING_BANK, "Flat 3, Om Residency, Chinchwad, Pune 411019",
                         "water_damage", d(4), "Water leaked from the bathroom above and damaged the bedroom ceiling and wardrobe.",
                         ["bedroom ceiling", "wardrobe"], QUICKFIX, "QHR/26/0601",
                         [("Ceiling plaster repair", 21000), ("Wardrobe replacement", 38000), ("Painting", 14500)],
                         d(290), 2200000, 500000, ["water_ceiling"], label="fraud", tells=["ring", "photo_reused"],
                         pack_description="Looks like a routine leak. Watch the Linker tie it to the contractor and bank account.")


# ---------------- closed history (deterministic, no AI) ----------------

H_FRAUD = [
    dict(name="Sunil Gaikwad", phone="+91 97302 18845", bank=H_RING_BANK, hospital=SANJEEVANI, doctor=DR_KALE,
         bill="SMH/26/0231", amount=58400, days_ago=200, diagnosis="Acute gastroenteritis",
         findings=[("forensics", "high", "Patient was never admitted",
                    "Hospital admission register and CCTV show no in-patient stay on the billed dates."),
                   ("linker", "high", "Payout account belongs to a hospital employee",
                    "Bank account A/c ••6618 is held by a billing executive at Sanjeevani Multispeciality Hospital."),
                   ("forensics", "medium", "Template discharge summary",
                    "Discharge summary text is identical to two other claims from the same doctor.")],
         siu="Case SIU/2026/052. Hospital billing executive arranged paper admissions with Dr. Rajesh Kale. "
             "Claim repudiated under clause 7.1."),
    dict(name="Meena Lokhande", phone="+91 98810 44267", bank="300500700911", hospital=SANJEEVANI, doctor=DR_KALE,
         bill="SMH/26/0388", amount=61200, days_ago=150, diagnosis="Acute gastroenteritis",
         findings=[("forensics", "high", "Admission dates overlap a claimed overseas trip",
                    "Passport stamps show the patient was in Dubai during the billed admission."),
                   ("forensics", "high", "Template discharge summary",
                    "Discharge summary text matches claim RS-812 word for word."),
                   ("policy", "medium", "Investigation reports not produced",
                    "Hospital could not produce the lab reports billed on the final bill (clause 6.2).")],
         siu="Case SIU/2026/061. Linked to RS-812 through the same doctor and template paperwork. "
             "Claim repudiated under clause 7.1."),
]
P_FRAUD = [
    dict(name="Rakesh Chavan", phone="+91 97650 32208", bank=P_RING_BANK, contractor=QUICKFIX, invoice="QHR/26/0144",
         amount=148000, days_ago=240, incident="flood", address="Bungalow 9, Shanti Nagar, Pimpri, Pune 411018",
         findings=[("forensics", "high", "Damage pre-dates the policy",
                    "Survey found long-term damp and rot behind the plaster, not fresh flood damage."),
                   ("linker", "high", "Payout account controlled by the contractor",
                    "Bank account A/c ••3304 belongs to a partner of QuickFix Home Restorations."),
                   ("forensics", "medium", "Invoice inflated",
                    "Market rates for the listed work are about 40% lower than invoiced.")],
         siu="Case SIU/2026/044. QuickFix partner admitted to inflating invoices and routing payouts. "
             "Claim repudiated under clause 6.1."),
    dict(name="Pooja Waghmare", phone="+91 98500 77314", bank="400600800122", contractor=QUICKFIX, invoice="QHR/26/0287",
         amount=126500, days_ago=170, incident="water_damage", address="Flat 12, Ganga Heights, Akurdi, Pune 411035",
         findings=[("forensics", "high", "Photos are from a different property",
                    "Reverse image search matched the damage photos to an earlier claim in Nashik."),
                   ("forensics", "high", "Work never carried out",
                    "Site inspection found the original ceiling and wardrobe intact."),
                   ("linker", "medium", "Same contractor as a confirmed fraud case",
                    "QuickFix Home Restorations was the contractor on RS-910.")],
         siu="Case SIU/2026/057. Linked to RS-910 through the same contractor. Claim repudiated under clause 6.1."),
]

HOSP_POOL = [LOTUS, AROGYA, KAVYA, CITYCARE, SANJEEVANI]
DOC_FOR = {LOTUS.name: DR_JOSHI, AROGYA.name: DR_IYER, KAVYA.name: DR_RAO, CITYCARE.name: DR_SHAH, SANJEEVANI.name: DR_KALE}
DIAG = [("Acute appendicitis", "Laparoscopic appendectomy"), ("Dengue fever", ""), ("Typhoid fever", ""),
        ("Fracture of left radius", "Open reduction and internal fixation"), ("Pneumonia", ""),
        ("Gall bladder stones", "Laparoscopic cholecystectomy"), ("Kidney stone", "Ureteroscopic lithotripsy")]
CON_POOL = [PRIME, FIRESAFE, BUILDRIGHT, QUICKFIX]
P_INCIDENTS = [("water_damage", "Water leaked from a burst pipe and damaged the ceiling."),
               ("fire", "A short circuit caused a small fire in the living room."),
               ("storm", "A storm damaged the terrace and windows."),
               ("flood", "Heavy rain flooded the ground floor.")]


def health_history(rng: random.Random) -> list[dict]:
    rows = []
    for i in range(12):
        h = HOSP_POOL[i % len(HOSP_POOL)]
        diag, proc = rng.choice(DIAG)
        rows.append(dict(name=rname(rng), phone=rphone(rng), bank=racct(rng), hospital=h, doctor=DOC_FOR[h.name],
                         bill=f"{''.join(w[0] for w in h.name.split()[:3]).upper()}/25/{rng.randint(1000, 9999)}",
                         amount=rng.randint(25, 160) * 1000, days_ago=rng.randint(60, 600), diagnosis=diag,
                         procedure=proc, fraud=False, score=rng.choice([0, 0, 6, 15])))
    rows += [dict(**f, procedure="", fraud=True, score=s) for f, s in zip(H_FRAUD, (88, 81))]
    return rows


def property_history(rng: random.Random) -> list[dict]:
    rows = []
    cities = {PRIME.name: "Bengaluru", FIRESAFE.name: "Mumbai", BUILDRIGHT.name: "Chennai", QUICKFIX.name: "Pune"}
    for i in range(10):
        k = CON_POOL[i % len(CON_POOL)]
        inc, desc = rng.choice(P_INCIDENTS)
        rows.append(dict(name=rname(rng), phone=rphone(rng), bank=racct(rng), contractor=k,
                         invoice=f"{''.join(w[0] for w in k.name.split()[:3]).upper()}/25/{rng.randint(100, 999)}",
                         amount=rng.randint(30, 220) * 1000, days_ago=rng.randint(60, 600), incident=inc,
                         description=desc, address=f"Flat {rng.randint(1, 40)}, {rng.choice(['Sunrise', 'Lotus', 'Silver Oak', 'Green Park'])} "
                                                   f"Residency, {cities[k.name]}",
                         fraud=False, score=rng.choice([0, 0, 6, 15])))
    rows += [dict(**f, description=dict(P_INCIDENTS)[f["incident"]], fraud=True, score=s) for f, s in zip(P_FRAUD, (90, 84))]
    return rows
