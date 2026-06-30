"""Backend regression for Amount Mismatch & Discrepancy Invoice Detection.

Endpoints under test:
- POST /api/gst/invoices                              (rejects on mismatch + no reason)
- POST /api/gst/invoices  (with discrepancy_reason)   (saves with discrepancy fields)
- GET  /api/gst/discrepancies                         (lists discrepancies + summary)
- POST /api/gst/discrepancies/{id}/review             (approve/reject + audit)
- POST /api/gst/discrepancies/{id}/correct            (admin re-edit)
- GET  /api/gst/reports/discrepancy_invoices          (report data)
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASS = "Admin@123"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=10)
    r.raise_for_status()
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def cleanup_invoices(auth_headers):
    created_ids = []
    yield created_ids
    for inv_id in created_ids:
        try:
            requests.delete(f"{API}/gst/invoices/{inv_id}", headers=auth_headers, timeout=10)
        except Exception:
            pass


def test_create_invoice_with_mismatch_no_reason_rejected(auth_headers):
    """Server must return 400 with discrepancy details when amount mismatches and no reason given."""
    r = requests.post(f"{API}/gst/invoices", headers=auth_headers, json={
        "customer_name": f"DISC_NoReason_{uuid.uuid4().hex[:6]}",
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{
            "item_name": "Domestic LPG Refill",
            "hsn": "271119",
            "unit": "Cylinder",
            "gst_rate": 5,
            "quantity": 1,
            "rate": 50000.0,   # absurdly high; item-master = ~₹952.38 taxable + 5% = ₹1000
        }],
    }, timeout=10)
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    body = r.json()
    detail = body.get("detail")
    assert isinstance(detail, dict), f"detail should be a dict, got {type(detail).__name__}"
    assert detail.get("code") == "discrepancy_requires_reason"
    assert "expected_amount" in detail and "actual_amount" in detail and "discrepancy_amount" in detail


def test_create_invoice_with_mismatch_and_reason_saves(auth_headers, cleanup_invoices):
    """With discrepancy_reason, the invoice is saved with discrepancy fields populated."""
    r = requests.post(f"{API}/gst/invoices", headers=auth_headers, json={
        "customer_name": f"DISC_WithReason_{uuid.uuid4().hex[:6]}",
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{
            "item_name": "Domestic LPG Refill",
            "hsn": "271119",
            "unit": "Cylinder",
            "gst_rate": 5,
            "quantity": 1,
            "rate": 99999.0,
        }],
        "discrepancy_reason": "Customer paid early-adopter bonus of ₹103,499",
    }, timeout=10)
    assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
    inv = r.json()
    cleanup_invoices.append(inv["id"])
    assert inv["is_discrepancy"] is True
    assert inv["discrepancy_amount"] > 0
    assert inv["discrepancy_status"] == "pending"
    assert "early-adopter bonus" in inv["discrepancy_reason"]
    assert inv["expected_amount"] is not None
    assert inv["actual_amount"] is not None


def test_list_discrepancies_includes_new_invoice(auth_headers, cleanup_invoices):
    # Create one
    r = requests.post(f"{API}/gst/invoices", headers=auth_headers, json={
        "customer_name": f"DISC_ListCheck_{uuid.uuid4().hex[:6]}",
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{"item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder", "gst_rate": 5, "quantity": 1, "rate": 5000}],
        "discrepancy_reason": "Test list discrepancy",
    }, timeout=10)
    assert r.status_code == 200
    inv = r.json()
    cleanup_invoices.append(inv["id"])

    r2 = requests.get(f"{API}/gst/discrepancies", headers=auth_headers, timeout=10)
    assert r2.status_code == 200
    body = r2.json()
    assert "summary" in body and "rows" in body
    ids = [x["id"] for x in body["rows"]]
    assert inv["id"] in ids
    summary = body["summary"]
    assert summary["total"] >= 1
    assert summary["pending"] >= 1


def test_review_approve(auth_headers, cleanup_invoices):
    r = requests.post(f"{API}/gst/invoices", headers=auth_headers, json={
        "customer_name": f"DISC_ApproveTest_{uuid.uuid4().hex[:6]}",
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{"item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder", "gst_rate": 5, "quantity": 1, "rate": 4500}],
        "discrepancy_reason": "Bulk pricing offered",
    }, timeout=10)
    assert r.status_code == 200
    inv = r.json()
    cleanup_invoices.append(inv["id"])
    # Approve
    r2 = requests.post(f"{API}/gst/discrepancies/{inv['id']}/review", headers=auth_headers,
                       json={"action": "approve", "note": "Verified with manager"}, timeout=10)
    assert r2.status_code == 200
    approved = r2.json()
    assert approved["discrepancy_status"] == "approved"
    assert approved["discrepancy_reviewed_by_name"]
    assert approved["discrepancy_review_note"] == "Verified with manager"


def test_review_reject(auth_headers, cleanup_invoices):
    r = requests.post(f"{API}/gst/invoices", headers=auth_headers, json={
        "customer_name": f"DISC_RejectTest_{uuid.uuid4().hex[:6]}",
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{"item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder", "gst_rate": 5, "quantity": 1, "rate": 100}],
        "discrepancy_reason": "Suspiciously low",
    }, timeout=10)
    assert r.status_code == 200
    inv = r.json()
    cleanup_invoices.append(inv["id"])
    r2 = requests.post(f"{API}/gst/discrepancies/{inv['id']}/review", headers=auth_headers,
                       json={"action": "reject", "note": "Reject — invalid reason"}, timeout=10)
    assert r2.status_code == 200
    assert r2.json()["discrepancy_status"] == "rejected"


def test_correct_endpoint_clears_discrepancy_when_matched(auth_headers, cleanup_invoices):
    """Admin uses /correct to overwrite line_items so amount matches expected → status becomes 'corrected'."""
    r = requests.post(f"{API}/gst/invoices", headers=auth_headers, json={
        "customer_name": f"DISC_CorrectTest_{uuid.uuid4().hex[:6]}",
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{"item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder", "gst_rate": 5, "quantity": 1, "rate": 5000}],
        "discrepancy_reason": "Will be corrected",
    }, timeout=10)
    assert r.status_code == 200
    inv = r.json()
    cleanup_invoices.append(inv["id"])
    expected = inv["expected_amount"]
    # Build a line_items that match the expected grand_total (default Item Master rate 1000 incl)
    taxable_per_unit = round(expected * 100.0 / 105.0, 2)
    r2 = requests.post(f"{API}/gst/discrepancies/{inv['id']}/correct", headers=auth_headers, json={
        "line_items": [{"item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder", "gst_rate": 5, "quantity": 1, "rate": taxable_per_unit}],
        "note": "Corrected by admin",
    }, timeout=10)
    assert r2.status_code == 200, r2.text
    fixed = r2.json()
    # After correction, mismatch should be cleared and status='corrected'
    assert fixed["is_discrepancy"] is False
    assert fixed["discrepancy_status"] == "corrected"


def test_discrepancy_report(auth_headers, cleanup_invoices):
    r = requests.post(f"{API}/gst/invoices", headers=auth_headers, json={
        "customer_name": f"DISC_ReportTest_{uuid.uuid4().hex[:6]}",
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{"item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder", "gst_rate": 5, "quantity": 1, "rate": 7000}],
        "discrepancy_reason": "Report test",
    }, timeout=10)
    assert r.status_code == 200
    inv = r.json()
    cleanup_invoices.append(inv["id"])
    r2 = requests.get(f"{API}/gst/reports/discrepancy_invoices", headers=auth_headers, timeout=10)
    assert r2.status_code == 200
    body = r2.json()
    assert body["label"] == "Discrepancy Invoices Report"
    assert "summary" in body and "rows" in body and "columns" in body
    cols = [c.get("key") if isinstance(c, dict) else c for c in body["columns"]]
    # The structure may be tuple-like — accept either
    assert any("difference" in str(c).lower() or "diff" in str(c).lower() for c in cols)
    inv_nos = [r["invoice_number"] for r in body["rows"]]
    assert inv["invoice_number"] in inv_nos


def test_tolerance_within_1_rupee_no_flag(auth_headers, cleanup_invoices):
    """A small ±₹1 rounding difference should NOT be flagged as discrepancy."""
    # Find the active Item Master rate for Domestic LPG Refill dynamically
    r0 = requests.get(f"{API}/gst/items", headers=auth_headers, timeout=10)
    items = r0.json()
    refill = next(it for it in items if it["name"] == "Domestic LPG Refill")
    master_rate = float(refill["default_rate"])  # inclusive total
    gst = float(refill["gst_rate"])
    # Build a single-line invoice whose grand_total is within ±₹0.5 of master_rate
    taxable = round((master_rate - 0.4) * 100.0 / (100.0 + gst), 2)
    r = requests.post(f"{API}/gst/invoices", headers=auth_headers, json={
        "customer_name": f"DISC_Tolerance_{uuid.uuid4().hex[:6]}",
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{
            "item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder",
            "gst_rate": gst, "quantity": 1, "rate": taxable,
        }],
    }, timeout=10)
    assert r.status_code == 200, f"Should NOT require reason: {r.text}"
    inv = r.json()
    cleanup_invoices.append(inv["id"])
    assert inv["is_discrepancy"] is False
