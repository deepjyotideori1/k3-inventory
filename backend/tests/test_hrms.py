"""
HRMS Backend API Tests - Phase 1
Tests for: Dashboard Selector, HRMS Dashboard Stats, Employees, Departments, Company Settings
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token for admin"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("token")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestAuthLogin:
    """Authentication tests"""
    
    def test_login_success(self, api_client):
        """Test admin login returns 200 with token"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        print(f"Login successful for {ADMIN_EMAIL}")
    
    def test_login_invalid_credentials(self, api_client):
        """Test login with wrong credentials returns 401"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpass"
        })
        assert response.status_code == 401
        print("Invalid credentials correctly rejected")


class TestDashboardPreference:
    """Dashboard preference API tests"""
    
    def test_set_dashboard_inventory(self, authenticated_client):
        """Test setting dashboard preference to inventory"""
        response = authenticated_client.post(f"{BASE_URL}/api/auth/set-dashboard", json={
            "dashboard": "inventory"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["active_dashboard"] == "inventory"
        print("Dashboard preference set to inventory")
    
    def test_set_dashboard_hrms(self, authenticated_client):
        """Test setting dashboard preference to hrms"""
        response = authenticated_client.post(f"{BASE_URL}/api/auth/set-dashboard", json={
            "dashboard": "hrms"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["active_dashboard"] == "hrms"
        print("Dashboard preference set to hrms")
    
    def test_set_dashboard_invalid(self, authenticated_client):
        """Test setting invalid dashboard preference returns 400"""
        response = authenticated_client.post(f"{BASE_URL}/api/auth/set-dashboard", json={
            "dashboard": "invalid"
        })
        assert response.status_code == 400
        print("Invalid dashboard preference correctly rejected")
    
    def test_get_dashboard_preference(self, authenticated_client):
        """Test getting dashboard preference"""
        response = authenticated_client.get(f"{BASE_URL}/api/auth/dashboard-preference")
        assert response.status_code == 200
        data = response.json()
        assert "active_dashboard" in data
        print(f"Current dashboard preference: {data['active_dashboard']}")


class TestHRMSDashboardStats:
    """HRMS Dashboard Stats API tests"""
    
    def test_get_dashboard_stats(self, authenticated_client):
        """Test GET /api/hrms/dashboard/stats returns correct structure"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected fields
        assert "total_employees" in data
        assert "total_inactive" in data
        assert "total_departments" in data
        assert "department_breakdown" in data
        assert "recent_employees" in data
        assert "total_monthly_payroll" in data
        assert "gender_breakdown" in data
        
        # Verify types
        assert isinstance(data["total_employees"], int)
        assert isinstance(data["total_departments"], int)
        assert isinstance(data["department_breakdown"], list)
        assert isinstance(data["recent_employees"], list)
        assert isinstance(data["gender_breakdown"], dict)
        
        print(f"Dashboard stats: {data['total_employees']} employees, {data['total_departments']} departments")


