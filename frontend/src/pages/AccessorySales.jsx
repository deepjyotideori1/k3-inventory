import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { 
  getCustomers,
  getAccessories,
  getAccessoryDealers,
  getWarehouses
} from '../lib/api';
import api from '../lib/api';
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
  ShoppingBag,
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
  User,
  Phone,
  MapPin,
  Package,
  Users
} from 'lucide-react';
import { getTodayDate, formatDate } from '../lib/utils';
import { toast } from 'sonner';

const AccessorySales = () => {
  const { user, isAdmin } = useAuth();
  const [loading, setLoading] = useState(true);
  const [sales, setSales] = useState([]);
  const [summary, setSummary] = useState({});
  const [customers, setCustomers] = useState([]);
  const [accessories, setAccessories] = useState([]);
  const [dealers, setDealers] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [activeTab, setActiveTab] = useState('create');
  
  // Form state
  const [formData, setFormData] = useState({
    sale_date: getTodayDate(),
    customer_id: '',
    customer_name: '',
    mobile_number: '',
    address: '',
    connection_type: 'domestic',
    accessory_id: '',
    dealer_id: '',
    quantity: 1,
    payment_mode: 'cash',
    remarks: ''
  });
  const [submitting, setSubmitting] = useState(false);
  const [selectedWarehouse, setSelectedWarehouse] = useState('');
  const [useExistingCustomer, setUseExistingCustomer] = useState(false);
  
  // Edit state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingSale, setEditingSale] = useState(null);
  const [editForm, setEditForm] = useState({});
  
  // Filters
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [filterAccessory, setFilterAccessory] = useState('all');
  const [filterDealer, setFilterDealer] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    fetchInitialData();
  }, []);

  useEffect(() => {
    if (startDate && endDate) {
      fetchSales();
    }
  }, [startDate, endDate, filterAccessory, filterDealer, searchQuery]);

  const fetchInitialData = async () => {
    try {
      const [customersRes, accessoriesRes, dealersRes] = await Promise.all([
        getCustomers(),
        getAccessories(),
        getAccessoryDealers()
      ]);
      setCustomers(customersRes.data);
      setAccessories(accessoriesRes.data);
      setDealers(dealersRes.data);
      
      if (isAdmin) {
        const warehousesRes = await getWarehouses();
        setWarehouses(warehousesRes.data.filter(w => !w.is_plant));
      }
    } catch (error) {
      console.error('Failed to fetch initial data:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const fetchSales = async () => {
    setLoading(true);
    try {
      const params = {};
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      if (filterAccessory !== 'all') params.accessory_id = filterAccessory;
      if (filterDealer !== 'all') params.dealer_id = filterDealer;
      if (searchQuery) params.search = searchQuery;
      
      const response = await api.get('/accessory-sales', { params });
      setSales(response.data);
      
      // Calculate summary
      const summaryData = {
        total_sales: response.data.length,
        total_quantity: response.data.reduce((sum, s) => sum + s.quantity, 0)
      };
      setSummary(summaryData);
    } catch (error) {
      console.error('Failed to fetch sales:', error);
      toast.error('Failed to load sales');
    } finally {
      setLoading(false);
    }
  };

  const handleCustomerSelect = (customerId) => {
    const customer = customers.find(c => c.id === customerId);
    if (customer) {
      setFormData({
        ...formData,
        customer_id: customerId,
        customer_name: customer.customer_name,
        mobile_number: customer.phone || '',
        address: customer.address || '',
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
    if (!formData.accessory_id) {
      toast.error('Please select an accessory');
      return;
    }
    if (!formData.dealer_id) {
      toast.error('Please select a dealer');
      return;
    }
    if (isAdmin && !selectedWarehouse) {
      toast.error('Please select a warehouse');
      return;
    }
    
    setSubmitting(true);
    try {
      const data = {
        ...formData,
        warehouse_id: isAdmin ? selectedWarehouse : user?.warehouse_id
      };
      
      await api.post('/accessory-sales', data);
      toast.success('Accessory sale recorded successfully');
      
      // Reset form
      setFormData({
        sale_date: getTodayDate(),
        customer_id: '',
        customer_name: '',
        mobile_number: '',
        address: '',
        connection_type: 'domestic',
        accessory_id: '',
        dealer_id: '',
        quantity: 1,
        payment_mode: 'cash',
        remarks: ''
      });
      setUseExistingCustomer(false);
      fetchSales();
      setActiveTab('reports');
    } catch (error) {
      console.error('Failed to create sale:', error);
      toast.error(error.response?.data?.detail || 'Failed to create sale');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (sale) => {
    setEditingSale(sale);
    setEditForm({
      sale_date: sale.sale_date,
      customer_name: sale.customer_name,
      mobile_number: sale.mobile_number || '',
      address: sale.address || '',
      connection_type: sale.connection_type,
      accessory_id: sale.accessory_id,
      dealer_id: sale.dealer_id,
      quantity: sale.quantity,
      payment_mode: sale.payment_mode,
      remarks: sale.remarks || ''
    });
    setEditDialogOpen(true);
  };

  const handleEditSubmit = async () => {
    if (!editingSale) return;
    
    setSubmitting(true);
    try {
      await api.put(`/accessory-sales/${editingSale.id}`, editForm);
      toast.success('Sale updated successfully');
      setEditDialogOpen(false);
      setEditingSale(null);
      fetchSales();
    } catch (error) {
      console.error('Failed to update sale:', error);
      toast.error('Failed to update sale');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (saleId) => {
    if (!window.confirm('Are you sure you want to delete this sale?')) return;
    
    try {
      await api.delete(`/accessory-sales/${saleId}`);
      toast.success('Sale deleted successfully');
      fetchSales();
    } catch (error) {
      console.error('Failed to delete sale:', error);
      toast.error('Failed to delete sale');
    }
  };

  const handleExportPDF = async () => {
    setExporting(true);
    try {
      const params = {};
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      if (filterAccessory !== 'all') params.accessory_id = filterAccessory;
      if (filterDealer !== 'all') params.dealer_id = filterDealer;
      
      const response = await api.get('/export/accessory-sales-pdf', { params, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `accessory_sales_${new Date().toISOString().split('T')[0]}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
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
      const params = {};
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      if (filterAccessory !== 'all') params.accessory_id = filterAccessory;
      if (filterDealer !== 'all') params.dealer_id = filterDealer;
      
      const response = await api.get('/export/accessory-sales-excel', { params, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `accessory_sales_${new Date().toISOString().split('T')[0]}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success('Excel exported successfully');
    } catch (error) {
      toast.error('Failed to export Excel');
    } finally {
      setExporting(false);
    }
  };

  const getAccessoryName = (id) => accessories.find(a => a.id === id)?.name || 'Unknown';
  const getDealerName = (id) => dealers.find(d => d.id === id)?.name || 'Unknown';

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-800">Accessory Sales</h1>
            <p className="text-slate-500 mt-1">Record and manage accessory-only sales</p>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-gradient-to-br from-green-50 to-emerald-50 border-green-200">
            <CardContent className="p-4 text-center">
              <ShoppingBag className="w-6 h-6 text-green-600 mx-auto mb-2" />
              <p className="text-sm text-green-700 font-medium">Total Sales</p>
              <p className="text-2xl font-bold text-green-800">{summary.total_sales || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200">
            <CardContent className="p-4 text-center">
              <Package className="w-6 h-6 text-blue-600 mx-auto mb-2" />
              <p className="text-sm text-blue-700 font-medium">Total Quantity</p>
              <p className="text-2xl font-bold text-blue-800">{summary.total_quantity || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-purple-50 to-violet-50 border-purple-200">
            <CardContent className="p-4 text-center">
              <Users className="w-6 h-6 text-purple-600 mx-auto mb-2" />
              <p className="text-sm text-purple-700 font-medium">Accessories</p>
              <p className="text-2xl font-bold text-purple-800">{accessories.length}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-orange-50 to-amber-50 border-orange-200">
            <CardContent className="p-4 text-center">
              <Building2 className="w-6 h-6 text-orange-600 mx-auto mb-2" />
              <p className="text-sm text-orange-700 font-medium">Dealers</p>
              <p className="text-2xl font-bold text-orange-800">{dealers.length}</p>
            </CardContent>
          </Card>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white border">
            <TabsTrigger value="create" className="data-[state=active]:bg-green-100">
              <Plus className="w-4 h-4 mr-2" />
              Record Sale
            </TabsTrigger>
            <TabsTrigger value="reports" className="data-[state=active]:bg-green-100">
              <FileText className="w-4 h-4 mr-2" />
              Sales Reports
            </TabsTrigger>
          </TabsList>

          {/* Create Sale Tab */}
          <TabsContent value="create" className="mt-4">
            <Card data-testid="create-accessory-sale-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ShoppingBag className="w-5 h-5 text-green-700" />
                  Record Accessory Sale
                </CardTitle>
                <CardDescription>Record a sale for accessories only (no cylinders or refills)</CardDescription>
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
                      <Label>Sale Date *</Label>
                      <Input 
                        type="date" 
                        value={formData.sale_date}
                        onChange={(e) => setFormData({ ...formData, sale_date: e.target.value })}
                        className="mt-1"
                        data-testid="sale-date"
                      />
                    </div>
                    <div>
                      <Label>Connection Type</Label>
                      <Select 
                        value={formData.connection_type} 
                        onValueChange={(v) => setFormData({ ...formData, connection_type: v })}
                      >
                        <SelectTrigger className="mt-1" data-testid="connection-type">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="domestic">
                            <div className="flex items-center gap-2"><Home className="w-4 h-4" /> Domestic</div>
                          </SelectItem>
                          <SelectItem value="commercial">
                            <div className="flex items-center gap-2"><Building2 className="w-4 h-4" /> Commercial</div>
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Payment Mode</Label>
                      <Select 
                        value={formData.payment_mode} 
                        onValueChange={(v) => setFormData({ ...formData, payment_mode: v })}
                      >
                        <SelectTrigger className="mt-1" data-testid="payment-mode">
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
                            setFormData({ ...formData, customer_id: '', customer_name: '', mobile_number: '', address: '' });
                          }}
                        >
                          New Customer
                        </Button>
                      </div>
                    </div>

                    {useExistingCustomer ? (
                      <div>
                        <Label>Select Customer</Label>
                        <Select value={formData.customer_id} onValueChange={handleCustomerSelect}>
                          <SelectTrigger className="mt-1" data-testid="select-customer">
                            <SelectValue placeholder="Search and select customer" />
                          </SelectTrigger>
                          <SelectContent>
                            {customers.map((c) => (
                              <SelectItem key={c.id} value={c.id}>
                                {c.customer_name} - {c.phone || 'No phone'}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <Label>Customer Name *</Label>
                          <div className="relative">
                            <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
                            <Input 
                              value={formData.customer_name}
                              onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                              placeholder="Enter customer name"
                              className="pl-10 mt-1"
                              data-testid="customer-name"
                            />
                          </div>
                        </div>
                        <div>
                          <Label>Mobile Number</Label>
                          <div className="relative">
                            <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
                            <Input 
                              value={formData.mobile_number}
                              onChange={(e) => setFormData({ ...formData, mobile_number: e.target.value })}
                              placeholder="Enter mobile number"
                              className="pl-10 mt-1"
                              data-testid="mobile-number"
                            />
                          </div>
                        </div>
                      </div>
                    )}
                    
                    <div>
                      <Label>Address</Label>
                      <div className="relative">
                        <MapPin className="absolute left-3 top-3 w-4 h-4 text-slate-400" />
                        <Textarea 
                          value={formData.address}
                          onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                          placeholder="Enter address"
                          className="pl-10 mt-1"
                          data-testid="address"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Accessory Selection */}
                  <div className="p-4 bg-green-50 border border-green-200 rounded-lg space-y-4">
                    <Label className="text-lg font-medium text-green-800">Accessory Details</Label>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <Label>Select Accessory *</Label>
                        <Select value={formData.accessory_id} onValueChange={(v) => setFormData({ ...formData, accessory_id: v })}>
                          <SelectTrigger className="mt-1" data-testid="select-accessory">
                            <SelectValue placeholder="Choose accessory" />
                          </SelectTrigger>
                          <SelectContent>
                            {accessories.map((a) => (
                              <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label>Select Dealer *</Label>
                        <Select value={formData.dealer_id} onValueChange={(v) => setFormData({ ...formData, dealer_id: v })}>
                          <SelectTrigger className="mt-1" data-testid="select-dealer">
                            <SelectValue placeholder="Choose dealer" />
                          </SelectTrigger>
                          <SelectContent>
                            {dealers.map((d) => (
                              <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label>Quantity *</Label>
                        <Input 
                          type="number"
                          min="1"
                          value={formData.quantity}
                          onChange={(e) => setFormData({ ...formData, quantity: parseInt(e.target.value) || 1 })}
                          className="mt-1"
                          data-testid="quantity"
                        />
                      </div>
                    </div>
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

                  <div className="flex justify-end gap-2">
                    <Button type="button" variant="outline" onClick={() => setActiveTab('reports')}>
                      Cancel
                    </Button>
                    <Button 
                      type="submit" 
                      disabled={submitting}
                      className="bg-green-700 hover:bg-green-800"
                      data-testid="submit-sale-btn"
                    >
                      {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                      Record Sale
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Reports Tab */}
          <TabsContent value="reports" className="mt-4 space-y-4">
            {/* Filters */}
            <Card>
              <CardContent className="p-4">
                <div className="flex flex-wrap items-end gap-4">
                  <div>
                    <Label>Start Date</Label>
                    <Input 
                      type="date" 
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-40 mt-1"
                    />
                  </div>
                  <div>
                    <Label>End Date</Label>
                    <Input 
                      type="date" 
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-40 mt-1"
                    />
                  </div>
                  <div>
                    <Label>Accessory</Label>
                    <Select value={filterAccessory} onValueChange={setFilterAccessory}>
                      <SelectTrigger className="w-40 mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Accessories</SelectItem>
                        {accessories.map((a) => (
                          <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Dealer</Label>
                    <Select value={filterDealer} onValueChange={setFilterDealer}>
                      <SelectTrigger className="w-40 mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Dealers</SelectItem>
                        {dealers.map((d) => (
                          <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex-1 min-w-[200px]">
                    <Label>Search</Label>
                    <div className="flex gap-2 mt-1">
                      <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <Input 
                          type="text"
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && fetchSales()}
                          placeholder="Search customer name..."
                          className="pl-10"
                          data-testid="search-input"
                        />
                      </div>
                      <Button 
                        onClick={fetchSales}
                        className="bg-green-700 hover:bg-green-800"
                        data-testid="search-btn"
                      >
                        <Search className="w-4 h-4 mr-2" />
                        Search
                      </Button>
                    </div>
                  </div>
                  <Button variant="outline" onClick={fetchSales}>
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

            {/* Sales Table */}
            <Card>
              <CardHeader>
                <CardTitle>Accessory Sales ({sales.length})</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {loading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-green-700" />
                  </div>
                ) : sales.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Customer</th>
                          <th>Mobile</th>
                          <th>Type</th>
                          <th>Accessory</th>
                          <th>Dealer</th>
                          <th>Qty</th>
                          <th>Payment</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sales.map((s) => (
                          <tr key={s.id} data-testid={`sale-row-${s.id}`}>
                            <td>{formatDate(s.sale_date)}</td>
                            <td className="font-medium">{s.customer_name}</td>
                            <td>{s.mobile_number || '-'}</td>
                            <td>
                              <Badge variant={s.connection_type === 'domestic' ? 'default' : 'secondary'}>
                                {s.connection_type === 'domestic' ? <Home className="w-3 h-3 mr-1" /> : <Building2 className="w-3 h-3 mr-1" />}
                                {s.connection_type}
                              </Badge>
                            </td>
                            <td>{s.accessory_name || getAccessoryName(s.accessory_id)}</td>
                            <td>{s.dealer_name || getDealerName(s.dealer_id)}</td>
                            <td>{s.quantity}</td>
                            <td>
                              <Badge variant="outline">{s.payment_mode}</Badge>
                            </td>
                            <td>
                              <div className="flex gap-1">
                                <Button 
                                  variant="ghost" 
                                  size="sm"
                                  onClick={() => handleEdit(s)}
                                  className="text-blue-600 hover:text-blue-800"
                                  data-testid={`edit-sale-${s.id}`}
                                >
                                  <Edit className="w-4 h-4" />
                                </Button>
                                {isAdmin && (
                                  <Button 
                                    variant="ghost" 
                                    size="sm"
                                    onClick={() => handleDelete(s.id)}
                                    className="text-red-600 hover:text-red-800"
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
                    <ShoppingBag className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">No sales found. Select date range to view sales.</p>
                    <Button 
                      className="mt-4 bg-green-700 hover:bg-green-800"
                      onClick={() => setActiveTab('create')}
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Record First Sale
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Edit Dialog */}
        <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Edit Accessory Sale</DialogTitle>
              <DialogDescription>Update sale information</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Sale Date</Label>
                  <Input 
                    type="date" 
                    value={editForm.sale_date || ''}
                    onChange={(e) => setEditForm({ ...editForm, sale_date: e.target.value })}
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
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Customer Name</Label>
                  <Input 
                    value={editForm.customer_name || ''}
                    onChange={(e) => setEditForm({ ...editForm, customer_name: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Mobile Number</Label>
                  <Input 
                    value={editForm.mobile_number || ''}
                    onChange={(e) => setEditForm({ ...editForm, mobile_number: e.target.value })}
                    className="mt-1"
                  />
                </div>
              </div>
              <div>
                <Label>Address</Label>
                <Textarea 
                  value={editForm.address || ''}
                  onChange={(e) => setEditForm({ ...editForm, address: e.target.value })}
                  className="mt-1"
                />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <Label>Accessory</Label>
                  <Select 
                    value={editForm.accessory_id || ''} 
                    onValueChange={(v) => setEditForm({ ...editForm, accessory_id: v })}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {accessories.map((a) => (
                        <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Dealer</Label>
                  <Select 
                    value={editForm.dealer_id || ''} 
                    onValueChange={(v) => setEditForm({ ...editForm, dealer_id: v })}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {dealers.map((d) => (
                        <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Quantity</Label>
                  <Input 
                    type="number"
                    min="1"
                    value={editForm.quantity || 1}
                    onChange={(e) => setEditForm({ ...editForm, quantity: parseInt(e.target.value) || 1 })}
                    className="mt-1"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
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
                <div>
                  <Label>Remarks</Label>
                  <Input 
                    value={editForm.remarks || ''}
                    onChange={(e) => setEditForm({ ...editForm, remarks: e.target.value })}
                    className="mt-1"
                  />
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
      </div>
    </Layout>
  );
};

export default AccessorySales;
