"""
Backend Tests for Bulk Messaging Feature
- Tests for messaging settings API (GET/POST)
- Tests for recipient count API
- Tests for send bulk message API (simulated mode)
- Tests for message logs API
- Tests for admin-only access restrictions
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if BASE_URL:
    BASE_URL = BASE_URL.rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASSWORD = "Admin@123"
MANAGER_EMAIL = "jullang@k3gas.com"
MANAGER_PASSWORD = "Jullang@123"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["token"]


@pytest.fixture(scope="module")
def manager_token():
    """Get warehouse manager auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": MANAGER_EMAIL,
        "password": MANAGER_PASSWORD
    })
    assert response.status_code == 200, f"Manager login failed: {response.text}"
    return response.json()["token"]


class TestMessagingSettings:
    """Test GET/POST /api/messaging/settings"""
    
    def test_get_messaging_settings_admin(self, admin_token):
        """Admin should be able to get messaging settings"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/settings",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "provider" in data
        assert "sms_configured" in data
        assert "whatsapp_configured" in data
        assert isinstance(data["sms_configured"], bool)
        assert isinstance(data["whatsapp_configured"], bool)
        print(f"Messaging settings retrieved: sms_configured={data['sms_configured']}, whatsapp_configured={data['whatsapp_configured']}")
    
    def test_get_messaging_settings_manager_denied(self, manager_token):
        """Non-admin should be denied access to messaging settings"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/settings",
            headers={"Authorization": f"Bearer {manager_token}"}
        )
        assert response.status_code == 403
        assert "admin" in response.json().get("detail", "").lower()
        print("Manager correctly denied access to messaging settings")
    
    def test_update_messaging_settings_admin(self, admin_token):
        """Admin should be able to update messaging settings"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/settings",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "provider": "test_provider",
                "sms_sender_id": "K3GAS",
                "whatsapp_phone_number": "+919876543210"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("message") == "Messaging settings updated successfully"
        assert data.get("provider") == "test_provider"
        print(f"Messaging settings updated: provider={data['provider']}")
    
    def test_update_messaging_settings_manager_denied(self, manager_token):
        """Non-admin should be denied access to update messaging settings"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/settings",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "provider": "malicious_provider"
            }
        )
        assert response.status_code == 403
        print("Manager correctly denied access to update messaging settings")


