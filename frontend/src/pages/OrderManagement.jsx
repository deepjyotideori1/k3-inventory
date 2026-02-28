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
  getWarehouses
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
  Truck
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
      setCustomers(response.data);
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

  const handleCustomerSelect = (customerId) => {
    const customer = customers.find(c => c.id === customerId);
    if (customer) {
      setFormData({
        ...formData,
        customer_id: customerId,
        customer_name: customer.customer_name,
        mobile_number: customer.consumer_no || '',
        address_landmark: customer.address || '',
        connection_type: customer.connection_type
      });
    }
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

  const handleEdit = (order) => {
    setEditingOrder(order);
    setEditForm({
      order_date: order.order_date,
      customer_name: order.customer_name,
      mobile_number: order.mobile_number,
      address_landmark: order.address_landmark,
      connection_type: order.connection_type,
      payment_mode: order.payment_mode,
      remarks: order.remarks
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
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
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

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <Label>Order Date *</Label>
                      <Input 
                        type="date" 
                        value={formData.order_date}
                        onChange={(e) => setFormData({ ...formData, order_date: e.target.value })}
                        className="mt-1"
                        data-testid="order-date"
                      />
                    </div>
                    <div>
                      <Label>Order No</Label>
                      <Input 
                        value="Auto-generated"
                        disabled
                        className="mt-1 bg-slate-100"
                      />
                    </div>
                    <div>
                      <Label>Connection Type *</Label>
                      <Select 
                        value={formData.connection_type} 
                        onValueChange={(v) => setFormData({ ...formData, connection_type: v, cylinder_nos: '' })}
                      >
                        <SelectTrigger className="mt-1" data-testid="connection-type">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="domestic">
                            <div className="flex items-center gap-2"><Home className="w-4 h-4" /> Domestic</div>
                          </SelectItem>
                          <SelectItem value="domestic_refill">
                            <div className="flex items-center gap-2"><Home className="w-4 h-4 text-blue-600" /> Domestic Refill</div>
                          </SelectItem>
                          <SelectItem value="commercial">
                            <div className="flex items-center gap-2"><Building2 className="w-4 h-4" /> Commercial</div>
                          </SelectItem>
                          <SelectItem value="commercial_refill">
                            <div className="flex items-center gap-2"><Building2 className="w-4 h-4 text-blue-600" /> Commercial Refill</div>
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    
                    {/* Cylinder Nos field for refill types */}
                    {(formData.connection_type === 'domestic_refill' || formData.connection_type === 'commercial_refill') && (
                      <div>
                        <Label>Cylinder Nos. *</Label>
                        <Input 
                          value={formData.cylinder_nos}
                          onChange={(e) => setFormData({ ...formData, cylinder_nos: e.target.value })}
                          placeholder="Enter cylinder numbers (e.g., CYL001, CYL002)"
                          className="mt-1"
                          data-testid="cylinder-nos"
                        />
                        <p className="text-xs text-slate-500 mt-1">Enter cylinder numbers for refill tracking</p>
                      </div>
                    )}
                  </div>

                  {/* Customer Selection */}
                  <div className="p-4 bg-slate-50 border rounded-lg space-y-4">
                    <div className="flex items-center justify-between">
                      <Label className="text-lg font-medium">Customer Details</Label>
                      <div className="flex gap-2">
                        <Button 
                          type="button"
                          variant={useExistingCustomer ? "default" : "outline"}
                          size="sm"
                          onClick={() => setUseExistingCustomer(true)}
                        >
                          Select Existing
                        </Button>
                        <Button 
                          type="button"
                          variant={!useExistingCustomer ? "default" : "outline"}
                          size="sm"
                          onClick={() => {
                            setUseExistingCustomer(false);
                            setFormData({ ...formData, customer_id: '', customer_name: '', mobile_number: '', address_landmark: '' });
                          }}
                        >
                          New Customer
                        </Button>
                      </div>
                    </div>

                    {useExistingCustomer ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <Label>Filter by Category</Label>
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
                          <Label>Select Customer *</Label>
                          <Select value={formData.customer_id} onValueChange={handleCustomerSelect}>
                            <SelectTrigger className="mt-1" data-testid="customer-select">
                              <SelectValue placeholder="Choose a customer" />
                            </SelectTrigger>
                            <SelectContent>
                              {customers.map((c) => (
                                <SelectItem key={c.id} value={c.id}>
                                  {c.customer_name} - {c.address?.substring(0, 30)}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Button 
                          type="button"
                          variant="outline"
                          onClick={() => setShowNewCustomerDialog(true)}
                          className="border-green-300 text-green-700"
                        >
                          <Plus className="w-4 h-4 mr-2" />
                          Add New Customer
                        </Button>
                        {formData.customer_name && (
                          <span className="text-sm text-green-700">Selected: {formData.customer_name}</span>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label className="flex items-center gap-2"><User className="w-4 h-4" /> Customer Name *</Label>
                      <Input 
                        value={formData.customer_name}
                        onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                        placeholder="Enter customer name"
                        className="mt-1"
                        data-testid="customer-name"
                      />
                    </div>
                    <div>
                      <Label className="flex items-center gap-2"><Phone className="w-4 h-4" /> Mobile Number</Label>
                      <Input 
                        value={formData.mobile_number}
                        onChange={(e) => setFormData({ ...formData, mobile_number: e.target.value })}
                        placeholder="Enter mobile number"
                        className="mt-1"
                        data-testid="mobile-number"
                      />
                    </div>
                  </div>

                  <div>
                    <Label className="flex items-center gap-2"><MapPin className="w-4 h-4" /> Address / Landmark</Label>
                    <Textarea 
                      value={formData.address_landmark}
                      onChange={(e) => setFormData({ ...formData, address_landmark: e.target.value })}
                      placeholder="Enter delivery address or landmark"
                      className="mt-1"
                      data-testid="address"
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label className="flex items-center gap-2"><CreditCard className="w-4 h-4" /> Payment Mode *</Label>
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
                      <Label>Remarks</Label>
                      <Input 
                        value={formData.remarks}
                        onChange={(e) => setFormData({ ...formData, remarks: e.target.value })}
                        placeholder="Optional remarks"
                        className="mt-1"
                        data-testid="remarks"
                      />
                    </div>
                  </div>

                  <div className="flex justify-end gap-2">
                    <Button 
                      type="submit" 
                      disabled={submitting}
                      className="bg-green-700 hover:bg-green-800"
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
                      <SelectTrigger className="w-36 mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="domestic">Domestic</SelectItem>
                        <SelectItem value="commercial">Commercial</SelectItem>
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
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex-1 min-w-[200px]">
                    <Label>Search</Label>
                    <div className="relative mt-1">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
                      <Input 
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search by name, mobile, order no..."
                        className="pl-10"
                      />
                    </div>
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

            {/* Orders Table */}
            <Card>
              <CardHeader>
                <CardTitle>Orders ({orders.length})</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {loading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-green-700" />
                  </div>
                ) : orders.length > 0 ? (
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
                        {orders.map((o) => (
                          <tr key={o.id} data-testid={`order-row-${o.id}`}>
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
                              <Badge variant={o.connection_type === 'domestic' ? 'default' : 'secondary'}>
                                {o.connection_type === 'domestic' ? <Home className="w-3 h-3 mr-1" /> : <Building2 className="w-3 h-3 mr-1" />}
                                {o.connection_type}
                              </Badge>
                            </td>
                            <td>{getPaymentBadge(o.payment_mode)}</td>
                            <td>
                              {updatingStatus === o.id ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
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
                                {(isAdmin || o.order_date === getTodayDate()) && (
                                  <Button 
                                    variant="ghost" 
                                    size="sm"
                                    onClick={() => handleEdit(o)}
                                    className="text-blue-600 hover:text-blue-800"
                                    title="Edit"
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
                    onValueChange={(v) => setEditForm({ ...editForm, connection_type: v })}
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
              <div>
                <Label>Remarks</Label>
                <Input 
                  value={editForm.remarks || ''}
                  onChange={(e) => setEditForm({ ...editForm, remarks: e.target.value })}
                  className="mt-1"
                />
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
      </div>
    </Layout>
  );
};

export default OrderManagement;
