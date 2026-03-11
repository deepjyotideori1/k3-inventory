"""
Backend Tests for Dealer Reports Feature
Tests: Dealers CRUD, Dealer Entries, Summary, and PDF/Excel Exports
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PLANT_HOLLONGI_USER = {
    "email": "hollongi@k3gas.com",
    "password": "Hollongi@123"
}

ADMIN_USER = {
    "email": "admin@k3gas.com",
    "password": "Admin@123"
}


class TestHealthAndAuth:
    """Basic health check and authentication tests"""
    
    def test_api_root(self):
        """Test API is accessible"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200, f"API root failed: {response.text}"
        data = response.json()
        assert "K3 GAS SERVICE" in data.get("message", "")
        print("✓ API root accessible")
    
    def test_plant_hollongi_login(self):
        """Test Plant Hollongi user login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=PLANT_HOLLONGI_USER)
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert data["user"]["email"] == PLANT_HOLLONGI_USER["email"]
        print(f"✓ Plant Hollongi login successful - User: {data['user']['name']}")
        return data["token"]
    
    def test_admin_login(self):
        """Test Admin user login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_USER)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful - User: {data['user']['name']}")
        return data["token"]


@pytest.fixture(scope="class")
def hollongi_token():
    """Get Plant Hollongi user token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=PLANT_HOLLONGI_USER)
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Plant Hollongi login failed")


@pytest.fixture(scope="class")
def admin_token():
    """Get Admin user token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_USER)
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Admin login failed")


class TestDealerCRUD:
    """Test Dealer management APIs"""
    
    def test_get_dealers(self, hollongi_token):
        """Test getting all dealers"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        response = requests.get(f"{BASE_URL}/api/dealers", headers=headers)
        assert response.status_code == 200, f"Get dealers failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of dealers"
        print(f"✓ Get dealers successful - Found {len(data)} dealers")
        return data
    
    def test_create_dealer(self, hollongi_token):
        """Test creating a new dealer"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        dealer_data = {
            "name": "TEST_Dealer_AutoTest",
            "contact": "9876543210",
            "address": "Test Address, City"
        }
        response = requests.post(f"{BASE_URL}/api/dealers", headers=headers, json=dealer_data)
        assert response.status_code == 200, f"Create dealer failed: {response.text}"
        data = response.json()
        assert data["name"] == dealer_data["name"]
        assert data["contact"] == dealer_data["contact"]
        assert "id" in data
        print(f"✓ Create dealer successful - ID: {data['id']}")
        return data
    
    def test_update_dealer(self, hollongi_token):
        """Test updating a dealer"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        # First create a dealer to update
        create_data = {"name": "TEST_Dealer_ToUpdate", "contact": "1111111111", "address": "Old Address"}
        create_response = requests.post(f"{BASE_URL}/api/dealers", headers=headers, json=create_data)
        assert create_response.status_code == 200
        dealer_id = create_response.json()["id"]
        
        # Update the dealer
        update_data = {"name": "TEST_Dealer_Updated", "contact": "2222222222", "address": "New Address"}
        update_response = requests.put(f"{BASE_URL}/api/dealers/{dealer_id}", headers=headers, json=update_data)
        assert update_response.status_code == 200, f"Update dealer failed: {update_response.text}"
        data = update_response.json()
        assert data["name"] == update_data["name"]
        assert data["contact"] == update_data["contact"]
        print(f"✓ Update dealer successful - Name changed to: {data['name']}")
        return dealer_id
    
    def test_delete_dealer(self, hollongi_token):
        """Test deleting (soft) a dealer"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        # Create a dealer to delete
        create_data = {"name": "TEST_Dealer_ToDelete", "contact": "3333333333", "address": "Delete Me"}
        create_response = requests.post(f"{BASE_URL}/api/dealers", headers=headers, json=create_data)
        assert create_response.status_code == 200
        dealer_id = create_response.json()["id"]
        
        # Delete the dealer
        delete_response = requests.delete(f"{BASE_URL}/api/dealers/{dealer_id}", headers=headers)
        assert delete_response.status_code == 200, f"Delete dealer failed: {delete_response.text}"
        
        # Verify dealer is not in active dealers list
        get_response = requests.get(f"{BASE_URL}/api/dealers", headers=headers)
        dealers = get_response.json()
        deleted_dealer = next((d for d in dealers if d["id"] == dealer_id), None)
        assert deleted_dealer is None, "Deleted dealer should not appear in active list"
        print(f"✓ Delete dealer successful - ID: {dealer_id}")


