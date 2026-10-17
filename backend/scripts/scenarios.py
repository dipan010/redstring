"""The demo world: policies, garages, seeded demo claims, the hidden fraud ring,
and the live sample packs offered on the New Claim page. All fictional."""

from datetime import date, timedelta

from claimgen import ClaimSpec, Garage, Policy

TODAY = date(2026, 10, 17)


def d(days_ago: int) -> date:
    return TODAY - timedelta(days=days_ago)


# ---------- garages ----------
SPEEDFIX = Garage("Speedfix Motor Works", "27AAKFS4821M1Z9", "+91 20 4120 7788", "Plot 14, Bhosari MIDC, Pune 411026")
CITYAUTO = Garage("City Auto Care", "27AAECC9012K1Z3", "+91 20 2556 1200", "Baner Road, Pune 411045")
KAVERI = Garage("Kaveri Motors", "29AABCK4410P1Z7", "+91 80 4567 2210", "Hosur Road, Bengaluru 560068")
GLASSPRO = Garage("GlassPro Windshields", "33AAGFG7781Q1Z2", "+91 44 2811 9090", "Anna Salai, Chennai 600002")
MARINE = Garage("Marine Drive Autohaus", "27AAMFM3321R1Z5", "+91 22 6650 4411", "Worli, Mumbai 400018")

# ---------- image pool (generated once with Imagen) ----------
IMAGE_PROMPTS = {
    "rear_white_sedan": "white Honda City sedan, rear bumper dented and scraped after a minor rear-end collision",
    "windscreen_white_suv": "white Tata Nexon compact SUV, windscreen with a large spider-web crack from a stone",
    "windscreen_white_suv_b": "white Tata Nexon compact SUV, windscreen with a long crack across the driver side from a stone chip",
    "door_grey_suv": "grey Hyundai Creta SUV, front left door with a deep dent and scratched paint",
    "front_silver_hatch": "silver Maruti Suzuki Swift hatchback, crumpled front bumper and broken left headlamp",
    "front_red_hatch": "red Hyundai i20 hatchback, crushed front bumper, bent bonnet and cracked grille",
    "front_black_suv": "black Mahindra XUV700 SUV, heavily damaged front grille, bumper and right headlamp",
    "old_rust_white_hatch": "white Maruti Suzuki Swift hatchback, old rusty dent on the rear quarter panel with faded, peeling paint and dirt in the dent",
    "rear_blue_suv": "blue Kia Seltos SUV, rear bumper cracked and right tail lamp smashed",
}
IMAGE_STYLE = ("Realistic smartphone photo taken by a car owner for an insurance claim, parked on an Indian city street, "
               "daylight, the whole damaged area clearly visible, no people, no text, no watermark. Subject: ")

# ---------- policies ----------
P = {
    "priya": Policy("PCP-2026-418230", "Priya Nair", "MH 12 KT 4471", "Honda City ZX", d(200), 920000, 1498),
    "arjun": Policy("PCP-2026-418231", "Arjun Mehta", "TN 09 BX 2290", "Tata Nexon XZ+", d(150), 810000, 1199),
    "sneha": Policy("PCP-2026-418232", "Sneha Kulkarni", "KA 03 MN 7812", "Hyundai Creta SX", d(300), 1150000, 1497),
    "vikram": Policy("PCP-2026-418233", "Vikram Rao", "MH 12 RS 9034", "Maruti Suzuki Swift VXI", d(240), 560000, 1197),
    "ishaan": Policy("PCP-2026-418234", "Ishaan Gupta", "MH 02 FA 1187", "Hyundai i20 Asta", d(180), 690000, 1197),
    "farhan": Policy("PCP-2026-418235", "Farhan Sheikh", "MH 02 GH 6650", "Mahindra XUV700 AX5", d(21), 1890000, 1997, True),
    "rahul": Policy("PCP-2026-418236", "Rahul Deshmukh", "MH 14 DT 3021", "Maruti Suzuki Swift VXI", d(120), 540000, 1197),
    "kiran": Policy("PCP-2026-418237", "Kiran Jadhav", "MH 12 PQ 7719", "Hyundai i20 Asta", d(95), 650000, 1197),
    "sameer": Policy("PCP-2026-418238", "Sameer Pawar", "MH 14 EV 5520", "Kia Seltos HTX", d(160), 1240000, 1497),
    # live sample packs
    "amol": Policy("PCP-2026-418239", "Amol Shinde", "MH 12 WX 8806", "Maruti Suzuki Swift VXI", d(75), 550000, 1197),
    "meera": Policy("PCP-2026-418240", "Meera Iyer", "TN 09 CK 5512", "Tata Nexon XZ+", d(210), 830000, 1199),
    "deepa": Policy("PCP-2026-418241", "Deepa Menon", "MH 02 JK 2049", "Hyundai i20 Asta", d(110), 700000, 1197),
}

