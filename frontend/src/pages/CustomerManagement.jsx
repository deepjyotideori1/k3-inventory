import React, { useState, useEffect, useRef, useMemo } from 'react';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { 
  getCustomers, 
  createCustomer,
  createCustomerForWarehouse,
  updateCustomer,
  deleteCustomer,
  getCustomerLinkedRecords,
  bulkUploadCustomers,
  bulkUploadCustomersForWarehouse,
  getCustomerSummary,
  downloadCustomerTemplate,
  exportCustomersPDF,
  exportCustomersExcel,
  getWarehouses,
  getCustomerRefillStatus,
  exportCustomerRefillPDF,
  exportCustomerRefillExcel,
  syncCustomersFromSales
} from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger, DialogFooter, DialogClose } from '../components/ui/dialog';
import { Checkbox } from '../components/ui/checkbox';
import SearchBar, { HighlightMatch } from '../components/SearchBar';
import { 
  Users,
  Plus,
  Loader2,
  FileText,
  Download,
  Trash2,
  Calendar,
  Upload,
  FileSpreadsheet,
  Save,
  Search,
  Home,
  Building2,
  Edit,
  CheckCircle,
  XCircle,
  RefreshCw,
  AlertTriangle,
  Flame,
  Clock
} from 'lucide-react';
import { getTodayDate, formatDate } from '../lib/utils';
import { toast } from 'sonner';
import * as XLSX from 'xlsx';

