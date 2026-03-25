"""
Test Plant Cylinder Issuance Feature for Hollongi Plant Warehouse
Tests:
- GET /api/plant/available-stock - Returns available_15kg, available_21kg, issued_today counts
- POST /api/plant/issue-to-dealer - Validates dealer, stock, creates issuance and dealer entry
- GET /api/plant/issuance-history - Returns issuance records filtered by date and dealer_id
- GET /api/dealers - Returns list of active dealers for dropdown
- Verify auto-created dealer entry appears in GET /api/dealer-entries after issuance
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPlantIssuance:
    """Plant Cylinder Issuance to Dealers Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures - login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        assert login_response.status_code == 200, f"Admin login failed: {login_response.text}"
        token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        self.today = datetime.now().strftime('%Y-%m-%d')
        yield
        
    # ============ GET /api/dealers Tests ============
    
    def test_get_dealers_returns_list(self):
        """GET /api/dealers - Returns list of active dealers for dropdown"""
        response = self.session.get(f"{BASE_URL}/api/dealers")
        assert response.status_code == 200, f"Failed to get dealers: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Check if jullang dealer exists (mentioned in requirements)
        dealer_names = [d.get('name', '').lower() for d in data]
        print(f"Found {len(data)} dealers: {dealer_names[:5]}...")
        
        # Verify dealer structure
        if len(data) > 0:
            dealer = data[0]
            assert 'id' in dealer, "Dealer should have id"
            assert 'name' in dealer, "Dealer should have name"
            assert 'is_active' in dealer, "Dealer should have is_active"
            print(f"Sample dealer: {dealer}")
    
    # ============ GET /api/plant/available-stock Tests ============
    
    def test_get_plant_available_stock(self):
        """GET /api/plant/available-stock - Returns available_15kg, available_21kg, issued_today counts"""
        response = self.session.get(f"{BASE_URL}/api/plant/available-stock", params={"date": self.today})
        assert response.status_code == 200, f"Failed to get available stock: {response.text}"
        
        data = response.json()
        print(f"Available stock response: {data}")
        
        # Verify response structure
        assert 'available_15kg' in data, "Response should have available_15kg"
        assert 'available_21kg' in data, "Response should have available_21kg"
        assert 'issued_today_15kg' in data or 'closing_15kg' in data, "Response should have issued_today or closing fields"
        
        # Values should be integers
        assert isinstance(data['available_15kg'], int), "available_15kg should be integer"
        assert isinstance(data['available_21kg'], int), "available_21kg should be integer"
        
    def test_get_plant_available_stock_with_date_param(self):
        """GET /api/plant/available-stock with date parameter"""
        response = self.session.get(f"{BASE_URL}/api/plant/available-stock", params={"date": "2025-01-01"})
        assert response.status_code == 200, f"Failed with date param: {response.text}"
        
        data = response.json()
        assert 'available_15kg' in data
        assert 'available_21kg' in data
    
    # ============ POST /api/plant/issue-to-dealer Validation Tests ============
    
    def test_issue_to_dealer_rejects_zero_quantities(self):
        """POST /api/plant/issue-to-dealer - Rejects issuance when quantities are 0"""
        # First get a dealer
        dealers_response = self.session.get(f"{BASE_URL}/api/dealers")
        dealers = dealers_response.json()
        
        if len(dealers) == 0:
            pytest.skip("No dealers available for testing")
        
        dealer_id = dealers[0]['id']
        
        response = self.session.post(f"{BASE_URL}/api/plant/issue-to-dealer", json={
            "date": self.today,
            "dealer_id": dealer_id,
            "qty_15kg": 0,
            "qty_21kg": 0,
            "remarks": "Test zero quantities"
        })
        
        assert response.status_code == 400, f"Should reject zero quantities: {response.text}"
        assert "quantity" in response.json().get('detail', '').lower() or "greater than 0" in response.json().get('detail', '').lower()
        print(f"Zero quantity rejection: {response.json()}")
    
    def test_issue_to_dealer_rejects_negative_quantities(self):
        """POST /api/plant/issue-to-dealer - Rejects issuance when quantities are negative"""
        dealers_response = self.session.get(f"{BASE_URL}/api/dealers")
        dealers = dealers_response.json()
        
        if len(dealers) == 0:
            pytest.skip("No dealers available for testing")
        
        dealer_id = dealers[0]['id']
        
        response = self.session.post(f"{BASE_URL}/api/plant/issue-to-dealer", json={
            "date": self.today,
            "dealer_id": dealer_id,
            "qty_15kg": -5,
            "qty_21kg": 0,
            "remarks": "Test negative quantities"
        })
        
        assert response.status_code == 400, f"Should reject negative quantities: {response.text}"
        print(f"Negative quantity rejection: {response.json()}")
    
    def test_issue_to_dealer_rejects_invalid_dealer(self):
        """POST /api/plant/issue-to-dealer - Rejects issuance for non-existent dealer"""
        response = self.session.post(f"{BASE_URL}/api/plant/issue-to-dealer", json={
            "date": self.today,
            "dealer_id": "non-existent-dealer-id-12345",
            "qty_15kg": 5,
            "qty_21kg": 0,
            "remarks": "Test invalid dealer"
        })
        
        assert response.status_code == 404, f"Should reject invalid dealer: {response.text}"
        assert "dealer" in response.json().get('detail', '').lower() or "not found" in response.json().get('detail', '').lower()
        print(f"Invalid dealer rejection: {response.json()}")
    
    def test_issue_to_dealer_validates_stock_sufficiency(self):
        """POST /api/plant/issue-to-dealer - Rejects issuance when stock is insufficient"""
        dealers_response = self.session.get(f"{BASE_URL}/api/dealers")
        dealers = dealers_response.json()
        
        if len(dealers) == 0:
            pytest.skip("No dealers available for testing")
        
        dealer_id = dealers[0]['id']
        
        # Request more than available (very large number)
        response = self.session.post(f"{BASE_URL}/api/plant/issue-to-dealer", json={
            "date": self.today,
            "dealer_id": dealer_id,
            "qty_15kg": 999999,
            "qty_21kg": 0,
            "remarks": "Test insufficient stock"
        })
        
        assert response.status_code == 400, f"Should reject insufficient stock: {response.text}"
        detail = response.json().get('detail', '').lower()
        assert "insufficient" in detail or "available" in detail, f"Error should mention insufficient stock: {detail}"
        print(f"Insufficient stock rejection: {response.json()}")
    
    # ============ GET /api/plant/issuance-history Tests ============
    
    def test_get_issuance_history(self):
        """GET /api/plant/issuance-history - Returns issuance records"""
        response = self.session.get(f"{BASE_URL}/api/plant/issuance-history")
        assert response.status_code == 200, f"Failed to get issuance history: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} issuance records")
        
        # Verify structure if records exist
        if len(data) > 0:
            record = data[0]
            assert 'id' in record, "Record should have id"
            assert 'date' in record, "Record should have date"
            assert 'dealer_id' in record, "Record should have dealer_id"
            assert 'dealer_name' in record, "Record should have dealer_name"
            assert 'qty_15kg' in record, "Record should have qty_15kg"
            assert 'qty_21kg' in record, "Record should have qty_21kg"
            print(f"Sample issuance record: {record}")
    
    def test_get_issuance_history_with_date_filter(self):
        """GET /api/plant/issuance-history - Filters by date range"""
        response = self.session.get(f"{BASE_URL}/api/plant/issuance-history", params={
            "start_date": self.today,
            "end_date": self.today
        })
        assert response.status_code == 200, f"Failed with date filter: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        
        # All records should be from today
        for record in data:
            assert record.get('date') == self.today, f"Record date {record.get('date')} should be {self.today}"
        print(f"Found {len(data)} issuance records for today")
    
    def test_get_issuance_history_with_dealer_filter(self):
        """GET /api/plant/issuance-history - Filters by dealer_id"""
        dealers_response = self.session.get(f"{BASE_URL}/api/dealers")
        dealers = dealers_response.json()
        
        if len(dealers) == 0:
            pytest.skip("No dealers available for testing")
        
        dealer_id = dealers[0]['id']
        
        response = self.session.get(f"{BASE_URL}/api/plant/issuance-history", params={
            "dealer_id": dealer_id
        })
        assert response.status_code == 200, f"Failed with dealer filter: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        
        # All records should be for this dealer
        for record in data:
            assert record.get('dealer_id') == dealer_id, f"Record dealer_id should be {dealer_id}"
        print(f"Found {len(data)} issuance records for dealer {dealer_id}")