# Shared identifiers inside the ring
RING_BANK_A = "601234558812"
RING_BANK_B = "502288114477"
RING_PHONE_1 = "+91 98220 41736"
RING_PHONE_3 = "+91 97300 58821"
RING_DUP_INVOICE = "SMW/25-26/0412"  # also used on a historical confirmed-fraud claim

STD_REAR = [("Rear bumper (OEM) replacement", 9800), ("Rear bumper painting", 4200), ("Denting & labour", 2500)]


def demo_claims() -> list[ClaimSpec]:
    return [
        ClaimSpec("demo-clean-rear", "Minor rear-end collision", P["priya"], "Priya Nair", "+91 98450 22781",
                  "priya.nair@example.com", "918020045571", "HDFC0001234", d(6), "18:40", "FC Road signal, Pune",
                  "Stopped at a red signal when a two-wheeler hit the rear bumper. Rider exchanged details.",
                  ["rear bumper"], CITYAUTO, "CAC/2026/1182", STD_REAR, ["rear_white_sedan"], label="clean"),
        ClaimSpec("demo-clean-windscreen", "Windscreen crack from stone", P["arjun"], "Arjun Mehta", "+91 98840 11025",
                  "arjun.mehta@example.com", "330011887766", "ICIC0000331", d(9), "08:15", "OMR, Chennai",
                  "A stone thrown up by a truck cracked the windscreen while driving on OMR.",
                  ["windscreen"], GLASSPRO, "GP-77812",
                  [("Windscreen glass (laminated) replacement", 11500), ("Moulding & sealant", 1200), ("Fitting labour", 1500)],
                  ["windscreen_white_suv"], label="clean"),
        ClaimSpec("demo-clean-door", "Door dent in parking", P["sneha"], "Sneha Kulkarni", "+91 99000 34512",
                  "sneha.k@example.com", "771100229933", "SBIN0004455", d(12), "13:05", "Phoenix Mall parking, Bengaluru",
                  "Another car's door hit the front left door while parked at the mall.",
                  ["front left door"], KAVERI, "KM/OD/5521",
                  [("Front left door denting", 3800), ("Door painting", 5200), ("Labour", 2000)],
                  ["door_grey_suv"], colour="Grey", label="clean"),
        ClaimSpec("demo-invoice-dates", "Invoice dated before the accident", P["vikram"], "Vikram Rao", "+91 98190 77210",
                  "vikram.rao@example.com", "440099112233", "AXIS0001907", d(8), "21:30", "Katraj bypass, Pune",
                  "Hit a road divider in heavy rain; front bumper and left headlamp damaged.",
                  ["front bumper", "left headlamp"], CITYAUTO, "CAC/2026/1094",
                  [("Front bumper replacement", 8900), ("Left headlamp assembly", 7400), ("Painting", 3600), ("Labour", 2200)],
                  ["front_silver_hatch"], colour="Silver", invoice_offset_days=-5, subtotal_override=27600,
                  label="fraud", tells=["invoice_before_incident", "invoice_arithmetic"]),
        ClaimSpec("demo-photo-mismatch", "Rear-end claim, front-end photos", P["ishaan"], "Ishaan Gupta",
                  "+91 99200 41188", "ishaan.g@example.com", "120034005600", "KKBK0000652", d(5), "10:20",
                  "Western Express Highway, Mumbai",
                  "A car rear-ended me in slow traffic. Rear bumper and right tail lamp broken.",
                  ["rear bumper", "right tail lamp"], MARINE, "MDA-2026-0877",
                  [("Rear bumper replacement", 10400), ("Right tail lamp", 6100), ("Painting", 4300), ("Labour", 2400)],
                  ["front_red_hatch"], colour="Red", amount_claimed=41500,
                  label="fraud", tells=["photo_mismatch", "claim_above_invoice"]),
        ClaimSpec("demo-early-claim", "Big claim weeks after a break-in policy", P["farhan"], "Farhan Sheikh",
                  "+91 98670 90012", "farhan.s@example.com", "667788990011", "YESB0000123", d(9), "02:10",
                  "Eastern Freeway, Mumbai",
                  "Lost control at night and hit a barricade. Heavy front damage.",
                  ["front grille", "front bumper", "right headlamp", "radiator"], MARINE, "MDA-2026-0912",
                  [("Front bumper assembly", 24500), ("Grille & emblem", 11200), ("Right headlamp (LED)", 38900),
                   ("Radiator & condenser", 31600), ("Painting", 9800), ("Labour", 8500)],
                  ["front_black_suv"], colour="Black", filed_offset_days=8,
                  label="fraud", tells=["early_claim", "break_in", "late_intimation", "missing_fir"]),
        # ---- the ring (Speedfix Motor Works) ----
        ClaimSpec("demo-ring-1", "Parked car hit at night", P["rahul"], "Rahul Deshmukh", RING_PHONE_1,
                  "rahul.d.1988@example.com", RING_BANK_A, "SBIN0011223", d(30), "23:45", "Chakan, Pune",
                  "Car was parked outside home overnight; found the rear damaged by an unknown vehicle in the morning.",
                  ["rear bumper", "boot lid", "rear quarter panel"], SPEEDFIX, "SMW/26-27/0141",
                  [("Rear bumper replacement", 12800), ("Boot lid replacement", 21500), ("Quarter panel denting", 9800),
                   ("Painting (full rear)", 11400), ("Labour", 6500)],
                  ["old_rust_white_hatch"], label="fraud", tells=["ring", "old_damage"]),
        ClaimSpec("demo-ring-2", "Hit-and-run while parked", P["kiran"], "Kiran Jadhav", RING_PHONE_1,
                  "kiranjadhav.auto@example.com", RING_BANK_B, "BARB0BHOSAR", d(18), "22:30", "Bhosari, Pune",
                  "Unknown vehicle hit my parked car at night and drove away. Front badly damaged.",
                  ["front bumper", "bonnet", "grille"], SPEEDFIX, "SMW/26-27/0167",
                  [("Front bumper replacement", 13900), ("Bonnet replacement", 18700), ("Grille", 5400),
                   ("Painting", 9900), ("Labour", 6000)],
                  ["front_red_hatch"], colour="Red", label="fraud", tells=["ring"]),
        ClaimSpec("demo-ring-3", "Unknown vehicle damage at night", P["sameer"], "Sameer Pawar", RING_PHONE_3,
                  "sameer.pawar.p@example.com", RING_BANK_A, "SBIN0011223", d(11), "01:15", "Moshi, Pune",
                  "Parked SUV hit by an unidentified vehicle late at night. Rear bumper and tail lamp damaged.",
                  ["rear bumper", "right tail lamp"], SPEEDFIX, RING_DUP_INVOICE,
                  [("Rear bumper replacement", 15600), ("Right tail lamp", 9800), ("Painting", 8800), ("Labour", 5500)],
                  ["rear_blue_suv"], colour="Blue", label="fraud", tells=["ring", "duplicate_invoice"]),
    ]


