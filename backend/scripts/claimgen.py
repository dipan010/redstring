"""Synthetic claim packs: specs + PDF rendering (claim form, repair invoice, KYC, FIR).
All people, policies, garages and numbers are fictional."""

from __future__ import annotations

import random
import zlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

W, H = A4
INSURER = "Redstring Demo General Insurance"


@dataclass
class Garage:
    name: str
    gstin: str
    phone: str
    address: str


@dataclass
class Policy:
    number: str
    holder: str
    vehicle_reg: str
    make_model: str
    start: date
    idv: int
    cc: int = 1197
    break_in: bool = False

    @property
    def end(self) -> date:
        return self.start + timedelta(days=364)

    def record(self) -> dict:
        return {
            "policyNumber": self.number, "holderName": self.holder, "vehicleRegistration": self.vehicle_reg,
            "vehicleMakeModel": self.make_model, "startDate": self.start.isoformat(), "endDate": self.end.isoformat(),
            "idv": self.idv, "cubicCapacity": self.cc, "breakIn": self.break_in, "product": "private_car_package",
            "compulsoryDeductible": 1000 if self.cc <= 1500 else 2000,
        }


@dataclass
class ClaimSpec:
    id: str
    title: str
    policy: Policy
    claimant: str
    phone: str
    email: str
    bank_acct: str
    ifsc: str
    incident: date
    incident_time: str
    location: str
    description: str
    damage_areas: list[str]
    garage: Garage
    invoice_no: str
    line_items: list[tuple[str, int]]
    photos: list[str] = field(default_factory=list)  # image pool keys
    vehicle_reg: str | None = None  # defaults to policy vehicle
    colour: str = "White"
    filed_offset_days: int = 1
    invoice_offset_days: int = 4  # invoice date relative to incident
    amount_claimed: int | None = None  # defaults to invoice total
    subtotal_override: int | None = None
    invoice_customer: str | None = None
    fir_number: str | None = None
    include_kyc: bool = True
    label: str = "clean"  # clean | fraud (benchmark ground truth)
    tells: list[str] = field(default_factory=list)
    description_for_pack: str = ""

    @property
    def vehicle(self) -> str:
        return self.vehicle_reg or self.policy.vehicle_reg

    @property
    def subtotal(self) -> int:
        return self.subtotal_override or sum(a for _, a in self.line_items)

    @property
    def tax(self) -> int:
        return round(self.subtotal * 0.18)

    @property
    def total(self) -> int:
        return self.subtotal + self.tax

    @property
    def claimed(self) -> int:
        return self.amount_claimed or self.total

    @property
    def filed(self) -> date:
        return self.incident + timedelta(days=self.filed_offset_days)

    @property
    def invoice_date(self) -> date:
        return self.incident + timedelta(days=self.invoice_offset_days)


# ---------------- PDF rendering ----------------


def _header(c: canvas.Canvas, title: str, subtitle: str = "") -> float:
    c.setFillColor(colors.HexColor("#1d2b4f"))
    c.rect(0, H - 28 * mm, W, 28 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(18 * mm, H - 14 * mm, title)
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, H - 21 * mm, subtitle)
    c.setFillColor(colors.black)
    return H - 40 * mm


def _rows(c: canvas.Canvas, y: float, rows: list[tuple[str, str]], col: float = 62 * mm) -> float:
    for k, v in rows:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(18 * mm, y, k)
        c.setFont("Helvetica", 10)
        lines = _wrap(v, 80)
        for i, line in enumerate(lines):
            c.drawString(18 * mm + col, y - i * 12, line)
        y -= 12 * max(1, len(lines)) + 6
    return y


def _wrap(s: str, n: int) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + [cur] if cur else lines or [""]


