import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard,
  Warehouse,
  FileText,
  Users,
  Settings,
  LogOut,
  Factory,
  ClipboardList,
  AlertTriangle,
  Menu,
  X,
  UserCheck,
  Boxes,
  UserPlus,
  ShoppingCart,
  MessageSquare,
  TrendingUp,
  ShoppingBag
} from 'lucide-react';
import { Button } from './ui/button';
import { cn } from '../lib/utils';

const Layout = ({ children }) => {
  const { user, logout, isAdmin, isSalesExecutive, maintenanceMode } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = React.useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const adminLinks = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/warehouses', label: 'Warehouses', icon: Warehouse },
    { path: '/reports', label: 'Reports', icon: FileText },
    { path: '/sales-data', label: 'Sales Data', icon: TrendingUp },
    { path: '/customers', label: 'Customers', icon: UserPlus },
    { path: '/orders', label: 'Orders', icon: ShoppingCart },
    { path: '/customer-order-report', label: 'Order Report', icon: ClipboardList },
    { path: '/bulk-messaging', label: 'Bulk Messaging', icon: MessageSquare },
    { path: '/plant-hollongi', label: 'Plant Hollongi', icon: Factory },
    { path: '/dealer-reports', label: 'Dealer Reports', icon: UserCheck },
    { path: '/accessory-reports', label: 'LPG Accessories', icon: Boxes },
    { path: '/accessory-sales', label: 'Accessory Sales', icon: ShoppingBag },
    { path: '/users', label: 'Users', icon: Users },
    { path: '/settings', label: 'Settings', icon: Settings },
  ];

  const managerLinks = [
    { path: '/manager-dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/daily-entry', label: 'Daily Entry', icon: ClipboardList },
    { path: '/sales-data', label: 'Sales Data', icon: TrendingUp },
    { path: '/customers', label: 'Customers', icon: UserPlus },
    { path: '/orders', label: 'Orders', icon: ShoppingCart },
    { path: '/accessory-sales', label: 'Accessory Sales', icon: ShoppingBag },
    { path: '/my-reports', label: 'My Reports', icon: FileText },
  ];

  const salesExecutiveLinks = [
    { path: '/sales-data', label: 'Sales Data', icon: TrendingUp },
    { path: '/customers', label: 'Customers', icon: UserPlus },
    { path: '/orders', label: 'Orders', icon: ShoppingCart },
    { path: '/accessory-sales', label: 'Accessory Sales', icon: ShoppingBag },
    { path: '/bulk-messaging', label: 'Bulk Messaging', icon: MessageSquare },
  ];

  // Select links based on role
  let links;
  if (isAdmin) {
    links = adminLinks;
  } else if (isSalesExecutive) {
    links = salesExecutiveLinks;
  } else {
    links = [...managerLinks]; // Clone to avoid mutation
  }

  // Check if current user is plant manager
  const isPlantManager = user?.warehouse_name === 'Plant Hollongi';
  if (!isAdmin && isPlantManager) {
    const plantLink = { path: '/plant-entry', label: 'Plant Entry', icon: Factory };
    const dealerLink = { path: '/dealer-reports', label: 'Dealer Reports', icon: UserCheck };
    if (!links.find(l => l.path === '/plant-entry')) {
      links.splice(1, 1, plantLink);
    }
    if (!links.find(l => l.path === '/dealer-reports')) {
      links.push(dealerLink);
    }
    // Remove orders link for Plant Hollongi
    const orderIndex = links.findIndex(l => l.path === '/orders');
    if (orderIndex !== -1) {
      links.splice(orderIndex, 1);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50" data-testid="main-layout">
      {/* Maintenance Banner */}
      {maintenanceMode && isAdmin && (
        <div className="maintenance-banner flex items-center justify-center gap-2" data-testid="maintenance-banner">
          <AlertTriangle className="w-4 h-4" />
          <span>Maintenance Mode is Active</span>
        </div>
      )}

      {/* Mobile Header */}
      <div className="lg:hidden flex items-center justify-between p-4 bg-white border-b">
        <div className="flex items-center gap-2">
          <img 
            src="https://customer-assets.emergentagent.com/job_gas-stock-master/artifacts/nww68qmn_customcolor_icon_customcolor_background.png" 
            alt="K3 Logo" 
            className="w-10 h-10 object-contain"
          />
          <span className="font-bold text-green-700">K3 GAS SERVICE</span>
        </div>
        <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(!sidebarOpen)}>
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </Button>
      </div>

      <div className="flex">
        {/* Sidebar */}
        <aside 
          className={cn(
            "sidebar fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-200 ease-in-out overflow-y-auto",
            sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
          )}
          data-testid="sidebar"
        >
          <div className="flex flex-col h-full">
            {/* Logo */}
            <div className="p-6 border-b border-white/10">
              <div className="flex items-center gap-3">
                <img 
                  src="https://customer-assets.emergentagent.com/job_gas-stock-master/artifacts/nww68qmn_customcolor_icon_customcolor_background.png" 
                  alt="K3 Logo" 
                  className="w-12 h-12 object-contain bg-white/90 rounded-lg p-1"
                />
                <div>
                  <h1 className="text-white font-bold text-lg leading-tight">K3 GAS SERVICE</h1>
                  <p className="text-green-200 text-xs">Khayal Hamesha</p>
                </div>
              </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4 space-y-1">
              {links.map((link) => (
                <Link
                  key={link.path}
                  to={link.path}
                  onClick={() => setSidebarOpen(false)}
                  className={cn("sidebar-link", location.pathname === link.path && "active")}
                  data-testid={`nav-${link.path.slice(1)}`}
                >
                  <link.icon className="w-5 h-5 mr-3" />
                  {link.label}
                </Link>
              ))}
            </nav>

            {/* User Info */}
            <div className="p-4 border-t border-white/10">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
                  <span className="text-white font-semibold">
                    {user?.name?.charAt(0) || 'U'}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm font-medium truncate">{user?.name}</p>
                  <p className="text-green-200 text-xs truncate">
                    {isAdmin ? 'Master Admin' : isSalesExecutive ? 'Sales Executive' : user?.warehouse_name}
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                className="w-full justify-start text-white/80 hover:text-white hover:bg-white/10"
                onClick={handleLogout}
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </aside>

        {/* Overlay for mobile */}
        {sidebarOpen && (
          <div 
            className="fixed inset-0 bg-black/50 z-40 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Main Content */}
        <main className="flex-1 min-h-screen lg:ml-64">
          <div className="p-6 lg:p-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

export default Layout;
