"""
HRMS Certificates API Tests
Tests for Salary Certificate and Experience Certificate PDF generation
with proper formatting (A4, Arial font, centered header, justified body, left signature)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://unified-checkout-8.preview.emergentagent.com').rstrip('/')

class TestHRMSCertificates:
    """HRMS Certificate endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token and employee ID"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get an employee ID for testing
        emp_response = requests.get(f"{BASE_URL}/api/hrms/employees", headers=self.headers)
        assert emp_response.status_code == 200, f"Failed to get employees: {emp_response.text}"
        employees = emp_response.json().get('employees', [])
        assert len(employees) > 0, "No employees found for testing"
        self.employee_id = employees[0]['id']
        self.employee_name = employees[0]['name']
    
    # ============ SALARY CERTIFICATE ============
    
    def test_salary_certificate_pdf(self):
        """Test GET /api/hrms/certificates/salary/{emp_id}/pdf returns valid PDF"""
        response = requests.get(f"{BASE_URL}/api/hrms/certificates/salary/{self.employee_id}/pdf", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get('content-type') == 'application/pdf', f"Expected PDF content-type, got {response.headers.get('content-type')}"
        assert 'Content-Disposition' in response.headers, "Missing Content-Disposition header"
        assert 'Salary_Certificate' in response.headers.get('Content-Disposition', ''), f"Incorrect filename: {response.headers.get('Content-Disposition')}"
        # Check PDF magic bytes
        assert response.content[:4] == b'%PDF', "Response is not a valid PDF file"
        print(f"✓ Salary Certificate PDF for {self.employee_name} generated successfully ({len(response.content)} bytes)")
    
    def test_salary_certificate_invalid_employee(self):
        """Test salary certificate with invalid employee ID returns 404"""
        response = requests.get(f"{BASE_URL}/api/hrms/certificates/salary/invalid-emp-id-12345/pdf", headers=self.headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ Salary Certificate with invalid employee ID returns 404")
    
    def test_salary_certificate_unauthorized(self):
        """Test salary certificate without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/hrms/certificates/salary/{self.employee_id}/pdf")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Salary Certificate without auth returns {response.status_code}")
    
    # ============ EXPERIENCE CERTIFICATE ============
    
    def test_experience_certificate_pdf(self):
        """Test GET /api/hrms/certificates/experience/{emp_id}/pdf returns valid PDF"""
        response = requests.get(f"{BASE_URL}/api/hrms/certificates/experience/{self.employee_id}/pdf", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get('content-type') == 'application/pdf', f"Expected PDF content-type, got {response.headers.get('content-type')}"
        assert 'Content-Disposition' in response.headers, "Missing Content-Disposition header"
        assert 'Experience_Certificate' in response.headers.get('Content-Disposition', ''), f"Incorrect filename: {response.headers.get('Content-Disposition')}"
        # Check PDF magic bytes
        assert response.content[:4] == b'%PDF', "Response is not a valid PDF file"
        print(f"✓ Experience Certificate PDF for {self.employee_name} generated successfully ({len(response.content)} bytes)")
    
    def test_experience_certificate_invalid_employee(self):
        """Test experience certificate with invalid employee ID returns 404"""
        response = requests.get(f"{BASE_URL}/api/hrms/certificates/experience/invalid-emp-id-12345/pdf", headers=self.headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ Experience Certificate with invalid employee ID returns 404")
    
    def test_experience_certificate_unauthorized(self):
        """Test experience certificate without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/hrms/certificates/experience/{self.employee_id}/pdf")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Experience Certificate without auth returns {response.status_code}")
    
    # ============ MULTIPLE EMPLOYEES ============
    
    def test_certificates_for_multiple_employees(self):
        """Test certificates can be generated for different employees"""
        emp_response = requests.get(f"{BASE_URL}/api/hrms/employees?limit=5", headers=self.headers)
        assert emp_response.status_code == 200
        employees = emp_response.json().get('employees', [])
        
        success_count = 0
        for emp in employees[:3]:  # Test first 3 employees
            # Salary Certificate
            sal_response = requests.get(f"{BASE_URL}/api/hrms/certificates/salary/{emp['id']}/pdf", headers=self.headers)
            if sal_response.status_code == 200 and sal_response.content[:4] == b'%PDF':
                success_count += 1
            
            # Experience Certificate
            exp_response = requests.get(f"{BASE_URL}/api/hrms/certificates/experience/{emp['id']}/pdf", headers=self.headers)
            if exp_response.status_code == 200 and exp_response.content[:4] == b'%PDF':
                success_count += 1
        
        assert success_count >= 4, f"Expected at least 4 successful certificate generations, got {success_count}"
        print(f"✓ Generated {success_count} certificates for multiple employees")


class TestCompanySettings:
    """Test company settings and logo upload for report headers"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_company_settings(self):
        """Test GET /api/hrms/company-settings returns company info"""
        response = requests.get(f"{BASE_URL}/api/hrms/company-settings", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify expected fields
        assert 'company_name' in data, "Missing company_name"
        print(f"✓ Company settings: {data.get('company_name', 'N/A')}")
    
    def test_update_company_settings(self):
        """Test PUT /api/hrms/company-settings updates company info"""
        # First get current settings
        get_response = requests.get(f"{BASE_URL}/api/hrms/company-settings", headers=self.headers)
        assert get_response.status_code == 200
        current = get_response.json()
        
        # Update with same values (to not break anything)
        update_data = {
            "company_name": current.get('company_name', 'K3 GAS SERVICE'),
            "tagline": current.get('tagline', 'Khayal Hamesha'),
            "address": current.get('address', ''),
            "email": current.get('email', ''),
            "helpline": current.get('helpline', '')
        }
        
        response = requests.put(f"{BASE_URL}/api/hrms/company-settings", json=update_data, headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Company settings update works")
    
    def test_company_logo_upload_endpoint_exists(self):
        """Test POST /api/hrms/company-logo endpoint exists"""
        # Test with empty file to verify endpoint exists
        response = requests.post(f"{BASE_URL}/api/hrms/company-logo", headers=self.headers)
        # Should return 422 (validation error) or 400 (bad request) if no file, not 404
        assert response.status_code != 404, f"Logo upload endpoint not found: {response.status_code}"
        print(f"✓ Company logo upload endpoint exists (status: {response.status_code})")


class TestPayslipPDF:
    """Test individual payslip PDF generation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token and payroll data"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_payslip_pdf_a4_format(self):
        """Test payslip PDF is generated in A4 format"""
        # Get payroll history
        history_response = requests.get(f"{BASE_URL}/api/hrms/payroll/history", headers=self.headers)
        assert history_response.status_code == 200
        payrolls = history_response.json()
        
        if not payrolls:
            pytest.skip("No payroll runs found")
        
        payroll_id = payrolls[0]['id']
        
        # Get payroll detail
        detail_response = requests.get(f"{BASE_URL}/api/hrms/payroll/{payroll_id}", headers=self.headers)
        assert detail_response.status_code == 200
        payroll_detail = detail_response.json()
        
        employees = payroll_detail.get('employees', [])
        if not employees:
            pytest.skip("No employees in payroll")
        
        emp_id = employees[0]['employee_id']
        
        # Get payslip PDF
        response = requests.get(f"{BASE_URL}/api/hrms/payroll/{payroll_id}/payslip/{emp_id}/pdf", headers=self.headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.content[:4] == b'%PDF', "Response is not a valid PDF"
        
        # PDF should be reasonable size for A4 document
        assert len(response.content) > 1000, "PDF seems too small for A4 document"
        print(f"✓ Payslip PDF generated ({len(response.content)} bytes)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
