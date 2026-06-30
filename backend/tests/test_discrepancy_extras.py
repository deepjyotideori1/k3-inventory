"""Additional backend regression for Discrepancy feature (PUT flow + sales endpoints).

Endpoints under test:
- PUT  /api/gst/invoices/{id}                  (mismatch edit requires reason; clearing restores)
- POST /api/sales-entries                      (sales-entry discrepancy guard)
- POST /api/warehouse-sales-entries            (warehouse sales discrepancy guard)
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
    ids = []
    yield ids
    for inv_id in ids:
        try:
            requests.delete(f"{API}/gst/invoices/{inv_id}", headers=auth_headers, timeout=10)
        except Exception:
            pass


def _make_clean_invoice(auth_headers):
    """Helper to create a clean (non-discrepancy) invoice for PUT tests."""
    r = requests.get(f"{API}/gst/items", headers=auth_headers, timeout=10)
    items = r.json()
    refill = next(it for it in items if it["name"] == "Domestic LPG Refill")
    master_rate = float(refill["default_rate"])
    gst = float(refill["gst_rate"])
    taxable = round(master_rate * 100.0 / (100.0 + gst), 2)
    create = requests.post(f"{API}/gst/invoices", headers=auth_headers, json={
        "customer_name": f"DISC_PUT_{uuid.uuid4().hex[:6]}",
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{"item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder",
                        "gst_rate": gst, "quantity": 1, "rate": taxable}],
    }, timeout=10)
    assert create.status_code == 200, create.text
    return create.json(), taxable, gst


# --- PUT flow: existing invoice edited to mismatch ---
def test_put_invoice_mismatch_requires_reason(auth_headers, cleanup_invoices):
    inv, _, gst = _make_clean_invoice(auth_headers)
    cleanup_invoices.append(inv["id"])
    assert inv["is_discrepancy"] is False

    # Edit to a wildly wrong rate without reason
    body = {
        "customer_name": inv["customer_name"],
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{"item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder",
                        "gst_rate": gst, "quantity": 1, "rate": 90000.0}],
    }
    r = requests.put(f"{API}/gst/invoices/{inv['id']}", headers=auth_headers, json=body, timeout=10)
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    detail = r.json().get("detail")
    assert isinstance(detail, dict) and detail.get("code") == "discrepancy_requires_reason"

    # With reason, it should succeed
    body["discrepancy_reason"] = "Reason for high amount via PUT"
    r2 = requests.put(f"{API}/gst/invoices/{inv['id']}", headers=auth_headers, json=body, timeout=10)
    assert r2.status_code == 200, r2.text
    updated = r2.json()
    assert updated["is_discrepancy"] is True
    assert updated["discrepancy_status"] == "pending"


def test_put_invoice_back_to_match_clears_discrepancy(auth_headers, cleanup_invoices):
    """Editing a discrepant invoice back to a matching amount clears discrepancy_status."""
    # Create discrepant first
    r = requests.post(f"{API}/gst/invoices", headers=auth_headers, json={
        "customer_name": f"DISC_PUTClear_{uuid.uuid4().hex[:6]}",
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{"item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder",
                        "gst_rate": 5, "quantity": 1, "rate": 5000}],
        "discrepancy_reason": "Initial mismatch",
    }, timeout=10)
    assert r.status_code == 200
    inv = r.json()
    cleanup_invoices.append(inv["id"])
    assert inv["is_discrepancy"] is True

    # Determine matching taxable rate
    items_r = requests.get(f"{API}/gst/items", headers=auth_headers, timeout=10)
    refill = next(it for it in items_r.json() if it["name"] == "Domestic LPG Refill")
    master_rate = float(refill["default_rate"])
    gst = float(refill["gst_rate"])
    taxable = round(master_rate * 100.0 / (100.0 + gst), 2)

    body = {
        "customer_name": inv["customer_name"],
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{"item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder",
                        "gst_rate": gst, "quantity": 1, "rate": taxable}],
    }
    r2 = requests.put(f"{API}/gst/invoices/{inv['id']}", headers=auth_headers, json=body, timeout=10)
    assert r2.status_code == 200, r2.text
    fixed = r2.json()
    assert fixed["is_discrepancy"] is False
    # status should be either cleared or set to 'corrected' — the spec says cleared/corrected
    assert fixed.get("discrepancy_status") in (None, "", "corrected")


# --- List filter regression ---
def test_list_discrepancies_status_filter(auth_headers, cleanup_invoices):
    r = requests.post(f"{API}/gst/invoices", headers=auth_headers, json={
        "customer_name": f"DISC_Filter_{uuid.uuid4().hex[:6]}",
        "tax_mode": "intra_state",
        "bill_type": "manual",
        "line_items": [{"item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder",
                        "gst_rate": 5, "quantity": 1, "rate": 5000}],
        "discrepancy_reason": "Filter test",
    }, timeout=10)
    assert r.status_code == 200
    inv = r.json()
    cleanup_invoices.append(inv["id"])

    r2 = requests.get(f"{API}/gst/discrepancies", headers=auth_headers, params={"status": "pending"}, timeout=10)
    assert r2.status_code == 200
    body = r2.json()
    assert all(row["discrepancy_status"] == "pending" for row in body["rows"])
    assert inv["id"] in [row["id"] for row in body["rows"]]


# --- Sales endpoints discrepancy guard (best-effort: skip if validation not wired) ---
def test_sales_entries_discrepancy_guard_optional(auth_headers):
    """POST /api/sales-entries/warehouse/{id} should reject mismatched refill amount without reason."""
    # Discover a warehouse id
    wh_resp = requests.get(f"{API}/warehouses", headers=auth_headers, timeout=10)
    if wh_resp.status_code != 200:
        pytest.skip("No warehouses endpoint")
    wh_list = wh_resp.json()
    wh_list = wh_list if isinstance(wh_list, list) else wh_list.get("items", [])
    jullang = next((w for w in wh_list if w.get("name") == "Jullang"), None)
    if not jullang:
        pytest.skip("Jullang warehouse not found")
    wh_id = jullang["id"]

    payload = {
        "date": "2026-01-15",
        "consumer_name": f"DISC_Sales_{uuid.uuid4().hex[:6]}",
        "connection_type": "domestic_refill",
        "no_of_refills": 1,
        "amount": 999999.0,
        "payment_mode": "cash",
        "cash_amount": 999999.0,
    }
    r = requests.post(f"{API}/sales-entries/warehouse/{wh_id}", headers=auth_headers, json=payload, timeout=10)
    assert r.status_code == 400, f"Expected 400 mismatch guard, got {r.status_code}: {r.text}"
    detail = r.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "discrepancy_requires_reason"
    assert detail.get("expected_amount") is not None
    assert detail.get("actual_amount") == 999999.0

    # Retry with reason
    payload["discrepancy_reason"] = "Test sales discrepancy"
    r2 = requests.post(f"{API}/sales-entries/warehouse/{wh_id}", headers=auth_headers, json=payload, timeout=10)
    assert r2.status_code in (200, 201), f"With reason expected 200, got {r2.status_code}: {r2.text}"
    saved = r2.json()
    assert saved.get("amount") == 999999.0
