"""Tests for the new /api/gst/customer-lookup endpoint and Customer Master
auto-hydration + historical snapshot behavior on GST invoices."""
import os
import time
import requests
import pytest
from pathlib import Path

def _load_backend_url():
    env_url = os.environ.get("REACT_APP_BACKEND_URL")
    if env_url:
        return env_url.rstrip("/")
    env_file = Path("/app/frontend/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = _load_backend_url()
ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASS = "Admin@123"
EMP_EMAIL = "employee@k3gas.com"
EMP_PASS = "Employee@123"

# Known seeds referenced in the review request
CUST_WITH_PHONE_NAME = "BUG"
CUST_WITHOUT_PHONE_NAME = "SFG"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Login failed for {email}: {r.status_code} {r.text}")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_headers():
    tok = _login(ADMIN_EMAIL, ADMIN_PASS)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def emp_headers():
    tok = _login(EMP_EMAIL, EMP_PASS)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---- customer-lookup basic ----

def test_lookup_min_2_chars(admin_headers):
    r = requests.get(f"{BASE_URL}/api/gst/customer-lookup?q=B", headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("customers") == []


def test_lookup_returns_matching_customer_shape(admin_headers):
    r = requests.get(f"{BASE_URL}/api/gst/customer-lookup?q={CUST_WITH_PHONE_NAME}", headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    customers = r.json().get("customers", [])
    assert isinstance(customers, list)
    assert len(customers) >= 1
    c = customers[0]
    for k in ("id", "customer_name", "phone", "address", "consumer_no", "connection_type", "warehouse_id", "warehouse_name"):
        assert k in c, f"missing key: {k} in {c.keys()}"


def test_lookup_customer_without_phone_returns_empty_phone(admin_headers):
    r = requests.get(f"{BASE_URL}/api/gst/customer-lookup?q={CUST_WITHOUT_PHONE_NAME}", headers=admin_headers, timeout=15)
    assert r.status_code == 200, r.text
    customers = r.json().get("customers", [])
    sfg = next((c for c in customers if (c.get("customer_name") or "").upper().startswith("SFG")), None)
    if sfg is None:
        pytest.skip("SFG customer not present in DB")
    assert (sfg.get("phone") or "") == "", f"Expected empty phone, got {sfg.get('phone')!r}"


def test_lookup_by_customer_id(admin_headers):
    # first search to get an id
    r = requests.get(f"{BASE_URL}/api/gst/customer-lookup?q={CUST_WITH_PHONE_NAME}", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    lst = r.json().get("customers", [])
    if not lst:
        pytest.skip("no BUG customer to look up by id")
    cid = lst[0]["id"]
    r2 = requests.get(f"{BASE_URL}/api/gst/customer-lookup?customer_id={cid}", headers=admin_headers, timeout=15)
    assert r2.status_code == 200
    body = r2.json()
    assert "customer" in body
    assert body["customer"] is not None
    assert body["customer"]["id"] == cid


def test_lookup_by_unknown_customer_id_returns_null(admin_headers):
    r = requests.get(f"{BASE_URL}/api/gst/customer-lookup?customer_id=does-not-exist", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    assert r.json().get("customer") in (None,)


def test_lookup_non_admin_forbidden(emp_headers):
    r = requests.get(f"{BASE_URL}/api/gst/customer-lookup?q=BUG", headers=emp_headers, timeout=15)
    # gst_billing router is admin-only; must not leak customers to employee
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}: {r.text}"


# ---- Auto-hydration on create ----

def _get_bug_customer(admin_headers):
    r = requests.get(f"{BASE_URL}/api/gst/customer-lookup?q={CUST_WITH_PHONE_NAME}", headers=admin_headers, timeout=15)
    lst = r.json().get("customers", [])
    if not lst:
        pytest.skip("BUG customer not seeded")
    return lst[0]


def test_create_invoice_auto_hydrates_from_master(admin_headers):
    c = _get_bug_customer(admin_headers)
    payload = {
        "customer_id": c["id"],
        "line_items": [{
            "description": "TEST_LOOKUP domestic refill",
            "hsn_code": "27111900",
            "qty": 1,
            "rate": 100.0,
            "gst_rate": 5.0,
            "item_type": "refill",
        }],
    }
    r = requests.post(f"{BASE_URL}/api/gst/invoices", json=payload, headers=admin_headers, timeout=30)
    if r.status_code == 400 and "discrepancy" in r.text.lower():
        # Add reason and retry
        payload["discrepancy_reason"] = "TEST_LOOKUP verification"
        r = requests.post(f"{BASE_URL}/api/gst/invoices", json=payload, headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    inv = r.json()
    assert inv.get("customer_id") == c["id"]
    assert inv.get("customer_name") == c["customer_name"]
    assert inv.get("customer_phone") == (c.get("phone") or "")
    assert inv.get("customer_source") == "master"
    # cleanup
    if inv.get("id"):
        requests.delete(f"{BASE_URL}/api/gst/invoices/{inv['id']}", headers=admin_headers, timeout=15)


def test_create_invoice_without_customer_id_is_manual(admin_headers):
    payload = {
        "customer_name": "TEST_LOOKUP walkin",
        "customer_phone": "9000099000",
        "line_items": [{
            "description": "TEST_LOOKUP walkin refill",
            "hsn_code": "27111900",
            "qty": 1,
            "rate": 250.0,
            "gst_rate": 5.0,
            "item_type": "refill",
        }],
        "discrepancy_reason": "TEST_LOOKUP walkin",
    }
    r = requests.post(f"{BASE_URL}/api/gst/invoices", json=payload, headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    inv = r.json()
    assert inv.get("customer_source") == "manual"
    assert inv.get("customer_name") == "TEST_LOOKUP walkin"
    if inv.get("id"):
        requests.delete(f"{BASE_URL}/api/gst/invoices/{inv['id']}", headers=admin_headers, timeout=15)


# ---- Historical snapshot ----

def test_historical_snapshot_preserved_on_master_update(admin_headers):
    c = _get_bug_customer(admin_headers)
    original_phone = c.get("phone") or ""
    if not original_phone:
        pytest.skip("BUG customer has no phone to snapshot")
    # 1. Create invoice A
    payload_a = {
        "customer_id": c["id"],
        "line_items": [{"description": "TEST_SNAP A", "hsn_code": "27111900", "qty": 1, "rate": 100.0, "gst_rate": 5.0, "item_type": "refill"}],
        "discrepancy_reason": "TEST_SNAP",
    }
    ra = requests.post(f"{BASE_URL}/api/gst/invoices", json=payload_a, headers=admin_headers, timeout=30)
    assert ra.status_code == 200, ra.text
    inv_a = ra.json()
    inv_a_id = inv_a["id"]
    assert inv_a["customer_phone"] == original_phone

    new_phone = "7777700007"
    try:
        # 2. Update master phone
        upd = requests.put(f"{BASE_URL}/api/customers/{c['id']}", json={"phone": new_phone}, headers=admin_headers, timeout=15)
        assert upd.status_code == 200, upd.text

        # 3. Re-fetch invoice A -> phone must be original
        rfa = requests.get(f"{BASE_URL}/api/gst/invoices/{inv_a_id}", headers=admin_headers, timeout=15)
        assert rfa.status_code == 200
        assert rfa.json().get("customer_phone") == original_phone, "historical snapshot was clobbered!"

        # 4. Create invoice B -> should have new phone
        payload_b = dict(payload_a)
        rb = requests.post(f"{BASE_URL}/api/gst/invoices", json=payload_b, headers=admin_headers, timeout=30)
        assert rb.status_code == 200, rb.text
        inv_b = rb.json()
        assert inv_b["customer_phone"] == new_phone
        requests.delete(f"{BASE_URL}/api/gst/invoices/{inv_b['id']}", headers=admin_headers, timeout=15)
    finally:
        # restore master phone
        requests.put(f"{BASE_URL}/api/customers/{c['id']}", json={"phone": original_phone}, headers=admin_headers, timeout=15)
        requests.delete(f"{BASE_URL}/api/gst/invoices/{inv_a_id}", headers=admin_headers, timeout=15)


# ---- Edit invoice must not clobber snapshot from Customer Master ----

def test_update_invoice_preserves_snapshot(admin_headers):
    c = _get_bug_customer(admin_headers)
    original_phone = c.get("phone") or ""
    payload = {
        "customer_id": c["id"],
        "line_items": [{"description": "TEST_EDIT snap", "hsn_code": "27111900", "qty": 1, "rate": 100.0, "gst_rate": 5.0, "item_type": "refill"}],
        "discrepancy_reason": "TEST_EDIT",
    }
    r = requests.post(f"{BASE_URL}/api/gst/invoices", json=payload, headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    inv = r.json()
    inv_id = inv["id"]
    try:
        # Change master phone
        requests.put(f"{BASE_URL}/api/customers/{c['id']}", json={"phone": "6666600006"}, headers=admin_headers, timeout=15)
        # Now update invoice (change remarks only)
        u = requests.put(f"{BASE_URL}/api/gst/invoices/{inv_id}", json={"remarks": "edited by TEST_EDIT"}, headers=admin_headers, timeout=15)
        assert u.status_code == 200, u.text
        # Refetch -> phone must still be original
        rf = requests.get(f"{BASE_URL}/api/gst/invoices/{inv_id}", headers=admin_headers, timeout=15)
        assert rf.status_code == 200
        assert rf.json().get("customer_phone") == original_phone, "edit clobbered historical snapshot"
    finally:
        requests.put(f"{BASE_URL}/api/customers/{c['id']}", json={"phone": original_phone}, headers=admin_headers, timeout=15)
        requests.delete(f"{BASE_URL}/api/gst/invoices/{inv_id}", headers=admin_headers, timeout=15)
