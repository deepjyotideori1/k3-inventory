"""
Backend tests for Customer LPG Refill Status Feature
Tests the new refill-status endpoints and export functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@k3gas.com",
        "password": "Admin@123"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")

@pytest.fixture(scope="module")
def warehouse_manager_token():
    """Get warehouse manager authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "jullang@k3gas.com",
        "password": "Jullang@123"
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Warehouse manager authentication failed")

@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

@pytest.fixture
def wm_headers(warehouse_manager_token):
    return {"Authorization": f"Bearer {warehouse_manager_token}", "Content-Type": "application/json"}


class TestAuthLogin:
    """Test authentication endpoints"""
    
    def test_admin_login_success(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Token missing in response"
        assert "user" in data, "User missing in response"
        assert data["user"]["role"] == "admin"
        print("PASS: Admin login successful")

    def test_warehouse_manager_login_success(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "jullang@k3gas.com",
            "password": "Jullang@123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Token missing in response"
        assert data["user"]["role"] == "warehouse_manager"
        print("PASS: Warehouse manager login successful")


class TestCustomerRefillStatusAPI:
    """Test GET /api/customers/refill-status endpoint"""
    
    def test_refill_status_endpoint_returns_200(self, admin_headers):
        """Test that refill-status endpoint returns 200 for authenticated admin"""
        response = requests.get(f"{BASE_URL}/api/customers/refill-status", headers=admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: /api/customers/refill-status returns 200")
    
    def test_refill_status_response_structure(self, admin_headers):
        """Test that response has correct structure with customers and summary"""
        response = requests.get(f"{BASE_URL}/api/customers/refill-status", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level keys
        assert "customers" in data, "Missing 'customers' in response"
        assert "summary" in data, "Missing 'summary' in response"
        
        # Check summary stats
        summary = data["summary"]
        assert "total" in summary, "Missing 'total' in summary"
        assert "recent" in summary, "Missing 'recent' in summary"
        assert "moderate" in summary, "Missing 'moderate' in summary"
        assert "overdue" in summary, "Missing 'overdue' in summary"
        assert "no_history" in summary, "Missing 'no_history' in summary"
        
        print(f"PASS: Response has correct structure - Summary: {summary}")
    
    def test_refill_status_customer_fields(self, admin_headers):
        """Test that each customer has required refill fields"""
        response = requests.get(f"{BASE_URL}/api/customers/refill-status", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        if len(data["customers"]) > 0:
            customer = data["customers"][0]
            assert "id" in customer, "Missing 'id' in customer"
            assert "customer_name" in customer, "Missing 'customer_name' in customer"
            assert "last_refill_date" in customer, "Missing 'last_refill_date' in customer"
            assert "days_since_refill" in customer, "Missing 'days_since_refill' in customer"
            assert "warehouse_name" in customer, "Missing 'warehouse_name' in customer"
            print(f"PASS: Customer has required fields - Example: {customer['customer_name']}, last_refill: {customer['last_refill_date']}, days_since: {customer['days_since_refill']}")
        else:
            print("PASS: Response structure correct (no customers found)")
    
    def test_refill_status_with_warehouse_filter(self, admin_headers):
        """Test filtering by warehouse_id"""
        # First get warehouses
        wh_response = requests.get(f"{BASE_URL}/api/warehouses", headers=admin_headers)
        assert wh_response.status_code == 200
        warehouses = wh_response.json()
        
        if len(warehouses) > 0:
            warehouse_id = warehouses[0]["id"]
            response = requests.get(f"{BASE_URL}/api/customers/refill-status?warehouse_id={warehouse_id}", headers=admin_headers)
            assert response.status_code == 200
            print(f"PASS: Refill status filtered by warehouse_id={warehouse_id}")
    
    def test_refill_status_warehouse_manager_access(self, wm_headers):
        """Test that warehouse manager can access refill status (limited to their warehouse)"""
        response = requests.get(f"{BASE_URL}/api/customers/refill-status", headers=wm_headers)
        assert response.status_code == 200, f"WM access failed: {response.text}"
        data = response.json()
        assert "customers" in data
        print(f"PASS: Warehouse manager can access refill status - Total customers: {data['summary']['total']}")
    
    def test_refill_status_unauthenticated(self):
        """Test that unauthenticated requests are rejected"""
        response = requests.get(f"{BASE_URL}/api/customers/refill-status")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: Unauthenticated requests correctly rejected")


class TestCustomerLastRefillAPI:
    """Test GET /api/customers/{id}/last-refill endpoint"""
    
    def test_last_refill_endpoint_with_valid_customer(self, admin_headers):
        """Test last-refill endpoint with a valid customer ID"""
        # First get a customer ID
        customers_response = requests.get(f"{BASE_URL}/api/customers", headers=admin_headers)
        assert customers_response.status_code == 200
        customers = customers_response.json()
        
        if len(customers) > 0:
            customer_id = customers[0]["id"]
            response = requests.get(f"{BASE_URL}/api/customers/{customer_id}/last-refill", headers=admin_headers)
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            data = response.json()
            assert "has_refill" in data, "Missing 'has_refill' in response"
            
            if data["has_refill"]:
                assert "last_refill_date" in data, "Missing 'last_refill_date'"
                assert "days_since_refill" in data, "Missing 'days_since_refill'"
                print(f"PASS: Customer {customer_id} has refill - last: {data['last_refill_date']}, days: {data['days_since_refill']}")
            else:
                assert "message" in data, "Missing 'message' for no refill"
                print(f"PASS: Customer {customer_id} has no refill history - message: {data.get('message')}")
        else:
            pytest.skip("No customers found to test")
    
    def test_last_refill_with_invalid_customer_id(self, admin_headers):
        """Test last-refill endpoint with invalid customer ID"""
        response = requests.get(f"{BASE_URL}/api/customers/invalid-id-12345/last-refill", headers=admin_headers)
        # Should return 200 with has_refill: false (since customer doesn't exist, no refill found)
        assert response.status_code == 200
        data = response.json()
        assert data["has_refill"] == False, "Expected has_refill=false for invalid customer"
        print("PASS: Invalid customer ID returns has_refill=false")


class TestCustomerRefillExportPDF:
    """Test GET /api/export/customer-refill-pdf endpoint"""
    
    def test_export_refill_pdf_returns_file(self, admin_headers):
        """Test that PDF export returns a file"""
        response = requests.get(f"{BASE_URL}/api/export/customer-refill-pdf", headers=admin_headers)
        assert response.status_code == 200, f"PDF export failed: {response.status_code} - {response.text}"
        assert response.headers.get("content-type") == "application/pdf", f"Expected PDF content-type, got {response.headers.get('content-type')}"
        assert "content-disposition" in response.headers, "Missing content-disposition header"
        assert "customer_refill_status" in response.headers["content-disposition"], "Filename missing in content-disposition"
        assert len(response.content) > 0, "PDF content is empty"
        print(f"PASS: Refill PDF export successful - Size: {len(response.content)} bytes")
    
    def test_export_refill_pdf_with_warehouse_filter(self, admin_headers):
        """Test PDF export with warehouse filter"""
        wh_response = requests.get(f"{BASE_URL}/api/warehouses", headers=admin_headers)
        if wh_response.status_code == 200 and len(wh_response.json()) > 0:
            warehouse_id = wh_response.json()[0]["id"]
            response = requests.get(f"{BASE_URL}/api/export/customer-refill-pdf?warehouse_id={warehouse_id}", headers=admin_headers)
            assert response.status_code == 200
            print(f"PASS: PDF export with warehouse filter successful")
    
    def test_export_refill_pdf_warehouse_manager(self, wm_headers):
        """Test warehouse manager can export PDF"""
        response = requests.get(f"{BASE_URL}/api/export/customer-refill-pdf", headers=wm_headers)
        assert response.status_code == 200, f"WM PDF export failed: {response.status_code}"
        print("PASS: Warehouse manager can export refill PDF")


class TestCustomerRefillExportExcel:
    """Test GET /api/export/customer-refill-excel endpoint"""
    
    def test_export_refill_excel_returns_file(self, admin_headers):
        """Test that Excel export returns a file"""
        response = requests.get(f"{BASE_URL}/api/export/customer-refill-excel", headers=admin_headers)
        assert response.status_code == 200, f"Excel export failed: {response.status_code} - {response.text}"
        content_type = response.headers.get("content-type", "")
        assert "spreadsheet" in content_type or "excel" in content_type.lower(), f"Expected Excel content-type, got {content_type}"
        assert "content-disposition" in response.headers, "Missing content-disposition header"
        assert "customer_refill_status" in response.headers["content-disposition"], "Filename missing in content-disposition"
        assert len(response.content) > 0, "Excel content is empty"
        print(f"PASS: Refill Excel export successful - Size: {len(response.content)} bytes")
    
    def test_export_refill_excel_with_warehouse_filter(self, admin_headers):
        """Test Excel export with warehouse filter"""
        wh_response = requests.get(f"{BASE_URL}/api/warehouses", headers=admin_headers)
        if wh_response.status_code == 200 and len(wh_response.json()) > 0:
            warehouse_id = wh_response.json()[0]["id"]
            response = requests.get(f"{BASE_URL}/api/export/customer-refill-excel?warehouse_id={warehouse_id}", headers=admin_headers)
            assert response.status_code == 200
            print("PASS: Excel export with warehouse filter successful")
    
    def test_export_refill_excel_warehouse_manager(self, wm_headers):
        """Test warehouse manager can export Excel"""
        response = requests.get(f"{BASE_URL}/api/export/customer-refill-excel", headers=wm_headers)
        assert response.status_code == 200, f"WM Excel export failed: {response.status_code}"
        print("PASS: Warehouse manager can export refill Excel")


class TestDaysSinceRefillCalculation:
    """Test the days_since_refill calculation is correct"""
    
    def test_days_calculation_with_refill_data(self, admin_headers):
        """Verify days_since_refill is calculated correctly for customers with refill records"""
        response = requests.get(f"{BASE_URL}/api/customers/refill-status", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        customers_with_refill = [c for c in data["customers"] if c["days_since_refill"] is not None]
        
        if len(customers_with_refill) > 0:
            customer = customers_with_refill[0]
            days = customer["days_since_refill"]
            last_refill_date = customer["last_refill_date"]
            
            # Verify days is a non-negative integer
            assert isinstance(days, int), f"days_since_refill should be int, got {type(days)}"
            assert days >= 0, f"days_since_refill should be non-negative, got {days}"
            
            print(f"PASS: Customer '{customer['customer_name']}' - Last refill: {last_refill_date}, Days since: {days}")
        else:
            print("INFO: No customers with refill data found - calculation test skipped")
    
    def test_no_history_customers_have_null_days(self, admin_headers):
        """Verify customers without refill history have null days_since_refill"""
        response = requests.get(f"{BASE_URL}/api/customers/refill-status", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        customers_no_history = [c for c in data["customers"] if c["days_since_refill"] is None]
        
        if len(customers_no_history) > 0:
            customer = customers_no_history[0]
            assert customer["last_refill_date"] is None, "last_refill_date should be None for no history"
            print(f"PASS: Customer '{customer['customer_name']}' has no refill history (days_since_refill=None)")
        
        # Verify summary stats
        no_history_count = data["summary"]["no_history"]
        actual_no_history = len(customers_no_history)
        assert no_history_count == actual_no_history, f"Summary no_history ({no_history_count}) != actual ({actual_no_history})"
        print(f"PASS: Summary 'no_history' count matches - {no_history_count} customers without history")


class TestRefillStatusSummaryStats:
    """Test the summary statistics in refill-status response"""
    
    def test_summary_stats_are_accurate(self, admin_headers):
        """Verify summary statistics match actual data"""
        response = requests.get(f"{BASE_URL}/api/customers/refill-status", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        customers = data["customers"]
        summary = data["summary"]
        
        # Calculate expected values
        total = len(customers)
        recent = sum(1 for c in customers if c["days_since_refill"] is not None and c["days_since_refill"] <= 15)
        moderate = sum(1 for c in customers if c["days_since_refill"] is not None and 15 < c["days_since_refill"] <= 30)
        overdue = sum(1 for c in customers if c["days_since_refill"] is not None and c["days_since_refill"] > 30)
        no_history = sum(1 for c in customers if c["days_since_refill"] is None)
        
        # Verify
        assert summary["total"] == total, f"Total mismatch: {summary['total']} != {total}"
        assert summary["recent"] == recent, f"Recent mismatch: {summary['recent']} != {recent}"
        assert summary["moderate"] == moderate, f"Moderate mismatch: {summary['moderate']} != {moderate}"
        assert summary["overdue"] == overdue, f"Overdue mismatch: {summary['overdue']} != {overdue}"
        assert summary["no_history"] == no_history, f"No history mismatch: {summary['no_history']} != {no_history}"
        
        print(f"PASS: Summary stats verified - Total: {total}, Recent (<=15d): {recent}, Moderate (16-30d): {moderate}, Overdue (>30d): {overdue}, No history: {no_history}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
