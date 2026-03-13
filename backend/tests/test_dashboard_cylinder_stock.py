"""
Backend Tests for Dashboard Cylinder Stock Summary Widget
Tests for admin dashboard stats including:
- Top stats cards data (Total Warehouses, Filled Cylinders, Empty Cylinders, Discrepancies)
- Per-warehouse breakdown data
- Plant data inclusion
- Proper totals calculation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDashboardStats:
    """Test /api/dashboard/stats endpoint for Cylinder Stock Summary widget"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@k3gas.com", "password": "Admin@123"}
        )
        assert login_response.status_code == 200, f"Admin login failed: {login_response.text}"
        self.admin_token = login_response.json()["token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
    
    def test_dashboard_stats_returns_200(self):
        """Test that /api/dashboard/stats returns 200 for admin"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("SUCCESS: Dashboard stats endpoint returns 200")
    
    def test_dashboard_stats_contains_total_warehouses(self):
        """Test that response contains total_warehouses count"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.admin_headers
        )
        data = response.json()
        
        assert "total_warehouses" in data, "Missing total_warehouses field"
        assert isinstance(data["total_warehouses"], int), "total_warehouses should be integer"
        assert data["total_warehouses"] >= 0, "total_warehouses should be non-negative"
        print(f"SUCCESS: total_warehouses = {data['total_warehouses']}")
    
    def test_dashboard_stats_contains_filled_cylinder_totals(self):
        """Test that response contains total filled cylinders (15kg and 21kg)"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.admin_headers
        )
        data = response.json()
        
        # Check for 15kg filled
        assert "total_15kg_filled" in data, "Missing total_15kg_filled field"
        assert isinstance(data["total_15kg_filled"], int), "total_15kg_filled should be integer"
        
        # Check for 21kg filled
        assert "total_21kg_filled" in data, "Missing total_21kg_filled field"
        assert isinstance(data["total_21kg_filled"], int), "total_21kg_filled should be integer"
        
        print(f"SUCCESS: total_15kg_filled = {data['total_15kg_filled']}, total_21kg_filled = {data['total_21kg_filled']}")
    
    def test_dashboard_stats_contains_empty_cylinder_totals(self):
        """Test that response contains total empty cylinders (15kg and 21kg)"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.admin_headers
        )
        data = response.json()
        
        # Check for 15kg empty
        assert "total_15kg_empty" in data, "Missing total_15kg_empty field"
        assert isinstance(data["total_15kg_empty"], int), "total_15kg_empty should be integer"
        
        # Check for 21kg empty
        assert "total_21kg_empty" in data, "Missing total_21kg_empty field"
        assert isinstance(data["total_21kg_empty"], int), "total_21kg_empty should be integer"
        
        print(f"SUCCESS: total_15kg_empty = {data['total_15kg_empty']}, total_21kg_empty = {data['total_21kg_empty']}")
    
    def test_dashboard_stats_contains_warehouses_array(self):
        """Test that response contains warehouses array with per-warehouse data"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.admin_headers
        )
        data = response.json()
        
        assert "warehouses" in data, "Missing warehouses field"
        assert isinstance(data["warehouses"], list), "warehouses should be a list"
        
        if len(data["warehouses"]) > 0:
            warehouse = data["warehouses"][0]
            required_fields = ["id", "name", "closing_15kg_filled", "closing_21kg_filled", 
                            "closing_15kg_empty", "closing_21kg_empty", "last_report_date", 
                            "has_discrepancy"]
            for field in required_fields:
                assert field in warehouse, f"Warehouse missing field: {field}"
        
        print(f"SUCCESS: {len(data['warehouses'])} warehouses in response")
    
    def test_dashboard_stats_contains_plant_data(self):
        """Test that response contains plant data"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.admin_headers
        )
        data = response.json()
        
        assert "plant" in data, "Missing plant field"
        
        if data["plant"] is not None:
            plant_fields = ["bullet_tank_kg", "closing_15kg_filled", "closing_21kg_filled",
                          "closing_15kg_empty", "closing_21kg_empty", "last_report_date"]
            for field in plant_fields:
                assert field in data["plant"], f"Plant missing field: {field}"
            print(f"SUCCESS: Plant data present with {data['plant']['closing_15kg_filled'] + data['plant']['closing_21kg_filled']} filled cylinders")
        else:
            print("INFO: Plant data is null (no plant reports yet)")
    
    def test_dashboard_stats_contains_discrepancies_array(self):
        """Test that response contains discrepancies array"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.admin_headers
        )
        data = response.json()
        
        assert "discrepancies" in data, "Missing discrepancies field"
        assert isinstance(data["discrepancies"], list), "discrepancies should be a list"
        
        print(f"SUCCESS: {len(data['discrepancies'])} discrepancies found")
    
    def test_totals_match_warehouse_sum(self):
        """Test that total filled/empty equals sum of all warehouses"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.admin_headers
        )
        data = response.json()
        
        # Calculate sums from warehouses
        sum_15kg_filled = sum(w["closing_15kg_filled"] for w in data["warehouses"])
        sum_21kg_filled = sum(w["closing_21kg_filled"] for w in data["warehouses"])
        sum_15kg_empty = sum(w["closing_15kg_empty"] for w in data["warehouses"])
        sum_21kg_empty = sum(w["closing_21kg_empty"] for w in data["warehouses"])
        
        # Compare with totals
        assert data["total_15kg_filled"] == sum_15kg_filled, \
            f"total_15kg_filled mismatch: {data['total_15kg_filled']} != {sum_15kg_filled}"
        assert data["total_21kg_filled"] == sum_21kg_filled, \
            f"total_21kg_filled mismatch: {data['total_21kg_filled']} != {sum_21kg_filled}"
        assert data["total_15kg_empty"] == sum_15kg_empty, \
            f"total_15kg_empty mismatch: {data['total_15kg_empty']} != {sum_15kg_empty}"
        assert data["total_21kg_empty"] == sum_21kg_empty, \
            f"total_21kg_empty mismatch: {data['total_21kg_empty']} != {sum_21kg_empty}"
        
        print(f"SUCCESS: Totals match warehouse sums")
        print(f"  15kg Filled: {data['total_15kg_filled']}")
        print(f"  21kg Filled: {data['total_21kg_filled']}")
        print(f"  15kg Empty: {data['total_15kg_empty']}")
        print(f"  21kg Empty: {data['total_21kg_empty']}")


class TestWarehouseManagerAccess:
    """Test that warehouse managers get appropriate data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as warehouse manager"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "jullang@k3gas.com", "password": "Jullang@123"}
        )
        assert login_response.status_code == 200, f"Warehouse manager login failed: {login_response.text}"
        self.manager_token = login_response.json()["token"]
        self.manager_headers = {"Authorization": f"Bearer {self.manager_token}"}
    
    def test_warehouse_manager_can_access_dashboard_stats(self):
        """Test that warehouse manager can access dashboard stats endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.manager_headers
        )
        # Warehouse manager should be able to access the endpoint
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("SUCCESS: Warehouse manager can access dashboard stats")


class TestSalesExecAccess:
    """Test that sales executives get appropriate data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as sales executive"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "sales@k3gas.com", "password": "Sales@123"}
        )
        assert login_response.status_code == 200, f"Sales exec login failed: {login_response.text}"
        self.exec_token = login_response.json()["token"]
        self.exec_headers = {"Authorization": f"Bearer {self.exec_token}"}
    
    def test_sales_exec_can_access_dashboard_stats(self):
        """Test that sales exec can access dashboard stats endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.exec_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("SUCCESS: Sales exec can access dashboard stats")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
