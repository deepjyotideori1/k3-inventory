"""
Order Status Tracking Feature Tests - K3 GAS SERVICE
Tests the new status tracking feature: Pending → Delivered
"""
import pytest
import requests
import os

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://k3-export-preview.preview.emergentagent.com"


class TestOrderStatusTracking:
    """Test Order Status Tracking Feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and setup test context"""
        # Login as Jullang Manager
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "jullang@k3gas.com", "password": "Jullang@123"}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data['token']
        self.headers = {"Authorization": f"Bearer {self.token}"}
        yield
    
    def test_get_order_summary_includes_status_counts(self):
        """Test that order summary includes pending and delivered counts"""
        response = requests.get(
            f"{BASE_URL}/api/orders/summary/stats",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify status-related fields exist
        assert 'total_orders' in data
        assert 'total_pending' in data
        assert 'total_delivered' in data
        
        # Verify counts are integers
        assert isinstance(data['total_pending'], int)
        assert isinstance(data['total_delivered'], int)
        
        # Verify total = pending + delivered
        assert data['total_orders'] == data['total_pending'] + data['total_delivered']
        
        print(f"✓ Summary: Total={data['total_orders']}, Pending={data['total_pending']}, Delivered={data['total_delivered']}")
    
    def test_orders_list_includes_status_field(self):
        """Test that orders list includes status field"""
        response = requests.get(
            f"{BASE_URL}/api/orders",
            headers=self.headers
        )
        assert response.status_code == 200
        orders = response.json()
        
        assert len(orders) > 0, "No orders found"
        
        for order in orders:
            assert 'status' in order, f"Order {order.get('order_no')} missing status field"
            assert order['status'] in ['pending', 'delivered'], f"Invalid status: {order['status']}"
        
        print(f"✓ All {len(orders)} orders have valid status field")
    
    def test_filter_orders_by_pending_status(self):
        """Test filtering orders by status=pending"""
        response = requests.get(
            f"{BASE_URL}/api/orders?status=pending",
            headers=self.headers
        )
        assert response.status_code == 200
        orders = response.json()
        
        for order in orders:
            assert order['status'] == 'pending', f"Order {order['order_no']} has status {order['status']}, expected pending"
        
        print(f"✓ Filter by pending returned {len(orders)} orders, all with status='pending'")
    
    def test_filter_orders_by_delivered_status(self):
        """Test filtering orders by status=delivered"""
        response = requests.get(
            f"{BASE_URL}/api/orders?status=delivered",
            headers=self.headers
        )
        assert response.status_code == 200
        orders = response.json()
        
        for order in orders:
            assert order['status'] == 'delivered', f"Order {order['order_no']} has status {order['status']}, expected delivered"
        
        print(f"✓ Filter by delivered returned {len(orders)} orders, all with status='delivered'")
    
    def test_update_order_status_pending_to_delivered(self):
        """Test PATCH /orders/{id}/status - change from pending to delivered"""
        # Get a pending order
        response = requests.get(
            f"{BASE_URL}/api/orders?status=pending",
            headers=self.headers
        )
        assert response.status_code == 200
        orders = response.json()
        assert len(orders) > 0, "No pending orders to test"
        
        test_order = orders[0]
        order_id = test_order['id']
        order_no = test_order['order_no']
        
        # Get initial summary
        initial_summary = requests.get(f"{BASE_URL}/api/orders/summary/stats", headers=self.headers).json()
        initial_pending = initial_summary['total_pending']
        initial_delivered = initial_summary['total_delivered']
        
        # Update status to delivered
        response = requests.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "delivered"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response
        assert data['status'] == 'delivered'
        assert 'delivered_at' in data and data['delivered_at'] is not None
        assert data['message'] == f"Order {order_no} marked as delivered"
        
        # Verify summary counts updated
        updated_summary = requests.get(f"{BASE_URL}/api/orders/summary/stats", headers=self.headers).json()
        assert updated_summary['total_pending'] == initial_pending - 1
        assert updated_summary['total_delivered'] == initial_delivered + 1
        
        print(f"✓ Updated order {order_no} from pending to delivered")
        print(f"  Summary: Pending {initial_pending}→{updated_summary['total_pending']}, Delivered {initial_delivered}→{updated_summary['total_delivered']}")
        
        # Revert back to pending for other tests
        requests.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "pending"},
            headers=self.headers
        )
    
    def test_update_order_status_delivered_to_pending(self):
        """Test PATCH /orders/{id}/status - change from delivered to pending"""
        # Get a delivered order
        response = requests.get(
            f"{BASE_URL}/api/orders?status=delivered",
            headers=self.headers
        )
        assert response.status_code == 200
        orders = response.json()
        
        if len(orders) == 0:
            pytest.skip("No delivered orders to test reverting")
        
        test_order = orders[0]
        order_id = test_order['id']
        order_no = test_order['order_no']
        
        # Update status to pending
        response = requests.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "pending"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response
        assert data['status'] == 'pending'
        assert data['delivered_at'] is None  # delivered_at should be cleared
        
        print(f"✓ Reverted order {order_no} from delivered to pending")
        
        # Revert back to delivered
        requests.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "delivered"},
            headers=self.headers
        )
    
    def test_update_status_invalid_value(self):
        """Test PATCH with invalid status value returns 400"""
        # Get any order
        response = requests.get(f"{BASE_URL}/api/orders", headers=self.headers)
        orders = response.json()
        assert len(orders) > 0
        
        order_id = orders[0]['id']
        
        # Try invalid status
        response = requests.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "invalid_status"},
            headers=self.headers
        )
        assert response.status_code == 400
        assert "Invalid status" in response.json()['detail']
        
        print("✓ Invalid status value correctly rejected with 400")
    
    def test_update_status_nonexistent_order(self):
        """Test PATCH for non-existent order returns 404"""
        response = requests.patch(
            f"{BASE_URL}/api/orders/nonexistent-order-id/status",
            json={"status": "delivered"},
            headers=self.headers
        )
        assert response.status_code == 404
        
        print("✓ Non-existent order correctly returns 404")
    
    def test_new_order_starts_with_pending_status(self):
        """Test that newly created orders have status='pending'"""
        # Create a test order
        response = requests.post(
            f"{BASE_URL}/api/orders",
            json={
                "order_date": "2026-02-23",
                "customer_name": "TEST_StatusCheck",
                "mobile_number": "1234567890",
                "address_landmark": "Test Address",
                "connection_type": "domestic",
                "payment_mode": "cash",
                "remarks": "Testing status default"
            },
            headers=self.headers
        )
        assert response.status_code == 200
        order = response.json()
        
        # Verify status is pending
        assert order['status'] == 'pending', f"New order should have status='pending', got '{order['status']}'"
        
        print(f"✓ New order {order['order_no']} created with status='pending'")
        
        # Cleanup - get admin token to delete
        admin_login = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@k3gas.com", "password": "Admin@123"}
        )
        if admin_login.status_code == 200:
            admin_token = admin_login.json()['token']
            requests.delete(
                f"{BASE_URL}/api/orders/{order['id']}",
                headers={"Authorization": f"Bearer {admin_token}"}
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
