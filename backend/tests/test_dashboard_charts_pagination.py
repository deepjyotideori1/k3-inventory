"""
Test Dashboard Charts, Pagination, Audit Logs, and Plant Issuance Features
- GET /api/dashboard/chart-data with period and warehouse_id filters
- GET /api/audit-logs (admin only)
- GET /api/sales-entries with pagination (page, limit)
- GET /api/plant/issuance-history
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASSWORD = "Admin@123"

# Known warehouse ID from previous tests
JULLANG_WAREHOUSE_ID = "8f2dc176-4450-4bf7-8ccc-2c2618fc6d32"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth token"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


class TestDashboardChartData:
    """Tests for GET /api/dashboard/chart-data endpoint"""
    
    def test_chart_data_default_30d(self, admin_headers):
        """Test chart data with default 30d period"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/chart-data",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "daily_trend" in data, "Missing daily_trend"
        assert "payment_breakdown" in data, "Missing payment_breakdown"
        assert "connection_types" in data, "Missing connection_types"
        assert "warehouse_totals" in data, "Missing warehouse_totals"
        assert "total_amount" in data, "Missing total_amount"
        assert "total_entries" in data, "Missing total_entries"
        
        # Verify data types
        assert isinstance(data["daily_trend"], list), "daily_trend should be a list"
        assert isinstance(data["payment_breakdown"], list), "payment_breakdown should be a list"
        assert isinstance(data["connection_types"], list), "connection_types should be a list"
        assert isinstance(data["warehouse_totals"], list), "warehouse_totals should be a list"
        assert isinstance(data["total_amount"], (int, float)), "total_amount should be numeric"
        assert isinstance(data["total_entries"], int), "total_entries should be int"
        
        print(f"✓ Chart data 30d: {data['total_entries']} entries, Rs.{data['total_amount']}")
    
    def test_chart_data_7d_period(self, admin_headers):
        """Test chart data with 7d period filter"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/chart-data?period=7d",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "daily_trend" in data
        assert "payment_breakdown" in data
        assert "total_entries" in data
        
        print(f"✓ Chart data 7d: {data['total_entries']} entries")
    
    def test_chart_data_90d_period(self, admin_headers):
        """Test chart data with 90d period filter"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/chart-data?period=90d",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "daily_trend" in data
        assert "total_entries" in data
        
        print(f"✓ Chart data 90d: {data['total_entries']} entries")
    
    def test_chart_data_warehouse_filter(self, admin_headers):
        """Test chart data with warehouse_id filter"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/chart-data?warehouse_id={JULLANG_WAREHOUSE_ID}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "daily_trend" in data
        assert "payment_breakdown" in data
        # warehouse_totals should be empty when filtering by single warehouse
        assert isinstance(data["warehouse_totals"], list)
        
        print(f"✓ Chart data Jullang: {data['total_entries']} entries, Rs.{data['total_amount']}")
    
    def test_chart_data_combined_filters(self, admin_headers):
        """Test chart data with period and warehouse_id combined"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/chart-data?period=7d&warehouse_id={JULLANG_WAREHOUSE_ID}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "daily_trend" in data
        assert "total_entries" in data
        
        print(f"✓ Chart data 7d + Jullang: {data['total_entries']} entries")
    
    def test_payment_breakdown_structure(self, admin_headers):
        """Verify payment breakdown has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/chart-data",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        payment_breakdown = data["payment_breakdown"]
        assert len(payment_breakdown) == 3, "Should have 3 payment types"
        
        names = [p["name"] for p in payment_breakdown]
        assert "Cash" in names, "Missing Cash in payment breakdown"
        assert "Online" in names, "Missing Online in payment breakdown"
        assert "Pending" in names, "Missing Pending in payment breakdown"
        
        for p in payment_breakdown:
            assert "name" in p
            assert "value" in p
            assert isinstance(p["value"], (int, float))
        
        print(f"✓ Payment breakdown: {payment_breakdown}")


class TestAuditLogs:
    """Tests for GET /api/audit-logs endpoint (admin only)"""
    
    def test_audit_logs_admin_access(self, admin_headers):
        """Test admin can access audit logs"""
        response = requests.get(
            f"{BASE_URL}/api/audit-logs",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "logs" in data, "Missing logs field"
        assert "total" in data, "Missing total field"
        assert "page" in data, "Missing page field"
        assert "pages" in data, "Missing pages field"
        
        assert isinstance(data["logs"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["page"], int)
        assert isinstance(data["pages"], int)
        
        print(f"✓ Audit logs: {data['total']} total, page {data['page']}/{data['pages']}")
    
    def test_audit_logs_pagination(self, admin_headers):
        """Test audit logs pagination parameters"""
        response = requests.get(
            f"{BASE_URL}/api/audit-logs?page=1&limit=10",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["page"] == 1
        assert len(data["logs"]) <= 10
        
        print(f"✓ Audit logs pagination: {len(data['logs'])} logs on page 1")
    
    def test_audit_logs_resource_type_filter(self, admin_headers):
        """Test audit logs with resource_type filter"""
        response = requests.get(
            f"{BASE_URL}/api/audit-logs?resource_type=sales_entry",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # All logs should be of the filtered type (if any exist)
        for log in data["logs"]:
            assert log.get("resource_type") == "sales_entry"
        
        print(f"✓ Audit logs filtered by resource_type: {len(data['logs'])} logs")
    
    def test_audit_logs_unauthenticated(self):
        """Test audit logs requires authentication"""
        response = requests.get(f"{BASE_URL}/api/audit-logs")
        assert response.status_code in [401, 403], f"Should require auth: {response.status_code}"
        print("✓ Audit logs requires authentication")


class TestSalesEntriesPagination:
    """Tests for GET /api/sales-entries pagination"""
    
    def test_sales_entries_default_pagination(self, admin_headers):
        """Test sales entries returns paginated response"""
        response = requests.get(
            f"{BASE_URL}/api/sales-entries",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify paginated response structure
        assert "entries" in data, "Missing entries field"
        assert "total" in data, "Missing total field"
        assert "page" in data, "Missing page field"
        assert "pages" in data, "Missing pages field"
        
        assert isinstance(data["entries"], list)
        assert isinstance(data["total"], int)
        assert data["page"] == 1, "Default page should be 1"
        
        print(f"✓ Sales entries: {data['total']} total, {data['pages']} pages")
    
    def test_sales_entries_page_1_limit_5(self, admin_headers):
        """Test sales entries with page=1, limit=5"""
        response = requests.get(
            f"{BASE_URL}/api/sales-entries?page=1&limit=5",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["page"] == 1
        assert len(data["entries"]) <= 5
        
        # Calculate expected pages
        if data["total"] > 0:
            expected_pages = (data["total"] + 5 - 1) // 5
            assert data["pages"] == expected_pages, f"Expected {expected_pages} pages, got {data['pages']}"
        
        print(f"✓ Page 1 limit 5: {len(data['entries'])} entries, {data['pages']} total pages")
    
    def test_sales_entries_page_2_limit_5(self, admin_headers):
        """Test sales entries with page=2, limit=5"""
        response = requests.get(
            f"{BASE_URL}/api/sales-entries?page=2&limit=5",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["page"] == 2
        
        # If there are enough entries, page 2 should have entries
        if data["total"] > 5:
            assert len(data["entries"]) > 0, "Page 2 should have entries if total > 5"
        
        print(f"✓ Page 2 limit 5: {len(data['entries'])} entries")
    
    def test_sales_entries_different_pages_different_data(self, admin_headers):
        """Verify page 1 and page 2 return different entries"""
        response1 = requests.get(
            f"{BASE_URL}/api/sales-entries?page=1&limit=5",
            headers=admin_headers
        )
        response2 = requests.get(
            f"{BASE_URL}/api/sales-entries?page=2&limit=5",
            headers=admin_headers
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        if data1["total"] > 5 and len(data2["entries"]) > 0:
            # IDs should be different between pages
            ids1 = set(e["id"] for e in data1["entries"])
            ids2 = set(e["id"] for e in data2["entries"])
            assert ids1.isdisjoint(ids2), "Page 1 and Page 2 should have different entries"
            print("✓ Page 1 and Page 2 have different entries")
        else:
            print("✓ Not enough entries to verify different pages")
    
    def test_sales_entries_pagination_with_filters(self, admin_headers):
        """Test pagination works with other filters"""
        response = requests.get(
            f"{BASE_URL}/api/sales-entries?page=1&limit=10&warehouse_id={JULLANG_WAREHOUSE_ID}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "entries" in data
        assert "total" in data
        assert "pages" in data
        
        # All entries should be from Jullang warehouse
        for entry in data["entries"]:
            assert entry.get("warehouse_id") == JULLANG_WAREHOUSE_ID
        
        print(f"✓ Pagination with warehouse filter: {len(data['entries'])} Jullang entries")


class TestPlantIssuanceHistory:
    """Tests for GET /api/plant/issuance-history endpoint"""
    
    def test_plant_issuance_history_basic(self, admin_headers):
        """Test plant issuance history returns list"""
        response = requests.get(
            f"{BASE_URL}/api/plant/issuance-history",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Should return a list"
        
        # If there are entries, verify structure
        if len(data) > 0:
            entry = data[0]
            assert "id" in entry
            assert "date" in entry
            assert "dealer_id" in entry
            assert "dealer_name" in entry
            assert "qty_15kg" in entry
            assert "qty_21kg" in entry
        
        print(f"✓ Plant issuance history: {len(data)} entries")
    
    def test_plant_issuance_history_date_filter(self, admin_headers):
        """Test plant issuance history with date filters"""
        response = requests.get(
            f"{BASE_URL}/api/plant/issuance-history?start_date=2024-01-01&end_date=2026-12-31",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        
        print(f"✓ Plant issuance history with date filter: {len(data)} entries")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