def claim_form(s: ClaimSpec, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = _header(c, "MOTOR CLAIM FORM: OWN DAMAGE", f"{INSURER} · Private Car Package Policy")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y, "Section A: Policy & Insured")
    y = _rows(c, y - 16, [
        ("Policy number", s.policy.number),
        ("Name of insured", s.claimant),
        ("Mobile", s.phone),
        ("Email", s.email),
    ])
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y - 4, "Section B: Vehicle")
    y = _rows(c, y - 20, [
        ("Registration no.", s.vehicle),
        ("Make / model", s.policy.make_model),
        ("Colour", s.colour),
    ])
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y - 4, "Section C: Incident")
    y = _rows(c, y - 20, [
        ("Date of incident", s.incident.strftime("%d/%m/%Y")),
        ("Time", s.incident_time),
        ("Place", s.location),
        ("Description", s.description),
        ("Damaged parts", ", ".join(s.damage_areas)),
        ("Police report (FIR) no.", s.fir_number or "Not filed"),
        ("Repairing garage", f"{s.garage.name}, {s.garage.address}"),
        ("Amount claimed (INR)", f"{s.claimed:,}"),
    ])
    c.setFont("Helvetica-Bold", 11)
    c.drawString(18 * mm, y - 4, "Section D: Bank details for settlement")
    y = _rows(c, y - 20, [("Account number", s.bank_acct), ("IFSC", s.ifsc), ("Account holder", s.claimant)])
    c.setFont("Helvetica", 8.5)
    c.drawString(18 * mm, y - 6, "I declare that the information above is true and complete to the best of my knowledge.")
    c.setFont("Helvetica-Oblique", 11)
    c.drawString(18 * mm, y - 30, s.claimant)
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, y - 42, f"Signature of insured          Date: {s.filed.strftime('%d/%m/%Y')}")
    c.showPage()
    c.save()


