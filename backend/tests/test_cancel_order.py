"""
Test Cancel Order Feature
Tests for:
- PATCH /api/orders/{id}/status with status=cancelled
- PUT /api/orders/{id} on cancelled order (should return 400)
- GET /api/orders/summary/stats includes total_cancelled
- GET /api/orders returns cancelled_at and cancellation_reason fields
- GET /api/orders?status=cancelled filter
- Admin can revert cancelled order back to pending
- Non-admin warehouse manager can cancel their own orders
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCancelOrder:
    """Cancel Order feature tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.admin_email = "admin@k3gas.com"
        self.admin_password = "Admin@123"
        self.manager_email = "jullang@k3gas.com"
        self.manager_password = "Jullang@123"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def get_admin_token(self):
        """Get admin auth token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.admin_email,
            "password": self.admin_password
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["token"]
        
    def get_manager_token(self):
        """Get warehouse manager auth token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.manager_email,
            "password": self.manager_password
        })
        assert response.status_code == 200, f"Manager login failed: {response.text}"
        return response.json()
    
    def create_test_order(self, token, warehouse_id=None):
        """Create a test order and return its ID"""
        headers = {"Authorization": f"Bearer {token}"}
        order_data = {
            "order_date": datetime.now().strftime("%Y-%m-%d"),
            "customer_name": f"TEST_Cancel_Customer_{uuid.uuid4().hex[:6]}",
            "mobile_number": "9876543210",
            "address_landmark": "Test Address",
            "connection_type": "domestic",
            "payment_mode": "cash",
            "remarks": "Test order for cancellation"
        }
        if warehouse_id:
            response = self.session.post(
                f"{BASE_URL}/api/orders/warehouse/{warehouse_id}",
                json=order_data,
                headers=headers
            )
        else:
            response = self.session.post(
                f"{BASE_URL}/api/orders",
                json=order_data,
                headers=headers
            )
        assert response.status_code == 201 or response.status_code == 200, f"Order creation failed: {response.text}"
        return response.json()
    
    # ==================== CANCEL ORDER STATUS TESTS ====================
    
    def test_patch_order_status_cancelled_with_reason(self):
        """Test PATCH /api/orders/{id}/status with status=cancelled and cancellation_reason"""
        # Login as manager
        login_resp = self.get_manager_token()
        token = login_resp["token"]
        warehouse_id = login_resp["user"].get("warehouse_id")
        
        # Create test order
        order = self.create_test_order(token)
        order_id = order["id"]
        
        # Cancel the order with reason
        headers = {"Authorization": f"Bearer {token}"}
        cancel_reason = "Customer requested cancellation"
        response = self.session.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "cancelled", "cancellation_reason": cancel_reason},
            headers=headers
        )
        
        assert response.status_code == 200, f"Cancel status failed: {response.text}"
        data = response.json()
        assert data["status"] == "cancelled"
        assert data.get("cancellation_reason") == cancel_reason
        assert data.get("cancelled_at") is not None
        print(f"PASS: Order cancelled with reason, cancelled_at={data.get('cancelled_at')}")
        
    def test_patch_order_status_cancelled_without_reason(self):
        """Test PATCH /api/orders/{id}/status with status=cancelled without reason"""
        login_resp = self.get_manager_token()
        token = login_resp["token"]
        
        order = self.create_test_order(token)
        order_id = order["id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        response = self.session.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "cancelled"},
            headers=headers
        )
        
        assert response.status_code == 200, f"Cancel status failed: {response.text}"
        data = response.json()
        assert data["status"] == "cancelled"
        assert data.get("cancelled_at") is not None
        print("PASS: Order cancelled without reason")
        
    def test_admin_revert_cancelled_to_pending(self):
        """Test admin can revert cancelled order back to pending"""
        # First cancel as manager
        login_resp = self.get_manager_token()
        manager_token = login_resp["token"]
        
        order = self.create_test_order(manager_token)
        order_id = order["id"]
        
        # Cancel the order
        headers = {"Authorization": f"Bearer {manager_token}"}
        self.session.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "cancelled"},
            headers=headers
        )
        
        # Now admin reverts to pending
        admin_token = self.get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = self.session.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "pending"},
            headers=headers
        )
        
        assert response.status_code == 200, f"Admin revert failed: {response.text}"
        data = response.json()
        assert data["status"] == "pending"
        assert data.get("cancelled_at") is None
        assert data.get("cancellation_reason") in [None, "", None]
        print("PASS: Admin successfully reverted cancelled order to pending")
        
    def test_nonadmin_cannot_modify_cancelled_order_status(self):
        """Test non-admin cannot modify cancelled order status"""
        login_resp = self.get_manager_token()
        token = login_resp["token"]
        
        order = self.create_test_order(token)
        order_id = order["id"]
        
        # Cancel the order first
        headers = {"Authorization": f"Bearer {token}"}
        self.session.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "cancelled"},
            headers=headers
        )
        
        # Try to change status as non-admin (should fail)
        response = self.session.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "pending"},
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("PASS: Non-admin cannot modify cancelled order status")
        
    # ==================== EDIT BLOCKED TESTS ====================
    
    def test_put_order_on_cancelled_returns_400(self):
        """Test PUT /api/orders/{id} on cancelled order returns 400"""
        login_resp = self.get_manager_token()
        token = login_resp["token"]
        
        order = self.create_test_order(token)
        order_id = order["id"]
        
        # Cancel the order first
        headers = {"Authorization": f"Bearer {token}"}
        self.session.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "cancelled"},
            headers=headers
        )
        
        # Try to edit the cancelled order (should fail)
        response = self.session.put(
            f"{BASE_URL}/api/orders/{order_id}",
            json={"customer_name": "Updated Name"},
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        assert "cancelled" in response.text.lower() or "cannot be edited" in response.text.lower()
        print("PASS: PUT on cancelled order returns 400 'Cancelled orders cannot be edited'")
    
    # ==================== SUMMARY STATS TESTS ====================
    
    def test_summary_stats_includes_total_cancelled(self):
        """Test GET /api/orders/summary/stats includes total_cancelled field"""
        token = self.get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        response = self.session.get(
            f"{BASE_URL}/api/orders/summary/stats",
            headers=headers
        )
        
        assert response.status_code == 200, f"Summary stats failed: {response.text}"
        data = response.json()
        
        assert "total_cancelled" in data, "total_cancelled field missing from summary stats"
        assert isinstance(data["total_cancelled"], int)
        print(f"PASS: Summary stats includes total_cancelled={data['total_cancelled']}")
        
    # ==================== GET ORDERS TESTS ====================
    
    def test_get_orders_returns_cancelled_fields(self):
        """Test GET /api/orders returns cancelled_at and cancellation_reason fields"""
        login_resp = self.get_manager_token()
        token = login_resp["token"]
        
        # Create and cancel an order
        order = self.create_test_order(token)
        order_id = order["id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        cancel_reason = "Test cancellation reason"
        self.session.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "cancelled", "cancellation_reason": cancel_reason},
            headers=headers
        )
        
        # Get orders
        response = self.session.get(
            f"{BASE_URL}/api/orders",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get orders failed: {response.text}"
        orders = response.json()
        
        # Find our cancelled order
        cancelled_order = next((o for o in orders if o["id"] == order_id), None)
        assert cancelled_order is not None, "Cancelled order not found in response"
        assert cancelled_order.get("status") == "cancelled"
        assert "cancelled_at" in cancelled_order, "cancelled_at field missing"
        assert "cancellation_reason" in cancelled_order, "cancellation_reason field missing"
        assert cancelled_order.get("cancellation_reason") == cancel_reason
        print("PASS: GET /api/orders returns cancelled_at and cancellation_reason fields")
        
    def test_get_orders_filter_by_cancelled_status(self):
        """Test GET /api/orders?status=cancelled filters cancelled orders only"""
        login_resp = self.get_manager_token()
        token = login_resp["token"]
        
        # Create and cancel an order
        order = self.create_test_order(token)
        order_id = order["id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        self.session.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "cancelled"},
            headers=headers
        )
        
        # Get only cancelled orders
        response = self.session.get(
            f"{BASE_URL}/api/orders?status=cancelled",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get cancelled orders failed: {response.text}"
        orders = response.json()
        
        # All returned orders should be cancelled
        for order in orders:
            assert order.get("status") == "cancelled", f"Non-cancelled order in results: {order.get('status')}"
        
        print(f"PASS: GET /api/orders?status=cancelled returns {len(orders)} cancelled orders")
        
    # ==================== INVALID STATUS TESTS ====================
    
    def test_invalid_status_returns_400(self):
        """Test invalid status returns 400"""
        login_resp = self.get_manager_token()
        token = login_resp["token"]
        
        order = self.create_test_order(token)
        order_id = order["id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        response = self.session.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "invalid_status"},
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("PASS: Invalid status returns 400")
        
    # ==================== DELIVERY TO CANCELLED TRANSITION ====================
    
    def test_delivered_order_can_be_cancelled_by_admin(self):
        """Test admin can cancel a delivered order"""
        login_resp = self.get_manager_token()
        manager_token = login_resp["token"]
        
        # Create and deliver order
        order = self.create_test_order(manager_token)
        order_id = order["id"]
        
        headers = {"Authorization": f"Bearer {manager_token}"}
        self.session.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "delivered"},
            headers=headers
        )
        
        # Admin cancels delivered order
        admin_token = self.get_admin_token()
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = self.session.patch(
            f"{BASE_URL}/api/orders/{order_id}/status",
            json={"status": "cancelled", "cancellation_reason": "Admin cancelled after delivery"},
            headers=headers
        )
        
        assert response.status_code == 200, f"Admin cancel failed: {response.text}"
        data = response.json()
        assert data["status"] == "cancelled"
        print("PASS: Admin can cancel delivered order")


class TestCancelOrderCleanup:
    """Cleanup test orders after tests"""
    
    @pytest.fixture(autouse=True, scope="class")
    def cleanup(self, request):
        """Cleanup TEST_ prefixed orders after test class"""
        yield
        # Cleanup would go here if needed


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
