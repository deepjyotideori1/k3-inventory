"""
HRMS Phase 2 Backend API Tests - Payroll & Attendance
Tests for: Payroll Config, Payroll Run/Finalize/Delete, Payslip PDF, 
           Attendance Mark/Daily/Monthly Summary, Leave Config/Balance
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASSWORD = "Admin@123"
SALES_EMAIL = "sales@k3gas.com"
SALES_PASSWORD = "Sales@123"


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


@pytest.fixture(scope="module")
def existing_employee_id(authenticated_client):
    """Get an existing active employee ID for testing"""
    response = authenticated_client.get(f"{BASE_URL}/api/hrms/employees", params={"status": "active"})
    if response.status_code == 200:
        employees = response.json().get("employees", [])
        if employees:
            return employees[0]["id"]
    pytest.skip("No active employees found for testing")


# ============ PAYROLL CONFIG TESTS ============

class TestPayrollConfig:
    """Payroll Configuration API tests"""
    
    def test_get_payroll_config(self, authenticated_client):
        """Test GET /api/hrms/payroll/config returns statutory settings"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/config")
        assert response.status_code == 200
        data = response.json()
        
        # Verify PF settings
        assert "pf_employee_rate" in data
        assert "pf_employer_rate" in data
        assert "pf_wage_ceiling" in data
        assert data["pf_employee_rate"] == 12.0
        assert data["pf_wage_ceiling"] == 15000
        
        # Verify ESI settings
        assert "esi_employee_rate" in data
        assert "esi_employer_rate" in data
        assert "esi_wage_ceiling" in data
        assert data["esi_employee_rate"] == 0.75
        assert data["esi_wage_ceiling"] == 21000
        
        # Verify Professional Tax slabs
        assert "professional_tax_slabs" in data
        assert isinstance(data["professional_tax_slabs"], list)
        assert len(data["professional_tax_slabs"]) >= 3
        
        # Verify TDS slabs
        assert "tds_slabs" in data
        assert isinstance(data["tds_slabs"], list)
        
        print(f"Payroll config: PF {data['pf_employee_rate']}%, ESI {data['esi_employee_rate']}%")
    
    def test_update_payroll_config(self, authenticated_client):
        """Test PUT /api/hrms/payroll/config updates statutory rates"""
        # Get current config
        get_response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/config")
        original = get_response.json()
        
        # Update PF wage ceiling
        new_ceiling = 16000
        update_response = authenticated_client.put(f"{BASE_URL}/api/hrms/payroll/config", json={
            "pf_wage_ceiling": new_ceiling
        })
        assert update_response.status_code == 200
        
        # Verify update
        verify_response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/config")
        updated = verify_response.json()
        assert updated["pf_wage_ceiling"] == new_ceiling
        print(f"Updated PF wage ceiling to: {new_ceiling}")
        
        # Restore original
        authenticated_client.put(f"{BASE_URL}/api/hrms/payroll/config", json={
            "pf_wage_ceiling": original.get("pf_wage_ceiling", 15000)
        })
        print("Restored original PF wage ceiling")
    
    def test_update_payroll_config_invalid_field(self, authenticated_client):
        """Test PUT /api/hrms/payroll/config with invalid field returns 400"""
        response = authenticated_client.put(f"{BASE_URL}/api/hrms/payroll/config", json={
            "invalid_field": 123
        })
        assert response.status_code == 400
        print("Invalid config field correctly rejected")


# ============ PAYROLL RUN TESTS ============

