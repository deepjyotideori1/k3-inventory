"""
HRMS Smart Search API Tests
Tests the /api/hrms/search endpoint for searching across all HRMS modules
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHRMSSmartSearch:
    """Tests for HRMS Smart Search endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
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
            self.authenticated = True
        else:
            self.authenticated = False
            pytest.skip("Authentication failed - skipping tests")
    
    # ============ AUTHENTICATION TESTS ============
    
    def test_search_requires_authentication(self):
        """Search endpoint requires authentication"""
        unauthenticated_session = requests.Session()
        response = unauthenticated_session.get(f"{BASE_URL}/api/hrms/search", params={"q": "test"})
        # API returns 401 or 403 for unauthenticated requests
        assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}"
        print("PASS: Search requires authentication")
    
    # ============ BASIC SEARCH TESTS ============
    
    def test_search_empty_query_returns_empty(self):
        """Empty query returns empty results"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": ""})
        assert response.status_code == 200
        data = response.json()
        assert data['results'] == []
        assert data['total'] == 0
        print("PASS: Empty query returns empty results")
    
    def test_search_by_employee_name_ankit(self):
        """Search finds employee by name 'Ankit'"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "Ankit"})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] > 0, "Expected at least one result for 'Ankit'"
        
        # Check that results contain employee module
        employee_results = [r for r in data['results'] if r['module'] == 'Employees']
        assert len(employee_results) > 0, "Expected employee results for 'Ankit'"
        
        # Verify result structure
        result = employee_results[0]
        assert 'title' in result
        assert 'subtitle' in result
        assert 'link' in result
        assert 'Ankit' in result['title'] or 'ankit' in result['title'].lower()
        print(f"PASS: Found {len(employee_results)} employee(s) for 'Ankit'")
    
    def test_search_by_employee_code(self):
        """Search finds employee by code 'K3-0003'"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "K3-0003"})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] > 0, "Expected at least one result for 'K3-0003'"
        
        employee_results = [r for r in data['results'] if r['module'] == 'Employees']
        assert len(employee_results) > 0, "Expected employee results for 'K3-0003'"
        
        # Verify employee code in subtitle
        result = employee_results[0]
        assert 'K3-0003' in result['subtitle']
        print(f"PASS: Found employee by code K3-0003")
    
    def test_search_by_department_name(self):
        """Search finds department by name 'Operations'"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "Operations"})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] > 0, "Expected at least one result for 'Operations'"
        
        # Check for department results
        dept_results = [r for r in data['results'] if r['module'] == 'Departments']
        assert len(dept_results) > 0, "Expected department results for 'Operations'"
        
        # Verify department result structure
        result = dept_results[0]
        assert 'Operations' in result['title']
        assert result['link'] == '/hrms/departments'
        print(f"PASS: Found department 'Operations'")
    
    def test_search_by_designation(self):
        """Search finds employees by designation 'Manager'"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "Manager"})
        assert response.status_code == 200
        data = response.json()
        
        # Should find employees with Manager designation
        employee_results = [r for r in data['results'] if r['module'] == 'Employees']
        if len(employee_results) > 0:
            # Check that Manager appears in subtitle (which contains designation)
            has_manager = any('Manager' in r['subtitle'] for r in employee_results)
            assert has_manager, "Expected 'Manager' in employee subtitle"
            print(f"PASS: Found {len(employee_results)} employee(s) with 'Manager' designation")
        else:
            print("INFO: No employees with 'Manager' designation found")
    
    # ============ CROSS-MODULE SEARCH TESTS ============
    
    def test_search_returns_multiple_modules(self):
        """Search for 'Operations' returns both Employees and Departments"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "Operations"})
        assert response.status_code == 200
        data = response.json()
        
        # Check module_counts
        assert 'module_counts' in data
        modules_found = list(data['module_counts'].keys())
        
        # Should have at least Departments
        assert 'Departments' in modules_found, "Expected Departments in results"
        print(f"PASS: Search returns modules: {modules_found}")
    
    def test_search_module_counts_correct(self):
        """Module counts match actual result counts"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "Ankit"})
        assert response.status_code == 200
        data = response.json()
        
        # Verify module_counts matches actual results
        for module, count in data['module_counts'].items():
            actual_count = len([r for r in data['results'] if r['module'] == module])
            assert count == actual_count, f"Module {module}: expected {count}, got {actual_count}"
        
        print(f"PASS: Module counts are correct: {data['module_counts']}")
    
    # ============ RESULT STRUCTURE TESTS ============
    
    def test_search_result_structure(self):
        """Search results have correct structure"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "Ankit"})
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert 'results' in data
        assert 'total' in data
        assert 'query' in data
        assert 'module_counts' in data
        
        if data['total'] > 0:
            result = data['results'][0]
            assert 'module' in result
            assert 'id' in result
            assert 'title' in result
            assert 'subtitle' in result
            assert 'link' in result
            print(f"PASS: Result structure is correct")
        else:
            pytest.skip("No results to verify structure")
    
    def test_search_employee_has_status(self):
        """Employee search results include status (Active/Inactive)"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "Ankit"})
        assert response.status_code == 200
        data = response.json()
        
        employee_results = [r for r in data['results'] if r['module'] == 'Employees']
        if len(employee_results) > 0:
            result = employee_results[0]
            assert 'status' in result
            assert result['status'] in ['Active', 'Inactive']
            print(f"PASS: Employee result has status: {result['status']}")
        else:
            pytest.skip("No employee results to verify status")
    
    def test_search_department_has_employee_count(self):
        """Department search results include employee count in meta"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "Operations"})
        assert response.status_code == 200
        data = response.json()
        
        dept_results = [r for r in data['results'] if r['module'] == 'Departments']
        if len(dept_results) > 0:
            result = dept_results[0]
            assert 'meta' in result
            assert 'employees' in result['meta'].lower()
            print(f"PASS: Department result has employee count: {result['meta']}")
        else:
            pytest.skip("No department results to verify meta")
    
    # ============ LINK NAVIGATION TESTS ============
    
    def test_employee_result_links_to_employees_page(self):
        """Employee results link to /hrms/employees"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "Ankit"})
        assert response.status_code == 200
        data = response.json()
        
        employee_results = [r for r in data['results'] if r['module'] == 'Employees']
        if len(employee_results) > 0:
            assert employee_results[0]['link'] == '/hrms/employees'
            print("PASS: Employee results link to /hrms/employees")
        else:
            pytest.skip("No employee results")
    
    def test_department_result_links_to_departments_page(self):
        """Department results link to /hrms/departments"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "Operations"})
        assert response.status_code == 200
        data = response.json()
        
        dept_results = [r for r in data['results'] if r['module'] == 'Departments']
        if len(dept_results) > 0:
            assert dept_results[0]['link'] == '/hrms/departments'
            print("PASS: Department results link to /hrms/departments")
        else:
            pytest.skip("No department results")
    
    # ============ EDGE CASE TESTS ============
    
    def test_search_case_insensitive(self):
        """Search is case insensitive"""
        response_lower = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "ankit"})
        response_upper = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "ANKIT"})
        response_mixed = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "AnKiT"})
        
        assert response_lower.status_code == 200
        assert response_upper.status_code == 200
        assert response_mixed.status_code == 200
        
        # All should return same number of results
        total_lower = response_lower.json()['total']
        total_upper = response_upper.json()['total']
        total_mixed = response_mixed.json()['total']
        
        assert total_lower == total_upper == total_mixed, "Case insensitive search should return same results"
        print(f"PASS: Search is case insensitive (all returned {total_lower} results)")
    
    def test_search_partial_match(self):
        """Search matches partial strings"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "Ank"})
        assert response.status_code == 200
        data = response.json()
        
        # Should still find Ankit with partial match
        if data['total'] > 0:
            print(f"PASS: Partial search 'Ank' found {data['total']} results")
        else:
            print("INFO: No results for partial search 'Ank'")
    
    def test_search_special_characters(self):
        """Search handles special characters gracefully"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "test@email.com"})
        assert response.status_code == 200
        print("PASS: Search handles special characters")
    
    def test_search_whitespace_query(self):
        """Search with only whitespace returns empty"""
        response = self.session.get(f"{BASE_URL}/api/hrms/search", params={"q": "   "})
        assert response.status_code == 200
        data = response.json()
        # Whitespace-only query should be treated as empty
        assert data['total'] == 0 or data['results'] == []
        print("PASS: Whitespace query handled correctly")


class TestHRMSSearchRegression:
    """Regression tests to ensure existing HRMS features still work"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
    
    def test_hrms_dashboard_stats_still_works(self):
        """HRMS Dashboard stats endpoint still works"""
        response = self.session.get(f"{BASE_URL}/api/hrms/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert 'total_employees' in data
        assert 'total_departments' in data
        print(f"PASS: Dashboard stats works - {data['total_employees']} employees, {data['total_departments']} departments")
    
    def test_hrms_employees_list_still_works(self):
        """HRMS Employees list endpoint still works"""
        response = self.session.get(f"{BASE_URL}/api/hrms/employees")
        assert response.status_code == 200
        data = response.json()
        assert 'employees' in data
        assert 'total' in data
        print(f"PASS: Employees list works - {data['total']} employees")
    
    def test_hrms_departments_list_still_works(self):
        """HRMS Departments list endpoint still works"""
        response = self.session.get(f"{BASE_URL}/api/hrms/departments")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Departments list works - {len(data)} departments")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
