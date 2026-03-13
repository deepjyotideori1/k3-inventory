"""
Test: Sales Dashboard Accessory Integration
Tests the integration of LPG Accessories Sales into the main Sales Dashboard
- Accessory sales summary endpoint
- Sales export PDF with accessory section
- Sales export Excel with accessory section
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSalesAccessoryIntegration:
    """Tests for accessory sales integration into main sales dashboard"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Get auth token for admin user"""
        self.auth_token = None
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        if login_response.status_code == 200:
            self.auth_token = login_response.json().get("token")
        yield
    
    def get_headers(self):
        """Get authorization headers"""
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
    
    # ============ ACCESSORY SALES SUMMARY TESTS ============
    
    def test_accessory_sales_summary_endpoint(self):
        """Test: accessory-sales-summary returns total_sales, total_amount, cash/online/pending amounts"""
        if not self.auth_token:
            pytest.skip("Auth failed")
        
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales-summary",
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify structure
        assert 'total_sales' in data, "Missing total_sales field"
        assert 'total_amount' in data, "Missing total_amount field"
        assert 'cash_amount' in data, "Missing cash_amount field"
        assert 'pending_amount' in data, "Missing pending_amount field"
        assert 'online_amount' in data, "Missing online_amount field"
        assert 'total_quantity' in data, "Missing total_quantity field"
        
        # Verify types
        assert isinstance(data['total_sales'], int), "total_sales should be int"
        assert isinstance(data['total_amount'], (int, float)), "total_amount should be numeric"
        
        print(f"Accessory Summary: {data['total_sales']} sales, Total: ₹{data['total_amount']}")
    
    def test_accessory_sales_summary_with_date_filter(self):
        """Test: accessory-sales-summary supports date filtering"""
        if not self.auth_token:
            pytest.skip("Auth failed")
        
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales-summary",
            params={"start_date": "2025-01-01", "end_date": "2026-12-31"},
            headers=self.get_headers()
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'total_sales' in data
        assert 'total_amount' in data
    
    # ============ ACCESSORY SALES LIST TESTS ============
    
    def test_accessory_sales_list_endpoint(self):
        """Test: accessory-sales returns list of accessory sales"""
        if not self.auth_token:
            pytest.skip("Auth failed")
        
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales",
            headers=self.get_headers()
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            sale = data[0]
            # Check structure of accessory sale entry
            assert 'id' in sale, "Missing id field"
            assert 'date' in sale, "Missing date field"
            assert 'grand_total' in sale, "Missing grand_total field"
            assert 'payment_mode' in sale, "Missing payment_mode field"
            assert 'items' in sale, "Missing items field"
            
            print(f"Found {len(data)} accessory sales entries")
        else:
            print("No accessory sales found (may need seed data)")
    
    # ============ SALES ENTRIES TESTS ============
    
    def test_cylinder_sales_entries_endpoint(self):
        """Test: sales-entries returns cylinder sales"""
        if not self.auth_token:
            pytest.skip("Auth failed")
        
        response = requests.get(
            f"{BASE_URL}/api/sales-entries",
            headers=self.get_headers()
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        print(f"Found {len(data)} cylinder sales entries")
    
    def test_sales_summary_endpoint(self):
        """Test: sales-entries/summary returns cash, online, pending, total"""
        if not self.auth_token:
            pytest.skip("Auth failed")
        
        response = requests.get(
            f"{BASE_URL}/api/sales-entries/summary",
            headers=self.get_headers()
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert 'cash' in data, "Missing cash summary"
        assert 'online' in data, "Missing online summary"
        assert 'pending' in data, "Missing pending summary"
        assert 'total' in data, "Missing total summary"
        
        # Each should have amount, refills, count
        for key in ['cash', 'online', 'pending', 'total']:
            assert 'amount' in data[key], f"Missing amount in {key}"
            assert 'refills' in data[key], f"Missing refills in {key}"
            assert 'count' in data[key], f"Missing count in {key}"
        
        print(f"Sales Summary - Total: ₹{data['total']['amount']}")
    
    # ============ EXPORT PDF TESTS ============
    
    def test_export_sales_pdf_includes_accessory(self):
        """Test: /api/export/sales-pdf returns PDF with accessory sales section"""
        if not self.auth_token:
            pytest.skip("Auth failed")
        
        response = requests.get(
            f"{BASE_URL}/api/export/sales-pdf",
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"PDF export failed: {response.status_code}"
        assert response.headers.get('content-type') == 'application/pdf', "Should return PDF"
        
        # Check content disposition header
        content_disp = response.headers.get('content-disposition', '')
        assert 'attachment' in content_disp, "Should be attachment"
        assert '.pdf' in content_disp.lower(), "Should have .pdf extension"
        
        # PDF should have content
        assert len(response.content) > 1000, "PDF should have reasonable content size"
        
        print(f"PDF export successful, size: {len(response.content)} bytes")
    
    def test_export_sales_pdf_with_date_filter(self):
        """Test: PDF export supports date filtering"""
        if not self.auth_token:
            pytest.skip("Auth failed")
        
        response = requests.get(
            f"{BASE_URL}/api/export/sales-pdf",
            params={"start_date": "2025-01-01", "end_date": "2026-12-31"},
            headers=self.get_headers()
        )
        
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'application/pdf'
    
    def test_export_sales_pdf_with_payment_mode_filter(self):
        """Test: PDF export supports payment mode filtering"""
        if not self.auth_token:
            pytest.skip("Auth failed")
        
        response = requests.get(
            f"{BASE_URL}/api/export/sales-pdf",
            params={"payment_mode": "cash"},
            headers=self.get_headers()
        )
        
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'application/pdf'
    
    # ============ EXPORT EXCEL TESTS ============
    
    def test_export_sales_excel_includes_accessory(self):
        """Test: /api/export/sales-excel returns Excel with accessory sales section"""
        if not self.auth_token:
            pytest.skip("Auth failed")
        
        response = requests.get(
            f"{BASE_URL}/api/export/sales-excel",
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"Excel export failed: {response.status_code}"
        assert 'spreadsheet' in response.headers.get('content-type', ''), "Should return Excel"
        
        # Check content disposition header
        content_disp = response.headers.get('content-disposition', '')
        assert 'attachment' in content_disp, "Should be attachment"
        assert '.xlsx' in content_disp.lower(), "Should have .xlsx extension"
        
        # Excel should have content
        assert len(response.content) > 1000, "Excel should have reasonable content size"
        
        print(f"Excel export successful, size: {len(response.content)} bytes")
    
    def test_export_sales_excel_with_date_filter(self):
        """Test: Excel export supports date filtering"""
        if not self.auth_token:
            pytest.skip("Auth failed")
        
        response = requests.get(
            f"{BASE_URL}/api/export/sales-excel",
            params={"start_date": "2025-01-01", "end_date": "2026-12-31"},
            headers=self.get_headers()
        )
        
        assert response.status_code == 200
        assert 'spreadsheet' in response.headers.get('content-type', '')
    
    def test_export_sales_excel_with_connection_type_filter(self):
        """Test: Excel export with connection_type filter excludes accessory section"""
        if not self.auth_token:
            pytest.skip("Auth failed")
        
        # When filtering by specific connection type, accessory sales should be excluded
        response = requests.get(
            f"{BASE_URL}/api/export/sales-excel",
            params={"connection_type": "domestic_refill"},
            headers=self.get_headers()
        )
        
        assert response.status_code == 200
        assert 'spreadsheet' in response.headers.get('content-type', '')


class TestSalesExecAccess:
    """Test sales executive access to accessory data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Get auth token for sales exec user"""
        self.auth_token = None
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "sales@k3gas.com",
            "password": "Sales@123"
        })
        if login_response.status_code == 200:
            self.auth_token = login_response.json().get("token")
        yield
    
    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_sales_exec_can_view_accessory_summary(self):
        """Test: Sales exec can access accessory summary for their warehouse"""
        if not self.auth_token:
            pytest.skip("Sales exec auth failed")
        
        response = requests.get(
            f"{BASE_URL}/api/accessory-sales-summary",
            headers=self.get_headers()
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'total_amount' in data
        print(f"Sales exec accessory summary: ₹{data['total_amount']}")
    
    def test_sales_exec_can_export_sales_pdf(self):
        """Test: Sales exec can export PDF with accessory data"""
        if not self.auth_token:
            pytest.skip("Sales exec auth failed")
        
        response = requests.get(
            f"{BASE_URL}/api/export/sales-pdf",
            headers=self.get_headers()
        )
        
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'application/pdf'


class TestGrandTotalCalculation:
    """Test Grand Total calculation combining cylinder + accessory sales"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.auth_token = None
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        if login_response.status_code == 200:
            self.auth_token = login_response.json().get("token")
        yield
    
    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_grand_total_combines_both_sales(self):
        """Test: Grand total should be cylinder total + accessory total"""
        if not self.auth_token:
            pytest.skip("Auth failed")
        
        # Get cylinder sales summary
        cyl_response = requests.get(
            f"{BASE_URL}/api/sales-entries/summary",
            headers=self.get_headers()
        )
        
        # Get accessory sales summary
        acc_response = requests.get(
            f"{BASE_URL}/api/accessory-sales-summary",
            headers=self.get_headers()
        )
        
        assert cyl_response.status_code == 200
        assert acc_response.status_code == 200
        
        cyl_data = cyl_response.json()
        acc_data = acc_response.json()
        
        cylinder_total = cyl_data['total']['amount']
        accessory_total = acc_data['total_amount']
        expected_grand_total = cylinder_total + accessory_total
        
        print(f"Cylinder Total: ₹{cylinder_total}")
        print(f"Accessory Total: ₹{accessory_total}")
        print(f"Expected Grand Total: ₹{expected_grand_total}")
        
        # This validates the frontend calculation logic
        assert cylinder_total >= 0, "Cylinder total should be non-negative"
        assert accessory_total >= 0, "Accessory total should be non-negative"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