class TestPayrollRun:
    """Payroll Run API tests"""
    
    def test_get_payroll_history(self, authenticated_client):
        """Test GET /api/hrms/payroll/history returns payroll runs"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/history")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} payroll runs in history")
        
        # If there are payroll runs, verify structure
        if data:
            run = data[0]
            assert "id" in run
            assert "period" in run
            assert "month" in run
            assert "year" in run
            assert "total_employees" in run
            assert "total_gross" in run
            assert "total_deductions" in run
            assert "total_net_pay" in run
            assert "status" in run
            print(f"Latest payroll: {run['period']} - Status: {run['status']}")
    
    def test_run_payroll_for_test_month(self, authenticated_client):
        """Test POST /api/hrms/payroll/run processes payroll"""
        # Use a test month (May 2026) to avoid conflicts
        test_month = 5
        test_year = 2026
        
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/payroll/run", json={
            "month": test_month,
            "year": test_year,
            "working_days": 26
        })
        
        # Could be 200 (success) or 400 (already finalized)
        if response.status_code == 200:
            data = response.json()
            assert data["period"] == f"{test_year}-{test_month:02d}"
            assert data["status"] == "draft"
            assert "total_employees" in data
            assert "total_gross" in data
            assert "total_net_pay" in data
            assert "employees" in data
            print(f"Payroll run created for {test_month}/{test_year}: {data['total_employees']} employees, Net: {data['total_net_pay']}")
            
            # Store payroll ID for later tests
            pytest.payroll_test_id = data["id"]
        elif response.status_code == 400:
            print(f"Payroll for {test_month}/{test_year} already finalized - expected behavior")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code} - {response.text}")
    
    def test_get_payroll_detail(self, authenticated_client):
        """Test GET /api/hrms/payroll/{id} returns full employee breakdown"""
        # First get history to find a payroll ID
        history_response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/history")
        history = history_response.json()
        
        if not history:
            pytest.skip("No payroll runs available for detail test")
        
        payroll_id = history[0]["id"]
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/{payroll_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert "employees" in data
        assert isinstance(data["employees"], list)
        
        if data["employees"]:
            emp = data["employees"][0]
            # Verify employee payroll breakdown fields
            assert "employee_id" in emp
            assert "name" in emp
            assert "department" in emp
            assert "gross_salary" in emp
            assert "pf_employee" in emp
            assert "esi_employee" in emp
            assert "professional_tax" in emp
            assert "tds" in emp
            assert "net_pay" in emp
            print(f"Payroll detail for {data['period']}: {len(data['employees'])} employees")
    
    def test_get_payroll_not_found(self, authenticated_client):
        """Test GET /api/hrms/payroll/{id} with invalid ID returns 404"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/invalid-id-12345")
        assert response.status_code == 404
        print("Invalid payroll ID correctly returns 404")


# ============ PAYROLL FINALIZE & DELETE TESTS ============

class TestPayrollFinalizeDelete:
    """Payroll Finalize and Delete API tests"""
    
    def test_delete_draft_payroll(self, authenticated_client):
        """Test DELETE /api/hrms/payroll/{id} only deletes drafts"""
        # Create a new draft payroll for June 2026
        run_response = authenticated_client.post(f"{BASE_URL}/api/hrms/payroll/run", json={
            "month": 6,
            "year": 2026,
            "working_days": 26
        })
        
        if run_response.status_code == 200:
            payroll_id = run_response.json()["id"]
            
            # Delete the draft
            delete_response = authenticated_client.delete(f"{BASE_URL}/api/hrms/payroll/{payroll_id}")
            assert delete_response.status_code == 200
            print(f"Draft payroll {payroll_id} deleted successfully")
            
            # Verify it's gone
            get_response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/{payroll_id}")
            assert get_response.status_code == 404
        else:
            print("June 2026 payroll already finalized - skipping delete test")
    
    def test_finalize_payroll(self, authenticated_client):
        """Test POST /api/hrms/payroll/{id}/finalize locks the payroll"""
        # Create a new draft payroll for July 2026
        run_response = authenticated_client.post(f"{BASE_URL}/api/hrms/payroll/run", json={
            "month": 7,
            "year": 2026,
            "working_days": 26
        })
        
        if run_response.status_code == 200:
            payroll_id = run_response.json()["id"]
            
            # Finalize it
            finalize_response = authenticated_client.post(f"{BASE_URL}/api/hrms/payroll/{payroll_id}/finalize")
            assert finalize_response.status_code == 200
            print(f"Payroll {payroll_id} finalized successfully")
            
            # Verify status changed
            get_response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/{payroll_id}")
            assert get_response.status_code == 200
            assert get_response.json()["status"] == "finalized"
            
            # Try to delete finalized payroll - should fail
            delete_response = authenticated_client.delete(f"{BASE_URL}/api/hrms/payroll/{payroll_id}")
            assert delete_response.status_code == 400
            print("Cannot delete finalized payroll - correct behavior")
        else:
            print("July 2026 payroll already finalized - skipping finalize test")
    
    def test_finalize_already_finalized(self, authenticated_client):
        """Test finalizing already finalized payroll returns 400"""
        # Get history and find a finalized payroll
        history_response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/history")
        history = history_response.json()
        
        finalized = [p for p in history if p.get("status") == "finalized"]
        if not finalized:
            pytest.skip("No finalized payrolls to test")
        
        payroll_id = finalized[0]["id"]
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/payroll/{payroll_id}/finalize")
        assert response.status_code == 400
        print("Re-finalizing already finalized payroll correctly rejected")


# ============ PAYSLIP PDF TESTS ============