class TestDealerEntries:
    """Test Dealer Entry APIs"""
    
    @pytest.fixture
    def test_dealer_id(self, hollongi_token):
        """Create/get a test dealer for entries"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        # Check existing dealers first
        response = requests.get(f"{BASE_URL}/api/dealers", headers=headers)
        dealers = response.json()
        
        # Find or create test dealer
        test_dealer = next((d for d in dealers if d["name"].startswith("TEST_")), None)
        if not test_dealer:
            create_response = requests.post(
                f"{BASE_URL}/api/dealers", 
                headers=headers, 
                json={"name": "TEST_EntryDealer", "contact": "5555555555", "address": "Entry Test"}
            )
            test_dealer = create_response.json()
        
        return test_dealer["id"]
    
    def test_create_dealer_entry(self, hollongi_token, test_dealer_id):
        """Test creating a dealer entry"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        entry_data = {
            "dealer_id": test_dealer_id,
            "date": "2026-01-15",
            "issued_15kg": 10,
            "issued_21kg": 5,
            "refilled_15kg": 8,
            "refilled_21kg": 3,
            "remarks": "Test entry from automated testing"
        }
        response = requests.post(f"{BASE_URL}/api/dealer-entries", headers=headers, json=entry_data)
        assert response.status_code == 200, f"Create entry failed: {response.text}"
        data = response.json()
        assert data["issued_15kg"] == entry_data["issued_15kg"]
        assert data["issued_21kg"] == entry_data["issued_21kg"]
        assert "id" in data
        print(f"✓ Create dealer entry successful - 15kg: {data['issued_15kg']}, 21kg: {data['issued_21kg']}")
        return data
    
    def test_get_dealer_entries(self, hollongi_token):
        """Test getting dealer entries with filters"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        # Get all entries
        response = requests.get(f"{BASE_URL}/api/dealer-entries", headers=headers)
        assert response.status_code == 200, f"Get entries failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Get dealer entries successful - Found {len(data)} entries")
        
        # Test with date filter
        response_filtered = requests.get(
            f"{BASE_URL}/api/dealer-entries",
            headers=headers,
            params={"start_date": "2026-01-01", "end_date": "2026-12-31"}
        )
        assert response_filtered.status_code == 200
        print(f"✓ Date filtered entries - Found {len(response_filtered.json())} entries")
        
        return data
    
    def test_get_dealer_summary(self, hollongi_token):
        """Test getting dealer summary with totals"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        # Get all-time summary (no date filter)
        response = requests.get(f"{BASE_URL}/api/dealer-entries/summary", headers=headers)
        assert response.status_code == 200, f"Get summary failed: {response.text}"
        data = response.json()
        
        assert "dealers" in data, "Expected 'dealers' key in summary"
        assert "grand_totals" in data, "Expected 'grand_totals' key in summary"
        
        # Validate grand_totals structure
        totals = data["grand_totals"]
        assert "total_issued_15kg" in totals
        assert "total_issued_21kg" in totals
        assert "total_refilled_15kg" in totals
        assert "total_refilled_21kg" in totals
        
        print(f"✓ Get summary successful - {len(data['dealers'])} dealers")
        print(f"  Total 15kg Issued: {totals['total_issued_15kg']}")
        print(f"  Total 21kg Issued: {totals['total_issued_21kg']}")
        
        return data
    
    def test_get_summary_with_date_range(self, hollongi_token):
        """Test summary with date range filter"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        # Get summary for specific date range
        params = {"start_date": "2026-01-01", "end_date": "2026-01-31"}
        response = requests.get(f"{BASE_URL}/api/dealer-entries/summary", headers=headers, params=params)
        assert response.status_code == 200
        data = response.json()
        
        assert "dealers" in data
        assert "grand_totals" in data
        print(f"✓ Summary with date range successful - Found data for {len(data['dealers'])} dealers")
        return data


class TestDealerExports:
    """Test PDF and Excel export endpoints"""
    
    def test_export_dealer_pdf(self, hollongi_token):
        """Test PDF export for dealers"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        response = requests.get(f"{BASE_URL}/api/export/dealer-pdf", headers=headers)
        assert response.status_code == 200, f"PDF export failed: {response.text}"
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        assert "pdf" in content_type.lower(), f"Expected PDF content type, got: {content_type}"
        
        # Check content disposition header
        disposition = response.headers.get("Content-Disposition", "")
        assert "dealer_report" in disposition, f"Expected dealer_report in filename, got: {disposition}"
        
        # Check content length
        assert len(response.content) > 0, "PDF content is empty"
        
        print(f"✓ PDF export successful - Size: {len(response.content)} bytes")
        return True
    
    def test_export_dealer_pdf_with_filters(self, hollongi_token):
        """Test PDF export with date filters"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        params = {
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }
        response = requests.get(f"{BASE_URL}/api/export/dealer-pdf", headers=headers, params=params)
        assert response.status_code == 200, f"Filtered PDF export failed: {response.text}"
        assert len(response.content) > 0
        print(f"✓ Filtered PDF export successful - Size: {len(response.content)} bytes")
    
    def test_export_dealer_excel(self, hollongi_token):
        """Test Excel export for dealers"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        response = requests.get(f"{BASE_URL}/api/export/dealer-excel", headers=headers)
        assert response.status_code == 200, f"Excel export failed: {response.text}"
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        assert "spreadsheet" in content_type.lower() or "excel" in content_type.lower() or "openxml" in content_type.lower(), \
            f"Expected Excel content type, got: {content_type}"
        
        # Check content disposition
        disposition = response.headers.get("Content-Disposition", "")
        assert "dealer_report" in disposition, f"Expected dealer_report in filename, got: {disposition}"
        
        # Check content
        assert len(response.content) > 0, "Excel content is empty"
        
        print(f"✓ Excel export successful - Size: {len(response.content)} bytes")
        return True
    
    def test_export_dealer_excel_with_filters(self, hollongi_token):
        """Test Excel export with date filters"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        params = {
            "start_date": "2026-01-01",
            "end_date": "2026-01-31"
        }
        response = requests.get(f"{BASE_URL}/api/export/dealer-excel", headers=headers, params=params)
        assert response.status_code == 200, f"Filtered Excel export failed: {response.text}"
        assert len(response.content) > 0
        print(f"✓ Filtered Excel export successful - Size: {len(response.content)} bytes")
    
    def test_export_all_time_pdf(self, hollongi_token):
        """Test all-time PDF export (no date filter)"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        response = requests.get(f"{BASE_URL}/api/export/dealer-pdf", headers=headers)
        assert response.status_code == 200
        print(f"✓ All-time PDF export successful - Size: {len(response.content)} bytes")
    
    def test_export_all_time_excel(self, hollongi_token):
        """Test all-time Excel export (no date filter)"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        response = requests.get(f"{BASE_URL}/api/export/dealer-excel", headers=headers)
        assert response.status_code == 200
        print(f"✓ All-time Excel export successful - Size: {len(response.content)} bytes")


class TestCleanup:
    """Cleanup test data after all tests"""
    
    def test_cleanup_test_dealers(self, hollongi_token):
        """Clean up TEST_ prefixed dealers"""
        headers = {"Authorization": f"Bearer {hollongi_token}"}
        
        # Get all dealers
        response = requests.get(f"{BASE_URL}/api/dealers", headers=headers)
        dealers = response.json()
        
        # Delete test dealers
        deleted_count = 0
        for dealer in dealers:
            if dealer["name"].startswith("TEST_"):
                delete_response = requests.delete(f"{BASE_URL}/api/dealers/{dealer['id']}", headers=headers)
                if delete_response.status_code == 200:
                    deleted_count += 1
        
        print(f"✓ Cleanup complete - Deleted {deleted_count} test dealers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
