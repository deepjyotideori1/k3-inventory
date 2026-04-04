"""
Test suite for HRMS API after refactoring from monolithic hrms.py to 5 modular routers:
- hrms_settings.py (Company Settings + Departments + Logo)
- hrms_employees.py (CRUD + Bulk Upload + Increment + Photo)
- hrms_dashboard.py (Stats + Preference)
- hrms_search.py (Smart Search)
- hrms_users.py (User Management)

This is a REGRESSION test to ensure zero functional regression after the split.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://unified-checkout-8.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASSWORD = "Admin@123"
HR_ADMIN_EMAIL = "hr@k3gas.com"
HR_ADMIN_PASSWORD = "Hr@123"
EMPLOYEE_EMAIL = "employee@k3gas.com"
EMPLOYEE_PASSWORD = "Employee@123"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token for authenticated requests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def hr_admin_token():
    """Get HR admin token for authenticated requests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": HR_ADMIN_EMAIL,
        "password": HR_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("HR Admin authentication failed")


@pytest.fixture(scope="module")
def employee_token():
    """Get employee token for authenticated requests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": EMPLOYEE_EMAIL,
        "password": EMPLOYEE_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Employee authentication failed")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Get authorization headers for admin"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def hr_headers(hr_admin_token):
    """Get authorization headers for HR admin"""
    return {"Authorization": f"Bearer {hr_admin_token}"}


@pytest.fixture(scope="module")
def employee_headers(employee_token):
    """Get authorization headers for employee"""
    return {"Authorization": f"Bearer {employee_token}"}


# ============ HRMS SETTINGS ROUTER TESTS (hrms_settings.py) ============

class TestHRMSCompanySettings:
    """Tests for /api/hrms/company-settings endpoints"""
    
    def test_get_company_settings(self, admin_headers):
        """Test GET /api/hrms/company-settings"""
        response = requests.get(f"{BASE_URL}/api/hrms/company-settings", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "company_name" in data
        assert "email" in data
        print(f"✓ Company settings: {data.get('company_name')}")
    
    def test_update_company_settings(self, hr_headers):
        """Test PUT /api/hrms/company-settings"""
        response = requests.put(f"{BASE_URL}/api/hrms/company-settings", 
            headers=hr_headers,
            json={"tagline": "Khayal Hamesha"})
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print("✓ Company settings updated")


class TestHRMSDepartments:
    """Tests for /api/hrms/departments endpoints"""
    
    def test_get_departments(self, admin_headers):
        """Test GET /api/hrms/departments"""
        response = requests.get(f"{BASE_URL}/api/hrms/departments", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Departments list: {len(data)} departments")
    
    def test_create_department_requires_admin(self, employee_headers):
        """Test POST /api/hrms/departments requires admin/hr_admin role"""
        response = requests.post(f"{BASE_URL}/api/hrms/departments",
            headers=employee_headers,
            json={"name": "Test Dept"})
        assert response.status_code == 403
        print("✓ Create department correctly requires admin/hr_admin role")


# ============ HRMS EMPLOYEES ROUTER TESTS (hrms_employees.py) ============

class TestHRMSEmployees:
    """Tests for /api/hrms/employees endpoints"""
    
    def test_get_employees_list(self, admin_headers):
        """Test GET /api/hrms/employees with pagination"""
        response = requests.get(f"{BASE_URL}/api/hrms/employees?page=1&limit=10", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "employees" in data
        assert "total" in data
        assert "page" in data
        assert "total_pages" in data
        print(f"✓ Employees list: {data['total']} total, page {data['page']}/{data['total_pages']}")
    
    def test_get_employees_with_search(self, admin_headers):
        """Test GET /api/hrms/employees with search filter"""
        response = requests.get(f"{BASE_URL}/api/hrms/employees?search=admin", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "employees" in data
        print(f"✓ Employees search: {len(data['employees'])} results for 'admin'")
    
    def test_get_upload_logs(self, hr_headers):
        """Test GET /api/hrms/employees/upload-logs"""
        response = requests.get(f"{BASE_URL}/api/hrms/employees/upload-logs", headers=hr_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Upload logs: {len(data)} logs")
    
    def test_bulk_upload_template(self, hr_headers):
        """Test GET /api/hrms/employees/bulk-upload/template returns xlsx"""
        response = requests.get(f"{BASE_URL}/api/hrms/employees/bulk-upload/template", headers=hr_headers)
        assert response.status_code == 200
        assert 'spreadsheet' in response.headers.get('content-type', '')
        print(f"✓ Bulk upload template: {len(response.content)} bytes")


# ============ HRMS DASHBOARD ROUTER TESTS (hrms_dashboard.py) ============

class TestHRMSDashboard:
    """Tests for /api/hrms/dashboard endpoints"""
    
    def test_get_dashboard_stats(self, hr_headers):
        """Test GET /api/hrms/dashboard/stats"""
        response = requests.get(f"{BASE_URL}/api/hrms/dashboard/stats", headers=hr_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_employees" in data
        assert "total_departments" in data
        assert "department_breakdown" in data
        assert "recent_employees" in data
        assert "total_monthly_payroll" in data
        assert "gender_breakdown" in data
        print(f"✓ Dashboard stats: {data['total_employees']} employees, {data['total_departments']} departments")


class TestDashboardPreference:
    """Tests for /api/auth/set-dashboard and /api/auth/dashboard-preference"""
    
    def test_set_dashboard_preference(self, admin_headers):
        """Test POST /api/auth/set-dashboard"""
        response = requests.post(f"{BASE_URL}/api/auth/set-dashboard",
            headers=admin_headers,
            json={"dashboard": "hrms"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("active_dashboard") == "hrms"
        print("✓ Dashboard preference set to hrms")
    
    def test_get_dashboard_preference(self, admin_headers):
        """Test GET /api/auth/dashboard-preference"""
        response = requests.get(f"{BASE_URL}/api/auth/dashboard-preference", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "active_dashboard" in data
        print(f"✓ Dashboard preference: {data.get('active_dashboard')}")
    
    def test_set_invalid_dashboard_preference(self, admin_headers):
        """Test POST /api/auth/set-dashboard with invalid value"""
        response = requests.post(f"{BASE_URL}/api/auth/set-dashboard",
            headers=admin_headers,
            json={"dashboard": "invalid"})
        assert response.status_code == 400
        print("✓ Invalid dashboard preference correctly rejected")


# ============ HRMS SEARCH ROUTER TESTS (hrms_search.py) ============

class TestHRMSSearch:
    """Tests for /api/hrms/search endpoint"""
    
    def test_search_employees(self, admin_headers):
        """Test GET /api/hrms/search?q=admin"""
        response = requests.get(f"{BASE_URL}/api/hrms/search?q=admin", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data
        assert "query" in data
        assert data["query"] == "admin"
        print(f"✓ Search 'admin': {data['total']} results")
    
    def test_search_empty_query(self, admin_headers):
        """Test GET /api/hrms/search with empty query"""
        response = requests.get(f"{BASE_URL}/api/hrms/search?q=", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []
        assert data["total"] == 0
        print("✓ Empty search returns empty results")
    
    def test_search_departments(self, admin_headers):
        """Test GET /api/hrms/search?q=admin searches across modules"""
        response = requests.get(f"{BASE_URL}/api/hrms/search?q=admin", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "module_counts" in data
        print(f"✓ Search module counts: {data.get('module_counts', {})}")


# ============ HRMS USERS ROUTER TESTS (hrms_users.py) ============

class TestHRMSUsers:
    """Tests for /api/hrms/users endpoints"""
    
    def test_list_hrms_users(self, admin_headers):
        """Test GET /api/hrms/users"""
        response = requests.get(f"{BASE_URL}/api/hrms/users", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should include hr_admin and hrms_employee users
        roles = [u.get('role') for u in data]
        print(f"✓ HRMS users list: {len(data)} users, roles: {set(roles)}")
    
    def test_list_hrms_users_requires_admin(self, employee_headers):
        """Test GET /api/hrms/users requires admin/hr_admin role"""
        response = requests.get(f"{BASE_URL}/api/hrms/users", headers=employee_headers)
        assert response.status_code == 403
        print("✓ HRMS users list correctly requires admin/hr_admin role")


# ============ ACCESS CONTROL TESTS ============

class TestAccessControl:
    """Tests for role-based access control"""
    
    def test_employee_can_view_employees(self, employee_headers):
        """Test employee can view employees list"""
        response = requests.get(f"{BASE_URL}/api/hrms/employees", headers=employee_headers)
        assert response.status_code == 200
        print("✓ Employee can view employees list")
    
    def test_employee_cannot_create_employee(self, employee_headers):
        """Test employee cannot create new employee"""
        response = requests.post(f"{BASE_URL}/api/hrms/employees",
            headers=employee_headers,
            json={
                "name": "Test Employee",
                "email": "test@test.com",
                "phone": "1234567890",
                "department_id": "test",
                "designation": "Test",
                "date_of_joining": "2024-01-01"
            })
        assert response.status_code == 403
        print("✓ Employee correctly cannot create new employee")
    
    def test_hr_admin_can_access_dashboard_stats(self, hr_headers):
        """Test HR admin can access dashboard stats"""
        response = requests.get(f"{BASE_URL}/api/hrms/dashboard/stats", headers=hr_headers)
        assert response.status_code == 200
        print("✓ HR admin can access dashboard stats")
    
    def test_admin_can_access_all_hrms_endpoints(self, admin_headers):
        """Test admin can access all HRMS endpoints"""
        endpoints = [
            "/api/hrms/company-settings",
            "/api/hrms/departments",
            "/api/hrms/employees",
            "/api/hrms/dashboard/stats",
            "/api/hrms/search?q=test",
            "/api/hrms/users"
        ]
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=admin_headers)
            assert response.status_code == 200, f"Admin failed to access {endpoint}"
        print(f"✓ Admin can access all {len(endpoints)} HRMS endpoints")


# ============ AUTHENTICATION TESTS ============

class TestAuthentication:
    """Tests for authentication"""
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print("✓ Admin login successful")
    
    def test_hr_admin_login(self):
        """Test HR admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": HR_ADMIN_EMAIL,
            "password": HR_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "hr_admin"
        print("✓ HR admin login successful")
    
    def test_employee_login(self):
        """Test employee login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": EMPLOYEE_EMAIL,
            "password": EMPLOYEE_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "hrms_employee"
        print("✓ Employee login successful")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
