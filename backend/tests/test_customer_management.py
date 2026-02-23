"""
Customer Management Backend API Tests
Testing warehouse-specific customer storage and role-based access control
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASSWORD = "Admin@123"
JULLANG_EMAIL = "jullang@k3gas.com"
JULLANG_PASSWORD = "Jullang@123"
NAHARLAGUN_EMAIL = "naharlagun@k3gas.com"
NAHARLAGUN_PASSWORD = "Naharlagun@123"


class TestAuth:
    """Authentication tests for Customer Management"""
    
    def test_admin_login(self):
        """Test admin can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful")
    
    def test_jullang_manager_login(self):
        """Test Jullang warehouse manager can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": JULLANG_EMAIL,
            "password": JULLANG_PASSWORD
        })
        assert response.status_code == 200, f"Jullang login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "warehouse_manager"
        assert data["user"]["warehouse_name"] == "Jullang"
        print(f"✓ Jullang manager login successful")
    
    def test_naharlagun_manager_login(self):
        """Test Naharlagun warehouse manager can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": NAHARLAGUN_EMAIL,
            "password": NAHARLAGUN_PASSWORD
        })
        assert response.status_code == 200, f"Naharlagun login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "warehouse_manager"
        assert data["user"]["warehouse_name"] == "Naharlagun"
        print(f"✓ Naharlagun manager login successful")


@pytest.fixture
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200
    return response.json()["token"]


@pytest.fixture
def jullang_token():
    """Get Jullang warehouse manager token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": JULLANG_EMAIL,
        "password": JULLANG_PASSWORD
    })
    assert response.status_code == 200
    return response.json()["token"]


@pytest.fixture
def naharlagun_token():
    """Get Naharlagun warehouse manager token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": NAHARLAGUN_EMAIL,
        "password": NAHARLAGUN_PASSWORD
    })
    assert response.status_code == 200
    return response.json()["token"]


@pytest.fixture
def jullang_warehouse_id(admin_token):
    """Get Jullang warehouse ID"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{BASE_URL}/api/warehouses", headers=headers)
    assert response.status_code == 200
    warehouses = response.json()
    for w in warehouses:
        if w['name'] == 'Jullang':
            return w['id']
    pytest.fail("Jullang warehouse not found")


@pytest.fixture
def naharlagun_warehouse_id(admin_token):
    """Get Naharlagun warehouse ID"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{BASE_URL}/api/warehouses", headers=headers)
    assert response.status_code == 200
    warehouses = response.json()
    for w in warehouses:
        if w['name'] == 'Naharlagun':
            return w['id']
    pytest.fail("Naharlagun warehouse not found")


