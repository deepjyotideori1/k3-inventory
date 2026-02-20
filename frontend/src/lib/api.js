import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('k3gas_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('k3gas_token');
      localStorage.removeItem('k3gas_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth
export const login = (email, password) => api.post('/auth/login', { email, password });
export const getMe = () => api.get('/auth/me');
export const changePassword = (currentPassword, newPassword) => 
  api.post('/auth/change-password', { current_password: currentPassword, new_password: newPassword });

// Settings
export const getSettings = () => api.get('/settings');
export const updateSettings = (data) => api.put('/settings', data);

// Users
export const getUsers = () => api.get('/users');
export const createUser = (data) => api.post('/users', data);
export const deleteUser = (userId) => api.delete(`/users/${userId}`);

// Warehouses
export const getWarehouses = () => api.get('/warehouses');
export const createWarehouse = (data) => api.post('/warehouses', data);
export const updateWarehouse = (warehouseId, data) => api.put(`/warehouses/${warehouseId}`, data);
export const deleteWarehouse = (warehouseId) => api.delete(`/warehouses/${warehouseId}`);

// Inventory Items
export const getInventoryItems = () => api.get('/inventory-items');
export const createInventoryItem = (data) => api.post('/inventory-items', data);

// Daily Reports
export const createDailyReport = (data) => api.post('/reports/daily', data);
export const getDailyReports = (params) => api.get('/reports/daily', { params });
export const getLatestClosing = (warehouseId) => api.get(`/reports/daily/latest/${warehouseId}`);

// Plant Reports
export const createPlantReport = (data) => api.post('/reports/plant', data);
export const getPlantReports = (params) => api.get('/reports/plant', { params });
export const getLatestPlantClosing = () => api.get('/reports/plant/latest');
export const getPlantReceivedFromWarehouses = (date) => api.get(`/reports/plant-received/${date}`);
export const getWarehouseReceivedFromPlant = (warehouseId, date) => api.get(`/reports/warehouse-received-from-plant/${warehouseId}/${date}`);

// Stock Update
export const updateStock = (data) => api.post('/stock/update', data);
export const updatePlantStock = (data) => api.post('/stock/plant-update', data);

// Dashboard
export const getDashboardStats = () => api.get('/dashboard/stats');

// Export - Download files with authentication
export const exportPDF = async (params) => {
  try {
    const response = await api.get('/export/pdf', { 
      params,
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `k3_gas_report_${new Date().toISOString().split('T')[0]}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('PDF export failed:', error);
    throw error;
  }
};

export const exportExcel = async (params) => {
  try {
    const response = await api.get('/export/excel', { 
      params,
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `k3_gas_report_${new Date().toISOString().split('T')[0]}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Excel export failed:', error);
    throw error;
  }
};

export default api;
