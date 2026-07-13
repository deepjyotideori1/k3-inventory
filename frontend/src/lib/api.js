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
export const resetUserPassword = (userId, newPassword = null) => 
  api.post(`/users/${userId}/reset-password`, newPassword ? { new_password: newPassword } : {});

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
export const getWarehousesReceivedSummary = (date) => api.get(`/reports/warehouses-received-summary/${date}`);

// Stock Update
export const updateStock = (data) => api.post('/stock/update', data);
export const updatePlantStock = (data) => api.post('/stock/plant-update', data);
export const issueCylindersToDealer = (data) => api.post('/plant/issue-to-dealer', data);
export const getPlantIssuanceHistory = (params) => api.get('/plant/issuance-history', { params });
export const getPlantAvailableStock = (date) => api.get('/plant/available-stock', { params: { date } });

// Dashboard Charts
export const getDashboardChartData = (params) => api.get('/dashboard/chart-data', { params });

// Audit Logs
export const getAuditLogs = (params) => api.get('/audit-logs', { params });
export const exportAuditLogs = (params) => api.get('/audit-logs/export', { params, responseType: 'blob' });

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

// Sales Entries
export const getSalesEntries = (params) => api.get('/sales-entries', { params });
export const createSalesEntry = (data) => api.post('/sales-entries', data);
export const createSalesEntryForWarehouse = (warehouseId, data) => api.post(`/sales-entries/warehouse/${warehouseId}`, data);
export const updateSalesEntry = (entryId, data) => api.put(`/sales-entries/${entryId}`, data);
export const deleteSalesEntry = (entryId) => api.delete(`/sales-entries/${entryId}`);
export const getSalesSummary = (params) => api.get('/sales-entries/summary', { params });
export const getFrequentCustomers = (limit = 10) => api.get('/sales-entries/frequent-customers', { params: { limit } });

export const exportSalesPdf = async (params) => {
  try {
    const response = await api.get('/export/sales-pdf', { 
      params,
      responseType: 'blob'
    });
    const contentDisposition = response.headers['content-disposition'];
    let filename = `Sales_Report_${new Date().toISOString().split('T')[0]}.pdf`;
    if (contentDisposition) {
      const match = contentDisposition.match(/filename=(.+)/);
      if (match) filename = match[1];
    }
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Sales PDF export failed:', error);
    throw error;
  }
};

export const exportSalesExcel = async (params) => {
  try {
    const response = await api.get('/export/sales-excel', { 
      params,
      responseType: 'blob'
    });
    const contentDisposition = response.headers['content-disposition'];
    let filename = `Sales_Report_${new Date().toISOString().split('T')[0]}.xlsx`;
    if (contentDisposition) {
      const match = contentDisposition.match(/filename=(.+)/);
      if (match) filename = match[1];
    }
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Sales Excel export failed:', error);
    throw error;
  }
};

// Sales Summary Report Exports
export const exportSalesSummaryPdf = async (params) => {
  try {
    const response = await api.get('/export/sales-summary-pdf', { 
      params,
      responseType: 'blob'
    });
    const contentDisposition = response.headers['content-disposition'];
    const groupBy = params.group_by || 'daily';
    let filename = `Sales_Summary_${groupBy}_${new Date().toISOString().split('T')[0]}.pdf`;
    if (contentDisposition) {
      const match = contentDisposition.match(/filename=(.+)/);
      if (match) filename = match[1];
    }
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Sales Summary PDF export failed:', error);
    throw error;
  }
};

export const exportSalesSummaryExcel = async (params) => {
  try {
    const response = await api.get('/export/sales-summary-excel', { 
      params,
      responseType: 'blob'
    });
    const contentDisposition = response.headers['content-disposition'];
    const groupBy = params.group_by || 'daily';
    let filename = `Sales_Summary_${groupBy}_${new Date().toISOString().split('T')[0]}.xlsx`;
    if (contentDisposition) {
      const match = contentDisposition.match(/filename=(.+)/);
      if (match) filename = match[1];
    }
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Sales Summary Excel export failed:', error);
    throw error;
  }
};

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
export const updateAccessoryEntry = (entryId, data) => api.put(`/accessory-entries/${entryId}`, data);
export const deleteAccessoryEntry = (entryId) => api.delete(`/accessory-entries/${entryId}`);
export const getAccessorySummary = (params) => api.get('/accessory-entries/summary', { params });
export const getLatestAccessoryRemaining = (accessoryId, dealerId, beforeDate) => 
  api.get('/accessory-entries/latest-remaining', { params: { accessory_id: accessoryId, dealer_id: dealerId, before_date: beforeDate } });

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

// Accessory Sales
export const createAccessorySale = (data) => api.post('/accessory-sales', data);
export const getAccessorySales = (params) => api.get('/accessory-sales', { params });
export const getAccessorySale = (saleId) => api.get(`/accessory-sales/${saleId}`);
export const deleteAccessorySale = (saleId) => api.delete(`/accessory-sales/${saleId}`);
export const getAccessorySalesSummary = (params) => api.get('/accessory-sales-summary', { params });

