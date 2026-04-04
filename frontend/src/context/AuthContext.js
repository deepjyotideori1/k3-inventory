import React, { createContext, useContext, useState, useEffect } from 'react';
import { getMe, getSettings } from '../lib/api';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [maintenanceMode, setMaintenanceMode] = useState(false);
  const [maintenanceMessage, setMaintenanceMessage] = useState('');

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    const token = localStorage.getItem('k3gas_token');
    if (token) {
      try {
        const response = await getMe();
        setUser(response.data);
      } catch (error) {
        console.error('Auth check failed:', error);
        localStorage.removeItem('k3gas_token');
        localStorage.removeItem('k3gas_user');
      }
    }
    
    // Check maintenance mode
    try {
      const settingsRes = await getSettings();
      setMaintenanceMode(settingsRes.data.maintenance_mode);
      setMaintenanceMessage(settingsRes.data.maintenance_message);
    } catch (error) {
      console.error('Failed to get settings:', error);
    }
    
    setLoading(false);
  };

  const loginUser = (userData, token) => {
    localStorage.setItem('k3gas_token', token);
    localStorage.setItem('k3gas_user', JSON.stringify(userData));
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem('k3gas_token');
    localStorage.removeItem('k3gas_user');
    setUser(null);
  };

  const refreshSettings = async () => {
    try {
      const settingsRes = await getSettings();
      setMaintenanceMode(settingsRes.data.maintenance_mode);
      setMaintenanceMessage(settingsRes.data.maintenance_message);
    } catch (error) {
      console.error('Failed to refresh settings:', error);
    }
  };

  const value = {
    user,
    loading,
    loginUser,
    logout,
    maintenanceMode,
    maintenanceMessage,
    refreshSettings,
    isAdmin: user?.role === 'admin',
    isHRAdmin: user?.role === 'hr_admin',
    isHRMSEmployee: user?.role === 'hrms_employee',
    isWarehouseManager: user?.role === 'warehouse_manager',
    isSalesExecutive: user?.role === 'sales_executive',
    canAccessHRMS: ['admin', 'hr_admin', 'hrms_employee'].includes(user?.role),
    canAccessInventory: ['admin', 'warehouse_manager', 'sales_executive'].includes(user?.role),
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