class TestWarehouseManagerCustomers:
    """Tests for warehouse managers creating/viewing customers"""
    
    def test_jullang_create_customer(self, jullang_token):
        """Jullang manager can create customer for their warehouse"""
        headers = {"Authorization": f"Bearer {jullang_token}"}
        test_name = f"TEST_Jullang_Customer_{uuid.uuid4().hex[:6]}"
        
        customer_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "connection_type": "domestic",
            "customer_name": test_name,
            "address": "Jullang Test Address",
            "consumer_no": f"CON_{uuid.uuid4().hex[:6]}",
            "cash_memo_no": "CM001",
            "cylinder_nos": "CYL-001",
            "gas_card_issued": True,
            "kyc_done": True,
            "remarks": "Test customer for Jullang"
        }
        
        response = requests.post(f"{BASE_URL}/api/customers", 
                                headers=headers, json=customer_data)
        assert response.status_code == 200, f"Failed to create customer: {response.text}"
        data = response.json()
        assert data["customer_name"] == test_name
        assert data["warehouse_name"] == "Jullang"
        assert data["gas_card_issued"] == True
        assert data["kyc_done"] == True
        print(f"✓ Jullang manager created customer: {test_name}")
        return data["id"]
    
    def test_naharlagun_create_customer(self, naharlagun_token):
        """Naharlagun manager can create customer for their warehouse"""
        headers = {"Authorization": f"Bearer {naharlagun_token}"}
        test_name = f"TEST_Naharlagun_Customer_{uuid.uuid4().hex[:6]}"
        
        customer_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "connection_type": "commercial",
            "customer_name": test_name,
            "address": "Naharlagun Test Address",
            "consumer_no": f"CON_{uuid.uuid4().hex[:6]}",
            "cash_memo_no": "CM002",
            "cylinder_nos": "CYL-002, CYL-003",
            "gas_card_issued": False,
            "kyc_done": True,
            "remarks": "Test commercial customer"
        }
        
        response = requests.post(f"{BASE_URL}/api/customers", 
                                headers=headers, json=customer_data)
        assert response.status_code == 200, f"Failed to create customer: {response.text}"
        data = response.json()
        assert data["customer_name"] == test_name
        assert data["warehouse_name"] == "Naharlagun"
        assert data["connection_type"] == "commercial"
        print(f"✓ Naharlagun manager created customer: {test_name}")
        return data["id"]
    
    def test_jullang_can_only_see_own_customers(self, jullang_token):
        """Jullang manager should only see Jullang customers"""
        headers = {"Authorization": f"Bearer {jullang_token}"}
        response = requests.get(f"{BASE_URL}/api/customers", headers=headers)
        assert response.status_code == 200, f"Failed to get customers: {response.text}"
        customers = response.json()
        
        # All customers should be from Jullang
        for customer in customers:
            assert customer["warehouse_name"] == "Jullang", \
                f"Jullang manager sees customer from {customer['warehouse_name']}"
        
        print(f"✓ Jullang manager sees only {len(customers)} Jullang customers")
    
    def test_naharlagun_can_only_see_own_customers(self, naharlagun_token):
        """Naharlagun manager should only see Naharlagun customers"""
        headers = {"Authorization": f"Bearer {naharlagun_token}"}
        response = requests.get(f"{BASE_URL}/api/customers", headers=headers)
        assert response.status_code == 200, f"Failed to get customers: {response.text}"
        customers = response.json()
        
        # All customers should be from Naharlagun
        for customer in customers:
            assert customer["warehouse_name"] == "Naharlagun", \
                f"Naharlagun manager sees customer from {customer['warehouse_name']}"
        
        print(f"✓ Naharlagun manager sees only {len(customers)} Naharlagun customers")