export const exportAccessorySalesPDF = async (params) => {
  try {
    const response = await api.get('/export/accessory-sales-pdf', { 
      params,
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `accessory_sales_${new Date().toISOString().split('T')[0]}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Accessory Sales PDF export failed:', error);
    throw error;
  }
};

export const exportAccessorySalesExcel = async (params) => {
  try {
    const response = await api.get('/export/accessory-sales-excel', { 
      params,
      responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `accessory_sales_${new Date().toISOString().split('T')[0]}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Accessory Sales Excel export failed:', error);
    throw error;
  }
};

// ============ CUSTOMER MANAGEMENT ============

// Customers
export const getCustomers = (params) => api.get('/customers', { params });
export const syncCustomersFromSales = () => api.post('/customers/sync-from-sales');
export const createCustomer = (data) => api.post('/customers', data);
export const createCustomerForWarehouse = (warehouseId, data) => api.post(`/customers/warehouse/${warehouseId}`, data);
export const updateCustomer = (customerId, data) => api.put(`/customers/${customerId}`, data);
export const deleteCustomer = (customerId) => api.delete(`/customers/${customerId}`);
export const getCustomerLinkedRecords = (customerId) => api.get(`/customers/${customerId}/linked-records`);
export const bulkUploadCustomers = (data) => api.post('/customers/bulk', data);
export const bulkUploadCustomersForWarehouse = (warehouseId, data) => api.post(`/customers/bulk/warehouse/${warehouseId}`, data);
export const getCustomerSummary = (params) => api.get('/customers/summary', { params });
export const getCustomerRefillStatus = (params) => api.get('/customers/refill-status', { params });
export const getCustomerLastRefill = (customerId) => api.get(`/customers/${customerId}/last-refill`);

export const exportCustomerRefillPDF = async (params = {}) => {
  const response = await api.get('/export/customer-refill-pdf', { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `customer_refill_status_${new Date().toISOString().split('T')[0]}.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  return response;
};

export const exportCustomerRefillExcel = async (params = {}) => {
  const response = await api.get('/export/customer-refill-excel', { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `customer_refill_status_${new Date().toISOString().split('T')[0]}.xlsx`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  return response;
};

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
export const updateOrderStatus = (orderId, status, cancellation_reason) => api.patch(`/orders/${orderId}/status`, { status, cancellation_reason });
export const deleteOrder = (orderId) => api.delete(`/orders/${orderId}`);
export const getOrderSummary = (params) => api.get('/orders/summary/stats', { params });
export const getOrderAnalysis = (params) => api.get('/admin/order-analysis', { params });
export const getCustomerOrderReport = (params) => api.get('/admin/customer-order-report', { params });

export const exportCustomerOrderReportPDF = async (params = {}) => {
  const response = await api.get('/export/customer-order-report-pdf', { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `customer_order_report_${new Date().toISOString().split('T')[0]}.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  return response;
};

export const exportCustomerOrderReportExcel = async (params = {}) => {
  const response = await api.get('/export/customer-order-report-excel', { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `customer_order_report_${new Date().toISOString().split('T')[0]}.xlsx`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  return response;
};

export const exportOrderAnalysisPDF = async (params = {}) => {
  const response = await api.get('/export/order-analysis-pdf', { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `order_analysis_${new Date().toISOString().split('T')[0]}.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  return response;
};

export const exportOrderAnalysisExcel = async (params = {}) => {
  const response = await api.get('/export/order-analysis-excel', { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `order_analysis_${new Date().toISOString().split('T')[0]}.xlsx`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  return response;
};

// Connection & Refill Analytics
export const getConnectionRefillAnalytics = (params) => api.get('/admin/connection-refill-analytics', { params });

export const exportConnectionRefillPDF = async (params = {}) => {
  const response = await api.get('/export/connection-refill-analytics-pdf', { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `connection_refill_analytics_${new Date().toISOString().split('T')[0]}.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  return response;
};

export const exportConnectionRefillExcel = async (params = {}) => {
  const response = await api.get('/export/connection-refill-analytics-excel', { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `connection_refill_analytics_${new Date().toISOString().split('T')[0]}.xlsx`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  return response;
};

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

// ============ BULK MESSAGING ============

// Messaging Settings
export const getMessagingSettings = () => api.get('/messaging/settings');
export const updateMessagingSettings = (data) => api.post('/messaging/settings', data);

// Recipients
export const getRecipientCount = (params) => api.get('/messaging/recipients/count', { params });

// Send Messages
export const sendBulkMessage = (data) => api.post('/messaging/send', data);

// Message Logs
export const getMessageLogs = (limit = 50) => api.get('/messaging/logs', { params: { limit } });
export const getMessageLogDetail = (logId) => api.get(`/messaging/logs/${logId}`);

// ============ GST BILLING ============

export const getGstConfig = () => api.get('/gst/config');
export const updateGstConfig = (data) => api.put('/gst/config', data);

export const getGstItems = () => api.get('/gst/items');
export const createGstItem = (data) => api.post('/gst/items', data);
export const updateGstItem = (itemId, data) => api.put(`/gst/items/${itemId}`, data);
export const deleteGstItem = (itemId) => api.delete(`/gst/items/${itemId}`);
export const activateGstItem = (itemId) => api.post(`/gst/items/${itemId}/activate`);
export const downloadGstItemTemplate = async () => {
  const response = await api.get('/gst/items/template/excel', { responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', 'ItemMaster_BulkTemplate.xlsx');
  document.body.appendChild(link); link.click(); link.remove();
  window.URL.revokeObjectURL(url);
};
export const bulkUploadGstItems = (formData) => api.post('/gst/items/bulk-upload', formData, {
  headers: { 'Content-Type': 'multipart/form-data' },
});
export const getGstItemHistory = (params) => api.get('/gst/items/history', { params });
export const downloadGstItemHistoryExcel = async (params = {}) => {
  const response = await api.get('/gst/items/history/excel', { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `Item_Rate_History_${new Date().toISOString().split('T')[0]}.xlsx`);
  document.body.appendChild(link); link.click(); link.remove();
  window.URL.revokeObjectURL(url);
};

export const getGstPlans = () => api.get('/gst/plans');
export const getGstPlan = (planId) => api.get(`/gst/plans/${planId}`);
export const createGstPlan = (data) => api.post('/gst/plans', data);
export const updateGstPlan = (planId, data) => api.put(`/gst/plans/${planId}`, data);
export const deleteGstPlan = (planId) => api.delete(`/gst/plans/${planId}`);

// GST Discrepancies
export const listGstDiscrepancies = (params = {}) => api.get('/gst/discrepancies', { params });
export const reviewGstDiscrepancy = (invoiceId, action, note = '') =>
  api.post(`/gst/discrepancies/${invoiceId}/review`, { action, note });
export const correctGstDiscrepancy = (invoiceId, line_items, note = '') =>
  api.post(`/gst/discrepancies/${invoiceId}/correct`, { line_items, note });

// GST Party Ledger
export const getPartyLedgerCustomers = (params = {}) => api.get('/gst/party-ledger/customers', { params });
export const getPartyLedger = (params) => api.get('/gst/party-ledger', { params });
export const backfillGstPayments = () => api.post('/gst/invoices/backfill-payments');

// GST Warehouse summary (per-warehouse 8-metric grid)
export const getGstWarehouseSummary = (params = {}) => api.get('/gst/warehouse-summary', { params });
export const exportGstWarehouseSummaryExcel = async (params = {}) => {
  const response = await api.get('/gst/warehouse-summary/excel', { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `Warehouse_Summary_${new Date().toISOString().split('T')[0]}.xlsx`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

// GST Customer Master lookup (auto-populate invoice form)
export const gstCustomerLookup = (params) => api.get('/gst/customer-lookup', { params });

// GST Invoice-number repair (fixes malformed numbers with duplicated FY segments)
export const repairGstInvoiceNumbers = () => api.post('/gst/invoices/repair-numbers');

// GST Reports
export const listGstReports = () => api.get('/gst/reports/list');
export const getGstReport = (reportType, params) => api.get(`/gst/reports/${reportType}`, { params });
export const exportGstReportExcel = async (reportType, params = {}, label = 'Report') => {
  const response = await api.get(`/gst/reports/${reportType}/excel`, { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `${label.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.xlsx`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};
export const exportGstReportPdf = async (reportType, params = {}, label = 'Report') => {
  const response = await api.get(`/gst/reports/${reportType}/pdf`, { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `${label.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const getGstInvoices = (params) => api.get('/gst/invoices', { params });
export const getGstInvoice = (invoiceId) => api.get(`/gst/invoices/${invoiceId}`);
export const createGstInvoice = (data) => api.post('/gst/invoices', data);
export const updateGstInvoice = (invoiceId, data) => api.put(`/gst/invoices/${invoiceId}`, data);
export const cancelGstInvoice = (invoiceId, reason) => api.post(`/gst/invoices/${invoiceId}/cancel`, { reason });
export const deleteGstInvoice = (invoiceId) => api.delete(`/gst/invoices/${invoiceId}`);
export const generateGstFromSale = (saleType, saleId) => api.post(`/gst/invoices/generate-from-sale/${saleType}/${saleId}`);
export const getGstSummary = (params) => api.get('/gst/invoices/summary', { params });

export const downloadGstInvoicePdf = async (invoiceId, invoiceNumber = '') => {
  const response = await api.get(`/gst/invoices/${invoiceId}/pdf`, { responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  const safeNum = (invoiceNumber || invoiceId).replace(/\//g, '_');
  link.setAttribute('download', `Invoice_${safeNum}.pdf`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const exportGstInvoicesExcel = async (params = {}) => {
  const response = await api.get('/gst/invoices/export/excel', { params, responseType: 'blob' });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `GST_Invoices_${new Date().toISOString().split('T')[0]}.xlsx`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export default api;
