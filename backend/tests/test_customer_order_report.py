"""
Test Customer Order Report Feature - Admin-only endpoints for warehouse-wise customer order reporting
Endpoints tested:
- GET /api/admin/customer-order-report (Admin only)
- GET /api/export/customer-order-report-pdf (Admin only)
- GET /api/export/customer-order-report-excel (Admin only)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"email": "admin@k3gas.com", "password": "Admin@123"}
MANAGER_CREDS = {"email": "jullang@k3gas.com", "password": "Jullang@123"}

class TestCustomerOrderReport:
    """Test suite for Customer Order Report feature"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def manager_token(self):
        """Get warehouse manager auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=MANAGER_CREDS)
        assert response.status_code == 200, f"Manager login failed: {response.text}"
        return response.json()["token"]
    
    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def manager_headers(self, manager_token):
        return {"Authorization": f"Bearer {manager_token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def warehouses(self, admin_headers):
        """Get list of warehouses"""
        response = requests.get(f"{BASE_URL}/api/warehouses", headers=admin_headers)
        return response.json() if response.status_code == 200 else []

    # ============ Authentication Tests ============
    
    def test_login_admin_success(self):
        """Test admin login returns 200"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print("PASS: Admin login successful")
    
    def test_login_manager_success(self):
        """Test warehouse manager login returns 200"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=MANAGER_CREDS)
        assert response.status_code == 200, f"Manager login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "warehouse_manager"
        print("PASS: Warehouse manager login successful")

    # ============ Customer Order Report API Tests ============
    
    def test_customer_order_report_admin_access(self, admin_headers):
        """Test GET /api/admin/customer-order-report returns 200 for admin"""
        response = requests.get(f"{BASE_URL}/api/admin/customer-order-report", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "customers" in data, "Response should have 'customers' field"
        assert "summary" in data, "Response should have 'summary' field"
        
        # Verify summary structure
        summary = data["summary"]
        assert "total_customers" in summary, "Summary should have 'total_customers'"
        assert "total_orders" in summary, "Summary should have 'total_orders'"
        assert "total_refills" in summary, "Summary should have 'total_refills'"
        
        print(f"PASS: Customer order report API works for admin. {summary['total_customers']} customers, {summary['total_orders']} orders, {summary['total_refills']} refills")
    
    def test_customer_order_report_manager_forbidden(self, manager_headers):
        """Test GET /api/admin/customer-order-report returns 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/admin/customer-order-report", headers=manager_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("PASS: Non-admin correctly gets 403 Forbidden")
    
    def test_customer_order_report_unauthenticated(self):
        """Test GET /api/admin/customer-order-report returns 401/403 without auth"""
        response = requests.get(f"{BASE_URL}/api/admin/customer-order-report")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: Unauthenticated request correctly blocked")
    
    def test_customer_order_report_warehouse_filter(self, admin_headers, warehouses):
        """Test warehouse filter parameter works correctly"""
        if not warehouses:
            pytest.skip("No warehouses available")
        
        # Get first non-plant warehouse
        non_plant_wh = next((w for w in warehouses if not w.get('is_plant')), None)
        if not non_plant_wh:
            pytest.skip("No non-plant warehouses available")
        
        response = requests.get(
            f"{BASE_URL}/api/admin/customer-order-report",
            params={"warehouse_id": non_plant_wh["id"]},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.status_code}"
        data = response.json()
        
        # Verify all returned customers belong to filtered warehouse
        for c in data.get("customers", []):
            assert c.get("warehouse_id") == non_plant_wh["id"] or c.get("warehouse_name") == non_plant_wh["name"], \
                f"Customer {c.get('customer_name')} does not belong to filtered warehouse"
        
        print(f"PASS: Warehouse filter works. Found {len(data.get('customers', []))} customers for {non_plant_wh['name']}")
    
    def test_customer_order_report_date_range_filter(self, admin_headers):
        """Test date range filter parameters work"""
        response = requests.get(
            f"{BASE_URL}/api/admin/customer-order-report",
            params={"start_date": "2025-01-01", "end_date": "2026-12-31"},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.status_code}"
        print("PASS: Date range filter accepted")
    
    def test_customer_order_report_search_filter(self, admin_headers):
        """Test search filter parameter works"""
        response = requests.get(
            f"{BASE_URL}/api/admin/customer-order-report",
            params={"search": "test"},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.status_code}"
        print("PASS: Search filter accepted")
    
    def test_customer_order_report_customer_structure(self, admin_headers):
        """Test customer objects have all required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/customer-order-report", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        if data.get("customers"):
            customer = data["customers"][0]
            required_fields = ["customer_name", "customer_id", "warehouse_id", "warehouse_name", "entries", "total_entries"]
            for field in required_fields:
                assert field in customer, f"Customer missing required field: {field}"
            
            # Optional but expected fields
            optional_fields = ["phone", "consumer_no", "address", "connection_date"]
            present_optional = [f for f in optional_fields if f in customer]
            print(f"PASS: Customer structure verified. Optional fields present: {present_optional}")
        else:
            print("PASS: No customers to verify (empty response is valid)")
    
    def test_customer_order_report_entry_structure(self, admin_headers):
        """Test entry objects within customers have required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/customer-order-report", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Find a customer with entries
        customer_with_entries = next((c for c in data.get("customers", []) if c.get("entries")), None)
        
        if customer_with_entries:
            entry = customer_with_entries["entries"][0]
            required_fields = ["id", "date", "type", "quantity", "status"]
            for field in required_fields:
                assert field in entry, f"Entry missing required field: {field}"
            
            # Check entry type is Connection or Refill
            assert entry["type"] in ["New Connection", "Refill"], f"Unexpected entry type: {entry['type']}"
            
            print(f"PASS: Entry structure verified. Type: {entry['type']}, Status: {entry['status']}")
        else:
            print("PASS: No entries to verify (empty entries is valid)")
    
    def test_customer_order_report_entries_sorted_by_date(self, admin_headers):
        """Test entries within each customer are sorted by date ascending"""
        response = requests.get(f"{BASE_URL}/api/admin/customer-order-report", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        for customer in data.get("customers", []):
            entries = customer.get("entries", [])
            if len(entries) > 1:
                dates = [e.get("date", "") for e in entries]
                assert dates == sorted(dates), f"Entries not sorted by date for customer {customer.get('customer_name')}"
        
        print("PASS: Entries sorted by date ascending")
    
    def test_customer_order_report_customers_sorted_alphabetically(self, admin_headers):
        """Test customers are sorted alphabetically by name"""
        response = requests.get(f"{BASE_URL}/api/admin/customer-order-report", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        customers = data.get("customers", [])
        if len(customers) > 1:
            names = [c.get("customer_name", "").lower() for c in customers]
            assert names == sorted(names), "Customers not sorted alphabetically"
        
        print("PASS: Customers sorted alphabetically")

    # ============ PDF Export Tests ============
    
    def test_export_pdf_admin_access(self, admin_headers):
        """Test PDF export returns 200 for admin"""
        response = requests.get(f"{BASE_URL}/api/export/customer-order-report-pdf", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        assert "application/pdf" in response.headers.get("content-type", ""), "Response should be PDF"
        assert len(response.content) > 0, "PDF content should not be empty"
        print(f"PASS: PDF export works. Size: {len(response.content)} bytes")
    
    def test_export_pdf_manager_forbidden(self, manager_headers):
        """Test PDF export returns 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/export/customer-order-report-pdf", headers=manager_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("PASS: Non-admin correctly gets 403 for PDF export")
    
    def test_export_pdf_with_warehouse_filter(self, admin_headers, warehouses):
        """Test PDF export with warehouse filter"""
        if not warehouses:
            pytest.skip("No warehouses available")
        
        non_plant_wh = next((w for w in warehouses if not w.get('is_plant')), None)
        if not non_plant_wh:
            pytest.skip("No non-plant warehouses")
        
        response = requests.get(
            f"{BASE_URL}/api/export/customer-order-report-pdf",
            params={"warehouse_id": non_plant_wh["id"]},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.status_code}"
        assert "application/pdf" in response.headers.get("content-type", "")
        print(f"PASS: PDF export with warehouse filter works")
    
    def test_export_pdf_with_date_filters(self, admin_headers):
        """Test PDF export with date filters"""
        response = requests.get(
            f"{BASE_URL}/api/export/customer-order-report-pdf",
            params={"start_date": "2025-01-01", "end_date": "2026-12-31"},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.status_code}"
        print("PASS: PDF export with date filters works")

    # ============ Excel Export Tests ============
    
    def test_export_excel_admin_access(self, admin_headers):
        """Test Excel export returns 200 for admin"""
        response = requests.get(f"{BASE_URL}/api/export/customer-order-report-excel", headers=admin_headers)
        assert response.status_code == 200, f"Failed: {response.status_code} - {response.text}"
        content_type = response.headers.get("content-type", "")
        assert "spreadsheetml" in content_type or "excel" in content_type.lower() or "octet-stream" in content_type, \
            f"Response should be Excel, got: {content_type}"
        assert len(response.content) > 0, "Excel content should not be empty"
        print(f"PASS: Excel export works. Size: {len(response.content)} bytes")
    
    def test_export_excel_manager_forbidden(self, manager_headers):
        """Test Excel export returns 403 for non-admin"""
        response = requests.get(f"{BASE_URL}/api/export/customer-order-report-excel", headers=manager_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("PASS: Non-admin correctly gets 403 for Excel export")
    
    def test_export_excel_with_warehouse_filter(self, admin_headers, warehouses):
        """Test Excel export with warehouse filter"""
        if not warehouses:
            pytest.skip("No warehouses available")
        
        non_plant_wh = next((w for w in warehouses if not w.get('is_plant')), None)
        if not non_plant_wh:
            pytest.skip("No non-plant warehouses")
        
        response = requests.get(
            f"{BASE_URL}/api/export/customer-order-report-excel",
            params={"warehouse_id": non_plant_wh["id"]},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.status_code}"
        print("PASS: Excel export with warehouse filter works")
    
    def test_export_excel_with_date_filters(self, admin_headers):
        """Test Excel export with date filters"""
        response = requests.get(
            f"{BASE_URL}/api/export/customer-order-report-excel",
            params={"start_date": "2025-01-01", "end_date": "2026-12-31"},
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.status_code}"
        print("PASS: Excel export with date filters works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