const CustomerManagement = () => {
  const { user, isAdmin } = useAuth();
  const canEditDelete = isAdmin || user?.role === 'warehouse_manager';
  const fileInputRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [customers, setCustomers] = useState([]);
  const [summary, setSummary] = useState({});
  const [warehouses, setWarehouses] = useState([]);
  const [activeTab, setActiveTab] = useState('list');
  
  // Form state
  const [formData, setFormData] = useState({
    date: getTodayDate(),
    connection_type: 'domestic',
    customer_name: '',
    address: '',
    phone: '',
    consumer_no: '',
    cash_memo_no: '',
    cylinder_nos: '',
    gas_card_issued: false,
    kyc_done: false,
    remarks: ''
  });
  const [submitting, setSubmitting] = useState(false);
  const [selectedWarehouse, setSelectedWarehouse] = useState('');
  
  // Edit state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState(null);
  const [editForm, setEditForm] = useState({});
  
  // Delete state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingCustomer, setDeletingCustomer] = useState(null);
  const [linkedRecords, setLinkedRecords] = useState(null);
  const [loadingLinked, setLoadingLinked] = useState(false);
  const [deleting, setDeleting] = useState(false);
  
  // Filters
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterWarehouse, setFilterWarehouse] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [exporting, setExporting] = useState(false);
  const [filteredCustomers, setFilteredCustomers] = useState([]);
  
  // Bulk upload
  const [bulkUploading, setBulkUploading] = useState(false);
  const [bulkPreview, setBulkPreview] = useState([]);
  const [showBulkPreview, setShowBulkPreview] = useState(false);
  
  // Refill status
  const [refillMap, setRefillMap] = useState({});
  const [refillSummary, setRefillSummary] = useState({});
  const [exportingRefill, setExportingRefill] = useState(false);

  useEffect(() => {
    fetchData();
  }, [filterCategory, filterWarehouse, searchQuery, startDate, endDate]);

  useEffect(() => {
    if (isAdmin) {
      fetchWarehouses();
    }
  }, [isAdmin]);

  const fetchWarehouses = async () => {
    try {
      const response = await getWarehouses();
      setWarehouses(response.data);
    } catch (error) {
      console.error('Failed to fetch warehouses:', error);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      // High limit so the full customer base loads in one shot.
      // Backend defaults to 50/page which made FY2024-25 (older) customers
      // disappear once the warehouse grew past 50 records.
      const params = { limit: 10000, page: 1 };
      if (filterCategory !== 'all') params.category = filterCategory;
      if (filterWarehouse !== 'all') params.warehouse_id = filterWarehouse;
      if (searchQuery) params.search = searchQuery;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      
      const [customersRes, summaryRes] = await Promise.all([
        getCustomers(params),
        getCustomerSummary(filterWarehouse !== 'all' ? { warehouse_id: filterWarehouse } : {})
      ]);
      
      const custData = customersRes.data.customers || customersRes.data;
      const totalInDb = customersRes.data.total ?? custData.length;
      setCustomers(custData);
      setFilteredCustomers(custData);
      setSummary(summaryRes.data);

      // Defensive notice if record count exceeds the load cap
      if (totalInDb > custData.length) {
        toast.warning(
          `Loaded ${custData.length} of ${totalInDb} customers. Apply filters to narrow down.`
        );
      }
      
      // Fetch refill status separately (non-blocking) so it doesn't break the page
      try {
        const refillRes = await getCustomerRefillStatus(filterWarehouse !== 'all' ? { warehouse_id: filterWarehouse } : {});
        const rMap = {};
        (refillRes.data.customers || []).forEach(c => { rMap[c.id] = c; });
        setRefillMap(rMap);
        setRefillSummary(refillRes.data.summary || {});
      } catch (refillErr) {
        console.error('Failed to fetch refill status:', refillErr);
        setRefillMap({});
        setRefillSummary({});
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      toast.error('Failed to load customers');
    } finally {
      setLoading(false);
    }
  };

  const getRefillBadge = (days) => {
    if (days === null || days === undefined) return <span className="text-slate-400 text-xs italic">No history</span>;
    if (days <= 15) return <Badge className="bg-green-100 text-green-800 text-xs">{days}d</Badge>;
    if (days <= 30) return <Badge className="bg-yellow-100 text-yellow-800 text-xs">{days}d</Badge>;
    return <Badge className="bg-red-100 text-red-800 text-xs"><AlertTriangle className="w-3 h-3 mr-0.5" />{days}d</Badge>;
  };

  const handleExportRefillPDF = async () => {
    setExportingRefill(true);
    try {
      await exportCustomerRefillPDF(filterWarehouse !== 'all' ? { warehouse_id: filterWarehouse } : {});
      toast.success('Refill status PDF exported');
    } catch { toast.error('Failed to export'); }
    finally { setExportingRefill(false); }
  };

  const handleExportRefillExcel = async () => {
    setExportingRefill(true);
    try {
      await exportCustomerRefillExcel(filterWarehouse !== 'all' ? { warehouse_id: filterWarehouse } : {});
      toast.success('Refill status Excel exported');
    } catch { toast.error('Failed to export'); }
    finally { setExportingRefill(false); }
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
      if (isAdmin) {
        await createCustomerForWarehouse(selectedWarehouse, formData);
      } else {
        await createCustomer(formData);
      }
      toast.success('Customer added successfully');
      setFormData({
        date: getTodayDate(),
        connection_type: 'domestic',
        customer_name: '',
        address: '',
        phone: '',
        consumer_no: '',
        cash_memo_no: '',
        cylinder_nos: '',
        gas_card_issued: false,
        kyc_done: false,
        remarks: ''
      });
      fetchData();
      setActiveTab('list');
    } catch (error) {
      console.error('Failed to add customer:', error);
      toast.error(error.response?.data?.detail || 'Failed to add customer');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (customer) => {
    setEditingCustomer(customer);
    setEditForm({
      date: customer.date,
      connection_type: customer.connection_type,
      customer_name: customer.customer_name,
      address: customer.address,
      phone: customer.phone || '',
      consumer_no: customer.consumer_no,
      cash_memo_no: customer.cash_memo_no,
      cylinder_nos: customer.cylinder_nos,
      gas_card_issued: customer.gas_card_issued,
      kyc_done: customer.kyc_done,
      remarks: customer.remarks
    });
    setEditDialogOpen(true);
  };

  const handleEditSubmit = async () => {
    if (!editingCustomer) return;
    
    setSubmitting(true);
    try {
      await updateCustomer(editingCustomer.id, editForm);
      toast.success('Customer updated successfully');
      setEditDialogOpen(false);
      setEditingCustomer(null);
      fetchData();
    } catch (error) {
      console.error('Failed to update customer:', error);
      toast.error(error.response?.data?.detail || 'Failed to update customer');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteClick = async (customer) => {
    setDeletingCustomer(customer);
    setLinkedRecords(null);
    setDeleteDialogOpen(true);
    setLoadingLinked(true);
    try {
      const res = await getCustomerLinkedRecords(customer.id);
      setLinkedRecords(res.data);
    } catch {
      setLinkedRecords({ active_orders: 0, total_orders: 0, sales_entries: 0, has_linked_records: false });
    } finally {
      setLoadingLinked(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deletingCustomer) return;
    setDeleting(true);
    try {
      await deleteCustomer(deletingCustomer.id);
      toast.success('Customer deleted successfully');
      setDeleteDialogOpen(false);
      setDeletingCustomer(null);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete customer');
    } finally {
      setDeleting(false);
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      await downloadCustomerTemplate();
      toast.success('Template downloaded');
    } catch (error) {
      toast.error('Failed to download template');
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const data = new Uint8Array(event.target.result);
        // cellDates:true -> Excel date cells are returned as JS Date objects
        const workbook = XLSX.read(data, { type: 'array', cellDates: true });
        const sheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[sheetName];
        const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1, raw: true });

        const MONTH_MAP = {
          jan: '01', feb: '02', mar: '03', apr: '04', may: '05', jun: '06',
          jul: '07', aug: '08', sep: '09', sept: '09', oct: '10', nov: '11', dec: '12',
        };

        // Robust date parser: returns 'YYYY-MM-DD' or null if unparseable.
        const parseDate = (raw) => {
          if (raw === null || raw === undefined || raw === '') return null;

          // 1. JS Date (from cellDates:true)
          if (raw instanceof Date && !isNaN(raw.getTime())) {
            const yyyy = raw.getFullYear();
            const mm = String(raw.getMonth() + 1).padStart(2, '0');
            const dd = String(raw.getDate()).padStart(2, '0');
            return `${yyyy}-${mm}-${dd}`;
          }

          // 2. Excel serial number (days since 1899-12-30)
          if (typeof raw === 'number' && raw > 0 && raw < 200000) {
            const epoch = Date.UTC(1899, 11, 30);
            const ms = epoch + raw * 86400000;
            const d = new Date(ms);
            if (!isNaN(d.getTime())) {
              const yyyy = d.getUTCFullYear();
              const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
              const dd = String(d.getUTCDate()).padStart(2, '0');
              return `${yyyy}-${mm}-${dd}`;
            }
          }

          const str = String(raw).trim();
          if (!str) return null;

          // 3. YYYY-MM-DD (already correct)
          let m = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
          if (m) return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`;

          // 4. DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY (Indian format)
          m = str.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/);
          if (m) return `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;

          // 5. DD-MM-YY (2-digit year, assume 2000s)
          m = str.match(/^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2})$/);
          if (m) {
            const yy = parseInt(m[3], 10);
            const yyyy = yy < 50 ? 2000 + yy : 1900 + yy;
            return `${yyyy}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
          }

          // 6. DD-Mon-YYYY (e.g., 15-Apr-2025, 1 April 2025)
          m = str.match(/^(\d{1,2})[\s-]([A-Za-z]+)[\s-](\d{4})$/);
          if (m && MONTH_MAP[m[2].toLowerCase()]) {
            return `${m[3]}-${MONTH_MAP[m[2].toLowerCase()]}-${m[1].padStart(2, '0')}`;
          }

          // 7. Mon DD, YYYY (e.g., Apr 15, 2025)
          m = str.match(/^([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})$/);
          if (m && MONTH_MAP[m[1].toLowerCase()]) {
            return `${m[3]}-${MONTH_MAP[m[1].toLowerCase()]}-${m[2].padStart(2, '0')}`;
          }

          // 8. Last resort: let Date constructor try
          const d = new Date(str);
          if (!isNaN(d.getTime()) && d.getFullYear() > 1970 && d.getFullYear() < 2100) {
            const yyyy = d.getFullYear();
            const mm = String(d.getMonth() + 1).padStart(2, '0');
            const dd = String(d.getDate()).padStart(2, '0');
            return `${yyyy}-${mm}-${dd}`;
          }

          return null;
        };

        // Skip header row - new format with phone column
        let unparsedDateCount = 0;
        const customers = jsonData.slice(1).filter(row => row.length > 0 && row[2]).map(row => {
          const parsed = parseDate(row[0]);
          if (parsed === null && row[0] !== '' && row[0] !== null && row[0] !== undefined) {
            unparsedDateCount += 1;
          }
          return {
            date: parsed || getTodayDate(),
            connection_type: (row[1] || 'domestic').toString().toLowerCase(),
            customer_name: (row[2] || '').toString(),
            address: (row[3] || '').toString(),
            phone: row[4]?.toString().replace(/\D/g, '').slice(0, 10) || '',
            consumer_no: row[5]?.toString().replace(/\D/g, '').slice(0, 10) || '',
            cash_memo_no: row[6]?.toString() || '',
            cylinder_nos: row[7]?.toString() || '',
            gas_card_issued: (row[8] || '').toString().toLowerCase() === 'yes',
            kyc_done: (row[9] || '').toString().toLowerCase() === 'yes',
            remarks: (row[10] || '').toString(),
          };
        });

        setBulkPreview(customers);
        setShowBulkPreview(true);
        if (unparsedDateCount > 0) {
          toast.warning(`${unparsedDateCount} row(s) had unparseable dates and were set to today. Use DD-MM-YYYY format.`);
        }
      } catch (error) {
        console.error('Error parsing file:', error);
        toast.error('Failed to parse Excel file. Please check the format.');
      }
    };
    reader.readAsArrayBuffer(file);
    e.target.value = '';
  };

  const handleBulkUpload = async () => {
    if (bulkPreview.length === 0) {
      toast.error('No customers to upload');
      return;
    }
    
    if (isAdmin && !selectedWarehouse) {
      toast.error('Please select a warehouse for bulk upload');
      return;
    }
    
    setBulkUploading(true);
    try {
      if (isAdmin) {
        await bulkUploadCustomersForWarehouse(selectedWarehouse, { customers: bulkPreview });
      } else {
        await bulkUploadCustomers({ customers: bulkPreview });
      }
      toast.success(`Successfully uploaded ${bulkPreview.length} customers`);
      setBulkPreview([]);
      setShowBulkPreview(false);
      fetchData();
      setActiveTab('list');
    } catch (error) {
      console.error('Bulk upload failed:', error);
      toast.error(error.response?.data?.detail || 'Failed to upload customers');
    } finally {
      setBulkUploading(false);
    }
  };

  const handleExportPDF = async () => {
    setExporting(true);
    try {
      const params = { category: filterCategory, start_date: startDate, end_date: endDate };
      if (filterWarehouse !== 'all') params.warehouse_id = filterWarehouse;
      await exportCustomersPDF(params);
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
      const params = { category: filterCategory, start_date: startDate, end_date: endDate };
      if (filterWarehouse !== 'all') params.warehouse_id = filterWarehouse;
      await exportCustomersExcel(params);
      toast.success('Excel exported successfully');
    } catch (error) {
      toast.error('Failed to export Excel');
    } finally {
      setExporting(false);
    }
  };

  const [syncing, setSyncing] = useState(false);
  const handleSyncFromSales = async () => {
    if (!window.confirm(
      'This will scan all sales entries and create any missing customer records ' +
      '(preserving the original date so FY2024-25 and earlier customers reappear ' +
      'in their correct financial year). Continue?'
    )) return;
    setSyncing(true);
    try {
      const res = await syncCustomersFromSales();
      const d = res.data;
      toast.success(
        `Sync complete: ${d.created} new customer(s), ${d.linked_sales_entries} sales entries linked. ` +
        `Scanned ${d.scanned}.`
      );
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to sync from sales');
    } finally {
      setSyncing(false);
    }
  };

  if (loading && customers.length === 0) {
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
      <div className="space-y-6" data-testid="customer-management-page">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-800">Customer Management</h1>
            <p className="text-slate-500 mt-1">
              {isAdmin ? 'Manage customers across all warehouses' : `Manage customers for ${user?.warehouse_name || 'your warehouse'}`}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleSyncFromSales}
              disabled={syncing}
              data-testid="sync-from-sales-btn"
              title="Create missing customer records from existing sales entries (e.g., FY2024-25 customers)"
            >
              {syncing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
              Sync from Sales
            </Button>
            <Button variant="outline" onClick={handleDownloadTemplate} data-testid="download-template-btn">
              <Download className="w-4 h-4 mr-2" />
              Sample Excel
            </Button>
            <Button 
              className="bg-green-700 hover:bg-green-800"
              onClick={() => setActiveTab('add')}
              data-testid="add-customer-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Customer
            </Button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card className="bg-gradient-to-br from-green-50 to-emerald-50 border-green-200">
            <CardContent className="p-4 text-center">
              <p className="text-sm text-green-700 font-medium">Total Customers</p>
              <p className="text-3xl font-bold text-green-800">{summary.total_customers || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200">
            <CardContent className="p-4 text-center">
              <Home className="w-5 h-5 text-blue-600 mx-auto mb-1" />
              <p className="text-sm text-blue-700 font-medium">Domestic</p>
              <p className="text-2xl font-bold text-blue-800">{summary.total_domestic || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-purple-50 to-violet-50 border-purple-200">
            <CardContent className="p-4 text-center">
              <Building2 className="w-5 h-5 text-purple-600 mx-auto mb-1" />
              <p className="text-sm text-purple-700 font-medium">Commercial</p>
              <p className="text-2xl font-bold text-purple-800">{summary.total_commercial || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-amber-50 to-yellow-50 border-amber-200">
            <CardContent className="p-4 text-center">
              <p className="text-sm text-amber-700 font-medium">Gas Card Issued</p>
              <p className="text-2xl font-bold text-amber-800">{summary.total_gas_card_issued || 0}</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-teal-50 to-cyan-50 border-teal-200">
            <CardContent className="p-4 text-center">
              <p className="text-sm text-teal-700 font-medium">KYC Done</p>
              <p className="text-2xl font-bold text-teal-800">{summary.total_kyc_done || 0}</p>
            </CardContent>
          </Card>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-white border">
            <TabsTrigger value="list" className="data-[state=active]:bg-green-100">
              <Users className="w-4 h-4 mr-2" />
              Customer List
            </TabsTrigger>
            <TabsTrigger value="add" className="data-[state=active]:bg-green-100">
              <Plus className="w-4 h-4 mr-2" />
              Add Customer
            </TabsTrigger>
            <TabsTrigger value="bulk" className="data-[state=active]:bg-green-100">
              <Upload className="w-4 h-4 mr-2" />
              Bulk Upload
            </TabsTrigger>
          </TabsList>

          {/* Customer List Tab */}
          <TabsContent value="list" className="mt-4 space-y-4">
            {/* Enhanced Search Bar */}
            <Card className="bg-gradient-to-r from-green-50 to-emerald-50 border-green-200">
              <CardContent className="p-4">
                <div className="mb-4">
                  <Label className="text-green-800 font-medium mb-2 block">Quick Search</Label>
                  <SearchBar
                    data={customers}
                    searchFields={['customer_name', 'phone', 'consumer_no', 'address', 'warehouse_name']}
                    onFilter={setFilteredCustomers}
                    placeholder="Search by name, phone, consumer no, address..."
                    showSuggestions={true}
                    maxSuggestions={6}
                    suggestionLabelField="customer_name"
                    className="max-w-2xl"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Filters */}
            <Card>
              <CardContent className="p-4">
                <div className="flex flex-wrap items-end gap-4">
                  <div>
                    <Label>Category</Label>
                    <Select value={filterCategory} onValueChange={setFilterCategory}>
                      <SelectTrigger className="w-36 mt-1" data-testid="category-filter">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All</SelectItem>
                        <SelectItem value="domestic">Domestic</SelectItem>
                        <SelectItem value="commercial">Commercial</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {isAdmin && (
                    <div>
                      <Label>Warehouse</Label>
                      <Select value={filterWarehouse} onValueChange={setFilterWarehouse}>
                        <SelectTrigger className="w-44 mt-1" data-testid="warehouse-filter">
                          <SelectValue placeholder="All Warehouses" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="all">All Warehouses</SelectItem>
                          {warehouses.filter(w => w.name !== 'Plant Hollongi').map(w => (
                            <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
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
                  <Button variant="outline" onClick={fetchData}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Refresh
                  </Button>
                  <div className="flex gap-2 ml-auto">
                    <Button 
                      variant="outline" 
                      onClick={handleExportRefillPDF}
                      disabled={exportingRefill}
                      className="border-orange-300 text-orange-700 hover:bg-orange-50"
                      data-testid="export-refill-pdf-btn"
                    >
                      {exportingRefill ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Flame className="w-4 h-4 mr-2" />}
                      Refill PDF
                    </Button>
                    <Button 
                      variant="outline" 
                      onClick={handleExportRefillExcel}
                      disabled={exportingRefill}
                      className="border-orange-300 text-orange-700 hover:bg-orange-50"
                      data-testid="export-refill-excel-btn"
                    >
                      {exportingRefill ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Flame className="w-4 h-4 mr-2" />}
                      Refill Excel
                    </Button>
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

            {/* Customer Table */}
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">Customer List</CardTitle>
                  <Badge variant="outline" className="text-green-700">
                    {filteredCustomers.length} of {customers.length} customers
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {filteredCustomers.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Type</th>
                          <th>Customer Name</th>
                          <th>Phone</th>
                          <th>Address</th>
                          <th>Consumer No</th>
                          <th>Last Refill</th>
                          <th>Days Since</th>
                          <th>Gas Card</th>
                          <th>KYC</th>
                          {isAdmin && <th>Warehouse</th>}
                          {canEditDelete && <th>Actions</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {filteredCustomers.map((c) => (
                          <tr key={c.id} data-testid={`customer-row-${c.id}`}>
                            <td>{formatDate(c.date)}</td>
                            <td>
                              <Badge variant={c.connection_type === 'domestic' ? 'default' : 'secondary'}>
                                {c.connection_type === 'domestic' ? <Home className="w-3 h-3 mr-1" /> : <Building2 className="w-3 h-3 mr-1" />}
                                {c.connection_type}
                              </Badge>
                            </td>
                            <td className="font-medium">{c.customer_name}</td>
                            <td>{c.phone || '-'}</td>
                            <td className="text-sm text-slate-600 max-w-[200px] truncate">{c.address}</td>
                            <td>{c.consumer_no}</td>
                            <td className="text-xs">
                              {refillMap[c.id]?.last_refill_date ? (
                                (() => { try { return new Date(refillMap[c.id].last_refill_date).toLocaleDateString('en-IN', { day: '2-digit', month: '2-digit', year: 'numeric' }); } catch { return refillMap[c.id].last_refill_date; } })()
                              ) : <span className="text-slate-400 italic">-</span>}
                            </td>
                            <td>{getRefillBadge(refillMap[c.id]?.days_since_refill)}</td>
                            <td>
                              {c.gas_card_issued ? 
                                <CheckCircle className="w-5 h-5 text-green-600" /> : 
                                <XCircle className="w-5 h-5 text-slate-300" />
                              }
                            </td>
                            <td>
                              {c.kyc_done ? 
                                <CheckCircle className="w-5 h-5 text-green-600" /> : 
                                <XCircle className="w-5 h-5 text-slate-300" />
                              }
                            </td>
                            {isAdmin && <td className="text-sm">{c.warehouse_name}</td>}
                            {canEditDelete && (
                              <td>
                                <div className="flex gap-1">
                                  <Button 
                                    variant="ghost" 
                                    size="sm"
                                    onClick={() => handleEdit(c)}
                                    className="text-blue-600 hover:text-blue-800"
                                    data-testid={`edit-customer-${c.id}`}
                                  >
                                    <Edit className="w-4 h-4" />
                                  </Button>
                                  <Button 
                                    variant="ghost" 
                                    size="sm"
                                    onClick={() => handleDeleteClick(c)}
                                    className="text-red-600 hover:text-red-800"
                                    data-testid={`delete-customer-${c.id}`}
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </Button>
                                </div>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500">No customers found</p>
                    <Button 
                      className="mt-4 bg-green-700 hover:bg-green-800"
                      onClick={() => setActiveTab('add')}
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Add First Customer
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Add Customer Tab */}
          <TabsContent value="add" className="mt-4">
            <Card data-testid="add-customer-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Plus className="w-5 h-5 text-green-700" />
                  Add New Customer
                </CardTitle>
                <CardDescription>Enter customer details to add a new customer record</CardDescription>
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
                      <Label>Date *</Label>
                      <Input 
                        type="date" 
                        value={formData.date}
                        onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                        className="mt-1"
                        data-testid="customer-date"
                      />
                    </div>
                    <div>
                      <Label>Connection Type *</Label>
                      <Select 
                        value={formData.connection_type} 
                        onValueChange={(v) => setFormData({ ...formData, connection_type: v })}
                      >
                        <SelectTrigger className="mt-1" data-testid="connection-type">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="domestic">
                            <div className="flex items-center gap-2">
                              <Home className="w-4 h-4" /> Domestic
                            </div>
                          </SelectItem>
                          <SelectItem value="commercial">
                            <div className="flex items-center gap-2">
                              <Building2 className="w-4 h-4" /> Commercial
                            </div>
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label>Customer Name *</Label>
                      <Input 
                        value={formData.customer_name}
                        onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                        placeholder="Enter customer name"
                        className="mt-1"
                        data-testid="customer-name"
                      />
                    </div>
                    <div>
                      <Label>Phone (10 digits for SMS/WhatsApp)</Label>
                      <Input 
                        value={formData.phone}
                        onChange={(e) => {
                          const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                          setFormData({ ...formData, phone: value });
                        }}
                        placeholder="Enter 10 digit number"
                        className="mt-1"
                        maxLength={10}
                        data-testid="customer-phone"
                      />
                      {formData.phone && formData.phone.length !== 10 && (
                        <p className="text-xs text-red-500 mt-1">Must be 10 digits ({formData.phone.length}/10)</p>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label>Address</Label>
                      <Textarea 
                        value={formData.address}
                        onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                        placeholder="Enter full address"
                        className="mt-1"
                        data-testid="customer-address"
                      />
                    </div>
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
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
                            data-testid="consumer-no"
                          />
                          {formData.consumer_no && formData.consumer_no.length !== 10 && (
                            <p className="text-xs text-red-500 mt-1">Must be 10 digits ({formData.consumer_no.length}/10)</p>
                          )}
                        </div>
                        <div>
                          <Label>Cash Memo No</Label>
                          <Input 
                            value={formData.cash_memo_no}
                            onChange={(e) => setFormData({ ...formData, cash_memo_no: e.target.value })}
                            placeholder="e.g., CM001"
                            className="mt-1"
                            data-testid="cash-memo-no"
                          />
                        </div>
                      </div>
                      <div>
                        <Label>Cylinder Nos</Label>
                        <Input 
                          value={formData.cylinder_nos}
                          onChange={(e) => setFormData({ ...formData, cylinder_nos: e.target.value })}
                          placeholder="e.g., CYL-001, CYL-002"
                          className="mt-1"
                          data-testid="cylinder-nos"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="flex items-center space-x-3 p-4 bg-slate-50 rounded-lg">
                      <Checkbox 
                        id="gas_card"
                        checked={formData.gas_card_issued}
                        onCheckedChange={(checked) => setFormData({ ...formData, gas_card_issued: checked })}
                        data-testid="gas-card-checkbox"
                      />
                      <Label htmlFor="gas_card" className="cursor-pointer">Gas Card Issued</Label>
                    </div>
                    <div className="flex items-center space-x-3 p-4 bg-slate-50 rounded-lg">
                      <Checkbox 
                        id="kyc"
                        checked={formData.kyc_done}
                        onCheckedChange={(checked) => setFormData({ ...formData, kyc_done: checked })}
                        data-testid="kyc-checkbox"
                      />
                      <Label htmlFor="kyc" className="cursor-pointer">KYC Done</Label>
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
                    <Button type="button" variant="outline" onClick={() => setActiveTab('list')}>
                      Cancel
                    </Button>
                    <Button 
                      type="submit" 
                      disabled={submitting}
                      className="bg-green-700 hover:bg-green-800"
                      data-testid="submit-customer-btn"
                    >
                      {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                      Save Customer
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Bulk Upload Tab */}
          <TabsContent value="bulk" className="mt-4 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Upload className="w-5 h-5 text-green-700" />
                  Bulk Customer Upload
                </CardTitle>
                <CardDescription>Upload multiple customers at once using an Excel file</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {isAdmin && (
                  <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                    <Label className="text-amber-800">Select Warehouse for Bulk Upload *</Label>
                    <Select value={selectedWarehouse} onValueChange={setSelectedWarehouse}>
                      <SelectTrigger className="mt-2" data-testid="bulk-warehouse-select">
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

                <div className="border-2 border-dashed border-slate-300 rounded-lg p-8 text-center">
                  <Upload className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-slate-700 mb-2">Upload Excel File</h3>
                  <p className="text-sm text-slate-500 mb-4">
                    Download the sample template first, fill in your data, then upload
                  </p>
                  <div className="flex justify-center gap-4">
                    <Button variant="outline" onClick={handleDownloadTemplate}>
                      <Download className="w-4 h-4 mr-2" />
                      Download Template
                    </Button>
                    <input 
                      type="file" 
                      ref={fileInputRef}
                      accept=".xlsx,.xls"
                      onChange={handleFileSelect}
                      className="hidden"
                    />
                    <Button 
                      onClick={() => fileInputRef.current?.click()}
                      className="bg-green-700 hover:bg-green-800"
                      data-testid="upload-file-btn"
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      Select File
                    </Button>
                  </div>
                </div>

                {/* Preview */}
                {showBulkPreview && bulkPreview.length > 0 && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="font-medium text-slate-700">
                        Preview ({bulkPreview.length} customers)
                      </h4>
                      <div className="flex gap-2">
                        <Button 
                          variant="outline" 
                          onClick={() => { setBulkPreview([]); setShowBulkPreview(false); }}
                        >
                          Cancel
                        </Button>
                        <Button 
                          onClick={handleBulkUpload}
                          disabled={bulkUploading}
                          className="bg-green-700 hover:bg-green-800"
                          data-testid="confirm-bulk-upload-btn"
                        >
                          {bulkUploading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Upload className="w-4 h-4 mr-2" />}
                          Upload {bulkPreview.length} Customers
                        </Button>
                      </div>
                    </div>
                    <div className="overflow-x-auto max-h-96 border rounded-lg">
                      <table className="data-table">
                        <thead className="sticky top-0 bg-white">
                          <tr>
                            <th>#</th>
                            <th>Date</th>
                            <th>Type</th>
                            <th>Name</th>
                            <th>Address</th>
                            <th>Consumer No</th>
                            <th>Gas Card</th>
                            <th>KYC</th>
                          </tr>
                        </thead>
                        <tbody>
                          {bulkPreview.slice(0, 20).map((c, idx) => (
                            <tr key={idx}>
                              <td>{idx + 1}</td>
                              <td>{c.date}</td>
                              <td>
                                <Badge variant={c.connection_type === 'domestic' ? 'default' : 'secondary'}>
                                  {c.connection_type}
                                </Badge>
                              </td>
                              <td className="font-medium">{c.customer_name}</td>
                              <td className="text-sm max-w-[150px] truncate">{c.address}</td>
                              <td>{c.consumer_no}</td>
                              <td>{c.gas_card_issued ? <CheckCircle className="w-4 h-4 text-green-600" /> : <XCircle className="w-4 h-4 text-slate-300" />}</td>
                              <td>{c.kyc_done ? <CheckCircle className="w-4 h-4 text-green-600" /> : <XCircle className="w-4 h-4 text-slate-300" />}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {bulkPreview.length > 20 && (
                        <div className="p-4 text-center text-sm text-slate-500 bg-slate-50">
                          Showing first 20 of {bulkPreview.length} customers
                        </div>
                      )}
                    </div>
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
              <DialogTitle>Edit Customer</DialogTitle>
              <DialogDescription>Update customer information</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Date</Label>
                  <Input 
                    type="date" 
                    value={editForm.date || ''}
                    onChange={(e) => setEditForm({ ...editForm, date: e.target.value })}
                    className="mt-1"
                    data-testid="edit-customer-date"
                  />
                </div>
                <div>
                  <Label>Connection Type</Label>
                  <Select 
                    value={editForm.connection_type || 'domestic'} 
                    onValueChange={(v) => setEditForm({ ...editForm, connection_type: v })}
                  >
                    <SelectTrigger className="mt-1" data-testid="edit-connection-type">
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
                <Label>Customer Name *</Label>
                <Input 
                  value={editForm.customer_name || ''}
                  onChange={(e) => setEditForm({ ...editForm, customer_name: e.target.value })}
                  className="mt-1"
                  data-testid="edit-customer-name"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Phone (10 digits)</Label>
                  <Input 
                    value={editForm.phone || ''}
                    onChange={(e) => {
                      const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                      setEditForm({ ...editForm, phone: value });
                    }}
                    placeholder="Enter 10 digit number"
                    maxLength={10}
                    className="mt-1"
                    data-testid="edit-customer-phone"
                  />
                  {editForm.phone && editForm.phone.length !== 10 && (
                    <p className="text-xs text-red-500 mt-1">Must be 10 digits ({editForm.phone.length}/10)</p>
                  )}
                </div>
                <div>
                  <Label>Consumer No (10 digits)</Label>
                  <Input 
                    value={editForm.consumer_no || ''}
                    onChange={(e) => {
                      const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                      setEditForm({ ...editForm, consumer_no: value });
                    }}
                    placeholder="Enter 10 digit number"
                    maxLength={10}
                    className="mt-1"
                    data-testid="edit-consumer-no"
                  />
                  {editForm.consumer_no && editForm.consumer_no.length !== 10 && (
                    <p className="text-xs text-red-500 mt-1">Must be 10 digits ({editForm.consumer_no.length}/10)</p>
                  )}
                </div>
              </div>
              <div>
                <Label>Address</Label>
                <Textarea 
                  value={editForm.address || ''}
                  onChange={(e) => setEditForm({ ...editForm, address: e.target.value })}
                  className="mt-1"
                  data-testid="edit-customer-address"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Cash Memo No</Label>
                  <Input 
                    value={editForm.cash_memo_no || ''}
                    onChange={(e) => setEditForm({ ...editForm, cash_memo_no: e.target.value })}
                    className="mt-1"
                    data-testid="edit-cash-memo-no"
                  />
                </div>
                <div>
                  <Label>Cylinder Nos</Label>
                  <Input 
                    value={editForm.cylinder_nos || ''}
                    onChange={(e) => setEditForm({ ...editForm, cylinder_nos: e.target.value })}
                    className="mt-1"
                    data-testid="edit-cylinder-nos"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex items-center space-x-3 p-4 bg-slate-50 rounded-lg">
                  <Checkbox 
                    id="edit_gas_card"
                    checked={editForm.gas_card_issued || false}
                    onCheckedChange={(checked) => setEditForm({ ...editForm, gas_card_issued: checked })}
                    data-testid="edit-gas-card-checkbox"
                  />
                  <Label htmlFor="edit_gas_card" className="cursor-pointer">Gas Card Issued</Label>
                </div>
                <div className="flex items-center space-x-3 p-4 bg-slate-50 rounded-lg">
                  <Checkbox 
                    id="edit_kyc"
                    checked={editForm.kyc_done || false}
                    onCheckedChange={(checked) => setEditForm({ ...editForm, kyc_done: checked })}
                    data-testid="edit-kyc-checkbox"
                  />
                  <Label htmlFor="edit_kyc" className="cursor-pointer">KYC Done</Label>
                </div>
              </div>
              <div>
                <Label>Remarks</Label>
                <Input 
                  value={editForm.remarks || ''}
                  onChange={(e) => setEditForm({ ...editForm, remarks: e.target.value })}
                  className="mt-1"
                  data-testid="edit-remarks"
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
                data-testid="save-edit-customer-btn"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                Save Changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-red-700">
                <AlertTriangle className="w-5 h-5" />
                Delete Customer
              </DialogTitle>
              <DialogDescription>
                Are you sure you want to delete <strong>{deletingCustomer?.customer_name}</strong>?
              </DialogDescription>
            </DialogHeader>
            <div className="py-4 space-y-3">
              {loadingLinked ? (
                <div className="flex items-center gap-2 text-slate-500">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Checking linked records...
                </div>
              ) : linkedRecords?.has_linked_records ? (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-1" data-testid="delete-warning-panel">
                  <p className="text-sm font-medium text-amber-800 flex items-center gap-1">
                    <AlertTriangle className="w-4 h-4" />
                    Warning: This customer has linked records
                  </p>
                  {linkedRecords.active_orders > 0 && (
                    <p className="text-sm text-amber-700">
                      {linkedRecords.active_orders} active/pending order(s)
                    </p>
                  )}
                  {linkedRecords.total_orders > 0 && (
                    <p className="text-sm text-amber-700">
                      {linkedRecords.total_orders} total order(s)
                    </p>
                  )}
                  {linkedRecords.sales_entries > 0 && (
                    <p className="text-sm text-amber-700">
                      {linkedRecords.sales_entries} sales entry/entries
                    </p>
                  )}
                  <p className="text-xs text-amber-600 mt-2">
                    Deleting this customer will not remove linked orders or sales entries, but they will lose the customer reference.
                  </p>
                </div>
              ) : (
                <p className="text-sm text-slate-600">
                  No linked orders or sales entries found. This customer can be safely deleted.
                </p>
              )}
              <p className="text-sm text-red-600 font-medium">
                This action cannot be undone.
              </p>
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" data-testid="cancel-delete-btn">Cancel</Button>
              </DialogClose>
              <Button 
                variant="destructive"
                onClick={handleDeleteConfirm}
                disabled={deleting}
                data-testid="confirm-delete-customer-btn"
              >
                {deleting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Trash2 className="w-4 h-4 mr-2" />}
                Delete Customer
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default CustomerManagement;
