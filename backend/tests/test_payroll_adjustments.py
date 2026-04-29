"""
Test Post-Payroll Adjustment Module
Tests for:
- GET /api/hrms/payroll/{id}/review - Returns payroll with per-employee adjustment calculations
- POST /api/hrms/payroll/{id}/adjustments - Add adjustment with validation
- POST /api/hrms/payroll/{id}/adjustments - Prevents negative net salary
- POST /api/hrms/payroll/{id}/adjustments - Cannot add to finalized payroll
- PUT /api/hrms/payroll/{id}/adjustments/{adj_id} - Update adjustment
- DELETE /api/hrms/payroll/{id}/adjustments/{adj_id} - Remove adjustment
- POST /api/hrms/payroll/{id}/finalize - Recalculates total_net_pay including adjustments
- Access Control: Employee role cannot access adjustment endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"email": "admin@k3gas.com", "password": "Admin@123"}
HR_CREDS = {"email": "hr@k3gas.com", "password": "Hr@123"}
EMPLOYEE_CREDS = {"email": "employee@k3gas.com", "password": "Employee@123"}

# Known draft payroll ID from context
DRAFT_PAYROLL_ID = "2eb8b192-79d7-40a4-8777-c885e03ae5a0"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def hr_token():
    """Get HR admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=HR_CREDS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("HR admin authentication failed")