class TestAdminCustomerOperations:
    """Tests for admin customer operations"""
    
    def test_admin_can_see_all_customers(self, admin_token):
        """Admin should see customers from all warehouses"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/customers", headers=headers)
        assert response.status_code == 200, f"Failed to get customers: {response.text}"
        customers = response.json()
        
        # Get unique warehouse names
        warehouses = set(c["warehouse_name"] for c in customers)
        print(f"✓ Admin sees {len(customers)} customers from warehouses: {warehouses}")
    
    def test_admin_create_customer_for_warehouse(self, admin_token, jullang_warehouse_id):
        """Admin can create customer for a specific warehouse"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        test_name = f"TEST_Admin_Created_{uuid.uuid4().hex[:6]}"
        
        customer_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "connection_type": "domestic",
            "customer_name": test_name,
            "address": "Admin Created Address",
            "consumer_no": f"CON_{uuid.uuid4().hex[:6]}",
            "cash_memo_no": "CM_ADMIN",
            "cylinder_nos": "CYL-ADMIN",
            "gas_card_issued": True,
            "kyc_done": False,
            "remarks": "Admin created customer"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/customers/warehouse/{jullang_warehouse_id}",
            headers=headers, json=customer_data
        )
        assert response.status_code == 200, f"Failed to create customer: {response.text}"
        data = response.json()
        assert data["customer_name"] == test_name
        assert data["warehouse_name"] == "Jullang"
        print(f"✓ Admin created customer for Jullang: {test_name}")
        return data["id"]
    
    def test_admin_edit_customer(self, admin_token, jullang_warehouse_id):
        """Admin can edit a customer"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # First create a customer
        test_name = f"TEST_Edit_{uuid.uuid4().hex[:6]}"
        customer_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "connection_type": "domestic",
            "customer_name": test_name,
            "address": "Original Address",
            "consumer_no": "CON_EDIT",
            "cash_memo_no": "CM_EDIT",
            "cylinder_nos": "CYL-EDIT",
            "gas_card_issued": False,
            "kyc_done": False,
            "remarks": ""
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/customers/warehouse/{jullang_warehouse_id}",
            headers=headers, json=customer_data
        )
        assert create_response.status_code == 200
        customer_id = create_response.json()["id"]
        
        # Now update the customer
        update_data = {
            "customer_name": f"{test_name}_UPDATED",
            "address": "Updated Address",
            "gas_card_issued": True,
            "kyc_done": True
        }
        
        update_response = requests.put(
            f"{BASE_URL}/api/customers/{customer_id}",
            headers=headers, json=update_data
        )
        assert update_response.status_code == 200, f"Failed to update: {update_response.text}"
        updated = update_response.json()
        assert updated["customer_name"] == f"{test_name}_UPDATED"
        assert updated["gas_card_issued"] == True
        assert updated["kyc_done"] == True
        print(f"✓ Admin edited customer successfully")
    
    def test_admin_delete_customer(self, admin_token, jullang_warehouse_id):
        """Admin can delete a customer"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create a customer to delete
        test_name = f"TEST_Delete_{uuid.uuid4().hex[:6]}"
        customer_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "connection_type": "domestic",
            "customer_name": test_name,
            "address": "To Be Deleted",
            "consumer_no": "CON_DEL",
            "cash_memo_no": "CM_DEL",
            "cylinder_nos": "CYL-DEL",
            "gas_card_issued": False,
            "kyc_done": False,
            "remarks": ""
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/customers/warehouse/{jullang_warehouse_id}",
            headers=headers, json=customer_data
        )
        assert create_response.status_code == 200
        customer_id = create_response.json()["id"]
        
        # Delete the customer
        delete_response = requests.delete(
            f"{BASE_URL}/api/customers/{customer_id}",
            headers=headers
        )
        assert delete_response.status_code == 200, f"Failed to delete: {delete_response.text}"
        print(f"✓ Admin deleted customer successfully")
    
    def test_manager_cannot_edit_customer(self, jullang_token, admin_token, jullang_warehouse_id):
        """Warehouse manager cannot edit customers"""
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        manager_headers = {"Authorization": f"Bearer {jullang_token}"}
        
        # Admin creates a customer
        test_name = f"TEST_NoEdit_{uuid.uuid4().hex[:6]}"
        customer_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "connection_type": "domestic",
            "customer_name": test_name,
            "address": "Test Address",
            "consumer_no": "CON_NOEDIT",
            "cash_memo_no": "CM_NOEDIT",
            "cylinder_nos": "CYL-NOEDIT",
            "gas_card_issued": False,
            "kyc_done": False,
            "remarks": ""
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/customers/warehouse/{jullang_warehouse_id}",
            headers=admin_headers, json=customer_data
        )
        assert create_response.status_code == 200
        customer_id = create_response.json()["id"]
        
        # Manager tries to edit - should fail
        update_data = {"customer_name": "Modified Name"}
        edit_response = requests.put(
            f"{BASE_URL}/api/customers/{customer_id}",
            headers=manager_headers, json=update_data
        )
        assert edit_response.status_code == 403, "Manager should not be able to edit customers"
        print(f"✓ Manager correctly denied edit access")
    
    def test_manager_cannot_delete_customer(self, jullang_token, admin_token, jullang_warehouse_id):
        """Warehouse manager cannot delete customers"""
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        manager_headers = {"Authorization": f"Bearer {jullang_token}"}
        
        # Admin creates a customer
        test_name = f"TEST_NoDelete_{uuid.uuid4().hex[:6]}"
        customer_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "connection_type": "domestic",
            "customer_name": test_name,
            "address": "Test Address",
            "consumer_no": "CON_NODEL",
            "cash_memo_no": "CM_NODEL",
            "cylinder_nos": "CYL-NODEL",
            "gas_card_issued": False,
            "kyc_done": False,
            "remarks": ""
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/customers/warehouse/{jullang_warehouse_id}",
            headers=admin_headers, json=customer_data
        )
        assert create_response.status_code == 200
        customer_id = create_response.json()["id"]
        
        # Manager tries to delete - should fail
        delete_response = requests.delete(
            f"{BASE_URL}/api/customers/{customer_id}",
            headers=manager_headers
        )
        assert delete_response.status_code == 403, "Manager should not be able to delete customers"
        print(f"✓ Manager correctly denied delete access")


