#!/usr/bin/env python3
import requests
import json
import sys
from datetime import datetime

class K3GasAPITester:
    def __init__(self, base_url="https://edit-deploy-5.preview.emergentagent.com"):
        self.base_url = base_url
        self.admin_token = None
        self.manager_token = None
        self.warehouse_id = None
        self.accessory_id = None
        self.accessory_dealer_id = None
        self.customer_id = None
        self.order_id = None
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                if response.content:
                    try:
                        return success, response.json()
                    except:
                        return success, response.text
                return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_details = response.json()
                    print(f"   Error details: {error_details}")
                except:
                    print(f"   Error text: {response.text}")

            return success, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test basic API health"""
        return self.run_test("Health Check", "GET", "health", 200)

    def test_admin_login(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@k3gas.com", "password": "Admin@123"}
        )
        if success and 'token' in response:
            self.admin_token = response['token']
            print(f"   Admin token obtained: {self.admin_token[:20]}...")
            return True
        return False

    def test_manager_login(self):
        """Test warehouse manager login"""
        success, response = self.run_test(
            "Manager Login (Jullang)",
            "POST",
            "auth/login",
            200,
            data={"email": "jullang@k3gas.com", "password": "Jullang@123"}
        )
        if success and 'token' in response:
            self.manager_token = response['token']
            print(f"   Manager token obtained: {self.manager_token[:20]}...")
            return True
        return False

    def test_get_warehouses(self):
        """Test getting warehouses list"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        success, response = self.run_test(
            "Get Warehouses",
            "GET",
            "warehouses",
            200,
            headers=headers
        )
        if success and response:
            print(f"   Found {len(response)} warehouses")
            # Store first warehouse ID for later tests
            if response:
                self.warehouse_id = response[0]['id']
                print(f"   Using warehouse ID: {self.warehouse_id}")
        return success

    def test_dashboard_stats(self):
        """Test dashboard stats endpoint"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        success, response = self.run_test(
            "Dashboard Stats",
            "GET",
            "dashboard/stats",
            200,
            headers=headers
        )
        if success and response:
            print(f"   Total warehouses: {response.get('total_warehouses', 0)}")
            print(f"   15kg filled total: {response.get('total_15kg_filled', 0)}")
        return success

    def test_get_users(self):
        """Test getting users list (admin only)"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        success, response = self.run_test(
            "Get Users",
            "GET",
            "users",
            200,
            headers=headers
        )
        if success and response:
            print(f"   Found {len(response)} users")
        return success

    def test_settings_get(self):
        """Test getting settings"""
        success, response = self.run_test(
            "Get Settings",
            "GET",
            "settings",
            200
        )
        if success and response:
            print(f"   Maintenance mode: {response.get('maintenance_mode', False)}")
        return success

    def test_daily_report_create(self):
        """Test creating a daily report"""
        if not self.warehouse_id:
            print("❌ Cannot test daily report - no warehouse ID")
            return False

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.manager_token}'
        }
        
        today = datetime.now().strftime('%Y-%m-%d')
        data = {
            "warehouse_id": self.warehouse_id,
            "date": today,
            "opening_15kg_filled": 100,
            "opening_21kg_filled": 50,
            "opening_15kg_empty": 20,
            "opening_21kg_empty": 10,
            "sold_15kg_filled": 10,
            "sold_21kg_filled": 5,
            "refilling_15kg": 5,
            "refilling_21kg": 3,
            "refilling_plant_15kg": 0,
            "refilling_plant_21kg": 0,
            "closing_15kg_filled": 95,
            "closing_21kg_filled": 48,
            "closing_15kg_empty": 25,
            "closing_21kg_empty": 12,
            "remarks": "Test report"
        }

        success, response = self.run_test(
            "Create Daily Report",
            "POST",
            "reports/daily",
            200,
            data=data,
            headers=headers
        )
        if success and response:
            print(f"   Report created with ID: {response.get('id', 'N/A')}")
            print(f"   Has discrepancy: {response.get('has_discrepancy', False)}")
        return success

    def test_get_daily_reports(self):
        """Test getting daily reports"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        success, response = self.run_test(
            "Get Daily Reports",
            "GET",
            "reports/daily",
            200,
            headers=headers
        )
        if success and response:
            print(f"   Found {len(response)} daily reports")
        return success

    def test_export_pdf(self):
        """Test PDF export"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        success, response = self.run_test(
            "Export PDF",
            "GET",
            "export/pdf?report_type=daily",
            200,
            headers=headers
        )
        if success:
            print("   PDF export successful")
        return success

    def test_unauthorized_access(self):
        """Test unauthorized access to admin endpoints"""
        success, response = self.run_test(
            "Unauthorized Access to Users",
            "GET",
            "users",
            401  # Should fail without token
        )
        return success

    def test_accessories_crud(self):
        """Test LPG Accessories CRUD operations"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        
        # Create accessory
        success, response = self.run_test(
            "Create Accessory",
            "POST",
            "accessories",
            200,
            data={"name": "Test Regulator", "description": "Test accessory", "unit": "pcs"},
            headers=headers
        )
        if success and response:
            self.accessory_id = response.get('id')
            print(f"   Accessory created with ID: {self.accessory_id}")
        
        # Get accessories
        success2, response2 = self.run_test(
            "Get Accessories",
            "GET",
            "accessories",
            200,
            headers=headers
        )
        if success2 and response2:
            print(f"   Found {len(response2)} accessories")
        
        return success and success2

    def test_accessory_dealers_crud(self):
        """Test Accessory Dealers CRUD operations"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        
        # Create accessory dealer
        success, response = self.run_test(
            "Create Accessory Dealer",
            "POST",
            "accessory-dealers",
            200,
            data={"name": "Test Dealer", "contact": "9876543210", "address": "Test Address"},
            headers=headers
        )
        if success and response:
            self.accessory_dealer_id = response.get('id')
            print(f"   Accessory Dealer created with ID: {self.accessory_dealer_id}")
        
        # Get accessory dealers
        success2, response2 = self.run_test(
            "Get Accessory Dealers",
            "GET",
            "accessory-dealers",
            200,
            headers=headers
        )
        if success2 and response2:
            print(f"   Found {len(response2)} accessory dealers")
        
        return success and success2

    def test_accessory_entries_crud(self):
        """Test Accessory Entries CRUD operations"""
        if not self.accessory_id or not self.accessory_dealer_id:
            print("❌ Cannot test accessory entries - missing accessory or dealer ID")
            return False

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Create accessory entry
        success, response = self.run_test(
            "Create Accessory Entry",
            "POST",
            "accessory-entries",
            200,
            data={
                "accessory_id": self.accessory_id,
                "dealer_id": self.accessory_dealer_id,
                "date": today,
                "total_issued": 10,
                "total_sold": 5,
                "total_remaining": 5,
                "remarks": "Test entry"
            },
            headers=headers
        )
        entry_id = None
        if success and response:
            entry_id = response.get('id')
            print(f"   Accessory Entry created with ID: {entry_id}")
        
        # Get accessory entries
        success2, response2 = self.run_test(
            "Get Accessory Entries",
            "GET",
            "accessory-entries",
            200,
            headers=headers
        )
        if success2 and response2:
            print(f"   Found {len(response2)} accessory entries")
            
        # Test edit accessory entry
        if entry_id:
            success3, response3 = self.run_test(
                "Update Accessory Entry",
                "PUT",
                f"accessory-entries/{entry_id}",
                200,
                data={
                    "total_issued": 15,
                    "total_sold": 8,
                    "remarks": "Updated test entry"
                },
                headers=headers
            )
            if success3:
                print("   Accessory Entry update successful")
        else:
            success3 = False
        
        return success and success2 and success3

    def test_customers_crud(self):
        """Test Customer CRUD operations"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Create customer
        success, response = self.run_test(
            "Create Customer",
            "POST",
            "customers",
            200,
            data={
                "date": today,
                "connection_type": "domestic",
                "customer_name": "Test Customer",
                "address": "Test Address",
                "phone": "9876543210",
                "consumer_no": "CON001",
                "cash_memo_no": "CM001",
                "cylinder_nos": "CYL001",
                "gas_card_issued": True,
                "kyc_done": True,
                "remarks": "Test customer"
            },
            headers=headers
        )
        if success and response:
            self.customer_id = response.get('id')
            print(f"   Customer created with ID: {self.customer_id}")
        
        # Get customers with search
        success2, response2 = self.run_test(
            "Get Customers with Search",
            "GET",
            "customers?search=Test",
            200,
            headers=headers
        )
        if success2 and response2:
            print(f"   Found {len(response2)} customers with search")
        
        return success and success2

    def test_orders_crud(self):
        """Test Order Management operations"""
        if not self.warehouse_id or not self.customer_id:
            print("❌ Cannot test orders - missing warehouse or customer ID")
            return False

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Create order
        success, response = self.run_test(
            "Create Order",
            "POST",
            f"warehouses/{self.warehouse_id}/orders",
            200,
            data={
                "order_date": today,
                "customer_name": "Test Customer",
                "mobile_number": "9876543210",
                "address_landmark": "Test Address",
                "connection_type": "domestic",
                "payment_mode": "cash",
                "remarks": "Test order"
            },
            headers=headers
        )
        if success and response:
            self.order_id = response.get('id')
            print(f"   Order created with ID: {self.order_id}")
        
        # Get orders with search
        success2, response2 = self.run_test(
            "Get Orders with Search",
            "GET",
            "orders?search=Test",
            200,
            headers=headers
        )
        if success2 and response2:
            print(f"   Found {len(response2)} orders with search")
        
        # Test edit order (should now work for all users)
        if self.order_id:
            success3, response3 = self.run_test(
                "Update Order",
                "PUT",
                f"orders/{self.order_id}",
                200,
                data={
                    "order_date": today,
                    "customer_name": "Updated Test Customer",
                    "mobile_number": "9876543211",
                    "address_landmark": "Updated Test Address",
                    "connection_type": "domestic",
                    "payment_mode": "online",
                    "remarks": "Updated test order"
                },
                headers=headers
            )
            if success3:
                print("   Order update successful")
        else:
            success3 = False
        
        return success and success2 and success3

    def test_dealers_filter(self):
        """Test Dealer Reports - filtered dealers (active only)"""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        
        # Get dealers (should only return active ones)
        success, response = self.run_test(
            "Get Dealers (Active Only)",
            "GET",
            "dealers",
            200,
            headers=headers
        )
        if success and response:
            print(f"   Found {len(response)} active dealers")
        
        # Get dealer entries summary (should exclude deleted dealers)
        success2, response2 = self.run_test(
            "Get Dealer Summary (Active Only)",
            "GET",
            "dealer-entries/summary",
            200,
            headers=headers
        )
        if success2 and response2:
            print(f"   Dealer summary excludes deleted dealers")
        
        return success and success2

    def test_accessory_sales_crud(self):
        """Test New Accessory Sales feature"""
        if not self.accessory_id or not self.accessory_dealer_id or not self.warehouse_id:
            print("❌ Cannot test accessory sales - missing required IDs")
            return False

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Create accessory sale
        success, response = self.run_test(
            "Create Accessory Sale",
            "POST",
            "accessory-sales",
            200,
            data={
                "sale_date": today,
                "customer_name": "Test Sale Customer",
                "mobile_number": "9876543210",
                "address": "Test Sale Address",
                "connection_type": "domestic",
                "accessory_id": self.accessory_id,
                "dealer_id": self.accessory_dealer_id,
                "quantity": 2,
                "payment_mode": "cash",
                "remarks": "Test accessory sale",
                "warehouse_id": self.warehouse_id
            },
            headers=headers
        )
        sale_id = None
        if success and response:
            sale_id = response.get('id')
            print(f"   Accessory Sale created with ID: {sale_id}")
        
        # Get accessory sales
        success2, response2 = self.run_test(
            "Get Accessory Sales",
            "GET",
            "accessory-sales",
            200,
            headers=headers
        )
        if success2 and response2:
            print(f"   Found {len(response2)} accessory sales")
        
        return success and success2

def main():
    print("🚀 Starting K3 GAS SERVICE API Testing")
    print("=" * 50)
    
    tester = K3GasAPITester()
    
    # Test sequence
    tests = [
        ("Health Check", tester.test_health_check),
        ("Admin Login", tester.test_admin_login),
        ("Manager Login", tester.test_manager_login),
        ("Get Warehouses", tester.test_get_warehouses),
        ("Dashboard Stats", tester.test_dashboard_stats),
        ("Get Users", tester.test_get_users),
        ("Get Settings", tester.test_settings_get),
        ("Create Daily Report", tester.test_daily_report_create),
        ("Get Daily Reports", tester.test_get_daily_reports),
        ("Export PDF", tester.test_export_pdf),
        ("Accessories CRUD", tester.test_accessories_crud),
        ("Accessory Dealers CRUD", tester.test_accessory_dealers_crud),
        ("Accessory Entries CRUD", tester.test_accessory_entries_crud),
        ("Customers CRUD", tester.test_customers_crud),
        ("Orders CRUD", tester.test_orders_crud),
        ("Dealers Filter", tester.test_dealers_filter),
        ("Accessory Sales CRUD", tester.test_accessory_sales_crud),
        ("Unauthorized Access", tester.test_unauthorized_access),
    ]

    failed_tests = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            if not success:
                failed_tests.append(test_name)
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            failed_tests.append(test_name)

    # Final results
    print("\n" + "=" * 50)
    print("📊 FINAL TEST RESULTS")
    print("=" * 50)
    print(f"Total Tests: {tester.tests_run}")
    print(f"Passed: {tester.tests_passed}")
    print(f"Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed / tester.tests_run * 100):.1f}%" if tester.tests_run > 0 else "0%")
    
    if failed_tests:
        print(f"\n❌ Failed Tests: {', '.join(failed_tests)}")
    else:
        print("\n✅ All tests passed!")
    
    return 0 if len(failed_tests) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())