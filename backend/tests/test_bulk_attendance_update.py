"""
Test Bulk Attendance Update Feature
- POST /api/hrms/attendance/bulk-update/preview
- POST /api/hrms/attendance/bulk-update/apply
- POST /api/hrms/attendance/bulk-update/undo
- GET /api/hrms/attendance/bulk-update/logs
- Access control tests
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"email": "admin@k3gas.com", "password": "Admin@123"}
HR_CREDS = {"email": "hr@k3gas.com", "password": "Hr@123"}
EMPLOYEE_CREDS = {"email": "employee@k3gas.com", "password": "Employee@123"}


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    res = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    if res.status_code == 200:
        return res.json().get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def hr_token():
    """Get HR admin auth token"""
    res = requests.post(f"{BASE_URL}/api/auth/login", json=HR_CREDS)
    if res.status_code == 200:
        return res.json().get("token")
    pytest.skip("HR authentication failed")


@pytest.fixture(scope="module")
def employee_token():
    """Get employee auth token"""
    res = requests.post(f"{BASE_URL}/api/auth/login", json=EMPLOYEE_CREDS)
    if res.status_code == 200:
        return res.json().get("token")
    pytest.skip("Employee authentication failed")


@pytest.fixture(scope="module")
def test_employees(admin_token):
    """Get list of active employees for testing"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = requests.get(f"{BASE_URL}/api/hrms/employees?limit=10", headers=headers)
    if res.status_code == 200:
        employees = res.data if isinstance(res.json(), list) else res.json().get("employees", [])
        active_emps = [e for e in employees if e.get("is_active", True)]
        if len(active_emps) >= 2:
            return active_emps[:2]
    pytest.skip("Could not fetch test employees")


class TestBulkUpdatePreview:
    """Tests for POST /api/hrms/attendance/bulk-update/preview"""

    def test_preview_returns_expected_fields(self, admin_token, test_employees):
        """Preview should return preview array, total_changes, locked_count, biometric_overrides"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = {
            "employee_ids": [test_employees[0]["id"]],
            "dates": ["2026-01-15"],
            "status": "present"
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/preview", json=payload, headers=headers)
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        # Verify response structure
        assert "preview" in data, "Response should contain 'preview' array"
        assert "total_changes" in data, "Response should contain 'total_changes'"
        assert "locked_count" in data, "Response should contain 'locked_count'"
        assert "biometric_overrides" in data, "Response should contain 'biometric_overrides'"
        
        # Verify preview item structure
        if len(data["preview"]) > 0:
            item = data["preview"][0]
            assert "employee_id" in item
            assert "employee_name" in item
            assert "date" in item
            assert "old_status" in item
            assert "new_status" in item
            assert "is_locked" in item

    def test_preview_multiple_employees_dates(self, admin_token, test_employees):
        """Preview should handle multiple employees and dates"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = {
            "employee_ids": [e["id"] for e in test_employees],
            "dates": ["2026-01-15", "2026-01-16"],
            "status": "absent"
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/preview", json=payload, headers=headers)
        
        assert res.status_code == 200
        data = res.json()
        
        # Should have entries for each employee x date combination
        expected_count = len(test_employees) * 2  # 2 dates
        assert len(data["preview"]) == expected_count, f"Expected {expected_count} preview items"

    def test_preview_requires_employees(self, admin_token):
        """Preview should return 400 if no employees selected"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = {
            "employee_ids": [],
            "dates": ["2026-01-15"],
            "status": "present"
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/preview", json=payload, headers=headers)
        
        assert res.status_code == 400
        assert "employee" in res.json().get("detail", "").lower()

    def test_preview_requires_dates(self, admin_token, test_employees):
        """Preview should return 400 if no dates selected"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = {
            "employee_ids": [test_employees[0]["id"]],
            "dates": [],
            "status": "present"
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/preview", json=payload, headers=headers)
        
        assert res.status_code == 400
        assert "date" in res.json().get("detail", "").lower()