class TestCustomerSummary:
    """Tests for customer summary statistics"""
    
    def test_customer_summary(self, admin_token):
        """Test customer summary endpoint returns correct stats"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/customers/summary", headers=headers)
        assert response.status_code == 200, f"Failed to get summary: {response.text}"
        data = response.json()
        
        assert "total_customers" in data
        assert "total_domestic" in data
        assert "total_commercial" in data
        assert "total_gas_card_issued" in data
        assert "total_kyc_done" in data
        
        # Verify totals add up
        assert data["total_customers"] == data["total_domestic"] + data["total_commercial"]
        print(f"✓ Customer summary: {data['total_customers']} total, {data['total_domestic']} domestic, {data['total_commercial']} commercial")


class TestCustomerSearch:
    """Tests for customer search and filtering"""
    
    def test_search_by_name(self, admin_token, jullang_warehouse_id):
        """Test searching customers by name"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create a unique customer to search for
        unique_name = f"SEARCHTEST_{uuid.uuid4().hex[:6]}"
        customer_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "connection_type": "domestic",
            "customer_name": unique_name,
            "address": "Searchable Address",
            "consumer_no": "CON_SEARCH",
            "cash_memo_no": "CM_SEARCH",
            "cylinder_nos": "CYL-SEARCH",
            "gas_card_issued": False,
            "kyc_done": False,
            "remarks": ""
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/customers/warehouse/{jullang_warehouse_id}",
            headers=headers, json=customer_data
        )
        assert create_response.status_code == 200
        
        # Search for the customer
        search_response = requests.get(
            f"{BASE_URL}/api/customers?search={unique_name}",
            headers=headers
        )
        assert search_response.status_code == 200
        results = search_response.json()
        assert len(results) >= 1, "Search should find the customer"
        assert any(c["customer_name"] == unique_name for c in results)
        print(f"✓ Search by name working correctly")
    
    def test_filter_by_category(self, admin_token):
        """Test filtering customers by category (domestic/commercial)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get domestic customers
        domestic_response = requests.get(
            f"{BASE_URL}/api/customers?category=domestic",
            headers=headers
        )
        assert domestic_response.status_code == 200
        domestic_customers = domestic_response.json()
        
        # All should be domestic
        for c in domestic_customers:
            assert c["connection_type"] == "domestic", f"Expected domestic, got {c['connection_type']}"
        
        # Get commercial customers
        commercial_response = requests.get(
            f"{BASE_URL}/api/customers?category=commercial",
            headers=headers
        )
        assert commercial_response.status_code == 200
        commercial_customers = commercial_response.json()
        
        # All should be commercial
        for c in commercial_customers:
            assert c["connection_type"] == "commercial", f"Expected commercial, got {c['connection_type']}"
        
        print(f"✓ Category filter working: {len(domestic_customers)} domestic, {len(commercial_customers)} commercial")


class TestExports:
    """Tests for PDF and Excel exports"""
    
    def test_download_sample_template(self, admin_token):
        """Test downloading sample Excel template"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/customers/sample-excel", headers=headers)
        assert response.status_code == 200, f"Failed to download template: {response.text}"
        assert response.headers.get("content-type") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert len(response.content) > 0
        print(f"✓ Sample Excel template download working")
    
    def test_export_pdf(self, admin_token):
        """Test exporting customers to PDF"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/export/customers-pdf", headers=headers)
        assert response.status_code == 200, f"Failed to export PDF: {response.text}"
        assert response.headers.get("content-type") == "application/pdf"
        assert len(response.content) > 0
        print(f"✓ PDF export working")
    
    def test_export_excel(self, admin_token):
        """Test exporting customers to Excel"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/export/customers-excel", headers=headers)
        assert response.status_code == 200, f"Failed to export Excel: {response.text}"
        assert response.headers.get("content-type") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert len(response.content) > 0
        print(f"✓ Excel export working")


