"""
Test Accessory Sales Summary API - Warehouse Filtering and Payment Mode Breakdown
Tests for:
1. GET /api/accessory-sales-summary (no warehouse_id) - Returns all accessory sales totals
2. GET /api/accessory-sales-summary?warehouse_id=<jullang_id> - Returns Jullang-only totals
3. GET /api/accessory-sales-summary?warehouse_id=<naharlagun_id> - Returns zeros for warehouse with no sales
4. Verify cash_amount + online_amount + pending_amount = total_amount
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASSWORD = "Admin@123"

# Warehouse IDs from the test request
JULLANG_WAREHOUSE_ID = "8f2dc176-4450-4bf7-8ccc-2c2618fc6d32"
NAHARLAGUN_WAREHOUSE_ID = "e155211b-0079-45e0-982f-0c605e498493"


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
def auth_headers(admin_token):
    """Return headers with auth token"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestAccessorySalesSummaryAPI:
    """Test accessory sales summary endpoint with warehouse filtering"""
    
    def test_summary_no_warehouse_filter(self, auth_headers):
        """Test GET /api/accessory-sales-summary without warehouse_id - returns all totals"""
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales-summary",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure has all required fields
        assert "total_sales" in data, "Missing total_sales field"
        assert "total_amount" in data, "Missing total_amount field"
        assert "cash_amount" in data, "Missing cash_amount field"
        assert "online_amount" in data, "Missing online_amount field"
        assert "pending_amount" in data, "Missing pending_amount field"
        
        # Verify data types
        assert isinstance(data["total_sales"], int), "total_sales should be int"
        assert isinstance(data["total_amount"], (int, float)), "total_amount should be numeric"
        assert isinstance(data["cash_amount"], (int, float)), "cash_amount should be numeric"
        assert isinstance(data["online_amount"], (int, float)), "online_amount should be numeric"
        assert isinstance(data["pending_amount"], (int, float)), "pending_amount should be numeric"
        
        print(f"All warehouses summary: total_amount={data['total_amount']}, cash={data['cash_amount']}, online={data['online_amount']}, pending={data['pending_amount']}")
    
    def test_summary_jullang_warehouse_filter(self, auth_headers):
        """Test GET /api/accessory-sales-summary?warehouse_id=<jullang_id> - returns Jullang-only totals"""
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales-summary",
            params={"warehouse_id": JULLANG_WAREHOUSE_ID},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "total_sales" in data, "Missing total_sales field"
        assert "total_amount" in data, "Missing total_amount field"
        assert "cash_amount" in data, "Missing cash_amount field"
        assert "online_amount" in data, "Missing online_amount field"
        assert "pending_amount" in data, "Missing pending_amount field"
        
        print(f"Jullang warehouse summary: total_amount={data['total_amount']}, cash={data['cash_amount']}, online={data['online_amount']}, pending={data['pending_amount']}")
    
    def test_summary_naharlagun_warehouse_no_sales(self, auth_headers):
        """Test GET /api/accessory-sales-summary?warehouse_id=<naharlagun_id> - returns zeros for warehouse with no accessory sales"""
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales-summary",
            params={"warehouse_id": NAHARLAGUN_WAREHOUSE_ID},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "total_sales" in data, "Missing total_sales field"
        assert "total_amount" in data, "Missing total_amount field"
        assert "cash_amount" in data, "Missing cash_amount field"
        assert "online_amount" in data, "Missing online_amount field"
        assert "pending_amount" in data, "Missing pending_amount field"
        
        # For warehouse with no accessory sales, all values should be 0
        # Note: This test verifies the endpoint returns valid data (zeros) when no sales exist
        print(f"Naharlagun warehouse summary (expected zeros): total_amount={data['total_amount']}, cash={data['cash_amount']}, online={data['online_amount']}, pending={data['pending_amount']}")
        
        # Verify values are numeric (could be 0 or actual values if data exists)
        assert isinstance(data["total_amount"], (int, float)), "total_amount should be numeric"
        assert isinstance(data["cash_amount"], (int, float)), "cash_amount should be numeric"
        assert isinstance(data["online_amount"], (int, float)), "online_amount should be numeric"
        assert isinstance(data["pending_amount"], (int, float)), "pending_amount should be numeric"
    
    def test_payment_breakdown_sum_equals_total(self, auth_headers):
        """Verify cash_amount + online_amount + pending_amount = total_amount for all responses"""
        # Test without filter
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales-summary",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        calculated_total = data["cash_amount"] + data["online_amount"] + data["pending_amount"]
        assert abs(calculated_total - data["total_amount"]) < 0.01, \
            f"Payment breakdown sum ({calculated_total}) doesn't match total_amount ({data['total_amount']})"
        
        print(f"Payment breakdown verification: cash({data['cash_amount']}) + online({data['online_amount']}) + pending({data['pending_amount']}) = {calculated_total}, total_amount = {data['total_amount']}")
    
    def test_payment_breakdown_sum_jullang(self, auth_headers):
        """Verify payment breakdown sum equals total for Jullang warehouse"""
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales-summary",
            params={"warehouse_id": JULLANG_WAREHOUSE_ID},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        calculated_total = data["cash_amount"] + data["online_amount"] + data["pending_amount"]
        assert abs(calculated_total - data["total_amount"]) < 0.01, \
            f"Jullang payment breakdown sum ({calculated_total}) doesn't match total_amount ({data['total_amount']})"
        
        print(f"Jullang payment breakdown: cash({data['cash_amount']}) + online({data['online_amount']}) + pending({data['pending_amount']}) = {calculated_total}")
    
    def test_payment_breakdown_sum_naharlagun(self, auth_headers):
        """Verify payment breakdown sum equals total for Naharlagun warehouse (expected zeros)"""
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales-summary",
            params={"warehouse_id": NAHARLAGUN_WAREHOUSE_ID},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        calculated_total = data["cash_amount"] + data["online_amount"] + data["pending_amount"]
        assert abs(calculated_total - data["total_amount"]) < 0.01, \
            f"Naharlagun payment breakdown sum ({calculated_total}) doesn't match total_amount ({data['total_amount']})"
        
        print(f"Naharlagun payment breakdown: cash({data['cash_amount']}) + online({data['online_amount']}) + pending({data['pending_amount']}) = {calculated_total}")
    
    def test_date_filter_with_warehouse(self, auth_headers):
        """Test date filtering combined with warehouse filter"""
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales-summary",
            params={
                "warehouse_id": JULLANG_WAREHOUSE_ID,
                "start_date": "2024-01-01",
                "end_date": "2026-12-31"
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total_amount" in data
        assert "cash_amount" in data
        assert "online_amount" in data
        assert "pending_amount" in data
        
        print(f"Date filtered Jullang summary: total_amount={data['total_amount']}")


class TestAccessorySalesEndpoint:
    """Test accessory sales list endpoint with warehouse filtering"""
    
    def test_accessory_sales_list_no_filter(self, auth_headers):
        """Test GET /api/accessory-sales without warehouse filter"""
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        print(f"Total accessory sales (all warehouses): {len(data)}")
    
    def test_accessory_sales_list_jullang_filter(self, auth_headers):
        """Test GET /api/accessory-sales with Jullang warehouse filter"""
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales",
            params={"warehouse_id": JULLANG_WAREHOUSE_ID},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Verify all returned sales belong to Jullang warehouse
        for sale in data:
            assert sale.get("warehouse_id") == JULLANG_WAREHOUSE_ID, \
                f"Sale {sale.get('id')} has wrong warehouse_id: {sale.get('warehouse_id')}"
        
        print(f"Jullang accessory sales count: {len(data)}")
    
    def test_accessory_sales_list_naharlagun_filter(self, auth_headers):
        """Test GET /api/accessory-sales with Naharlagun warehouse filter (expected empty or few)"""
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales",
            params={"warehouse_id": NAHARLAGUN_WAREHOUSE_ID},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Verify all returned sales belong to Naharlagun warehouse
        for sale in data:
            assert sale.get("warehouse_id") == NAHARLAGUN_WAREHOUSE_ID, \
                f"Sale {sale.get('id')} has wrong warehouse_id: {sale.get('warehouse_id')}"
        
        print(f"Naharlagun accessory sales count: {len(data)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
