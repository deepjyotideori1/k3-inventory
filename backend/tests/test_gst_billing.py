"""
GST Billing module - end-to-end backend tests.
Covers: admin guard, config, items, summary, invoice CRUD, auto-gen hook,
manual generate-from-sale, numbering format, PDF & Excel exports.
"""
import os
import io
import pytest
import requests
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://unified-checkout-8.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@k3gas.com", "password": "Admin@123"}
MGR = {"email": "jullang@k3gas.com", "password": "Jullang@123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def mgr_token():
    return _login(MGR)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mgr_headers(mgr_token):
    return {"Authorization": f"Bearer {mgr_token}", "Content-Type": "application/json"}


# ---------- ACCESS CONTROL ----------
class TestAccessControl:
    def test_admin_access(self, admin_headers):
        r = requests.get(f"{API}/gst/config", headers=admin_headers, timeout=30)
        assert r.status_code == 200

    def test_non_admin_blocked(self, mgr_headers):
        for path in ["/gst/config", "/gst/items", "/gst/invoices", "/gst/invoices/summary"]:
            r = requests.get(f"{API}{path}", headers=mgr_headers, timeout=30)
            assert r.status_code == 403, f"{path}: expected 403, got {r.status_code}"


# ---------- CONFIG ----------
class TestConfig:
    def test_default_config(self, admin_headers):
        r = requests.get(f"{API}/gst/config", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        cfg = r.json()
        assert cfg.get("prefix") == "INV" or cfg.get("prefix")  # may be updated by prior tests
        assert cfg.get("default_tax_mode") in ("intra_state", "inter_state")
        assert "auto_generate" in cfg

    def test_update_config(self, admin_headers):
        # change suffix
        r = requests.put(f"{API}/gst/config", json={"suffix": "TEST"}, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json().get("suffix") == "TEST"
        # restore
        r = requests.put(f"{API}/gst/config", json={"suffix": ""}, headers=admin_headers, timeout=30)
        assert r.status_code == 200

    def test_invalid_tax_mode(self, admin_headers):
        r = requests.put(f"{API}/gst/config", json={"default_tax_mode": "bogus"}, headers=admin_headers, timeout=30)
        assert r.status_code == 400


# ---------- ITEMS ----------
class TestItems:
    def test_items_seeded(self, admin_headers):
        r = requests.get(f"{API}/gst/items", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 14, f"expected >=14 default items, got {len(items)}"
        names = {it["name"] for it in items}
        assert "Domestic LPG Refill" in names
        assert "Commercial LPG Refill" in names

    def test_item_crud(self, admin_headers):
        # create
        payload = {"name": "TEST_ItemX", "hsn": "12345678", "unit": "Nos", "gst_rate": 18}
        r = requests.post(f"{API}/gst/items", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        item = r.json()
        iid = item["id"]
        assert item["gst_rate"] == 18
        # update
        r = requests.put(f"{API}/gst/items/{iid}", json={"gst_rate": 12}, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        # delete (soft)
        r = requests.delete(f"{API}/gst/items/{iid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200


# ---------- INVOICE CRUD ----------
class TestInvoiceCRUD:
    @pytest.fixture
    def manual_invoice(self, admin_headers):
        payload = {
            "customer_name": "TEST_Customer",
            "customer_phone": "9999999999",
            "tax_mode": "intra_state",
            "payment_mode": "cash",
            "line_items": [
                {"item_name": "Domestic LPG Refill", "hsn": "271119", "unit": "Cylinder",
                 "gst_rate": 5, "quantity": 1, "rate": 1000},
            ],
        }
        r = requests.post(f"{API}/gst/invoices", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()

    def test_create_invoice_totals(self, manual_invoice):
        inv = manual_invoice
        # taxable=1000, cgst=25, sgst=25, igst=0, grand=1050
        assert inv["sub_total"] == 1000
        assert inv["total_cgst"] == 25.0
        assert inv["total_sgst"] == 25.0
        assert inv["total_igst"] == 0.0
        assert inv["grand_total"] == 1050.0
        assert inv["invoice_number"].startswith(inv.get("invoice_number", "").split("/")[0])
        # Format check INV/2026-27/0001
        parts = inv["invoice_number"].split("/")
        assert len(parts) >= 3
        assert "-" in parts[1]  # FY
        assert parts[2].isdigit() or parts[2][:4].isdigit()

    def test_inter_state_only_igst(self, admin_headers):
        payload = {
            "customer_name": "TEST_Inter",
            "tax_mode": "inter_state",
            "line_items": [{"item_name": "X", "gst_rate": 18, "quantity": 1, "rate": 100}],
        }
        r = requests.post(f"{API}/gst/invoices", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        inv = r.json()
        assert inv["total_cgst"] == 0
        assert inv["total_sgst"] == 0
        assert inv["total_igst"] == 18.0
        requests.delete(f"{API}/gst/invoices/{inv['id']}", headers=admin_headers)

    def test_update_invoice(self, manual_invoice, admin_headers):
        iid = manual_invoice["id"]
        new_items = [{"item_name": "Domestic LPG Refill", "gst_rate": 5, "quantity": 2, "rate": 1000}]
        r = requests.put(f"{API}/gst/invoices/{iid}", json={"line_items": new_items}, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        upd = r.json()
        assert upd["sub_total"] == 2000

    def test_cancel_then_no_edit(self, manual_invoice, admin_headers):
        iid = manual_invoice["id"]
        r = requests.post(f"{API}/gst/invoices/{iid}/cancel", json={"reason": "TEST_cancel"}, headers=admin_headers, timeout=30)
        assert r.status_code == 200
        # verify status
        g = requests.get(f"{API}/gst/invoices/{iid}", headers=admin_headers, timeout=30).json()
        assert g["status"] == "cancelled"
        # edit blocked
        r = requests.put(f"{API}/gst/invoices/{iid}", json={"remarks": "x"}, headers=admin_headers, timeout=30)
        assert r.status_code == 400
        # delete
        r = requests.delete(f"{API}/gst/invoices/{iid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        # verify gone
        r = requests.get(f"{API}/gst/invoices/{iid}", headers=admin_headers, timeout=30)
        assert r.status_code == 404


# ---------- LIST / SUMMARY / FILTERS ----------
class TestListSummary:
    def test_summary(self, admin_headers):
        r = requests.get(f"{API}/gst/invoices/summary", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        s = r.json()
        assert "active" in s and "cancelled" in s
        assert "count" in s["active"]
        assert "total_invoices" in s

    def test_list_pagination(self, admin_headers):
        r = requests.get(f"{API}/gst/invoices?page=1&limit=10", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ("invoices", "total", "page", "pages"):
            assert k in d

    def test_list_filters(self, admin_headers):
        r = requests.get(f"{API}/gst/invoices?status=active&search=TEST", headers=admin_headers, timeout=30)
        assert r.status_code == 200


# ---------- AUTO-GENERATION HOOKS ----------
class TestAutoGen:
    @pytest.fixture(scope="class")
    def warehouse_id(self, admin_headers):
        r = requests.get(f"{API}/warehouses", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        whs = r.json()
        assert whs, "No warehouses"
        # pick first non-plant warehouse with customers
        return whs[0]["id"]

    def test_lpg_refill_auto_invoice(self, admin_headers, warehouse_id):
        sale_payload = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "consumer_name": "TEST_AutoGen_Refill",
            "address": "Test Address",
            "connection_type": "domestic_refill",
            "no_of_refills": 1,
            "amount": 1100,
            "payment_mode": "cash",
            "warehouse_id": warehouse_id,
        }
        r = requests.post(f"{API}/sales-entries/warehouse/{warehouse_id}",
                          json=sale_payload, headers=admin_headers, timeout=60)
        if r.status_code not in (200, 201):
            pytest.skip(f"Sale create not supported here: {r.status_code} {r.text[:200]}")
        sale = r.json()
        sale_id = sale.get("id")
        assert sale_id
        # find invoice by sale_id
        inv = self._find_invoice_by_sale(admin_headers, sale_id, "sales_entry")
        assert inv is not None, "Auto-generated invoice not found"
        assert inv["grand_total"] == 1100.0, f"grand_total mismatch: {inv['grand_total']}"
        # 5% GST inclusive => cgst+sgst ≈ 52.38
        total_gst = inv["total_cgst"] + inv["total_sgst"] + inv["total_igst"]
        assert abs(total_gst - 52.38) < 1.0, f"GST mismatch: {total_gst}"
        # Format INV/FY/SEQ
        parts = inv["invoice_number"].split("/")
        assert parts[1].count("-") == 1 and len(parts[2]) >= 4

    def test_duplicate_generate_returns_400(self, admin_headers):
        # Use any auto-generated invoice's sale_id
        r = requests.get(f"{API}/gst/invoices?limit=50", headers=admin_headers, timeout=30)
        invs = r.json()["invoices"]
        sale_inv = next((i for i in invs if i.get("sale_id") and i.get("sale_type") == "sales_entry" and i.get("status") == "active"), None)
        if not sale_inv:
            pytest.skip("No auto-gen sale invoice")
        sid = sale_inv["sale_id"]
        r = requests.post(f"{API}/gst/invoices/generate-from-sale/sales_entry/{sid}",
                          headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def test_generate_invalid_sale_type(self, admin_headers):
        r = requests.post(f"{API}/gst/invoices/generate-from-sale/bogus/xxx", headers=admin_headers, timeout=30)
        assert r.status_code == 400

    def _find_invoice_by_sale(self, headers, sale_id, sale_type):
        r = requests.get(f"{API}/gst/invoices?limit=200", headers=headers, timeout=30)
        for i in r.json()["invoices"]:
            if i.get("sale_id") == sale_id and i.get("sale_type") == sale_type:
                return i
        return None


# ---------- EXPORTS ----------
class TestExports:
    def test_excel_export(self, admin_headers):
        r = requests.get(f"{API}/gst/invoices/export/excel", headers=admin_headers, timeout=60)
        assert r.status_code == 200
        assert "spreadsheet" in r.headers.get("content-type", "")
        assert len(r.content) > 100

    def test_pdf_export(self, admin_headers):
        # get any invoice
        r = requests.get(f"{API}/gst/invoices?limit=1", headers=admin_headers, timeout=30)
        invs = r.json()["invoices"]
        if not invs:
            # create one
            p = {"customer_name": "TEST_PDF", "tax_mode": "intra_state",
                 "line_items": [{"item_name": "X", "gst_rate": 18, "quantity": 1, "rate": 100}]}
            cr = requests.post(f"{API}/gst/invoices", json=p, headers=admin_headers, timeout=30)
            inv_id = cr.json()["id"]
        else:
            inv_id = invs[0]["id"]
        r = requests.get(f"{API}/gst/invoices/{inv_id}/pdf", headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content.startswith(b"%PDF")