class TestBulkUpdateApply:
    """Tests for POST /api/hrms/attendance/bulk-update/apply"""

    def test_apply_creates_attendance_records(self, admin_token, test_employees):
        """Apply should create/update attendance records and return counts"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        test_date = "2026-01-20"  # Use a unique date for testing
        
        payload = {
            "entries": [
                {"employee_id": test_employees[0]["id"], "date": test_date, "status": "present"},
            ],
            "reason": "TEST_bulk_update_apply_test"
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/apply", json=payload, headers=headers)
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        # Verify response structure
        assert "message" in data
        assert "created" in data or "updated" in data
        assert "skipped" in data
        assert "log_id" in data
        
        # Verify log_id is returned for undo functionality
        assert data["log_id"] is not None, "log_id should be returned for undo"

    def test_apply_requires_reason(self, admin_token, test_employees):
        """Apply should return 400 if reason is missing"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = {
            "entries": [
                {"employee_id": test_employees[0]["id"], "date": "2026-01-21", "status": "present"},
            ],
            "reason": ""  # Empty reason
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/apply", json=payload, headers=headers)
        
        assert res.status_code == 400, f"Expected 400 for missing reason, got {res.status_code}"
        assert "reason" in res.json().get("detail", "").lower()

    def test_apply_requires_reason_missing_field(self, admin_token, test_employees):
        """Apply should return 400 if reason field is not provided"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = {
            "entries": [
                {"employee_id": test_employees[0]["id"], "date": "2026-01-21", "status": "present"},
            ]
            # No reason field at all
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/apply", json=payload, headers=headers)
        
        assert res.status_code == 400, f"Expected 400 for missing reason, got {res.status_code}"

    def test_apply_validates_status(self, admin_token, test_employees):
        """Apply should skip entries with invalid status"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = {
            "entries": [
                {"employee_id": test_employees[0]["id"], "date": "2026-01-22", "status": "invalid_status"},
            ],
            "reason": "TEST_invalid_status_test"
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/apply", json=payload, headers=headers)
        
        assert res.status_code == 200
        data = res.json()
        # Invalid status should be skipped
        assert data.get("skipped", 0) >= 1

    def test_apply_with_leave_type(self, admin_token, test_employees):
        """Apply should handle leave status with leave_type"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        payload = {
            "entries": [
                {"employee_id": test_employees[0]["id"], "date": "2026-01-23", "status": "leave", "leave_type": "casual"},
            ],
            "reason": "TEST_leave_type_test"
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/apply", json=payload, headers=headers)
        
        assert res.status_code == 200
        data = res.json()
        assert data.get("created", 0) + data.get("updated", 0) >= 1


class TestBulkUpdateUndo:
    """Tests for POST /api/hrms/attendance/bulk-update/undo"""

    def test_undo_reverts_changes(self, admin_token, test_employees):
        """Undo should revert bulk update changes"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        test_date = "2026-01-24"
        
        # First, apply a bulk update
        apply_payload = {
            "entries": [
                {"employee_id": test_employees[0]["id"], "date": test_date, "status": "absent"},
            ],
            "reason": "TEST_undo_test_apply"
        }
        apply_res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/apply", json=apply_payload, headers=headers)
        assert apply_res.status_code == 200
        log_id = apply_res.json().get("log_id")
        assert log_id is not None
        
        # Now undo it
        undo_payload = {"log_id": log_id}
        undo_res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/undo", json=undo_payload, headers=headers)
        
        assert undo_res.status_code == 200, f"Expected 200, got {undo_res.status_code}: {undo_res.text}"
        data = undo_res.json()
        assert "message" in data
        assert "reverted" in data["message"].lower() or "undone" in data["message"].lower()

    def test_undo_double_undo_fails(self, admin_token, test_employees):
        """Double undo should return error"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        test_date = "2026-01-25"
        
        # Apply a bulk update
        apply_payload = {
            "entries": [
                {"employee_id": test_employees[0]["id"], "date": test_date, "status": "half_day"},
            ],
            "reason": "TEST_double_undo_test"
        }
        apply_res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/apply", json=apply_payload, headers=headers)
        assert apply_res.status_code == 200
        log_id = apply_res.json().get("log_id")
        
        # First undo - should succeed
        undo_res1 = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/undo", json={"log_id": log_id}, headers=headers)
        assert undo_res1.status_code == 200
        
        # Second undo - should fail
        undo_res2 = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/undo", json={"log_id": log_id}, headers=headers)
        assert undo_res2.status_code == 400, f"Expected 400 for double undo, got {undo_res2.status_code}"
        assert "already" in undo_res2.json().get("detail", "").lower()

    def test_undo_invalid_log_id(self, admin_token):
        """Undo with invalid log_id should return 404"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        undo_payload = {"log_id": "non-existent-log-id-12345"}
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/undo", json=undo_payload, headers=headers)
        
        assert res.status_code == 404

    def test_undo_requires_log_id(self, admin_token):
        """Undo should return 400 if log_id is missing"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/undo", json={}, headers=headers)
        
        assert res.status_code == 400


class TestBulkUpdateLogs:
    """Tests for GET /api/hrms/attendance/bulk-update/logs"""

    def test_logs_returns_list(self, admin_token):
        """Logs endpoint should return list of bulk update logs"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        res = requests.get(f"{BASE_URL}/api/hrms/attendance/bulk-update/logs", headers=headers)
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        assert isinstance(data, list), "Response should be a list"
        
        # If there are logs, verify structure
        if len(data) > 0:
            log = data[0]
            assert "id" in log
            assert "type" in log
            assert "updated_by" in log
            assert "reason" in log
            assert "created_at" in log

    def test_logs_hr_admin_access(self, hr_token):
        """HR Admin should be able to access logs"""
        headers = {"Authorization": f"Bearer {hr_token}"}
        res = requests.get(f"{BASE_URL}/api/hrms/attendance/bulk-update/logs", headers=headers)
        
        assert res.status_code == 200


