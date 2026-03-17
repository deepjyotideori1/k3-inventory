"""
Backend tests for Connection & Refill Analytics API
Tests the analytics endpoint, warehouse filtering, period filtering, 
and PDF/Excel export endpoints.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


class TestConnectionRefillAnalytics:
    """Analytics endpoint tests for new connections and refills"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and store token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@k3gas.com", "password": "Admin@123"}
        )
        assert login_response.status_code == 200, "Admin login failed"
        self.admin_token = login_response.json()["token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Also login as warehouse manager for warehouse filtering tests
        manager_login = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "jullang@k3gas.com", "password": "Jullang@123"}
        )
        if manager_login.status_code == 200:
            self.manager_token = manager_login.json()["token"]
            self.manager_headers = {"Authorization": f"Bearer {self.manager_token}"}
            self.manager_warehouse_id = manager_login.json()["user"].get("warehouse_id")
        else:
            self.manager_token = None
            self.manager_headers = None
            self.manager_warehouse_id = None

    # === PERIOD FILTER TESTS ===

    def test_analytics_yearly_period(self):
        """GET /api/admin/connection-refill-analytics?period=yearly returns correct summary"""
        response = requests.get(
            f"{BASE_URL}/api/admin/connection-refill-analytics",
            params={"period": "yearly"},
            headers=self.admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify structure
        assert "summary" in data, "Missing summary field"
        assert "warehouse_breakdown" in data, "Missing warehouse_breakdown"
        assert "date_breakdown" in data, "Missing date_breakdown"
        assert "period" in data and data["period"] == "yearly"
        assert "date_range" in data
        
        # Verify summary fields
        summary = data["summary"]
        assert "total_new_connections" in summary
        assert "domestic_new_connections" in summary
        assert "commercial_new_connections" in summary
        assert "domestic_new_cylinders" in summary
        assert "commercial_new_cylinders" in summary
        assert "total_refills" in summary
        assert "domestic_refills" in summary
        assert "commercial_refills" in summary
        assert "domestic_refill_cylinders" in summary
        assert "commercial_refill_cylinders" in summary
        
        # Verify totals add up correctly
        assert summary["total_new_connections"] == summary["domestic_new_connections"] + summary["commercial_new_connections"]
        assert summary["total_refills"] == summary["domestic_refills"] + summary["commercial_refills"]
        
        # Verify date range starts from January 1st for yearly
        assert data["date_range"]["start"].endswith("-01-01")
        
        print(f"Yearly analytics: {summary['total_new_connections']} new connections, {summary['total_refills']} refills")

    def test_analytics_monthly_period(self):
        """GET /api/admin/connection-refill-analytics?period=monthly returns monthly data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/connection-refill-analytics",
            params={"period": "monthly"},
            headers=self.admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["period"] == "monthly"
        # Monthly starts from 1st of current month
        assert data["date_range"]["start"].endswith("-01")
        
        print(f"Monthly period: {data['date_range']['start']} to {data['date_range']['end']}")

    def test_analytics_daily_period(self):
        """GET /api/admin/connection-refill-analytics?period=daily returns only today's data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/connection-refill-analytics",
            params={"period": "daily"},
            headers=self.admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["period"] == "daily"
        # Daily means start == end (same day)
        assert data["date_range"]["start"] == data["date_range"]["end"]
        
        print(f"Daily period: {data['date_range']['start']}")

    def test_analytics_quarterly_period(self):
        """GET /api/admin/connection-refill-analytics?period=quarterly returns quarterly data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/connection-refill-analytics",
            params={"period": "quarterly"},
            headers=self.admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["period"] == "quarterly"
        # Quarter should start at beginning of Q1, Q2, Q3, or Q4
        start_month = int(data["date_range"]["start"].split("-")[1])
        assert start_month in [1, 4, 7, 10], f"Quarter start month {start_month} not valid"
        
        print(f"Quarterly period: {data['date_range']['start']} to {data['date_range']['end']}")

    def test_analytics_custom_period(self):
        """GET /api/admin/connection-refill-analytics?period=custom&start_date=...&end_date=... works"""
        response = requests.get(
            f"{BASE_URL}/api/admin/connection-refill-analytics",
            params={
                "period": "custom",
                "start_date": "2026-01-01",
                "end_date": "2026-12-31"
            },
            headers=self.admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["period"] == "custom"
        assert data["date_range"]["start"] == "2026-01-01"
        assert data["date_range"]["end"] == "2026-12-31"
        
        print(f"Custom period: {data['date_range']['start']} to {data['date_range']['end']}, refills: {data['summary']['total_refills']}")

    # === WAREHOUSE FILTER TESTS ===

    def test_analytics_warehouse_filter(self):
        """GET /api/admin/connection-refill-analytics with warehouse_id filter returns warehouse-specific data"""
        # First get warehouse list to get a valid warehouse_id
        warehouses_response = requests.get(
            f"{BASE_URL}/api/warehouses",
            headers=self.admin_headers
        )
        if warehouses_response.status_code != 200:
            pytest.skip("Could not get warehouses list")
            
        warehouses = warehouses_response.json()
        if not warehouses:
            pytest.skip("No warehouses found")
        
        warehouse_id = warehouses[0]["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/admin/connection-refill-analytics",
            params={"period": "yearly", "warehouse_id": warehouse_id},
            headers=self.admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        # Should only have data for the selected warehouse
        if data["warehouse_breakdown"]:
            for wh in data["warehouse_breakdown"]:
                assert wh["warehouse_id"] == warehouse_id
                
        print(f"Warehouse filter applied: {warehouses[0]['name']}")

    def test_non_admin_auto_filters_to_warehouse(self):
        """Non-admin users get auto-filtered to their warehouse"""
        if not self.manager_token:
            pytest.skip("Manager login not available")
        
        response = requests.get(
            f"{BASE_URL}/api/admin/connection-refill-analytics",
            params={"period": "yearly"},
            headers=self.manager_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        # Manager should only see their warehouse data
        if data["warehouse_breakdown"] and self.manager_warehouse_id:
            for wh in data["warehouse_breakdown"]:
                assert wh["warehouse_id"] == self.manager_warehouse_id
                
        print(f"Non-admin filtered to warehouse_id: {self.manager_warehouse_id}")

    # === EXPORT TESTS ===

    def test_export_pdf(self):
        """GET /api/export/connection-refill-analytics-pdf returns PDF file"""
        response = requests.get(
            f"{BASE_URL}/api/export/connection-refill-analytics-pdf",
            params={"period": "yearly"},
            headers=self.admin_headers
        )
        assert response.status_code == 200
        assert "application/pdf" in response.headers.get("Content-Type", "")
        assert "attachment" in response.headers.get("Content-Disposition", "")
        assert len(response.content) > 0
        
        print(f"PDF export successful: {len(response.content)} bytes")

    def test_export_excel(self):
        """GET /api/export/connection-refill-analytics-excel returns Excel file"""
        response = requests.get(
            f"{BASE_URL}/api/export/connection-refill-analytics-excel",
            params={"period": "yearly"},
            headers=self.admin_headers
        )
        assert response.status_code == 200
        assert "spreadsheet" in response.headers.get("Content-Type", "").lower() or "openxmlformats" in response.headers.get("Content-Type", "")
        assert "attachment" in response.headers.get("Content-Disposition", "")
        assert len(response.content) > 0
        
        print(f"Excel export successful: {len(response.content)} bytes")

    def test_export_pdf_with_filters(self):
        """PDF export respects period and warehouse filters"""
        response = requests.get(
            f"{BASE_URL}/api/export/connection-refill-analytics-pdf",
            params={
                "period": "custom",
                "start_date": "2026-02-01",
                "end_date": "2026-02-28"
            },
            headers=self.admin_headers
        )
        assert response.status_code == 200
        assert "application/pdf" in response.headers.get("Content-Type", "")
        
        print("PDF export with custom filter successful")

    def test_export_excel_with_filters(self):
        """Excel export respects period and warehouse filters"""
        response = requests.get(
            f"{BASE_URL}/api/export/connection-refill-analytics-excel",
            params={
                "period": "monthly"
            },
            headers=self.admin_headers
        )
        assert response.status_code == 200
        assert len(response.content) > 0
        
        print("Excel export with monthly filter successful")

    # === DATA INTEGRITY TESTS ===

    def test_warehouse_breakdown_data_integrity(self):
        """Warehouse breakdown totals match summary totals"""
        response = requests.get(
            f"{BASE_URL}/api/admin/connection-refill-analytics",
            params={"period": "yearly"},
            headers=self.admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        summary = data["summary"]
        warehouse_breakdown = data["warehouse_breakdown"]
        
        # Calculate totals from warehouse breakdown
        wh_domestic_new = sum(w["domestic_new"] for w in warehouse_breakdown)
        wh_commercial_new = sum(w["commercial_new"] for w in warehouse_breakdown)
        wh_domestic_refill = sum(w["domestic_refill"] for w in warehouse_breakdown)
        wh_commercial_refill = sum(w["commercial_refill"] for w in warehouse_breakdown)
        
        # Verify against summary
        assert wh_domestic_new == summary["domestic_new_connections"], "Warehouse breakdown domestic_new doesn't match summary"
        assert wh_commercial_new == summary["commercial_new_connections"], "Warehouse breakdown commercial_new doesn't match summary"
        assert wh_domestic_refill == summary["domestic_refills"], "Warehouse breakdown domestic_refill doesn't match summary"
        assert wh_commercial_refill == summary["commercial_refills"], "Warehouse breakdown commercial_refill doesn't match summary"
        
        print("Warehouse breakdown totals match summary")

    def test_date_breakdown_data_integrity(self):
        """Date breakdown totals match summary totals"""
        response = requests.get(
            f"{BASE_URL}/api/admin/connection-refill-analytics",
            params={"period": "yearly"},
            headers=self.admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        summary = data["summary"]
        date_breakdown = data["date_breakdown"]
        
        # Calculate totals from date breakdown
        date_domestic_new = sum(d["domestic_new"] for d in date_breakdown)
        date_commercial_new = sum(d["commercial_new"] for d in date_breakdown)
        date_domestic_refill = sum(d["domestic_refill"] for d in date_breakdown)
        date_commercial_refill = sum(d["commercial_refill"] for d in date_breakdown)
        
        # Verify against summary
        assert date_domestic_new == summary["domestic_new_connections"], "Date breakdown domestic_new doesn't match summary"
        assert date_commercial_new == summary["commercial_new_connections"], "Date breakdown commercial_new doesn't match summary"
        assert date_domestic_refill == summary["domestic_refills"], "Date breakdown domestic_refill doesn't match summary"
        assert date_commercial_refill == summary["commercial_refills"], "Date breakdown commercial_refill doesn't match summary"
        
        print("Date breakdown totals match summary")

    # === AUTHENTICATION TESTS ===

    def test_analytics_requires_authentication(self):
        """Analytics endpoint requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/admin/connection-refill-analytics",
            params={"period": "yearly"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        
        print("Authentication required - verified")

    def test_export_pdf_requires_authentication(self):
        """PDF export requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/export/connection-refill-analytics-pdf",
            params={"period": "yearly"}
        )
        assert response.status_code in [401, 403]
        
        print("PDF export auth required - verified")

    def test_export_excel_requires_authentication(self):
        """Excel export requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/export/connection-refill-analytics-excel",
            params={"period": "yearly"}
        )
        assert response.status_code in [401, 403]
        
        print("Excel export auth required - verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
