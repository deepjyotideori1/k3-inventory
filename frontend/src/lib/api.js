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
export const getTodayReport = (warehouseId, date) => api.get(`/reports/daily/today/${warehouseId}`, { params: { date } });
export const updateDailyReport = (reportId, data) => api.put(`/reports/daily/${reportId}`, data);

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

// Dealers
export const getDealers = () => api.get('/dealers');
export const createDealer = (data) => api.post('/dealers', data);
export const updateDealer = (dealerId, data) => api.put(`/dealers/${dealerId}`, data);
export const deleteDealer = (dealerId) => api.delete(`/dealers/${dealerId}`);

// Dealer Entries
export const createDealerEntry = (data) => api.post('/dealer-entries', data);
export const getDealerEntries = (params) => api.get('/dealer-entries', { params });
export const getDealerSummary = (params) => api.get('/dealer-entries/summary', { params });
export const updateDealerEntry = (entryId, data) => api.put(`/dealer-entries/${entryId}`, data);

// Dealer Report Exports
export const exportDealerPDF = async (params) => {
  try {
    const response = await api.get('/export/dealer-pdf', { 
      params,
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `dealer_report_${new Date().toISOString().split('T')[0]}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Dealer PDF export failed:', error);
    throw error;
  }
};

export const exportDealerExcel = async (params) => {
  try {
    const response = await api.get('/export/dealer-excel', { 
      params,
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `dealer_report_${new Date().toISOString().split('T')[0]}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Dealer Excel export failed:', error);
    throw error;
  }
};

// LPG Accessories
export const getAccessories = () => api.get('/accessories');
export const createAccessory = (data) => api.post('/accessories', data);
export const updateAccessory = (accessoryId, data) => api.put(`/accessories/${accessoryId}`, data);
export const deleteAccessory = (accessoryId) => api.delete(`/accessories/${accessoryId}`);

// Accessory Dealers
export const getAccessoryDealers = () => api.get('/accessory-dealers');
export const createAccessoryDealer = (data) => api.post('/accessory-dealers', data);
export const updateAccessoryDealer = (dealerId, data) => api.put(`/accessory-dealers/${dealerId}`, data);
export const deleteAccessoryDealer = (dealerId) => api.delete(`/accessory-dealers/${dealerId}`);

// Accessory Entries
export const createAccessoryEntry = (data) => api.post('/accessory-entries', data);
export const getAccessoryEntries = (params) => api.get('/accessory-entries', { params });
export const getAccessorySummary = (params) => api.get('/accessory-entries/summary', { params });

// Accessory Report Exports
export const exportAccessoryPDF = async (params) => {
  try {
    const response = await api.get('/export/accessory-pdf', { 
      params,
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `accessory_report_${new Date().toISOString().split('T')[0]}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Accessory PDF export failed:', error);
    throw error;
  }
};

export const exportAccessoryExcel = async (params) => {
  try {
    const response = await api.get('/export/accessory-excel', { 
      params,
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `accessory_report_${new Date().toISOString().split('T')[0]}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Accessory Excel export failed:', error);
    throw error;
  }
};

// ============ CUSTOMER MANAGEMENT ============

// Customers
export const getCustomers = (params) => api.get('/customers', { params });
export const createCustomer = (data) => api.post('/customers', data);
export const createCustomerForWarehouse = (warehouseId, data) => api.post(`/customers/warehouse/${warehouseId}`, data);
export const updateCustomer = (customerId, data) => api.put(`/customers/${customerId}`, data);
export const deleteCustomer = (customerId) => api.delete(`/customers/${customerId}`);
export const bulkUploadCustomers = (data) => api.post('/customers/bulk', data);
export const bulkUploadCustomersForWarehouse = (warehouseId, data) => api.post(`/customers/bulk/warehouse/${warehouseId}`, data);
export const getCustomerSummary = () => api.get('/customers/summary');

// Customer Sample Excel Template
export const downloadCustomerTemplate = async () => {
  try {
    const response = await api.get('/customers/sample-excel', {
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'customer_upload_template.xlsx');
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Template download failed:', error);
    throw error;
  }
};

// Customer Export
export const exportCustomersPDF = async (params) => {
  try {
    const response = await api.get('/export/customers-pdf', { 
      params,
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    const category = params?.category || 'all';
    link.setAttribute('download', `customers_${category}_${new Date().toISOString().split('T')[0]}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Customer PDF export failed:', error);
    throw error;
  }
};

export const exportCustomersExcel = async (params) => {
  try {
    const response = await api.get('/export/customers-excel', { 
      params,
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    const category = params?.category || 'all';
    link.setAttribute('download', `customers_${category}_${new Date().toISOString().split('T')[0]}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Customer Excel export failed:', error);
    throw error;
  }
};

// ============ ORDER MANAGEMENT ============

// Orders
export const getOrders = (params) => api.get('/orders', { params });
export const getOrder = (orderId) => api.get(`/orders/${orderId}`);
export const createOrder = (data) => api.post('/orders', data);
export const createOrderForWarehouse = (warehouseId, data) => api.post(`/orders/warehouse/${warehouseId}`, data);
export const updateOrder = (orderId, data) => api.put(`/orders/${orderId}`, data);
export const deleteOrder = (orderId) => api.delete(`/orders/${orderId}`);
export const getOrderSummary = (params) => api.get('/orders/summary/stats', { params });

// Order PDF Download (single order)
export const downloadOrderPDF = async (orderId) => {
  try {
    const response = await api.get(`/orders/pdf/${orderId}`, {
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `order_${orderId}_${new Date().toISOString().split('T')[0]}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Order PDF download failed:', error);
    throw error;
  }
};

// Order Reports Export
export const exportOrdersPDF = async (params) => {
  try {
    const response = await api.get('/export/orders-pdf', { 
      params,
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `orders_report_${new Date().toISOString().split('T')[0]}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Orders PDF export failed:', error);
    throw error;
  }
};

export const exportOrdersExcel = async (params) => {
  try {
    const response = await api.get('/export/orders-excel', { 
      params,
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `orders_report_${new Date().toISOString().split('T')[0]}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Orders Excel export failed:', error);
    throw error;
  }
};

export default api;
