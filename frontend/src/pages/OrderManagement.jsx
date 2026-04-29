import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { 
  getOrders, 
  createOrder,
  createOrderForWarehouse,
  updateOrder,
  updateOrderStatus,
  deleteOrder,
  getOrderSummary,
  downloadOrderPDF,
  exportOrdersPDF,
  exportOrdersExcel,
  getCustomers,
  createCustomer,
  createCustomerForWarehouse,
  getWarehouses,
  getCustomerLastRefill
} from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose } from '../components/ui/dialog';
import SearchBar from '../components/SearchBar';
import SearchableSelect from '../components/SearchableSelect';
import { 
  ShoppingCart,
  Plus,
  Loader2,
  FileText,
  Download,
  Trash2,
  Calendar,
  FileSpreadsheet,
  Save,
  Search,
  Home,
  Building2,
  Edit,
  RefreshCw,
  CreditCard,
  Banknote,
  Smartphone,
  Clock,
  User,
  Phone,
  MapPin,
  Hash,
  CheckCircle2,
  Package,
  Truck,
  AlertTriangle,
  Flame,
  XCircle
} from 'lucide-react';
import { getTodayDate, formatDate, getDateRange } from '../lib/utils';
import { toast } from 'sonner';

const OrderManagement = () => {
  const { user, isAdmin } = useAuth();
  const [loading, setLoading] = useState(true);
  const [orders, setOrders] = useState([]);
  const [summary, setSummary] = useState({});
  const [customers, setCustomers] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [activeTab, setActiveTab] = useState('create');
  
  // Form state
  const [formData, setFormData] = useState({
    order_date: getTodayDate(),
    customer_id: '',
    customer_name: '',
    mobile_number: '',
    address_landmark: '',
    connection_type: 'domestic',
    cylinder_nos: '',
    payment_mode: 'cash',
    remarks: ''
  });
  const [submitting, setSubmitting] = useState(false);
  const [selectedWarehouse, setSelectedWarehouse] = useState('');
  const [customerCategory, setCustomerCategory] = useState('all');
  const [useExistingCustomer, setUseExistingCustomer] = useState(false);
  
  // New customer dialog
  const [showNewCustomerDialog, setShowNewCustomerDialog] = useState(false);
  const [newCustomerData, setNewCustomerData] = useState({
    customer_name: '',
    mobile_number: '',
    address: '',
    connection_type: 'domestic'
  });
  
  // Edit state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingOrder, setEditingOrder] = useState(null);
  const [editForm, setEditForm] = useState({});
  
  // Last refill info
  const [lastRefill, setLastRefill] = useState(null);
  const [loadingRefill, setLoadingRefill] = useState(false);
  
  // Filters
  const [dateRange, setDateRange] = useState('daily');
  const [startDate, setStartDate] = useState(getTodayDate());
  const [endDate, setEndDate] = useState(getTodayDate());
  const [filterPayment, setFilterPayment] = useState('all');
  const [filterConnection, setFilterConnection] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [exporting, setExporting] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(null);
  const [filteredOrders, setFilteredOrders] = useState([]);

  // Cancel dialog state
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [cancellingOrder, setCancellingOrder] = useState(null);
  const [cancelReason, setCancelReason] = useState('');

  useEffect(() => {
    fetchCustomers();
    if (isAdmin) {
      fetchWarehouses();
    }
  }, [isAdmin, customerCategory]);

  useEffect(() => {
    fetchOrders();
    fetchSummary();
  }, [startDate, endDate, filterPayment, filterConnection, filterStatus, searchQuery]);

  const fetchWarehouses = async () => {
    try {
      const response = await getWarehouses();
      // Filter out Plant Hollongi
      const filtered = response.data.filter(w => !w.is_plant);
      setWarehouses(filtered);
    } catch (error) {
      console.error('Failed to fetch warehouses:', error);
    }
  };

  const fetchCustomers = async () => {
    try {
      const params = {};
      if (customerCategory !== 'all') params.category = customerCategory;
      const response = await getCustomers(params);
      setCustomers(response.data.customers || response.data || []);
    } catch (error) {
      console.error('Failed to fetch customers:', error);
    }
  };

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const params = { start_date: startDate, end_date: endDate };
      if (filterPayment !== 'all') params.payment_mode = filterPayment;
      if (filterConnection !== 'all') params.connection_type = filterConnection;
      if (filterStatus !== 'all') params.status = filterStatus;
      if (searchQuery) params.search = searchQuery;
      
      const response = await getOrders(params);
      setOrders(response.data);
      setFilteredOrders(response.data);
    } catch (error) {
      console.error('Failed to fetch orders:', error);
      toast.error('Failed to load orders');
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = async () => {
    try {
      const params = { start_date: startDate, end_date: endDate };
      const response = await getOrderSummary(params);
      setSummary(response.data);
    } catch (error) {
      console.error('Failed to fetch summary:', error);
    }
  };

  const handleDateRangeChange = (value) => {
    setDateRange(value);
    const range = getDateRange(value);
    setStartDate(range.start);
    setEndDate(range.end);
  };

  const handleCustomerSelect = async (customerId) => {
    const customer = customers.find(c => c.id === customerId);
    if (customer) {
      setFormData({
        ...formData,
        customer_id: customerId,
        customer_name: customer.customer_name || '',
        mobile_number: customer.phone || customer.consumer_no || '',
        address_landmark: customer.address || '',
        remarks: customer.remarks || ''
      });
      // Fetch last refill info
      setLoadingRefill(true);
      try {
        const res = await getCustomerLastRefill(customerId);
        setLastRefill(res.data);
      } catch {
        setLastRefill(null);
      } finally {
        setLoadingRefill(false);
      }
    }
  };

  const getRefillBadge = (days) => {
    if (days === null || days === undefined) return null;
    if (days <= 15) return <Badge className="bg-green-100 text-green-800 text-xs">Recently Refilled</Badge>;
    if (days <= 30) return <Badge className="bg-yellow-100 text-yellow-800 text-xs">Moderate Gap</Badge>;
    return <Badge className="bg-red-100 text-red-800 text-xs"><AlertTriangle className="w-3 h-3 mr-1" />Overdue</Badge>;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.customer_name.trim()) {
      toast.error('Customer name is required');
      return;
    }
    
    if (isAdmin && !selectedWarehouse) {
      toast.error('Please select a warehouse');
      return;
    }
    
    setSubmitting(true);
    try {
      let result;
      if (isAdmin) {
        result = await createOrderForWarehouse(selectedWarehouse, formData);
      } else {
        result = await createOrder(formData);
      }
      toast.success(`Order ${result.data.order_no} created successfully!`);
      setFormData({
        order_date: getTodayDate(),
        customer_id: '',
        customer_name: '',
        mobile_number: '',
        address_landmark: '',
        connection_type: 'domestic',
        cylinder_nos: '',
        payment_mode: 'cash',
        remarks: ''
      });
      setUseExistingCustomer(false);
      fetchOrders();
      fetchSummary();
    } catch (error) {
      console.error('Failed to create order:', error);
      toast.error(error.response?.data?.detail || 'Failed to create order');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddNewCustomer = async () => {
    if (!newCustomerData.customer_name.trim()) {
      toast.error('Customer name is required');
      return;
    }
    
    setSubmitting(true);
    try {
      const customerPayload = {
        date: getTodayDate(),
        connection_type: newCustomerData.connection_type,
        customer_name: newCustomerData.customer_name,
        address: newCustomerData.address,
        consumer_no: newCustomerData.mobile_number,
        cash_memo_no: '',
        cylinder_nos: '',
        gas_card_issued: false,
        kyc_done: false,
        remarks: 'Added from Orders'
      };
      
      if (isAdmin && selectedWarehouse) {
        await createCustomerForWarehouse(selectedWarehouse, customerPayload);
      } else {
        await createCustomer(customerPayload);
      }
      
      toast.success('Customer added successfully');
      
      // Set form data with new customer info
      setFormData({
        ...formData,
        customer_name: newCustomerData.customer_name,
        mobile_number: newCustomerData.mobile_number,
        address_landmark: newCustomerData.address,
        connection_type: newCustomerData.connection_type
      });
      
      setShowNewCustomerDialog(false);
      setNewCustomerData({ customer_name: '', mobile_number: '', address: '', connection_type: 'domestic' });
      fetchCustomers();
    } catch (error) {
      console.error('Failed to add customer:', error);
      toast.error(error.response?.data?.detail || 'Failed to add customer');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDownloadPDF = async (orderId) => {
    try {
      await downloadOrderPDF(orderId);
      toast.success('Order PDF downloaded');
    } catch (error) {
      toast.error('Failed to download PDF');
    }
  };

  const handleStatusChange = async (orderId, newStatus) => {
    if (newStatus === 'cancelled') {
      // Show cancel confirmation dialog
      setCancellingOrder(orderId);
      setCancelReason('');
      setCancelDialogOpen(true);
      return;
    }
    setUpdatingStatus(orderId);
    try {
      const response = await updateOrderStatus(orderId, newStatus);
      toast.success(response.data.message);
      fetchOrders();
      fetchSummary();
    } catch (error) {
      console.error('Failed to update status:', error);
      toast.error(error.response?.data?.detail || 'Failed to update status');
    } finally {
      setUpdatingStatus(null);
    }
  };

  const handleConfirmCancel = async () => {
    if (!cancellingOrder) return;
    setUpdatingStatus(cancellingOrder);
    setCancelDialogOpen(false);
    try {
      const response = await updateOrderStatus(cancellingOrder, 'cancelled', cancelReason || undefined);
      toast.success(response.data.message);
      fetchOrders();
      fetchSummary();
    } catch (error) {
      console.error('Failed to cancel order:', error);
      toast.error(error.response?.data?.detail || 'Failed to cancel order');
    } finally {
      setUpdatingStatus(null);
      setCancellingOrder(null);
      setCancelReason('');
    }
  };

  const handleEdit = (order) => {
    setEditingOrder(order);
    setEditForm({
      order_date: order.order_date,
      customer_name: order.customer_name,
      mobile_number: order.mobile_number,
      address_landmark: order.address_landmark,
      connection_type: order.connection_type,
      cylinder_nos: order.cylinder_nos || '',
      payment_mode: order.payment_mode,
      remarks: order.remarks,
      status: order.status || 'pending'
    });
    setEditDialogOpen(true);
  };

  const handleEditSubmit = async () => {
    if (!editingOrder) return;
    
    setSubmitting(true);
    try {
      await updateOrder(editingOrder.id, editForm);
      toast.success('Order updated successfully');
      setEditDialogOpen(false);
      setEditingOrder(null);
      fetchOrders();
    } catch (error) {
      console.error('Failed to update order:', error);
      toast.error(error.response?.data?.detail || 'Failed to update order');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (orderId) => {
    if (!window.confirm('Are you sure you want to delete this order?')) return;
    
    try {
      await deleteOrder(orderId);
      toast.success('Order deleted');
      fetchOrders();
      fetchSummary();
    } catch (error) {
      console.error('Failed to delete order:', error);
      toast.error(error.response?.data?.detail || 'Failed to delete order');
    }
  };

  const handleExportPDF = async () => {
    setExporting(true);
    try {
      await exportOrdersPDF({ 
        start_date: startDate, 
        end_date: endDate,
        payment_mode: filterPayment !== 'all' ? filterPayment : undefined,
        connection_type: filterConnection !== 'all' ? filterConnection : undefined
      });
      toast.success('PDF exported successfully');
    } catch (error) {
      toast.error('Failed to export PDF');
    } finally {
      setExporting(false);
    }
  };

  const handleExportExcel = async () => {
    setExporting(true);
    try {
      await exportOrdersExcel({ 
        start_date: startDate, 
        end_date: endDate,
        payment_mode: filterPayment !== 'all' ? filterPayment : undefined,
        connection_type: filterConnection !== 'all' ? filterConnection : undefined
      });
      toast.success('Excel exported successfully');
    } catch (error) {
      toast.error('Failed to export Excel');
    } finally {
      setExporting(false);
    }
  };

  const getPaymentBadge = (mode) => {
    switch(mode) {
      case 'cash':
        return <Badge className="bg-green-100 text-green-800"><Banknote className="w-3 h-3 mr-1" />Cash</Badge>;
      case 'online':
        return <Badge className="bg-blue-100 text-blue-800"><Smartphone className="w-3 h-3 mr-1" />Online</Badge>;
      case 'credit_pending':
        return <Badge className="bg-amber-100 text-amber-800"><Clock className="w-3 h-3 mr-1" />Credit/Pending</Badge>;
      default:
        return <Badge variant="outline">{mode}</Badge>;
    }
  };

  const getStatusBadge = (status) => {
    switch(status) {
      case 'pending':
        return <Badge className="bg-orange-100 text-orange-800 border-orange-300"><Package className="w-3 h-3 mr-1" />Pending</Badge>;
      case 'delivered':
        return <Badge className="bg-green-100 text-green-800 border-green-300"><CheckCircle2 className="w-3 h-3 mr-1" />Delivered</Badge>;
      case 'cancelled':
        return <Badge className="bg-red-100 text-red-800 border-red-300"><XCircle className="w-3 h-3 mr-1" />Cancelled</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getConnectionTypeBadge = (type) => {
    switch(type) {
      case 'domestic':
        return <Badge className="bg-emerald-100 text-emerald-800"><Home className="w-3 h-3 mr-1" />Domestic</Badge>;
      case 'domestic_refill':
        return <Badge className="bg-blue-100 text-blue-800"><Home className="w-3 h-3 mr-1" />Domestic Refill</Badge>;
      case 'commercial':
        return <Badge className="bg-purple-100 text-purple-800"><Building2 className="w-3 h-3 mr-1" />Commercial</Badge>;
      case 'commercial_refill':
        return <Badge className="bg-indigo-100 text-indigo-800"><Building2 className="w-3 h-3 mr-1" />Commercial Refill</Badge>;
      default:
        return <Badge variant="outline">{type}</Badge>;
    }
  };

  // Check if user is Plant Hollongi (orders not allowed)
  const isPlantHollongi = user?.warehouse_name === 'Plant Hollongi';
  
  if (isPlantHollongi && !isAdmin) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <ShoppingCart className="w-16 h-16 text-slate-300 mb-4" />
          <h2 className="text-2xl font-bold text-slate-700 mb-2">Orders Not Available</h2>
          <p className="text-slate-500">Order management is not available for Plant Hollongi.</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6" data-testid="order-management-page">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-800">Order Management</h1>
            <p className="text-slate-500 mt-1">
              {isAdmin ? 'Manage orders across all warehouses' : `Create and manage orders for ${user?.warehouse_name || 'your warehouse'}`}
            </p>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-9 gap-3">
          <Card className="bg-gradient-to-br from-green-50 to-emerald-50 border-green-200">
            <CardContent className="p-3 text-center">
              <ShoppingCart className="w-5 h-5 text-green-600 mx-auto mb-1" />
              <p className="text-xs text-green-700 font-medium">Total Orders</p>
              <p className="text-2xl font-bold text-green-800">{summary.total_orders || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-orange-50 to-amber-50 border-orange-200">
            <CardContent className="p-3 text-center">
              <Package className="w-5 h-5 text-orange-600 mx-auto mb-1" />
              <p className="text-xs text-orange-700 font-medium">Pending</p>
              <p className="text-2xl font-bold text-orange-800">{summary.total_pending || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-teal-50 to-emerald-50 border-teal-200">
            <CardContent className="p-3 text-center">
              <CheckCircle2 className="w-5 h-5 text-teal-600 mx-auto mb-1" />
              <p className="text-xs text-teal-700 font-medium">Delivered</p>
              <p className="text-2xl font-bold text-teal-800">{summary.total_delivered || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-red-50 to-rose-50 border-red-200">
            <CardContent className="p-3 text-center">
              <XCircle className="w-5 h-5 text-red-600 mx-auto mb-1" />
              <p className="text-xs text-red-700 font-medium">Cancelled</p>
              <p className="text-2xl font-bold text-red-800">{summary.total_cancelled || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200">
            <CardContent className="p-3 text-center">
              <Home className="w-5 h-5 text-blue-600 mx-auto mb-1" />
              <p className="text-xs text-blue-700 font-medium">Domestic</p>
              <p className="text-2xl font-bold text-blue-800">{summary.total_domestic || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-purple-50 to-violet-50 border-purple-200">
            <CardContent className="p-3 text-center">
              <Building2 className="w-5 h-5 text-purple-600 mx-auto mb-1" />
              <p className="text-xs text-purple-700 font-medium">Commercial</p>
              <p className="text-2xl font-bold text-purple-800">{summary.total_commercial || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-emerald-50 to-green-50 border-emerald-200">
            <CardContent className="p-3 text-center">
              <Banknote className="w-5 h-5 text-emerald-600 mx-auto mb-1" />
              <p className="text-xs text-emerald-700 font-medium">Cash</p>
              <p className="text-2xl font-bold text-emerald-800">{summary.total_cash || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-sky-50 to-cyan-50 border-sky-200">
            <CardContent className="p-3 text-center">
              <Smartphone className="w-5 h-5 text-sky-600 mx-auto mb-1" />
              <p className="text-xs text-sky-700 font-medium">Online</p>
              <p className="text-2xl font-bold text-sky-800">{summary.total_online || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-amber-50 to-yellow-50 border-amber-200">
            <CardContent className="p-3 text-center">
              <Clock className="w-5 h-5 text-amber-600 mx-auto mb-1" />
              <p className="text-xs text-amber-700 font-medium">Credit</p>
              <p className="text-2xl font-bold text-amber-800">{summary.total_credit_pending || 0}</p>
            </CardContent>
          </Card>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white border">
            <TabsTrigger value="create" className="data-[state=active]:bg-green-100">
              <Plus className="w-4 h-4 mr-2" />
              Create Order
            </TabsTrigger>
            <TabsTrigger value="reports" className="data-[state=active]:bg-green-100">
              <FileText className="w-4 h-4 mr-2" />
              Order Reports
            </TabsTrigger>
          </TabsList>

          {/* Create Order Tab */}
          <TabsContent value="create" className="mt-4">
            <Card data-testid="create-order-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShoppingCart className="w-5 h-5 text-green-700" />
                  Create New Order
                </CardTitle>
                <CardDescription>Fill in the order details. Order number will be auto-generated.</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-6">
                  {isAdmin && (
                    <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                      <Label className="text-amber-800">Select Warehouse *</Label>
                      <Select value={selectedWarehouse} onValueChange={setSelectedWarehouse}>
                        <SelectTrigger className="mt-2" data-testid="warehouse-select">
                          <SelectValue placeholder="Choose a warehouse" />
                        </SelectTrigger>
                        <SelectContent>
                          {warehouses.map((w) => (
                            <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
                    <div>
                      <Label className="text-sm">Order Date *</Label>
                      <Input 
                        type="date" 
                        value={formData.order_date}
                        onChange={(e) => setFormData({ ...formData, order_date: e.target.value })}
                        className="mt-1"
                        data-testid="order-date"
                      />
                    </div>
                    <div>
                      <Label className="text-sm">Order No</Label>
                      <Input 
                        value="Auto-generated"
                        disabled
                        className="mt-1 bg-slate-100"
                      />
                    </div>
                    <div>
                      <Label className="text-sm">Connection Type *</Label>
                      <Select 
                        value={formData.connection_type} 
                        onValueChange={(v) => setFormData({ ...formData, connection_type: v, cylinder_nos: '' })}
                      >
                        <SelectTrigger className="mt-1" data-testid="connection-type">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {!useExistingCustomer ? (
                            <>
                              <SelectItem value="domestic">
                                <div className="flex items-center gap-2"><Home className="w-4 h-4" /> Domestic</div>
                              </SelectItem>
                              <SelectItem value="commercial">
                                <div className="flex items-center gap-2"><Building2 className="w-4 h-4" /> Commercial</div>
                              </SelectItem>
                            </>
                          ) : (
                            <>
                              <SelectItem value="domestic_refill">
                                <div className="flex items-center gap-2"><Home className="w-4 h-4 text-blue-600" /> Domestic Refill</div>
                              </SelectItem>
                              <SelectItem value="commercial_refill">
                                <div className="flex items-center gap-2"><Building2 className="w-4 h-4 text-blue-600" /> Commercial Refill</div>
                              </SelectItem>
                            </>
                          )}
                        </SelectContent>
                      </Select>
                    </div>
                    
                    {/* Cylinder Nos field for New Customer (domestic/commercial) only */}
                    {!useExistingCustomer && (
                      <div>
                        <Label className="text-sm">Cylinder Nos.</Label>
                        <Input 
                          value={formData.cylinder_nos}
                          onChange={(e) => setFormData({ ...formData, cylinder_nos: e.target.value })}
                          placeholder="Enter cylinder numbers"
                          className="mt-1"
                          data-testid="cylinder-nos"
                        />
                      </div>
                    )}
                  </div>

                  {/* Customer Selection */}
                  <div className="p-3 sm:p-4 bg-slate-50 border rounded-lg space-y-3 sm:space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <Label className="text-base sm:text-lg font-medium">Customer Details</Label>
                      <div className="flex gap-2">
                        <Button 
                          type="button"
                          variant={useExistingCustomer ? "default" : "outline"}
                          size="sm"
                          onClick={() => {
                            setUseExistingCustomer(true);
                            setFormData({ ...formData, connection_type: 'domestic_refill', cylinder_nos: '' });
                          }}
                          className="flex-1 sm:flex-none text-xs sm:text-sm"
                        >
                          Select Existing
                        </Button>
                        <Button 
                          type="button"
                          variant={!useExistingCustomer ? "default" : "outline"}
                          size="sm"
                          onClick={() => {
                            setUseExistingCustomer(false);
                            setFormData({ ...formData, customer_id: '', customer_name: '', mobile_number: '', address_landmark: '', connection_type: 'domestic', cylinder_nos: '' });
                          }}
                          className="flex-1 sm:flex-none text-xs sm:text-sm"
                        >
                          New Customer
                        </Button>
                      </div>
                    </div>

                    {useExistingCustomer ? (
                      <>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                        <div>
                          <Label className="text-sm">Filter by Category</Label>
                          <Select value={customerCategory} onValueChange={setCustomerCategory}>
                            <SelectTrigger className="mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">All Customers</SelectItem>
                              <SelectItem value="domestic">Domestic Only</SelectItem>
                              <SelectItem value="commercial">Commercial Only</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-sm">Select Customer *</Label>
                          <Select value={formData.customer_id} onValueChange={handleCustomerSelect}>
                            <SelectTrigger className="mt-1" data-testid="customer-select">
                              <SelectValue placeholder="Choose a customer" />
                            </SelectTrigger>
                            <SelectContent>
                              {customers.map((c) => (
                                <SelectItem key={c.id} value={c.id}>
                                  <div className="flex flex-wrap items-center gap-1 sm:gap-2">
                                    <span className="font-medium text-sm">{c.customer_name}</span>
                                    <Badge variant="outline" className="text-xs">{c.connection_type}</Badge>
                                    {c.phone && <span className="text-slate-500 text-xs">({c.phone})</span>}
                                  </div>
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      {/* Last Refill Info Panel */}
                      {formData.customer_id && (
                        <div className="mt-3 p-3 rounded-lg border" data-testid="last-refill-panel"
                          style={{ 
                            backgroundColor: loadingRefill ? '#f8fafc' : 
                              !lastRefill?.has_refill ? '#f1f5f9' :
                              lastRefill.days_since_refill <= 15 ? '#f0fdf4' :
                              lastRefill.days_since_refill <= 30 ? '#fefce8' : '#fef2f2',
                            borderColor: loadingRefill ? '#e2e8f0' :
                              !lastRefill?.has_refill ? '#cbd5e1' :
                              lastRefill.days_since_refill <= 15 ? '#bbf7d0' :
                              lastRefill.days_since_refill <= 30 ? '#fef08a' : '#fecaca'
                          }}
                        >
                          <div className="flex items-center gap-2 text-sm">
                            <Flame className="w-4 h-4 text-orange-500" />
                            <span className="font-medium text-slate-700">Last LPG Refill:</span>
                            {loadingRefill ? (
                              <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
                            ) : !lastRefill?.has_refill ? (
                              <span className="text-slate-500 italic">No refill history available</span>
                            ) : (
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="font-semibold">
                                  {(() => { try { return new Date(lastRefill.last_refill_date).toLocaleDateString('en-IN', { day: '2-digit', month: '2-digit', year: 'numeric' }); } catch { return lastRefill.last_refill_date; } })()}
                                </span>
                                <span className="text-slate-500">|</span>
                                <span className="font-semibold">{lastRefill.days_since_refill} days ago</span>
                                {getRefillBadge(lastRefill.days_since_refill)}
                                {lastRefill.days_since_refill > 30 && (
                                  <span className="text-red-600 text-xs font-medium flex items-center gap-1">
                                    <AlertTriangle className="w-3 h-3" /> Refill Alert!
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </>
                    ) : (
                      <div className="flex flex-wrap items-center gap-2">
                        <Button 
                          type="button"
                          variant="outline"
                          onClick={() => setShowNewCustomerDialog(true)}
                          className="border-green-300 text-green-700 text-sm"
                        >
                          <Plus className="w-4 h-4 mr-1 sm:mr-2" />
                          Add New Customer
                        </Button>
                        {formData.customer_name && (
                          <span className="text-sm text-green-700">Selected: {formData.customer_name}</span>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                    <div>
                      <Label className="flex items-center gap-2 text-sm"><User className="w-4 h-4" /> Customer Name *</Label>
                      <Input 
                        value={formData.customer_name}
                        onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                        placeholder="Enter customer name"
                        className="mt-1"
                        data-testid="customer-name"
                      />
                    </div>
                    <div>
                      <Label className="flex items-center gap-2 text-sm"><Phone className="w-4 h-4" /> Mobile Number (10 digits)</Label>
                      <Input 
                        value={formData.mobile_number}
                        onChange={(e) => {
                          const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                          setFormData({ ...formData, mobile_number: value });
                        }}
                        placeholder="Enter 10 digit mobile number"
                        className="mt-1"
                        maxLength={10}
                        data-testid="mobile-number"
                      />
                      {formData.mobile_number && formData.mobile_number.length !== 10 && (
                        <p className="text-xs text-red-500 mt-1">Must be 10 digits ({formData.mobile_number.length}/10)</p>
                      )}
                    </div>
                  </div>

                  <div>
                    <Label className="flex items-center gap-2 text-sm"><MapPin className="w-4 h-4" /> Address / Landmark</Label>
                    <Textarea 
                      value={formData.address_landmark}
                      onChange={(e) => setFormData({ ...formData, address_landmark: e.target.value })}
                      placeholder="Enter delivery address or landmark"
                      className="mt-1"
                      data-testid="address"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                    <div>
                      <Label className="flex items-center gap-2 text-sm"><CreditCard className="w-4 h-4" /> Payment Mode *</Label>
                      <Select 
                        value={formData.payment_mode} 
                        onValueChange={(v) => setFormData({ ...formData, payment_mode: v })}
                      >
                        <SelectTrigger className="mt-1" data-testid="payment-mode">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="cash">
                            <div className="flex items-center gap-2"><Banknote className="w-4 h-4 text-green-600" /> Cash</div>
                          </SelectItem>
                          <SelectItem value="online">
                            <div className="flex items-center gap-2"><Smartphone className="w-4 h-4 text-blue-600" /> Online</div>
                          </SelectItem>
                          <SelectItem value="credit_pending">
                            <div className="flex items-center gap-2"><Clock className="w-4 h-4 text-amber-600" /> Credit / Pending</div>
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-sm">Remarks</Label>
                      <Input 
                        value={formData.remarks}
                        onChange={(e) => setFormData({ ...formData, remarks: e.target.value })}
                        placeholder="Optional remarks"
                        className="mt-1"
                        data-testid="remarks"
                      />
                    </div>
                  </div>

                  <div className="flex flex-col sm:flex-row justify-end gap-2 pt-2">
                    <Button 
                      type="submit" 
                      disabled={submitting}
                      className="bg-green-700 hover:bg-green-800 w-full sm:w-auto"
                      data-testid="submit-order-btn"
                    >
                      {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <ShoppingCart className="w-4 h-4 mr-2" />}
                      Create Order
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Order Reports Tab */}
          <TabsContent value="reports" className="mt-4 space-y-4">
            {/* Filters */}
            <Card>
              <CardContent className="p-4">
                <div className="flex flex-wrap items-end gap-4">
                  <div>
                    <Label>Period</Label>
                    <Select value={dateRange} onValueChange={handleDateRangeChange}>
                      <SelectTrigger className="w-32 mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="daily">Daily</SelectItem>
                        <SelectItem value="weekly">Weekly</SelectItem>
                        <SelectItem value="monthly">Monthly</SelectItem>
                        <SelectItem value="yearly">Yearly</SelectItem>
                        <SelectItem value="custom">Custom</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Start Date</Label>
                    <Input 
                      type="date" 
                      value={startDate}
                      onChange={(e) => { setStartDate(e.target.value); setDateRange('custom'); }}
                      className="w-40 mt-1"
                    />
                  </div>
                  <div>
                    <Label>End Date</Label>
                    <Input 
                      type="date" 
                      value={endDate}
                      onChange={(e) => { setEndDate(e.target.value); setDateRange('custom'); }}
                      className="w-40 mt-1"
                    />
                  </div>
                  <div>
                    <Label>Payment</Label>
                    <Select value={filterPayment} onValueChange={setFilterPayment}>
                      <SelectTrigger className="w-36 mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="cash">Cash</SelectItem>
                        <SelectItem value="online">Online</SelectItem>
                        <SelectItem value="credit_pending">Credit/Pending</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Type</Label>
                    <Select value={filterConnection} onValueChange={setFilterConnection}>
                      <SelectTrigger className="w-40 mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="domestic">Domestic</SelectItem>
                        <SelectItem value="domestic_refill">Domestic Refill</SelectItem>
                        <SelectItem value="commercial">Commercial</SelectItem>
                        <SelectItem value="commercial_refill">Commercial Refill</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Status</Label>
                    <Select value={filterStatus} onValueChange={setFilterStatus}>
                      <SelectTrigger className="w-36 mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Status</SelectItem>
                        <SelectItem value="pending">Pending</SelectItem>
                        <SelectItem value="delivered">Delivered</SelectItem>
                        <SelectItem value="cancelled">Cancelled</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button variant="outline" onClick={() => { fetchOrders(); fetchSummary(); }}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Refresh
                  </Button>
                  <div className="flex gap-2 ml-auto">
                    <Button 
                      variant="outline" 
                      onClick={handleExportPDF}
                      disabled={exporting}
                      className="border-red-300 text-red-700 hover:bg-red-50"
                      data-testid="export-pdf-btn"
                    >
                      {exporting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Download className="w-4 h-4 mr-2" />}
                      PDF
                    </Button>
                    <Button 
                      variant="outline" 
                      onClick={handleExportExcel}
                      disabled={exporting}
                      className="border-green-300 text-green-700 hover:bg-green-50"
                      data-testid="export-excel-btn"
                    >
                      {exporting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <FileSpreadsheet className="w-4 h-4 mr-2" />}
                      Excel
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Enhanced Search Bar */}
            <Card className="bg-gradient-to-r from-green-50 to-emerald-50 border-green-200">
              <CardContent className="p-4">
                <Label className="text-green-800 font-medium mb-2 block">Quick Search</Label>
                <SearchBar
                  data={orders}
                  searchFields={['customer_name', 'mobile_number', 'order_no', 'address_landmark', 'warehouse_name']}
                  onFilter={setFilteredOrders}
                  placeholder="Search by customer name, mobile, order no, address..."
                  showSuggestions={true}
                  maxSuggestions={6}
                  suggestionLabelField="customer_name"
                  className="max-w-2xl"
                />
              </CardContent>
            </Card>

            {/* Orders Table */}
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle>Orders</CardTitle>
                  <Badge variant="outline" className="text-green-700">
                    {filteredOrders.length} of {orders.length} orders
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {loading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-green-700" />
                  </div>
                ) : filteredOrders.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Order No</th>
                          <th>Customer</th>
                          <th>Mobile</th>
                          <th>Type</th>
                          <th>Payment</th>
                          <th>Status</th>
                          {isAdmin && <th>Warehouse</th>}
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredOrders.map((o) => (
                          <tr key={o.id} data-testid={`order-row-${o.id}`} className={o.status === 'cancelled' ? 'bg-red-50/50 opacity-75' : ''}>
                            <td>{formatDate(o.order_date)}</td>
                            <td>
                              <Badge variant="outline" className="font-mono">
                                <Hash className="w-3 h-3 mr-1" />
                                {o.order_no}
                              </Badge>
                            </td>
                            <td className="font-medium">{o.customer_name}</td>
                            <td>{o.mobile_number || '-'}</td>
                            <td>
                              {getConnectionTypeBadge(o.connection_type)}
                              {o.cylinder_nos && (
                                <div className="text-xs text-slate-500 mt-1">
                                  <span className="font-medium">Cyl:</span> {o.cylinder_nos}
                                </div>
                              )}
                            </td>
                            <td>{getPaymentBadge(o.payment_mode)}</td>
                            <td>
                              {updatingStatus === o.id ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : o.status === 'cancelled' ? (
                                <div>
                                  {getStatusBadge('cancelled')}
                                  {o.cancellation_reason && (
                                    <p className="text-xs text-red-500 mt-1 max-w-[120px] truncate" title={o.cancellation_reason}>{o.cancellation_reason}</p>
                                  )}
                                </div>
                              ) : (
                                <Select 
                                  value={o.status || 'pending'} 
                                  onValueChange={(v) => handleStatusChange(o.id, v)}
                                >
                                  <SelectTrigger className="w-32 h-8 text-xs" data-testid={`status-select-${o.id}`}>
                                    <SelectValue>
                                      {getStatusBadge(o.status || 'pending')}
                                    </SelectValue>
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="pending">
                                      <div className="flex items-center gap-2">
                                        <Package className="w-3 h-3 text-orange-600" /> Pending
                                      </div>
                                    </SelectItem>
                                    <SelectItem value="delivered">
                                      <div className="flex items-center gap-2">
                                        <CheckCircle2 className="w-3 h-3 text-green-600" /> Delivered
                                      </div>
                                    </SelectItem>
                                    <SelectItem value="cancelled">
                                      <div className="flex items-center gap-2">
                                        <XCircle className="w-3 h-3 text-red-600" /> Cancel Order
                                      </div>
                                    </SelectItem>
                                  </SelectContent>
                                </Select>
                              )}
                            </td>
                            {isAdmin && <td className="text-sm">{o.warehouse_name}</td>}
                            <td>
                              <div className="flex gap-1">
                                <Button 
                                  variant="ghost" 
                                  size="sm"
                                  onClick={() => handleDownloadPDF(o.id)}
                                  className="text-red-600 hover:text-red-800"
                                  title="Download PDF"
                                >
                                  <Download className="w-4 h-4" />
                                </Button>
                                {o.status !== 'cancelled' && (
                                  <Button 
                                    variant="ghost" 
                                    size="sm"
                                    onClick={() => handleEdit(o)}
                                    className="text-blue-600 hover:text-blue-800"
                                    title="Edit"
                                    data-testid={`edit-order-${o.id}`}
                                  >
                                    <Edit className="w-4 h-4" />
                                  </Button>
                                )}
                                {isAdmin && (
                                  <Button 
                                    variant="ghost" 
                                    size="sm"
                                    onClick={() => handleDelete(o.id)}
                                    className="text-red-600 hover:text-red-800"
                                    title="Delete"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </Button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <ShoppingCart className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">No orders found for selected period</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* New Customer Dialog */}
        <Dialog open={showNewCustomerDialog} onOpenChange={setShowNewCustomerDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add New Customer</DialogTitle>
              <DialogDescription>Add a new customer to the database</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label>Customer Name *</Label>
                <Input 
                  value={newCustomerData.customer_name}
                  onChange={(e) => setNewCustomerData({ ...newCustomerData, customer_name: e.target.value })}
                  placeholder="Enter customer name"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Mobile Number</Label>
                <Input 
                  value={newCustomerData.mobile_number}
                  onChange={(e) => setNewCustomerData({ ...newCustomerData, mobile_number: e.target.value })}
                  placeholder="Enter mobile number"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Address</Label>
                <Textarea 
                  value={newCustomerData.address}
                  onChange={(e) => setNewCustomerData({ ...newCustomerData, address: e.target.value })}
                  placeholder="Enter address"
                  className="mt-1"
                />
              </div>
              <div>
                <Label>Connection Type</Label>
                <Select 
                  value={newCustomerData.connection_type} 
                  onValueChange={(v) => setNewCustomerData({ ...newCustomerData, connection_type: v })}
                >
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="domestic">Domestic</SelectItem>
                    <SelectItem value="commercial">Commercial</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline">Cancel</Button>
              </DialogClose>
              <Button 
                onClick={handleAddNewCustomer} 
                disabled={submitting}
                className="bg-green-700 hover:bg-green-800"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                Add Customer
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Edit Order Dialog */}
        <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
          <DialogContent className="max-w-xl">
            <DialogHeader>
              <DialogTitle>Edit Order {editingOrder?.order_no}</DialogTitle>
              <DialogDescription>Update order details</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Order Date</Label>
                  <Input 
                    type="date" 
                    value={editForm.order_date || ''}
                    onChange={(e) => setEditForm({ ...editForm, order_date: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Connection Type</Label>
                  <Select 
                    value={editForm.connection_type || 'domestic'} 
                    onValueChange={(v) => setEditForm({ ...editForm, connection_type: v, cylinder_nos: v.includes('refill') ? editForm.cylinder_nos : '' })}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="domestic">Domestic</SelectItem>
                      <SelectItem value="domestic_refill">Domestic Refill</SelectItem>
                      <SelectItem value="commercial">Commercial</SelectItem>
                      <SelectItem value="commercial_refill">Commercial Refill</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              {/* Cylinder Nos for refill types in edit form */}
              {(editForm.connection_type === 'domestic_refill' || editForm.connection_type === 'commercial_refill') && (
                <div>
                  <Label>Cylinder Nos. *</Label>
                  <Input 
                    value={editForm.cylinder_nos || ''}
                    onChange={(e) => setEditForm({ ...editForm, cylinder_nos: e.target.value })}
                    placeholder="Enter cylinder numbers"
                    className="mt-1"
                  />
                </div>
              )}
              
              <div>
                <Label>Customer Name</Label>
                <Input 
                  value={editForm.customer_name || ''}
                  onChange={(e) => setEditForm({ ...editForm, customer_name: e.target.value })}
                  className="mt-1"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Mobile Number</Label>
                  <Input 
                    value={editForm.mobile_number || ''}
                    onChange={(e) => setEditForm({ ...editForm, mobile_number: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Payment Mode</Label>
                  <Select 
                    value={editForm.payment_mode || 'cash'} 
                    onValueChange={(v) => setEditForm({ ...editForm, payment_mode: v })}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cash">Cash</SelectItem>
                      <SelectItem value="online">Online</SelectItem>
                      <SelectItem value="credit_pending">Credit/Pending</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label>Address / Landmark</Label>
                <Textarea 
                  value={editForm.address_landmark || ''}
                  onChange={(e) => setEditForm({ ...editForm, address_landmark: e.target.value })}
                  className="mt-1"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Remarks</Label>
                  <Input 
                    value={editForm.remarks || ''}
                    onChange={(e) => setEditForm({ ...editForm, remarks: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Status</Label>
                  <Select 
                    value={editForm.status || 'pending'} 
                    onValueChange={(v) => setEditForm({ ...editForm, status: v })}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="pending">Pending</SelectItem>
                      <SelectItem value="delivered">Delivered</SelectItem>
                      <SelectItem value="cancelled">Cancelled</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline">Cancel</Button>
              </DialogClose>
              <Button 
                onClick={handleEditSubmit} 
                disabled={submitting}
                className="bg-green-700 hover:bg-green-800"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                Save Changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Cancel Order Confirmation Dialog */}
        <Dialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-red-700">
                <XCircle className="w-5 h-5" /> Cancel Order
              </DialogTitle>
              <DialogDescription>
                Are you sure you want to cancel this order? This action will exclude it from sales data and reporting calculations.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <Label className="text-sm font-medium">Cancellation Reason (optional)</Label>
              <Textarea
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="Enter reason for cancellation..."
                className="mt-2"
                data-testid="cancel-reason-input"
              />
            </div>
            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => { setCancelDialogOpen(false); setCancellingOrder(null); }}>
                Go Back
              </Button>
              <Button 
                variant="destructive" 
                onClick={handleConfirmCancel}
                data-testid="confirm-cancel-btn"
              >
                <XCircle className="w-4 h-4 mr-2" /> Confirm Cancel
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default OrderManagement;
