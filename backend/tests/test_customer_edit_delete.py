"""
Test Customer Edit/Delete Access Control
Tests for PUT /api/customers/{id}, DELETE /api/customers/{id}, GET /api/customers/{id}/linked-records
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASSWORD = "Admin@123"
MANAGER_EMAIL = "jullang@k3gas.com"  # Jullang warehouse manager
MANAGER_PASSWORD = "Jullang@123"
SALES_EMAIL = "sales@k3gas.com"
SALES_PASSWORD = "Sales@123"

# Warehouse IDs
JULLANG_WAREHOUSE_ID = "8f2dc176-4450-4bf7-8ccc-2c2618fc6d32"
NAHARLAGUN_WAREHOUSE_ID = "e155211b-0079-45e0-982f-0c605e498493"


class TestCustomerEditDeleteAccessControl:
    """Test access control for customer edit and delete operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_customer_ids = []
    
    def get_auth_token(self, email, password):
        """Get authentication token for a user"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def create_test_customer(self, token, warehouse_id):
        """Create a test customer for testing"""
        headers = {"Authorization": f"Bearer {token}"}
        customer_data = {
            "date": "2025-01-15",
            "connection_type": "domestic",
            "customer_name": f"TEST_Customer_{uuid.uuid4().hex[:8]}",
            "address": "Test Address",
            "phone": "9876543210",
            "consumer_no": "1234567890",
            "cash_memo_no": "CM001",
            "cylinder_nos": "CYL001",
            "gas_card_issued": False,
            "kyc_done": False,
            "remarks": "Test customer for edit/delete testing"
        }
        response = self.session.post(
            f"{BASE_URL}/api/customers/warehouse/{warehouse_id}",
            json=customer_data,
            headers=headers
        )
        if response.status_code in [200, 201]:
            customer_id = response.json().get("id")
            self.created_customer_ids.append(customer_id)
            return customer_id
        return None
    
    def cleanup_test_customers(self, token):
        """Clean up test customers"""
        headers = {"Authorization": f"Bearer {token}"}
        for customer_id in self.created_customer_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/customers/{customer_id}", headers=headers)
            except:
                pass
    
    # ============ ADMIN TESTS ============
    
    def test_admin_can_edit_any_customer(self):
        """Admin can edit any customer regardless of warehouse"""
        admin_token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert admin_token, "Admin login failed"
        
        # Create a customer in Jullang warehouse
        customer_id = self.create_test_customer(admin_token, JULLANG_WAREHOUSE_ID)
        assert customer_id, "Failed to create test customer"
        
        # Admin edits the customer
        headers = {"Authorization": f"Bearer {admin_token}"}
        update_data = {"customer_name": "TEST_Updated_By_Admin"}
        response = self.session.put(
            f"{BASE_URL}/api/customers/{customer_id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Admin should be able to edit customer. Got: {response.status_code} - {response.text}"
        assert response.json()["customer_name"] == "TEST_Updated_By_Admin"
        print("PASS: Admin can edit any customer")
        
        # Cleanup
        self.cleanup_test_customers(admin_token)
    
    def test_admin_can_delete_any_customer(self):
        """Admin can delete any customer regardless of warehouse"""
        admin_token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert admin_token, "Admin login failed"
        
        # Create a customer in Naharlagun warehouse
        customer_id = self.create_test_customer(admin_token, NAHARLAGUN_WAREHOUSE_ID)
        assert customer_id, "Failed to create test customer"
        
        # Admin deletes the customer
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = self.session.delete(
            f"{BASE_URL}/api/customers/{customer_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Admin should be able to delete customer. Got: {response.status_code} - {response.text}"
        print("PASS: Admin can delete any customer")
        
        # Remove from cleanup list since already deleted
        if customer_id in self.created_customer_ids:
            self.created_customer_ids.remove(customer_id)
    
    # ============ WAREHOUSE MANAGER TESTS ============
    
    def test_manager_can_edit_own_warehouse_customer(self):
        """Warehouse manager can edit customer in their own warehouse"""
        admin_token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        manager_token = self.get_auth_token(MANAGER_EMAIL, MANAGER_PASSWORD)
        assert admin_token, "Admin login failed"
        assert manager_token, "Manager login failed"
        
        # Create a customer in Jullang warehouse (manager's warehouse)
        customer_id = self.create_test_customer(admin_token, JULLANG_WAREHOUSE_ID)
        assert customer_id, "Failed to create test customer"
        
        # Manager edits the customer
        headers = {"Authorization": f"Bearer {manager_token}"}
        update_data = {"customer_name": "TEST_Updated_By_Manager"}
        response = self.session.put(
            f"{BASE_URL}/api/customers/{customer_id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Manager should be able to edit customer in own warehouse. Got: {response.status_code} - {response.text}"
        assert response.json()["customer_name"] == "TEST_Updated_By_Manager"
        print("PASS: Warehouse manager can edit customer in own warehouse")
        
        # Cleanup
        self.cleanup_test_customers(admin_token)
    
    def test_manager_cannot_edit_other_warehouse_customer(self):
        """Warehouse manager CANNOT edit customer in another warehouse"""
        admin_token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        manager_token = self.get_auth_token(MANAGER_EMAIL, MANAGER_PASSWORD)
        assert admin_token, "Admin login failed"
        assert manager_token, "Manager login failed"
        
        # Create a customer in Naharlagun warehouse (NOT manager's warehouse)
        customer_id = self.create_test_customer(admin_token, NAHARLAGUN_WAREHOUSE_ID)
        assert customer_id, "Failed to create test customer"
        
        # Manager tries to edit the customer
        headers = {"Authorization": f"Bearer {manager_token}"}
        update_data = {"customer_name": "TEST_Should_Not_Update"}
        response = self.session.put(
            f"{BASE_URL}/api/customers/{customer_id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 403, f"Manager should NOT be able to edit customer in other warehouse. Got: {response.status_code} - {response.text}"
        print("PASS: Warehouse manager CANNOT edit customer in another warehouse (403)")
        
        # Cleanup
        self.cleanup_test_customers(admin_token)
    
    def test_manager_can_delete_own_warehouse_customer(self):
        """Warehouse manager can delete customer in their own warehouse"""
        admin_token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        manager_token = self.get_auth_token(MANAGER_EMAIL, MANAGER_PASSWORD)
        assert admin_token, "Admin login failed"
        assert manager_token, "Manager login failed"
        
        # Create a customer in Jullang warehouse (manager's warehouse)
        customer_id = self.create_test_customer(admin_token, JULLANG_WAREHOUSE_ID)
        assert customer_id, "Failed to create test customer"
        
        # Manager deletes the customer
        headers = {"Authorization": f"Bearer {manager_token}"}
        response = self.session.delete(
            f"{BASE_URL}/api/customers/{customer_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Manager should be able to delete customer in own warehouse. Got: {response.status_code} - {response.text}"
        print("PASS: Warehouse manager can delete customer in own warehouse")
        
        # Remove from cleanup list since already deleted
        if customer_id in self.created_customer_ids:
            self.created_customer_ids.remove(customer_id)
    
    def test_manager_cannot_delete_other_warehouse_customer(self):
        """Warehouse manager CANNOT delete customer in another warehouse"""
        admin_token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        manager_token = self.get_auth_token(MANAGER_EMAIL, MANAGER_PASSWORD)
        assert admin_token, "Admin login failed"
        assert manager_token, "Manager login failed"
        
        # Create a customer in Naharlagun warehouse (NOT manager's warehouse)
        customer_id = self.create_test_customer(admin_token, NAHARLAGUN_WAREHOUSE_ID)
        assert customer_id, "Failed to create test customer"
        
        # Manager tries to delete the customer
        headers = {"Authorization": f"Bearer {manager_token}"}
        response = self.session.delete(
            f"{BASE_URL}/api/customers/{customer_id}",
            headers=headers
        )
        
        assert response.status_code == 403, f"Manager should NOT be able to delete customer in other warehouse. Got: {response.status_code} - {response.text}"
        print("PASS: Warehouse manager CANNOT delete customer in another warehouse (403)")
        
        # Cleanup
        self.cleanup_test_customers(admin_token)
    
    # ============ SALES EXECUTIVE TESTS ============
    
    def test_sales_executive_cannot_edit_customer(self):
        """Sales executive CANNOT edit any customer"""
        admin_token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        sales_token = self.get_auth_token(SALES_EMAIL, SALES_PASSWORD)
        assert admin_token, "Admin login failed"
        
        if not sales_token:
            pytest.skip("Sales executive user not found - skipping test")
        
        # Create a customer
        customer_id = self.create_test_customer(admin_token, JULLANG_WAREHOUSE_ID)
        assert customer_id, "Failed to create test customer"
        
        # Sales executive tries to edit the customer
        headers = {"Authorization": f"Bearer {sales_token}"}
        update_data = {"customer_name": "TEST_Should_Not_Update"}
        response = self.session.put(
            f"{BASE_URL}/api/customers/{customer_id}",
            json=update_data,
            headers=headers
        )
        
        assert response.status_code == 403, f"Sales executive should NOT be able to edit customer. Got: {response.status_code} - {response.text}"
        print("PASS: Sales executive CANNOT edit customer (403)")
        
        # Cleanup
        self.cleanup_test_customers(admin_token)
    
    def test_sales_executive_cannot_delete_customer(self):
        """Sales executive CANNOT delete any customer"""
        admin_token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        sales_token = self.get_auth_token(SALES_EMAIL, SALES_PASSWORD)
        assert admin_token, "Admin login failed"
        
        if not sales_token:
            pytest.skip("Sales executive user not found - skipping test")
        
        # Create a customer
        customer_id = self.create_test_customer(admin_token, JULLANG_WAREHOUSE_ID)
        assert customer_id, "Failed to create test customer"
        
        # Sales executive tries to delete the customer
        headers = {"Authorization": f"Bearer {sales_token}"}
        response = self.session.delete(
            f"{BASE_URL}/api/customers/{customer_id}",
            headers=headers
        )
        
        assert response.status_code == 403, f"Sales executive should NOT be able to delete customer. Got: {response.status_code} - {response.text}"
        print("PASS: Sales executive CANNOT delete customer (403)")
        
        # Cleanup
        self.cleanup_test_customers(admin_token)
    
    # ============ LINKED RECORDS TESTS ============
    
    def test_get_customer_linked_records(self):
        """GET /api/customers/{id}/linked-records returns counts"""
        admin_token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        assert admin_token, "Admin login failed"
        
        # Create a customer
        customer_id = self.create_test_customer(admin_token, JULLANG_WAREHOUSE_ID)
        assert customer_id, "Failed to create test customer"
        
        # Get linked records
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = self.session.get(
            f"{BASE_URL}/api/customers/{customer_id}/linked-records",
            headers=headers
        )
        
        assert response.status_code == 200, f"Should get linked records. Got: {response.status_code} - {response.text}"
        data = response.json()
        assert "active_orders" in data, "Response should contain active_orders"
        assert "total_orders" in data, "Response should contain total_orders"
        assert "sales_entries" in data, "Response should contain sales_entries"
        assert "has_linked_records" in data, "Response should contain has_linked_records"
        print(f"PASS: GET linked-records returns: active_orders={data['active_orders']}, total_orders={data['total_orders']}, sales_entries={data['sales_entries']}")
        
        # Cleanup
        self.cleanup_test_customers(admin_token)
    
    def test_manager_can_get_linked_records_own_warehouse(self):
        """Manager can get linked records for customer in own warehouse"""
        admin_token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        manager_token = self.get_auth_token(MANAGER_EMAIL, MANAGER_PASSWORD)
        assert admin_token, "Admin login failed"
        assert manager_token, "Manager login failed"
        
        # Create a customer in manager's warehouse
        customer_id = self.create_test_customer(admin_token, JULLANG_WAREHOUSE_ID)
        assert customer_id, "Failed to create test customer"
        
        # Manager gets linked records
        headers = {"Authorization": f"Bearer {manager_token}"}
        response = self.session.get(
            f"{BASE_URL}/api/customers/{customer_id}/linked-records",
            headers=headers
        )
        
        assert response.status_code == 200, f"Manager should get linked records for own warehouse customer. Got: {response.status_code} - {response.text}"
        print("PASS: Manager can get linked records for own warehouse customer")
        
        # Cleanup
        self.cleanup_test_customers(admin_token)
    
    def test_manager_cannot_get_linked_records_other_warehouse(self):
        """Manager CANNOT get linked records for customer in other warehouse"""
        admin_token = self.get_auth_token(ADMIN_EMAIL, ADMIN_PASSWORD)
        manager_token = self.get_auth_token(MANAGER_EMAIL, MANAGER_PASSWORD)
        assert admin_token, "Admin login failed"
        assert manager_token, "Manager login failed"
        
        # Create a customer in other warehouse
        customer_id = self.create_test_customer(admin_token, NAHARLAGUN_WAREHOUSE_ID)
        assert customer_id, "Failed to create test customer"
        
        # Manager tries to get linked records
        headers = {"Authorization": f"Bearer {manager_token}"}
        response = self.session.get(
            f"{BASE_URL}/api/customers/{customer_id}/linked-records",
            headers=headers
        )
        
        assert response.status_code == 403, f"Manager should NOT get linked records for other warehouse customer. Got: {response.status_code} - {response.text}"
        print("PASS: Manager CANNOT get linked records for other warehouse customer (403)")
        
        # Cleanup
        self.cleanup_test_customers(admin_token)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
