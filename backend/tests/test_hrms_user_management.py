"""
HRMS User Management API Tests
Tests for: GET/POST/PUT/DELETE /api/hrms/users, reset-password
Access Control: Admin & HR Admin can access, Employee gets 403
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"email": "admin@k3gas.com", "password": "Admin@123"}
HR_ADMIN_CREDS = {"email": "hr@k3gas.com", "password": "Hr@123"}
EMPLOYEE_CREDS = {"email": "employee@k3gas.com", "password": "Employee@123"}


class TestHRMSUserManagement:
    """HRMS User Management endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup tokens for each test"""
        self.admin_token = self._get_token(ADMIN_CREDS)
        self.hr_admin_token = self._get_token(HR_ADMIN_CREDS)
        self.employee_token = self._get_token(EMPLOYEE_CREDS)
        self.created_user_ids = []
        yield
        # Cleanup: Delete test users created during tests
        for user_id in self.created_user_ids:
            try:
                requests.delete(
                    f"{BASE_URL}/api/hrms/users/{user_id}",
                    headers={"Authorization": f"Bearer {self.admin_token}"}
                )
            except:
                pass
    
    def _get_token(self, creds):
        """Helper to get auth token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json=creds)
        if resp.status_code == 200:
            return resp.json().get("token")
        return None
    
    def _auth_header(self, token):
        return {"Authorization": f"Bearer {token}"}
    
    # ============ GET /api/hrms/users ============
    
    def test_list_users_as_admin(self):
        """Admin can list HRMS users"""
        resp = requests.get(
            f"{BASE_URL}/api/hrms/users",
            headers=self._auth_header(self.admin_token)
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "Response should be a list"
        # Verify response structure for each user
        if len(data) > 0:
            user = data[0]
            assert 'id' in user
            assert 'email' in user
            assert 'name' in user
            assert 'role' in user
            assert user['role'] in ('hr_admin', 'hrms_employee'), f"Role should be hr_admin or hrms_employee, got {user['role']}"
            assert 'is_active' in user
            assert 'created_at' in user
            # Check for linked employee fields
            assert 'linked_employee_name' in user
            assert 'linked_employee_code' in user
            assert 'visible_password' in user
        print(f"✓ Admin can list HRMS users - found {len(data)} users")
    
    def test_list_users_as_hr_admin(self):
        """HR Admin can list HRMS users"""
        resp = requests.get(
            f"{BASE_URL}/api/hrms/users",
            headers=self._auth_header(self.hr_admin_token)
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ HR Admin can list HRMS users - found {len(data)} users")
    
    def test_list_users_as_employee_denied(self):
        """Employee should be denied access to list users (403)"""
        resp = requests.get(
            f"{BASE_URL}/api/hrms/users",
            headers=self._auth_header(self.employee_token)
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("✓ Employee correctly denied access to list users (403)")
    
    def test_list_users_excludes_admin_sales_roles(self):
        """List users should only return hr_admin and hrms_employee roles"""
        resp = requests.get(
            f"{BASE_URL}/api/hrms/users",
            headers=self._auth_header(self.admin_token)
        )
        assert resp.status_code == 200
        data = resp.json()
        for user in data:
            assert user['role'] in ('hr_admin', 'hrms_employee'), f"Found unexpected role: {user['role']}"
        print("✓ List users correctly excludes admin/sales roles")
    
    # ============ POST /api/hrms/users ============
    
    def test_create_user_as_admin(self):
        """Admin can create HRMS user"""
        unique_email = f"test_user_{uuid.uuid4().hex[:8]}@k3gas.com"
        payload = {
            "email": unique_email,
            "password": "Test@123",
            "name": "Test User Admin Created",
            "role": "hrms_employee",
            "linked_employee_id": ""
        }
        resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json=payload,
            headers=self._auth_header(self.admin_token)
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert 'id' in data
        assert 'message' in data
        self.created_user_ids.append(data['id'])
        print(f"✓ Admin can create HRMS user: {unique_email}")
    
    def test_create_user_as_hr_admin(self):
        """HR Admin can create HRMS user"""
        unique_email = f"test_user_{uuid.uuid4().hex[:8]}@k3gas.com"
        payload = {
            "email": unique_email,
            "password": "Test@123",
            "name": "Test User HR Created",
            "role": "hr_admin",
            "linked_employee_id": ""
        }
        resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json=payload,
            headers=self._auth_header(self.hr_admin_token)
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert 'id' in data
        self.created_user_ids.append(data['id'])
        print(f"✓ HR Admin can create HRMS user: {unique_email}")
    
    def test_create_user_as_employee_denied(self):
        """Employee should be denied access to create users (403)"""
        payload = {
            "email": "should_not_create@k3gas.com",
            "password": "Test@123",
            "name": "Should Not Create",
            "role": "hrms_employee"
        }
        resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json=payload,
            headers=self._auth_header(self.employee_token)
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("✓ Employee correctly denied access to create users (403)")
    
    def test_create_user_validates_required_fields(self):
        """Create user should validate required fields"""
        # Missing email
        resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"password": "Test@123", "name": "Test", "role": "hrms_employee"},
            headers=self._auth_header(self.admin_token)
        )
        assert resp.status_code == 400, f"Expected 400 for missing email, got {resp.status_code}"
        
        # Missing password
        resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"email": "test@k3gas.com", "name": "Test", "role": "hrms_employee"},
            headers=self._auth_header(self.admin_token)
        )
        assert resp.status_code == 400, f"Expected 400 for missing password, got {resp.status_code}"
        
        # Missing name
        resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"email": "test@k3gas.com", "password": "Test@123", "role": "hrms_employee"},
            headers=self._auth_header(self.admin_token)
        )
        assert resp.status_code == 400, f"Expected 400 for missing name, got {resp.status_code}"
        
        # Missing role
        resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"email": "test@k3gas.com", "password": "Test@123", "name": "Test"},
            headers=self._auth_header(self.admin_token)
        )
        assert resp.status_code == 400, f"Expected 400 for missing role, got {resp.status_code}"
        print("✓ Create user validates required fields")
    
    def test_create_user_validates_role_constraint(self):
        """Create user should only allow hr_admin or hrms_employee roles"""
        payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@k3gas.com",
            "password": "Test@123",
            "name": "Test Invalid Role",
            "role": "admin"  # Invalid role
        }
        resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json=payload,
            headers=self._auth_header(self.admin_token)
        )
        assert resp.status_code == 400, f"Expected 400 for invalid role, got {resp.status_code}"
        assert "hr_admin or hrms_employee" in resp.json().get('detail', '').lower() or "role" in resp.json().get('detail', '').lower()
        print("✓ Create user validates role constraint (hr_admin/hrms_employee only)")
    
    def test_create_user_validates_duplicate_email(self):
        """Create user should reject duplicate email"""
        # First create a user
        unique_email = f"test_dup_{uuid.uuid4().hex[:8]}@k3gas.com"
        payload = {
            "email": unique_email,
            "password": "Test@123",
            "name": "Test Duplicate",
            "role": "hrms_employee"
        }
        resp1 = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json=payload,
            headers=self._auth_header(self.admin_token)
        )
        assert resp1.status_code == 200
        self.created_user_ids.append(resp1.json()['id'])
        
        # Try to create another with same email
        resp2 = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json=payload,
            headers=self._auth_header(self.admin_token)
        )
        assert resp2.status_code == 400, f"Expected 400 for duplicate email, got {resp2.status_code}"
        assert "email" in resp2.json().get('detail', '').lower() and "exists" in resp2.json().get('detail', '').lower()
        print("✓ Create user validates duplicate email")
    
    def test_create_user_validates_password_length(self):
        """Create user should require min 6 char password"""
        payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@k3gas.com",
            "password": "12345",  # Only 5 chars
            "name": "Test Short Password",
            "role": "hrms_employee"
        }
        resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json=payload,
            headers=self._auth_header(self.admin_token)
        )
        assert resp.status_code == 400, f"Expected 400 for short password, got {resp.status_code}"
        assert "6" in resp.json().get('detail', '') or "password" in resp.json().get('detail', '').lower()
        print("✓ Create user validates password min 6 characters")
    
    def test_create_user_sets_allowed_dashboards_hrms(self):
        """Created HRMS user should have allowed_dashboards=['hrms']"""
        unique_email = f"test_dash_{uuid.uuid4().hex[:8]}@k3gas.com"
        payload = {
            "email": unique_email,
            "password": "Test@123",
            "name": "Test Dashboard Check",
            "role": "hrms_employee"
        }
        resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json=payload,
            headers=self._auth_header(self.admin_token)
        )
        assert resp.status_code == 200
        user_id = resp.json()['id']
        self.created_user_ids.append(user_id)
        
        # Login as the new user and check allowed_dashboards
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": "Test@123"
        })
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        # allowed_dashboards is in the user object
        user_data = login_data.get('user', {})
        assert user_data.get('allowed_dashboards') == ['hrms'], f"Expected ['hrms'], got {user_data.get('allowed_dashboards')}"
        print("✓ Created HRMS user has allowed_dashboards=['hrms']")
    
    # ============ PUT /api/hrms/users/{user_id} ============
    
    def test_update_user_as_admin(self):
        """Admin can update HRMS user"""
        # First create a user
        unique_email = f"test_upd_{uuid.uuid4().hex[:8]}@k3gas.com"
        create_resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"email": unique_email, "password": "Test@123", "name": "Original Name", "role": "hrms_employee"},
            headers=self._auth_header(self.admin_token)
        )
        assert create_resp.status_code == 200
        user_id = create_resp.json()['id']
        self.created_user_ids.append(user_id)
        
        # Update the user
        update_resp = requests.put(
            f"{BASE_URL}/api/hrms/users/{user_id}",
            json={"name": "Updated Name", "role": "hr_admin"},
            headers=self._auth_header(self.admin_token)
        )
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}: {update_resp.text}"
        
        # Verify update by listing users
        list_resp = requests.get(f"{BASE_URL}/api/hrms/users", headers=self._auth_header(self.admin_token))
        users = list_resp.json()
        updated_user = next((u for u in users if u['id'] == user_id), None)
        assert updated_user is not None
        assert updated_user['name'] == "Updated Name"
        assert updated_user['role'] == "hr_admin"
        print("✓ Admin can update HRMS user")
    
    def test_update_user_as_hr_admin(self):
        """HR Admin can update HRMS user"""
        # First create a user
        unique_email = f"test_upd_hr_{uuid.uuid4().hex[:8]}@k3gas.com"
        create_resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"email": unique_email, "password": "Test@123", "name": "HR Update Test", "role": "hrms_employee"},
            headers=self._auth_header(self.admin_token)
        )
        assert create_resp.status_code == 200
        user_id = create_resp.json()['id']
        self.created_user_ids.append(user_id)
        
        # Update as HR Admin
        update_resp = requests.put(
            f"{BASE_URL}/api/hrms/users/{user_id}",
            json={"name": "HR Updated Name"},
            headers=self._auth_header(self.hr_admin_token)
        )
        assert update_resp.status_code == 200, f"Expected 200, got {update_resp.status_code}: {update_resp.text}"
        print("✓ HR Admin can update HRMS user")
    
    def test_update_user_as_employee_denied(self):
        """Employee should be denied access to update users (403)"""
        # Get any existing HRMS user
        list_resp = requests.get(f"{BASE_URL}/api/hrms/users", headers=self._auth_header(self.admin_token))
        users = list_resp.json()
        if len(users) > 0:
            user_id = users[0]['id']
            update_resp = requests.put(
                f"{BASE_URL}/api/hrms/users/{user_id}",
                json={"name": "Should Not Update"},
                headers=self._auth_header(self.employee_token)
            )
            assert update_resp.status_code == 403, f"Expected 403, got {update_resp.status_code}"
        print("✓ Employee correctly denied access to update users (403)")
    
    def test_update_user_validates_duplicate_email(self):
        """Update user should check for duplicate email"""
        # Create two users
        email1 = f"test_dup1_{uuid.uuid4().hex[:8]}@k3gas.com"
        email2 = f"test_dup2_{uuid.uuid4().hex[:8]}@k3gas.com"
        
        resp1 = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"email": email1, "password": "Test@123", "name": "User 1", "role": "hrms_employee"},
            headers=self._auth_header(self.admin_token)
        )
        assert resp1.status_code == 200
        self.created_user_ids.append(resp1.json()['id'])
        
        resp2 = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"email": email2, "password": "Test@123", "name": "User 2", "role": "hrms_employee"},
            headers=self._auth_header(self.admin_token)
        )
        assert resp2.status_code == 200
        user2_id = resp2.json()['id']
        self.created_user_ids.append(user2_id)
        
        # Try to update user2's email to user1's email
        update_resp = requests.put(
            f"{BASE_URL}/api/hrms/users/{user2_id}",
            json={"email": email1},
            headers=self._auth_header(self.admin_token)
        )
        assert update_resp.status_code == 400, f"Expected 400 for duplicate email on update, got {update_resp.status_code}"
        print("✓ Update user validates duplicate email")
    
    # ============ POST /api/hrms/users/{user_id}/reset-password ============
    
    def test_reset_password_as_admin(self):
        """Admin can reset HRMS user password"""
        # Create a user
        unique_email = f"test_pwd_{uuid.uuid4().hex[:8]}@k3gas.com"
        create_resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"email": unique_email, "password": "OldPass123", "name": "Password Test", "role": "hrms_employee"},
            headers=self._auth_header(self.admin_token)
        )
        assert create_resp.status_code == 200
        user_id = create_resp.json()['id']
        self.created_user_ids.append(user_id)
        
        # Reset password
        reset_resp = requests.post(
            f"{BASE_URL}/api/hrms/users/{user_id}/reset-password",
            json={"password": "NewPass456"},
            headers=self._auth_header(self.admin_token)
        )
        assert reset_resp.status_code == 200, f"Expected 200, got {reset_resp.status_code}: {reset_resp.text}"
        
        # Verify new password works
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": "NewPass456"
        })
        assert login_resp.status_code == 200, "New password should work after reset"
        
        # Verify visible_password is updated
        list_resp = requests.get(f"{BASE_URL}/api/hrms/users", headers=self._auth_header(self.admin_token))
        users = list_resp.json()
        user = next((u for u in users if u['id'] == user_id), None)
        assert user is not None
        assert user.get('visible_password') == "NewPass456", f"visible_password should be updated, got {user.get('visible_password')}"
        print("✓ Admin can reset HRMS user password and visible_password is updated")
    
    def test_reset_password_as_hr_admin(self):
        """HR Admin can reset HRMS user password"""
        # Create a user
        unique_email = f"test_pwd_hr_{uuid.uuid4().hex[:8]}@k3gas.com"
        create_resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"email": unique_email, "password": "OldPass123", "name": "HR Password Test", "role": "hrms_employee"},
            headers=self._auth_header(self.admin_token)
        )
        assert create_resp.status_code == 200
        user_id = create_resp.json()['id']
        self.created_user_ids.append(user_id)
        
        # Reset password as HR Admin
        reset_resp = requests.post(
            f"{BASE_URL}/api/hrms/users/{user_id}/reset-password",
            json={"password": "HRReset789"},
            headers=self._auth_header(self.hr_admin_token)
        )
        assert reset_resp.status_code == 200, f"Expected 200, got {reset_resp.status_code}: {reset_resp.text}"
        print("✓ HR Admin can reset HRMS user password")
    
    def test_reset_password_as_employee_denied(self):
        """Employee should be denied access to reset passwords (403)"""
        # Get any existing HRMS user
        list_resp = requests.get(f"{BASE_URL}/api/hrms/users", headers=self._auth_header(self.admin_token))
        users = list_resp.json()
        if len(users) > 0:
            user_id = users[0]['id']
            reset_resp = requests.post(
                f"{BASE_URL}/api/hrms/users/{user_id}/reset-password",
                json={"password": "ShouldNotWork"},
                headers=self._auth_header(self.employee_token)
            )
            assert reset_resp.status_code == 403, f"Expected 403, got {reset_resp.status_code}"
        print("✓ Employee correctly denied access to reset passwords (403)")
    
    def test_reset_password_validates_min_length(self):
        """Reset password should require min 6 characters"""
        # Create a user
        unique_email = f"test_pwd_len_{uuid.uuid4().hex[:8]}@k3gas.com"
        create_resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"email": unique_email, "password": "Test@123", "name": "Password Length Test", "role": "hrms_employee"},
            headers=self._auth_header(self.admin_token)
        )
        assert create_resp.status_code == 200
        user_id = create_resp.json()['id']
        self.created_user_ids.append(user_id)
        
        # Try to reset with short password
        reset_resp = requests.post(
            f"{BASE_URL}/api/hrms/users/{user_id}/reset-password",
            json={"password": "12345"},  # Only 5 chars
            headers=self._auth_header(self.admin_token)
        )
        assert reset_resp.status_code == 400, f"Expected 400 for short password, got {reset_resp.status_code}"
        print("✓ Reset password validates min 6 characters")
    
    # ============ DELETE /api/hrms/users/{user_id} ============
    
    def test_deactivate_user_as_admin(self):
        """Admin can deactivate HRMS user"""
        # Create a user
        unique_email = f"test_del_{uuid.uuid4().hex[:8]}@k3gas.com"
        create_resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"email": unique_email, "password": "Test@123", "name": "Deactivate Test", "role": "hrms_employee"},
            headers=self._auth_header(self.admin_token)
        )
        assert create_resp.status_code == 200
        user_id = create_resp.json()['id']
        self.created_user_ids.append(user_id)
        
        # Deactivate the user
        delete_resp = requests.delete(
            f"{BASE_URL}/api/hrms/users/{user_id}",
            headers=self._auth_header(self.admin_token)
        )
        assert delete_resp.status_code == 200, f"Expected 200, got {delete_resp.status_code}: {delete_resp.text}"
        
        # Verify user is deactivated (is_active=false)
        list_resp = requests.get(f"{BASE_URL}/api/hrms/users", headers=self._auth_header(self.admin_token))
        users = list_resp.json()
        user = next((u for u in users if u['id'] == user_id), None)
        assert user is not None
        assert user.get('is_active') == False, f"User should be deactivated, got is_active={user.get('is_active')}"
        print("✓ Admin can deactivate HRMS user (soft delete)")
    
    def test_deactivate_user_as_hr_admin(self):
        """HR Admin can deactivate HRMS user"""
        # Create a user
        unique_email = f"test_del_hr_{uuid.uuid4().hex[:8]}@k3gas.com"
        create_resp = requests.post(
            f"{BASE_URL}/api/hrms/users",
            json={"email": unique_email, "password": "Test@123", "name": "HR Deactivate Test", "role": "hrms_employee"},
            headers=self._auth_header(self.admin_token)
        )
        assert create_resp.status_code == 200
        user_id = create_resp.json()['id']
        self.created_user_ids.append(user_id)
        
        # Deactivate as HR Admin
        delete_resp = requests.delete(
            f"{BASE_URL}/api/hrms/users/{user_id}",
            headers=self._auth_header(self.hr_admin_token)
        )
        assert delete_resp.status_code == 200, f"Expected 200, got {delete_resp.status_code}: {delete_resp.text}"
        print("✓ HR Admin can deactivate HRMS user")
    
    def test_deactivate_user_as_employee_denied(self):
        """Employee should be denied access to deactivate users (403)"""
        # Get any existing HRMS user
        list_resp = requests.get(f"{BASE_URL}/api/hrms/users", headers=self._auth_header(self.admin_token))
        users = list_resp.json()
        if len(users) > 0:
            user_id = users[0]['id']
            delete_resp = requests.delete(
                f"{BASE_URL}/api/hrms/users/{user_id}",
                headers=self._auth_header(self.employee_token)
            )
            assert delete_resp.status_code == 403, f"Expected 403, got {delete_resp.status_code}"
        print("✓ Employee correctly denied access to deactivate users (403)")
    
    def test_cannot_deactivate_self(self):
        """User cannot deactivate their own account"""
        # Get HR Admin's user ID
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers=self._auth_header(self.hr_admin_token))
        assert me_resp.status_code == 200
        hr_admin_id = me_resp.json().get('id')
        
        # Try to deactivate self
        delete_resp = requests.delete(
            f"{BASE_URL}/api/hrms/users/{hr_admin_id}",
            headers=self._auth_header(self.hr_admin_token)
        )
        assert delete_resp.status_code == 400, f"Expected 400 for self-deactivation, got {delete_resp.status_code}"
        assert "own" in delete_resp.json().get('detail', '').lower() or "self" in delete_resp.json().get('detail', '').lower()
        print("✓ User cannot deactivate their own account")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
