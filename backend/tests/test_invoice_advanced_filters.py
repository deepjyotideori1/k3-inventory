"""Backend tests for GST Invoices tab advanced filters (iteration_59).

Covers:
- fy filter (Indian financial year YYYY-YY)
- month + year filter
- payment_status filter (Paid / Partial / Pending)
- memo_no substring in search
- combined filters (warehouse + fy + payment_status + status)
- Excel export honours all params
- get_invoice_summary respects fy/month/payment_status/warehouse_ids
- non-admin employee gets 403 on GST endpoints
"""
import os
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    if not v:
        raise RuntimeError("REACT_APP_BACKEND_URL not set")
    return v.rstrip("/")

BASE = _load_backend_url()
WH_JULLANG = "8f2dc176-4450-4bf7-8ccc-2c2618fc6d32"
WH_FAKE = "00000000-0000-0000-0000-000000000000"


@pytest.fixture(scope="module")
def admin_h():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "admin@k3gas.com", "password": "Admin@123"},
                      timeout=15)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def employee_h():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "employee@k3gas.com", "password": "Employee@123"},
                      timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Employee login failed: {r.status_code} {r.text}")
    return {"Authorization": f"Bearer {r.json()['token']}"}


# --------- FY FILTER ---------
class TestFYFilter:
    def test_fy_202627_returns_subset(self, admin_h):
        r = requests.get(f"{BASE}/api/gst/invoices?fy=2026-27&limit=500", headers=admin_h, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "invoices" in data and "total" in data
        # All invoices in FY 2026-27 should be between 2026-04-01 and 2027-03-31
        for inv in data["invoices"]:
            d = inv.get("invoice_date", "")
            assert "2026-04-01" <= d <= "2027-03-31", f"invoice_date {d} outside FY 2026-27"
        # Expect at least 1 invoice; per playbook ~33
        assert data["total"] >= 1

    def test_fy_all_invoices_sorted_desc(self, admin_h):
        r = requests.get(f"{BASE}/api/gst/invoices?fy=2026-27&limit=500", headers=admin_h, timeout=15)
        assert r.status_code == 200
        dates = [i["invoice_date"] for i in r.json()["invoices"]]
        assert dates == sorted(dates, reverse=True), "Invoice list not sorted by invoice_date DESC"

    def test_fy_invalid_gracefully_ignored(self, admin_h):
        r = requests.get(f"{BASE}/api/gst/invoices?fy=garbage", headers=admin_h, timeout=15)
        # invalid FY should be ignored (no crash) — returns full dataset
        assert r.status_code == 200

    def test_summary_with_fy(self, admin_h):
        r = requests.get(f"{BASE}/api/gst/invoices/summary?fy=2026-27", headers=admin_h, timeout=15)
        assert r.status_code == 200
        s = r.json()
        assert "total_invoices" in s and "active" in s and "cancelled" in s

    def test_export_excel_with_fy(self, admin_h):
        r = requests.get(f"{BASE}/api/gst/invoices/export/excel?fy=2026-27", headers=admin_h, timeout=30)
        assert r.status_code == 200
        assert "spreadsheet" in r.headers.get("content-type", "").lower()
        assert len(r.content) > 500  # non-empty xlsx


# --------- MONTH FILTER ---------
class TestMonthFilter:
    def test_month_and_year(self, admin_h):
        r = requests.get(f"{BASE}/api/gst/invoices?month=7&year=2026&limit=500",
                         headers=admin_h, timeout=15)
        assert r.status_code == 200
        for inv in r.json()["invoices"]:
            d = inv.get("invoice_date", "")
            assert d.startswith("2026-07"), f"unexpected date {d}"

    def test_month_summary(self, admin_h):
        r = requests.get(f"{BASE}/api/gst/invoices/summary?month=7&year=2026",
                         headers=admin_h, timeout=15)
        assert r.status_code == 200
        assert "total_invoices" in r.json()


# --------- PAYMENT STATUS FILTER ---------
class TestPaymentStatus:
    @pytest.mark.parametrize("status", ["Paid", "Partial", "Pending"])
    def test_payment_status_subset(self, admin_h, status):
        r = requests.get(f"{BASE}/api/gst/invoices?payment_status={status}&limit=500",
                         headers=admin_h, timeout=15)
        assert r.status_code == 200
        invs = r.json()["invoices"]
        for inv in invs:
            assert inv.get("payment_status") == status, (
                f"expected {status} got {inv.get('payment_status')} for {inv.get('invoice_number')}"
            )

    def test_payment_status_summary(self, admin_h):
        r = requests.get(f"{BASE}/api/gst/invoices/summary?payment_status=Paid",
                         headers=admin_h, timeout=15)
        assert r.status_code == 200


# --------- SEARCH INCLUDES MEMO_NO ---------
class TestSearchMemoNo:
    def test_search_by_invoice_number(self, admin_h):
        # First get any invoice with a memo_no
        r = requests.get(f"{BASE}/api/gst/invoices?limit=50", headers=admin_h, timeout=15)
        assert r.status_code == 200
        invs = r.json()["invoices"]
        target = next((i for i in invs if i.get("memo_no")), None)
        if not target:
            pytest.skip("No invoice with memo_no found in dataset")
        memo = target["memo_no"]

        r2 = requests.get(f"{BASE}/api/gst/invoices?search={memo}&limit=50",
                          headers=admin_h, timeout=15)
        assert r2.status_code == 200
        matched = r2.json()["invoices"]
        assert any(i.get("memo_no") == memo for i in matched), (
            f"search by memo_no={memo} did not return the expected invoice"
        )


# --------- COMBINED FILTERS ---------
class TestCombinedFilters:
    def test_warehouse_plus_fy_plus_paid_plus_status(self, admin_h):
        r = requests.get(
            f"{BASE}/api/gst/invoices?warehouse_ids={WH_JULLANG}&fy=2026-27"
            f"&payment_status=Paid&status=active&limit=500",
            headers=admin_h, timeout=15,
        )
        assert r.status_code == 200
        invs = r.json()["invoices"]
        for inv in invs:
            assert inv.get("warehouse_id") == WH_JULLANG
            assert "2026-04-01" <= inv.get("invoice_date", "") <= "2027-03-31"
            assert inv.get("payment_status") == "Paid"
            assert inv.get("status") == "active"

    def test_summary_combined(self, admin_h):
        r = requests.get(
            f"{BASE}/api/gst/invoices/summary?warehouse_ids={WH_JULLANG}"
            f"&fy=2026-27&payment_status=Paid",
            headers=admin_h, timeout=15,
        )
        assert r.status_code == 200

    def test_export_excel_combined(self, admin_h):
        r = requests.get(
            f"{BASE}/api/gst/invoices/export/excel?warehouse_ids={WH_JULLANG}"
            f"&fy=2026-27&payment_status=Paid",
            headers=admin_h, timeout=30,
        )
        assert r.status_code == 200
        assert len(r.content) > 500


# --------- PAGINATION PRESERVES FILTERS ---------
class TestPagination:
    def test_pagination_preserves_filters(self, admin_h):
        # Small page size to guarantee multiple pages
        r1 = requests.get(f"{BASE}/api/gst/invoices?fy=2026-27&limit=5&page=1",
                          headers=admin_h, timeout=15)
        assert r1.status_code == 200
        d1 = r1.json()
        r2 = requests.get(f"{BASE}/api/gst/invoices?fy=2026-27&limit=5&page=2",
                          headers=admin_h, timeout=15)
        assert r2.status_code == 200
        d2 = r2.json()
        # Same total, different page contents
        assert d1["total"] == d2["total"]
        if d1["total"] > 5:
            ids1 = {i["id"] for i in d1["invoices"]}
            ids2 = {i["id"] for i in d2["invoices"]}
            assert ids1.isdisjoint(ids2), "page 1 and page 2 overlap"


# --------- FAKE WAREHOUSE => EMPTY ---------
class TestFakeWarehouse:
    def test_fake_wh_returns_zero(self, admin_h):
        r = requests.get(f"{BASE}/api/gst/invoices?warehouse_ids={WH_FAKE}",
                         headers=admin_h, timeout=15)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_fake_wh_summary_zero(self, admin_h):
        r = requests.get(f"{BASE}/api/gst/invoices/summary?warehouse_ids={WH_FAKE}",
                         headers=admin_h, timeout=15)
        assert r.status_code == 200
        assert r.json()["total_invoices"] == 0


# --------- NON-ADMIN ACCESS ---------
class TestNonAdminLock:
    def test_employee_gets_403_or_401_on_gst_invoices(self, employee_h):
        r = requests.get(f"{BASE}/api/gst/invoices", headers=employee_h, timeout=15)
        # Route is admin-only (require_admin) — should be 403; some setups return 401
        assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}: {r.text[:200]}"


# --------- EXPORT MEDIA TYPE ---------
class TestExportMediaType:
    def test_export_returns_xlsx(self, admin_h):
        r = requests.get(f"{BASE}/api/gst/invoices/export/excel", headers=admin_h, timeout=30)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "").lower()
        assert "spreadsheet" in ct or "excel" in ct
        assert r.content[:2] == b"PK"  # xlsx = zip signature
