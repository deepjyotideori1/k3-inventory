"""
GST Billing - Connection Plans feature tests.
Covers:
- Plan seeding (11 default plans: 4 domestic + 7 commercial)
- Plan CRUD (GET list/single, POST create, PUT update, DELETE soft-delete)
- Validation (name required, at least one item)
- Access control (non-admin gets 403)
- Auto-gen with plan when all rates set (multi-line invoice)
- Auto-gen fallback to single-line when rates unset
- has_accessories toggle picks correct plan
- Double-cylinder plan selection
- Refill stays single-line (no plan lookup)
- Explicit connection_plan_id override
"""
import os
import pytest
import requests
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@k3gas.com", "password": "Admin@123"}
MGR = {"email": "jullang@k3gas.com", "password": "Jullang@123"}

EXPECTED_PLAN_TYPES = {
    "domestic_single_basic", "domestic_single_full",
    "domestic_double_basic", "domestic_double_full",
    "commercial_1", "commercial_2", "commercial_3",
    "commercial_4", "commercial_6", "commercial_10", "commercial_15",
}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def admin_headers():
    tok = _login(ADMIN)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mgr_headers():
    tok = _login(MGR)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def warehouse_id(admin_headers):
    r = requests.get(f"{API}/warehouses", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    whs = r.json()
    assert whs
    return whs[0]["id"]


def _find_invoice_by_sale(headers, sale_id):
    r = requests.get(f"{API}/gst/invoices?limit=200", headers=headers, timeout=30)
    for inv in r.json()["invoices"]:
        if inv.get("sale_id") == sale_id:
            return inv
    return None


def _get_plan_by_type(headers, plan_type):
    r = requests.get(f"{API}/gst/plans", headers=headers, timeout=30)
    assert r.status_code == 200
    for p in r.json():
        if p["plan_type"] == plan_type:
            return p
    return None


# -------------------- ACCESS CONTROL --------------------
class TestPlanAccess:
    def test_non_admin_blocked(self, mgr_headers):
        r = requests.get(f"{API}/gst/plans", headers=mgr_headers, timeout=30)
        assert r.status_code == 403


# -------------------- SEEDING --------------------
class TestPlanSeeding:
    def test_11_plans_seeded(self, admin_headers):
        r = requests.get(f"{API}/gst/plans", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        plans = r.json()
        # only active default ones - but seed only happens once; previous tests may have added/soft-deleted
        types = {p["plan_type"] for p in plans}
        missing = EXPECTED_PLAN_TYPES - types
        assert not missing, f"Missing default plan_types: {missing}"

    def test_domestic_single_full_has_stove_burner(self, admin_headers):
        plan = _get_plan_by_type(admin_headers, "domestic_single_full")
        assert plan is not None
        names = [it["item_name"] for it in plan["items"]]
        assert "Two Stove Burner" in names
        assert plan["has_accessories"] is True
        assert plan["connection_type"] == "domestic"
        assert plan["cylinder_count"] == 1
        # 9 items in 'with accessories' single
        assert len(plan["items"]) == 9

    def test_domestic_single_basic_8_items(self, admin_headers):
        plan = _get_plan_by_type(admin_headers, "domestic_single_basic")
        assert plan and plan["has_accessories"] is False
        assert plan["cylinder_count"] == 1
        assert len(plan["items"]) == 8

    def test_get_single_plan(self, admin_headers):
        plan = _get_plan_by_type(admin_headers, "commercial_1")
        r = requests.get(f"{API}/gst/plans/{plan['id']}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == plan["id"]
        assert body["connection_type"] == "commercial"
        assert len(body["items"]) >= 5


# -------------------- CRUD --------------------
class TestPlanCRUD:
    def test_create_validation_missing_name(self, admin_headers):
        r = requests.post(f"{API}/gst/plans",
                          json={"items": [{"item_name": "X", "quantity": 1, "gst_rate": 18}]},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_create_validation_no_items(self, admin_headers):
        r = requests.post(f"{API}/gst/plans",
                          json={"name": "TEST_NoItems", "items": []},
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_create_and_delete_custom_plan(self, admin_headers):
        payload = {
            "name": "TEST_CustomPlan",
            "plan_type": "test_custom",
            "connection_type": "domestic",
            "cylinder_count": 1,
            "has_accessories": False,
            "items": [
                {"item_name": "TEST_Item1", "hsn": "111", "unit": "Nos",
                 "quantity": 1, "gst_rate": 18, "unit_price": 100},
            ],
        }
        r = requests.post(f"{API}/gst/plans", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        # delete (soft)
        r = requests.delete(f"{API}/gst/plans/{pid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        # verify soft delete
        r = requests.get(f"{API}/gst/plans/{pid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["is_active"] is False


# -------------------- AUTO-GEN with Plan --------------------
def _set_plan_prices(headers, plan, price=100.0):
    """Update plan items to all have unit_price=price."""
    items = [{**it, "unit_price": price} for it in plan["items"]]
    r = requests.put(f"{API}/gst/plans/{plan['id']}", json={"items": items},
                     headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _reset_plan_prices(headers, plan):
    items = [{**it, "unit_price": 0} for it in plan["items"]]
    requests.put(f"{API}/gst/plans/{plan['id']}", json={"items": items},
                 headers=headers, timeout=30)


def _create_sale(headers, warehouse_id, **overrides):
    payload = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "consumer_name": "TEST_PlanAuto",
        "address": "Addr",
        "connection_type": "domestic",
        "cylinder_nos": "1",
        "amount": 5000,
        "payment_mode": "cash",
        "warehouse_id": warehouse_id,
    }
    payload.update(overrides)
    r = requests.post(f"{API}/sales-entries/warehouse/{warehouse_id}",
                      json=payload, headers=headers, timeout=60)
    assert r.status_code in (200, 201), f"Sale create failed: {r.status_code} {r.text[:300]}"
    return r.json()


class TestAutoGenWithPlan:
    def test_domestic_single_basic_plan(self, admin_headers, warehouse_id):
        plan = _get_plan_by_type(admin_headers, "domestic_single_basic")
        _set_plan_prices(admin_headers, plan, 100)
        try:
            sale = _create_sale(admin_headers, warehouse_id,
                                connection_type="domestic", cylinder_nos="1",
                                has_accessories=False, consumer_name="TEST_PlanBasic")
            inv = _find_invoice_by_sale(admin_headers, sale["id"])
            assert inv is not None, "Auto-gen invoice not created"
            assert len(inv["line_items"]) == 8, f"Expected 8 lines, got {len(inv['line_items'])}"
            # Verify a known item (Cooker) present with correct HSN
            cooker = next((li for li in inv["line_items"] if "Cooker" in li.get("item_name", "")), None)
            assert cooker is not None
            assert cooker["hsn"] == "73211110"
            assert cooker["rate"] == 100.0
            assert inv["bill_type"] == "new_connection"
        finally:
            _reset_plan_prices(admin_headers, plan)

    def test_domestic_single_full_with_accessories(self, admin_headers, warehouse_id):
        plan = _get_plan_by_type(admin_headers, "domestic_single_full")
        _set_plan_prices(admin_headers, plan, 50)
        try:
            sale = _create_sale(admin_headers, warehouse_id,
                                connection_type="domestic", cylinder_nos="1",
                                has_accessories=True, consumer_name="TEST_PlanFull")
            inv = _find_invoice_by_sale(admin_headers, sale["id"])
            assert inv is not None
            assert len(inv["line_items"]) == 9, f"Expected 9 lines, got {len(inv['line_items'])}"
            stove = next((li for li in inv["line_items"]
                          if "Stove Burner" in li.get("item_name", "")), None)
            assert stove is not None, "Two Stove Burner should be in plan"
        finally:
            _reset_plan_prices(admin_headers, plan)

    def test_domestic_double_basic(self, admin_headers, warehouse_id):
        plan = _get_plan_by_type(admin_headers, "domestic_double_basic")
        _set_plan_prices(admin_headers, plan, 100)
        try:
            sale = _create_sale(admin_headers, warehouse_id,
                                connection_type="domestic", cylinder_nos="2",
                                has_accessories=False, consumer_name="TEST_DoubleBasic")
            inv = _find_invoice_by_sale(admin_headers, sale["id"])
            assert inv is not None
            # Should use double_basic plan (8 items)
            assert len(inv["line_items"]) == 8
            # Double cyl: Empty Cylinder qty should be 2
            empty = next((li for li in inv["line_items"]
                          if "Empty Cylinder" in li.get("item_name", "")), None)
            assert empty is not None
            assert empty["quantity"] == 2
        finally:
            _reset_plan_prices(admin_headers, plan)

    def test_commercial_fallback_when_rates_unset(self, admin_headers, warehouse_id):
        # Commercial plans default to unit_price=0 (no rates set) -> single line fallback
        sale = _create_sale(admin_headers, warehouse_id,
                            connection_type="commercial", cylinder_nos="1",
                            amount=20000, consumer_name="TEST_CommFallback")
        inv = _find_invoice_by_sale(admin_headers, sale["id"])
        assert inv is not None
        # Fallback = single line
        assert len(inv["line_items"]) == 1
        assert "Commercial New Connection" in inv["line_items"][0]["item_name"]

    def test_refill_single_line(self, admin_headers, warehouse_id):
        sale_payload = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "consumer_name": "TEST_RefillSingle",
            "connection_type": "domestic_refill",
            "no_of_refills": 1,
            "amount": 1100,
            "payment_mode": "cash",
            "warehouse_id": warehouse_id,
        }
        r = requests.post(f"{API}/sales-entries/warehouse/{warehouse_id}",
                          json=sale_payload, headers=admin_headers, timeout=60)
        assert r.status_code in (200, 201)
        sale = r.json()
        inv = _find_invoice_by_sale(admin_headers, sale["id"])
        assert inv is not None
        # Refills always single-line regardless of plans
        assert len(inv["line_items"]) == 1
        assert inv["bill_type"] == "refill"

    def test_explicit_plan_id_override(self, admin_headers, warehouse_id):
        """Pass connection_plan_id explicitly - backend should use that plan."""
        plan = _get_plan_by_type(admin_headers, "domestic_single_full")
        _set_plan_prices(admin_headers, plan, 75)
        try:
            # Pass plan_id explicitly even though has_accessories=False
            sale = _create_sale(admin_headers, warehouse_id,
                                connection_type="domestic", cylinder_nos="1",
                                has_accessories=False,
                                connection_plan_id=plan["id"],
                                consumer_name="TEST_ExplicitPlan")
            inv = _find_invoice_by_sale(admin_headers, sale["id"])
            assert inv is not None
            # Should match domestic_single_full (9 items) since explicit plan_id given
            assert len(inv["line_items"]) == 9, \
                f"Expected explicit plan with 9 lines, got {len(inv['line_items'])}"
        finally:
            _reset_plan_prices(admin_headers, plan)
