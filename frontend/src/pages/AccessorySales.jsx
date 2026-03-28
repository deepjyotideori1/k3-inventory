import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { 
  getAccessories,
  getCustomers,
  getAccessorySales,
  createAccessorySale,
  deleteAccessorySale,
  getAccessorySalesSummary,
  exportAccessorySalesPDF,
  exportAccessorySalesExcel,
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
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from '../components/ui/dialog';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import SearchBar from '../components/SearchBar';
import { HighlightMatch } from '../components/SearchBar';
import SearchableSelect from '../components/SearchableSelect';
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
  User,
  Phone,
  MapPin,
  Package,
  DollarSign,
  CreditCard,
  Banknote,
  Clock,
  RefreshCw,
  X,
  UserPlus,
  Users
} from 'lucide-react';
import { getTodayDate, formatDate, formatINR, getDateRange } from '../lib/utils';
import { toast } from 'sonner';

const AccessorySales = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  
  // Data state
  const [accessories, setAccessories] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [sales, setSales] = useState([]);
  const [filteredSales, setFilteredSales] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [summary, setSummary] = useState({});
  const [warehouses, setWarehouses] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Form state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [customerMode, setCustomerMode] = useState('existing');
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [newCustomer, setNewCustomer] = useState({ name: '', phone: '', address: '' });
  const [saleItems, setSaleItems] = useState([{ accessory_id: '', quantity: 1, unit_price: 0 }]);
  const [paymentMode, setPaymentMode] = useState('cash');
  const [saleDate, setSaleDate] = useState(getTodayDate());
  const [memoNo, setMemoNo] = useState('');
  const [remarks, setRemarks] = useState('');
  const [selectedWarehouse, setSelectedWarehouse] = useState('');
  const [submitting, setSubmitting] = useState(false);
  
  // Filters
  const [dateRange, setDateRange] = useState('daily');
  const [startDate, setStartDate] = useState(getTodayDate());
  const [endDate, setEndDate] = useState(getTodayDate());
  const [filterWarehouse, setFilterWarehouse] = useState('all');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (startDate && endDate) {
      fetchSales();
      fetchSummary();
    }
  }, [startDate, endDate, filterWarehouse]);

  useEffect(() => {
    const { start, end } = getDateRange(dateRange);
    setStartDate(start);
    setEndDate(end);
  }, [dateRange]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [accessoriesRes, customersRes, warehousesRes] = await Promise.all([
        getAccessories(),
        getCustomers(),
        isAdmin ? getWarehouses() : Promise.resolve({ data: [] })
      ]);
      setAccessories(accessoriesRes.data.filter(a => a.is_active));
      setCustomers(customersRes.data);
      setWarehouses(warehousesRes.data || []);
    } catch (error) {
      console.error('Failed to fetch data:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const fetchSales = async () => {
    try {
      const params = { start_date: startDate, end_date: endDate };
      if (filterWarehouse && filterWarehouse !== 'all') {
        params.warehouse_id = filterWarehouse;
      }
      const response = await getAccessorySales(params);
      // Preprocess: add flat items_text for searching accessory item names
      const processed = response.data.map(s => ({
        ...s,
        items_text: (s.items || []).map(i => i.accessory_name || '').join(', ')
      }));
      setSales(processed);
      setFilteredSales(processed);
    } catch (error) {
      console.error('Failed to fetch sales:', error);
    }
  };

  const fetchSummary = async () => {
    try {
      const params = { start_date: startDate, end_date: endDate };
      const response = await getAccessorySalesSummary(params);
      setSummary(response.data);
    } catch (error) {
      console.error('Failed to fetch summary:', error);
    }
  };

  const handleCustomerSelect = (customerId) => {
    const customer = customers.find(c => c.id === customerId);
    setSelectedCustomer(customer);
  };

  const addItem = () => {
    setSaleItems([...saleItems, { accessory_id: '', quantity: 1, unit_price: 0 }]);
  };

  const removeItem = (index) => {
    if (saleItems.length > 1) {
      setSaleItems(saleItems.filter((_, i) => i !== index));
    }
  };

  const updateItem = (index, field, value) => {
    const updated = [...saleItems];
    updated[index][field] = value;
    setSaleItems(updated);
  };

  const calculateSubtotal = () => {
    return saleItems.reduce((sum, item) => {
      return sum + (item.quantity * item.unit_price);
    }, 0);
  };

  const handleSubmit = async () => {
    // Validation
    if (customerMode === 'existing' && !selectedCustomer) {
      toast.error('Please select a customer');
      return;
    }
    if (customerMode === 'new' && !newCustomer.name) {
      toast.error('Please enter customer name');
      return;
    }
    if (saleItems.some(item => !item.accessory_id || item.quantity <= 0)) {
      toast.error('Please select accessories and enter valid quantities');
      return;
    }

    setSubmitting(true);
    try {
      const saleData = {
        customer_id: customerMode === 'existing' ? selectedCustomer?.id : '',
        customer_name: customerMode === 'existing' ? selectedCustomer?.customer_name : newCustomer.name,
        customer_phone: customerMode === 'existing' ? selectedCustomer?.phone : newCustomer.phone,
        customer_address: customerMode === 'existing' ? selectedCustomer?.address : newCustomer.address,
        is_new_customer: customerMode === 'new',
        date: saleDate,
        memo_no: memoNo,
        items: saleItems.map(item => ({
          accessory_id: item.accessory_id,
          quantity: parseInt(item.quantity),
          unit_price: parseFloat(item.unit_price)
        })),
        payment_mode: paymentMode,
        remarks: remarks,
        warehouse_id: isAdmin ? selectedWarehouse : user?.warehouse_id
      };

      await createAccessorySale(saleData);
      toast.success('Sale recorded successfully!');
      
      // Reset form
      setDialogOpen(false);
      setCustomerMode('existing');
      setSelectedCustomer(null);
      setNewCustomer({ name: '', phone: '', address: '' });
      setSaleItems([{ accessory_id: '', quantity: 1, unit_price: 0 }]);
      setPaymentMode('cash');
      setMemoNo('');
      setRemarks('');
      
      // Refresh data
      fetchSales();
      fetchSummary();
      fetchData();
    } catch (error) {
      console.error('Failed to create sale:', error);
      toast.error('Failed to record sale');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (saleId) => {
    if (!window.confirm('Are you sure you want to delete this sale?')) return;
    
    try {
      await deleteAccessorySale(saleId);
      toast.success('Sale deleted');
      fetchSales();
      fetchSummary();
    } catch (error) {
      toast.error('Failed to delete sale');
    }
  };

  const handleExportPDF = async () => {
    setExporting(true);
    try {
      const params = { start_date: startDate, end_date: endDate };
      if (filterWarehouse && filterWarehouse !== 'all') {
        params.warehouse_id = filterWarehouse;
      }
      await exportAccessorySalesPDF(params);
      toast.success('PDF downloaded');
    } catch (error) {
      toast.error('Export failed');
    } finally {
      setExporting(false);
    }
  };

  const handleExportExcel = async () => {
    setExporting(true);
    try {
      const params = { start_date: startDate, end_date: endDate };
      if (filterWarehouse && filterWarehouse !== 'all') {
        params.warehouse_id = filterWarehouse;
      }
      await exportAccessorySalesExcel(params);
      toast.success('Excel downloaded');
    } catch (error) {
      toast.error('Export failed');
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-purple-700" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
              <ShoppingBag className="w-7 h-7 text-purple-700" />
              LPG Accessories Sales
            </h1>
            <p className="text-slate-500 mt-1">Record and manage accessory sales</p>
          </div>
          <Button 
            onClick={() => setDialogOpen(true)}
            className="bg-purple-700 hover:bg-purple-800"
            data-testid="add-sale-btn"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Sale Entry
          </Button>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-600 rounded-lg">
                  <ShoppingBag className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="text-xs text-purple-600">Total Sales</p>
                  <p className="text-xl font-bold text-purple-800">{summary.total_sales || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-600 rounded-lg">
                  <DollarSign className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="text-xs text-green-600">Total Amount</p>
                  <p className="text-xl font-bold text-green-800">{formatINR(summary.total_amount || 0)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-600 rounded-lg">
                  <Package className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="text-xs text-blue-600">Items Sold</p>
                  <p className="text-xl font-bold text-blue-800">{summary.total_quantity || 0}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-orange-50 to-orange-100 border-orange-200">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-orange-600 rounded-lg">
                  <Clock className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="text-xs text-orange-600">Pending</p>
                  <p className="text-xl font-bold text-orange-800">{formatINR(summary.pending_amount || 0)}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="sales" className="w-full">
          <TabsList>
            <TabsTrigger value="sales">Sales Records</TabsTrigger>
          </TabsList>

          <TabsContent value="sales" className="mt-4 space-y-4">
            {/* Filters */}
            <Card>
              <CardContent className="p-4">
                <div className="flex flex-wrap items-end gap-4">
                  <div>
                    <Label>Period</Label>
                    <Select value={dateRange} onValueChange={setDateRange}>
                      <SelectTrigger className="w-36 mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="daily">Today</SelectItem>
                        <SelectItem value="weekly">This Week</SelectItem>
                        <SelectItem value="monthly">This Month</SelectItem>
                        <SelectItem value="custom">Custom</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {dateRange === 'custom' && (
                    <>
                      <div>
                        <Label>From</Label>
                        <Input 
                          type="date" 
                          value={startDate}
                          onChange={(e) => setStartDate(e.target.value)}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label>To</Label>
                        <Input 
                          type="date" 
                          value={endDate}
                          onChange={(e) => setEndDate(e.target.value)}
                          className="mt-1"
                        />
                      </div>
                    </>
                  )}
                  {isAdmin && (
                    <div>
                      <Label>Warehouse</Label>
                      <Select value={filterWarehouse} onValueChange={setFilterWarehouse}>
                        <SelectTrigger className="w-40 mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Warehouses</SelectItem>
                          {warehouses.map(w => (
                            <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                  <Button variant="outline" onClick={() => { fetchSales(); fetchSummary(); }}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Refresh
                  </Button>
                  <div className="flex gap-2 ml-auto">
                    <Button 
                      variant="outline" 
                      onClick={handleExportPDF}
                      disabled={exporting}
                      className="border-red-300 text-red-700 hover:bg-red-50"
                    >
                      {exporting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Download className="w-4 h-4 mr-2" />}
                      PDF
                    </Button>
                    <Button 
                      variant="outline" 
                      onClick={handleExportExcel}
                      disabled={exporting}
                      className="border-green-300 text-green-700 hover:bg-green-50"
                    >
                      {exporting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <FileSpreadsheet className="w-4 h-4 mr-2" />}
                      Excel
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Search Bar */}
            <Card className="bg-gradient-to-r from-purple-50 to-violet-50 border-purple-200">
              <CardContent className="p-4">
                <Label className="text-purple-800 font-medium mb-2 block">Quick Search</Label>
                <SearchBar
                  data={sales}
                  searchFields={['customer_name', 'customer_phone', 'memo_no', 'warehouse_name', 'items_text']}
                  onFilter={(results) => { setFilteredSales(results); }}
                  onQueryChange={setSearchQuery}
                  placeholder="Search by customer, accessory, phone, memo..."
                  showSuggestions={true}
                  maxSuggestions={1}
                  suggestionLabelField="customer_name"
                  className="max-w-2xl"
                />
              </CardContent>
            </Card>

            {/* Sales Table */}
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle>Sales Records</CardTitle>
                  <Badge variant="outline" className="text-purple-700">
                    {filteredSales.length} of {sales.length} records
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {filteredSales.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Memo No</th>
                          <th>Customer</th>
                          <th>Phone</th>
                          <th>Items</th>
                          <th>Total</th>
                          <th>Payment</th>
                          {isAdmin && <th>Warehouse</th>}
                          <th>Created By</th>
                          {isAdmin && <th>Actions</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {filteredSales.map((sale) => (
                          <tr key={sale.id}>
                            <td>{formatDate(sale.date)}</td>
                            <td className="font-medium text-purple-700">{sale.memo_no || '-'}</td>
                            <td className="font-medium">
                              <HighlightMatch text={sale.customer_name} query={searchQuery} />
                            </td>
                            <td>
                              <HighlightMatch text={sale.customer_phone || '-'} query={searchQuery} />
                            </td>
                            <td>
                              <div className="text-xs">
                                {sale.items?.map((item, i) => (
                                  <div key={i} className="text-slate-600">
                                    <HighlightMatch text={`${item.accessory_name} x${item.quantity}`} query={searchQuery} />
                                  </div>
                                ))}
                              </div>
                            </td>
                            <td className="font-semibold text-green-700">{formatINR(sale.grand_total)}</td>
                            <td>
                              <Badge variant={
                                sale.payment_mode === 'cash' ? 'default' : 
                                sale.payment_mode === 'pending' ? 'secondary' : 'outline'
                              }>
                                {sale.payment_mode === 'cash' && <Banknote className="w-3 h-3 mr-1" />}
                                {sale.payment_mode === 'pending' && <Clock className="w-3 h-3 mr-1" />}
                                {sale.payment_mode === 'online' && <CreditCard className="w-3 h-3 mr-1" />}
                                {sale.payment_mode}
                              </Badge>
                            </td>
                            {isAdmin && <td className="text-sm">{sale.warehouse_name}</td>}
                            <td className="text-sm text-slate-600">{sale.created_by_name}</td>
                            {isAdmin && (
                              <td>
                                <Button 
                                  variant="ghost" 
                                  size="sm"
                                  onClick={() => handleDelete(sale.id)}
                                  className="text-red-600 hover:text-red-800"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </Button>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <ShoppingBag className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">
                      {searchQuery ? 'No matching accessory sales found.' : 'No sales records found'}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* New Sale Dialog */}
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <ShoppingBag className="w-5 h-5 text-purple-700" />
                New Accessory Sale
              </DialogTitle>
            </DialogHeader>

            <div className="space-y-6 py-4">
              {/* Customer Selection */}
              <div className="space-y-4">
                <Label className="text-base font-semibold">Customer Information</Label>
                
                <RadioGroup 
                  value={customerMode} 
                  onValueChange={setCustomerMode}
                  className="flex gap-4"
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="existing" id="existing" />
                    <Label htmlFor="existing" className="flex items-center gap-1 cursor-pointer">
                      <Users className="w-4 h-4" />
                      Existing Customer
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="new" id="new" />
                    <Label htmlFor="new" className="flex items-center gap-1 cursor-pointer">
                      <UserPlus className="w-4 h-4" />
                      New Customer
                    </Label>
                  </div>
                </RadioGroup>

                {customerMode === 'existing' ? (
                  <div>
                    <Label>Select Customer *</Label>
                    <SearchableSelect
                      options={customers.map(c => ({
                        ...c,
                        display_name: c.customer_name || c.name,
                        display_info: `${c.phone || ''} • ${c.address || ''}`
                      }))}
                      value={selectedCustomer?.id || ''}
                      onChange={handleCustomerSelect}
                      placeholder="Type to search customer..."
                      labelField="display_name"
                      valueField="id"
                      searchFields={['display_name', 'phone', 'consumer_no', 'address']}
                      className="mt-1"
                    />
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <Label>Customer Name *</Label>
                      <Input 
                        value={newCustomer.name}
                        onChange={(e) => setNewCustomer({ ...newCustomer, name: e.target.value })}
                        placeholder="Enter name"
                        className="mt-1"
                      />
                    </div>
                    <div>
                      <Label>Phone</Label>
                      <Input 
                        value={newCustomer.phone}
                        onChange={(e) => setNewCustomer({ ...newCustomer, phone: e.target.value })}
                        placeholder="Enter phone"
                        className="mt-1"
                      />
                    </div>
                    <div>
                      <Label>Address</Label>
                      <Input 
                        value={newCustomer.address}
                        onChange={(e) => setNewCustomer({ ...newCustomer, address: e.target.value })}
                        placeholder="Enter address"
                        className="mt-1"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Sale Items */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label className="text-base font-semibold">Sale Items</Label>
                  <Button variant="outline" size="sm" onClick={addItem}>
                    <Plus className="w-4 h-4 mr-1" />
                    Add Item
                  </Button>
                </div>

                <div className="space-y-3">
                  {saleItems.map((item, index) => (
                    <div key={index} className="grid grid-cols-12 gap-3 p-3 bg-slate-50 rounded-lg items-end">
                      <div className="col-span-4">
                        <Label className="text-xs">Accessory *</Label>
                        <SearchableSelect
                          options={accessories}
                          value={item.accessory_id}
                          onChange={(val) => updateItem(index, 'accessory_id', val)}
                          placeholder="Select accessory"
                          labelField="name"
                          valueField="id"
                          searchFields={['name', 'description']}
                          className="mt-1"
                        />
                      </div>
                      <div className="col-span-2">
                        <Label className="text-xs">Quantity *</Label>
                        <Input 
                          type="number"
                          min="1"
                          value={item.quantity}
                          onChange={(e) => updateItem(index, 'quantity', parseInt(e.target.value) || 1)}
                          className="mt-1"
                        />
                      </div>
                      <div className="col-span-2">
                        <Label className="text-xs">Unit Price (Rs.)</Label>
                        <Input 
                          type="number"
                          min="0"
                          step="0.01"
                          value={item.unit_price}
                          onChange={(e) => updateItem(index, 'unit_price', parseFloat(e.target.value) || 0)}
                          className="mt-1"
                        />
                      </div>
                      <div className="col-span-3">
                        <Label className="text-xs">Total</Label>
                        <div className="mt-1 px-3 py-2 bg-green-50 rounded-md font-semibold text-green-800">
                          {formatINR(item.quantity * item.unit_price)}
                        </div>
                      </div>
                      <div className="col-span-1">
                        {saleItems.length > 1 && (
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => removeItem(index)}
                            className="text-red-600"
                          >
                            <X className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Grand Total */}
                <div className="flex justify-end">
                  <div className="bg-purple-100 px-6 py-3 rounded-lg">
                    <span className="text-purple-700 font-medium mr-3">Grand Total:</span>
                    <span className="text-2xl font-bold text-purple-800">{formatINR(calculateSubtotal())}</span>
                  </div>
                </div>
              </div>

              {/* Sale Details */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <Label>Date</Label>
                  <Input 
                    type="date"
                    value={saleDate}
                    onChange={(e) => setSaleDate(e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Memo No</Label>
                  <Input 
                    type="text"
                    value={memoNo}
                    onChange={(e) => setMemoNo(e.target.value)}
                    placeholder="Enter memo number"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Payment Mode</Label>
                  <Select value={paymentMode} onValueChange={setPaymentMode}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cash">
                        <div className="flex items-center gap-2">
                          <Banknote className="w-4 h-4" />
                          Cash
                        </div>
                      </SelectItem>
                      <SelectItem value="pending">
                        <div className="flex items-center gap-2">
                          <Clock className="w-4 h-4" />
                          Pending
                        </div>
                      </SelectItem>
                      <SelectItem value="online">
                        <div className="flex items-center gap-2">
                          <CreditCard className="w-4 h-4" />
                          Online
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {isAdmin && (
                  <div>
                    <Label>Warehouse</Label>
                    <Select value={selectedWarehouse} onValueChange={setSelectedWarehouse}>
                      <SelectTrigger className="mt-1">
                        <SelectValue placeholder="Select warehouse" />
                      </SelectTrigger>
                      <SelectContent>
                        {warehouses.map(w => (
                          <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>

              <div>
                <Label>Remarks / Notes</Label>
                <Textarea 
                  value={remarks}
                  onChange={(e) => setRemarks(e.target.value)}
                  placeholder="Any additional notes..."
                  className="mt-1"
                />
              </div>
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline">Cancel</Button>
              </DialogClose>
              <Button 
                onClick={handleSubmit}
                disabled={submitting}
                className="bg-purple-700 hover:bg-purple-800"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                Save Sale
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default AccessorySales;
