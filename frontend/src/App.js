import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./context/AuthContext";

// Pages
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import ManagerDashboard from "./pages/ManagerDashboard";
import SalesExecutiveDashboard from "./pages/SalesExecutiveDashboard";
import SalesDashboard from "./pages/SalesDashboard";
import DailyEntry from "./pages/DailyEntry";
import PlantEntry from "./pages/PlantEntry";
import Reports from "./pages/Reports";
import Warehouses from "./pages/Warehouses";
import UsersPage from "./pages/Users";
import SettingsPage from "./pages/Settings";
import PlantHollongi from "./pages/PlantHollongi";
import AdminEditReport from "./pages/AdminEditReport";
import DealerReports from "./pages/DealerReports";
import AccessoryReports from "./pages/AccessoryReports";
import AccessorySales from "./pages/AccessorySales";
import CustomerManagement from "./pages/CustomerManagement";
import OrderManagement from "./pages/OrderManagement";
import BulkMessaging from "./pages/BulkMessaging";

// Protected Route Component
const ProtectedRoute = ({ children, adminOnly = false, allowSalesExecutive = false }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="w-12 h-12 border-4 border-green-200 border-t-green-700 rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (adminOnly && user.role !== 'admin') {
    // Allow sales executive for specific routes
    if (allowSalesExecutive && user.role === 'sales_executive') {
      return children;
    }
    if (user.role === 'sales_executive') {
      return <Navigate to="/sales-data" replace />;
    }
    return <Navigate to="/manager-dashboard" replace />;
  }

  return children;
};

// Redirect based on role
const RoleBasedRedirect = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="w-12 h-12 border-4 border-green-200 border-t-green-700 rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (user.role === 'admin') {
    return <Navigate to="/dashboard" replace />;
  } else if (user.role === 'sales_executive') {
    return <Navigate to="/sales-data" replace />;
  } else {
    return <Navigate to="/manager-dashboard" replace />;
  }
};

function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<Login />} />

      {/* Role-based redirect */}
      <Route path="/" element={<RoleBasedRedirect />} />

      {/* Admin Routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute adminOnly>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/warehouses"
        element={
          <ProtectedRoute adminOnly>
            <Warehouses />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports"
        element={
          <ProtectedRoute adminOnly>
            <Reports />
          </ProtectedRoute>
        }
      />
      <Route
        path="/plant-hollongi"
        element={
          <ProtectedRoute adminOnly>
            <PlantHollongi />
          </ProtectedRoute>
        }
      />
      <Route
        path="/users"
        element={
          <ProtectedRoute adminOnly>
            <UsersPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute adminOnly>
            <SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/edit-report/:reportId"
        element={
          <ProtectedRoute adminOnly>
            <AdminEditReport />
          </ProtectedRoute>
        }
      />

      {/* Manager Routes */}
      <Route
        path="/manager-dashboard"
        element={
          <ProtectedRoute>
            <ManagerDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/daily-entry"
        element={
          <ProtectedRoute>
            <DailyEntry />
          </ProtectedRoute>
        }
      />
      <Route
        path="/plant-entry"
        element={
          <ProtectedRoute>
            <PlantEntry />
          </ProtectedRoute>
        }
      />
      <Route
        path="/my-reports"
        element={
          <ProtectedRoute>
            <Reports />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dealer-reports"
        element={
          <ProtectedRoute>
            <DealerReports />
          </ProtectedRoute>
        }
      />
      <Route
        path="/accessory-reports"
        element={
          <ProtectedRoute adminOnly>
            <AccessoryReports />
          </ProtectedRoute>
        }
      />
      <Route
        path="/accessory-sales"
        element={
          <ProtectedRoute>
            <AccessorySales />
          </ProtectedRoute>
        }
      />
      <Route
        path="/customers"
        element={
          <ProtectedRoute>
            <CustomerManagement />
          </ProtectedRoute>
        }
      />
      <Route
        path="/orders"
        element={
          <ProtectedRoute>
            <OrderManagement />
          </ProtectedRoute>
        }
      />
      <Route
        path="/bulk-messaging"
        element={
          <ProtectedRoute adminOnly allowSalesExecutive>
            <BulkMessaging />
          </ProtectedRoute>
        }
      />
      <Route
        path="/sales-data"
        element={
          <ProtectedRoute>
            <SalesDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/sales-dashboard"
        element={
          <ProtectedRoute>
            <SalesExecutiveDashboard />
          </ProtectedRoute>
        }
      />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
        <Toaster position="top-right" richColors />
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
