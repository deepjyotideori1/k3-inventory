"""
Test suite for K3 Gas Service API after refactoring from monolithic server.py to modular routes.
Tests all major endpoints to ensure zero functional regression.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://unified-checkout-8.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@k3gas.com"
ADMIN_PASSWORD = "Admin@123"


class TestHealthAndAuth:
    """Health check and authentication tests"""
    
    def test_health_endpoint(self):
        """Test /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        print("✓ Health endpoint working")
    
    def test_admin_login(self):
        """Test admin login with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful - User: {data['user']['name']}")
        return data["token"]
    
    def test_invalid_login(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@email.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid login correctly rejected")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token for authenticated requests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Get authorization headers"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestDashboardRoutes:
    """Dashboard API tests - routes/dashboard.py"""
    
    def test_dashboard_stats(self, auth_headers):
        """Test GET /api/dashboard/stats"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_warehouses" in data
        assert "warehouses" in data
        assert isinstance(data["warehouses"], list)
        print(f"✓ Dashboard stats: {data['total_warehouses']} warehouses")
    
    def test_dashboard_chart_data(self, auth_headers):
        """Test GET /api/dashboard/chart-data"""
        response = requests.get(f"{BASE_URL}/api/dashboard/chart-data", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "daily_trend" in data
        assert "payment_breakdown" in data
        assert "connection_types" in data
        assert "warehouse_totals" in data
        assert "total_amount" in data
        assert "total_entries" in data
        print(f"✓ Dashboard chart data: {data['total_entries']} entries, Rs.{data['total_amount']}")
    
    def test_dashboard_chart_data_with_period(self, auth_headers):
        """Test GET /api/dashboard/chart-data with period filter"""
        for period in ["7d", "30d", "90d"]:
            response = requests.get(f"{BASE_URL}/api/dashboard/chart-data?period={period}", headers=auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert "daily_trend" in data
            print(f"✓ Dashboard chart data with period={period}")


class TestSalesRoutes:
    """Sales API tests - routes/sales.py"""
    
    def test_sales_entries_list(self, auth_headers):
        """Test GET /api/sales-entries with pagination"""
        response = requests.get(f"{BASE_URL}/api/sales-entries?page=1&limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data
        assert isinstance(data["entries"], list)
        print(f"✓ Sales entries: {data['total']} total, page {data['page']}/{data['pages']}")
    
    def test_sales_summary(self, auth_headers):
        """Test GET /api/sales-entries/summary"""
        response = requests.get(f"{BASE_URL}/api/sales-entries/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "cash" in data
        assert "online" in data
        assert "pending" in data
        assert "total" in data
        print(f"✓ Sales summary: Total Rs.{data['total']['amount']}, {data['total']['count']} entries")


class TestCustomerRoutes:
    """Customer API tests - routes/customers.py"""
    
    def test_customers_list(self, auth_headers):
        """Test GET /api/customers"""
        response = requests.get(f"{BASE_URL}/api/customers", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Customers list: {len(data)} customers")
    
    def test_customers_summary(self, auth_headers):
        """Test GET /api/customers/summary"""
        response = requests.get(f"{BASE_URL}/api/customers/summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_domestic" in data
        assert "total_commercial" in data
        assert "total_customers" in data
        print(f"✓ Customer summary: {data['total_customers']} total (Dom: {data['total_domestic']}, Com: {data['total_commercial']})")


class TestOrderRoutes:
    """Order API tests - routes/orders.py"""
    
    def test_orders_list(self, auth_headers):
        """Test GET /api/orders"""
        response = requests.get(f"{BASE_URL}/api/orders", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Orders list: {len(data)} orders")
    
    def test_order_analysis(self, auth_headers):
        """Test GET /api/admin/order-analysis"""
        response = requests.get(f"{BASE_URL}/api/admin/order-analysis", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "groups" in data
        assert "summary" in data
        print(f"✓ Order analysis: {data['summary']['total_orders']} total orders")


class TestWarehouseRoutes:
    """Warehouse API tests - routes/warehouses.py"""
    
    def test_warehouses_list(self, auth_headers):
        """Test GET /api/warehouses"""
        response = requests.get(f"{BASE_URL}/api/warehouses", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        print(f"✓ Warehouses list: {len(data)} warehouses")
        # Verify expected warehouses exist
        warehouse_names = [w['name'] for w in data]
        assert any('Jullang' in name for name in warehouse_names), "Jullang warehouse not found"
        assert any('Naharlagun' in name for name in warehouse_names), "Naharlagun warehouse not found"


class TestUserRoutes:
    """User management API tests - routes/auth.py"""
    
    def test_users_list(self, auth_headers):
        """Test GET /api/users"""
        response = requests.get(f"{BASE_URL}/api/users", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify admin user exists
        admin_users = [u for u in data if u['email'] == ADMIN_EMAIL]
        assert len(admin_users) == 1
        print(f"✓ Users list: {len(data)} users")
    
    def test_auth_me(self, auth_headers):
        """Test GET /api/auth/me"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        print(f"✓ Auth me: {data['name']} ({data['role']})")


class TestDealerRoutes:
    """Dealer API tests - routes/dealers.py"""
    
    def test_dealers_list(self, auth_headers):
        """Test GET /api/dealers"""
        response = requests.get(f"{BASE_URL}/api/dealers", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Dealers list: {len(data)} dealers")


class TestAccessoryRoutes:
    """Accessory API tests - routes/accessories.py"""
    
    def test_accessories_list(self, auth_headers):
        """Test GET /api/accessories"""
        response = requests.get(f"{BASE_URL}/api/accessories", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Accessories list: {len(data)} accessories")


class TestAuditRoutes:
    """Audit log API tests - routes/audit.py"""
    
    def test_audit_logs(self, auth_headers):
        """Test GET /api/audit-logs"""
        response = requests.get(f"{BASE_URL}/api/audit-logs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        assert "page" in data
        print(f"✓ Audit logs: {data['total']} total logs")


class TestAnalyticsRoutes:
    """Analytics API tests - routes/analytics.py"""
    
    def test_connection_refill_analytics(self, auth_headers):
        """Test GET /api/admin/connection-refill-analytics"""
        response = requests.get(f"{BASE_URL}/api/admin/connection-refill-analytics?period=monthly", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "warehouse_breakdown" in data
        assert "date_breakdown" in data
        print(f"✓ Connection/Refill analytics: {data['summary']['total_new_connections']} new, {data['summary']['total_refills']} refills")


class TestPlantRoutes:
    """Plant API tests - routes/plant.py"""
    
    def test_plant_issuance_history(self, auth_headers):
        """Test GET /api/plant/issuance-history"""
        response = requests.get(f"{BASE_URL}/api/plant/issuance-history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Plant issuance history: {len(data)} records")
    
    def test_plant_available_stock(self, auth_headers):
        """Test GET /api/plant/available-stock"""
        response = requests.get(f"{BASE_URL}/api/plant/available-stock", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "available_15kg" in data
        assert "available_21kg" in data
        print(f"✓ Plant available stock: 15kg={data['available_15kg']}, 21kg={data['available_21kg']}")


class TestExportRoutes:
    """Export API tests - routes/exports.py and routes/sales.py"""
    
    def test_export_pdf(self, auth_headers):
        """Test GET /api/export/pdf"""
        response = requests.get(f"{BASE_URL}/api/export/pdf", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'application/pdf'
        print(f"✓ Export PDF: {len(response.content)} bytes")
    
    def test_export_excel(self, auth_headers):
        """Test GET /api/export/excel"""
        response = requests.get(f"{BASE_URL}/api/export/excel", headers=auth_headers)
        assert response.status_code == 200
        assert 'spreadsheet' in response.headers.get('content-type', '')
        print(f"✓ Export Excel: {len(response.content)} bytes")
    
    def test_export_sales_pdf(self, auth_headers):
        """Test GET /api/export/sales-pdf"""
        response = requests.get(f"{BASE_URL}/api/export/sales-pdf", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'application/pdf'
        print(f"✓ Export Sales PDF: {len(response.content)} bytes")
    
    def test_export_sales_excel(self, auth_headers):
        """Test GET /api/export/sales-excel"""
        response = requests.get(f"{BASE_URL}/api/export/sales-excel", headers=auth_headers)
        assert response.status_code == 200
        assert 'spreadsheet' in response.headers.get('content-type', '')
        print(f"✓ Export Sales Excel: {len(response.content)} bytes")
    
    def test_export_customers_pdf(self, auth_headers):
        """Test GET /api/export/customers-pdf"""
        response = requests.get(f"{BASE_URL}/api/export/customers-pdf", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'application/pdf'
        print(f"✓ Export Customers PDF: {len(response.content)} bytes")
    
    def test_export_orders_pdf(self, auth_headers):
        """Test GET /api/export/orders-pdf"""
        response = requests.get(f"{BASE_URL}/api/export/orders-pdf", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'application/pdf'
        print(f"✓ Export Orders PDF: {len(response.content)} bytes")
    
    def test_export_sales_summary_pdf(self, auth_headers):
        """Test GET /api/export/sales-summary-pdf"""
        response = requests.get(f"{BASE_URL}/api/export/sales-summary-pdf?group_by=daily", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers.get('content-type') == 'application/pdf'
        print(f"✓ Export Sales Summary PDF: {len(response.content)} bytes")


class TestSettingsRoutes:
    """Settings API tests - routes/auth.py"""
    
    def test_get_settings(self, auth_headers):
        """Test GET /api/settings"""
        response = requests.get(f"{BASE_URL}/api/settings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "maintenance_mode" in data
        assert "app_version" in data
        print(f"✓ Settings: v{data['app_version']}, maintenance={data['maintenance_mode']}")


class TestUnauthorizedAccess:
    """Test that protected endpoints require authentication"""
    
    def test_dashboard_stats_requires_auth(self):
        """Test /api/dashboard/stats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code in [401, 403]
        print("✓ Dashboard stats correctly requires auth")
    
    def test_users_requires_auth(self):
        """Test /api/users requires authentication"""
        response = requests.get(f"{BASE_URL}/api/users")
        assert response.status_code in [401, 403]
        print("✓ Users endpoint correctly requires auth")
    
    def test_audit_logs_requires_auth(self):
        """Test /api/audit-logs requires authentication"""
        response = requests.get(f"{BASE_URL}/api/audit-logs")
        assert response.status_code in [401, 403]
        print("✓ Audit logs correctly requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