class TestPlantIssuanceFullFlow:
    """Full flow test: Create plant stock, issue to dealer, verify dealer entry"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures - login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        assert login_response.status_code == 200, f"Admin login failed: {login_response.text}"
        token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        self.today = datetime.now().strftime('%Y-%m-%d')
        yield
    
    def test_full_issuance_flow_with_stock_seeding(self):
        """Full flow: Seed stock -> Issue to dealer -> Verify dealer entry created"""
        # Step 1: Seed plant stock using plant-update endpoint
        seed_response = self.session.post(f"{BASE_URL}/api/stock/plant-update", json={
            "bullet_tank_kg": 1000,
            "stock_15kg_filled": 100,
            "stock_21kg_filled": 50,
            "stock_15kg_empty": 20,
            "stock_21kg_empty": 10,
            "reason": "TEST_seed_stock_for_issuance_test"
        })
        assert seed_response.status_code == 200, f"Failed to seed plant stock: {seed_response.text}"
        print(f"Seeded plant stock: {seed_response.json()}")
        
        # Step 2: Verify available stock
        stock_response = self.session.get(f"{BASE_URL}/api/plant/available-stock", params={"date": self.today})
        assert stock_response.status_code == 200
        stock_data = stock_response.json()
        print(f"Available stock after seeding: {stock_data}")
        
        available_15 = stock_data.get('available_15kg', 0)
        available_21 = stock_data.get('available_21kg', 0)
        
        # Step 3: Get a dealer
        dealers_response = self.session.get(f"{BASE_URL}/api/dealers")
        dealers = dealers_response.json()
        
        if len(dealers) == 0:
            pytest.skip("No dealers available for testing")
        
        # Find jullang dealer or use first one
        dealer = next((d for d in dealers if 'jullang' in d.get('name', '').lower()), dealers[0])
        dealer_id = dealer['id']
        dealer_name = dealer['name']
        print(f"Using dealer: {dealer_name} ({dealer_id})")
        
        # Step 4: Issue cylinders to dealer (only if stock available)
        issue_qty_15 = min(5, available_15) if available_15 > 0 else 0
        issue_qty_21 = min(3, available_21) if available_21 > 0 else 0
        
        if issue_qty_15 == 0 and issue_qty_21 == 0:
            print("No stock available to issue, skipping issuance test")
            pytest.skip("No stock available for issuance")
        
        issue_response = self.session.post(f"{BASE_URL}/api/plant/issue-to-dealer", json={
            "date": self.today,
            "dealer_id": dealer_id,
            "qty_15kg": issue_qty_15,
            "qty_21kg": issue_qty_21,
            "remarks": "TEST_issuance_flow_test"
        })
        
        assert issue_response.status_code == 200, f"Failed to issue cylinders: {issue_response.text}"
        issuance_data = issue_response.json()
        print(f"Issuance created: {issuance_data}")
        
        # Verify issuance response structure
        assert 'id' in issuance_data, "Issuance should have id"
        assert issuance_data.get('dealer_id') == dealer_id, "Issuance dealer_id should match"
        assert issuance_data.get('qty_15kg') == issue_qty_15, "Issuance qty_15kg should match"
        assert issuance_data.get('qty_21kg') == issue_qty_21, "Issuance qty_21kg should match"
        
        # Step 5: Verify issuance appears in history
        history_response = self.session.get(f"{BASE_URL}/api/plant/issuance-history", params={
            "start_date": self.today,
            "end_date": self.today,
            "dealer_id": dealer_id
        })
        assert history_response.status_code == 200
        history = history_response.json()
        
        # Find our issuance
        our_issuance = next((h for h in history if h.get('id') == issuance_data.get('id')), None)
        assert our_issuance is not None, "Issuance should appear in history"
        print(f"Issuance found in history: {our_issuance}")
        
        # Step 6: Verify dealer entry was auto-created
        dealer_entries_response = self.session.get(f"{BASE_URL}/api/dealer-entries", params={
            "dealer_id": dealer_id,
            "start_date": self.today,
            "end_date": self.today
        })
        assert dealer_entries_response.status_code == 200, f"Failed to get dealer entries: {dealer_entries_response.text}"
        dealer_entries = dealer_entries_response.json()
        print(f"Dealer entries for today: {dealer_entries}")
        
        # Find entry with our issued quantities
        matching_entry = None
        for entry in dealer_entries:
            if entry.get('issued_15kg', 0) >= issue_qty_15 and entry.get('issued_21kg', 0) >= issue_qty_21:
                matching_entry = entry
                break
        
        assert matching_entry is not None, f"Dealer entry should be auto-created with issued quantities. Entries: {dealer_entries}"
        print(f"Auto-created dealer entry found: {matching_entry}")
        
        # Step 7: Verify stock was reduced
        stock_after_response = self.session.get(f"{BASE_URL}/api/plant/available-stock", params={"date": self.today})
        stock_after = stock_after_response.json()
        print(f"Stock after issuance: {stock_after}")
        
        # issued_today should reflect our issuance
        assert stock_after.get('issued_today_15kg', 0) >= issue_qty_15, "issued_today_15kg should include our issuance"
        assert stock_after.get('issued_today_21kg', 0) >= issue_qty_21, "issued_today_21kg should include our issuance"


class TestPlantIssuanceAccessControl:
    """Test access control for plant issuance endpoints"""
    
    def test_unauthenticated_access_denied(self):
        """Unauthenticated requests should be denied"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Test available-stock
        response = session.get(f"{BASE_URL}/api/plant/available-stock")
        assert response.status_code == 401 or response.status_code == 403, f"Should deny unauthenticated: {response.status_code}"
        
        # Test issuance-history
        response = session.get(f"{BASE_URL}/api/plant/issuance-history")
        assert response.status_code == 401 or response.status_code == 403
        
        # Test issue-to-dealer
        response = session.post(f"{BASE_URL}/api/plant/issue-to-dealer", json={
            "date": "2025-01-01",
            "dealer_id": "test",
            "qty_15kg": 1,
            "qty_21kg": 0
        })
        assert response.status_code == 401 or response.status_code == 403
        print("Unauthenticated access correctly denied")
    
    def test_sales_executive_can_access_endpoints(self):
        """Sales executive should be able to access plant issuance endpoints"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login as sales executive
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "sales@k3gas.com",
            "password": "Sales@123"
        })
        
        if login_response.status_code != 200:
            pytest.skip("Sales executive user not available")
        
        token = login_response.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Test available-stock
        response = session.get(f"{BASE_URL}/api/plant/available-stock")
        assert response.status_code == 200, f"Sales exec should access available-stock: {response.text}"
        
        # Test issuance-history
        response = session.get(f"{BASE_URL}/api/plant/issuance-history")
        assert response.status_code == 200, f"Sales exec should access issuance-history: {response.text}"
        
        print("Sales executive can access plant issuance endpoints")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
