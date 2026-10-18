"""Deterministic rules for the health and property lines, on the demo scenarios."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import lines_data as L  # noqa: E402
from lines_seed import health_extracted, property_extracted  # noqa: E402

from app.lines import health, property as prop  # noqa: E402


def h_codes(s):
    r = health_extracted(s)
    return {f.code for f in health.policy_rules(r, s.policy_record()) + health.doc_rules(r)}


def p_codes(s):
    r = property_extracted(s)
    r.work_address, r.property_address = s.work_address or s.address, s.loss_address or s.address
    return {f.code for f in prop.policy_rules(r, s.policy_record()) + prop.doc_rules(r)}


def test_health_scenarios():
    by_id = {s.id: s for s in L.health_claims() + [L.health_pack()]}
    assert h_codes(by_id["demo-h-appendix"]) == set()
    assert h_codes(by_id["demo-h-dengue"]) == set()
    assert {"SPECIFIC_WAITING_PERIOD", "ROOM_RENT_ABOVE_LIMIT"} <= h_codes(by_id["demo-h-knee"])
    assert {"BILL_ARITHMETIC", "CLAIM_ABOVE_BILL"} <= h_codes(by_id["demo-h-inflated"])
    assert h_codes(by_id["demo-h-ring"]) == set()      # only the Linker should catch the ring
    assert h_codes(by_id["live-health-ring"]) == set()


def test_property_scenarios():
    by_id = {s.id: s for s in L.property_claims() + [L.property_pack()]}
    assert p_codes(by_id["demo-p-pipe"]) == set()
    assert p_codes(by_id["demo-p-fire"]) == set()
    assert {"NO_POLICE_REPORT", "EARLY_CLAIM"} <= p_codes(by_id["demo-p-burglary"])
    assert {"INVOICE_SITE_MISMATCH", "INVOICE_BEFORE_INCIDENT"} <= p_codes(by_id["demo-p-address"])
    assert p_codes(by_id["demo-p-ring"]) == set()


def test_entities_use_provider_kinds():
    h = {e["kind"] for e in health.entities(health_extracted(L.health_claims()[4]))}
    p = {e["kind"] for e in prop.entities(property_extracted(L.property_claims()[4]))}
    assert {"hospital", "doctor", "bill", "bank", "phone"} <= h and "garage" not in h
    assert {"contractor", "invoice", "address", "bank", "phone"} <= p and "garage" not in p