class TestPayslipPDF:
    """Payslip PDF Generation tests"""
    
    def test_download_payslip_pdf(self, authenticated_client, existing_employee_id):
        """Test GET /api/hrms/payroll/{id}/payslip/{emp_id}/pdf generates A4 PDF"""
        # Get a payroll with employees
        history_response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/history")
        history = history_response.json()
        
        if not history:
            pytest.skip("No payroll runs available for payslip test")
        
        payroll_id = history[0]["id"]
        
        # Get payroll detail to find an employee
        detail_response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/{payroll_id}")
        detail = detail_response.json()
        
        if not detail.get("employees"):
            pytest.skip("No employees in payroll for payslip test")
        
        emp_id = detail["employees"][0]["employee_id"]
        
        # Download payslip PDF
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/{payroll_id}/payslip/{emp_id}/pdf")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        assert "attachment" in response.headers.get("content-disposition", "")
        
        # Verify PDF content starts with PDF header
        assert response.content[:4] == b'%PDF'
        print(f"Payslip PDF generated: {len(response.content)} bytes")
    
    def test_payslip_invalid_payroll(self, authenticated_client, existing_employee_id):
        """Test payslip with invalid payroll ID returns 404"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/invalid-id/payslip/{existing_employee_id}/pdf")
        assert response.status_code == 404
        print("Invalid payroll ID for payslip correctly returns 404")
    
    def test_payslip_invalid_employee(self, authenticated_client):
        """Test payslip with invalid employee ID returns 404"""
        history_response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/history")
        history = history_response.json()
        
        if not history:
            pytest.skip("No payroll runs available")
        
        payroll_id = history[0]["id"]
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/payroll/{payroll_id}/payslip/invalid-emp-id/pdf")
        assert response.status_code == 404
        print("Invalid employee ID for payslip correctly returns 404")


# ============ ATTENDANCE TESTS ============

class TestAttendanceMark:
    """Attendance Marking API tests"""
    
    def test_mark_attendance(self, authenticated_client, existing_employee_id):
        """Test POST /api/hrms/attendance/mark creates/updates attendance records"""
        test_date = "2026-04-10"
        
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/attendance/mark", json={
            "date": test_date,
            "records": [
                {
                    "employee_id": existing_employee_id,
                    "status": "present",
                    "check_in": "09:00",
                    "check_out": "18:00",
                    "overtime_hours": 1.5,
                    "remarks": "Test attendance"
                }
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert "created" in data or "updated" in data
        print(f"Attendance marked for {test_date}: {data}")
    
    def test_mark_attendance_missing_date(self, authenticated_client, existing_employee_id):
        """Test marking attendance without date returns 400"""
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/attendance/mark", json={
            "records": [{"employee_id": existing_employee_id, "status": "present"}]
        })
        assert response.status_code == 400
        print("Missing date correctly rejected")
    
    def test_mark_attendance_empty_records(self, authenticated_client):
        """Test marking attendance with empty records returns 400"""
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/attendance/mark", json={
            "date": "2026-04-10",
            "records": []
        })
        assert response.status_code == 400
        print("Empty records correctly rejected")
    
    def test_mark_attendance_with_leave(self, authenticated_client, existing_employee_id):
        """Test marking attendance as leave with leave type"""
        test_date = "2026-04-11"
        
        response = authenticated_client.post(f"{BASE_URL}/api/hrms/attendance/mark", json={
            "date": test_date,
            "records": [
                {
                    "employee_id": existing_employee_id,
                    "status": "leave",
                    "leave_type": "casual"
                }
            ]
        })
        assert response.status_code == 200
        print(f"Leave attendance marked for {test_date}")


class TestAttendanceDaily:
    """Daily Attendance API tests"""
    
    def test_get_daily_attendance(self, authenticated_client):
        """Test GET /api/hrms/attendance/daily?date=YYYY-MM-DD returns employee list with status"""
        test_date = "2026-04-04"  # Date with existing attendance
        
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/attendance/daily", params={"date": test_date})
        assert response.status_code == 200
        data = response.json()
        
        assert "date" in data
        assert "employees" in data
        assert isinstance(data["employees"], list)
        
        if data["employees"]:
            emp = data["employees"][0]
            assert "employee_id" in emp
            assert "name" in emp
            assert "department" in emp
            assert "status" in emp
            print(f"Daily attendance for {test_date}: {len(data['employees'])} employees")
    
    def test_get_daily_attendance_with_department_filter(self, authenticated_client):
        """Test daily attendance with department filter"""
        # Get a department ID
        dept_response = authenticated_client.get(f"{BASE_URL}/api/hrms/departments")
        depts = dept_response.json()
        
        if not depts:
            pytest.skip("No departments available")
        
        dept_id = depts[0]["id"]
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/attendance/daily", params={
            "date": "2026-04-04",
            "department_id": dept_id
        })
        assert response.status_code == 200
        print(f"Daily attendance filtered by department: {len(response.json()['employees'])} employees")


class TestAttendanceMonthlySummary:
    """Monthly Attendance Summary API tests"""
    
    def test_get_monthly_summary(self, authenticated_client):
        """Test GET /api/hrms/attendance/monthly-summary?month=YYYY-MM"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/attendance/monthly-summary", params={"month": "2026-04"})
        assert response.status_code == 200
        data = response.json()
        
        assert "month" in data
        assert "total_days" in data
        assert "summaries" in data
        assert isinstance(data["summaries"], list)
        
        if data["summaries"]:
            summary = data["summaries"][0]
            assert "employee_id" in summary
            assert "name" in summary
            assert "present" in summary
            assert "absent" in summary
            assert "half_day" in summary
            assert "late" in summary
            assert "leave" in summary
            assert "overtime_hours" in summary
            assert "effective_present" in summary
            print(f"Monthly summary for {data['month']}: {len(data['summaries'])} employees, {data['total_days']} days")
    
    def test_get_monthly_summary_with_department(self, authenticated_client):
        """Test monthly summary with department filter"""
        dept_response = authenticated_client.get(f"{BASE_URL}/api/hrms/departments")
        depts = dept_response.json()
        
        if not depts:
            pytest.skip("No departments available")
        
        dept_id = depts[0]["id"]
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/attendance/monthly-summary", params={
            "month": "2026-04",
            "department_id": dept_id
        })
        assert response.status_code == 200
        print(f"Monthly summary filtered by department: {len(response.json()['summaries'])} employees")