class TestBulkUpload:
    """Tests for bulk customer upload"""
    
    def test_manager_bulk_upload(self, jullang_token):
        """Warehouse manager can bulk upload customers to their warehouse"""
        headers = {"Authorization": f"Bearer {jullang_token}"}
        
        bulk_data = {
            "customers": [
                {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "connection_type": "domestic",
                    "customer_name": f"BULK_TEST_1_{uuid.uuid4().hex[:6]}",
                    "address": "Bulk Address 1",
                    "consumer_no": "BULK_CON_1",
                    "cash_memo_no": "BULK_CM_1",
                    "cylinder_nos": "BULK_CYL_1",
                    "gas_card_issued": True,
                    "kyc_done": False,
                    "remarks": "Bulk upload test 1"
                },
                {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "connection_type": "commercial",
                    "customer_name": f"BULK_TEST_2_{uuid.uuid4().hex[:6]}",
                    "address": "Bulk Address 2",
                    "consumer_no": "BULK_CON_2",
                    "cash_memo_no": "BULK_CM_2",
                    "cylinder_nos": "BULK_CYL_2",
                    "gas_card_issued": False,
                    "kyc_done": True,
                    "remarks": "Bulk upload test 2"
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/customers/bulk", 
                                headers=headers, json=bulk_data)
        assert response.status_code == 200, f"Bulk upload failed: {response.text}"
        data = response.json()
        assert data["count"] == 2
        print(f"✓ Manager bulk upload working: {data['count']} customers uploaded")
    
    def test_admin_bulk_upload_for_warehouse(self, admin_token, naharlagun_warehouse_id):
        """Admin can bulk upload customers to a specific warehouse"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        bulk_data = {
            "customers": [
                {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "connection_type": "domestic",
                    "customer_name": f"ADMIN_BULK_1_{uuid.uuid4().hex[:6]}",
                    "address": "Admin Bulk Address",
                    "consumer_no": "ADMIN_BULK_CON",
                    "cash_memo_no": "ADMIN_BULK_CM",
                    "cylinder_nos": "ADMIN_BULK_CYL",
                    "gas_card_issued": True,
                    "kyc_done": True,
                    "remarks": "Admin bulk upload"
                }
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/customers/bulk/warehouse/{naharlagun_warehouse_id}",
            headers=headers, json=bulk_data
        )
        assert response.status_code == 200, f"Admin bulk upload failed: {response.text}"
        data = response.json()
        assert data["count"] == 1
        print(f"✓ Admin bulk upload working for Naharlagun: {data['count']} customer uploaded")


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Clean up test data after all tests"""
    yield
    # Cleanup runs after all tests
    try:
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # Get all customers with TEST_ prefix
            customers = requests.get(f"{BASE_URL}/api/customers", headers=headers).json()
            deleted = 0
            for c in customers:
                if c["customer_name"].startswith("TEST_") or \
                   c["customer_name"].startswith("BULK_TEST_") or \
                   c["customer_name"].startswith("ADMIN_BULK_") or \
                   c["customer_name"].startswith("SEARCHTEST_"):
                    requests.delete(f"{BASE_URL}/api/customers/{c['id']}", headers=headers)
                    deleted += 1
            if deleted > 0:
                print(f"\n✓ Cleaned up {deleted} test customers")
    except Exception as e:
        print(f"\nWarning: Cleanup failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
