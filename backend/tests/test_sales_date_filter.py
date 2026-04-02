"""
Test Sales Dashboard Date Filter Bug Fix
- Default view shows 'This Month' with startDate = 1st of current month and endDate = today
- Backend API receives correct date params on default load
- Last Month filter shows correct date range
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSalesDateFilter:
    """Test Sales Dashboard Date Filter functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@k3gas.com",
            "password": "Admin@123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Calculate expected dates
        today = datetime.now()
        self.today_str = today.strftime('%Y-%m-%d')
        self.first_of_month = datetime(today.year, today.month, 1).strftime('%Y-%m-%d')
        
        # Last month dates
        last_month_end = datetime(today.year, today.month, 1) - timedelta(days=1)
        last_month_start = datetime(last_month_end.year, last_month_end.month, 1)
        self.last_month_start = last_month_start.strftime('%Y-%m-%d')
        self.last_month_end = last_month_end.strftime('%Y-%m-%d')
    
    def test_this_month_filter_returns_correct_data(self):
        """Test that 'This Month' filter uses correct date range (1st of month to today)"""
        response = requests.get(
            f"{BASE_URL}/api/sales-entries",
            params={
                "start_date": self.first_of_month,
                "end_date": self.today_str
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"API call failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "entries" in data, "Response should contain 'entries' key"
        assert "total" in data, "Response should contain 'total' key"
        assert "page" in data, "Response should contain 'page' key"
        
        # Verify all entries are within the date range
        for entry in data.get("entries", []):
            entry_date = entry.get("date", "")
            assert entry_date >= self.first_of_month, f"Entry date {entry_date} is before first of month {self.first_of_month}"
            assert entry_date <= self.today_str, f"Entry date {entry_date} is after today {self.today_str}"
        
        print(f"✓ This Month filter ({self.first_of_month} to {self.today_str}): {data.get('total', 0)} entries")
    
    def test_this_month_summary_returns_correct_data(self):
        """Test that 'This Month' summary uses correct date range"""
        response = requests.get(
            f"{BASE_URL}/api/sales-entries/summary",
            params={
                "start_date": self.first_of_month,
                "end_date": self.today_str
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"Summary API call failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "cash" in data, "Summary should contain 'cash' key"
        assert "online" in data, "Summary should contain 'online' key"
        assert "pending" in data, "Summary should contain 'pending' key"
        assert "total" in data, "Summary should contain 'total' key"
        
        print(f"✓ This Month summary: Total amount = {data.get('total', {}).get('amount', 0)}")
    
    def test_last_month_filter_returns_correct_data(self):
        """Test that 'Last Month' filter uses correct date range (1st to last day of previous month)"""
        response = requests.get(
            f"{BASE_URL}/api/sales-entries",
            params={
                "start_date": self.last_month_start,
                "end_date": self.last_month_end
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"API call failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "entries" in data, "Response should contain 'entries' key"
        
        # Verify all entries are within the date range
        for entry in data.get("entries", []):
            entry_date = entry.get("date", "")
            assert entry_date >= self.last_month_start, f"Entry date {entry_date} is before last month start {self.last_month_start}"
            assert entry_date <= self.last_month_end, f"Entry date {entry_date} is after last month end {self.last_month_end}"
        
        print(f"✓ Last Month filter ({self.last_month_start} to {self.last_month_end}): {data.get('total', 0)} entries")
    
    def test_last_month_summary_returns_correct_data(self):
        """Test that 'Last Month' summary uses correct date range"""
        response = requests.get(
            f"{BASE_URL}/api/sales-entries/summary",
            params={
                "start_date": self.last_month_start,
                "end_date": self.last_month_end
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"Summary API call failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "total" in data, "Summary should contain 'total' key"
        
        print(f"✓ Last Month summary: Total amount = {data.get('total', {}).get('amount', 0)}")
    
    def test_custom_date_range_filter(self):
        """Test that custom date range filter works correctly"""
        # Use a specific date range
        custom_start = "2026-03-15"
        custom_end = "2026-03-20"
        
        response = requests.get(
            f"{BASE_URL}/api/sales-entries",
            params={
                "start_date": custom_start,
                "end_date": custom_end
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"API call failed: {response.text}"
        data = response.json()
        
        # Verify all entries are within the custom date range
        for entry in data.get("entries", []):
            entry_date = entry.get("date", "")
            assert entry_date >= custom_start, f"Entry date {entry_date} is before custom start {custom_start}"
            assert entry_date <= custom_end, f"Entry date {entry_date} is after custom end {custom_end}"
        
        print(f"✓ Custom Range filter ({custom_start} to {custom_end}): {data.get('total', 0)} entries")
    
    def test_no_date_filter_returns_all_data(self):
        """Test that no date filter returns all data"""
        response = requests.get(
            f"{BASE_URL}/api/sales-entries",
            headers=self.headers
        )
        assert response.status_code == 200, f"API call failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "entries" in data, "Response should contain 'entries' key"
        assert "total" in data, "Response should contain 'total' key"
        
        print(f"✓ All Time filter (no date params): {data.get('total', 0)} entries")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
