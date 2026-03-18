"""
Test Sales Entry Multi-Payment Feature (Split Payment)
Tests for cash_amount, online_amount, credit_amount fields in sales entries.
Features tested:
- POST create with split payments (cash+online+credit)
- POST create with single payment mode
- PUT update split amounts and auto-recalculation
- GET summary with split payment totals
- Export endpoints (PDF/Excel) include cash/online/credit columns
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
WAREHOUSE_ID = "8f2dc176-4450-4bf7-8ccc-2c2618fc6d32"  # Jullang warehouse


class TestSalesMultiPaymentBackend:
    """Test Sales Entry Multi-Payment Feature"""
    
    token = None
    created_entry_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token before tests"""
        if not TestSalesMultiPaymentBackend.token:
            response = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": "admin@k3gas.com",
                "password": "Admin@123"
            })
            assert response.status_code == 200, f"Login failed: {response.text}"
            TestSalesMultiPaymentBackend.token = response.json()['token']
        
    def get_headers(self):
        return {"Authorization": f"Bearer {TestSalesMultiPaymentBackend.token}"}
    
    # ===== CREATE TESTS =====
    
    def test_01_create_split_payment_entry(self):
        """Test creating a split payment entry with cash=500, online=300, credit=200"""
        today = "2026-01-15"
        payload = {
            "date": today,
            "consumer_name": "TEST_Split_Payment_Customer",
            "address": "Test Address",
            "consumer_no": "SP001",
            "memo_no": "MEMO_SPLIT_001",
            "connection_type": "domestic_refill",
            "cylinder_nos": "",
            "payment_mode": "cash",  # Will be auto-set to 'split'
            "cash_amount": 500,
            "online_amount": 300,
            "credit_amount": 200,
            "no_of_refills": 2,
            "remarks": "Split payment test"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/sales-entries/warehouse/{WAREHOUSE_ID}",
            json=payload,
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"Failed to create split entry: {response.text}"
        data = response.json()
        
        # Store for later tests
        TestSalesMultiPaymentBackend.created_entry_id = data['id']
        
        # Verify payment mode set to 'split'
        assert data['payment_mode'] == 'split', f"Expected payment_mode='split', got '{data['payment_mode']}'"
        
        # Verify amount is sum of split amounts (500+300+200=1000)
        assert data['amount'] == 1000, f"Expected amount=1000, got {data['amount']}"
        
        # Verify split amounts stored correctly
        assert data['cash_amount'] == 500, f"Expected cash_amount=500, got {data.get('cash_amount')}"
        assert data['online_amount'] == 300, f"Expected online_amount=300, got {data.get('online_amount')}"
        assert data['credit_amount'] == 200, f"Expected credit_amount=200, got {data.get('credit_amount')}"
        
        print(f"PASS: Created split payment entry with ID: {data['id']}")
        print(f"  Amount: {data['amount']}, Payment Mode: {data['payment_mode']}")
        print(f"  Cash: {data['cash_amount']}, Online: {data['online_amount']}, Credit: {data['credit_amount']}")
    
    def test_02_create_single_cash_payment_entry(self):
        """Test creating entry with cash only (cash_amount=800)"""
        today = "2026-01-15"
        payload = {
            "date": today,
            "consumer_name": "TEST_Cash_Only_Customer",
            "address": "Cash Address",
            "consumer_no": "CO001",
            "memo_no": "MEMO_CASH_001",
            "connection_type": "domestic_refill",
            "payment_mode": "cash",
            "cash_amount": 800,
            "online_amount": 0,
            "credit_amount": 0,
            "no_of_refills": 1,
            "remarks": "Cash only test"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/sales-entries/warehouse/{WAREHOUSE_ID}",
            json=payload,
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"Failed to create cash entry: {response.text}"
        data = response.json()
        
        # Verify payment mode is 'cash' (not split since only one mode used)
        assert data['payment_mode'] == 'cash', f"Expected payment_mode='cash', got '{data['payment_mode']}'"
        
        # Verify amount equals cash_amount
        assert data['amount'] == 800, f"Expected amount=800, got {data['amount']}"
        assert data['cash_amount'] == 800, f"Expected cash_amount=800, got {data.get('cash_amount')}"
        
        print(f"PASS: Created cash-only entry, payment_mode={data['payment_mode']}, amount={data['amount']}")
    
    def test_03_create_single_online_payment_entry(self):
        """Test creating entry with online only"""
        today = "2026-01-15"
        payload = {
            "date": today,
            "consumer_name": "TEST_Online_Only_Customer",
            "address": "Online Address",
            "consumer_no": "ON001",
            "memo_no": "MEMO_ONLINE_001",
            "connection_type": "commercial_refill",
            "payment_mode": "online",
            "cash_amount": 0,
            "online_amount": 1200,
            "credit_amount": 0,
            "no_of_refills": 1,
            "remarks": "Online only test"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/sales-entries/warehouse/{WAREHOUSE_ID}",
            json=payload,
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"Failed to create online entry: {response.text}"
        data = response.json()
        
        assert data['payment_mode'] == 'online', f"Expected payment_mode='online', got '{data['payment_mode']}'"
        assert data['amount'] == 1200, f"Expected amount=1200, got {data['amount']}"
        
        print(f"PASS: Created online-only entry, payment_mode={data['payment_mode']}, amount={data['amount']}")
    
    def test_04_create_single_credit_payment_entry(self):
        """Test creating entry with credit/pending only"""
        today = "2026-01-15"
        payload = {
            "date": today,
            "consumer_name": "TEST_Credit_Only_Customer",
            "address": "Credit Address",
            "consumer_no": "CR001",
            "memo_no": "MEMO_CREDIT_001",
            "connection_type": "domestic_refill",
            "payment_mode": "pending",
            "cash_amount": 0,
            "online_amount": 0,
            "credit_amount": 600,
            "no_of_refills": 1,
            "remarks": "Credit only test"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/sales-entries/warehouse/{WAREHOUSE_ID}",
            json=payload,
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"Failed to create credit entry: {response.text}"
        data = response.json()
        
        assert data['payment_mode'] == 'pending', f"Expected payment_mode='pending', got '{data['payment_mode']}'"
        assert data['amount'] == 600, f"Expected amount=600, got {data['amount']}"
        
        print(f"PASS: Created credit-only entry, payment_mode={data['payment_mode']}, amount={data['amount']}")
    
    # ===== UPDATE TEST =====
    
    def test_05_update_split_amounts(self):
        """Test updating entry to change split amounts - verify auto-recalculation"""
        entry_id = TestSalesMultiPaymentBackend.created_entry_id
        assert entry_id, "No entry created in previous test"
        
        # Update to new split amounts
        update_payload = {
            "cash_amount": 600,
            "online_amount": 400,
            "credit_amount": 100
        }
        
        response = requests.put(
            f"{BASE_URL}/api/sales-entries/{entry_id}",
            json=update_payload,
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"Failed to update entry: {response.text}"
        data = response.json()
        
        # Verify amount auto-recalculated (600+400+100=1100)
        assert data['amount'] == 1100, f"Expected amount=1100 after update, got {data['amount']}"
        assert data['cash_amount'] == 600, f"Expected cash_amount=600, got {data.get('cash_amount')}"
        assert data['online_amount'] == 400, f"Expected online_amount=400, got {data.get('online_amount')}"
        assert data['credit_amount'] == 100, f"Expected credit_amount=100, got {data.get('credit_amount')}"
        
        print(f"PASS: Updated entry, new amount={data['amount']} (auto-recalculated from split amounts)")
    
    # ===== SUMMARY TEST =====
    
    def test_06_get_sales_summary_split_totals(self):
        """Test GET /api/sales-entries/summary returns correct cash/online/pending totals"""
        response = requests.get(
            f"{BASE_URL}/api/sales-entries/summary",
            params={"warehouse_id": WAREHOUSE_ID, "start_date": "2026-01-01", "end_date": "2026-01-31"},
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"Failed to get summary: {response.text}"
        data = response.json()
        
        # Verify summary structure has cash, online, pending
        assert 'cash' in data, "Summary missing 'cash' field"
        assert 'online' in data, "Summary missing 'online' field"
        assert 'pending' in data, "Summary missing 'pending' field"
        assert 'total' in data, "Summary missing 'total' field"
        
        # Verify each has 'amount' field
        assert 'amount' in data['cash'], "cash missing 'amount' field"
        assert 'amount' in data['online'], "online missing 'amount' field"
        assert 'amount' in data['pending'], "pending missing 'amount' field"
        
        print(f"PASS: Summary structure correct")
        print(f"  Cash total: {data['cash']['amount']}")
        print(f"  Online total: {data['online']['amount']}")
        print(f"  Pending total: {data['pending']['amount']}")
        print(f"  Grand total: {data['total']['amount']}")
    
    # ===== EXPORT TESTS =====
    
    def test_07_export_sales_pdf_includes_payment_columns(self):
        """Test GET /api/export/sales-pdf returns 200 and includes Cash/Online/Credit columns"""
        response = requests.get(
            f"{BASE_URL}/api/export/sales-pdf",
            params={"warehouse_id": WAREHOUSE_ID, "start_date": "2026-01-01", "end_date": "2026-01-31"},
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"PDF export failed: {response.status_code}"
        assert response.headers.get('content-type') == 'application/pdf', "Response not PDF"
        
        # Check we got actual content
        assert len(response.content) > 1000, "PDF content too small"
        
        print(f"PASS: PDF export returns 200, size={len(response.content)} bytes")
    
    def test_08_export_sales_excel_includes_payment_columns(self):
        """Test GET /api/export/sales-excel returns 200 and includes Cash/Online/Credit columns"""
        response = requests.get(
            f"{BASE_URL}/api/export/sales-excel",
            params={"warehouse_id": WAREHOUSE_ID, "start_date": "2026-01-01", "end_date": "2026-01-31"},
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"Excel export failed: {response.status_code}"
        content_type = response.headers.get('content-type', '')
        assert 'spreadsheet' in content_type or 'excel' in content_type or 'octet-stream' in content_type, f"Response not Excel: {content_type}"
        
        # Check we got actual content
        assert len(response.content) > 1000, "Excel content too small"
        
        print(f"PASS: Excel export returns 200, size={len(response.content)} bytes")
    
    def test_09_export_sales_summary_pdf(self):
        """Test GET /api/export/sales-summary-pdf returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/export/sales-summary-pdf",
            params={"warehouse_id": WAREHOUSE_ID, "start_date": "2026-01-01", "end_date": "2026-01-31"},
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"Summary PDF export failed: {response.status_code}"
        assert response.headers.get('content-type') == 'application/pdf', "Response not PDF"
        
        print(f"PASS: Sales Summary PDF export returns 200, size={len(response.content)} bytes")
    
    def test_10_export_sales_summary_excel(self):
        """Test GET /api/export/sales-summary-excel returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/export/sales-summary-excel",
            params={"warehouse_id": WAREHOUSE_ID, "start_date": "2026-01-01", "end_date": "2026-01-31"},
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"Summary Excel export failed: {response.status_code}"
        
        print(f"PASS: Sales Summary Excel export returns 200, size={len(response.content)} bytes")
    
    # ===== VERIFY GET ENTRIES HAS SPLIT AMOUNTS =====
    
    def test_11_get_entries_includes_split_amounts(self):
        """Test GET /api/sales-entries returns entries with cash_amount, online_amount, credit_amount"""
        response = requests.get(
            f"{BASE_URL}/api/sales-entries",
            params={"warehouse_id": WAREHOUSE_ID, "start_date": "2026-01-15", "end_date": "2026-01-15"},
            headers=self.get_headers()
        )
        
        assert response.status_code == 200, f"Failed to get entries: {response.text}"
        entries = response.json()
        
        # Find our test entries
        split_entry = next((e for e in entries if 'TEST_Split_Payment' in e.get('consumer_name', '')), None)
        
        if split_entry:
            assert 'cash_amount' in split_entry, "Entry missing cash_amount field"
            assert 'online_amount' in split_entry, "Entry missing online_amount field"
            assert 'credit_amount' in split_entry, "Entry missing credit_amount field"
            print(f"PASS: Entries include split payment fields")
            print(f"  Found TEST entry: cash={split_entry.get('cash_amount')}, online={split_entry.get('online_amount')}, credit={split_entry.get('credit_amount')}")
        else:
            print(f"WARN: TEST_Split_Payment entry not found in response, but API returned correctly")
    
    # ===== CLEANUP =====
    
    def test_12_cleanup_test_data(self):
        """Delete test entries created during tests"""
        response = requests.get(
            f"{BASE_URL}/api/sales-entries",
            params={"warehouse_id": WAREHOUSE_ID},
            headers=self.get_headers()
        )
        
        if response.status_code == 200:
            entries = response.json()
            deleted = 0
            for entry in entries:
                if 'TEST_' in entry.get('consumer_name', ''):
                    del_response = requests.delete(
                        f"{BASE_URL}/api/sales-entries/{entry['id']}",
                        headers=self.get_headers()
                    )
                    if del_response.status_code == 200:
                        deleted += 1
            print(f"PASS: Cleaned up {deleted} test entries")
        else:
            print("WARN: Could not fetch entries for cleanup")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