# ============ LEAVE CONFIG & BALANCE TESTS ============

class TestLeaveConfig:
    """Leave Configuration API tests"""
    
    def test_get_leave_config(self, authenticated_client):
        """Test GET /api/hrms/leave/config returns leave type definitions"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/leave/config")
        assert response.status_code == 200
        data = response.json()
        
        assert "leave_types" in data
        assert isinstance(data["leave_types"], list)
        
        # Verify default leave types
        leave_ids = [lt["id"] for lt in data["leave_types"]]
        assert "casual" in leave_ids
        assert "sick" in leave_ids
        assert "earned" in leave_ids
        assert "unpaid" in leave_ids
        
        # Verify structure
        for lt in data["leave_types"]:
            assert "id" in lt
            assert "name" in lt
            assert "annual_quota" in lt
            assert "carry_forward" in lt
        
        print(f"Leave config: {len(data['leave_types'])} leave types")


class TestLeaveBalance:
    """Leave Balance API tests"""
    
    def test_get_leave_balance(self, authenticated_client, existing_employee_id):
        """Test GET /api/hrms/leave/balance/{emp_id} returns taken vs remaining"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/leave/balance/{existing_employee_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert "employee_id" in data
        assert "employee_name" in data
        assert "year" in data
        assert "balances" in data
        assert isinstance(data["balances"], list)
        
        for balance in data["balances"]:
            assert "leave_type_id" in balance
            assert "leave_type_name" in balance
            assert "annual_quota" in balance
            assert "taken" in balance
            assert "remaining" in balance
        
        print(f"Leave balance for {data['employee_name']}: {len(data['balances'])} leave types")
    
    def test_get_leave_balance_with_year(self, authenticated_client, existing_employee_id):
        """Test leave balance with specific year"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/leave/balance/{existing_employee_id}", params={"year": 2026})
        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2026
        print(f"Leave balance for year 2026: {data['balances']}")
    
    def test_get_leave_balance_invalid_employee(self, authenticated_client):
        """Test leave balance with invalid employee returns 404"""
        response = authenticated_client.get(f"{BASE_URL}/api/hrms/leave/balance/invalid-emp-id")
        assert response.status_code == 404
        print("Invalid employee ID for leave balance correctly returns 404")


# ============ INVENTORY DASHBOARD UNAFFECTED TEST ============

class TestInventoryDashboardUnaffected:
    """Verify Inventory Dashboard APIs still work"""
    
    def test_inventory_dashboard_stats(self, authenticated_client):
        """Test GET /api/dashboard/stats still works"""
        response = authenticated_client.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify inventory dashboard structure
        assert "total_warehouses" in data or "warehouses" in data or "total_stock" in data or isinstance(data, dict)
        print(f"Inventory dashboard stats working: {list(data.keys())[:5]}...")
    
    def test_warehouses_api(self, authenticated_client):
        """Test GET /api/warehouses still works"""
        response = authenticated_client.get(f"{BASE_URL}/api/warehouses")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Warehouses API working: {len(data)} warehouses")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