class TestHRMSDepartments:
    """HRMS Departments API tests"""
    
    def test_get_departments(self, authenticated_client):
        """Test GET /api/hrms/departments returns list"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/departments")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} departments")
    
    def test_create_department(self, authenticated_client):
        """Test POST /api/hrms/departments creates department"""
        unique_name = f"TEST_Dept_{uuid.uuid4().hex[:6]}"
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/departments", json={
            "name": unique_name,
            "description": "Test department for automated testing"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == unique_name
        assert "id" in data
        print(f"Created department: {unique_name}")
        
        # Verify via GET
        get_response = authenticated_client.get(f"{BASE_URL}/api/hrms/departments")
        assert get_response.status_code == 200
        depts = get_response.json()
        found = any(d["name"] == unique_name for d in depts)
        assert found, "Created department not found in list"
        
        # Cleanup - delete the test department
        dept_id = data["id"]
        del_response = authenticated_client.delete(f"{BASE_URL}/api/hrms/departments/{dept_id}")
        assert del_response.status_code == 200
        print(f"Cleaned up test department: {unique_name}")
    
    def test_create_duplicate_department(self, authenticated_client):
        """Test creating duplicate department returns 400"""
        # First get existing departments
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/departments")
        depts = response.json()
        if len(depts) > 0:
            existing_name = depts[0]["name"]
            dup_response = authenticated_client.post(f"{BASE_URL}/api/hrms/departments", json={
                "name": existing_name
            })
            assert dup_response.status_code == 400
            print(f"Duplicate department '{existing_name}' correctly rejected")
        else:
            pytest.skip("No existing departments to test duplicate")


class TestHRMSEmployees:
    """HRMS Employees API tests"""
    
    def test_get_employees_paginated(self, authenticated_client):
        """Test GET /api/hrms/employees returns paginated results"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/employees")
        assert response.status_code == 200
        data = response.json()
        
        # Verify pagination structure
        assert "employees" in data
        assert "total" in data
        assert "page" in data
        assert "total_pages" in data
        assert isinstance(data["employees"], list)
        print(f"Found {data['total']} employees, page {data['page']} of {data['total_pages']}")
    
    def test_get_employees_with_search(self, authenticated_client):
        """Test GET /api/hrms/employees with search parameter"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/employees", params={"search": "Rajesh"})
        assert response.status_code == 200
        data = response.json()
        assert "employees" in data
        print(f"Search 'Rajesh' returned {len(data['employees'])} results")
    
    def test_get_employees_with_status_filter(self, authenticated_client):
        """Test GET /api/hrms/employees with status filter"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/employees", params={"status": "active"})
        assert response.status_code == 200
        data = response.json()
        # All returned employees should be active
        for emp in data["employees"]:
            assert emp.get("is_active") == True
        print(f"Active employees filter returned {len(data['employees'])} results")
    
    def test_create_employee_and_verify(self, authenticated_client):
        """Test POST /api/hrms/employees creates employee and verify via GET"""
        # First get a department ID
        dept_response = authenticated_client.get(f"{BASE_URL}/api/hrms/departments")
        depts = dept_response.json()
        if len(depts) == 0:
            pytest.skip("No departments available for employee creation")
        
        dept_id = depts[0]["id"]
        unique_email = f"test_{uuid.uuid4().hex[:8]}@test.com"
        
        employee_data = {
            "name": "TEST_Employee",
            "email": unique_email,
            "phone": "9876543210",
            "department_id": dept_id,
            "designation": "Test Engineer",
            "date_of_joining": "2025-01-15",
            "gender": "male",
            "basic_salary": 25000,
            "hra": 5000,
            "da": 2000
        }
        
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/employees", json=employee_data)
        assert response.status_code == 200
        data = response.json()
        
        # Verify response data
        assert data["name"] == "TEST_Employee"
        assert data["email"] == unique_email
        assert "id" in data
        assert "employee_id" in data  # Auto-generated K3-XXXX
        assert data["employee_id"].startswith("K3-")
        
        emp_id = data["id"]
        print(f"Created employee: {data['employee_id']} - {data['name']}")
        
        # Verify via GET single employee
        get_response = authenticated_client.get(f"{BASE_URL}/api/hrms/employees/{emp_id}")
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["email"] == unique_email
        assert fetched["name"] == "TEST_Employee"
        
        # Cleanup - deactivate the test employee
        del_response = authenticated_client.delete(f"{BASE_URL}/api/hrms/employees/{emp_id}")
        assert del_response.status_code == 200
        print(f"Cleaned up test employee: {data['employee_id']}")
    
    def test_create_employee_missing_fields(self, authenticated_client):
        """Test POST /api/hrms/employees with missing required fields returns 400"""
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/employees", json={
            "name": "Incomplete Employee"
            # Missing email, phone, department_id, designation, date_of_joining
        })
        assert response.status_code == 400
        print("Missing required fields correctly rejected")
    
    def test_create_employee_duplicate_email(self, authenticated_client):
        """Test creating employee with duplicate email returns 400"""
        # Get existing employees
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/employees")
        employees = response.json()["employees"]
        if len(employees) > 0:
            existing_email = employees[0]["email"]
            dept_response = authenticated_client.get(f"{BASE_URL}/api/hrms/departments")
            depts = dept_response.json()
            if len(depts) > 0:
                dup_response = authenticated_client.post(f"{BASE_URL}/api/hrms/employees", json={
                    "name": "Duplicate Test",
                    "email": existing_email,
                    "phone": "1234567890",
                    "department_id": depts[0]["id"],
                    "designation": "Test",
                    "date_of_joining": "2025-01-01"
                })
                assert dup_response.status_code == 400
                print(f"Duplicate email '{existing_email}' correctly rejected")
        else:
            pytest.skip("No existing employees to test duplicate email")


class TestHRMSCompanySettings:
    """HRMS Company Settings API tests"""
    
    def test_get_company_settings(self, authenticated_client):
        """Test GET /api/hrms/company-settings returns company info"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/company-settings")
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected fields
        assert "company_name" in data
        assert "tagline" in data
        assert "address" in data
        assert "email" in data
        assert "helpline" in data
        print(f"Company settings: {data['company_name']}")
    
    def test_update_company_settings(self, authenticated_client):
        """Test PUT /api/hrms/company-settings updates settings"""
        # First get current settings
        get_response = authenticated_client.get(f"{BASE_URL}/api/hrms/company-settings")
        original = get_response.json()
        
        # Update tagline
        new_tagline = f"Test Tagline {uuid.uuid4().hex[:6]}"
        update_response = authenticated_client.put(f"{BASE_URL}/api/hrms/company-settings", json={
            "tagline": new_tagline
        })
        assert update_response.status_code == 200
        
        # Verify update
        verify_response = authenticated_client.get(f"{BASE_URL}/api/hrms/company-settings")
        updated = verify_response.json()
        assert updated["tagline"] == new_tagline
        print(f"Updated tagline to: {new_tagline}")
        
        # Restore original
        authenticated_client.put(f"{BASE_URL}/api/hrms/company-settings", json={
            "tagline": original.get("tagline", "Khayal Hamesha")
        })
        print("Restored original tagline")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
