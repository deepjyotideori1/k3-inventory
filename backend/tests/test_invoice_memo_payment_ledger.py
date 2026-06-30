"""Tests for the Memo No, Payment Status, Party Ledger and Latest-First sort
features in the GST Billing module.

Endpoints under test:
  - POST /api/gst/invoices               (memo_no, cash_received, online_received, payment_status)
  - GET  /api/gst/invoices               (memo + payment_status in response; latest-first sort)
  - PUT  /api/gst/invoices/{id}          (edit cash/online recomputes status)
  - POST /api/gst/invoices/backfill-payments (admin-only, idempotent)
  - GET  /api/gst/party-ledger/customers (distinct customer aggregation)
  - GET  /api/gst/party-ledger           (rows + totals + customer)
  - GET  /api/gst/invoices/export/excel  (6 new tail cols)
  - GET  /api/gst/invoices/{id}/pdf      (PDF byte response w/ Memo + Payment Status)
"""
import os
import time
import uuid
import pytest
import requests
from io import BytesIO

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASSWORD = "Admin@123"

# ----------------- Fixtures -----------------
@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(f"{API}/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                      timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in login response: {data}"
    return {"Authorization": f"Bearer {token}"}


def _line_item(rate=1000.0, qty=1, gst=18.0):
    return {
        "description": "TEST_LINE",
        "hsn_code": "27111900",
        "quantity": qty,
        "unit": "PCS",
        "rate": rate,
        "gst_rate": gst,
        "discount": 0,
    }


def _new_invoice_payload(memo=None, cash=0.0, online=0.0, rate=1000.0,
                         qty=1, reason=None):
    p = {
        "customer_name": f"TEST_CUST_{uuid.uuid4().hex[:6]}",
        "customer_phone": f"9{uuid.uuid4().int % 1000000000:09d}",
        "tax_mode": "exclusive",
        "bill_type": "manual",
        "payment_mode": "cash",
        "line_items": [_line_item(rate=rate, qty=qty)],
        "cash_received": cash,
        "online_received": online,
    }
    if memo is not None:
        p["memo_no"] = memo
    if reason is not None:
        p["discrepancy_reason"] = reason
    return p


# ----------------- POST /gst/invoices ------------------
class TestCreateInvoicePayment:
    """Create invoice with payment fields -> verify computed status."""

    def test_paid_status(self, admin_headers):
        payload = _new_invoice_payload(memo="M-PAID-001", cash=590.0, online=590.0, rate=1000.0)
        # grand = 1000 + 18% = 1180; cash+online = 1180 => Paid
        r = requests.post(f"{API}/gst/invoices", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        inv = r.json()
        assert inv["memo_no"] == "M-PAID-001"
        assert abs(inv["grand_total"] - 1180.0) < 0.01
        assert inv["cash_received"] == 590.0
        assert inv["online_received"] == 590.0
        assert inv["pending_amount"] == 0.0
        assert inv["payment_status"] == "Paid"
        # GET to verify persistence
        g = requests.get(f"{API}/gst/invoices/{inv['id']}", headers=admin_headers, timeout=20)
        assert g.status_code == 200
        assert g.json()["payment_status"] == "Paid"

    def test_partial_status(self, admin_headers):
        payload = _new_invoice_payload(memo="M-PART-001", cash=500.0, online=0.0, rate=1000.0)
        r = requests.post(f"{API}/gst/invoices", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200
        inv = r.json()
        assert inv["payment_status"] == "Partial"
        assert inv["pending_amount"] == round(1180.0 - 500.0, 2)

    def test_pending_status(self, admin_headers):
        payload = _new_invoice_payload(memo="M-PEND-001", cash=0.0, online=0.0, rate=1000.0)
        r = requests.post(f"{API}/gst/invoices", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200
        inv = r.json()
        assert inv["payment_status"] == "Pending"
        assert inv["pending_amount"] == 1180.0

    def test_memo_falls_back_to_invoice_number(self, admin_headers):
        payload = _new_invoice_payload(memo="", cash=1180.0, online=0.0, rate=1000.0)
        r = requests.post(f"{API}/gst/invoices", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200
        inv = r.json()
        assert inv["memo_no"] == inv["invoice_number"]

    def test_tolerance_one_rupee_paid(self, admin_headers):
        # Pay 1179 vs grand 1180 -> within ±1 tolerance => Paid
        payload = _new_invoice_payload(memo="M-TOL-001", cash=1179.0, online=0.0, rate=1000.0)
        r = requests.post(f"{API}/gst/invoices", json=payload, headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert r.json()["payment_status"] == "Paid"


# ----------------- GET /gst/invoices ------------------
class TestListInvoiceFields:
    def test_list_includes_new_fields_and_sorted_latest_first(self, admin_headers):
        r = requests.get(f"{API}/gst/invoices", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        body = r.json()
        rows = body["invoices"] if isinstance(body, dict) else body
        assert isinstance(rows, list) and len(rows) > 0
        for k in ("memo_no", "cash_received", "online_received",
                  "pending_amount", "payment_status"):
            assert k in rows[0], f"missing {k}"
        # Latest-first sort: invoice_date DESC, then created_at DESC.
        dates = [(r.get("invoice_date") or "", r.get("created_at") or "") for r in rows]
        assert dates == sorted(dates, reverse=True), "invoices not sorted latest-first"


# ----------------- PUT /gst/invoices/{id} ------------------
class TestUpdateInvoicePayment:
    def test_edit_payment_recomputes_status(self, admin_headers):
        # Create as Pending
        c = requests.post(f"{API}/gst/invoices",
                          json=_new_invoice_payload(memo="M-EDIT-1", cash=0.0, online=0.0),
                          headers=admin_headers, timeout=20)
        inv = c.json()
        # Update cash to full grand_total -> Paid
        u = requests.put(f"{API}/gst/invoices/{inv['id']}",
                          json={"cash_received": 1180.0, "online_received": 0.0},
                          headers=admin_headers, timeout=20)
        assert u.status_code == 200, u.text
        updated = u.json()
        assert updated["cash_received"] == 1180.0
        assert updated["payment_status"] == "Paid"
        assert updated["pending_amount"] == 0.0

        # Update to partial
        u2 = requests.put(f"{API}/gst/invoices/{inv['id']}",
                          json={"cash_received": 600.0, "online_received": 0.0},
                          headers=admin_headers, timeout=20)
        assert u2.status_code == 200
        assert u2.json()["payment_status"] == "Partial"


# ----------------- POST /gst/invoices/backfill-payments ------------------
class TestBackfillIdempotent:
    def test_idempotent_second_call(self, admin_headers):
        # First call may have any number (already executed once)
        r1 = requests.post(f"{API}/gst/invoices/backfill-payments",
                            headers=admin_headers, timeout=60)
        assert r1.status_code == 200
        body1 = r1.json()
        assert "updated" in body1 and "skipped" in body1
        # Second call should report 0 updates because the query filter only matches
        # invoices with empty memo_no OR empty payment_status — first call sets both.
        r2 = requests.post(f"{API}/gst/invoices/backfill-payments",
                            headers=admin_headers, timeout=60)
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["updated"] == 0, f"Backfill not idempotent: {body2}"


# ----------------- GET /gst/party-ledger/customers ------------------
class TestPartyLedgerCustomers:
    def test_distinct_customers_sorted(self, admin_headers):
        r = requests.get(f"{API}/gst/party-ledger/customers",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list) and len(rows) > 0
        # Validate shape
        for f in ("customer_name", "customer_phone", "last_invoice_date", "invoice_count"):
            assert f in rows[0]
        # Sorted DESC by last_invoice_date (None/empty values may slot anywhere)
        dates = [r["last_invoice_date"] or "" for r in rows]
        assert dates == sorted(dates, reverse=True)
        # Distinct on (name, phone) – no duplicates
        seen = set()
        for r in rows:
            key = (r["customer_name"], r["customer_phone"])
            assert key not in seen, f"duplicate party: {key}"
            seen.add(key)


# ----------------- GET /gst/party-ledger ------------------
class TestPartyLedger:
    @pytest.fixture
    def seeded_customer(self, admin_headers):
        # Create 2 invoices for the same customer with same phone
        phone = f"9{uuid.uuid4().int % 1000000000:09d}"
        name = f"TEST_LEDGER_{uuid.uuid4().hex[:6]}"
        invs = []
        for cash in (590.0, 0.0):  # one Paid (partially), one Pending
            payload = _new_invoice_payload(memo=None, cash=cash, online=0.0, rate=1000.0)
            payload["customer_name"] = name
            payload["customer_phone"] = phone
            r = requests.post(f"{API}/gst/invoices", json=payload, headers=admin_headers, timeout=20)
            assert r.status_code == 200, r.text
            invs.append(r.json())
            time.sleep(0.05)
        return {"name": name, "phone": phone, "invoices": invs}

    def test_ledger_by_phone(self, admin_headers, seeded_customer):
        r = requests.get(f"{API}/gst/party-ledger",
                         params={"customer_phone": seeded_customer["phone"], "period": "all"},
                         headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(["rows", "totals", "customer"]).issubset(body.keys())
        rows = body["rows"]
        assert len(rows) == 2
        # Totals consistency
        assert body["totals"]["count"] == len(rows)
        expected_total_value = round(sum(r["total_invoice_amount"] for r in rows), 2)
        assert abs(body["totals"]["total_invoice_value"] - expected_total_value) < 0.01
        # Sorted latest-first
        dates = [(r.get("invoice_date") or "", r.get("created_at") or "") for r in rows]
        assert dates == sorted(dates, reverse=True)

    def test_ledger_by_name_prefix(self, admin_headers, seeded_customer):
        # Use the first 8 chars of the unique name as prefix
        prefix = seeded_customer["name"][:8]
        r = requests.get(f"{API}/gst/party-ledger",
                         params={"customer_name": prefix, "period": "all"},
                         headers=admin_headers, timeout=20)
        assert r.status_code == 200
        rows = r.json()["rows"]
        assert any(rw["memo_no"] for rw in rows)
        for rw in rows:
            assert rw["payment_status"] in ("Paid", "Partial", "Pending", "")

    def test_ledger_missing_filter_400(self, admin_headers):
        r = requests.get(f"{API}/gst/party-ledger", headers=admin_headers, timeout=20)
        assert r.status_code == 400

    def test_ledger_period_filters(self, admin_headers, seeded_customer):
        for period in ("today", "this_month", "this_year", "all"):
            r = requests.get(f"{API}/gst/party-ledger",
                             params={"customer_phone": seeded_customer["phone"], "period": period},
                             headers=admin_headers, timeout=20)
            assert r.status_code == 200, f"period={period}: {r.status_code} {r.text}"

    def test_ledger_custom_date_range(self, admin_headers, seeded_customer):
        from datetime import date
        today = date.today().isoformat()
        r = requests.get(f"{API}/gst/party-ledger",
                         params={"customer_phone": seeded_customer["phone"],
                                 "start_date": today, "end_date": today},
                         headers=admin_headers, timeout=20)
        assert r.status_code == 200
        # Both seeded invoices were created today so both should appear
        assert r.json()["totals"]["count"] == 2


# ----------------- GET /gst/invoices/export/excel ------------------
class TestExcelExportNewColumns:
    def test_excel_has_six_new_tail_columns(self, admin_headers):
        r = requests.get(f"{API}/gst/invoices/export/excel",
                         headers=admin_headers, timeout=60)
        assert r.status_code == 200
        assert "spreadsheet" in r.headers.get("content-type", "").lower() or \
               "octet-stream" in r.headers.get("content-type", "").lower()
        try:
            import openpyxl  # noqa
        except ImportError:
            pytest.skip("openpyxl not available to read excel — content-type check ok")
        from openpyxl import load_workbook
        wb = load_workbook(filename=BytesIO(r.content))
        ws = wb.active
        # Brand banner / metadata occupy first rows. Search the first 10 rows
        # for the actual header row containing 'Memo No.'.
        header_row = None
        for i in range(1, min(15, ws.max_row + 1)):
            row_vals = [c.value for c in ws[i]]
            if "Memo No." in row_vals:
                header_row = row_vals
                break
        assert header_row is not None, "Could not locate header row containing 'Memo No.'"
        for col in ["Memo No.", "Cash Received", "Online Received",
                    "Total Paid", "Pending Amount", "Payment Status"]:
            assert col in header_row, f"Missing column: {col}; got header {header_row}"
        # Trim trailing None cells then assert the last 6 cols
        trimmed = list(header_row)
        while trimmed and trimmed[-1] in (None, ""):
            trimmed.pop()
        assert trimmed[-6:] == ["Memo No.", "Cash Received", "Online Received",
                                 "Total Paid", "Pending Amount", "Payment Status"]


# ----------------- GET /gst/invoices/{id}/pdf ------------------
class TestPdfEndpoint:
    def test_pdf_returns_bytes(self, admin_headers):
        # Use any existing invoice
        body = requests.get(f"{API}/gst/invoices", headers=admin_headers, timeout=20).json()
        lst = body["invoices"] if isinstance(body, dict) else body
        assert len(lst) > 0
        inv_id = lst[0]["id"]
        r = requests.get(f"{API}/gst/invoices/{inv_id}/pdf",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        # Per spec: byte-stream + content-type check only; full PDF parse not required
        # because content is FlateDecode/ASCII85Decode compressed.
        assert len(r.content) > 1000, "PDF payload too small"
