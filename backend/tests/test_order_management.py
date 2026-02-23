"""
Test Order Management Feature for K3 GAS SERVICE
Tests:
- Order creation with auto-generated sequence numbers (A1, A2...)
- Plant Hollongi exclusion from orders
- Order filtering (date, payment mode, connection type, search)
- Order CRUD operations
- Order exports (PDF, Excel)
- Admin vs Manager permissions
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASSWORD = "Admin@123"

JULLANG_EMAIL = "jullang@k3gas.com"
JULLANG_PASSWORD = "Jullang@123"

HOLLONGI_EMAIL = "hollongi@k3gas.com"
HOLLONGI_PASSWORD = "Hollongi@123"


class TestOrderManagement:
    """Order Management endpoint tests"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        """Login as admin and return session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        
        data = response.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        session.user = data['user']
        return session
    
    @pytest.fixture(scope="class")
    def jullang_session(self):
        """Login as Jullang manager and return session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": JULLANG_EMAIL,
            "password": JULLANG_PASSWORD
        })
        assert response.status_code == 200, f"Jullang login failed: {response.text}"
        
        data = response.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        session.user = data['user']
        return session
    
    @pytest.fixture(scope="class")
    def hollongi_session(self):
        """Login as Plant Hollongi manager and return session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": HOLLONGI_EMAIL,
            "password": HOLLONGI_PASSWORD
        })
        assert response.status_code == 200, f"Hollongi login failed: {response.text}"
        
        data = response.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        session.user = data['user']
        return session
    
    # ============ Authentication Tests ============
    
    def test_admin_login_success(self, admin_session):
        """Test admin login works"""
        assert admin_session.user['role'] == 'admin'
        assert admin_session.user['email'] == ADMIN_EMAIL
        print(f"SUCCESS: Admin login - {admin_session.user['name']}")
    
    def test_jullang_login_success(self, jullang_session):
        """Test Jullang manager login works"""
        assert jullang_session.user['role'] == 'warehouse_manager'
        assert jullang_session.user['warehouse_name'] == 'Jullang'
        print(f"SUCCESS: Jullang manager login - {jullang_session.user['name']}")
    
    def test_hollongi_login_success(self, hollongi_session):
        """Test Hollongi manager login works"""
        assert hollongi_session.user['role'] == 'warehouse_manager'
        assert hollongi_session.user['warehouse_name'] == 'Plant Hollongi'
        print(f"SUCCESS: Plant Hollongi manager login - {hollongi_session.user['name']}")
    
    # ============ Plant Hollongi Exclusion Tests ============
    
    def test_hollongi_cannot_create_order(self, hollongi_session):
        """Plant Hollongi should NOT be able to create orders"""
        order_data = {
            "order_date": datetime.now().strftime('%Y-%m-%d'),
            "customer_name": "TEST_Hollongi_Customer",
            "mobile_number": "9999999999",
            "address_landmark": "Test Address",
            "connection_type": "domestic",
            "payment_mode": "cash",
            "remarks": "Test order"
        }
        
        response = hollongi_session.post(f"{BASE_URL}/api/orders", json=order_data)
        assert response.status_code == 403, f"Expected 403 for Hollongi, got {response.status_code}"
        
        data = response.json()
        assert "Plant Hollongi" in data.get('detail', ''), f"Expected Plant Hollongi error, got: {data}"
        print("SUCCESS: Plant Hollongi correctly blocked from creating orders")
    
    # ============ Order Creation Tests ============
    
    def test_jullang_create_order_auto_sequence(self, jullang_session):
        """Test Jullang manager can create order with auto-generated sequence"""
        order_data = {
            "order_date": datetime.now().strftime('%Y-%m-%d'),
            "customer_name": "TEST_Customer_Order_1",
            "mobile_number": "8888888881",
            "address_landmark": "Test Address 1",
            "connection_type": "domestic",
            "payment_mode": "cash",
            "remarks": "First test order"
        }
        
        response = jullang_session.post(f"{BASE_URL}/api/orders", json=order_data)
        assert response.status_code == 200, f"Failed to create order: {response.text}"
        
        data = response.json()
        assert 'order_no' in data, "Order number not returned"
        assert data['order_no'].startswith('A'), f"Order number should start with A, got: {data['order_no']}"
        assert data['customer_name'] == "TEST_Customer_Order_1"
        
        # Store order ID for later tests
        jullang_session.first_order_id = data['id']
        jullang_session.first_order_no = data['order_no']
        
        print(f"SUCCESS: Created order {data['order_no']} for Jullang warehouse")
        return data
    
    def test_jullang_create_second_order_sequence(self, jullang_session):
        """Test that second order gets next sequence number"""
        order_data = {
            "order_date": datetime.now().strftime('%Y-%m-%d'),
            "customer_name": "TEST_Customer_Order_2",
            "mobile_number": "8888888882",
            "address_landmark": "Test Address 2",
            "connection_type": "commercial",
            "payment_mode": "online",
            "remarks": "Second test order"
        }
        
        response = jullang_session.post(f"{BASE_URL}/api/orders", json=order_data)
        assert response.status_code == 200, f"Failed to create second order: {response.text}"
        
        data = response.json()
        assert data['order_no'].startswith('A'), "Order number should start with A"
        
        # Verify sequence incremented
        first_seq = int(jullang_session.first_order_no[1:])
        second_seq = int(data['order_no'][1:])
        assert second_seq > first_seq, f"Second order sequence should be higher: {second_seq} > {first_seq}"
        
        jullang_session.second_order_id = data['id']
        print(f"SUCCESS: Created second order {data['order_no']} (sequence incremented)")
    
    def test_jullang_create_order_credit_pending(self, jullang_session):
        """Test creating order with credit_pending payment mode"""
        order_data = {
            "order_date": datetime.now().strftime('%Y-%m-%d'),
            "customer_name": "TEST_Customer_Credit",
            "mobile_number": "8888888883",
            "address_landmark": "Credit Customer Address",
            "connection_type": "domestic",
            "payment_mode": "credit_pending",
            "remarks": "Credit pending test"
        }
        
        response = jullang_session.post(f"{BASE_URL}/api/orders", json=order_data)
        assert response.status_code == 200, f"Failed to create credit order: {response.text}"
        
        data = response.json()
        assert data['payment_mode'] == 'credit_pending'
        jullang_session.credit_order_id = data['id']
        print(f"SUCCESS: Created credit_pending order {data['order_no']}")
    
    # ============ Order Read Tests ============
    
    def test_jullang_get_orders(self, jullang_session):
        """Test Jullang manager can get their orders"""
        today = datetime.now().strftime('%Y-%m-%d')
        response = jullang_session.get(f"{BASE_URL}/api/orders", params={
            'start_date': today,
            'end_date': today
        })
        assert response.status_code == 200, f"Failed to get orders: {response.text}"
        
        orders = response.json()
        assert isinstance(orders, list), "Expected list of orders"
        
        # Should see at least the orders we created
        test_orders = [o for o in orders if o['customer_name'].startswith('TEST_')]
        assert len(test_orders) >= 3, f"Expected at least 3 test orders, found {len(test_orders)}"
        
        print(f"SUCCESS: Retrieved {len(orders)} orders for Jullang (including {len(test_orders)} test orders)")
    
    def test_hollongi_cannot_see_orders(self, hollongi_session):
        """Plant Hollongi should get empty orders list (or be blocked)"""
        today = datetime.now().strftime('%Y-%m-%d')
        response = hollongi_session.get(f"{BASE_URL}/api/orders", params={
            'start_date': today,
            'end_date': today
        })
        # Should either be blocked or return empty list
        if response.status_code == 200:
            orders = response.json()
            # Should not see Jullang's orders
            jullang_orders = [o for o in orders if 'Jullang' in o.get('warehouse_name', '')]
            assert len(jullang_orders) == 0, "Hollongi should not see Jullang orders"
            print(f"SUCCESS: Plant Hollongi sees {len(orders)} orders (only their own warehouse - which has 0)")
        else:
            print(f"SUCCESS: Plant Hollongi blocked from orders endpoint with status {response.status_code}")
    
    # ============ Filter Tests ============
    
    def test_filter_by_payment_mode_cash(self, jullang_session):
        """Test filtering orders by cash payment"""
        today = datetime.now().strftime('%Y-%m-%d')
        response = jullang_session.get(f"{BASE_URL}/api/orders", params={
            'start_date': today,
            'end_date': today,
            'payment_mode': 'cash'
        })
        assert response.status_code == 200
        
        orders = response.json()
        for order in orders:
            assert order['payment_mode'] == 'cash', f"Expected cash payment, got {order['payment_mode']}"
        
        print(f"SUCCESS: Filter by cash payment returned {len(orders)} orders")
    
    def test_filter_by_payment_mode_credit(self, jullang_session):
        """Test filtering orders by credit_pending payment"""
        today = datetime.now().strftime('%Y-%m-%d')
        response = jullang_session.get(f"{BASE_URL}/api/orders", params={
            'start_date': today,
            'end_date': today,
            'payment_mode': 'credit_pending'
        })
        assert response.status_code == 200
        
        orders = response.json()
        test_credit_orders = [o for o in orders if o['customer_name'].startswith('TEST_')]
        assert len(test_credit_orders) >= 1, "Expected at least 1 credit_pending test order"
        
        for order in orders:
            assert order['payment_mode'] == 'credit_pending'
        
        print(f"SUCCESS: Filter by credit_pending returned {len(orders)} orders")
    
    def test_filter_by_connection_domestic(self, jullang_session):
        """Test filtering orders by domestic connection type"""
        today = datetime.now().strftime('%Y-%m-%d')
        response = jullang_session.get(f"{BASE_URL}/api/orders", params={
            'start_date': today,
            'end_date': today,
            'connection_type': 'domestic'
        })
        assert response.status_code == 200
        
        orders = response.json()
        for order in orders:
            assert order['connection_type'] == 'domestic'
        
        print(f"SUCCESS: Filter by domestic returned {len(orders)} orders")
    
    def test_filter_by_connection_commercial(self, jullang_session):
        """Test filtering orders by commercial connection type"""
        today = datetime.now().strftime('%Y-%m-%d')
        response = jullang_session.get(f"{BASE_URL}/api/orders", params={
            'start_date': today,
            'end_date': today,
            'connection_type': 'commercial'
        })
        assert response.status_code == 200
        
        orders = response.json()
        test_commercial = [o for o in orders if o['customer_name'].startswith('TEST_')]
        assert len(test_commercial) >= 1, "Expected at least 1 commercial test order"
        
        for order in orders:
            assert order['connection_type'] == 'commercial'
        
        print(f"SUCCESS: Filter by commercial returned {len(orders)} orders")
    
    def test_search_by_customer_name(self, jullang_session):
        """Test search functionality by customer name"""
        today = datetime.now().strftime('%Y-%m-%d')
        response = jullang_session.get(f"{BASE_URL}/api/orders", params={
            'start_date': today,
            'end_date': today,
            'search': 'TEST_Customer_Order'
        })
        assert response.status_code == 200
        
        orders = response.json()
        assert len(orders) >= 2, f"Expected at least 2 orders matching search, got {len(orders)}"
        
        for order in orders:
            assert 'TEST_Customer_Order' in order['customer_name']
        
        print(f"SUCCESS: Search by customer name returned {len(orders)} matching orders")
    
    def test_search_by_order_no(self, jullang_session):
        """Test search functionality by order number"""
        today = datetime.now().strftime('%Y-%m-%d')
        order_no = jullang_session.first_order_no
        
        response = jullang_session.get(f"{BASE_URL}/api/orders", params={
            'start_date': today,
            'end_date': today,
            'search': order_no
        })
        assert response.status_code == 200
        
        orders = response.json()
        assert len(orders) >= 1, f"Expected at least 1 order matching order_no search"
        
        found = False
        for order in orders:
            if order['order_no'] == order_no:
                found = True
                break
        
        assert found, f"Order {order_no} not found in search results"
        print(f"SUCCESS: Search by order number {order_no} works")
    
    # ============ Order Summary Tests ============
    
    def test_order_summary_stats(self, jullang_session):
        """Test order summary statistics endpoint"""
        today = datetime.now().strftime('%Y-%m-%d')
        response = jullang_session.get(f"{BASE_URL}/api/orders/summary/stats", params={
            'start_date': today,
            'end_date': today
        })
        assert response.status_code == 200, f"Failed to get order summary: {response.text}"
        
        summary = response.json()
        assert 'total_orders' in summary
        assert 'total_domestic' in summary
        assert 'total_commercial' in summary
        assert 'total_cash' in summary
        assert 'total_online' in summary
        assert 'total_credit_pending' in summary
        
        # Verify we have some orders counted
        assert summary['total_orders'] >= 3, f"Expected at least 3 orders, got {summary['total_orders']}"
        
        print(f"SUCCESS: Order summary - Total: {summary['total_orders']}, "
              f"Domestic: {summary['total_domestic']}, Commercial: {summary['total_commercial']}, "
              f"Cash: {summary['total_cash']}, Online: {summary['total_online']}, Credit: {summary['total_credit_pending']}")
    
    # ============ Order Update Tests ============
    
    def test_jullang_edit_same_day_order(self, jullang_session):
        """Test manager can edit same-day orders"""
        order_id = jullang_session.first_order_id
        
        update_data = {
            "customer_name": "TEST_Customer_Order_1_Updated",
            "remarks": "Updated remarks",
            "payment_mode": "online"
        }
        
        response = jullang_session.put(f"{BASE_URL}/api/orders/{order_id}", json=update_data)
        assert response.status_code == 200, f"Failed to update order: {response.text}"
        
        data = response.json()
        assert data['customer_name'] == "TEST_Customer_Order_1_Updated"
        assert data['remarks'] == "Updated remarks"
        assert data['payment_mode'] == "online"
        
        print(f"SUCCESS: Manager updated same-day order {data['order_no']}")
    
    # ============ Order Get Single Tests ============
    
    def test_get_single_order(self, jullang_session):
        """Test getting a single order by ID"""
        order_id = jullang_session.first_order_id
        
        response = jullang_session.get(f"{BASE_URL}/api/orders/{order_id}")
        assert response.status_code == 200, f"Failed to get order: {response.text}"
        
        order = response.json()
        assert order['id'] == order_id
        assert order['order_no'] == jullang_session.first_order_no
        
        print(f"SUCCESS: Retrieved single order {order['order_no']}")
    
    # ============ Order PDF Tests ============
    
    def test_download_single_order_pdf(self, jullang_session):
        """Test downloading PDF for a single order"""
        order_id = jullang_session.first_order_id
        
        response = jullang_session.get(f"{BASE_URL}/api/orders/pdf/{order_id}")
        assert response.status_code == 200, f"Failed to download order PDF: {response.text}"
        assert 'application/pdf' in response.headers.get('Content-Type', '')
        assert len(response.content) > 0, "PDF content is empty"
        
        print(f"SUCCESS: Downloaded PDF for order (size: {len(response.content)} bytes)")
    
    # ============ Order Export Tests ============
    
    def test_export_orders_pdf(self, jullang_session):
        """Test exporting orders report to PDF"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        response = jullang_session.get(f"{BASE_URL}/api/export/orders-pdf", params={
            'start_date': today,
            'end_date': today
        })
        assert response.status_code == 200, f"Failed to export orders PDF: {response.text}"
        assert 'application/pdf' in response.headers.get('Content-Type', '')
        assert len(response.content) > 0, "PDF content is empty"
        
        print(f"SUCCESS: Exported orders PDF report (size: {len(response.content)} bytes)")
    
    def test_export_orders_excel(self, jullang_session):
        """Test exporting orders report to Excel"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        response = jullang_session.get(f"{BASE_URL}/api/export/orders-excel", params={
            'start_date': today,
            'end_date': today
        })
        assert response.status_code == 200, f"Failed to export orders Excel: {response.text}"
        assert 'spreadsheet' in response.headers.get('Content-Type', '')
        assert len(response.content) > 0, "Excel content is empty"
        
        print(f"SUCCESS: Exported orders Excel report (size: {len(response.content)} bytes)")
    
    # ============ Admin Tests ============
    
    def test_admin_create_order_for_warehouse(self, admin_session, jullang_session):
        """Test admin can create order for a specific warehouse"""
        warehouse_id = jullang_session.user['warehouse_id']
        
        order_data = {
            "order_date": datetime.now().strftime('%Y-%m-%d'),
            "customer_name": "TEST_Admin_Created_Order",
            "mobile_number": "7777777777",
            "address_landmark": "Admin Created Address",
            "connection_type": "commercial",
            "payment_mode": "online",
            "remarks": "Created by admin"
        }
        
        response = admin_session.post(f"{BASE_URL}/api/orders/warehouse/{warehouse_id}", json=order_data)
        assert response.status_code == 200, f"Admin failed to create order: {response.text}"
        
        data = response.json()
        assert data['order_no'].startswith('A')
        assert data['customer_name'] == "TEST_Admin_Created_Order"
        
        admin_session.admin_order_id = data['id']
        print(f"SUCCESS: Admin created order {data['order_no']} for Jullang warehouse")
    
    def test_admin_can_see_all_orders(self, admin_session):
        """Test admin can see orders from all warehouses"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        response = admin_session.get(f"{BASE_URL}/api/orders", params={
            'start_date': today,
            'end_date': today
        })
        assert response.status_code == 200, f"Admin failed to get orders: {response.text}"
        
        orders = response.json()
        assert isinstance(orders, list)
        
        # Admin should see orders with warehouse info
        if orders:
            assert 'warehouse_name' in orders[0]
        
        print(f"SUCCESS: Admin retrieved {len(orders)} orders across all warehouses")
    
    def test_admin_delete_order(self, admin_session):
        """Test admin can delete an order"""
        order_id = admin_session.admin_order_id
        
        response = admin_session.delete(f"{BASE_URL}/api/orders/{order_id}")
        assert response.status_code == 200, f"Admin failed to delete order: {response.text}"
        
        # Verify deletion
        response = admin_session.get(f"{BASE_URL}/api/orders/{order_id}")
        assert response.status_code == 404, "Deleted order should not be found"
        
        print("SUCCESS: Admin deleted order successfully")
    
    def test_manager_cannot_delete_order(self, jullang_session):
        """Test manager cannot delete orders"""
        order_id = jullang_session.second_order_id
        
        response = jullang_session.delete(f"{BASE_URL}/api/orders/{order_id}")
        assert response.status_code == 403, f"Expected 403 for manager delete, got {response.status_code}"
        
        print("SUCCESS: Manager correctly blocked from deleting orders")
    
    # ============ Get Warehouses for Admin ============
    
    def test_admin_get_warehouses_for_order(self, admin_session):
        """Test admin can get warehouses (excluding Plant Hollongi for orders)"""
        response = admin_session.get(f"{BASE_URL}/api/warehouses")
        assert response.status_code == 200, f"Failed to get warehouses: {response.text}"
        
        warehouses = response.json()
        assert isinstance(warehouses, list)
        assert len(warehouses) >= 4, "Expected at least 4 warehouses (including Plant Hollongi)"
        
        # Verify Plant Hollongi is marked as plant
        hollongi = None
        for w in warehouses:
            if 'Hollongi' in w['name']:
                hollongi = w
                break
        
        assert hollongi is not None, "Plant Hollongi not found"
        assert hollongi['is_plant'] == True, "Plant Hollongi should have is_plant=True"
        
        # Non-plant warehouses should be available for orders
        non_plant = [w for w in warehouses if not w['is_plant']]
        assert len(non_plant) >= 3, "Expected at least 3 non-plant warehouses"
        
        print(f"SUCCESS: Admin retrieved {len(warehouses)} warehouses ({len(non_plant)} non-plant)")
    
    # ============ Cleanup ============
    
    def test_cleanup_test_orders(self, admin_session):
        """Clean up test orders created during tests"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get all orders to find test ones
        response = admin_session.get(f"{BASE_URL}/api/orders", params={
            'start_date': today,
            'end_date': today
        })
        
        if response.status_code == 200:
            orders = response.json()
            test_orders = [o for o in orders if o['customer_name'].startswith('TEST_')]
            
            deleted_count = 0
            for order in test_orders:
                del_response = admin_session.delete(f"{BASE_URL}/api/orders/{order['id']}")
                if del_response.status_code == 200:
                    deleted_count += 1
            
            print(f"CLEANUP: Deleted {deleted_count} test orders")
        else:
            print("CLEANUP: Could not retrieve orders for cleanup")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