class TestRecipientCount:
    """Test GET /api/messaging/recipients/count"""
    
    def test_get_recipient_count_admin(self, admin_token):
        """Admin should be able to get recipient count"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/recipients/count",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"recipient_filter": "all"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "total_recipients" in data
        assert "breakdown_by_warehouse" in data
        assert isinstance(data["total_recipients"], int)
        assert isinstance(data["breakdown_by_warehouse"], list)
        print(f"Recipient count retrieved: total={data['total_recipients']}, warehouses={len(data['breakdown_by_warehouse'])}")
    
    def test_get_recipient_count_by_warehouse(self, admin_token):
        """Test filtering recipients by warehouse"""
        # First get warehouses
        warehouses_response = requests.get(
            f"{BASE_URL}/api/warehouses",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert warehouses_response.status_code == 200
        warehouses = warehouses_response.json()
        
        if warehouses:
            warehouse_id = warehouses[0]["id"]
            response = requests.get(
                f"{BASE_URL}/api/messaging/recipients/count",
                headers={"Authorization": f"Bearer {admin_token}"},
                params={"recipient_filter": "warehouse", "warehouse_id": warehouse_id}
            )
            assert response.status_code == 200
            
            data = response.json()
            assert "total_recipients" in data
            print(f"Recipient count for warehouse: {data['total_recipients']}")
    
    def test_get_recipient_count_by_category(self, admin_token):
        """Test filtering recipients by category (domestic/commercial)"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/recipients/count",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"recipient_filter": "category", "category": "domestic"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "total_recipients" in data
        print(f"Recipient count for domestic category: {data['total_recipients']}")
    
    def test_get_recipient_count_manager_denied(self, manager_token):
        """Non-admin should be denied access to recipient count"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/recipients/count",
            headers={"Authorization": f"Bearer {manager_token}"}
        )
        assert response.status_code == 403
        print("Manager correctly denied access to recipient count")


class TestSendBulkMessage:
    """Test POST /api/messaging/send"""
    
    def test_send_sms_message_simulated(self, admin_token):
        """Test sending SMS message (simulated mode when no API configured)"""
        # First, create a test customer with phone number
        test_customer = {
            "date": "2026-01-15",
            "connection_type": "domestic",
            "customer_name": "TEST_Messaging_Customer",
            "address": "Test Address",
            "phone": "9876543210",
            "consumer_no": "MSG001",
            "cash_memo_no": "MSC001"
        }
        
        # Get warehouses to get a valid warehouse_id
        warehouses_response = requests.get(
            f"{BASE_URL}/api/warehouses",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert warehouses_response.status_code == 200
        warehouses = warehouses_response.json()
        non_plant_warehouses = [w for w in warehouses if not w.get("is_plant")]
        
        if non_plant_warehouses:
            warehouse_id = non_plant_warehouses[0]["id"]
            
            # Create test customer
            create_response = requests.post(
                f"{BASE_URL}/api/customers/warehouse/{warehouse_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
                json=test_customer
            )
            assert create_response.status_code == 200, f"Failed to create test customer: {create_response.text}"
            created_customer = create_response.json()
            
            try:
                # Now test sending message
                response = requests.post(
                    f"{BASE_URL}/api/messaging/send",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={
                        "channel": "sms",
                        "message": "Test SMS message from K3 Gas Service",
                        "recipient_filter": "all"
                    }
                )
                assert response.status_code == 200
                
                data = response.json()
                assert "message_log_id" in data
                assert "channel" in data
                assert data["channel"] == "sms"
                assert "recipient_count" in data
                assert "successful_count" in data
                assert "status" in data
                assert data["status"] == "completed"
                
                # Since no API is configured, it should be simulated
                assert data.get("simulated") == True
                print(f"SMS message sent (simulated): recipients={data['recipient_count']}, successful={data['successful_count']}")
            
            finally:
                # Cleanup: delete test customer
                requests.delete(
                    f"{BASE_URL}/api/customers/{created_customer['id']}",
                    headers={"Authorization": f"Bearer {admin_token}"}
                )
    
    def test_send_whatsapp_message_simulated(self, admin_token):
        """Test sending WhatsApp message (simulated mode)"""
        # First, create a test customer with phone number
        test_customer = {
            "date": "2026-01-15",
            "connection_type": "commercial",
            "customer_name": "TEST_WhatsApp_Customer",
            "address": "Test WhatsApp Address",
            "phone": "8765432109",
            "consumer_no": "WA001"
        }
        
        # Get warehouses
        warehouses_response = requests.get(
            f"{BASE_URL}/api/warehouses",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        warehouses = warehouses_response.json()
        non_plant_warehouses = [w for w in warehouses if not w.get("is_plant")]
        
        if non_plant_warehouses:
            warehouse_id = non_plant_warehouses[0]["id"]
            
            # Create test customer
            create_response = requests.post(
                f"{BASE_URL}/api/customers/warehouse/{warehouse_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
                json=test_customer
            )
            assert create_response.status_code == 200
            created_customer = create_response.json()
            
            try:
                # Send WhatsApp message
                response = requests.post(
                    f"{BASE_URL}/api/messaging/send",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={
                        "channel": "whatsapp",
                        "message": "Test WhatsApp message from K3 Gas Service",
                        "recipient_filter": "all"
                    }
                )
                assert response.status_code == 200
                
                data = response.json()
                assert data["channel"] == "whatsapp"
                assert data.get("simulated") == True
                print(f"WhatsApp message sent (simulated): recipients={data['recipient_count']}")
            
            finally:
                # Cleanup
                requests.delete(
                    f"{BASE_URL}/api/customers/{created_customer['id']}",
                    headers={"Authorization": f"Bearer {admin_token}"}
                )
    
    def test_send_both_channels_simulated(self, admin_token):
        """Test sending to both SMS and WhatsApp (simulated mode)"""
        # Create test customer
        test_customer = {
            "date": "2026-01-15",
            "connection_type": "domestic",
            "customer_name": "TEST_Both_Channels_Customer",
            "address": "Test Both Address",
            "phone": "7654321098",
            "consumer_no": "BOTH001"
        }
        
        warehouses_response = requests.get(
            f"{BASE_URL}/api/warehouses",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        warehouses = warehouses_response.json()
        non_plant_warehouses = [w for w in warehouses if not w.get("is_plant")]
        
        if non_plant_warehouses:
            warehouse_id = non_plant_warehouses[0]["id"]
            
            create_response = requests.post(
                f"{BASE_URL}/api/customers/warehouse/{warehouse_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
                json=test_customer
            )
            assert create_response.status_code == 200
            created_customer = create_response.json()
            
            try:
                response = requests.post(
                    f"{BASE_URL}/api/messaging/send",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={
                        "channel": "both",
                        "message": "Test message to both channels",
                        "recipient_filter": "all"
                    }
                )
                assert response.status_code == 200
                
                data = response.json()
                assert data["channel"] == "both"
                print(f"Message sent to both channels (simulated): recipients={data['recipient_count']}")
            
            finally:
                requests.delete(
                    f"{BASE_URL}/api/customers/{created_customer['id']}",
                    headers={"Authorization": f"Bearer {admin_token}"}
                )
    
    def test_send_message_empty_text_fails(self, admin_token):
        """Test that empty message returns error"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/send",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "channel": "sms",
                "message": "   ",
                "recipient_filter": "all"
            }
        )
        assert response.status_code == 400
        assert "empty" in response.json().get("detail", "").lower()
        print("Empty message correctly rejected")
    
    def test_send_message_invalid_channel_fails(self, admin_token):
        """Test that invalid channel returns error"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/send",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "channel": "invalid_channel",
                "message": "Test message",
                "recipient_filter": "all"
            }
        )
        assert response.status_code == 400
        assert "channel" in response.json().get("detail", "").lower()
        print("Invalid channel correctly rejected")
    
    def test_send_message_manager_denied(self, manager_token):
        """Non-admin should be denied access to send messages"""
        response = requests.post(
            f"{BASE_URL}/api/messaging/send",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "channel": "sms",
                "message": "Test message",
                "recipient_filter": "all"
            }
        )
        assert response.status_code == 403
        print("Manager correctly denied access to send messages")


class TestMessageLogs:
    """Test GET /api/messaging/logs"""
    
    def test_get_message_logs_admin(self, admin_token):
        """Admin should be able to get message logs"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/logs",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"limit": 50}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # If there are logs, check structure
        if data:
            log = data[0]
            assert "id" in log
            assert "channel" in log
            assert "message" in log
            assert "recipient_count" in log
            assert "status" in log
            print(f"Message logs retrieved: {len(data)} logs")
        else:
            print("No message logs found (expected if no messages have been sent)")
    
    def test_get_message_log_detail_admin(self, admin_token):
        """Admin should be able to get message log detail"""
        # First get logs
        logs_response = requests.get(
            f"{BASE_URL}/api/messaging/logs",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert logs_response.status_code == 200
        logs = logs_response.json()
        
        if logs:
            log_id = logs[0]["id"]
            
            response = requests.get(
                f"{BASE_URL}/api/messaging/logs/{log_id}",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["id"] == log_id
            assert "message" in data
            assert "channel" in data
            print(f"Message log detail retrieved for log {log_id}")
        else:
            print("Skipped log detail test - no logs available")
    
    def test_get_message_log_detail_not_found(self, admin_token):
        """Test 404 for non-existent log"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/logs/nonexistent-log-id",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404
        print("Non-existent log correctly returns 404")
    
    def test_get_message_logs_manager_denied(self, manager_token):
        """Non-admin should be denied access to message logs"""
        response = requests.get(
            f"{BASE_URL}/api/messaging/logs",
            headers={"Authorization": f"Bearer {manager_token}"}
        )
        assert response.status_code == 403
        print("Manager correctly denied access to message logs")


class TestCustomerPhoneField:
    """Test that customers can have phone field for messaging"""
    
    def test_customer_create_with_phone(self, admin_token):
        """Test creating customer with phone field"""
        warehouses_response = requests.get(
            f"{BASE_URL}/api/warehouses",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        warehouses = warehouses_response.json()
        non_plant_warehouses = [w for w in warehouses if not w.get("is_plant")]
        
        if non_plant_warehouses:
            warehouse_id = non_plant_warehouses[0]["id"]
            
            test_customer = {
                "date": "2026-01-15",
                "connection_type": "domestic",
                "customer_name": "TEST_Phone_Field_Customer",
                "address": "Test Address",
                "phone": "9123456789",
                "consumer_no": "PHN001"
            }
            
            response = requests.post(
                f"{BASE_URL}/api/customers/warehouse/{warehouse_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
                json=test_customer
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data["phone"] == "9123456789"
            print(f"Customer created with phone: {data['phone']}")
            
            # Cleanup
            requests.delete(
                f"{BASE_URL}/api/customers/{data['id']}",
                headers={"Authorization": f"Bearer {admin_token}"}
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