class TestAccessControl:
    """Access control tests - Employee role should not access bulk-update endpoints"""

    def test_employee_cannot_preview(self, employee_token, test_employees):
        """Employee should get 403 on preview endpoint"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        payload = {
            "employee_ids": [test_employees[0]["id"]] if test_employees else ["dummy-id"],
            "dates": ["2026-01-15"],
            "status": "present"
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/preview", json=payload, headers=headers)
        
        assert res.status_code == 403, f"Expected 403 for employee, got {res.status_code}"

    def test_employee_cannot_apply(self, employee_token, test_employees):
        """Employee should get 403 on apply endpoint"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        payload = {
            "entries": [{"employee_id": "dummy", "date": "2026-01-15", "status": "present"}],
            "reason": "test"
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/apply", json=payload, headers=headers)
        
        assert res.status_code == 403, f"Expected 403 for employee, got {res.status_code}"

    def test_employee_cannot_undo(self, employee_token):
        """Employee should get 403 on undo endpoint"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/undo", json={"log_id": "test"}, headers=headers)
        
        assert res.status_code == 403, f"Expected 403 for employee, got {res.status_code}"

    def test_employee_cannot_view_logs(self, employee_token):
        """Employee should get 403 on logs endpoint"""
        headers = {"Authorization": f"Bearer {employee_token}"}
        res = requests.get(f"{BASE_URL}/api/hrms/attendance/bulk-update/logs", headers=headers)
        
        assert res.status_code == 403, f"Expected 403 for employee, got {res.status_code}"


class TestHRAdminAccess:
    """HR Admin should have full access to bulk-update endpoints"""

    def test_hr_admin_can_preview(self, hr_token, test_employees):
        """HR Admin should be able to preview"""
        headers = {"Authorization": f"Bearer {hr_token}"}
        payload = {
            "employee_ids": [test_employees[0]["id"]],
            "dates": ["2026-01-26"],
            "status": "present"
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/preview", json=payload, headers=headers)
        
        assert res.status_code == 200

    def test_hr_admin_can_apply(self, hr_token, test_employees):
        """HR Admin should be able to apply bulk updates"""
        headers = {"Authorization": f"Bearer {hr_token}"}
        payload = {
            "entries": [
                {"employee_id": test_employees[0]["id"], "date": "2026-01-27", "status": "present"},
            ],
            "reason": "TEST_hr_admin_apply"
        }
        res = requests.post(f"{BASE_URL}/api/hrms/attendance/bulk-update/apply", json=payload, headers=headers)
        
        assert res.status_code == 200
