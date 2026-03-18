#!/usr/bin/env python3
import requests
import json
import sys
from datetime import datetime

class K3GasAPITester:
    def __init__(self, base_url="https://unified-checkout-8.preview.emergentagent.com"):
        self.base_url = base_url
        self.admin_token = None
        self.manager_token = None
        self.warehouse_id = None
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