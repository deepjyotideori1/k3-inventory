"""
Tests for Auto-Sync Item Master <-> Connection Plans feature.
Covers: backfill, cascade rename/hsn/unit/gst_rate, deactivate, reactivate,
historical invoice invariant, plan items[].item_id preservation,
non-admin 403 on activate.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@k3gas.com", "password": "Admin@123"}
JULLANG = {"email": "jullang@k3gas.com", "password": "Jullang@123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="session")
def jullang_token():
    try:
        return _login(JULLANG)
    except AssertionError:
        pytest.skip("Jullang manager login unavailable")


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- BACKFILL ----------
class TestBackfill:
    def test_backfill_links_master_items(self, admin_headers):
        r = requests.get(f"{API}/gst/plans", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        plans = r.json()
        assert isinstance(plans, list) and len(plans) > 0
        total = linked = 0
        for p in plans:
            for it in p.get("items", []):
                total += 1
                if it.get("item_id"):
                    linked += 1
        assert total > 0
        assert linked > 0, "expected at least some plan items to be backfilled"
        print(f"Backfill: {linked}/{total} plan items linked")

    def test_known_items_are_linked(self, admin_headers):
        items_r = requests.get(f"{API}/gst/items", headers=admin_headers).json()
        name_to_id = {i["name"].lower(): i["id"] for i in items_r}
        plans = requests.get(f"{API}/gst/plans", headers=admin_headers).json()
        target = "domestic regulator"
        target_id = name_to_id.get(target)
        assert target_id
        found_linked = any(
            it.get("item_id") == target_id
            for p in plans for it in p.get("items", [])
            if (it.get("item_name") or "").strip().lower() == target
        )
        assert found_linked, "'Domestic Regulator' should be linked in at least one plan"


# ---------- CASCADE UPDATE ----------
class TestCascadeUpdate:
    @pytest.fixture
    def temp_item(self, admin_headers):
        # create dedicated item + plan to avoid touching seed
        item_payload = {
            "name": f"TEST_ItemMaster_{uuid.uuid4().hex[:6]}",
            "hsn": "12345678",
            "unit": "Nos",
            "gst_rate": 18,
            "default_rate": 100,
        }
        item = requests.post(f"{API}/gst/items", json=item_payload,
                             headers=admin_headers).json()
        yield item
        # cleanup not strictly necessary; soft-delete
        requests.delete(f"{API}/gst/items/{item['id']}", headers=admin_headers)

    @pytest.fixture
    def temp_plan(self, admin_headers, temp_item):
        plan_payload = {
            "name": f"TEST_Plan_{uuid.uuid4().hex[:6]}",
            "plan_type": "custom",
            "connection_type": "domestic",
            "cylinder_count": 1,
            "has_accessories": False,
            "items": [{
                "item_id": temp_item["id"],
                "item_name": temp_item["name"],
                "hsn": temp_item["hsn"],
                "unit": temp_item["unit"],
                "gst_rate": temp_item["gst_rate"],
                "quantity": 1,
                "unit_price": 250,
            }],
        }
        p = requests.post(f"{API}/gst/plans", json=plan_payload,
                          headers=admin_headers)
        assert p.status_code == 200, p.text
        plan = p.json()
        yield plan
        requests.delete(f"{API}/gst/plans/{plan['id']}", headers=admin_headers)

    def test_post_plan_preserves_item_id(self, temp_plan, temp_item):
        items = temp_plan["items"]
        assert len(items) == 1
        assert items[0]["item_id"] == temp_item["id"]

    def test_cascade_name_hsn_unit_gst(self, admin_headers, temp_item, temp_plan):
        new_name = temp_item["name"] + " (Updated)"
        r = requests.put(
            f"{API}/gst/items/{temp_item['id']}",
            json={"name": new_name, "hsn": "99999999", "unit": "Set", "gst_rate": 12},
            headers=admin_headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "affected_plans" in data
        assert data["affected_plans"] >= 1

        # Fetch the plan to verify cascade
        plan = requests.get(f"{API}/gst/plans/{temp_plan['id']}",
                            headers=admin_headers).json()
        line = plan["items"][0]
        assert line["item_name"] == new_name
        assert line["hsn"] == "99999999"
        assert line["unit"] == "Set"
        assert float(line["gst_rate"]) == 12.0
        # unit_price MUST NOT cascade
        assert float(line["unit_price"]) == 250.0

    def test_cascade_excludes_unit_price(self, admin_headers, temp_item, temp_plan):
        # update default_rate on master should NOT change plan unit_price
        requests.put(
            f"{API}/gst/items/{temp_item['id']}",
            json={"default_rate": 9999},
            headers=admin_headers,
        )
        plan = requests.get(f"{API}/gst/plans/{temp_plan['id']}",
                            headers=admin_headers).json()
        assert float(plan["items"][0]["unit_price"]) == 250.0


# ---------- DEACTIVATE / REACTIVATE ----------
class TestActivateDeactivate:
    @pytest.fixture
    def temp_item(self, admin_headers):
        p = {"name": f"TEST_Toggle_{uuid.uuid4().hex[:6]}", "hsn": "1", "unit": "Nos", "gst_rate": 5}
        item = requests.post(f"{API}/gst/items", json=p, headers=admin_headers).json()
        yield item
        requests.delete(f"{API}/gst/items/{item['id']}", headers=admin_headers)

    def test_deactivate_then_list_shows_inactive(self, admin_headers, temp_item):
        r = requests.delete(f"{API}/gst/items/{temp_item['id']}", headers=admin_headers)
        assert r.status_code == 200
        items = requests.get(f"{API}/gst/items", headers=admin_headers).json()
        found = next((i for i in items if i["id"] == temp_item["id"]), None)
        assert found is not None, "deactivated item should still be listed"
        assert found["is_active"] is False

    def test_activate_restores(self, admin_headers, temp_item):
        requests.delete(f"{API}/gst/items/{temp_item['id']}", headers=admin_headers)
        r = requests.post(f"{API}/gst/items/{temp_item['id']}/activate",
                          headers=admin_headers)
        assert r.status_code == 200
        items = requests.get(f"{API}/gst/items", headers=admin_headers).json()
        found = next((i for i in items if i["id"] == temp_item["id"]), None)
        assert found and found["is_active"] is True

    def test_activate_404_for_unknown(self, admin_headers):
        r = requests.post(f"{API}/gst/items/non-existent-id/activate",
                          headers=admin_headers)
        assert r.status_code == 404

    def test_non_admin_403(self, jullang_token, temp_item):
        h = {"Authorization": f"Bearer {jullang_token}", "Content-Type": "application/json"}
        r = requests.post(f"{API}/gst/items/{temp_item['id']}/activate", headers=h)
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"


# ---------- HISTORICAL INVOICE INVARIANT ----------
class TestHistoricalInvariant:
    def test_invoice_not_cascaded_when_item_renamed(self, admin_headers):
        # create item
        item = requests.post(
            f"{API}/gst/items",
            json={"name": f"TEST_HistItem_{uuid.uuid4().hex[:6]}",
                  "hsn": "123", "unit": "Nos", "gst_rate": 18},
            headers=admin_headers,
        ).json()
        original_name = item["name"]

        # create invoice with line item carrying that name (no item_id on invoice)
        inv_payload = {
            "customer_name": "TEST_HistCust",
            "customer_phone": "9999999999",
            "tax_mode": "intra_state",
            "line_items": [{
                "item_name": original_name,
                "hsn": "123",
                "unit": "Nos",
                "quantity": 1,
                "rate": 100,
                "gst_rate": 18,
            }],
        }
        inv = requests.post(f"{API}/gst/invoices", json=inv_payload,
                            headers=admin_headers).json()
        invoice_id = inv["id"]

        # rename master item
        new_name = original_name + "_RENAMED"
        requests.put(f"{API}/gst/items/{item['id']}",
                     json={"name": new_name}, headers=admin_headers)

        # fetch invoice - should still show OLD name
        got = requests.get(f"{API}/gst/invoices/{invoice_id}",
                           headers=admin_headers).json()
        assert got["line_items"][0]["item_name"] == original_name

        # cleanup
        requests.delete(f"{API}/gst/invoices/{invoice_id}", headers=admin_headers)
        requests.delete(f"{API}/gst/items/{item['id']}", headers=admin_headers)


# ---------- PLAN PUT PRESERVES item_id ----------
class TestPlanPutPreservesItemId:
    def test_put_preserves_item_id(self, admin_headers):
        item = requests.post(
            f"{API}/gst/items",
            json={"name": f"TEST_Put_{uuid.uuid4().hex[:6]}",
                  "hsn": "5", "unit": "Nos", "gst_rate": 5},
            headers=admin_headers,
        ).json()
        plan = requests.post(
            f"{API}/gst/plans",
            json={
                "name": f"TEST_PutPlan_{uuid.uuid4().hex[:6]}",
                "plan_type": "custom",
                "connection_type": "domestic",
                "cylinder_count": 1,
                "items": [{"item_id": item["id"], "item_name": item["name"],
                           "hsn": "5", "unit": "Nos", "gst_rate": 5,
                           "quantity": 1, "unit_price": 50}],
            },
            headers=admin_headers,
        ).json()
        # update plan replacing items
        upd = requests.put(
            f"{API}/gst/plans/{plan['id']}",
            json={
                "items": [{"item_id": item["id"], "item_name": item["name"],
                           "hsn": "5", "unit": "Nos", "gst_rate": 5,
                           "quantity": 2, "unit_price": 75}],
            },
            headers=admin_headers,
        )
        assert upd.status_code == 200
        saved = upd.json()
        assert saved["items"][0]["item_id"] == item["id"]
        assert float(saved["items"][0]["quantity"]) == 2.0
        # cleanup
        requests.delete(f"{API}/gst/plans/{plan['id']}", headers=admin_headers)
        requests.delete(f"{API}/gst/items/{item['id']}", headers=admin_headers)
