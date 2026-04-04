import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../lib/api';
import {
  LayoutDashboard, Users, Building2, Settings, LogOut, Menu, X,
  ArrowLeftRight, UserCircle, ChevronDown, ChevronRight,
  DollarSign, CalendarDays
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';

const navItems = [
  { path: '/hrms', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/hrms/employees', label: 'Employees', icon: Users },
  { path: '/hrms/departments', label: 'Departments', icon: Building2 },
  { path: '/hrms/attendance', label: 'Attendance', icon: CalendarDays },
  { path: '/hrms/payroll', label: 'Payroll', icon: DollarSign },
  { path: '/hrms/settings', label: 'Company Settings', icon: Settings, roles: ['admin', 'hr_admin'] },
];

const HRMSLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleSwitchDashboard = async () => {
    try {
      await api.post('/auth/set-dashboard', { dashboard: 'inventory' });
      toast.success('Switched to Inventory Dashboard');
      navigate(user?.role === 'admin' ? '/dashboard' : '/manager-dashboard');
    } catch (e) {
      toast.error('Failed to switch dashboard');
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const filteredNav = navItems.filter(item => {
    if (!item.roles) return true;
    return item.roles.includes(user?.role);
  });

  return (
    <div className="min-h-screen bg-slate-50" data-testid="hrms-layout">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 bg-black/40 z-30 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`fixed top-0 left-0 z-40 h-screen w-64 bg-slate-900 text-white transform transition-transform duration-200 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0`}>
        <div className="h-full flex flex-col">
          {/* Header */}
          <div className="p-5 border-b border-slate-700">
            <div className="flex items-center gap-3">
              <img
                src="https://customer-assets.emergentagent.com/job_gas-stock-master/artifacts/nww68qmn_customcolor_icon_customcolor_background.png"
                alt="K3 Logo"
                className="w-10 h-10 object-contain"
              />
              <div>
                <h1 className="text-base font-bold text-white">K3 HRMS</h1>
                <p className="text-slate-400 text-xs">Human Resources</p>
              </div>
            </div>
          </div>

          {/* Nav */}
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
            {filteredNav.map(item => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                  data-testid={`hrms-nav-${item.label.toLowerCase().replace(/\s/g, '-')}`}
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </Link>
              );
            })}

            <div className="pt-4 mt-4 border-t border-slate-700">
              <button
                onClick={handleSwitchDashboard}
                className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium text-amber-300 hover:bg-slate-800 transition-colors"
                data-testid="switch-to-inventory"
              >
                <ArrowLeftRight className="w-4 h-4" />
                Switch to Inventory
              </button>
            </div>
          </nav>

          {/* User info */}
          <div className="p-4 border-t border-slate-700">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm font-bold">
                {user?.name?.charAt(0) || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user?.name}</p>
                <p className="text-xs text-slate-400 truncate">{user?.role}</p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="w-full justify-start gap-2 text-slate-400 hover:text-red-400 hover:bg-slate-800"
              data-testid="hrms-logout-btn"
            >
              <LogOut className="w-4 h-4" />
              Logout
            </Button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:ml-64">
        {/* Top bar */}
        <header className="bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-4 sticky top-0 z-20">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="lg:hidden text-slate-600 hover:text-slate-900"
          >
            {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
          <div className="flex-1" />
          <span className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded font-medium">HRMS</span>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
};

export default HRMSLayout;
