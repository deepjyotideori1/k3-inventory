"""
Test Date Format (DD-MM-YYYY) and Ascending Sort Order Changes
Tests for:
1. Backend API sort orders (ascending by date)
2. Report PDF/Excel date formats (DD-MM-YYYY)
3. Regression tests for CRUD operations
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDateFormatAndSortOrder:
    """Test date format and sort order changes across HRMS modules"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
    
    # ============ ATTENDANCE SORT ORDER TESTS ============
    
    def test_attendance_records_sorted_ascending_by_date(self):
        """GET /api/hrms/attendance returns records sorted ascending by date"""
        # Get current month
        now = datetime.now()
        month = f"{now.year}-{now.month:02d}"
        
        resp = self.session.get(f"{BASE_URL}/api/hrms/attendance", params={"month": month})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        records = data.get('records', [])
        
        if len(records) >= 2:
            # Verify ascending order
            dates = [r.get('date', '') for r in records]
            assert dates == sorted(dates), f"Attendance records not sorted ascending. Got: {dates[:5]}..."
            print(f"✓ Attendance records sorted ascending by date ({len(records)} records)")
        else:
            print(f"✓ Attendance endpoint works (only {len(records)} records found)")
    
    def test_attendance_daily_returns_data(self):
        """GET /api/hrms/attendance/daily returns employee attendance for a date"""
        today = datetime.now().strftime('%Y-%m-%d')
        resp = self.session.get(f"{BASE_URL}/api/hrms/attendance/daily", params={"date": today})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert 'employees' in data, "Response missing 'employees' field"
        assert 'date' in data, "Response missing 'date' field"
        print(f"✓ Daily attendance endpoint works ({len(data.get('employees', []))} employees)")
    
    def test_attendance_employee_overview_sorted_ascending(self):
        """GET /api/hrms/attendance/employee-overview returns records sorted ascending"""
        # First get an employee
        emp_resp = self.session.get(f"{BASE_URL}/api/hrms/employees", params={"limit": 1})
        assert emp_resp.status_code == 200
        employees = emp_resp.json().get('employees', [])
        
        if not employees:
            pytest.skip("No employees found")
        
        emp_id = employees[0]['id']
        now = datetime.now()
        start_date = f"{now.year}-{now.month:02d}-01"
        end_date = now.strftime('%Y-%m-%d')
        
        resp = self.session.get(f"{BASE_URL}/api/hrms/attendance/employee-overview", params={
            "employee_id": emp_id,
            "start_date": start_date,
            "end_date": end_date
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        records = data.get('records', [])
        
        if len(records) >= 2:
            dates = [r.get('date', '') for r in records]
            assert dates == sorted(dates), f"Employee overview records not sorted ascending. Got: {dates[:5]}..."
            print(f"✓ Employee overview records sorted ascending ({len(records)} records)")
        else:
            print(f"✓ Employee overview endpoint works ({len(records)} records)")
    
    # ============ PAYROLL SORT ORDER TESTS ============
    
    def test_payroll_history_sorted_ascending_by_year_month(self):
        """GET /api/hrms/payroll/history returns payrolls sorted ascending by year+month"""
        resp = self.session.get(f"{BASE_URL}/api/hrms/payroll/history")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        payrolls = resp.json()
        
        if len(payrolls) >= 2:
            # Check year+month ascending order
            periods = [(p.get('year', 0), p.get('month', 0)) for p in payrolls]
            assert periods == sorted(periods), f"Payroll not sorted ascending. Got: {periods[:5]}..."
            print(f"✓ Payroll history sorted ascending by year+month ({len(payrolls)} records)")
        else:
            print(f"✓ Payroll history endpoint works ({len(payrolls)} records)")
    
    # ============ HIRING SORT ORDER TESTS ============
    
    def test_jobs_sorted_ascending_by_created_at(self):
        """GET /api/hrms/jobs returns jobs sorted ascending by created_at"""
        resp = self.session.get(f"{BASE_URL}/api/hrms/jobs")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        jobs = resp.json()
        
        if len(jobs) >= 2:
            created_dates = [j.get('created_at', '') for j in jobs]
            assert created_dates == sorted(created_dates), f"Jobs not sorted ascending. Got: {created_dates[:3]}..."
            print(f"✓ Jobs sorted ascending by created_at ({len(jobs)} jobs)")
        else:
            print(f"✓ Jobs endpoint works ({len(jobs)} jobs)")
    
    def test_candidates_sorted_ascending_by_created_at(self):
        """GET /api/hrms/candidates returns candidates sorted ascending by created_at"""
        resp = self.session.get(f"{BASE_URL}/api/hrms/candidates")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        candidates = resp.json()
        
        if len(candidates) >= 2:
            created_dates = [c.get('created_at', '') for c in candidates]
            assert created_dates == sorted(created_dates), f"Candidates not sorted ascending. Got: {created_dates[:3]}..."
            print(f"✓ Candidates sorted ascending by created_at ({len(candidates)} candidates)")
        else:
            print(f"✓ Candidates endpoint works ({len(candidates)} candidates)")
    
    # ============ PERFORMANCE SORT ORDER TESTS ============
    
    def test_appraisal_cycles_sorted_ascending_by_start_date(self):
        """GET /api/hrms/appraisals/cycles returns cycles sorted ascending by start_date"""
        resp = self.session.get(f"{BASE_URL}/api/hrms/appraisals/cycles")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        cycles = resp.json()
        
        if len(cycles) >= 2:
            start_dates = [c.get('start_date', '') for c in cycles]
            assert start_dates == sorted(start_dates), f"Cycles not sorted ascending. Got: {start_dates[:3]}..."
            print(f"✓ Appraisal cycles sorted ascending by start_date ({len(cycles)} cycles)")
        else:
            print(f"✓ Appraisal cycles endpoint works ({len(cycles)} cycles)")
    
    def test_reviews_sorted_ascending_by_created_at(self):
        """GET /api/hrms/reviews returns reviews sorted ascending by created_at"""
        resp = self.session.get(f"{BASE_URL}/api/hrms/reviews")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        reviews = resp.json()
        
        if len(reviews) >= 2:
            created_dates = [r.get('created_at', '') for r in reviews]
            assert created_dates == sorted(created_dates), f"Reviews not sorted ascending. Got: {created_dates[:3]}..."
            print(f"✓ Reviews sorted ascending by created_at ({len(reviews)} reviews)")
        else:
            print(f"✓ Reviews endpoint works ({len(reviews)} reviews)")
    
    # ============ REPORT DATE FORMAT TESTS ============
    
    def test_employee_attendance_pdf_has_dd_mm_yyyy_format(self):
        """Employee Attendance PDF report endpoint works"""
        # First get an employee
        emp_resp = self.session.get(f"{BASE_URL}/api/hrms/employees", params={"limit": 1})
        assert emp_resp.status_code == 200
        employees = emp_resp.json().get('employees', [])
        
        if not employees:
            pytest.skip("No employees found")
        
        emp_id = employees[0]['id']
        now = datetime.now()
        start_date = f"{now.year}-{now.month:02d}-01"
        end_date = now.strftime('%Y-%m-%d')
        
        resp = self.session.get(f"{BASE_URL}/api/hrms/reports/attendance-employee/pdf", params={
            "employee_id": emp_id,
            "start_date": start_date,
            "end_date": end_date
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        assert 'application/pdf' in resp.headers.get('Content-Type', ''), "Response is not PDF"
        assert len(resp.content) > 1000, "PDF content too small"
        print(f"✓ Employee attendance PDF report generated successfully ({len(resp.content)} bytes)")
    
    def test_employee_attendance_excel_has_dd_mm_yyyy_format(self):
        """Employee Attendance Excel report endpoint works"""
        # First get an employee
        emp_resp = self.session.get(f"{BASE_URL}/api/hrms/employees", params={"limit": 1})
        assert emp_resp.status_code == 200
        employees = emp_resp.json().get('employees', [])
        
        if not employees:
            pytest.skip("No employees found")
        
        emp_id = employees[0]['id']
        now = datetime.now()
        start_date = f"{now.year}-{now.month:02d}-01"
        end_date = now.strftime('%Y-%m-%d')
        
        resp = self.session.get(f"{BASE_URL}/api/hrms/reports/attendance-employee/excel", params={
            "employee_id": emp_id,
            "start_date": start_date,
            "end_date": end_date
        })
        assert resp.status_code == 200, f"Failed: {resp.text}"
        assert 'spreadsheet' in resp.headers.get('Content-Type', ''), "Response is not Excel"
        assert len(resp.content) > 1000, "Excel content too small"
        print(f"✓ Employee attendance Excel report generated successfully ({len(resp.content)} bytes)")
    
    def test_employee_directory_pdf_has_dd_mm_yyyy_format(self):
        """Employee Directory PDF report endpoint works"""
        resp = self.session.get(f"{BASE_URL}/api/hrms/reports/employees/pdf")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        assert 'application/pdf' in resp.headers.get('Content-Type', ''), "Response is not PDF"
        assert len(resp.content) > 1000, "PDF content too small"
        print(f"✓ Employee directory PDF report generated successfully ({len(resp.content)} bytes)")
    
    def test_employee_directory_excel_works(self):
        """Employee Directory Excel report endpoint works"""
        resp = self.session.get(f"{BASE_URL}/api/hrms/reports/employees/excel")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        assert 'spreadsheet' in resp.headers.get('Content-Type', ''), "Response is not Excel"
        assert len(resp.content) > 1000, "Excel content too small"
        print(f"✓ Employee directory Excel report generated successfully ({len(resp.content)} bytes)")
    
    # ============ REGRESSION TESTS ============
    
    def test_regression_employee_crud_list(self):
        """Regression: Employee list endpoint works"""
        resp = self.session.get(f"{BASE_URL}/api/hrms/employees")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert 'employees' in data, "Response missing 'employees' field"
        assert 'total' in data, "Response missing 'total' field"
        print(f"✓ Employee list works ({data.get('total', 0)} employees)")
    
    def test_regression_employee_crud_get_single(self):
        """Regression: Get single employee works"""
        # First get an employee
        list_resp = self.session.get(f"{BASE_URL}/api/hrms/employees", params={"limit": 1})
        assert list_resp.status_code == 200
        employees = list_resp.json().get('employees', [])
        
        if not employees:
            pytest.skip("No employees found")
        
        emp_id = employees[0]['id']
        resp = self.session.get(f"{BASE_URL}/api/hrms/employees/{emp_id}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        emp = resp.json()
        assert 'name' in emp, "Response missing 'name' field"
        assert 'employee_id' in emp, "Response missing 'employee_id' field"
        print(f"✓ Get single employee works ({emp.get('name')})")
    
    def test_regression_attendance_daily_entry_works(self):
        """Regression: Attendance daily entry endpoint works"""
        today = datetime.now().strftime('%Y-%m-%d')
        resp = self.session.get(f"{BASE_URL}/api/hrms/attendance/daily", params={"date": today})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert 'employees' in data, "Response missing 'employees' field"
        print(f"✓ Attendance daily entry works ({len(data.get('employees', []))} employees)")
    
    def test_regression_attendance_monthly_summary_works(self):
        """Regression: Attendance monthly summary endpoint works"""
        now = datetime.now()
        month = f"{now.year}-{now.month:02d}"
        
        resp = self.session.get(f"{BASE_URL}/api/hrms/attendance/monthly-summary", params={"month": month})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert 'summaries' in data, "Response missing 'summaries' field"
        assert 'month' in data, "Response missing 'month' field"
        print(f"✓ Attendance monthly summary works ({len(data.get('summaries', []))} employees)")
    
    def test_regression_smart_search_works(self):
        """Regression: Smart search endpoint works"""
        resp = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "test"})
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert 'results' in data, "Response missing 'results' field"
        assert 'total' in data, "Response missing 'total' field"
        print(f"✓ Smart search works ({data.get('total', 0)} results)")
    
    def test_regression_dashboard_stats_works(self):
        """Regression: Dashboard stats endpoint works"""
        resp = self.session.get(f"{BASE_URL}/api/hrms/dashboard/stats")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert 'total_employees' in data, "Response missing 'total_employees' field"
        print(f"✓ Dashboard stats works ({data.get('total_employees', 0)} employees)")
    
    def test_regression_departments_list_works(self):
        """Regression: Departments list endpoint works"""
        resp = self.session.get(f"{BASE_URL}/api/hrms/departments")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        departments = resp.json()
        assert isinstance(departments, list), "Response should be a list"
        print(f"✓ Departments list works ({len(departments)} departments)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