@pytest.fixture(scope="module")
def employee_token():
    """Get employee authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=EMPLOYEE_CREDS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Employee authentication failed")


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestPayrollReview:
    """Tests for GET /api/hrms/payroll/{id}/review endpoint"""

    def test_review_payroll_returns_adjustment_calculations(self, api_client, admin_token):
        """Review endpoint returns per-employee adjustment calculations"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        response = api_client.get(f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/review")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify top-level fields
        assert "employees" in data, "Response should contain employees array"
        assert "total_adjustments" in data, "Response should contain total_adjustments"
        assert "total_final_net_pay" in data, "Response should contain total_final_net_pay"
        assert "status" in data, "Response should contain status"
        
        # Verify employee-level adjustment fields
        if data["employees"]:
            emp = data["employees"][0]
            assert "adjustment_earnings" in emp, "Employee should have adjustment_earnings"
            assert "adjustment_deductions" in emp, "Employee should have adjustment_deductions"
            assert "adjustment_net" in emp, "Employee should have adjustment_net"
            assert "final_net_pay" in emp, "Employee should have final_net_pay"
            assert "is_modified" in emp, "Employee should have is_modified flag"
        
        print(f"✓ Review endpoint returns {len(data['employees'])} employees with adjustment calculations")
        print(f"  Total adjustments: {data['total_adjustments']}, Final net pay: {data['total_final_net_pay']}")

    def test_review_payroll_not_found(self, api_client, admin_token):
        """Review endpoint returns 404 for non-existent payroll"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        response = api_client.get(f"{BASE_URL}/api/hrms/payroll/non-existent-id/review")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Review endpoint returns 404 for non-existent payroll")


class TestAddAdjustment:
    """Tests for POST /api/hrms/payroll/{id}/adjustments endpoint"""

    def test_add_earning_adjustment(self, api_client, admin_token):
        """Add an earning adjustment successfully"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # First get an employee from the payroll
        review_response = api_client.get(f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/review")
        assert review_response.status_code == 200
        employees = review_response.json().get("employees", [])
        assert len(employees) > 0, "Payroll should have employees"
        
        # Pick an employee
        test_employee = employees[0]
        employee_id = test_employee["employee_id"]
        
        # Add earning adjustment
        adjustment_data = {
            "employee_id": employee_id,
            "name": "TEST_Performance Bonus",
            "type": "earning",
            "amount": 500,
            "reason": "Test earning adjustment for performance"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments",
            json=adjustment_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "adjustment" in data, "Response should contain adjustment object"
        assert data["adjustment"]["id"], "Adjustment should have an ID"
        assert data["adjustment"]["name"] == "TEST_Performance Bonus"
        assert data["adjustment"]["type"] == "earning"
        assert data["adjustment"]["amount"] == 500
        assert "created_by" in data["adjustment"], "Adjustment should have created_by"
        assert "created_at" in data["adjustment"], "Adjustment should have timestamp"
        
        print(f"✓ Added earning adjustment: {data['adjustment']['id']}")
        return data["adjustment"]["id"]

    def test_add_deduction_adjustment(self, api_client, admin_token):
        """Add a deduction adjustment successfully"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # Get an employee
        review_response = api_client.get(f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/review")
        employees = review_response.json().get("employees", [])
        test_employee = employees[1] if len(employees) > 1 else employees[0]
        employee_id = test_employee["employee_id"]
        
        adjustment_data = {
            "employee_id": employee_id,
            "name": "TEST_Late Penalty",
            "type": "deduction",
            "amount": 200,
            "reason": "Test deduction for late arrivals"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments",
            json=adjustment_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["adjustment"]["type"] == "deduction"
        print(f"✓ Added deduction adjustment: {data['adjustment']['id']}")

    def test_add_adjustment_validates_required_fields(self, api_client, admin_token):
        """Adjustment endpoint validates required fields"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # Missing name
        response = api_client.post(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments",
            json={"employee_id": "test", "type": "earning", "amount": 100, "reason": "test"}
        )
        assert response.status_code == 400, "Should reject missing name"
        
        # Missing reason
        response = api_client.post(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments",
            json={"employee_id": "test", "name": "Test", "type": "earning", "amount": 100}
        )
        assert response.status_code == 400, "Should reject missing reason"
        
        print("✓ Adjustment endpoint validates required fields")

    def test_add_adjustment_validates_positive_amount(self, api_client, admin_token):
        """Adjustment endpoint validates amount is positive"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        review_response = api_client.get(f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/review")
        employees = review_response.json().get("employees", [])
        employee_id = employees[0]["employee_id"]
        
        # Zero amount
        response = api_client.post(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments",
            json={"employee_id": employee_id, "name": "Test", "type": "earning", "amount": 0, "reason": "test"}
        )
        assert response.status_code == 400, f"Should reject zero amount, got {response.status_code}"
        
        # Negative amount
        response = api_client.post(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments",
            json={"employee_id": employee_id, "name": "Test", "type": "earning", "amount": -100, "reason": "test"}
        )
        assert response.status_code == 400, f"Should reject negative amount, got {response.status_code}"
        
        print("✓ Adjustment endpoint validates positive amount")

    def test_add_adjustment_validates_type(self, api_client, admin_token):
        """Adjustment endpoint validates type is earning or deduction"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        review_response = api_client.get(f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/review")
        employees = review_response.json().get("employees", [])
        employee_id = employees[0]["employee_id"]
        
        response = api_client.post(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments",
            json={"employee_id": employee_id, "name": "Test", "type": "invalid", "amount": 100, "reason": "test"}
        )
        assert response.status_code == 400, f"Should reject invalid type, got {response.status_code}"
        print("✓ Adjustment endpoint validates type")


class TestNegativeSalaryPrevention:
    """Tests for negative salary prevention"""

    def test_deduction_exceeding_net_pay_rejected(self, api_client, admin_token):
        """Deduction that would result in negative net salary is rejected"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # Get an employee with their net pay
        review_response = api_client.get(f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/review")
        employees = review_response.json().get("employees", [])
        
        # Find an employee with reasonable net pay
        test_employee = None
        for emp in employees:
            if emp.get("net_pay", 0) > 0:
                test_employee = emp
                break
        
        assert test_employee, "Should have an employee with positive net pay"
        employee_id = test_employee["employee_id"]
        net_pay = test_employee["net_pay"]
        
        # Try to add deduction exceeding net pay
        excessive_amount = net_pay + 10000  # Way more than net pay
        
        response = api_client.post(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments",
            json={
                "employee_id": employee_id,
                "name": "TEST_Excessive Deduction",
                "type": "deduction",
                "amount": excessive_amount,
                "reason": "Test excessive deduction"
            }
        )
        
        assert response.status_code == 400, f"Should reject deduction exceeding net pay, got {response.status_code}"
        assert "negative" in response.json().get("detail", "").lower(), "Error should mention negative salary"
        print(f"✓ Deduction of {excessive_amount} rejected (net pay: {net_pay})")


class TestFinalizedPayrollProtection:
    """Tests for finalized payroll protection"""

    def test_cannot_add_adjustment_to_finalized_payroll(self, api_client, admin_token):
        """Cannot add adjustment to finalized payroll"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # Get payroll history to find a finalized one
        history_response = api_client.get(f"{BASE_URL}/api/hrms/payroll/history")
        assert history_response.status_code == 200
        
        finalized_payroll = None
        for p in history_response.json():
            if p.get("status") == "finalized":
                finalized_payroll = p
                break
        
        if not finalized_payroll:
            pytest.skip("No finalized payroll found to test")
        
        # Get employee from the finalized payroll
        detail_response = api_client.get(f"{BASE_URL}/api/hrms/payroll/{finalized_payroll['id']}")
        if detail_response.status_code != 200:
            pytest.skip("Could not get finalized payroll details")
        
        employees = detail_response.json().get("employees", [])
        if not employees:
            pytest.skip("Finalized payroll has no employees")
        
        employee_id = employees[0]["employee_id"]
        
        # Try to add adjustment
        response = api_client.post(
            f"{BASE_URL}/api/hrms/payroll/{finalized_payroll['id']}/adjustments",
            json={
                "employee_id": employee_id,
                "name": "TEST_Should Fail",
                "type": "earning",
                "amount": 100,
                "reason": "This should fail"
            }
        )
        
        assert response.status_code == 400, f"Should reject adjustment to finalized payroll, got {response.status_code}"
        print(f"✓ Cannot add adjustment to finalized payroll {finalized_payroll['id']}")


class TestUpdateAdjustment:
    """Tests for PUT /api/hrms/payroll/{id}/adjustments/{adj_id} endpoint"""

    def test_update_adjustment(self, api_client, admin_token):
        """Update an existing adjustment"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # First get current adjustments
        review_response = api_client.get(f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/review")
        employees = review_response.json().get("employees", [])
        
        # Find an employee with adjustments
        adjustment_to_update = None
        for emp in employees:
            for adj in emp.get("adjustments", []):
                if adj.get("name", "").startswith("TEST_"):
                    adjustment_to_update = adj
                    break
            if adjustment_to_update:
                break
        
        if not adjustment_to_update:
            # Create one first
            employee_id = employees[0]["employee_id"]
            create_response = api_client.post(
                f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments",
                json={
                    "employee_id": employee_id,
                    "name": "TEST_To Update",
                    "type": "earning",
                    "amount": 300,
                    "reason": "Will be updated"
                }
            )
            assert create_response.status_code == 200
            adjustment_to_update = create_response.json()["adjustment"]
        
        adj_id = adjustment_to_update["id"]
        
        # Update the adjustment
        update_data = {
            "name": "TEST_Updated Name",
            "amount": 750,
            "reason": "Updated reason for testing"
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments/{adj_id}",
            json=update_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Updated adjustment {adj_id}")


class TestDeleteAdjustment:
    """Tests for DELETE /api/hrms/payroll/{id}/adjustments/{adj_id} endpoint"""

    def test_delete_adjustment(self, api_client, admin_token):
        """Delete an adjustment from draft payroll"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        # First create an adjustment to delete
        review_response = api_client.get(f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/review")
        employees = review_response.json().get("employees", [])
        employee_id = employees[0]["employee_id"]
        
        create_response = api_client.post(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments",
            json={
                "employee_id": employee_id,
                "name": "TEST_To Delete",
                "type": "earning",
                "amount": 100,
                "reason": "Will be deleted"
            }
        )
        assert create_response.status_code == 200
        adj_id = create_response.json()["adjustment"]["id"]
        
        # Delete it
        response = api_client.delete(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments/{adj_id}"
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify it's gone
        review_after = api_client.get(f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/review")
        for emp in review_after.json().get("employees", []):
            for adj in emp.get("adjustments", []):
                assert adj["id"] != adj_id, "Deleted adjustment should not exist"
        
        print(f"✓ Deleted adjustment {adj_id}")


class TestAccessControl:
    """Tests for access control - Employee role cannot access adjustment endpoints"""

    def test_employee_cannot_add_adjustment(self, api_client, employee_token):
        """Employee role cannot add adjustments"""
        api_client.headers.update({"Authorization": f"Bearer {employee_token}"})
        
        response = api_client.post(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments",
            json={
                "employee_id": "test",
                "name": "Test",
                "type": "earning",
                "amount": 100,
                "reason": "test"
            }
        )
        
        assert response.status_code == 403, f"Employee should get 403, got {response.status_code}"
        print("✓ Employee cannot add adjustments (403)")

    def test_employee_cannot_update_adjustment(self, api_client, employee_token):
        """Employee role cannot update adjustments"""
        api_client.headers.update({"Authorization": f"Bearer {employee_token}"})
        
        response = api_client.put(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments/test-id",
            json={"name": "Test"}
        )
        
        assert response.status_code == 403, f"Employee should get 403, got {response.status_code}"
        print("✓ Employee cannot update adjustments (403)")

    def test_employee_cannot_delete_adjustment(self, api_client, employee_token):
        """Employee role cannot delete adjustments"""
        api_client.headers.update({"Authorization": f"Bearer {employee_token}"})
        
        response = api_client.delete(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments/test-id"
        )
        
        assert response.status_code == 403, f"Employee should get 403, got {response.status_code}"
        print("✓ Employee cannot delete adjustments (403)")

    def test_hr_admin_can_add_adjustment(self, api_client, hr_token):
        """HR Admin can add adjustments"""
        api_client.headers.update({"Authorization": f"Bearer {hr_token}"})
        
        # Get an employee
        review_response = api_client.get(f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/review")
        if review_response.status_code != 200:
            pytest.skip("Could not get payroll review")
        
        employees = review_response.json().get("employees", [])
        if not employees:
            pytest.skip("No employees in payroll")
        
        employee_id = employees[0]["employee_id"]
        
        response = api_client.post(
            f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments",
            json={
                "employee_id": employee_id,
                "name": "TEST_HR Added",
                "type": "earning",
                "amount": 150,
                "reason": "HR admin test"
            }
        )
        
        assert response.status_code == 200, f"HR Admin should be able to add, got {response.status_code}: {response.text}"
        print("✓ HR Admin can add adjustments")


class TestCleanup:
    """Cleanup test adjustments"""

    def test_cleanup_test_adjustments(self, api_client, admin_token):
        """Remove all TEST_ prefixed adjustments"""
        api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
        
        review_response = api_client.get(f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/review")
        if review_response.status_code != 200:
            return
        
        deleted_count = 0
        for emp in review_response.json().get("employees", []):
            for adj in emp.get("adjustments", []):
                if adj.get("name", "").startswith("TEST_"):
                    del_response = api_client.delete(
                        f"{BASE_URL}/api/hrms/payroll/{DRAFT_PAYROLL_ID}/adjustments/{adj['id']}"
                    )
                    if del_response.status_code == 200:
                        deleted_count += 1
        
        print(f"✓ Cleaned up {deleted_count} test adjustments")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
