import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
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
  exportSalesSummaryPdf,
  exportSalesSummaryExcel,
  exportAccessorySalesPDF,
  exportAccessorySalesExcel,
  getWarehouses,
  getCustomers,
  getFrequentCustomers,
  getAccessorySales,
  getAccessorySalesSummary
} from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import SearchBar from '../components/SearchBar';
import SearchableSelect from '../components/SearchableSelect';
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
  Star,
  BarChart3,
  ShoppingBag,
  Package
} from 'lucide-react';
import { formatDate, formatINR } from '../lib/utils';
import { toast } from 'sonner';
import useKeyboardShortcuts from '../hooks/useKeyboardShortcuts';
import ShortcutHelpModal from '../components/ShortcutHelpModal';
import ShortcutBar from '../components/ShortcutBar';

const SalesDashboard = () => {
  const { user, isAdmin } = useAuth();
  const [shortcutHelpOpen, setShortcutHelpOpen] = useState(false);
  const [entries, setEntries] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [frequentCustomers, setFrequentCustomers] = useState([]);
  const [summary, setSummary] = useState({
    cash: { amount: 0, refills: 0, count: 0, cylinders: 0, new_connections: 0 },
    online: { amount: 0, refills: 0, count: 0, cylinders: 0, new_connections: 0 },
    pending: { amount: 0, refills: 0, count: 0, cylinders: 0, new_connections: 0 },
    total: { amount: 0, refills: 0, count: 0, cylinders: 0, new_connections: 0 }
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
    cash_amount: '',
    online_amount: '',
    credit_amount: '',
    remarks: ''
  });
  
  // Accessory Sales State
  const [accessorySales, setAccessorySales] = useState([]);
  const [accessorySummary, setAccessorySummary] = useState({
    total_sales: 0,
    total_amount: 0,
    cash_amount: 0,
    pending_amount: 0,
    online_amount: 0
  });

  // Compute current month start/end for default initialization
  const toLocalDateStr = (d) => {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const getThisMonthRange = () => {
    const today = new Date();
    const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    return {
      start: toLocalDateStr(startOfMonth),
      end: toLocalDateStr(today)
    };
  };

  // Filters — initialize with current month dates
  const [filterWarehouse, setFilterWarehouse] = useState('all');
  const [filterPaymentMode, setFilterPaymentMode] = useState('all');
  const [filterConnectionType, setFilterConnectionType] = useState('all');
  const [filterDateRange, setFilterDateRange] = useState('this_month');
  const [startDate, setStartDate] = useState(() => getThisMonthRange().start);
  const [endDate, setEndDate] = useState(() => getThisMonthRange().end);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalEntries, setTotalEntries] = useState(0);
  const pageSize = 50;
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [exportConnectionType, setExportConnectionType] = useState('all');
  const [exportDateRange, setExportDateRange] = useState('all');
  const [exportStartDate, setExportStartDate] = useState('');
  const [exportEndDate, setExportEndDate] = useState('');

  // Sync export connection type with dashboard filter when dialog opens
  useEffect(() => {
    if (exportDialogOpen) {
      setExportConnectionType(filterConnectionType);
    }
  }, [exportDialogOpen, filterConnectionType]);
  const [summaryExportOpen, setSummaryExportOpen] = useState(false);
  const [summaryGroupBy, setSummaryGroupBy] = useState('daily');
  const [summaryDateRange, setSummaryDateRange] = useState('all');
  const [summaryStartDate, setSummaryStartDate] = useState('');
  const [summaryEndDate, setSummaryEndDate] = useState('');

  // Form state
  const getTodayDate = () => toLocalDateStr(new Date());
  
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
    cash_amount: '',
    online_amount: '',
    credit_amount: '',
    no_of_refills: '',
    remarks: '',
    warehouse_id: ''
  });

  const [editForm, setEditForm] = useState({});

  // Helper: format date for display
  const formatDateDisplay = (dateStr) => {
    if (!dateStr) return '';
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  };

  const getActiveRangeLabel = () => {
    if (filterDateRange === 'custom' && startDate && endDate) {
      return `Custom: ${formatDateDisplay(startDate)} – ${formatDateDisplay(endDate)}`;
    }
    if (filterDateRange === 'custom') return 'Custom Range';
    const labels = {
      this_month: 'Current Month',
      last_month: 'Last Month',
      today: 'Today',
      week: 'Last 7 Days',
      year: 'This Year',
      all: 'All Time'
    };
    const label = labels[filterDateRange] || filterDateRange;
    if (startDate && endDate) {
      return `${label}: ${formatDateDisplay(startDate)} – ${formatDateDisplay(endDate)}`;
    }
    return label;
  };

  useEffect(() => {
    setCurrentPage(1);
  }, [filterWarehouse, filterPaymentMode, filterConnectionType, startDate, endDate, debouncedSearch]);

  useEffect(() => {
    fetchData();
  }, [filterWarehouse, filterPaymentMode, filterConnectionType, startDate, endDate, debouncedSearch, currentPage]);

  // Debounce search input - waits 400ms after user stops typing
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 400);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const getDateRange = (range) => {
    const today = new Date();
    let start = '';
    let end = toLocalDateStr(today);

    switch(range) {
      case 'today':
        start = end;
        break;
      case 'week':
        const weekAgo = new Date(today);
        weekAgo.setDate(today.getDate() - 7);
        start = toLocalDateStr(weekAgo);
        break;
      case 'this_month': {
        const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
        start = toLocalDateStr(startOfMonth);
        break;
      }
      case 'last_month': {
        const lastMonthStart = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        const lastMonthEnd = new Date(today.getFullYear(), today.getMonth(), 0);
        start = toLocalDateStr(lastMonthStart);
        end = toLocalDateStr(lastMonthEnd);
        break;
      }
      case 'month':
        const monthAgo = new Date(today);
        monthAgo.setMonth(today.getMonth() - 1);
        start = toLocalDateStr(monthAgo);
        break;
      case 'year':
        const yearAgo = new Date(today);
        yearAgo.setFullYear(today.getFullYear() - 1);
        start = toLocalDateStr(yearAgo);
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
      if (searchQuery) params.search = searchQuery.trim();
      if (filterConnectionType !== 'all' && filterConnectionType !== 'accessory') {
        params.connection_type = filterConnectionType;
      }
      params.page = currentPage;
      params.limit = pageSize;

      const [entriesRes, summaryRes, customersRes, frequentRes, accSalesRes, accSummaryRes] = await Promise.all([
        getSalesEntries(params),
        getSalesSummary(params),
        getCustomers({ limit: 10000, page: 1 }),
        getFrequentCustomers(8),
        getAccessorySales({ start_date: startDate, end_date: endDate, warehouse_id: isAdmin && filterWarehouse !== 'all' ? filterWarehouse : undefined }),
        getAccessorySalesSummary({ start_date: startDate, end_date: endDate, warehouse_id: isAdmin && filterWarehouse !== 'all' ? filterWarehouse : undefined })
      ]);
      
      const entriesData = entriesRes.data.entries || entriesRes.data;
      setEntries(entriesData);
      setTotalPages(entriesRes.data.pages || 1);
      setTotalEntries(entriesRes.data.total || entriesData.length);
      setSummary(summaryRes.data);
      setCustomers(customersRes.data.customers || customersRes.data);
      setFrequentCustomers(frequentRes.data);
      setAccessorySales(accSalesRes.data || []);
      setAccessorySummary(accSummaryRes.data || { total_sales: 0, total_amount: 0, cash_amount: 0, pending_amount: 0, online_amount: 0 });

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
        no_of_refills: parseInt(formData.no_of_refills) || 0,
        cash_amount: parseFloat(formData.cash_amount) || 0,
        online_amount: parseFloat(formData.online_amount) || 0,
        credit_amount: parseFloat(formData.credit_amount) || 0
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
        cash_amount: '',
        online_amount: '',
        credit_amount: '',
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
      cash_amount: entry.cash_amount || 0,
      online_amount: entry.online_amount || 0,
      credit_amount: entry.credit_amount || 0,
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
        no_of_refills: parseInt(editForm.no_of_refills) || 0,
        cash_amount: parseFloat(editForm.cash_amount) || 0,
        online_amount: parseFloat(editForm.online_amount) || 0,
        credit_amount: parseFloat(editForm.credit_amount) || 0
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
        date: toLocalDateStr(new Date()),
        consumer_name: quickRefillCustomer.consumer_name,
        address: quickRefillCustomer.address,
        consumer_no: quickRefillCustomer.consumer_no,
        memo_no: quickRefillCustomer.memo_no || '',
        amount: parseFloat(quickRefillForm.amount) || 0,
        connection_type: quickRefillCustomer.connection_type || 'domestic_refill',
        payment_mode: quickRefillForm.payment_mode,
        cash_amount: parseFloat(quickRefillForm.cash_amount) || 0,
        online_amount: parseFloat(quickRefillForm.online_amount) || 0,
        credit_amount: parseFloat(quickRefillForm.credit_amount) || 0,
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
    let end = toLocalDateStr(today);
    
    switch(exportDateRange) {
      case 'daily':
        start = end;
        break;
      case 'weekly':
        const weekAgo = new Date(today);
        weekAgo.setDate(today.getDate() - 7);
        start = toLocalDateStr(weekAgo);
        break;
      case 'this_month': {
        const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
        start = toLocalDateStr(startOfMonth);
        break;
      }
      case 'last_month': {
        const lastMonthStart = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        const lastMonthEnd = new Date(today.getFullYear(), today.getMonth(), 0);
        start = toLocalDateStr(lastMonthStart);
        end = toLocalDateStr(lastMonthEnd);
        break;
      }
      case 'monthly':
        const monthAgo = new Date(today);
        monthAgo.setMonth(today.getMonth() - 1);
        start = toLocalDateStr(monthAgo);
        break;
      case 'yearly':
        const yearAgo = new Date(today);
        yearAgo.setFullYear(today.getFullYear() - 1);
        start = toLocalDateStr(yearAgo);
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
      
      if (connectionType === 'accessory') {
        await exportAccessorySalesPDF(params);
      } else {
        if (connectionType !== 'all') {
          params.connection_type = connectionType;
        }
        await exportSalesPdf(params);
      }
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
      
      if (connectionType === 'accessory') {
        await exportAccessorySalesExcel(params);
      } else {
        if (connectionType !== 'all') {
          params.connection_type = connectionType;
        }
        await exportSalesExcel(params);
      }
      toast.success('Excel exported successfully');
      setExportDialogOpen(false);
    } catch (error) {
      toast.error('Failed to export Excel');
    }
  };

  // Summary Export Functions
  const getSummaryDateRange = () => {
    const today = new Date();
    let start = '';
    let end = toLocalDateStr(today);
    
    switch(summaryDateRange) {
      case 'daily':
        start = end;
        break;
      case 'weekly':
        const weekAgo = new Date(today);
        weekAgo.setDate(today.getDate() - 7);
        start = toLocalDateStr(weekAgo);
        break;
      case 'this_month': {
        const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
        start = toLocalDateStr(startOfMonth);
        break;
      }
      case 'last_month': {
        const lastMonthStart = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        const lastMonthEnd = new Date(today.getFullYear(), today.getMonth(), 0);
        start = toLocalDateStr(lastMonthStart);
        end = toLocalDateStr(lastMonthEnd);
        break;
      }
      case 'monthly':
        const monthAgo = new Date(today);
        monthAgo.setDate(today.getDate() - 30);
        start = toLocalDateStr(monthAgo);
        break;
      case 'yearly':
        const yearAgo = new Date(today);
        yearAgo.setFullYear(today.getFullYear() - 1);
        start = toLocalDateStr(yearAgo);
        break;
      case 'custom':
        start = summaryStartDate;
        end = summaryEndDate || end;
        break;
      default:
        start = '';
        end = '';
    }
    return { start, end };
  };

  const handleSummaryExportPdf = async () => {
    try {
      const params = {};
      
      if (user?.role === 'admin' && filterWarehouse !== 'all') {
        params.warehouse_id = filterWarehouse;
      }
      
      const { start, end } = getSummaryDateRange();
      if (start) params.start_date = start;
      if (end) params.end_date = end;
      params.group_by = summaryGroupBy;

      await exportSalesSummaryPdf(params);
      toast.success('Summary PDF exported successfully');
      setSummaryExportOpen(false);
    } catch (error) {
      toast.error('Failed to export Summary PDF');
    }
  };

  const handleSummaryExportExcel = async () => {
    try {
      const params = {};
      
      if (user?.role === 'admin' && filterWarehouse !== 'all') {
        params.warehouse_id = filterWarehouse;
      }
      
      const { start, end } = getSummaryDateRange();
      if (start) params.start_date = start;
      if (end) params.end_date = end;
      params.group_by = summaryGroupBy;

      await exportSalesSummaryExcel(params);
      toast.success('Summary Excel exported successfully');
      setSummaryExportOpen(false);
    } catch (error) {
      toast.error('Failed to export Summary Excel');
    }
  };

  const getPaymentBadge = (mode, entry) => {
    if (mode === 'split' && entry) {
      const parts = [];
      if (entry.cash_amount > 0) parts.push(`C:₹${entry.cash_amount}`);
      if (entry.online_amount > 0) parts.push(`O:₹${entry.online_amount}`);
      if (entry.credit_amount > 0) parts.push(`P:₹${entry.credit_amount}`);
      return <Badge className="bg-purple-100 text-purple-800 text-[10px]">{parts.join(' + ')}</Badge>;
    }
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
      case 'accessory':
        return <Badge className="bg-orange-100 text-orange-800"><ShoppingBag className="w-3 h-3 mr-1" />Accessory</Badge>;
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

  // Calculate filtered totals - separate new connection cyl and refill cyl
  const filteredTotals = useMemo(() => {
    return entries.reduce((acc, e) => {
      const isRefill = (e.connection_type || '').includes('refill');
      const refillCyl = isRefill ? (e.no_of_refills || 0) : 0;
      let newCyl = 0;
      if (!isRefill) {
        const cn = parseInt(e.cylinder_nos);
        if (cn > 0) { newCyl = cn; }
        else {
          const nr = parseInt(e.no_of_refills);
          newCyl = (nr > 0) ? nr : 1;
        }
      }
      return {
        amount: acc.amount + (e.amount || 0),
        refills: acc.refills + refillCyl,
        newCyl: acc.newCyl + newCyl
      };
    }, { amount: 0, refills: 0, newCyl: 0 });
  }, [entries]);

  // Combined entries: merge cylinder + accessory sales for unified table
  const combinedEntries = useMemo(() => {
    // When 'accessory' filter is active, only show accessory entries
    if (filterConnectionType === 'accessory') {
      let filteredAccSales = accessorySales;
      if (debouncedSearch) {
        const q = debouncedSearch.toLowerCase().trim();
        filteredAccSales = accessorySales.filter(s => 
          (s.customer_name || '').toLowerCase().includes(q) ||
          (s.customer_phone || '').toLowerCase().includes(q) ||
          (s.customer_address || '').toLowerCase().includes(q) ||
          (s.memo_no || '').toLowerCase().includes(q) ||
          (s.items || []).some(i => (i.accessory_name || '').toLowerCase().includes(q))
        );
      }
      return filteredAccSales.map(s => ({
        ...s,
        sale_type: 'accessory',
        consumer_name: s.customer_name,
        consumer_no: s.customer_phone,
        address: s.customer_address,
        connection_type: 'accessory',
        amount: s.grand_total,
      })).sort((a, b) => (a.date || '').localeCompare(b.date || ''));
    }
    
    const cylinderRows = entries.map(e => ({ ...e, sale_type: 'cylinder' }));
    
    // Filter accessory sales client-side when search is active
    let filteredAccSales = accessorySales;
    if (debouncedSearch) {
      const q = debouncedSearch.toLowerCase().trim();
      filteredAccSales = accessorySales.filter(s => 
        (s.customer_name || '').toLowerCase().includes(q) ||
        (s.customer_phone || '').toLowerCase().includes(q) ||
        (s.customer_address || '').toLowerCase().includes(q) ||
        (s.memo_no || '').toLowerCase().includes(q) ||
        (s.items || []).some(i => (i.accessory_name || '').toLowerCase().includes(q))
      );
    }
    
    const accessoryRows = filteredAccSales.map(s => ({
      id: s.id,
      date: s.date,
      consumer_name: s.customer_name || '',
      address: s.customer_address || '',
      consumer_no: s.customer_phone || '',
      connection_type: 'accessory',
      memo_no: s.memo_no || '',
      amount: s.grand_total || 0,
      payment_mode: s.payment_mode || '',
      no_of_refills: 0,
      cylinder_nos: '',
      remarks: (s.items || []).map(i => `${i.accessory_name} x${i.quantity}`).join(', '),
      warehouse_name: s.warehouse_name || '',
      sale_type: 'accessory'
    }));
    // Sort combined by date descending
    return [...cylinderRows, ...accessoryRows].sort((a, b) => (a.date || '').localeCompare(b.date || ''));
  }, [entries, accessorySales, debouncedSearch, filterConnectionType]);

  const combinedTotals = useMemo(() => {
    return combinedEntries.reduce((acc, e) => {
      const isRefill = (e.connection_type || '').includes('refill');
      const refillCyl = isRefill ? (e.no_of_refills || 0) : 0;
      let newCyl = 0;
      if (!isRefill && e.sale_type !== 'accessory') {
        const cn = parseInt(e.cylinder_nos);
        if (cn > 0) { newCyl = cn; }
        else {
          const nr = parseInt(e.no_of_refills);
          newCyl = (nr > 0) ? nr : 1;
        }
      }
      return {
        amount: acc.amount + (e.amount || 0),
        refills: acc.refills + refillCyl,
        newCyl: acc.newCyl + newCyl
      };
    }, { amount: 0, refills: 0, newCyl: 0 });
  }, [combinedEntries]);

  // Keyboard Shortcuts
  useKeyboardShortcuts({
    onNewConnection: () => { setCustomerMode('new'); setAddDialogOpen(true); },
    onExistingCustomer: () => { setCustomerMode('existing'); setAddDialogOpen(true); },
    onExport: () => setExportDialogOpen(true),
    onSummary: () => setSummaryExportOpen(true),
    onNextPage: () => setCurrentPage(p => Math.min(p + 1, totalPages)),
    onPrevPage: () => setCurrentPage(p => Math.max(p - 1, 1)),
    onFirstPage: () => setCurrentPage(1),
    onLastPage: () => setCurrentPage(totalPages),
    onRefresh: fetchData,
    onHelp: () => setShortcutHelpOpen(true),
    onEscape: () => setShortcutHelpOpen(false),
  }, { enabled: true, userRole: user?.role || 'admin' });

  const shortcutBarItems = [
    { key: 'F1', label: 'New' },
    { key: 'F2', label: 'Existing' },
    { key: 'Ctrl+S', label: 'Save' },
    { key: 'F10', label: 'Export' },
    { key: 'F11', label: 'Summary' },
    { key: 'Alt+→', label: 'Next Pg' },
    { key: 'Alt+←', label: 'Prev Pg' },
  ];

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
      <div className="space-y-6 pb-10" data-testid="sales-dashboard">
        {/* Shortcut Help Modal */}
        <ShortcutHelpModal open={shortcutHelpOpen} onOpenChange={setShortcutHelpOpen} />
        {/* Floating Shortcut Bar */}
        <ShortcutBar shortcuts={shortcutBarItems} onHelpOpen={() => setShortcutHelpOpen(true)} />
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
                        <SelectItem value="this_month">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-blue-600" /> This Month</div>
                        </SelectItem>
                        <SelectItem value="last_month">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-indigo-600" /> Last Month</div>
                        </SelectItem>
                        <SelectItem value="all">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4" /> All Time</div>
                        </SelectItem>
                        <SelectItem value="daily">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-green-600" /> Today</div>
                        </SelectItem>
                        <SelectItem value="weekly">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-purple-600" /> Last 7 Days</div>
                        </SelectItem>
                        <SelectItem value="yearly">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-orange-600" /> This Year</div>
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
                        <SelectItem value="accessory">
                          <div className="flex items-center gap-2"><ShoppingBag className="w-4 h-4 text-violet-600" /> Accessory Sales</div>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <p className="text-sm text-slate-500 bg-slate-50 p-2 rounded">
                    Export filters: {exportDateRange === 'all' ? 'All Time' : exportDateRange === 'custom' ? `${exportStartDate || 'Start'} to ${exportEndDate || 'End'}` : exportDateRange.charAt(0).toUpperCase() + exportDateRange.slice(1)}
                    {exportConnectionType !== 'all' && ` · ${exportConnectionType === 'accessory' ? 'Accessory Sales' : exportConnectionType.replace('_', ' ')}`}
                    {filterWarehouse !== 'all' && ' · Filtered Warehouse'}
                    {exportConnectionType === 'accessory' && <span className="block text-xs text-violet-600 mt-1">Only accessory sales will be exported with item-level details.</span>}
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
            
            {/* Summary Report Dialog */}
            <Dialog open={summaryExportOpen} onOpenChange={setSummaryExportOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" className="gap-2 border-purple-200 hover:bg-purple-50" data-testid="summary-export-btn">
                  <BarChart3 className="w-4 h-4 text-purple-600" />
                  Summary Report
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <BarChart3 className="w-5 h-5 text-purple-600" />
                    Export Sales Summary
                  </DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <p className="text-sm text-slate-600 bg-purple-50 p-3 rounded-lg">
                    Generate period-based summary reports with totals by day, week, or month. Includes breakdowns by payment mode and connection type.
                  </p>
                  
                  <div>
                    <Label>Group By Period</Label>
                    <Select value={summaryGroupBy} onValueChange={setSummaryGroupBy}>
                      <SelectTrigger className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="daily">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-blue-600" /> Daily Totals</div>
                        </SelectItem>
                        <SelectItem value="weekly">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-green-600" /> Weekly Totals</div>
                        </SelectItem>
                        <SelectItem value="monthly">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-purple-600" /> Monthly Totals</div>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div>
                    <Label>Date Range</Label>
                    <Select value={summaryDateRange} onValueChange={(v) => {
                      setSummaryDateRange(v);
                      if (v !== 'custom') {
                        setSummaryStartDate('');
                        setSummaryEndDate('');
                      }
                    }}>
                      <SelectTrigger className="mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="this_month">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-blue-600" /> This Month</div>
                        </SelectItem>
                        <SelectItem value="last_month">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-indigo-600" /> Last Month</div>
                        </SelectItem>
                        <SelectItem value="all">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4" /> All Time</div>
                        </SelectItem>
                        <SelectItem value="weekly">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-green-600" /> Last 7 Days</div>
                        </SelectItem>
                        <SelectItem value="yearly">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-orange-600" /> This Year</div>
                        </SelectItem>
                        <SelectItem value="custom">
                          <div className="flex items-center gap-2"><Calendar className="w-4 h-4 text-slate-600" /> Custom Range</div>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {summaryDateRange === 'custom' && (
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label>Start Date</Label>
                        <Input 
                          type="date" 
                          value={summaryStartDate}
                          onChange={(e) => setSummaryStartDate(e.target.value)}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label>End Date</Label>
                        <Input 
                          type="date" 
                          value={summaryEndDate}
                          onChange={(e) => setSummaryEndDate(e.target.value)}
                          className="mt-1"
                        />
                      </div>
                    </div>
                  )}
                  
                  <div className="text-sm text-slate-500 bg-slate-50 p-2 rounded">
                    Summary: {summaryGroupBy.charAt(0).toUpperCase() + summaryGroupBy.slice(1)} totals
                    {summaryDateRange !== 'all' && ` · ${summaryDateRange === 'custom' ? `${summaryStartDate || 'Start'} to ${summaryEndDate || 'End'}` : summaryDateRange}`}
                    {filterWarehouse !== 'all' && ' · Filtered Warehouse'}
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-2">
                    <Button 
                      onClick={handleSummaryExportPdf} 
                      variant="outline" 
                      className="gap-2 border-red-200 hover:bg-red-50"
                      data-testid="summary-pdf-btn"
                    >
                      <FileText className="w-4 h-4 text-red-600" />
                      Download PDF
                    </Button>
                    <Button 
                      onClick={handleSummaryExportExcel} 
                      variant="outline" 
                      className="gap-2 border-green-200 hover:bg-green-50"
                      data-testid="summary-excel-btn"
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
                      <Label className="text-sm">Select Customer *</Label>
                      <SearchableSelect
                        options={customers.map(c => ({
                          ...c,
                          display_name: c.customer_name || c.name,
                          display_info: `${c.connection_type || c.category} • ${c.phone || c.consumer_no || ''}`
                        }))}
                        value={formData.customer_id}
                        onChange={handleCustomerSelect}
                        placeholder="Type to search customer..."
                        labelField="display_name"
                        valueField="id"
                        searchFields={['display_name', 'phone', 'consumer_no', 'address']}
                        className="mt-1"
                        emptyMessage="No customers found"
                      />
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                    <div>
                      <Label className="text-sm">Consumer Name *</Label>
                      <Input 
                        value={formData.consumer_name}
                        onChange={(e) => setFormData({ ...formData, consumer_name: e.target.value })}
                        placeholder="Enter consumer name"
                        className="mt-1"
                        disabled={customerMode === 'existing' && formData.customer_id}
                      />
                    </div>
                    <div>
                      <Label className="text-sm">Consumer No (10 digits)</Label>
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
                    <div className="sm:col-span-2">
                      <Label className="text-sm">Address</Label>
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
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                    <div>
                      <Label className="text-sm">Connection Type *</Label>
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
                    
                    {/* No. of Cylinders for New Connection (domestic/commercial) */}
                    {customerMode === 'new' && (
                      <div>
                        <Label>No. of Cylinders *</Label>
                        <Input 
                          type="number"
                          min="1"
                          value={formData.cylinder_nos}
                          onChange={(e) => setFormData({ ...formData, cylinder_nos: e.target.value })}
                          placeholder="Enter no. of cylinders"
                          className="mt-1"
                          data-testid="new-conn-cylinder-count"
                        />
                      </div>
                    )}
                    
                    {/* No. of Cylinders Refilled for Existing Customer (refill types) */}
                    {customerMode === 'existing' && (
                      <div>
                        <Label className="text-sm">No. of Cylinders Refilled *</Label>
                        <Input 
                          type="number"
                          value={formData.no_of_refills}
                          onChange={(e) => setFormData({ ...formData, no_of_refills: e.target.value })}
                          placeholder="No. of cylinders to refill"
                          className="mt-1"
                        />
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                    <div>
                      <Label className="text-sm">Memo No</Label>
                      <Input 
                        value={formData.memo_no}
                        onChange={(e) => setFormData({ ...formData, memo_no: e.target.value })}
                        placeholder="Enter memo number"
                        className="mt-1"
                      />
                    </div>
                    <div>
                      <Label className="text-sm">Remarks</Label>
                      <Input 
                        value={formData.remarks}
                        onChange={(e) => setFormData({ ...formData, remarks: e.target.value })}
                        placeholder="Enter any remarks"
                        className="mt-1"
                      />
                    </div>
                  </div>

                  {/* Multi-Payment Mode Section */}
                  <div className="border rounded-lg p-3 bg-slate-50/80 space-y-3" data-testid="payment-section">
                    <Label className="text-sm font-semibold text-slate-700">Payment Breakdown</Label>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div>
                        <Label className="text-xs text-green-700">Cash (₹)</Label>
                        <Input 
                          type="number" min="0"
                          value={formData.cash_amount}
                          onChange={(e) => {
                            const val = e.target.value;
                            const cash = parseFloat(val) || 0;
                            const online = parseFloat(formData.online_amount) || 0;
                            const credit = parseFloat(formData.credit_amount) || 0;
                            setFormData({ ...formData, cash_amount: val, amount: (cash + online + credit).toString() });
                          }}
                          placeholder="0"
                          className="mt-1 border-green-200 focus:border-green-400"
                          data-testid="cash-amount-input"
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-blue-700">Online / UPI (₹)</Label>
                        <Input 
                          type="number" min="0"
                          value={formData.online_amount}
                          onChange={(e) => {
                            const val = e.target.value;
                            const cash = parseFloat(formData.cash_amount) || 0;
                            const online = parseFloat(val) || 0;
                            const credit = parseFloat(formData.credit_amount) || 0;
                            setFormData({ ...formData, online_amount: val, amount: (cash + online + credit).toString() });
                          }}
                          placeholder="0"
                          className="mt-1 border-blue-200 focus:border-blue-400"
                          data-testid="online-amount-input"
                        />
                      </div>
                      <div>
                        <Label className="text-xs text-amber-700">Credit / Pending (₹)</Label>
                        <Input 
                          type="number" min="0"
                          value={formData.credit_amount}
                          onChange={(e) => {
                            const val = e.target.value;
                            const cash = parseFloat(formData.cash_amount) || 0;
                            const online = parseFloat(formData.online_amount) || 0;
                            const credit = parseFloat(val) || 0;
                            setFormData({ ...formData, credit_amount: val, amount: (cash + online + credit).toString() });
                          }}
                          placeholder="0"
                          className="mt-1 border-amber-200 focus:border-amber-400"
                          data-testid="credit-amount-input"
                        />
                      </div>
                    </div>
                    <div className="flex items-center justify-between text-sm bg-white rounded px-3 py-1.5 border">
                      <span className="text-slate-500">Total Amount:</span>
                      <span className="font-bold text-slate-800" data-testid="total-amount-display">
                        ₹{((parseFloat(formData.cash_amount) || 0) + (parseFloat(formData.online_amount) || 0) + (parseFloat(formData.credit_amount) || 0)).toLocaleString('en-IN')}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 pt-2">
                  <Button variant="outline" onClick={() => setAddDialogOpen(false)} className="w-full sm:w-auto">Cancel</Button>
                  <Button onClick={handleAddEntry} disabled={submitting} className="w-full sm:w-auto bg-green-700 hover:bg-green-800">
                    {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Add Entry'}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200" data-testid="cash-collection-card">
            <CardContent className="p-4">
              <div>
                <p className="text-sm text-green-600 font-medium flex items-center gap-1">
                  <Banknote className="w-4 h-4" /> Cash Collection
                </p>
                <p className="text-2xl font-bold text-green-800">{formatINR(summary.cash.amount)}</p>
                <p className="text-xs text-green-600">{summary.cash.count} entries · {summary.cash.refills} cyl refilled</p>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200" data-testid="online-collection-card">
            <CardContent className="p-4">
              <div>
                <p className="text-sm text-blue-600 font-medium flex items-center gap-1">
                  <CreditCard className="w-4 h-4" /> Online Collection
                </p>
                <p className="text-2xl font-bold text-blue-800">{formatINR(summary.online.amount)}</p>
                <p className="text-xs text-blue-600">{summary.online.count} entries · {summary.online.refills} cyl refilled</p>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200" data-testid="pending-collection-card">
            <CardContent className="p-4">
              <div>
                <p className="text-sm text-amber-600 font-medium flex items-center gap-1">
                  <Clock className="w-4 h-4" /> Pending Collection
                </p>
                <p className="text-2xl font-bold text-amber-800">{formatINR(summary.pending.amount)}</p>
                <p className="text-xs text-amber-600">{summary.pending.count} entries · {summary.pending.refills} cyl refilled</p>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-orange-50 to-orange-100 border-orange-200" data-testid="accessory-collection-card">
            <CardContent className="p-4">
              <div>
                <p className="text-sm text-orange-600 font-medium flex items-center gap-1">
                  <ShoppingBag className="w-4 h-4" /> Accessory Sales
                </p>
                <p className="text-2xl font-bold text-orange-800">{formatINR(accessorySummary.total_amount)}</p>
                <p className="text-xs text-orange-600">{accessorySummary.total_sales} sales · {accessorySummary.total_quantity || 0} items</p>
                <div className="flex gap-2 mt-1.5 text-xs">
                  <span className="text-green-700" data-testid="acc-cash-total">C: {formatINR(accessorySummary.cash_amount || 0)}</span>
                  <span className="text-blue-700" data-testid="acc-online-total">O: {formatINR(accessorySummary.online_amount || 0)}</span>
                  <span className="text-amber-700" data-testid="acc-pending-total">P: {formatINR(accessorySummary.pending_amount || 0)}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200" data-testid="total-collection-card">
            <CardContent className="p-4">
              <div>
                <p className="text-sm text-purple-600 font-medium flex items-center gap-1">
                  <TrendingUp className="w-4 h-4" /> Grand Total
                </p>
                <p className="text-2xl font-bold text-purple-800">{formatINR(summary.total.amount + accessorySummary.total_amount)}</p>
                <p className="text-xs text-purple-600">{summary.total.new_connection_cylinders || 0} new cyl · {summary.total.refill_cylinders || 0} refill cyl</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Category Breakdown Cards */}
        {summary.categories && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="category-breakdown">
            <Card className="border-cyan-200 bg-cyan-50/50">
              <CardContent className="p-3 text-center">
                <p className="text-xs text-cyan-700 font-medium">Domestic New Conn.</p>
                <p className="text-xl font-bold text-cyan-800">{summary.categories.domestic_new_cyl} <span className="text-xs font-normal">cyl</span></p>
                <p className="text-xs text-cyan-500">{summary.categories.domestic_new_count} entries</p>
              </CardContent>
            </Card>
            <Card className="border-violet-200 bg-violet-50/50">
              <CardContent className="p-3 text-center">
                <p className="text-xs text-violet-700 font-medium">Commercial New Conn.</p>
                <p className="text-xl font-bold text-violet-800">{summary.categories.commercial_new_cyl} <span className="text-xs font-normal">cyl</span></p>
                <p className="text-xs text-violet-500">{summary.categories.commercial_new_count} entries</p>
              </CardContent>
            </Card>
            <Card className="border-yellow-200 bg-yellow-50/50">
              <CardContent className="p-3 text-center">
                <p className="text-xs text-yellow-700 font-medium">Domestic Refills</p>
                <p className="text-xl font-bold text-yellow-800">{summary.categories.domestic_refill_cyl} <span className="text-xs font-normal">cyl</span></p>
                <p className="text-xs text-yellow-500">{summary.categories.domestic_refill_count} entries</p>
              </CardContent>
            </Card>
            <Card className="border-rose-200 bg-rose-50/50">
              <CardContent className="p-3 text-center">
                <p className="text-xs text-rose-700 font-medium">Commercial Refills</p>
                <p className="text-xl font-bold text-rose-800">{summary.categories.commercial_refill_cyl} <span className="text-xs font-normal">cyl</span></p>
                <p className="text-xs text-rose-500">{summary.categories.commercial_refill_count} entries</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Active Date Range Indicator */}
        <div className="flex items-center gap-2 text-sm" data-testid="active-date-range">
          <Calendar className="h-4 w-4 text-slate-500" />
          <span className="text-slate-500">Showing:</span>
          <Badge variant="outline" className={`font-medium ${filterDateRange === 'custom' ? 'border-purple-300 bg-purple-50 text-purple-700' : 'border-blue-300 bg-blue-50 text-blue-700'}`}>
            {filterDateRange === 'custom' ? 'Custom Range' : filterDateRange === 'this_month' ? 'Current Month' : filterDateRange === 'last_month' ? 'Last Month' : filterDateRange === 'today' ? 'Today' : filterDateRange === 'week' ? 'Last 7 Days' : filterDateRange === 'year' ? 'This Year' : 'All Time'}
          </Badge>
          {startDate && endDate && (
            <span className="text-slate-600 font-medium">
              {formatDateDisplay(startDate)} – {filterDateRange === 'this_month' ? 'Today' : formatDateDisplay(endDate)}
            </span>
          )}
          {filterDateRange === 'all' && (
            <span className="text-slate-400 text-xs">(no date filter applied)</span>
          )}
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
                    <SelectItem value="split">Split Payment</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label className="text-xs">Connection Type</Label>
                <Select value={filterConnectionType} onValueChange={setFilterConnectionType}>
                  <SelectTrigger className="w-48 mt-1" data-testid="filter-connection-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="domestic">Domestic New Conn.</SelectItem>
                    <SelectItem value="commercial">Commercial New Conn.</SelectItem>
                    <SelectItem value="domestic_refill">Domestic Refill</SelectItem>
                    <SelectItem value="commercial_refill">Commercial Refill</SelectItem>
                    <SelectItem value="accessory">Accessory Sales</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label className="text-xs">Date Range</Label>
                <Select value={filterDateRange} onValueChange={setFilterDateRange}>
                  <SelectTrigger className="w-40 mt-1" data-testid="filter-date-range">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="this_month">This Month</SelectItem>
                    <SelectItem value="last_month">Last Month</SelectItem>
                    <SelectItem value="today">Today</SelectItem>
                    <SelectItem value="week">Last 7 Days</SelectItem>
                    <SelectItem value="year">This Year</SelectItem>
                    <SelectItem value="all">All Time</SelectItem>
                    <SelectItem value="custom">Custom Range</SelectItem>
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
                <div className="flex gap-1 mt-1 items-center">
                  <Input 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search consumer, memo, address..."
                    className="w-56"
                    data-testid="sales-search-input"
                  />
                  {searchQuery && (
                    <Button onClick={() => setSearchQuery('')} variant="ghost" size="icon" className="text-slate-400 hover:text-slate-600 shrink-0" data-testid="clear-search-btn">
                      <span className="text-lg">&times;</span>
                    </Button>
                  )}
                </div>
              </div>

              <Button onClick={fetchData} variant="outline" className="gap-2" data-testid="refresh-btn">
                <RefreshCw className="w-4 h-4" />
                Refresh
              </Button>
              {filterDateRange !== 'this_month' && (
                <Button 
                  onClick={() => {
                    setFilterDateRange('this_month');
                    setFilterWarehouse('all');
                    setFilterPaymentMode('all');
                    setFilterConnectionType('all');
                    setSearchQuery('');
                  }} 
                  variant="outline" 
                  className="gap-2 border-blue-300 text-blue-700 hover:bg-blue-50"
                  data-testid="reset-current-month-btn"
                >
                  <Calendar className="w-4 h-4" />
                  Reset to Current Month
                </Button>
              )}
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
                    <Label>No of Cylinders Refilled *</Label>
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
                      readOnly
                    />
                  </div>
                </div>

                {/* Multi-Payment for Quick Refill */}
                <div className="border rounded-lg p-3 bg-slate-50/80 space-y-2">
                  <Label className="text-xs font-semibold text-slate-600">Payment Breakdown</Label>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <Label className="text-[10px] text-green-700">Cash (₹)</Label>
                      <Input type="number" min="0" value={quickRefillForm.cash_amount} onChange={(e) => {
                        const cash = parseFloat(e.target.value) || 0;
                        const online = parseFloat(quickRefillForm.online_amount) || 0;
                        const credit = parseFloat(quickRefillForm.credit_amount) || 0;
                        setQuickRefillForm({ ...quickRefillForm, cash_amount: e.target.value, amount: (cash + online + credit).toString() });
                      }} placeholder="0" className="mt-0.5 h-8 text-sm border-green-200" />
                    </div>
                    <div>
                      <Label className="text-[10px] text-blue-700">Online (₹)</Label>
                      <Input type="number" min="0" value={quickRefillForm.online_amount} onChange={(e) => {
                        const cash = parseFloat(quickRefillForm.cash_amount) || 0;
                        const online = parseFloat(e.target.value) || 0;
                        const credit = parseFloat(quickRefillForm.credit_amount) || 0;
                        setQuickRefillForm({ ...quickRefillForm, online_amount: e.target.value, amount: (cash + online + credit).toString() });
                      }} placeholder="0" className="mt-0.5 h-8 text-sm border-blue-200" />
                    </div>
                    <div>
                      <Label className="text-[10px] text-amber-700">Credit (₹)</Label>
                      <Input type="number" min="0" value={quickRefillForm.credit_amount} onChange={(e) => {
                        const cash = parseFloat(quickRefillForm.cash_amount) || 0;
                        const online = parseFloat(quickRefillForm.online_amount) || 0;
                        const credit = parseFloat(e.target.value) || 0;
                        setQuickRefillForm({ ...quickRefillForm, credit_amount: e.target.value, amount: (cash + online + credit).toString() });
                      }} placeholder="0" className="mt-0.5 h-8 text-sm border-amber-200" />
                    </div>
                  </div>
                  <div className="text-xs text-right text-slate-600">
                    Total: <span className="font-bold">₹{((parseFloat(quickRefillForm.cash_amount) || 0) + (parseFloat(quickRefillForm.online_amount) || 0) + (parseFloat(quickRefillForm.credit_amount) || 0)).toLocaleString('en-IN')}</span>
                  </div>
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
                    disabled={submitting || !quickRefillForm.amount || parseFloat(quickRefillForm.amount) <= 0}
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
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-green-700 border-green-700">
                  {entries.length} cylinder
                </Badge>
                {accessorySales.length > 0 && (
                  <Badge variant="outline" className="text-orange-700 border-orange-700">
                    {accessorySales.length} accessory
                  </Badge>
                )}
              </div>
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
                    <th title="Cash Amount">Cash</th>
                    <th title="Online Amount">Online</th>
                    <th title="Credit/Pending Amount">Credit</th>
                    <th>New Conn Cyl</th>
                    <th>Refill Cyl</th>
                    <th>Remarks</th>
                    {isAdmin && <th>Warehouse</th>}
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {combinedEntries.length === 0 ? (
                    <tr>
                      <td colSpan={isAdmin ? 17 : 16} className="text-center py-8 text-slate-500">
                        No sales entries found
                      </td>
                    </tr>
                  ) : (
                    <>
                      {combinedEntries.map((entry, index) => (
                        <tr key={entry.id} className={entry.sale_type === 'accessory' ? 'bg-orange-50/40' : ''}>
                          <td className="text-center font-medium">{((currentPage - 1) * pageSize) + index + 1}</td>
                          <td>{entry.date}</td>
                          <td className="font-medium">{entry.consumer_name}</td>
                          <td className="max-w-[150px] truncate">{entry.address || '-'}</td>
                          <td>{entry.consumer_no || '-'}</td>
                          <td>
                            {getConnectionTypeBadge(entry.connection_type)}
                          </td>
                          <td>{entry.memo_no || '-'}</td>
                          <td className="font-semibold text-green-700">{formatINR(entry.amount)}</td>
                          <td>{getPaymentBadge(entry.payment_mode, entry)}</td>
                          <td className="text-center text-green-700">{entry.cash_amount > 0 ? formatINR(entry.cash_amount) : '-'}</td>
                          <td className="text-center text-blue-700">{entry.online_amount > 0 ? formatINR(entry.online_amount) : '-'}</td>
                          <td className="text-center text-amber-700">{entry.credit_amount > 0 ? formatINR(entry.credit_amount) : '-'}</td>
                          <td className="text-center">
                            {entry.sale_type === 'accessory' ? '-' : 
                              (!(entry.connection_type || '').includes('refill') ? 
                                (parseInt(entry.cylinder_nos) || (entry.no_of_refills || 1)) : '-')}
                          </td>
                          <td className="text-center">
                            {entry.sale_type === 'accessory' ? '-' : 
                              ((entry.connection_type || '').includes('refill') ? (entry.no_of_refills || 0) : '-')}
                          </td>
                          <td className="max-w-[120px] truncate">{entry.remarks || '-'}</td>
                          {isAdmin && <td><Badge variant="outline">{entry.warehouse_name}</Badge></td>}
                          <td>
                            {entry.sale_type === 'cylinder' ? (
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
                            ) : (
                              <span className="text-xs text-slate-400">-</span>
                            )}
                          </td>
                        </tr>
                      ))}
                      {/* Total Row */}
                      <tr className="bg-green-50 font-bold">
                        <td colSpan={7} className="text-right">TOTAL:</td>
                        <td className="text-green-800">{formatINR(combinedTotals.amount)}</td>
                        <td></td>
                        <td className="text-center text-green-700">{formatINR(combinedEntries.reduce((s, e) => s + (e.cash_amount || 0), 0))}</td>
                        <td className="text-center text-blue-700">{formatINR(combinedEntries.reduce((s, e) => s + (e.online_amount || 0), 0))}</td>
                        <td className="text-center text-amber-700">{formatINR(combinedEntries.reduce((s, e) => s + (e.credit_amount || 0), 0))}</td>
                        <td className="text-center">{combinedTotals.newCyl}</td>
                        <td className="text-center">{combinedTotals.refills}</td>
                        <td colSpan={isAdmin ? 3 : 2}></td>
                      </tr>
                    </>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-2" data-testid="pagination-controls">
            <p className="text-sm text-slate-500">
              Showing {((currentPage - 1) * pageSize) + 1}–{Math.min(currentPage * pageSize, totalEntries)} of {totalEntries} entries
            </p>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(1)}
                data-testid="page-first"
              >First</Button>
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage(p => p - 1)}
                data-testid="page-prev"
              >Prev</Button>
              <span className="px-3 py-1 text-sm font-medium bg-slate-100 rounded">
                {currentPage} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage(p => p + 1)}
                data-testid="page-next"
              >Next</Button>
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage(totalPages)}
                data-testid="page-last"
              >Last</Button>
            </div>
          </div>
        )}

        {/* Edit Dialog */}
        <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle className="text-lg">Edit Sales Entry</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 sm:space-y-4 py-2 sm:py-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                <div>
                  <Label className="text-sm">Date</Label>
                  <Input 
                    type="date"
                    value={editForm.date || ''}
                    onChange={(e) => setEditForm({ ...editForm, date: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-sm">Consumer Name</Label>
                  <Input 
                    value={editForm.consumer_name || ''}
                    onChange={(e) => setEditForm({ ...editForm, consumer_name: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-sm">Consumer No</Label>
                  <Input 
                    value={editForm.consumer_no || ''}
                    onChange={(e) => setEditForm({ ...editForm, consumer_no: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-sm">Address</Label>
                  <Input 
                    value={editForm.address || ''}
                    onChange={(e) => setEditForm({ ...editForm, address: e.target.value })}
                    className="mt-1"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                <div>
                  <Label className="text-sm">Connection Type</Label>
                  <Select 
                    value={editForm.connection_type || 'domestic'} 
                    onValueChange={(v) => setEditForm({ ...editForm, connection_type: v, cylinder_nos: v.includes('refill') ? '' : editForm.cylinder_nos, no_of_refills: v.includes('refill') ? editForm.no_of_refills : '' })}
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
                  <Label className="text-sm">No. of Cylinders Refilled</Label>
                  <Input 
                    type="number"
                    min="1"
                    value={editForm.no_of_refills || ''}
                    onChange={(e) => setEditForm({ ...editForm, no_of_refills: e.target.value })}
                    className="mt-1"
                    disabled={!(editForm.connection_type || '').includes('refill')}
                  />
                </div>
              </div>

              {/* No. of Cylinders for new connection types */}
              {(editForm.connection_type === 'domestic' || editForm.connection_type === 'commercial') && (
                <div>
                  <Label className="text-sm">No. of Cylinders</Label>
                  <Input 
                    type="number"
                    min="1"
                    value={editForm.cylinder_nos || ''}
                    onChange={(e) => setEditForm({ ...editForm, cylinder_nos: e.target.value })}
                    placeholder="No. of cylinders sold"
                    className="mt-1"
                  />
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                <div>
                  <Label className="text-sm">Memo No</Label>
                  <Input 
                    value={editForm.memo_no || ''}
                    onChange={(e) => setEditForm({ ...editForm, memo_no: e.target.value })}
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-sm">Remarks</Label>
                  <Input 
                    value={editForm.remarks || ''}
                    onChange={(e) => setEditForm({ ...editForm, remarks: e.target.value })}
                    className="mt-1"
                  />
                </div>
              </div>

              {/* Multi-Payment Section */}
              <div className="border rounded-lg p-3 bg-slate-50/80 space-y-3">
                <Label className="text-sm font-semibold text-slate-700">Payment Breakdown</Label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div>
                    <Label className="text-xs text-green-700">Cash (₹)</Label>
                    <Input 
                      type="number" min="0"
                      value={editForm.cash_amount || ''}
                      onChange={(e) => {
                        const cash = parseFloat(e.target.value) || 0;
                        const online = parseFloat(editForm.online_amount) || 0;
                        const credit = parseFloat(editForm.credit_amount) || 0;
                        setEditForm({ ...editForm, cash_amount: e.target.value, amount: cash + online + credit });
                      }}
                      placeholder="0"
                      className="mt-1 border-green-200"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-blue-700">Online / UPI (₹)</Label>
                    <Input 
                      type="number" min="0"
                      value={editForm.online_amount || ''}
                      onChange={(e) => {
                        const cash = parseFloat(editForm.cash_amount) || 0;
                        const online = parseFloat(e.target.value) || 0;
                        const credit = parseFloat(editForm.credit_amount) || 0;
                        setEditForm({ ...editForm, online_amount: e.target.value, amount: cash + online + credit });
                      }}
                      placeholder="0"
                      className="mt-1 border-blue-200"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-amber-700">Credit / Pending (₹)</Label>
                    <Input 
                      type="number" min="0"
                      value={editForm.credit_amount || ''}
                      onChange={(e) => {
                        const cash = parseFloat(editForm.cash_amount) || 0;
                        const online = parseFloat(editForm.online_amount) || 0;
                        const credit = parseFloat(e.target.value) || 0;
                        setEditForm({ ...editForm, credit_amount: e.target.value, amount: cash + online + credit });
                      }}
                      placeholder="0"
                      className="mt-1 border-amber-200"
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between text-sm bg-white rounded px-3 py-1.5 border">
                  <span className="text-slate-500">Total Amount:</span>
                  <span className="font-bold text-slate-800">
                    ₹{((parseFloat(editForm.cash_amount) || 0) + (parseFloat(editForm.online_amount) || 0) + (parseFloat(editForm.credit_amount) || 0)).toLocaleString('en-IN')}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setEditDialogOpen(false)} className="w-full sm:w-auto">Cancel</Button>
              <Button onClick={handleUpdateEntry} disabled={submitting} className="w-full sm:w-auto bg-green-700 hover:bg-green-800">
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
