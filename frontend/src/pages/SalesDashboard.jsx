import React, { useState, useEffect, useMemo } from 'react';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { 
  getSalesEntries, 
  createSalesEntry, 
  createSalesEntryForWarehouse,
  updateSalesEntry, 
  deleteSalesEntry,
  getSalesSummary,
  exportSalesPdf,
  exportSalesExcel,
  getWarehouses,
  getCustomers,
  getFrequentCustomers
} from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  DollarSign,
  Plus,
  Edit2,
  Trash2,
  Loader2,
  FileText,
  Download,
  Search,
  Filter,
  Calendar,
  Banknote,
  CreditCard,
  Clock,
  RefreshCw,
  TrendingUp,
  Table as TableIcon,
  Home,
  Building2,
  UserPlus,
  Users,
  Zap,
  Repeat,
  Star
} from 'lucide-react';
import { formatDate, formatINR } from '../lib/utils';
import { toast } from 'sonner';

const SalesDashboard = () => {
  const { user, isAdmin } = useAuth();
  const [entries, setEntries] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [frequentCustomers, setFrequentCustomers] = useState([]);
  const [summary, setSummary] = useState({
    cash: { amount: 0, refills: 0, count: 0 },
    online: { amount: 0, refills: 0, count: 0 },
    pending: { amount: 0, refills: 0, count: 0 },
    total: { amount: 0, refills: 0, count: 0 }
  });
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState(null);
  const [customerMode, setCustomerMode] = useState('new'); // 'new' or 'existing'
  const [quickRefillDialogOpen, setQuickRefillDialogOpen] = useState(false);
  const [quickRefillCustomer, setQuickRefillCustomer] = useState(null);
  const [quickRefillForm, setQuickRefillForm] = useState({
    no_of_refills: '1',
    amount: '',
    payment_mode: 'cash',
    remarks: ''
  });

  // Filters
  const [filterWarehouse, setFilterWarehouse] = useState('all');
  const [filterPaymentMode, setFilterPaymentMode] = useState('all');
  const [filterConnectionType, setFilterConnectionType] = useState('all');
  const [filterDateRange, setFilterDateRange] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [exportConnectionType, setExportConnectionType] = useState('all');
  const [exportDateRange, setExportDateRange] = useState('all');
  const [exportStartDate, setExportStartDate] = useState('');
  const [exportEndDate, setExportEndDate] = useState('');

  // Form state
  const getTodayDate = () => new Date().toISOString().split('T')[0];
  
  const [formData, setFormData] = useState({
    date: getTodayDate(),
    customer_id: '',
    consumer_name: '',
    address: '',
    consumer_no: '',
    memo_no: '',
    amount: '',
    connection_type: 'domestic',
    cylinder_nos: '',
    payment_mode: 'cash',
    no_of_refills: '',
    remarks: '',
    warehouse_id: ''
  });

  const [editForm, setEditForm] = useState({});

  useEffect(() => {
    fetchData();
  }, [filterWarehouse, filterPaymentMode, startDate, endDate]);

  const getDateRange = (range) => {
    const today = new Date();
    let start = '';
    let end = today.toISOString().split('T')[0];

    switch(range) {
      case 'today':
        start = end;
        break;
      case 'week':
        const weekAgo = new Date(today);
        weekAgo.setDate(today.getDate() - 7);
        start = weekAgo.toISOString().split('T')[0];
        break;
      case 'month':
        const monthAgo = new Date(today);
        monthAgo.setMonth(today.getMonth() - 1);
        start = monthAgo.toISOString().split('T')[0];
        break;
      case 'year':
        const yearAgo = new Date(today);
        yearAgo.setFullYear(today.getFullYear() - 1);
        start = yearAgo.toISOString().split('T')[0];
        break;
      default:
        start = '';
        end = '';
    }
    return { start, end };
  };

  useEffect(() => {
    if (filterDateRange !== 'custom' && filterDateRange !== 'all') {
      const { start, end } = getDateRange(filterDateRange);
      setStartDate(start);
      setEndDate(end);
    } else if (filterDateRange === 'all') {
      setStartDate('');
      setEndDate('');
    }
  }, [filterDateRange]);

  const fetchData = async () => {
    try {
      const params = {};
      if (isAdmin && filterWarehouse !== 'all') {
        params.warehouse_id = filterWarehouse;
      }
      if (filterPaymentMode !== 'all') {
        params.payment_mode = filterPaymentMode;
      }
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      if (searchQuery) params.search = searchQuery;

      const [entriesRes, summaryRes, customersRes, frequentRes] = await Promise.all([
        getSalesEntries(params),
        getSalesSummary(params),
        getCustomers(),
        getFrequentCustomers(8)
      ]);
      
      setEntries(entriesRes.data);
      setSummary(summaryRes.data);
      setCustomers(customersRes.data);
      setFrequentCustomers(frequentRes.data);

      if (isAdmin && warehouses.length === 0) {
        const warehousesRes = await getWarehouses();
        setWarehouses(warehousesRes.data.filter(w => !w.is_plant));
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      toast.error('Failed to load sales data');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    fetchData();
  };

  const handleAddEntry = async () => {
    if (!formData.consumer_name || !formData.amount) {
      toast.error('Please fill in consumer name and amount');
      return;
    }

    setSubmitting(true);
    try {
      const data = {
        ...formData,
        amount: parseFloat(formData.amount) || 0,
        no_of_refills: parseInt(formData.no_of_refills) || 0
      };

      if (isAdmin) {
        if (!formData.warehouse_id) {
          toast.error('Please select a warehouse');
          setSubmitting(false);
          return;
        }
        await createSalesEntryForWarehouse(formData.warehouse_id, data);
      } else {
        await createSalesEntry(data);
      }

      toast.success('Sales entry added successfully');
      setAddDialogOpen(false);
      setCustomerMode('new');
      setFormData({
        date: getTodayDate(),
        customer_id: '',
        consumer_name: '',
        address: '',
        consumer_no: '',
        memo_no: '',
        amount: '',
        connection_type: 'domestic',
        cylinder_nos: '',
        payment_mode: 'cash',
        no_of_refills: '',
        remarks: '',
        warehouse_id: ''
      });
      fetchData();
    } catch (error) {
      console.error('Failed to add entry:', error);
      toast.error(error.response?.data?.detail || 'Failed to add entry');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditEntry = (entry) => {
    setEditingEntry(entry);
    setEditForm({
      date: entry.date,
      consumer_name: entry.consumer_name,
      address: entry.address || '',
      consumer_no: entry.consumer_no || '',
      memo_no: entry.memo_no || '',
      amount: entry.amount,
      connection_type: entry.connection_type || 'domestic',
      cylinder_nos: entry.cylinder_nos || '',
      payment_mode: entry.payment_mode,
      no_of_refills: entry.no_of_refills,
      remarks: entry.remarks || ''
    });
    setEditDialogOpen(true);
  };

  const handleUpdateEntry = async () => {
    if (!editingEntry) return;

    setSubmitting(true);
    try {
      await updateSalesEntry(editingEntry.id, {
        ...editForm,
        amount: parseFloat(editForm.amount) || 0,
        no_of_refills: parseInt(editForm.no_of_refills) || 0
      });
      toast.success('Entry updated successfully');
      setEditDialogOpen(false);
      setEditingEntry(null);
      fetchData();
    } catch (error) {
      console.error('Failed to update entry:', error);
      toast.error(error.response?.data?.detail || 'Failed to update entry');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteEntry = async (entryId) => {
    if (!window.confirm('Are you sure you want to delete this entry?')) return;

    try {
      await deleteSalesEntry(entryId);
      toast.success('Entry deleted successfully');
      fetchData();
    } catch (error) {
      console.error('Failed to delete entry:', error);
      toast.error('Failed to delete entry');
    }
  };

  const handleQuickRefill = (customer) => {
    setQuickRefillCustomer(customer);
    setQuickRefillForm({
      no_of_refills: '1',
      amount: customer.avg_amount ? String(Math.round(customer.avg_amount)) : '',
      payment_mode: 'cash',
      remarks: ''
    });
    setQuickRefillDialogOpen(true);
  };

  const handleSubmitQuickRefill = async () => {
    if (!quickRefillCustomer) return;
    
    setSubmitting(true);
    try {
      const entryData = {
        date: new Date().toISOString().split('T')[0],
        consumer_name: quickRefillCustomer.consumer_name,
        address: quickRefillCustomer.address,
        consumer_no: quickRefillCustomer.consumer_no,
        memo_no: quickRefillCustomer.memo_no || '',
        amount: parseFloat(quickRefillForm.amount) || 0,
        connection_type: quickRefillCustomer.connection_type || 'domestic_refill',
        payment_mode: quickRefillForm.payment_mode,
        no_of_refills: parseInt(quickRefillForm.no_of_refills) || 1,
        remarks: quickRefillForm.remarks
      };

      if (isAdmin && quickRefillCustomer.warehouse_id) {
        await createSalesEntryForWarehouse(quickRefillCustomer.warehouse_id, entryData);
      } else {
        await createSalesEntry(entryData);
      }

      toast.success(`Quick refill added for ${quickRefillCustomer.consumer_name}`);
      setQuickRefillDialogOpen(false);
      setQuickRefillCustomer(null);
      fetchData();
    } catch (error) {
      console.error('Failed to add quick refill:', error);
      toast.error(error.response?.data?.detail || 'Failed to add refill entry');
    } finally {
      setSubmitting(false);
    }
  };

  const getExportDateRange = () => {
    const today = new Date();
    let start = '';
    let end = today.toISOString().split('T')[0];
    
    switch(exportDateRange) {
      case 'daily':
        start = end;
        break;
      case 'weekly':
        const weekAgo = new Date(today);
        weekAgo.setDate(today.getDate() - 7);
        start = weekAgo.toISOString().split('T')[0];
        break;
      case 'monthly':
        const monthAgo = new Date(today);
        monthAgo.setMonth(today.getMonth() - 1);
        start = monthAgo.toISOString().split('T')[0];
        break;
      case 'yearly':
        const yearAgo = new Date(today);
        yearAgo.setFullYear(today.getFullYear() - 1);
        start = yearAgo.toISOString().split('T')[0];
        break;
      case 'custom':
        start = exportStartDate;
        end = exportEndDate || end;
        break;
      default:
        // 'all' - no date filter
        return { start: '', end: '' };
    }
    return { start, end };
  };

  const handleExportPdf = async (connectionType = 'all') => {
    try {
      const params = {};
      if (isAdmin && filterWarehouse !== 'all') {
        params.warehouse_id = filterWarehouse;
      }
      if (filterPaymentMode !== 'all') {
        params.payment_mode = filterPaymentMode;
      }
      
      const { start, end } = getExportDateRange();
      if (start) params.start_date = start;
      if (end) params.end_date = end;
      
      if (connectionType !== 'all') {
        params.connection_type = connectionType;
      }

      await exportSalesPdf(params);
      toast.success('PDF exported successfully');
      setExportDialogOpen(false);
    } catch (error) {
      toast.error('Failed to export PDF');
    }
  };

  const handleExportExcel = async (connectionType = 'all') => {
    try {
      const params = {};
      if (isAdmin && filterWarehouse !== 'all') {
        params.warehouse_id = filterWarehouse;
      }
      if (filterPaymentMode !== 'all') {
        params.payment_mode = filterPaymentMode;
      }
      
      const { start, end } = getExportDateRange();
      if (start) params.start_date = start;
      if (end) params.end_date = end;
      
      if (connectionType !== 'all') {
        params.connection_type = connectionType;
      }

      await exportSalesExcel(params);
      toast.success('Excel exported successfully');
      setExportDialogOpen(false);
    } catch (error) {
      toast.error('Failed to export Excel');
    }
  };

  const getPaymentBadge = (mode) => {
    switch(mode) {
      case 'cash':
        return <Badge className="bg-green-100 text-green-800"><Banknote className="w-3 h-3 mr-1" />Cash</Badge>;
      case 'online':
        return <Badge className="bg-blue-100 text-blue-800"><CreditCard className="w-3 h-3 mr-1" />Online</Badge>;
      case 'pending':
        return <Badge className="bg-amber-100 text-amber-800"><Clock className="w-3 h-3 mr-1" />Pending</Badge>;
      default:
        return <Badge variant="outline">{mode}</Badge>;
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

  const handleCustomerSelect = (customerId) => {
    const customer = customers.find(c => c.id === customerId);
    if (customer) {
      // Auto-fill customer info from bulk uploaded data
      // Keep the refill connection type since existing customers are for refills
      setFormData({
        ...formData,
        customer_id: customerId,
        consumer_name: customer.customer_name || customer.name || '',
        address: customer.address || '',
        consumer_no: customer.consumer_no || customer.phone || '',
        // Keep the current connection_type (refill type) - don't override from customer data
        memo_no: customer.cash_memo_no || '',
        remarks: customer.remarks || ''
      });
    }
  };

  // Calculate filtered totals
  const filteredTotals = useMemo(() => {
    return entries.reduce((acc, e) => ({
      amount: acc.amount + (e.amount || 0),
      refills: acc.refills + (e.no_of_refills || 0)
    }), { amount: 0, refills: 0 });
  }, [entries]);

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-green-700" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6" data-testid="sales-dashboard">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-800 flex items-center gap-2">
              <TrendingUp className="w-8 h-8 text-green-700" />
              Sales Dashboard
            </h1>
            <p className="text-slate-500 mt-1">
              {isAdmin ? 'View and manage all sales data' : `Sales data for ${user?.warehouse_name || 'your warehouse'}`}
            </p>
          </div>
          <div className="flex gap-2">
            <Dialog open={exportDialogOpen} onOpenChange={setExportDialogOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" className="gap-2" data-testid="export-btn">
                  <Download className="w-4 h-4" />
                  Export
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <Download className="w-5 h-5 text-green-700" />
                    Export Sales Data
                  </DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div>
                    <Label>Date Range</Label>
                    <Select value={exportDateRange} onValueChange={(v) => {
                      setExportDateRange(v);
                      if (v !== 'custom') {
                        setExportStartDate('');
                        setExportEndDate('');
                      }
                    }}>
                      <SelectTrigger className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4" /> All Time</div>
                        </SelectItem>
                        <SelectItem value="daily">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-blue-600" /> Daily (Today)</div>
                        </SelectItem>
                        <SelectItem value="weekly">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-green-600" /> Weekly (Last 7 days)</div>
                        </SelectItem>
                        <SelectItem value="monthly">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-purple-600" /> Monthly (Last 30 days)</div>
                        </SelectItem>
                        <SelectItem value="yearly">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-orange-600" /> Yearly (Last 365 days)</div>
                        </SelectItem>
                        <SelectItem value="custom">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-slate-600" /> Custom Range</div>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {exportDateRange === 'custom' && (
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label>Start Date</Label>
                        <Input 
                          type="date" 
                          value={exportStartDate}
                          onChange={(e) => setExportStartDate(e.target.value)}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label>End Date</Label>
                        <Input 
                          type="date" 
                          value={exportEndDate}
                          onChange={(e) => setExportEndDate(e.target.value)}
                          className="mt-1"
                        />
                      </div>
                    </div>
                  )}

                  <div>
                    <Label>Filter by Connection Type</Label>
                    <Select value={exportConnectionType} onValueChange={setExportConnectionType}>
                      <SelectTrigger className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">
                          <div className="flex items-center gap-2">All Types</div>
                        </SelectItem>
                        <SelectItem value="domestic">
                          <div className="flex items-center gap-2"><Home className="w-4 h-4 text-emerald-600" /> Domestic New Connection</div>
                        </SelectItem>
                        <SelectItem value="commercial">
                          <div className="flex items-center gap-2"><Building2 className="w-4 h-4 text-purple-600" /> Commercial New Connection</div>
                        </SelectItem>
                        <SelectItem value="domestic_refill">
                          <div className="flex items-center gap-2"><Home className="w-4 h-4 text-blue-600" /> Domestic Refill</div>
                        </SelectItem>
                        <SelectItem value="commercial_refill">
                          <div className="flex items-center gap-2"><Building2 className="w-4 h-4 text-orange-600" /> Commercial Refill</div>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <p className="text-sm text-slate-500 bg-slate-50 p-2 rounded">
                    Export filters: {exportDateRange === 'all' ? 'All Time' : exportDateRange === 'custom' ? `${exportStartDate || 'Start'} to ${exportEndDate || 'End'}` : exportDateRange.charAt(0).toUpperCase() + exportDateRange.slice(1)}
                    {exportConnectionType !== 'all' && ` · ${exportConnectionType.replace('_', ' ')}`}
                    {filterWarehouse !== 'all' && ' · Filtered Warehouse'}
                  </p>

                  <div className="grid grid-cols-2 gap-3 pt-2">
                    <Button 
                      onClick={() => handleExportPdf(exportConnectionType)} 
                      variant="outline" 
                      className="gap-2 border-red-200 hover:bg-red-50"
                      data-testid="export-pdf-btn"
                    >
                      <FileText className="w-4 h-4 text-red-600" />
                      Download PDF
                    </Button>
                    <Button 
                      onClick={() => handleExportExcel(exportConnectionType)} 
                      variant="outline" 
                      className="gap-2 border-green-200 hover:bg-green-50"
                      data-testid="export-excel-btn"
                    >
                      <Download className="w-4 h-4 text-green-600" />
                      Download Excel
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
            <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-green-700 hover:bg-green-800 gap-2" data-testid="add-entry-btn">
                  <Plus className="w-4 h-4" />
                  Add Entry
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Add Sales Entry</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  {/* Customer Selection Mode */}
                  <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 p-3 bg-slate-50 rounded-lg">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="customerMode"
                        checked={customerMode === 'new'}
                        onChange={() => {
                          setCustomerMode('new');
                          setFormData({ ...formData, customer_id: '', consumer_name: '', address: '', consumer_no: '', connection_type: 'domestic', cylinder_nos: '', no_of_refills: '' });
                        }}
                        className="w-4 h-4"
                      />
                      <span className="flex items-center gap-1 font-medium text-sm sm:text-base">
                        <UserPlus className="w-4 h-4 text-green-600" />
                        New Connection
                      </span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="customerMode"
                        checked={customerMode === 'existing'}
                        onChange={() => {
                          setCustomerMode('existing');
                          setFormData({ ...formData, connection_type: 'domestic_refill', cylinder_nos: '', no_of_refills: '' });
                        }}
                        className="w-4 h-4"
                      />
                      <span className="flex items-center gap-1 font-medium text-sm sm:text-base">
                        <Users className="w-4 h-4 text-blue-600" />
                        Existing Customer
                      </span>
                    </label>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                    <div>
                      <Label className="text-sm">Date *</Label>
                      <Input 
                        type="date"
                        value={formData.date}
                        onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                        className="mt-1"
                      />
                    </div>
                    {isAdmin && (
                      <div>
                        <Label className="text-sm">Warehouse *</Label>
                        <Select value={formData.warehouse_id} onValueChange={(v) => setFormData({ ...formData, warehouse_id: v })}>
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

                  {/* Existing Customer Selection */}
                  {customerMode === 'existing' && (
                    <div>
                      <Label>Select Customer *</Label>
                      <Select value={formData.customer_id} onValueChange={handleCustomerSelect}>
                        <SelectTrigger className="mt-1">
                          <SelectValue placeholder="Search and select customer" />
                        </SelectTrigger>
                        <SelectContent>
                          {customers.map(c => (
                            <SelectItem key={c.id} value={c.id}>
                              <div className="flex items-center gap-2">
                                <span className="font-medium">{c.customer_name || c.name}</span>
                                <Badge variant="outline" className="text-xs">{c.connection_type || c.category}</Badge>
                                {(c.phone || c.consumer_no) && <span className="text-slate-500 text-xs">({c.phone || c.consumer_no})</span>}
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Consumer Name *</Label>
                      <Input 
                        value={formData.consumer_name}
                        onChange={(e) => setFormData({ ...formData, consumer_name: e.target.value })}
                        placeholder="Enter consumer name"
                        className="mt-1"
                        disabled={customerMode === 'existing' && formData.customer_id}
                      />
                    </div>
                    <div>
                      <Label>Consumer No (10 digits)</Label>
                      <Input 
                        value={formData.consumer_no}
                        onChange={(e) => {
                          const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                          setFormData({ ...formData, consumer_no: value });
                        }}
                        placeholder="Enter 10 digit number"
                        className="mt-1"
                        maxLength={10}
                        disabled={customerMode === 'existing' && formData.customer_id}
                      />
                      {formData.consumer_no && formData.consumer_no.length !== 10 && (
                        <p className="text-xs text-red-500 mt-1">Must be 10 digits ({formData.consumer_no.length}/10)</p>
                      )}
                    </div>
                    <div className="col-span-2">
                      <Label>Address</Label>
                      <Input 
                        value={formData.address}
                        onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                        placeholder="Enter address"
                        className="mt-1"
                        disabled={customerMode === 'existing' && formData.customer_id}
                      />
                    </div>
                  </div>

                  {/* Connection Type */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Connection Type *</Label>
                      <Select 
                        value={formData.connection_type} 
                        onValueChange={(v) => setFormData({ ...formData, connection_type: v, cylinder_nos: '', no_of_refills: '' })}
                      >
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {customerMode === 'new' ? (
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
                    
                    {/* Cylinder Nos for New Connection (domestic/commercial) */}
                    {customerMode === 'new' && (
                      <div>
                        <Label>Cylinder Nos.</Label>
                        <Input 
                          value={formData.cylinder_nos}
                          onChange={(e) => setFormData({ ...formData, cylinder_nos: e.target.value })}
                          placeholder="Enter cylinder numbers"
                          className="mt-1"
                        />
                      </div>
                    )}
                    
                    {/* No of Refills for Existing Customer (refill types) */}
                    {customerMode === 'existing' && (
                      <div>
                        <Label>No of Refills *</Label>
                        <Input 
                          type="number"
                          value={formData.no_of_refills}
                          onChange={(e) => setFormData({ ...formData, no_of_refills: e.target.value })}
                          placeholder="Enter refills count"
                          className="mt-1"
                        />
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Memo No</Label>
                      <Input 
                        value={formData.memo_no}
                        onChange={(e) => setFormData({ ...formData, memo_no: e.target.value })}
                        placeholder="Enter memo number"
                        className="mt-1"
                      />
                    </div>
                    <div>
                      <Label>Amount (₹) *</Label>
                      <Input 
                        type="number"
                        value={formData.amount}
                        onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                        placeholder="Enter amount"
                        className="mt-1"
                      />
                    </div>
                    <div>
                      <Label>Mode of Payment</Label>
                      <Select value={formData.payment_mode} onValueChange={(v) => setFormData({ ...formData, payment_mode: v })}>
                        <SelectTrigger className="mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="cash">Cash</SelectItem>
                          <SelectItem value="online">Online</SelectItem>
                          <SelectItem value="pending">Pending</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Remarks</Label>
                      <Input 
                        value={formData.remarks}
                        onChange={(e) => setFormData({ ...formData, remarks: e.target.value })}
                        placeholder="Enter any remarks"
                        className="mt-1"
                      />
                    </div>
                  </div>
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setAddDialogOpen(false)}>Cancel</Button>
                  <Button onClick={handleAddEntry} disabled={submitting} className="bg-green-700 hover:bg-green-800">
                    {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Add Entry'}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-green-600 font-medium flex items-center gap-1">
                    <Banknote className="w-4 h-4" /> Cash Collection
                  </p>
                  <p className="text-2xl font-bold text-green-800">{formatINR(summary.cash.amount)}</p>
                  <p className="text-xs text-green-600">{summary.cash.count} entries · {summary.cash.refills} refills</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-blue-600 font-medium flex items-center gap-1">
                    <CreditCard className="w-4 h-4" /> Online Collection
                  </p>
                  <p className="text-2xl font-bold text-blue-800">{formatINR(summary.online.amount)}</p>
                  <p className="text-xs text-blue-600">{summary.online.count} entries · {summary.online.refills} refills</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-amber-600 font-medium flex items-center gap-1">
                    <Clock className="w-4 h-4" /> Pending Collection
                  </p>
                  <p className="text-2xl font-bold text-amber-800">{formatINR(summary.pending.amount)}</p>
                  <p className="text-xs text-amber-600">{summary.pending.count} entries · {summary.pending.refills} refills</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-purple-600 font-medium flex items-center gap-1">
                    <TrendingUp className="w-4 h-4" /> Total Collection
                  </p>
                  <p className="text-2xl font-bold text-purple-800">{formatINR(summary.total.amount)}</p>
                  <p className="text-xs text-purple-600">{summary.total.count} entries · {summary.total.refills} refills</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-wrap items-end gap-4">
              {isAdmin && (
                <div>
                  <Label className="text-xs">Warehouse</Label>
                  <Select value={filterWarehouse} onValueChange={setFilterWarehouse}>
                    <SelectTrigger className="w-44 mt-1">
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
              
              <div>
                <Label className="text-xs">Payment Mode</Label>
                <Select value={filterPaymentMode} onValueChange={setFilterPaymentMode}>
                  <SelectTrigger className="w-36 mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="cash">Cash</SelectItem>
                    <SelectItem value="online">Online</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label className="text-xs">Date Range</Label>
                <Select value={filterDateRange} onValueChange={setFilterDateRange}>
                  <SelectTrigger className="w-36 mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Time</SelectItem>
                    <SelectItem value="today">Today</SelectItem>
                    <SelectItem value="week">Last 7 Days</SelectItem>
                    <SelectItem value="month">Last 30 Days</SelectItem>
                    <SelectItem value="year">Last Year</SelectItem>
                    <SelectItem value="custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {filterDateRange === 'custom' && (
                <>
                  <div>
                    <Label className="text-xs">From</Label>
                    <Input 
                      type="date" 
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-40 mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">To</Label>
                    <Input 
                      type="date" 
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-40 mt-1"
                    />
                  </div>
                </>
              )}

              <div className="flex-1 min-w-[200px]">
                <Label className="text-xs">Search</Label>
                <div className="flex gap-2 mt-1">
                  <Input 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search consumer, memo..."
                    onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  />
                  <Button onClick={handleSearch} variant="outline" size="icon">
                    <Search className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              <Button onClick={fetchData} variant="outline" className="gap-2">
                <RefreshCw className="w-4 h-4" />
                Refresh
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Quick Refill Section */}
        {frequentCustomers.length > 0 && (
          <Card className="bg-gradient-to-r from-orange-50 to-amber-50 border-orange-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2 text-orange-800">
                <Zap className="w-5 h-5" />
                Quick Refill
                <Badge variant="outline" className="text-orange-600 border-orange-300 ml-2">
                  Top {frequentCustomers.length} Customers
                </Badge>
              </CardTitle>
              <p className="text-sm text-orange-600">One-click refill for your most frequent customers</p>
            </CardHeader>
            <CardContent className="pt-2">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {frequentCustomers.map((customer, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleQuickRefill(customer)}
                    className="group relative p-3 bg-white border border-orange-200 rounded-lg hover:border-orange-400 hover:shadow-md transition-all text-left"
                    data-testid={`quick-refill-${idx}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-slate-800 truncate">{customer.consumer_name}</p>
                        <p className="text-xs text-slate-500 truncate">{customer.address}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="outline" className="text-xs px-1.5 py-0">
                            <Repeat className="w-3 h-3 mr-1" />
                            {customer.total_refills} refills
                          </Badge>
                          {isAdmin && (
                            <span className="text-xs text-slate-400">{customer.warehouse_name}</span>
                          )}
                        </div>
                      </div>
                      <div className="ml-2 flex-shrink-0">
                        <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center group-hover:bg-orange-200 transition-colors">
                          <Plus className="w-4 h-4 text-orange-600" />
                        </div>
                      </div>
                    </div>
                    {customer.avg_amount > 0 && (
                      <p className="text-xs text-green-600 mt-1">Avg: {formatINR(Math.round(customer.avg_amount))}</p>
                    )}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Quick Refill Dialog */}
        <Dialog open={quickRefillDialogOpen} onOpenChange={setQuickRefillDialogOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Zap className="w-5 h-5 text-orange-600" />
                Quick Refill Entry
              </DialogTitle>
            </DialogHeader>
            {quickRefillCustomer && (
              <div className="space-y-4 py-4">
                <div className="p-3 bg-slate-50 rounded-lg">
                  <p className="font-semibold text-slate-800">{quickRefillCustomer.consumer_name}</p>
                  <p className="text-sm text-slate-500">{quickRefillCustomer.address}</p>
                  <p className="text-xs text-slate-400 mt-1">
                    {quickRefillCustomer.consumer_no} · {quickRefillCustomer.total_refills} previous refills
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>No of Refills *</Label>
                    <Input 
                      type="number"
                      value={quickRefillForm.no_of_refills}
                      onChange={(e) => setQuickRefillForm({ ...quickRefillForm, no_of_refills: e.target.value })}
                      placeholder="1"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label>Amount (₹) *</Label>
                    <Input 
                      type="number"
                      value={quickRefillForm.amount}
                      onChange={(e) => setQuickRefillForm({ ...quickRefillForm, amount: e.target.value })}
                      placeholder="Enter amount"
                      className="mt-1"
                    />
                  </div>
                </div>

                <div>
                  <Label>Payment Mode</Label>
                  <Select 
                    value={quickRefillForm.payment_mode} 
                    onValueChange={(v) => setQuickRefillForm({ ...quickRefillForm, payment_mode: v })}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cash">
                        <div className="flex items-center gap-2"><Banknote className="w-4 h-4 text-green-600" /> Cash</div>
                      </SelectItem>
                      <SelectItem value="online">
                        <div className="flex items-center gap-2"><CreditCard className="w-4 h-4 text-blue-600" /> Online</div>
                      </SelectItem>
                      <SelectItem value="pending">
                        <div className="flex items-center gap-2"><Clock className="w-4 h-4 text-amber-600" /> Pending</div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Remarks</Label>
                  <Input 
                    value={quickRefillForm.remarks}
                    onChange={(e) => setQuickRefillForm({ ...quickRefillForm, remarks: e.target.value })}
                    placeholder="Optional remarks"
                    className="mt-1"
                  />
                </div>

                <div className="flex gap-3 pt-2">
                  <Button 
                    variant="outline" 
                    onClick={() => setQuickRefillDialogOpen(false)}
                    className="flex-1"
                  >
                    Cancel
                  </Button>
                  <Button 
                    onClick={handleSubmitQuickRefill}
                    disabled={submitting || !quickRefillForm.amount}
                    className="flex-1 bg-orange-600 hover:bg-orange-700 gap-2"
                  >
                    {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                    Add Refill
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Sales Table */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center justify-between">
              <span className="flex items-center gap-2">
                <TableIcon className="w-5 h-5 text-green-700" />
                Sales Entries
              </span>
              <Badge variant="outline" className="text-green-700 border-green-700">
                {entries.length} entries
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>SL NO</th>
                    <th>Date</th>
                    <th>Consumer Name</th>
                    <th>Address</th>
                    <th>Consumer No</th>
                    <th>Type</th>
                    <th>Memo</th>
                    <th>Amount</th>
                    <th>Payment</th>
                    <th>Refills</th>
                    <th>Remarks</th>
                    {isAdmin && <th>Warehouse</th>}
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.length === 0 ? (
                    <tr>
                      <td colSpan={isAdmin ? 13 : 12} className="text-center py-8 text-slate-500">
                        No sales entries found
                      </td>
                    </tr>
                  ) : (
                    <>
                      {entries.map((entry, index) => (
                        <tr key={entry.id}>
                          <td className="text-center font-medium">{index + 1}</td>
                          <td>{entry.date}</td>
                          <td className="font-medium">{entry.consumer_name}</td>
                          <td className="max-w-[150px] truncate">{entry.address || '-'}</td>
                          <td>{entry.consumer_no || '-'}</td>
                          <td>
                            {getConnectionTypeBadge(entry.connection_type)}
                            {entry.cylinder_nos && (
                              <div className="text-xs text-slate-500 mt-1">
                                <span className="font-medium">Cyl:</span> {entry.cylinder_nos}
                              </div>
                            )}
                          </td>
                          <td>{entry.memo_no || '-'}</td>
                          <td className="font-semibold text-green-700">{formatINR(entry.amount)}</td>
                          <td>{getPaymentBadge(entry.payment_mode)}</td>
                          <td className="text-center">{entry.no_of_refills || 0}</td>
                          <td className="max-w-[120px] truncate">{entry.remarks || '-'}</td>
                          {isAdmin && <td><Badge variant="outline">{entry.warehouse_name}</Badge></td>}
                          <td>
                            <div className="flex items-center gap-1">
                              <Button 
                                variant="ghost" 
                                size="icon"
                                onClick={() => handleEditEntry(entry)}
                                title="Edit"
                              >
                                <Edit2 className="w-4 h-4 text-blue-600" />
                              </Button>
                              <Button 
                                variant="ghost" 
                                size="icon"
                                onClick={() => handleDeleteEntry(entry.id)}
                                title="Delete"
                              >
                                <Trash2 className="w-4 h-4 text-red-500" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                      {/* Total Row */}
                      <tr className="bg-green-50 font-bold">
                        <td colSpan={7} className="text-right">TOTAL:</td>
                        <td className="text-green-800">{formatINR(filteredTotals.amount)}</td>
                        <td></td>
                        <td className="text-center">{filteredTotals.refills}</td>
                        <td colSpan={isAdmin ? 3 : 2}></td>
                      </tr>
                    </>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Edit Dialog */}
        <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Edit Sales Entry</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Date</Label>
                  <Input 
                    type="date"
                    value={editForm.date || ''}
                    onChange={(e) => setEditForm({ ...editForm, date: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Consumer Name</Label>
                  <Input 
                    value={editForm.consumer_name || ''}
                    onChange={(e) => setEditForm({ ...editForm, consumer_name: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Consumer No</Label>
                  <Input 
                    value={editForm.consumer_no || ''}
                    onChange={(e) => setEditForm({ ...editForm, consumer_no: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Address</Label>
                  <Input 
                    value={editForm.address || ''}
                    onChange={(e) => setEditForm({ ...editForm, address: e.target.value })}
                    className="mt-1"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
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
                <div>
                  <Label>No of Refills</Label>
                  <Input 
                    type="number"
                    value={editForm.no_of_refills || ''}
                    onChange={(e) => setEditForm({ ...editForm, no_of_refills: e.target.value })}
                    className="mt-1"
                  />
                </div>
              </div>

              {/* Cylinder Nos for refill types */}
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

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Memo No</Label>
                  <Input 
                    value={editForm.memo_no || ''}
                    onChange={(e) => setEditForm({ ...editForm, memo_no: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Amount (₹)</Label>
                  <Input 
                    type="number"
                    value={editForm.amount || ''}
                    onChange={(e) => setEditForm({ ...editForm, amount: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label>Mode of Payment</Label>
                  <Select value={editForm.payment_mode || 'cash'} onValueChange={(v) => setEditForm({ ...editForm, payment_mode: v })}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cash">Cash</SelectItem>
                      <SelectItem value="online">Online</SelectItem>
                      <SelectItem value="pending">Pending</SelectItem>
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
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setEditDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleUpdateEntry} disabled={submitting} className="bg-green-700 hover:bg-green-800">
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Update Entry'}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default SalesDashboard;