def invoice(s: ClaimSpec, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(18 * mm, H - 22 * mm, s.garage.name.upper())
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, H - 28 * mm, s.garage.address)
    c.drawString(18 * mm, H - 33 * mm, f"Ph: {s.garage.phone}   GSTIN: {s.garage.gstin}")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(W - 18 * mm, H - 22 * mm, "TAX INVOICE")
    c.setFont("Helvetica", 9.5)
    c.drawRightString(W - 18 * mm, H - 28 * mm, f"Invoice No: {s.invoice_no}")
    c.drawRightString(W - 18 * mm, H - 33 * mm, f"Date: {s.invoice_date.strftime('%d/%m/%Y')}")
    c.line(18 * mm, H - 38 * mm, W - 18 * mm, H - 38 * mm)
    y = _rows(c, H - 48 * mm, [
        ("Billed to", s.invoice_customer or s.claimant),
        ("Vehicle", f"{s.vehicle} · {s.policy.make_model}"),
        ("Insurance", f"{INSURER} · Policy {s.policy.number}"),
    ], col=30 * mm)
    y -= 6
    c.setFillColor(colors.HexColor("#eef0f4"))
    c.rect(18 * mm, y - 4, W - 36 * mm, 16, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(20 * mm, y, "#")
    c.drawString(28 * mm, y, "Description")
    c.drawRightString(W - 20 * mm, y, "Amount (INR)")
    c.setFont("Helvetica", 9.5)
    for i, (d, a) in enumerate(s.line_items, 1):
        y -= 16
        c.drawString(20 * mm, y, str(i))
        c.drawString(28 * mm, y, d)
        c.drawRightString(W - 20 * mm, y, f"{a:,.2f}")
    y -= 10
    c.line(110 * mm, y, W - 18 * mm, y)
    for k, v in [("Sub-total", s.subtotal), ("GST @ 18%", s.tax), ("TOTAL", s.total)]:
        y -= 16
        c.setFont("Helvetica-Bold" if k == "TOTAL" else "Helvetica", 10)
        c.drawString(112 * mm, y, k)
        c.drawRightString(W - 20 * mm, y, f"{v:,.2f}")
    c.setFont("Helvetica", 8.5)
    c.drawString(18 * mm, 30 * mm, "Certified that the above repairs were carried out on the vehicle mentioned.")
    c.drawString(18 * mm, 24 * mm, f"For {s.garage.name} (Authorised signatory)")
    c.showPage()
    c.save()


def kyc(s: ClaimSpec, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = _header(c, "CERTIFICATE OF REGISTRATION (copy)", "Form 23 · Transport Department (specimen)")
    _rows(c, y - 4, [
        ("Registration no.", s.vehicle),
        ("Owner", s.policy.holder),
        ("Maker / model", s.policy.make_model),
        ("Colour", s.colour),
        ("Cubic capacity", f"{s.policy.cc} cc"),
        ("Registration date", (s.policy.start - timedelta(days=700)).strftime("%d/%m/%Y")),
    ])
    c.showPage()
    y = _header(c, "DRIVING LICENCE (copy)", "Union of India · Specimen for demo")
    _rows(c, y - 4, [
        ("Name", s.claimant),
        ("Licence no.", f"MH-{zlib.crc32(s.claimant.encode()) % 10**13:013d}"),
        ("Class of vehicle", "LMV"),
        ("Valid till", (s.incident + timedelta(days=3000)).strftime("%d/%m/%Y")),
    ])
    c.showPage()
    c.save()


def fir(s: ClaimSpec, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = _header(c, "FIRST INFORMATION REPORT (extract)", "Police Station, Traffic (specimen for demo)")
    _rows(c, y - 4, [
        ("FIR no.", s.fir_number or ""),
        ("Date of report", s.filed.strftime("%d/%m/%Y")),
        ("Complainant", s.claimant),
        ("Vehicle", s.vehicle),
        ("Place of occurrence", s.location),
        ("Brief facts", s.description),
    ])
    c.showPage()
    c.save()


def render_pack(s: ClaimSpec, out_dir: Path, image_dir: Path) -> list[tuple[str, str]]:
    """Write all documents of a pack. Returns [(filename, mime)]."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[tuple[str, str]] = []
    claim_form(s, out_dir / "claim_form.pdf")
    files.append(("claim_form.pdf", "application/pdf"))
    invoice(s, out_dir / "repair_invoice.pdf")
    files.append(("repair_invoice.pdf", "application/pdf"))
    if s.include_kyc:
        kyc(s, out_dir / "rc_and_licence.pdf")
        files.append(("rc_and_licence.pdf", "application/pdf"))
    if s.fir_number:
        fir(s, out_dir / "police_report.pdf")
        files.append(("police_report.pdf", "application/pdf"))
    for i, key in enumerate(s.photos, 1):
        src = image_dir / f"{key}.jpg"
        if src.exists():
            (out_dir / f"photo_{i}.jpg").write_bytes(src.read_bytes())
            files.append((f"photo_{i}.jpg", "image/jpeg"))
    return files


# ---------------- random helpers (history + benchmark) ----------------

FIRST = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Rohan", "Kabir", "Ananya", "Diya", "Isha", "Meera", "Kavya",
         "Riya", "Nikhil", "Pooja", "Sanjay", "Deepa", "Farhan", "Zoya", "Harpreet", "Lakshmi", "Suresh", "Neha"]
LAST = ["Sharma", "Iyer", "Reddy", "Menon", "Patel", "Gupta", "Khan", "Das", "Singh", "Joshi", "Bose", "Pillai",
        "Chatterjee", "Nair", "Kulkarni", "Banerjee", "Rao", "Shetty"]
CITIES = [("Pune", "MH12"), ("Mumbai", "MH02"), ("Bengaluru", "KA03"), ("Chennai", "TN09"), ("Hyderabad", "TS09"),
          ("Delhi", "DL8C"), ("Kolkata", "WB06")]
CARS = [("Maruti Suzuki Swift VXI", 1197), ("Hyundai i20 Asta", 1197), ("Honda City ZX", 1498),
        ("Tata Nexon XZ+", 1199), ("Hyundai Creta SX", 1497), ("Mahindra XUV700 AX5", 1997), ("Kia Seltos HTX", 1497)]


def rname(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def rphone(rng: random.Random) -> str:
    return f"+91 9{rng.randint(100000000, 999999999)}"


def rplate(rng: random.Random, prefix: str | None = None) -> str:
    p = prefix or rng.choice(CITIES)[1]
    return f"{p[:2]} {p[2:]} {rng.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}{rng.choice('ABCDEFGHJKLMNPRSTUVWXYZ')} {rng.randint(1000, 9999)}"


def racct(rng: random.Random) -> str:
    return str(rng.randint(10**11, 10**12 - 1))
