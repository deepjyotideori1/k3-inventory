"""
Access Control System Tests
Tests for role-based access control for HRMS and Inventory dashboards.
Roles: admin, hr_admin, hrms_employee, sales_executive, warehouse_manager
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"email": "admin@k3gas.com", "password": "Admin@123"}
HR_ADMIN_CREDS = {"email": "hr@k3gas.com", "password": "Hr@123"}
EMPLOYEE_CREDS = {"email": "employee@k3gas.com", "password": "Employee@123"}
SALES_CREDS = {"email": "sales@k3gas.com", "password": "Sales@123"}


class TestLoginAndAllowedDashboards:
    """Test login returns correct allowed_dashboards for each role"""
    
    def test_admin_login_returns_both_dashboards(self):
        """Admin should have access to both inventory and hrms dashboards"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        
        data = response.json()
        assert "user" in data
        assert data["user"]["role"] == "admin"
        assert "allowed_dashboards" in data["user"]
        assert set(data["user"]["allowed_dashboards"]) == {"inventory", "hrms"}
        print(f"✓ Admin login: role={data['user']['role']}, allowed_dashboards={data['user']['allowed_dashboards']}")
    
    def test_hr_admin_login_returns_hrms_only(self):
        """HR Admin should only have access to hrms dashboard"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=HR_ADMIN_CREDS)
        assert response.status_code == 200, f"HR Admin login failed: {response.text}"
        
        data = response.json()
        assert "user" in data
        assert data["user"]["role"] == "hr_admin"
        assert "allowed_dashboards" in data["user"]
        assert data["user"]["allowed_dashboards"] == ["hrms"]
        print(f"✓ HR Admin login: role={data['user']['role']}, allowed_dashboards={data['user']['allowed_dashboards']}")
    
    def test_employee_login_returns_hrms_only(self):
        """Employee should only have access to hrms dashboard"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=EMPLOYEE_CREDS)
        assert response.status_code == 200, f"Employee login failed: {response.text}"
        
        data = response.json()
        assert "user" in data
        assert data["user"]["role"] == "hrms_employee"
        assert "allowed_dashboards" in data["user"]
        assert data["user"]["allowed_dashboards"] == ["hrms"]
        # Check linked_employee_id is present
        assert "linked_employee_id" in data["user"]
        print(f"✓ Employee login: role={data['user']['role']}, allowed_dashboards={data['user']['allowed_dashboards']}, linked_employee_id={data['user'].get('linked_employee_id')}")
    
    def test_sales_executive_login_returns_inventory_only(self):
        """Sales Executive should only have access to inventory dashboard"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=SALES_CREDS)
        assert response.status_code == 200, f"Sales Executive login failed: {response.text}"
        
        data = response.json()
        assert "user" in data
        assert data["user"]["role"] == "sales_executive"
        assert "allowed_dashboards" in data["user"]
        assert data["user"]["allowed_dashboards"] == ["inventory"]
        print(f"✓ Sales Executive login: role={data['user']['role']}, allowed_dashboards={data['user']['allowed_dashboards']}")


class TestAuthMeEndpoint:
    """Test /api/auth/me returns correct allowed_dashboards and linked_employee_id"""
    
    def get_token(self, creds):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=creds)
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_admin_me_returns_both_dashboards(self):
        """GET /api/auth/me for admin returns both dashboards"""
        token = self.get_token(ADMIN_CREDS)
        assert token, "Failed to get admin token"
        
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["role"] == "admin"
        assert set(data["allowed_dashboards"]) == {"inventory", "hrms"}
        print(f"✓ Admin /me: allowed_dashboards={data['allowed_dashboards']}")
    
    def test_hr_admin_me_returns_hrms_only(self):
        """GET /api/auth/me for hr_admin returns hrms only"""
        token = self.get_token(HR_ADMIN_CREDS)
        assert token, "Failed to get hr_admin token"
        
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["role"] == "hr_admin"
        assert data["allowed_dashboards"] == ["hrms"]
        print(f"✓ HR Admin /me: allowed_dashboards={data['allowed_dashboards']}")
    
    def test_employee_me_returns_hrms_and_linked_employee_id(self):
        """GET /api/auth/me for employee returns hrms and linked_employee_id"""
        token = self.get_token(EMPLOYEE_CREDS)
        assert token, "Failed to get employee token"
        
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["role"] == "hrms_employee"
        assert data["allowed_dashboards"] == ["hrms"]
        assert "linked_employee_id" in data
        print(f"✓ Employee /me: allowed_dashboards={data['allowed_dashboards']}, linked_employee_id={data.get('linked_employee_id')}")
    
    def test_sales_me_returns_inventory_only(self):
        """GET /api/auth/me for sales_executive returns inventory only"""
        token = self.get_token(SALES_CREDS)
        assert token, "Failed to get sales token"
        
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["role"] == "sales_executive"
        assert data["allowed_dashboards"] == ["inventory"]
        print(f"✓ Sales /me: allowed_dashboards={data['allowed_dashboards']}")


class TestHRMSAccessMiddleware:
    """Test HRMS access middleware - require_hrms_access and require_hrms_admin"""
    
    def get_token(self, creds):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=creds)
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_admin_can_access_hrms_dashboard(self):
        """Admin can access HRMS dashboard stats"""
        token = self.get_token(ADMIN_CREDS)
        assert token, "Failed to get admin token"
        
        response = requests.get(
            f"{BASE_URL}/api/hrms/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        print("✓ Admin can access HRMS dashboard")
    
    def test_hr_admin_can_access_hrms_dashboard(self):
        """HR Admin can access HRMS dashboard stats"""
        token = self.get_token(HR_ADMIN_CREDS)
        assert token, "Failed to get hr_admin token"
        
        response = requests.get(
            f"{BASE_URL}/api/hrms/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        print("✓ HR Admin can access HRMS dashboard")
    
    def test_employee_can_access_hrms_dashboard(self):
        """Employee can access HRMS dashboard stats"""
        token = self.get_token(EMPLOYEE_CREDS)
        assert token, "Failed to get employee token"
        
        response = requests.get(
            f"{BASE_URL}/api/hrms/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        print("✓ Employee can access HRMS dashboard")
    
    def test_sales_cannot_access_hrms_dashboard(self):
        """Sales Executive cannot access HRMS dashboard"""
        token = self.get_token(SALES_CREDS)
        assert token, "Failed to get sales token"
        
        response = requests.get(
            f"{BASE_URL}/api/hrms/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Sales Executive correctly denied HRMS access (403)")


class TestEmployeeAttendanceRestriction:
    """Test that employee role can only see their own attendance records"""
    
    def get_token(self, creds):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=creds)
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_employee_attendance_restricted_to_own_records(self):
        """Employee can only see their own attendance records via linked_employee_id"""
        # First get employee's linked_employee_id
        token = self.get_token(EMPLOYEE_CREDS)
        assert token, "Failed to get employee token"
        
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200
        linked_employee_id = me_response.json().get("linked_employee_id")
        print(f"Employee linked_employee_id: {linked_employee_id}")
        
        # Get attendance records
        att_response = requests.get(
            f"{BASE_URL}/api/hrms/attendance",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert att_response.status_code == 200
        
        data = att_response.json()
        records = data.get("records", [])
        
        # If there are records, they should all belong to the linked employee
        if records and linked_employee_id:
            for rec in records:
                assert rec.get("employee_id") == linked_employee_id, \
                    f"Employee seeing other's attendance: {rec.get('employee_id')} != {linked_employee_id}"
            print(f"✓ Employee attendance restricted: {len(records)} records, all for linked_employee_id={linked_employee_id}")
        else:
            print(f"✓ Employee attendance restricted: {len(records)} records (no records or no linked_employee_id)")
    
    def test_hr_admin_can_see_all_attendance(self):
        """HR Admin can see all attendance records"""
        token = self.get_token(HR_ADMIN_CREDS)
        assert token, "Failed to get hr_admin token"
        
        response = requests.get(
            f"{BASE_URL}/api/hrms/attendance",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        records = data.get("records", [])
        print(f"✓ HR Admin can see all attendance: {len(records)} records")


class TestUserCreationWithRoles:
    """Test creating users with hr_admin and hrms_employee roles"""
    
    def get_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_create_hr_admin_user(self):
        """Admin can create HR Admin user"""
        token = self.get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create HR Admin user
        user_data = {
            "email": "test_hr_admin@k3gas.com",
            "password": "TestHR@123",
            "name": "Test HR Admin",
            "role": "hr_admin"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users",
            json=user_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 400 and "already exists" in response.text:
            print("✓ HR Admin user already exists (skipping creation)")
            return
        
        assert response.status_code in [200, 201], f"Failed to create HR Admin: {response.text}"
        
        data = response.json()
        assert data["role"] == "hr_admin"
        assert data["allowed_dashboards"] == ["hrms"]
        print(f"✓ Created HR Admin user: {data['email']}, allowed_dashboards={data['allowed_dashboards']}")
        
        # Cleanup - delete the test user
        requests.delete(
            f"{BASE_URL}/api/users/{data['id']}",
            headers={"Authorization": f"Bearer {token}"}
        )
    
    def test_create_employee_user_with_linked_employee_id(self):
        """Admin can create Employee user with linked_employee_id"""
        token = self.get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create Employee user with linked_employee_id
        user_data = {
            "email": "test_employee@k3gas.com",
            "password": "TestEmp@123",
            "name": "Test Employee",
            "role": "hrms_employee",
            "linked_employee_id": "test-employee-id-123"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users",
            json=user_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 400 and "already exists" in response.text:
            print("✓ Employee user already exists (skipping creation)")
            return
        
        assert response.status_code in [200, 201], f"Failed to create Employee: {response.text}"
        
        data = response.json()
        assert data["role"] == "hrms_employee"
        assert data["allowed_dashboards"] == ["hrms"]
        assert data.get("linked_employee_id") == "test-employee-id-123"
        print(f"✓ Created Employee user: {data['email']}, linked_employee_id={data.get('linked_employee_id')}")
        
        # Cleanup - delete the test user
        requests.delete(
            f"{BASE_URL}/api/users/{data['id']}",
            headers={"Authorization": f"Bearer {token}"}
        )


class TestRegressionHRMSDashboard:
    """Regression tests - HRMS Dashboard loads for all HRMS roles"""
    
    def get_token(self, creds):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=creds)
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_hrms_dashboard_loads_for_admin(self):
        """HRMS Dashboard loads for admin"""
        token = self.get_token(ADMIN_CREDS)
        assert token, "Failed to get admin token"
        
        response = requests.get(
            f"{BASE_URL}/api/hrms/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_employees" in data
        print(f"✓ HRMS Dashboard loads for admin: total_employees={data.get('total_employees')}")
    
    def test_hrms_dashboard_loads_for_hr_admin(self):
        """HRMS Dashboard loads for hr_admin"""
        token = self.get_token(HR_ADMIN_CREDS)
        assert token, "Failed to get hr_admin token"
        
        response = requests.get(
            f"{BASE_URL}/api/hrms/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_employees" in data
        print(f"✓ HRMS Dashboard loads for hr_admin: total_employees={data.get('total_employees')}")
    
    def test_hrms_dashboard_loads_for_employee(self):
        """HRMS Dashboard loads for employee"""
        token = self.get_token(EMPLOYEE_CREDS)
        assert token, "Failed to get employee token"
        
        response = requests.get(
            f"{BASE_URL}/api/hrms/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_employees" in data
        print(f"✓ HRMS Dashboard loads for employee: total_employees={data.get('total_employees')}")


class TestRegressionAdminBothDashboards:
    """Regression tests - Admin can access both dashboards"""
    
    def get_admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    def test_admin_can_access_inventory_dashboard(self):
        """Admin can access Inventory dashboard"""
        token = self.get_admin_token()
        assert token, "Failed to get admin token"
        
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        print("✓ Admin can access Inventory dashboard")
    
    def test_admin_can_access_hrms_dashboard(self):
        """Admin can access HRMS dashboard"""
        token = self.get_admin_token()
        assert token, "Failed to get admin token"
        
        response = requests.get(
            f"{BASE_URL}/api/hrms/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        print("✓ Admin can access HRMS dashboard")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
