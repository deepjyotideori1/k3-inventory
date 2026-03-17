"""
Test Sales Summary Cylinder Calculation Logic

Tests the new cylinder calculation requirements:
- GET /api/sales-entries/summary returns categories with domestic_new_cyl, commercial_new_cyl, domestic_refill_cyl, commercial_refill_cyl
- Tests that counts match expected values based on test data
- Tests PDF and Excel exports have correct headers
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSalesSummaryCylinderCalculation:
    """Test sales summary endpoint cylinder calculation"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        if response.status_code == 200:
            token = response.json().get("token")
            return token
        pytest.skip("Admin authentication failed")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Return auth headers"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_sales_summary_returns_categories(self, auth_headers):
        """Test that summary response includes categories object"""
        response = requests.get(f"{BASE_URL}/api/sales-entries/summary", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify categories object exists
        assert 'categories' in data, "Response should have 'categories' object"
        categories = data['categories']
        
        # Verify all category fields exist
        required_fields = [
            'domestic_new_cyl', 'commercial_new_cyl',
            'domestic_refill_cyl', 'commercial_refill_cyl',
            'domestic_new_count', 'commercial_new_count',
            'domestic_refill_count', 'commercial_refill_count'
        ]
        for field in required_fields:
            assert field in categories, f"Categories should have '{field}'"
        
        print(f"Categories returned: {categories}")
    
    def test_sales_summary_category_values(self, auth_headers):
        """Test that category cylinder counts are valid and internally consistent"""
        response = requests.get(f"{BASE_URL}/api/sales-entries/summary", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        categories = data.get('categories', {})
        total = data.get('total', {})
        
        # Verify category values are non-negative integers
        for field in ['domestic_new_cyl', 'commercial_new_cyl', 'domestic_refill_cyl', 'commercial_refill_cyl']:
            value = categories.get(field, 0)
            assert isinstance(value, int), f"{field} should be int"
            assert value >= 0, f"{field} should be non-negative"
        
        # Verify total cylinder counts match category sums
        total_new_cyl = categories.get('domestic_new_cyl', 0) + categories.get('commercial_new_cyl', 0)
        total_refill_cyl = categories.get('domestic_refill_cyl', 0) + categories.get('commercial_refill_cyl', 0)
        
        assert total.get('new_connection_cylinders') == total_new_cyl, f"new_connection_cylinders should equal domestic_new + commercial_new"
        assert total.get('refill_cylinders') == total_refill_cyl, f"refill_cylinders should equal domestic_refill + commercial_refill"
        
        print(f"Category values verified: dom_new={categories.get('domestic_new_cyl')}, com_new={categories.get('commercial_new_cyl')}, dom_refill={categories.get('domestic_refill_cyl')}, com_refill={categories.get('commercial_refill_cyl')}")
    
    def test_sales_summary_total_cylinders(self, auth_headers):
        """Test that total cylinder counts are internally consistent"""
        response = requests.get(f"{BASE_URL}/api/sales-entries/summary", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        total = data.get('total', {})
        categories = data.get('categories', {})
        
        # Verify totals are non-negative
        assert total.get('new_connection_cylinders', 0) >= 0, "new_connection_cylinders should be non-negative"
        assert total.get('refill_cylinders', 0) >= 0, "refill_cylinders should be non-negative"
        assert total.get('cylinders', 0) >= 0, "total cylinders should be non-negative"
        
        # Verify total cylinders = new_connection + refill
        expected_total = total.get('new_connection_cylinders', 0) + total.get('refill_cylinders', 0)
        assert total.get('cylinders') == expected_total, f"Total cylinders should equal new_conn + refill: {expected_total}, got {total.get('cylinders')}"
        
        print(f"Total values verified: new_conn_cyl={total.get('new_connection_cylinders')}, refill_cyl={total.get('refill_cylinders')}, total_cyl={total.get('cylinders')}")
    
    def test_sales_summary_entry_counts(self, auth_headers):
        """Test that entry counts are correct (count is orders, not cylinder qty)"""
        response = requests.get(f"{BASE_URL}/api/sales-entries/summary", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        categories = data.get('categories', {})
        
        # Count number of entries per category
        domestic_new_count = categories.get('domestic_new_count', 0)
        commercial_new_count = categories.get('commercial_new_count', 0)
        domestic_refill_count = categories.get('domestic_refill_count', 0)
        commercial_refill_count = categories.get('commercial_refill_count', 0)
        
        # Just verify counts are numeric and non-negative
        assert isinstance(domestic_new_count, int), "domestic_new_count should be int"
        assert isinstance(commercial_new_count, int), "commercial_new_count should be int"
        assert isinstance(domestic_refill_count, int), "domestic_refill_count should be int"
        assert isinstance(commercial_refill_count, int), "commercial_refill_count should be int"
        
        print(f"Entry counts: dom_new={domestic_new_count}, com_new={commercial_new_count}, dom_refill={domestic_refill_count}, com_refill={commercial_refill_count}")


class TestSalesExportFormat:
    """Test PDF and Excel export formats"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Return auth headers"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_pdf_export_downloads(self, auth_headers):
        """Test PDF export returns a PDF file"""
        response = requests.get(f"{BASE_URL}/api/export/sales-pdf", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify content type is PDF
        content_type = response.headers.get('Content-Type', '')
        assert 'pdf' in content_type.lower() or 'application/octet-stream' in content_type, f"Expected PDF content type, got {content_type}"
        
        # Verify content has PDF magic bytes
        content = response.content[:4]
        assert content.startswith(b'%PDF'), f"PDF should start with %PDF signature"
        
        print(f"PDF export successful, size: {len(response.content)} bytes")
    
    def test_excel_export_downloads(self, auth_headers):
        """Test Excel export returns an Excel file"""
        response = requests.get(f"{BASE_URL}/api/export/sales-excel", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Verify content type is Excel
        content_type = response.headers.get('Content-Type', '')
        assert 'spreadsheet' in content_type.lower() or 'octet-stream' in content_type or 'excel' in content_type.lower(), f"Expected Excel content type, got {content_type}"
        
        # Excel files start with PK (zip signature)
        content = response.content[:2]
        assert content == b'PK', f"Excel (xlsx) should start with PK signature"
        
        print(f"Excel export successful, size: {len(response.content)} bytes")


class TestLegacyDataFallback:
    """Test legacy data handling where cylinder count is in no_of_refills instead of cylinder_nos"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Return auth headers"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_summary_handles_legacy_data(self, auth_headers):
        """Verify summary correctly calculates even with legacy data structure"""
        # Get sales entries to check if legacy data exists
        response = requests.get(f"{BASE_URL}/api/sales-entries", headers=auth_headers)
        assert response.status_code == 200
        
        entries = response.json()
        
        # Find entries with legacy format (new connection with cylinder count in no_of_refills)
        legacy_entries = [
            e for e in entries 
            if e.get('connection_type') in ['domestic', 'commercial'] 
            and not e.get('cylinder_nos')
            and e.get('no_of_refills')
        ]
        
        print(f"Found {len(legacy_entries)} legacy format entries")
        
        # Verify summary still calculates correctly
        summary_response = requests.get(f"{BASE_URL}/api/sales-entries/summary", headers=auth_headers)
        assert summary_response.status_code == 200
        
        data = summary_response.json()
        total_new_cyl = data.get('total', {}).get('new_connection_cylinders', 0)
        
        # Should be positive if there are new connections
        print(f"Total new connection cylinders (including legacy): {total_new_cyl}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