def live_packs() -> list[ClaimSpec]:
    """Not seeded: offered as one-click sample packs so evaluators can watch the agents run live."""
    return [
        ClaimSpec("live-ring", "Fresh claim from Speedfix Motor Works", P["amol"], "Amol Shinde", RING_PHONE_3,
                  "amol.shinde.92@example.com", RING_BANK_B, "BARB0BHOSAR", d(2), "23:10", "Bhosari, Pune",
                  "Parked car was hit by an unknown vehicle at night. Front bumper and headlamp damaged.",
                  ["front bumper", "left headlamp"], SPEEDFIX, "SMW/26-27/0203",
                  [("Front bumper replacement", 14200), ("Left headlamp assembly", 9900), ("Painting", 8400), ("Labour", 6200)],
                  ["front_silver_hatch"], colour="Silver", label="fraud", tells=["ring"],
                  description_for_pack="Looks routine on its own. Watch the Linker agent connect it to other claims."),
        ClaimSpec("live-clean", "Windscreen replacement", P["meera"], "Meera Iyer", "+91 98400 66123",
                  "meera.iyer@example.com", "220033445566", "HDFC0000660", d(3), "07:50", "ECR, Chennai",
                  "A stone hit the windscreen on the highway and it cracked across.",
                  ["windscreen"], GLASSPRO, "GP-78110",
                  [("Windscreen glass (laminated) replacement", 11800), ("Moulding & sealant", 1200), ("Fitting labour", 1500)],
                  ["windscreen_white_suv_b"], label="clean",
                  description_for_pack="A clean, complete claim. Expect a fast-track recommendation."),
        ClaimSpec("live-mismatch", "Rear-end collision", P["deepa"], "Deepa Menon", "+91 99300 22870",
                  "deepa.menon@example.com", "887766554433", "KKBK0000652", d(4), "17:35", "Andheri, Mumbai",
                  "Rear-ended by a taxi at a signal. Rear bumper broken and tail lamp cracked.",
                  ["rear bumper", "left tail lamp"], MARINE, "MDA-2026-0951",
                  [("Rear bumper replacement", 10600), ("Left tail lamp", 5900), ("Painting", 4100), ("Labour", 2300)],
                  ["front_red_hatch"], colour="Red", invoice_offset_days=-2, label="fraud",
                  tells=["photo_mismatch", "invoice_before_incident"],
                  description_for_pack="The photos tell a different story from the claim form."),
    ]
