from app.agents.linker import entities
from app.rules import action_for, document_rules, policy_rules, risk_score
from app.schemas import Invoice, LineItem, ReaderOutput


def reader(**kw) -> ReaderOutput:
    base = dict(
        documents=[], claimant_name="Rahul Sharma", claimant_phone="+91 98765 43210", claimant_email=None,
        bank_account="123456789012", bank_ifsc=None, policy_number="PCP-1", vehicle_registration="MH 12 AB 1234",
        vehicle_make_model=None, vehicle_colour=None, incident_date="2026-09-10", incident_time=None,
        incident_location=None, incident_description=None, damage_areas_claimed=[], claim_amount=20000,
        filed_date="2026-09-11", police_report_number=None, invoice=None, photo_observations=[],
    )
    return ReaderOutput(**{**base, **kw})


POLICY = {"holderName": "Rahul Sharma", "vehicleRegistration": "MH12AB1234", "startDate": "2026-01-01",
          "endDate": "2026-12-31", "idv": 500000}


def codes(flags):
    return {f.code for f in flags}


def test_clean_claim_is_fast_tracked():
    r = reader()
    flags = policy_rules(r, POLICY) + document_rules(r)
    assert flags == []
    assert action_for(risk_score(flags), []) == "fast_track"


def test_policy_rules():
    r = reader(incident_date="2026-01-10", vehicle_registration="KA01ZZ9999", claimant_name="Amit Verma")
    assert {"EARLY_CLAIM", "VEHICLE_MISMATCH", "HOLDER_MISMATCH"} <= codes(policy_rules(r, POLICY))
    assert codes(policy_rules(reader(incident_date="2027-02-01"), POLICY)) == {"INCIDENT_OUTSIDE_PERIOD"}


def test_invoice_rules():
    inv = Invoice(number="77", date="2026-09-01", garage_name="Speedfix", garage_gstin="27ABC", garage_phone=None,
                  line_items=[LineItem(description="bumper", amount=10000), LineItem(description="paint", amount=5000)],
                  subtotal=18000, tax=3240, total=21240, name_on_invoice="Rahul Sharma", vehicle_on_invoice=None)
    c = codes(document_rules(reader(invoice=inv, claim_amount=30000)))
    assert {"INVOICE_BEFORE_INCIDENT", "INVOICE_ARITHMETIC", "CLAIM_ABOVE_INVOICE"} <= c


def test_entities_normalised():
    inv = Invoice(number="inv-77", date=None, garage_name="Speedfix Motors", garage_gstin="27 abc", garage_phone=None,
                  line_items=[], subtotal=None, tax=None, total=None, name_on_invoice=None, vehicle_on_invoice=None)
    keys = {e["key"] for e in entities(reader(invoice=inv))}
    assert {"phone:9876543210", "bank:123456789012", "vehicle:MH12AB1234", "garage:27ABC",
            "invoice:27ABC/INV77"} == keys


def test_plate_with_model_suffix_is_not_a_mismatch():
    from app.rules import plates_match
    assert plates_match("MH 02 FA 1187 · Hyundai i20 Asta", "MH02FA1187")
    assert not plates_match("MH 02 FA 1188", "MH 02 FA 1187")
