"""
Test suite for Order Analysis feature in Admin Dashboard
Tests: /api/admin/order-analysis, /api/export/order-analysis-pdf, /api/export/order-analysis-excel
Also tests 403 Forbidden for non-admin users
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://unified-checkout-8.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_CREDS = {"email": "admin@k3gas.com", "password": "Admin@123"}
WAREHOUSE_MANAGER_CREDS = {"email": "jullang@k3gas.com", "password": "Jullang@123"}


class TestOrderAnalysisAuthentication:
    """Test authentication and authorization for order analysis endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get tokens for admin and warehouse manager"""
        # Admin login
        resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert resp.status_code == 200, f"Admin login failed: {resp.text}"
        self.admin_token = resp.json()['token']
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        # Warehouse manager login
        resp = requests.post(f"{BASE_URL}/api/auth/login", json=WAREHOUSE_MANAGER_CREDS)
        assert resp.status_code == 200, f"Warehouse manager login failed: {resp.text}"
        self.wm_token = resp.json()['token']
        self.wm_headers = {"Authorization": f"Bearer {self.wm_token}"}
    
    def test_admin_can_access_order_analysis(self):
        """Admin should be able to access order analysis"""
        resp = requests.get(f"{BASE_URL}/api/admin/order-analysis", headers=self.admin_headers)
        assert resp.status_code == 200, f"Admin access denied: {resp.text}"
        data = resp.json()
        assert 'groups' in data, "Response missing 'groups' field"
        assert 'summary' in data, "Response missing 'summary' field"
        print(f"TEST PASSED: Admin can access order analysis - {len(data.get('groups', []))} date groups found")
    
    def test_warehouse_manager_gets_403_on_order_analysis(self):
        """Non-admin (warehouse manager) should get 403 Forbidden"""
        resp = requests.get(f"{BASE_URL}/api/admin/order-analysis", headers=self.wm_headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print("TEST PASSED: Warehouse manager correctly blocked with 403 on order-analysis")
    
    def test_warehouse_manager_gets_403_on_order_analysis_pdf(self):
        """Non-admin should get 403 on PDF export"""
        resp = requests.get(f"{BASE_URL}/api/export/order-analysis-pdf", headers=self.wm_headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        print("TEST PASSED: Warehouse manager correctly blocked with 403 on order-analysis-pdf")
    
    def test_warehouse_manager_gets_403_on_order_analysis_excel(self):
        """Non-admin should get 403 on Excel export"""
        resp = requests.get(f"{BASE_URL}/api/export/order-analysis-excel", headers=self.wm_headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        print("TEST PASSED: Warehouse manager correctly blocked with 403 on order-analysis-excel")
    
    def test_unauthenticated_gets_401(self):
        """Unauthenticated request should get 401"""
        resp = requests.get(f"{BASE_URL}/api/admin/order-analysis")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print("TEST PASSED: Unauthenticated request correctly rejected")


class TestOrderAnalysisDataStructure:
    """Test the structure and data of order analysis response"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert resp.status_code == 200
        self.token = resp.json()['token']
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_order_analysis_response_structure(self):
        """Verify the response structure matches expected format"""
        resp = requests.get(f"{BASE_URL}/api/admin/order-analysis", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        # Check top-level structure
        assert 'groups' in data, "Missing 'groups' in response"
        assert 'summary' in data, "Missing 'summary' in response"
        
        # Check summary structure
        summary = data['summary']
        assert 'total_orders' in summary, "Missing 'total_orders' in summary"
        assert 'total_quantity' in summary, "Missing 'total_quantity' in summary"
        assert 'total_pending' in summary, "Missing 'total_pending' in summary"
        assert 'total_delivered' in summary, "Missing 'total_delivered' in summary"
        assert 'warehouse_breakdown' in summary, "Missing 'warehouse_breakdown' in summary"
        
        print(f"TEST PASSED: Order analysis response structure correct")
        print(f"  - Total Orders: {summary['total_orders']}")
        print(f"  - Total Quantity: {summary['total_quantity']}")
        print(f"  - Pending: {summary['total_pending']}, Delivered: {summary['total_delivered']}")
        print(f"  - Warehouse breakdown: {summary['warehouse_breakdown']}")
    
    def test_date_groups_are_descending(self):
        """Verify date groups are sorted in descending order"""
        resp = requests.get(f"{BASE_URL}/api/admin/order-analysis", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        groups = data['groups']
        if len(groups) >= 2:
            dates = [g['date'] for g in groups]
            assert dates == sorted(dates, reverse=True), "Dates should be in descending order"
            print(f"TEST PASSED: Date groups correctly sorted descending ({dates[0]} > {dates[-1]})")
        else:
            print(f"TEST PASSED: Only {len(groups)} date group(s), skipping sort check")
    
    def test_order_entries_have_required_fields(self):
        """Verify each order entry has all required fields"""
        resp = requests.get(f"{BASE_URL}/api/admin/order-analysis", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        required_fields = ['id', 'order_no', 'customer_name', 'product', 'quantity', 
                           'status', 'payment_mode', 'warehouse_name']
        
        for group in data['groups'][:3]:  # Check first 3 groups
            for order in group['orders'][:5]:  # Check first 5 orders per group
                for field in required_fields:
                    assert field in order, f"Missing '{field}' in order entry"
        
        print(f"TEST PASSED: Order entries have all required fields")


class TestOrderAnalysisFilters:
    """Test various filter combinations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin and get warehouses"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert resp.status_code == 200
        self.token = resp.json()['token']
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Get warehouses for testing
        resp = requests.get(f"{BASE_URL}/api/warehouses", headers=self.headers)
        if resp.status_code == 200:
            self.warehouses = [w for w in resp.json() if not w.get('is_plant')]
        else:
            self.warehouses = []
    
    def test_filter_by_warehouse(self):
        """Test warehouse filter"""
        if not self.warehouses:
            pytest.skip("No warehouses found")
        
        warehouse_id = self.warehouses[0]['id']
        warehouse_name = self.warehouses[0]['name']
        
        resp = requests.get(f"{BASE_URL}/api/admin/order-analysis", 
                           params={'warehouse_id': warehouse_id}, headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        # All orders should be from this warehouse
        for group in data['groups']:
            for order in group['orders']:
                assert order['warehouse_id'] == warehouse_id or order['warehouse_name'] == warehouse_name, \
                    f"Order {order['order_no']} is from wrong warehouse"
        
        print(f"TEST PASSED: Warehouse filter works correctly for '{warehouse_name}'")
    
    def test_filter_by_status_pending(self):
        """Test status filter for pending orders"""
        resp = requests.get(f"{BASE_URL}/api/admin/order-analysis", 
                           params={'status': 'pending'}, headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        for group in data['groups']:
            for order in group['orders']:
                assert order['status'] == 'pending', f"Order {order['order_no']} is not pending"
        
        print(f"TEST PASSED: Status filter 'pending' works - {data['summary']['total_orders']} pending orders")
    
    def test_filter_by_status_delivered(self):
        """Test status filter for delivered orders"""
        resp = requests.get(f"{BASE_URL}/api/admin/order-analysis", 
                           params={'status': 'delivered'}, headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        for group in data['groups']:
            for order in group['orders']:
                assert order['status'] == 'delivered', f"Order {order['order_no']} is not delivered"
        
        print(f"TEST PASSED: Status filter 'delivered' works - {data['summary']['total_orders']} delivered orders")
    
    def test_filter_by_date_range(self):
        """Test date range filter"""
        today = "2026-03-17"
        week_ago = "2026-03-10"
        
        resp = requests.get(f"{BASE_URL}/api/admin/order-analysis", 
                           params={'start_date': week_ago, 'end_date': today}, headers=self.headers)
        assert resp.status_code == 200
        print(f"TEST PASSED: Date range filter accepted ({week_ago} to {today})")
    
    def test_search_filter(self):
        """Test search functionality"""
        # First get some orders to know what to search for
        resp = requests.get(f"{BASE_URL}/api/admin/order-analysis", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        
        if data['groups'] and data['groups'][0]['orders']:
            search_term = data['groups'][0]['orders'][0].get('customer_name', '')[:4]
            if search_term:
                resp = requests.get(f"{BASE_URL}/api/admin/order-analysis", 
                                   params={'search': search_term}, headers=self.headers)
                assert resp.status_code == 200
                print(f"TEST PASSED: Search filter works with term '{search_term}'")
            else:
                print("TEST PASSED: Search filter accepts empty search")
        else:
            print("TEST PASSED: No orders to search")


class TestOrderAnalysisExports:
    """Test PDF and Excel export endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert resp.status_code == 200
        self.token = resp.json()['token']
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_export_pdf_returns_pdf_content_type(self):
        """PDF export should return application/pdf"""
        resp = requests.get(f"{BASE_URL}/api/export/order-analysis-pdf", headers=self.headers)
        assert resp.status_code == 200, f"PDF export failed: {resp.status_code}"
        assert 'pdf' in resp.headers.get('content-type', '').lower(), \
            f"Expected PDF content-type, got {resp.headers.get('content-type')}"
        assert len(resp.content) > 0, "PDF content is empty"
        print(f"TEST PASSED: PDF export returns valid PDF ({len(resp.content)} bytes)")
    
    def test_export_excel_returns_excel_content_type(self):
        """Excel export should return spreadsheetml"""
        resp = requests.get(f"{BASE_URL}/api/export/order-analysis-excel", headers=self.headers)
        assert resp.status_code == 200, f"Excel export failed: {resp.status_code}"
        assert 'spreadsheet' in resp.headers.get('content-type', '').lower() or \
               'application/vnd' in resp.headers.get('content-type', '').lower(), \
            f"Expected Excel content-type, got {resp.headers.get('content-type')}"
        assert len(resp.content) > 0, "Excel content is empty"
        print(f"TEST PASSED: Excel export returns valid Excel ({len(resp.content)} bytes)")
    
    def test_export_pdf_with_filters(self):
        """PDF export with filters should work"""
        params = {'status': 'pending'}
        resp = requests.get(f"{BASE_URL}/api/export/order-analysis-pdf", 
                           params=params, headers=self.headers)
        assert resp.status_code == 200, f"PDF export with filters failed: {resp.status_code}"
        print("TEST PASSED: PDF export with status filter works")
    
    def test_export_excel_with_filters(self):
        """Excel export with filters should work"""
        params = {'status': 'delivered'}
        resp = requests.get(f"{BASE_URL}/api/export/order-analysis-excel", 
                           params=params, headers=self.headers)
        assert resp.status_code == 200, f"Excel export with filters failed: {resp.status_code}"
        print("TEST PASSED: Excel export with status filter works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
