"""
Test HRMS Attendance Features:
1. Employee Overview endpoint (GET /api/hrms/attendance/employee-overview)
2. Biometric Sync endpoint (POST /api/hrms/attendance/biometric-sync)
3. Attendance with date range (GET /api/hrms/attendance with start_date/end_date)
4. Employee-wise PDF export (GET /api/hrms/reports/attendance-employee/pdf)
5. Employee-wise Excel export (GET /api/hrms/reports/attendance-employee/excel)
6. Daily attendance endpoint (GET /api/hrms/attendance/daily)
7. Monthly summary endpoint (GET /api/hrms/attendance/monthly-summary)
8. Monthly summary PDF/Excel exports
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHRMSAttendanceFeatures:
    """Test new HRMS Attendance features - Employee Overview, Biometric Sync, Exports"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
        else:
            pytest.skip("Authentication failed - skipping tests")
        
        # Get an employee ID for testing
        emp_response = self.session.get(f"{BASE_URL}/api/hrms/employees", params={"limit": 5})
        if emp_response.status_code == 200:
            employees = emp_response.json().get("employees", [])
            if employees:
                self.test_employee_id = employees[0]["id"]
                self.test_employee_code = employees[0].get("employee_id", "K3-0001")
                self.test_employee_name = employees[0].get("name", "Test Employee")
            else:
                pytest.skip("No employees found")
        else:
            pytest.skip("Failed to fetch employees")
    
    # ============ EMPLOYEE OVERVIEW ENDPOINT TESTS ============
    
    def test_employee_overview_success(self):
        """Test GET /api/hrms/attendance/employee-overview returns correct data"""
        response = self.session.get(f"{BASE_URL}/api/hrms/attendance/employee-overview", params={
            "employee_id": self.test_employee_id,
            "start_date": "2026-01-01",
            "end_date": "2026-04-04"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "employee" in data, "Response should contain 'employee' field"
        assert "date_range" in data, "Response should contain 'date_range' field"
        assert "summary" in data, "Response should contain 'summary' field"
        assert "records" in data, "Response should contain 'records' field"
        
        # Verify employee info
        assert data["employee"]["id"] == self.test_employee_id
        assert "name" in data["employee"]
        assert "employee_code" in data["employee"]
        assert "department" in data["employee"]
        
        # Verify date range
        assert data["date_range"]["start"] == "2026-01-01"
        assert data["date_range"]["end"] == "2026-04-04"
        
        # Verify summary fields
        summary = data["summary"]
        assert "total_records" in summary
        assert "present" in summary
        assert "absent" in summary
        assert "half_day" in summary
        assert "late" in summary
        assert "leave" in summary
        assert "holiday" in summary
        assert "week_off" in summary
        assert "overtime_hours" in summary
        assert "effective_present" in summary
        assert "leave_breakdown" in summary
        
        print(f"✓ Employee Overview: {data['employee']['name']} - {summary['total_records']} records, {summary['present']} present, {summary['effective_present']} effective")
    
    def test_employee_overview_invalid_employee(self):
        """Test employee overview with invalid employee ID returns 404"""
        response = self.session.get(f"{BASE_URL}/api/hrms/attendance/employee-overview", params={
            "employee_id": "invalid-uuid-12345",
            "start_date": "2026-01-01",
            "end_date": "2026-04-04"
        })
        assert response.status_code == 404, f"Expected 404 for invalid employee, got {response.status_code}"
        print("✓ Employee Overview with invalid employee returns 404")
    
    def test_employee_overview_without_auth(self):
        """Test employee overview without authentication returns 401 or 403"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/hrms/attendance/employee-overview", params={
            "employee_id": self.test_employee_id,
            "start_date": "2026-01-01",
            "end_date": "2026-04-04"
        })
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print(f"✓ Employee Overview without auth returns {response.status_code}")
    
    def test_employee_overview_empty_date_range(self):
        """Test employee overview with date range having no records"""
        response = self.session.get(f"{BASE_URL}/api/hrms/attendance/employee-overview", params={
            "employee_id": self.test_employee_id,
            "start_date": "2020-01-01",
            "end_date": "2020-01-31"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total_records"] == 0
        assert len(data["records"]) == 0
        print("✓ Employee Overview with empty date range returns 0 records")
    
    # ============ BIOMETRIC SYNC ENDPOINT TESTS ============
    
    def test_biometric_sync_success(self):
        """Test POST /api/hrms/attendance/biometric-sync processes punches correctly"""
        response = self.session.post(f"{BASE_URL}/api/hrms/attendance/biometric-sync", json={
            "device_id": "BIO-TEST-001",
            "punches": [
                {"employee_code": self.test_employee_code, "timestamp": "2026-04-10T09:05:00", "type": "check_in"},
                {"employee_code": self.test_employee_code, "timestamp": "2026-04-10T18:10:00", "type": "check_out"}
            ]
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert "processed" in data
        assert "errors" in data
        assert data["processed"] >= 0
        print(f"✓ Biometric Sync: {data['processed']} punches processed, {len(data['errors'])} errors")
    
    def test_biometric_sync_invalid_employee_code(self):
        """Test biometric sync with invalid employee code reports error"""
        response = self.session.post(f"{BASE_URL}/api/hrms/attendance/biometric-sync", json={
            "device_id": "BIO-TEST-001",
            "punches": [
                {"employee_code": "INVALID-CODE-999", "timestamp": "2026-04-10T09:05:00", "type": "check_in"}
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["errors"]) > 0, "Should have errors for invalid employee code"
        assert "Employee not found" in data["errors"][0]
        print(f"✓ Biometric Sync with invalid employee code reports error: {data['errors'][0]}")
    
    def test_biometric_sync_invalid_punch_type(self):
        """Test biometric sync with invalid punch type reports error"""
        response = self.session.post(f"{BASE_URL}/api/hrms/attendance/biometric-sync", json={
            "device_id": "BIO-TEST-001",
            "punches": [
                {"employee_code": self.test_employee_code, "timestamp": "2026-04-10T09:05:00", "type": "invalid_type"}
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["errors"]) > 0, "Should have errors for invalid punch type"
        print(f"✓ Biometric Sync with invalid punch type reports error")
    
    def test_biometric_sync_empty_punches(self):
        """Test biometric sync with empty punches returns 400"""
        response = self.session.post(f"{BASE_URL}/api/hrms/attendance/biometric-sync", json={
            "device_id": "BIO-TEST-001",
            "punches": []
        })
        assert response.status_code == 400, f"Expected 400 for empty punches, got {response.status_code}"
        print("✓ Biometric Sync with empty punches returns 400")
    
    def test_biometric_sync_without_auth(self):
        """Test biometric sync without authentication returns 401 or 403"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        response = session.post(f"{BASE_URL}/api/hrms/attendance/biometric-sync", json={
            "device_id": "BIO-TEST-001",
            "punches": [
                {"employee_code": self.test_employee_code, "timestamp": "2026-04-10T09:05:00", "type": "check_in"}
            ]
        })
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print(f"✓ Biometric Sync without auth returns {response.status_code}")
    
    # ============ EMPLOYEE-WISE PDF/EXCEL EXPORT TESTS ============
    
    def test_employee_attendance_pdf_export(self):
        """Test GET /api/hrms/reports/attendance-employee/pdf returns valid PDF"""
        response = self.session.get(f"{BASE_URL}/api/hrms/reports/attendance-employee/pdf", params={
            "employee_id": self.test_employee_id,
            "start_date": "2026-01-01",
            "end_date": "2026-04-04"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get("content-type") == "application/pdf"
        assert "attachment" in response.headers.get("content-disposition", "")
        assert ".pdf" in response.headers.get("content-disposition", "")
        assert len(response.content) > 1000, "PDF should have substantial content"
        print(f"✓ Employee Attendance PDF export: {len(response.content)} bytes")
    
    def test_employee_attendance_excel_export(self):
        """Test GET /api/hrms/reports/attendance-employee/excel returns valid XLSX"""
        response = self.session.get(f"{BASE_URL}/api/hrms/reports/attendance-employee/excel", params={
            "employee_id": self.test_employee_id,
            "start_date": "2026-01-01",
            "end_date": "2026-04-04"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert "spreadsheetml" in response.headers.get("content-type", "")
        assert "attachment" in response.headers.get("content-disposition", "")
        assert ".xlsx" in response.headers.get("content-disposition", "")
        assert len(response.content) > 1000, "Excel should have substantial content"
        print(f"✓ Employee Attendance Excel export: {len(response.content)} bytes")
    
    def test_employee_attendance_pdf_invalid_employee(self):
        """Test PDF export with invalid employee returns 404"""
        response = self.session.get(f"{BASE_URL}/api/hrms/reports/attendance-employee/pdf", params={
            "employee_id": "invalid-uuid-12345",
            "start_date": "2026-01-01",
            "end_date": "2026-04-04"
        })
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Employee Attendance PDF with invalid employee returns 404")
    
    def test_employee_attendance_excel_invalid_employee(self):
        """Test Excel export with invalid employee returns 404"""
        response = self.session.get(f"{BASE_URL}/api/hrms/reports/attendance-employee/excel", params={
            "employee_id": "invalid-uuid-12345",
            "start_date": "2026-01-01",
            "end_date": "2026-04-04"
        })
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Employee Attendance Excel with invalid employee returns 404")
    
    # ============ EXISTING ATTENDANCE ENDPOINTS (REGRESSION) ============
    
    def test_daily_attendance_endpoint(self):
        """Test GET /api/hrms/attendance/daily returns employee list with attendance"""
        response = self.session.get(f"{BASE_URL}/api/hrms/attendance/daily", params={
            "date": "2026-04-01"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "date" in data
        assert "employees" in data
        assert data["date"] == "2026-04-01"
        assert isinstance(data["employees"], list)
        
        if data["employees"]:
            emp = data["employees"][0]
            assert "employee_id" in emp
            assert "name" in emp
            assert "department" in emp
            assert "status" in emp or emp.get("status") == ""
        
        print(f"✓ Daily Attendance: {len(data['employees'])} employees for 2026-04-01")
    
    def test_monthly_summary_endpoint(self):
        """Test GET /api/hrms/attendance/monthly-summary returns summary data"""
        response = self.session.get(f"{BASE_URL}/api/hrms/attendance/monthly-summary", params={
            "month": "2026-04"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "month" in data
        assert "total_days" in data
        assert "summaries" in data
        assert data["month"] == "2026-04"
        assert data["total_days"] == 30  # April has 30 days
        
        if data["summaries"]:
            summary = data["summaries"][0]
            assert "employee_id" in summary
            assert "name" in summary
            assert "present" in summary
            assert "absent" in summary
            assert "late" in summary
            assert "leave" in summary
            assert "effective_present" in summary
        
        print(f"✓ Monthly Summary: {len(data['summaries'])} employees for April 2026")
    
    def test_monthly_summary_pdf_export(self):
        """Test GET /api/hrms/reports/attendance/pdf returns valid PDF"""
        response = self.session.get(f"{BASE_URL}/api/hrms/reports/attendance/pdf", params={
            "month": "2026-04"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("content-type") == "application/pdf"
        assert "Attendance_April_2026.pdf" in response.headers.get("content-disposition", "")
        print(f"✓ Monthly Summary PDF export: {len(response.content)} bytes")
    
    def test_monthly_summary_excel_export(self):
        """Test GET /api/hrms/reports/attendance/excel returns valid XLSX"""
        response = self.session.get(f"{BASE_URL}/api/hrms/reports/attendance/excel", params={
            "month": "2026-04"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "spreadsheetml" in response.headers.get("content-type", "")
        assert "Attendance_April_2026.xlsx" in response.headers.get("content-disposition", "")
        print(f"✓ Monthly Summary Excel export: {len(response.content)} bytes")
    
    def test_attendance_mark_endpoint(self):
        """Test POST /api/hrms/attendance/mark works correctly"""
        response = self.session.post(f"{BASE_URL}/api/hrms/attendance/mark", json={
            "date": "2026-04-15",
            "records": [
                {
                    "employee_id": self.test_employee_id,
                    "status": "present",
                    "check_in": "09:00",
                    "check_out": "18:00",
                    "overtime_hours": 1.5,
                    "remarks": "Test attendance"
                }
            ]
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert "created" in data or "updated" in data
        print(f"✓ Attendance Mark: {data['message']}")
    
    def test_attendance_with_date_range(self):
        """Test GET /api/hrms/attendance with start_date and end_date params"""
        response = self.session.get(f"{BASE_URL}/api/hrms/attendance", params={
            "employee_id": self.test_employee_id,
            "start_date": "2026-01-01",
            "end_date": "2026-04-04"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "records" in data
        assert "total" in data
        print(f"✓ Attendance with date range: {data['total']} records")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
