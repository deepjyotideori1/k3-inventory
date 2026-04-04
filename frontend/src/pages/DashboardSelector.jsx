import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../lib/api';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Package, Users, ArrowRight, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const DashboardSelector = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState('');
  const [lastUsed, setLastUsed] = useState(null);

  useEffect(() => {
    loadPreference();
  }, []);

  const loadPreference = async () => {
    try {
      const res = await api.get('/auth/dashboard-preference');
      setLastUsed(res.data.active_dashboard || null);
    } catch (e) {
      console.error('Failed to load preference:', e);
    }
    setLoading(false);
  };

  const selectDashboard = async (dashboard) => {
    setSelecting(dashboard);
    try {
      await api.post('/auth/set-dashboard', { dashboard });
      toast.success(`Switched to ${dashboard === 'inventory' ? 'Inventory & Operations' : 'HRMS'} Dashboard`);
      if (dashboard === 'inventory') {
        navigate(user?.role === 'admin' ? '/dashboard' : '/manager-dashboard');
      } else {
        navigate('/hrms');
      }
    } catch (e) {
      toast.error('Failed to set dashboard');
      setSelecting('');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 animate-spin text-green-700" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-white to-slate-100 p-4" data-testid="dashboard-selector">
      <div className="max-w-3xl w-full">
        <div className="text-center mb-10">
          <div className="flex items-center justify-center gap-3 mb-4">
            <img
              src="https://customer-assets.emergentagent.com/job_gas-stock-master/artifacts/nww68qmn_customcolor_icon_customcolor_background.png"
              alt="K3 Logo"
              className="w-14 h-14 object-contain"
            />
            <div className="text-left">
              <h1 className="logo-text text-2xl">K3 GAS SERVICE</h1>
              <p className="text-slate-500 text-sm">Khayal Hamesha</p>
            </div>
          </div>
          <h2 className="text-2xl font-bold text-slate-800 mt-6">Select Dashboard</h2>
          <p className="text-slate-500 mt-1">Choose the module you want to access</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Inventory Dashboard */}
          <Card
            className={`group cursor-pointer border-2 hover:shadow-lg transition-all duration-200 ${lastUsed === 'inventory' ? 'border-green-500 shadow-md' : 'border-slate-200 hover:border-green-500'}`}
            onClick={() => selectDashboard('inventory')}
            data-testid="select-inventory"
          >
            <CardContent className="p-8 text-center">
              {lastUsed === 'inventory' && (
                <span className="inline-block mb-3 text-xs font-medium text-green-700 bg-green-50 px-3 py-1 rounded-full">Last Used</span>
              )}
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-green-50 flex items-center justify-center group-hover:bg-green-100 transition-colors">
                <Package className="w-8 h-8 text-green-700" />
              </div>
              <h3 className="text-xl font-bold text-slate-800 mb-2">Inventory & Operations</h3>
              <p className="text-slate-500 text-sm mb-6">
                Manage warehouses, cylinders, sales, orders, daily reports, and dealer operations.
              </p>
              <Button
                variant="outline"
                className="gap-2 group-hover:bg-green-700 group-hover:text-white group-hover:border-green-700 transition-colors"
                disabled={selecting === 'inventory'}
              >
                {selecting === 'inventory' ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                Open Inventory
              </Button>
            </CardContent>
          </Card>

          {/* HRMS Dashboard */}
          <Card
            className={`group cursor-pointer border-2 hover:shadow-lg transition-all duration-200 ${lastUsed === 'hrms' ? 'border-blue-500 shadow-md' : 'border-slate-200 hover:border-blue-500'}`}
            onClick={() => selectDashboard('hrms')}
            data-testid="select-hrms"
          >
            <CardContent className="p-8 text-center">
              {lastUsed === 'hrms' && (
                <span className="inline-block mb-3 text-xs font-medium text-blue-700 bg-blue-50 px-3 py-1 rounded-full">Last Used</span>
              )}
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-blue-50 flex items-center justify-center group-hover:bg-blue-100 transition-colors">
                <Users className="w-8 h-8 text-blue-700" />
              </div>
              <h3 className="text-xl font-bold text-slate-800 mb-2">HRMS</h3>
              <p className="text-slate-500 text-sm mb-6">
                Employee management, payroll, attendance, performance tracking, and HR operations.
              </p>
              <Button
                variant="outline"
                className="gap-2 group-hover:bg-blue-700 group-hover:text-white group-hover:border-blue-700 transition-colors"
                disabled={selecting === 'hrms'}
              >
                {selecting === 'hrms' ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                Open HRMS
              </Button>
            </CardContent>
          </Card>
        </div>

        <p className="text-center text-slate-400 text-xs mt-8">
          You can switch dashboards anytime from the sidebar menu
        </p>
      </div>
    </div>
  );
};

export default DashboardSelector;
