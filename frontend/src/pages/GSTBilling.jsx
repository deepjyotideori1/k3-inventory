import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import Layout from '../components/Layout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription
} from '../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Textarea } from '../components/ui/textarea';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import {
  Receipt, Search, Plus, FileDown, FileSpreadsheet, Settings as SettingsIcon,
  Edit2, XCircle, Trash2, Eye, RefreshCw, ChevronLeft, ChevronRight, FileText, AlertCircle,
  Upload, History, AlertTriangle, CheckCircle2, Ban, Users, Warehouse, ChevronDown,
  User as UserIcon, Phone as PhoneIcon
} from 'lucide-react';
import {
  getGstInvoices, getGstSummary, getGstConfig, updateGstConfig,
  getGstItems, createGstItem, updateGstItem, deleteGstItem, activateGstItem,
  getGstPlans, createGstPlan, updateGstPlan, deleteGstPlan,
  listGstReports, getGstReport, exportGstReportExcel, exportGstReportPdf,
  createGstInvoice, updateGstInvoice, cancelGstInvoice, deleteGstInvoice,
  generateGstFromSale, downloadGstInvoicePdf, exportGstInvoicesExcel,
  getSalesEntries, getAccessorySales,
  downloadGstItemTemplate, bulkUploadGstItems,
  getGstItemHistory, downloadGstItemHistoryExcel,
  listGstDiscrepancies, reviewGstDiscrepancy,
  getPartyLedgerCustomers, getPartyLedger,
  getGstWarehouseSummary, exportGstWarehouseSummaryExcel, getWarehouses,
  gstCustomerLookup, repairGstInvoiceNumbers
} from '../lib/api';

const formatRs = (n) => {
  const num = Number(n) || 0;
  return 'Rs. ' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

// Convert Indian amount to words (e.g. 12345 -> "Rupees Twelve Thousand Three Hundred Forty Five Only")
const amountInWords = (amount) => {
  const num = Math.floor(Number(amount) || 0);
  const paise = Math.round(((Number(amount) || 0) - num) * 100);
  if (num === 0 && paise === 0) return 'Rupees Zero Only';
  const ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
    'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'];
  const tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];
  const twoDigit = (n) => {
    if (n < 20) return ones[n];
    return tens[Math.floor(n / 10)] + (n % 10 ? ' ' + ones[n % 10] : '');
  };
  const threeDigit = (n) => {
    const h = Math.floor(n / 100);
    const r = n % 100;
    return (h ? ones[h] + ' Hundred' + (r ? ' ' : '') : '') + (r ? twoDigit(r) : '');
  };
  const inWords = (n) => {
    if (n === 0) return '';
    if (n < 1000) return threeDigit(n);
    if (n < 100000) return twoDigit(Math.floor(n / 1000)) + ' Thousand' + (n % 1000 ? ' ' + threeDigit(n % 1000) : '');
    if (n < 10000000) return twoDigit(Math.floor(n / 100000)) + ' Lakh' + (n % 100000 ? ' ' + inWords(n % 100000) : '');
    return twoDigit(Math.floor(n / 10000000)) + ' Crore' + (n % 10000000 ? ' ' + inWords(n % 10000000) : '');
  };
  let words = 'Rupees ' + inWords(num);
  if (paise > 0) words += ' and ' + twoDigit(paise) + ' Paise';
  return words.trim().replace(/\s+/g, ' ') + ' Only';
};

const todayISO = () => new Date().toISOString().split('T')[0];
const monthStartISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
};

// Indian FY options: current FY + previous 4. FY is Apr-Mar; if month < 4 the FY started previous year.
const fyOptions = () => {
  const d = new Date();
  const startYr = d.getMonth() + 1 >= 4 ? d.getFullYear() : d.getFullYear() - 1;
  const opts = [];
  for (let i = 0; i < 5; i++) {
    const s = startYr - i;
    opts.push({ value: `${s}-${String((s + 1) % 100).padStart(2, '0')}`, label: `${s}-${String((s + 1) % 100).padStart(2, '0')}` });
  }
  return opts;
};

const MONTH_LABELS = [
  { v: '1', l: 'January' }, { v: '2', l: 'February' }, { v: '3', l: 'March' },
  { v: '4', l: 'April' }, { v: '5', l: 'May' }, { v: '6', l: 'June' },
  { v: '7', l: 'July' }, { v: '8', l: 'August' }, { v: '9', l: 'September' },
  { v: '10', l: 'October' }, { v: '11', l: 'November' }, { v: '12', l: 'December' },
];

const GSTBilling = () => {
  const { user, isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState('invoices');

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [billTypeFilter, setBillTypeFilter] = useState('all');
  const [startDate, setStartDate] = useState(monthStartISO());
  const [endDate, setEndDate] = useState(todayISO());
  const [monthFilter, setMonthFilter] = useState('all');    // 'all' or '1'..'12'
  const [fyFilter, setFyFilter] = useState('all');          // 'all' or e.g. '2026-27'
  const [paymentStatusFilter, setPaymentStatusFilter] = useState('all');  // 'all'|'Paid'|'Partial'|'Pending'
  const [page, setPage] = useState(1);

  // Data
  const [invoices, setInvoices] = useState([]);
  const [totalPages, setTotalPages] = useState(1);
  const [totalInvoices, setTotalInvoices] = useState(0);
  const [summary, setSummary] = useState({});
  const [items, setItems] = useState([]);
  const [plans, setPlans] = useState([]);
  const [config, setConfig] = useState({});
  const [loading, setLoading] = useState(false);

  // Dialogs
  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [showInvoiceDialog, setShowInvoiceDialog] = useState(false);
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [showGenerateDialog, setShowGenerateDialog] = useState(false);
  const [showItemDialog, setShowItemDialog] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [editingInvoice, setEditingInvoice] = useState(null);
  const [viewingInvoice, setViewingInvoice] = useState(null);
  const [cancelTarget, setCancelTarget] = useState(null);
  const [cancelReason, setCancelReason] = useState('');
  const [editingItem, setEditingItem] = useState(null);
  const [showPlanDialog, setShowPlanDialog] = useState(false);
  const [editingPlan, setEditingPlan] = useState(null);

  // Bulk upload + history
  const [showBulkUploadDialog, setShowBulkUploadDialog] = useState(false);
  const [bulkFile, setBulkFile] = useState(null);
  const [bulkEffectiveFrom, setBulkEffectiveFrom] = useState(todayISO());
  const [bulkUploading, setBulkUploading] = useState(false);
  const [bulkResult, setBulkResult] = useState(null);
  const [showHistoryDialog, setShowHistoryDialog] = useState(false);
  const [histItemId, setHistItemId] = useState('all');
  const [histStart, setHistStart] = useState('');
  const [histEnd, setHistEnd] = useState('');
  const [historyRows, setHistoryRows] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Discrepancies
  const [discrepancyRows, setDiscrepancyRows] = useState([]);
  const [discrepancySummary, setDiscrepancySummary] = useState({ total: 0, pending: 0, approved: 0, rejected: 0, corrected: 0, total_difference: 0 });
  const [discStatusFilter, setDiscStatusFilter] = useState('all');
  const [discLoading, setDiscLoading] = useState(false);
  const [showReviewDialog, setShowReviewDialog] = useState(false);
  const [reviewTarget, setReviewTarget] = useState(null);
  const [reviewAction, setReviewAction] = useState('approve');
  const [reviewNote, setReviewNote] = useState('');
  const [reviewing, setReviewing] = useState(false);
  // Discrepancy-reason dialog (triggered when create/update invoice returns 400)
  const [showDiscReasonDialog, setShowDiscReasonDialog] = useState(false);
  const [discReasonInfo, setDiscReasonInfo] = useState(null);   // { expected, actual, diff, payloadFn }
  const [discReasonInput, setDiscReasonInput] = useState('');
  const [discReasonSaving, setDiscReasonSaving] = useState(false);

  // Party Ledger
  const [ledgerCustomers, setLedgerCustomers] = useState([]);
  const [ledgerSearch, setLedgerSearch] = useState('');
  const [ledgerSelected, setLedgerSelected] = useState(null);  // {customer_name, customer_phone}
  const [ledgerPeriod, setLedgerPeriod] = useState('all');
  const [ledgerStartDate, setLedgerStartDate] = useState('');
  const [ledgerEndDate, setLedgerEndDate] = useState('');
  const [ledgerRows, setLedgerRows] = useState([]);
  const [ledgerTotals, setLedgerTotals] = useState({});
  const [ledgerLoading, setLedgerLoading] = useState(false);

  // Reports state
  const [reportsList, setReportsList] = useState([]);
  const [reportType, setReportType] = useState('daily_sales');
  const [reportData, setReportData] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportStart, setReportStart] = useState(monthStartISO());
  const [reportEnd, setReportEnd] = useState(todayISO());

  // Warehouses (multi-select filter + Warehouses tab)
  const [warehouses, setWarehouses] = useState([]);
  const [selectedWarehouseIds, setSelectedWarehouseIds] = useState([]);
  const [warehouseSummary, setWarehouseSummary] = useState({ rows: [], totals: {} });
  const [warehouseSummaryLoading, setWarehouseSummaryLoading] = useState(false);
  const warehouseIdsCsv = selectedWarehouseIds.length ? selectedWarehouseIds.join(',') : undefined;

  // Manual invoice form state
  const [invForm, setInvForm] = useState(null);
  // Customer Master picker (autocomplete in the invoice modal)
  const [custLookupQuery, setCustLookupQuery] = useState('');
  const [custLookupResults, setCustLookupResults] = useState([]);
  const [custLookupOpen, setCustLookupOpen] = useState(false);
  const [custLookupLoading, setCustLookupLoading] = useState(false);

  // Generate-from-sale state
  const [genSaleType, setGenSaleType] = useState('sales_entry');
  const [legacySales, setLegacySales] = useState([]);
  const [legacyLoading, setLegacyLoading] = useState(false);

  const redirectIfNotAdmin = useCallback(() => {
    if (user && !isAdmin) {
      toast.error('GST Billing is admin-only');
      return true;
    }
    return false;
  }, [user, isAdmin]);

  const loadInvoices = useCallback(async () => {
    if (redirectIfNotAdmin()) return;
    setLoading(true);
    try {
      const params = { page, limit: 50 };
      if (search) params.search = search;
      if (statusFilter !== 'all') params.status = statusFilter;
      if (billTypeFilter !== 'all') params.item_type = billTypeFilter;
      if (paymentStatusFilter !== 'all') params.payment_status = paymentStatusFilter;
      if (fyFilter !== 'all') {
        params.fy = fyFilter;
      } else if (monthFilter !== 'all') {
        const now = new Date();
        params.month = Number(monthFilter);
        params.year = now.getFullYear();
      } else {
        if (startDate) params.start_date = startDate;
        if (endDate) params.end_date = endDate;
      }
      if (warehouseIdsCsv) params.warehouse_ids = warehouseIdsCsv;
      const { data } = await getGstInvoices(params);
      setInvoices(data.invoices || []);
      setTotalPages(data.pages || 1);
      setTotalInvoices(data.total || 0);
    } catch (e) {
      toast.error('Failed to load invoices');
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, billTypeFilter, paymentStatusFilter, monthFilter, fyFilter, startDate, endDate, warehouseIdsCsv, redirectIfNotAdmin]);

  const loadSummary = useCallback(async () => {
    if (redirectIfNotAdmin()) return;
    try {
      const params = {};
      if (fyFilter !== 'all') {
        params.fy = fyFilter;
      } else if (monthFilter !== 'all') {
        const now = new Date();
        params.month = Number(monthFilter);
        params.year = now.getFullYear();
      } else {
        params.start_date = startDate;
        params.end_date = endDate;
      }
      if (paymentStatusFilter !== 'all') params.payment_status = paymentStatusFilter;
      if (billTypeFilter !== 'all') params.item_type = billTypeFilter;
      if (warehouseIdsCsv) params.warehouse_ids = warehouseIdsCsv;
      const { data } = await getGstSummary(params);
      setSummary(data || {});
    } catch (e) { /* swallow */ }
  }, [startDate, endDate, monthFilter, fyFilter, paymentStatusFilter, billTypeFilter, warehouseIdsCsv, redirectIfNotAdmin]);

  const loadConfig = useCallback(async () => {
    try {
      const { data } = await getGstConfig();
      setConfig(data || {});
    } catch (e) { /* swallow */ }
  }, []);

  const loadItems = useCallback(async () => {
    try {
      const { data } = await getGstItems();
      setItems(data || []);
    } catch (e) { /* swallow */ }
  }, []);

  const loadPlans = useCallback(async () => {
    try {
      const { data } = await getGstPlans();
      setPlans(data || []);
    } catch (e) { /* swallow */ }
  }, []);

  const loadReportsList = useCallback(async () => {
    try {
      const { data } = await listGstReports();
      setReportsList(data || []);
    } catch (e) { /* swallow */ }
  }, []);

  const loadWarehouses = useCallback(async () => {
    try {
      const { data } = await getWarehouses();
      setWarehouses(data || []);
    } catch (e) { /* swallow */ }
  }, []);

  const loadWarehouseSummary = useCallback(async () => {
    setWarehouseSummaryLoading(true);
    try {
      const params = { start_date: startDate, end_date: endDate };
      if (warehouseIdsCsv) params.warehouse_ids = warehouseIdsCsv;
      const { data } = await getGstWarehouseSummary(params);
      setWarehouseSummary(data || { rows: [], totals: {} });
    } catch (e) {
      toast.error('Failed to load warehouse summary');
    } finally {
      setWarehouseSummaryLoading(false);
    }
  }, [startDate, endDate, warehouseIdsCsv]);

  const handleWarehouseSummaryExcel = async () => {
    try {
      const params = { start_date: startDate, end_date: endDate };
      if (warehouseIdsCsv) params.warehouse_ids = warehouseIdsCsv;
      await exportGstWarehouseSummaryExcel(params);
      toast.success('Warehouse summary Excel downloaded');
    } catch (e) {
      toast.error('Excel export failed');
    }
  };

  const runReport = useCallback(async () => {
    if (!reportType) return;
    setReportLoading(true);
    try {
      const params = { start_date: reportStart, end_date: reportEnd };
      if (warehouseIdsCsv) params.warehouse_ids = warehouseIdsCsv;
      const { data } = await getGstReport(reportType, params);
      setReportData(data);
    } catch (e) {
      toast.error('Failed to load report');
      setReportData(null);
    } finally {
      setReportLoading(false);
    }
  }, [reportType, reportStart, reportEnd, warehouseIdsCsv]);

  const handleExportReportExcel = async () => {
    try {
      const label = reportData?.label || reportType;
      const params = { start_date: reportStart, end_date: reportEnd };
      if (warehouseIdsCsv) params.warehouse_ids = warehouseIdsCsv;
      await exportGstReportExcel(reportType, params, label);
      toast.success('Excel downloaded');
    } catch (e) {
      toast.error('Excel export failed');
    }
  };

  const handleExportReportPdf = async () => {
    try {
      const label = reportData?.label || reportType;
      const params = { start_date: reportStart, end_date: reportEnd };
      if (warehouseIdsCsv) params.warehouse_ids = warehouseIdsCsv;
      await exportGstReportPdf(reportType, params, label);
      toast.success('PDF downloaded');
    } catch (e) {
      toast.error('PDF export failed');
    }
  };

  useEffect(() => {
    loadInvoices();
    loadSummary();
  }, [loadInvoices, loadSummary]);

  // Discrepancy loader (defined early so the useEffect below can reference it)
  const loadDiscrepancies = useCallback(async () => {
    setDiscLoading(true);
    try {
      const params = {};
      if (discStatusFilter && discStatusFilter !== 'all') params.status = discStatusFilter;
      if (warehouseIdsCsv) params.warehouse_ids = warehouseIdsCsv;
      const res = await listGstDiscrepancies(params);
      const data = res?.data || res;
      setDiscrepancyRows(data.rows || []);
      setDiscrepancySummary(data.summary || { total: 0, pending: 0, approved: 0, rejected: 0, corrected: 0, total_difference: 0 });
    } catch (e) {
      toast.error('Failed to load discrepancies');
    } finally {
      setDiscLoading(false);
    }
  }, [discStatusFilter, warehouseIdsCsv]);

  const loadLedgerCustomers = useCallback(async () => {
    try {
      const params = {};
      if (warehouseIdsCsv) params.warehouse_ids = warehouseIdsCsv;
      const res = await getPartyLedgerCustomers(params);
      setLedgerCustomers(res?.data || res || []);
    } catch (e) {
      toast.error('Failed to load customers');
    }
  }, [warehouseIdsCsv]);

  const loadLedger = useCallback(async () => {
    if (!ledgerSelected) {
      setLedgerRows([]);
      setLedgerTotals({});
      return;
    }
    setLedgerLoading(true);
    try {
      const params = { period: ledgerPeriod };
      if (ledgerSelected.customer_phone) params.customer_phone = ledgerSelected.customer_phone;
      else params.customer_name = ledgerSelected.customer_name;
      if (ledgerPeriod === 'custom') {
        if (ledgerStartDate) params.start_date = ledgerStartDate;
        if (ledgerEndDate) params.end_date = ledgerEndDate;
      }
      if (warehouseIdsCsv) params.warehouse_ids = warehouseIdsCsv;
      const res = await getPartyLedger(params);
      const data = res?.data || res;
      setLedgerRows(data.rows || []);
      setLedgerTotals(data.totals || {});
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load ledger');
    } finally {
      setLedgerLoading(false);
    }
  }, [ledgerSelected, ledgerPeriod, ledgerStartDate, ledgerEndDate, warehouseIdsCsv]);

  useEffect(() => {
    loadConfig();
    loadItems();
    loadPlans();
    loadReportsList();
    loadWarehouses();
  }, [loadConfig, loadItems, loadPlans, loadReportsList, loadWarehouses]);

  // Auto-load warehouse summary when Warehouses tab is active OR filter/dates change
  useEffect(() => {
    if (activeTab === 'warehouses') {
      loadWarehouseSummary();
    }
  }, [activeTab, loadWarehouseSummary]);

  // Auto-run report when type/dates change AND user is on Reports tab
  useEffect(() => {
    if (activeTab === 'reports') {
      runReport();
    }
  }, [activeTab, runReport]);

  // Auto-load discrepancies when user opens the Discrepancies tab or changes filter
  useEffect(() => {
    if (activeTab === 'discrepancies') {
      loadDiscrepancies();
    }
  }, [activeTab, loadDiscrepancies]);

  // Auto-load ledger customers + ledger rows when the Party Ledger tab is active
  useEffect(() => {
    if (activeTab === 'ledger') {
      loadLedgerCustomers();
    }
  }, [activeTab, loadLedgerCustomers]);

  useEffect(() => {
    if (activeTab === 'ledger' && ledgerSelected) {
      loadLedger();
    }
  }, [activeTab, ledgerSelected, ledgerPeriod, ledgerStartDate, ledgerEndDate, loadLedger]);

  // ----- HANDLERS -----
  const handleCancel = async () => {
    if (!cancelTarget) return;
    try {
      await cancelGstInvoice(cancelTarget.id, cancelReason);
      toast.success('Invoice cancelled');
      setShowCancelDialog(false);
      setCancelReason('');
      setCancelTarget(null);
      loadInvoices();
      loadSummary();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to cancel');
    }
  };

  const handleDelete = async (inv) => {
    if (!window.confirm(`Permanently delete invoice ${inv.invoice_number}?`)) return;
    try {
      await deleteGstInvoice(inv.id);
      toast.success('Invoice deleted');
      loadInvoices();
      loadSummary();
    } catch (e) {
      toast.error('Failed to delete');
    }
  };

  const handlePdf = async (inv) => {
    try {
      await downloadGstInvoicePdf(inv.id, inv.invoice_number);
    } catch (e) {
      toast.error('PDF download failed');
    }
  };

  const handleExcelExport = async () => {
    try {
      const params = {
        search: search || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        item_type: billTypeFilter !== 'all' ? billTypeFilter : undefined,
        payment_status: paymentStatusFilter !== 'all' ? paymentStatusFilter : undefined,
        warehouse_ids: warehouseIdsCsv,
      };
      if (fyFilter !== 'all') {
        params.fy = fyFilter;
      } else if (monthFilter !== 'all') {
        const now = new Date();
        params.month = Number(monthFilter);
        params.year = now.getFullYear();
      } else {
        params.start_date = startDate;
        params.end_date = endDate;
      }
      await exportGstInvoicesExcel(params);
      toast.success('Excel downloaded');
    } catch (e) {
      toast.error('Excel export failed');
    }
  };

  const openInvoiceDialog = (inv = null) => {
    if (inv) {
      setEditingInvoice(inv);
      setInvForm({
        ...inv,
        line_items: inv.line_items?.length ? [...inv.line_items.map(li => ({ ...li }))] : [emptyLineItem()],
      });
    } else {
      setEditingInvoice(null);
      setInvForm({
        invoice_date: todayISO(),
        memo_no: '',
        customer_id: '',
        customer_name: '',
        customer_phone: '',
        customer_address: '',
        customer_gstin: '',
        customer_consumer_no: '',
        customer_connection_type: '',
        customer_source: 'manual',
        tax_mode: config.default_tax_mode || 'intra_state',
        payment_mode: 'cash',
        bill_type: 'manual',
        place_of_supply: config.place_of_supply || '',
        remarks: '',
        cash_received: 0,
        online_received: 0,
        line_items: [emptyLineItem()],
      });
    }
    setShowInvoiceDialog(true);
    // Reset customer picker state
    setCustLookupQuery('');
    setCustLookupResults([]);
    setCustLookupOpen(false);
  };

  // Debounced Customer Master search
  useEffect(() => {
    if (!showInvoiceDialog) return;
    const q = custLookupQuery.trim();
    if (q.length < 2) {
      setCustLookupResults([]);
      return;
    }
    let cancelled = false;
    setCustLookupLoading(true);
    const t = setTimeout(async () => {
      try {
        const { data } = await gstCustomerLookup({ q, limit: 15 });
        if (!cancelled) setCustLookupResults(data?.customers || []);
      } catch (e) {
        if (!cancelled) setCustLookupResults([]);
      } finally {
        if (!cancelled) setCustLookupLoading(false);
      }
    }, 300);
    return () => { cancelled = true; clearTimeout(t); };
  }, [custLookupQuery, showInvoiceDialog]);

  const applyCustomerFromMaster = (c) => {
    if (!c) return;
    setInvForm(prev => ({
      ...prev,
      customer_id: c.id || '',
      customer_name: c.customer_name || '',
      customer_phone: c.phone || '',
      customer_address: c.address || '',
      customer_consumer_no: c.consumer_no || '',
      customer_connection_type: (c.connection_type || '').toLowerCase(),
      customer_source: 'master',
    }));
    setCustLookupOpen(false);
    setCustLookupQuery('');
    setCustLookupResults([]);
    if (!c.phone) {
      toast.warning('Customer mobile number is not available in the Customer Database.');
    } else {
      toast.success(`Loaded ${c.customer_name} from Customer Master`);
    }
  };

  const clearCustomerLink = () => {
    setInvForm(prev => ({
      ...prev,
      customer_id: '',
      customer_source: 'manual',
    }));
  };

  const emptyLineItem = () => ({
    item_name: '',
    hsn: '',
    unit: 'Nos',
    quantity: 1,
    rate: 0,
    gst_rate: 18,
  });

  const updateLineItem = (idx, key, value) => {
    setInvForm(prev => {
      const li = [...prev.line_items];
      li[idx] = { ...li[idx], [key]: value };
      return { ...prev, line_items: li };
    });
  };

  const setLineItemFromMaster = (idx, itemId) => {
    const m = items.find(i => i.id === itemId);
    if (!m) return;
    setInvForm(prev => {
      const li = [...prev.line_items];
      li[idx] = {
        ...li[idx],
        item_id: m.id,
        item_name: m.name,
        hsn: m.hsn,
        unit: m.unit,
        gst_rate: m.gst_rate,
        rate: m.default_rate || li[idx].rate || 0,
      };
      return { ...prev, line_items: li };
    });
  };

  const addLineItem = () => {
    setInvForm(prev => ({ ...prev, line_items: [...prev.line_items, emptyLineItem()] }));
  };

  const removeLineItem = (idx) => {
    setInvForm(prev => ({
      ...prev,
      line_items: prev.line_items.length > 1 ? prev.line_items.filter((_, i) => i !== idx) : prev.line_items,
    }));
  };

  const computePreview = () => {
    if (!invForm) return { sub_total: 0, total_cgst: 0, total_sgst: 0, total_igst: 0, total_gst: 0, total_before_roundoff: 0, round_off: 0, grand_total: 0 };
    let sub = 0, cgst = 0, sgst = 0, igst = 0;
    invForm.line_items.forEach(li => {
      const qty = Number(li.quantity) || 0;
      const rate = Number(li.rate) || 0;
      const gst = Number(li.gst_rate) || 0;
      const tax = qty * rate;
      sub += tax;
      if (invForm.tax_mode === 'inter_state') {
        igst += tax * gst / 100;
      } else {
        cgst += tax * gst / 200;
        sgst += tax * gst / 200;
      }
    });
    const totalGst = cgst + sgst + igst;
    const totalBefore = Math.round((sub + totalGst) * 100) / 100;
    const grandTotal = Math.round(totalBefore);
    const roundOff = Math.round((grandTotal - totalBefore) * 100) / 100;
    return {
      sub_total: sub,
      total_cgst: cgst,
      total_sgst: sgst,
      total_igst: igst,
      total_gst: totalGst,
      total_before_roundoff: totalBefore,
      round_off: roundOff,
      grand_total: grandTotal,
    };
  };

  const _saveInvoicePayload = async (payload) => {
    if (editingInvoice) {
      await updateGstInvoice(editingInvoice.id, payload);
      toast.success('Invoice updated');
    } else {
      await createGstInvoice(payload);
      toast.success(payload.discrepancy_reason ? 'Invoice saved as Discrepancy (pending review)' : 'Invoice created');
    }
    setShowInvoiceDialog(false);
    setInvForm(null);
    setEditingInvoice(null);
    loadInvoices();
    loadSummary();
  };

  const handleSaveInvoice = async () => {
    if (!invForm) return;
    if (!invForm.customer_name?.trim()) {
      toast.error('Customer name required');
      return;
    }
    if (!invForm.line_items?.length || invForm.line_items.some(li => !li.item_name || !Number(li.quantity) || !Number(li.rate))) {
      toast.error('All line items need item name, quantity, and rate');
      return;
    }
    try {
      await _saveInvoicePayload(invForm);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      // Backend returned discrepancy 400 — open reason dialog
      if (detail && typeof detail === 'object' && detail.code === 'discrepancy_requires_reason') {
        setDiscReasonInfo({
          expected: detail.expected_amount,
          actual: detail.actual_amount,
          diff: detail.discrepancy_amount,
          retry: (reason) => _saveInvoicePayload({ ...invForm, discrepancy_reason: reason }),
        });
        setDiscReasonInput('');
        setShowDiscReasonDialog(true);
        return;
      }
      toast.error(typeof detail === 'string' ? detail : 'Failed to save invoice');
    }
  };

  const handleConfirmDiscrepancyReason = async () => {
    if (!discReasonInput.trim()) {
      toast.error('Reason is required to save a discrepancy invoice');
      return;
    }
    if (!discReasonInfo?.retry) return;
    setDiscReasonSaving(true);
    try {
      await discReasonInfo.retry(discReasonInput.trim());
      setShowDiscReasonDialog(false);
      setDiscReasonInfo(null);
      setDiscReasonInput('');
    } catch (e) {
      toast.error(e?.response?.data?.detail?.message || e?.response?.data?.detail || 'Failed to save with reason');
    } finally {
      setDiscReasonSaving(false);
    }
  };

  const handleSaveConfig = async () => {
    try {
      await updateGstConfig({
        prefix: config.prefix,
        suffix: config.suffix,
        default_tax_mode: config.default_tax_mode,
        place_of_supply: config.place_of_supply,
        auto_generate: !!config.auto_generate,
        company_name: config.company_name,
        company_tagline: config.company_tagline,
        company_address: config.company_address,
        company_gstin: config.company_gstin,
        company_state: config.company_state,
        company_state_code: config.company_state_code,
        company_phone: config.company_phone,
        company_email: config.company_email,
        company_logo_url: config.company_logo_url,
        bank_name: config.bank_name,
        bank_account_no: config.bank_account_no,
        bank_ifsc: config.bank_ifsc,
        bank_branch: config.bank_branch,
        bank_account_holder: config.bank_account_holder,
        terms_conditions: config.terms_conditions,
        signatory_name: config.signatory_name,
        signatory_designation: config.signatory_designation,
      });
      toast.success('Settings saved');
      setShowConfigDialog(false);
      loadConfig();
    } catch (e) {
      toast.error('Failed to save settings');
    }
  };

  // -- Generate from sale --
  const loadLegacySales = useCallback(async () => {
    setLegacyLoading(true);
    try {
      if (genSaleType === 'sales_entry') {
        const { data } = await getSalesEntries({ start_date: startDate, end_date: endDate, limit: 100 });
        setLegacySales(data.entries || []);
      } else {
        const { data } = await getAccessorySales({ start_date: startDate, end_date: endDate });
        setLegacySales((data || []).map(s => ({
          id: s.id,
          date: s.date,
          consumer_name: s.customer_name,
          memo_no: s.memo_no,
          amount: s.grand_total,
          connection_type: 'accessory',
        })));
      }
    } catch (e) {
      toast.error('Failed to load sales');
    } finally {
      setLegacyLoading(false);
    }
  }, [genSaleType, startDate, endDate]);

  useEffect(() => {
    if (showGenerateDialog) loadLegacySales();
  }, [showGenerateDialog, loadLegacySales]);

  const handleGenerateFromSale = async (sale) => {
    try {
      await generateGstFromSale(genSaleType, sale.id);
      toast.success(`Invoice generated for ${sale.consumer_name || 'sale'}`);
      loadInvoices();
      loadSummary();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Generation failed');
    }
  };

  // ---- Item Master ----
  const handleSaveItem = async () => {
    if (!editingItem?.name) {
      toast.error('Item name required');
      return;
    }
    try {
      if (editingItem.id) {
        await updateGstItem(editingItem.id, editingItem);
        toast.success('Item updated');
      } else {
        await createGstItem(editingItem);
        toast.success('Item created');
      }
      setShowItemDialog(false);
      setEditingItem(null);
      loadItems();
    } catch (e) {
      toast.error('Failed to save item');
    }
  };

  const handleDeleteItem = async (item) => {
    if (!window.confirm(`Deactivate "${item.name}"?\n\nIt will be hidden from new plan items and invoice dropdowns, but existing plans and historical invoices that already use it will remain unchanged.`)) return;
    try {
      await deleteGstItem(item.id);
      toast.success(`"${item.name}" deactivated`);
      loadItems();
      loadPlans(); // plans may reflect the change visually
    } catch (e) {
      toast.error('Failed to deactivate');
    }
  };

  const handleActivateItem = async (item) => {
    try {
      await activateGstItem(item.id);
      toast.success(`"${item.name}" reactivated`);
      loadItems();
    } catch (e) {
      toast.error('Failed to reactivate');
    }
  };

  // ---- Bulk Update / Rate History ----
  const handleDownloadTemplate = async () => {
    try {
      await downloadGstItemTemplate();
      toast.success('Template downloaded');
    } catch (e) {
      toast.error('Failed to download template');
    }
  };

  const handleBulkUpload = async () => {
    if (!bulkFile) {
      toast.error('Pick an Excel or CSV file');
      return;
    }
    setBulkUploading(true);
    setBulkResult(null);
    try {
      const fd = new FormData();
      fd.append('file', bulkFile);
      fd.append('effective_from', bulkEffectiveFrom || '');
      const res = await bulkUploadGstItems(fd);
      const data = res?.data || res;
      setBulkResult(data);
      toast.success(`Bulk done — Created: ${data.created}, Updated: ${data.updated}, Skipped: ${data.skipped}`);
      loadItems();
      loadPlans();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Bulk upload failed');
    } finally {
      setBulkUploading(false);
    }
  };

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const params = {};
      if (histItemId && histItemId !== 'all') params.item_id = histItemId;
      if (histStart) params.start_date = histStart;
      if (histEnd) params.end_date = histEnd;
      const res = await getGstItemHistory(params);
      const rows = res?.data?.rows || res?.rows || [];
      setHistoryRows(rows);
    } catch (e) {
      toast.error('Failed to load history');
    } finally {
      setHistoryLoading(false);
    }
  }, [histItemId, histStart, histEnd]);

  const handleDownloadHistoryExcel = async () => {
    try {
      const params = {};
      if (histItemId && histItemId !== 'all') params.item_id = histItemId;
      if (histStart) params.start_date = histStart;
      if (histEnd) params.end_date = histEnd;
      await downloadGstItemHistoryExcel(params);
      toast.success('History downloaded');
    } catch (e) {
      toast.error('Failed to download history');
    }
  };

  const openHistoryDialog = () => {
    setShowHistoryDialog(true);
    setHistItemId('all');
    setHistStart('');
    setHistEnd('');
    setHistoryRows([]);
    // initial load with no filters
    setTimeout(() => loadHistory(), 50);
  };

  // ---- Discrepancy review ----

  const openReviewDialog = (row, action) => {
    setReviewTarget(row);
    setReviewAction(action);
    setReviewNote('');
    setShowReviewDialog(true);
  };

  const handleSubmitReview = async () => {
    if (!reviewTarget) return;
    if (reviewAction === 'reject' && !reviewNote.trim()) {
      toast.error('A note is required when rejecting');
      return;
    }
    setReviewing(true);
    try {
      await reviewGstDiscrepancy(reviewTarget.id, reviewAction, reviewNote.trim());
      toast.success(`Discrepancy ${reviewAction === 'approve' ? 'approved' : 'rejected'}`);
      setShowReviewDialog(false);
      setReviewTarget(null);
      setReviewNote('');
      loadDiscrepancies();
      loadInvoices();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to submit review');
    } finally {
      setReviewing(false);
    }
  };

  // ---- Connection Plans ----
  const handleSavePlan = async () => {
    if (!editingPlan?.name) {
      toast.error('Plan name required');
      return;
    }
    if (!editingPlan.items?.length) {
      toast.error('At least one item required');
      return;
    }
    try {
      if (editingPlan.id) {
        await updateGstPlan(editingPlan.id, editingPlan);
        toast.success('Plan updated');
      } else {
        await createGstPlan(editingPlan);
        toast.success('Plan created');
      }
      setShowPlanDialog(false);
      setEditingPlan(null);
      loadPlans();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to save plan');
    }
  };

  const handleDeletePlan = async (plan) => {
    if (!window.confirm(`Deactivate ${plan.name}?`)) return;
    try {
      await deleteGstPlan(plan.id);
      toast.success('Plan deactivated');
      loadPlans();
    } catch (e) {
      toast.error('Failed to deactivate');
    }
  };

  const loadInvoiceFromPlan = (planId) => {
    const p = plans.find(pl => pl.id === planId);
    if (!p) return;
    const newLines = p.items.map(it => ({
      item_name: it.item_name,
      hsn: it.hsn,
      unit: it.unit,
      quantity: Number(it.quantity) || 1,
      rate: Number(it.unit_price) || 0,
      gst_rate: Number(it.gst_rate) || 0,
    }));
    setInvForm(prev => ({
      ...prev,
      line_items: newLines,
      bill_type: 'new_connection',
      remarks: prev?.remarks || `Connection Plan: ${p.name}`,
    }));
    toast.success(`Loaded ${newLines.length} items from "${p.name}"`);
  };

  const updatePlanItem = (idx, key, value) => {
    setEditingPlan(prev => {
      const items = [...prev.items];
      items[idx] = { ...items[idx], [key]: value };
      return { ...prev, items };
    });
  };

  // Auto-sync from Item Master: when admin picks a master item, fill name/hsn/unit/gst_rate (locked)
  const selectMasterForPlanItem = (idx, masterId) => {
    const m = items.find(i => i.id === masterId);
    if (!m) return;
    setEditingPlan(prev => {
      const list = [...prev.items];
      list[idx] = {
        ...list[idx],
        item_id: m.id,
        item_name: m.name,
        hsn: m.hsn || '',
        unit: m.unit || 'Nos',
        gst_rate: Number(m.gst_rate) || 0,
        // Keep unit_price as-is (admin sets per plan) but default to master default_rate if blank
        unit_price: Number(list[idx].unit_price) > 0 ? list[idx].unit_price : (Number(m.default_rate) || 0),
      };
      return { ...prev, items: list };
    });
  };

  const addPlanItem = () => {
    setEditingPlan(prev => ({
      ...prev,
      items: [...(prev.items || []), { item_id: null, item_name: '', hsn: '', unit: 'Nos', quantity: 1, gst_rate: 18, unit_price: 0 }],
    }));
  };

  const removePlanItem = (idx) => {
    setEditingPlan(prev => ({
      ...prev,
      items: prev.items.length > 1 ? prev.items.filter((_, i) => i !== idx) : prev.items,
    }));
  };

  if (!isAdmin) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Card className="max-w-md">
            <CardContent className="p-8 text-center">
              <AlertCircle className="w-12 h-12 mx-auto text-amber-500 mb-3" />
              <h2 className="text-lg font-semibold mb-2">Admin Access Required</h2>
              <p className="text-sm text-slate-600">GST Billing Dashboard is restricted to administrators.</p>
            </CardContent>
          </Card>
        </div>
      </Layout>
    );
  }

  const preview = computePreview();

  // ----- Warehouse Filter (multi-select checkbox dropdown) -----
  const toggleWarehouseId = (wid) => {
    setSelectedWarehouseIds(prev => prev.includes(wid) ? prev.filter(x => x !== wid) : [...prev, wid]);
    setPage(1);
  };
  const clearWarehouseSelection = () => { setSelectedWarehouseIds([]); setPage(1); };
  const warehouseFilterLabel = selectedWarehouseIds.length === 0
    ? 'All Warehouses'
    : selectedWarehouseIds.length === 1
      ? (warehouses.find(w => w.id === selectedWarehouseIds[0])?.name || '1 selected')
      : `${selectedWarehouseIds.length} warehouses selected`;

  const WarehouseFilter = (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className="justify-between gap-2 min-w-[220px]"
          data-testid="warehouse-filter-trigger"
        >
          <span className="flex items-center gap-2 truncate">
            <Warehouse className="w-4 h-4 text-blue-700" />
            <span className="truncate">{warehouseFilterLabel}</span>
          </span>
          <ChevronDown className="w-4 h-4 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 p-0">
        <div className="flex items-center justify-between px-3 py-2 border-b">
          <span className="text-sm font-medium">Filter by Warehouse</span>
          {selectedWarehouseIds.length > 0 && (
            <button
              type="button"
              onClick={clearWarehouseSelection}
              className="text-xs text-blue-700 hover:underline"
              data-testid="warehouse-filter-clear"
            >
              Clear
            </button>
          )}
        </div>
        <div className="max-h-64 overflow-y-auto py-1">
          {warehouses.length === 0 && (
            <div className="px-3 py-4 text-xs text-slate-500">No warehouses found.</div>
          )}
          {warehouses.map(w => {
            const checked = selectedWarehouseIds.includes(w.id);
            return (
              <label
                key={w.id}
                className="flex items-start gap-2 px-3 py-2 hover:bg-slate-50 cursor-pointer"
                data-testid={`warehouse-filter-item-${w.id}`}
              >
                <Checkbox
                  checked={checked}
                  onCheckedChange={() => toggleWarehouseId(w.id)}
                  className="mt-0.5"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">
                    {w.name}{w.code ? ` (${w.code})` : ''}
                  </div>
                  <div className="text-[10px] text-slate-500 truncate">
                    {w.location || '—'}{w.is_plant ? ' · Plant' : ''}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
        <div className="px-3 py-2 border-t text-[11px] text-slate-500">
          Empty selection = show all warehouses in your scope.
        </div>
      </PopoverContent>
    </Popover>
  );

  return (
    <Layout>
      <div className="space-y-6" data-testid="gst-billing-page">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
              <Receipt className="w-6 h-6 text-blue-700" />
              GST Billing Dashboard
            </h1>
            <p className="text-sm text-slate-500">Auto-generated tax invoices for new sales. Manual control for legacy entries.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {WarehouseFilter}
            <Button variant="outline" onClick={() => { loadInvoices(); loadSummary(); }} data-testid="refresh-btn">
              <RefreshCw className="w-4 h-4 mr-1" /> Refresh
            </Button>
            <Button variant="outline" onClick={() => setShowGenerateDialog(true)} data-testid="generate-from-sale-btn">
              <FileText className="w-4 h-4 mr-1" /> Generate from Sale
            </Button>
            <Button variant="outline" onClick={() => setShowConfigDialog(true)} data-testid="settings-btn">
              <SettingsIcon className="w-4 h-4 mr-1" /> Settings
            </Button>
            <Button onClick={() => openInvoiceDialog(null)} className="bg-blue-700 hover:bg-blue-800" data-testid="new-invoice-btn">
              <Plus className="w-4 h-4 mr-1" /> New Invoice
            </Button>
          </div>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card data-testid="summary-total-invoices">
            <CardContent className="p-4">
              <p className="text-xs uppercase text-slate-500">Total Invoices</p>
              <p className="text-2xl font-bold text-slate-800">{summary.total_invoices || 0}</p>
            </CardContent>
          </Card>
          <Card data-testid="summary-active">
            <CardContent className="p-4">
              <p className="text-xs uppercase text-slate-500">Active</p>
              <p className="text-2xl font-bold text-green-700">{summary.active?.count || 0}</p>
            </CardContent>
          </Card>
          <Card data-testid="summary-cancelled">
            <CardContent className="p-4">
              <p className="text-xs uppercase text-slate-500">Cancelled</p>
              <p className="text-2xl font-bold text-red-600">{summary.cancelled?.count || 0}</p>
            </CardContent>
          </Card>
          <Card data-testid="summary-total-gst">
            <CardContent className="p-4">
              <p className="text-xs uppercase text-slate-500">Total GST Collected</p>
              <p className="text-xl font-bold text-blue-700">{formatRs(summary.total_gst_collected || 0)}</p>
              <p className="text-xs text-slate-500 mt-1">Sales: {formatRs(summary.total_amount || 0)}</p>
            </CardContent>
          </Card>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="invoices" data-testid="tab-invoices">Invoices</TabsTrigger>
            <TabsTrigger value="warehouses" data-testid="tab-warehouses">Warehouses</TabsTrigger>
            <TabsTrigger value="discrepancies" data-testid="tab-discrepancies">Discrepancies</TabsTrigger>
            <TabsTrigger value="ledger" data-testid="tab-ledger">Party Ledger</TabsTrigger>
            <TabsTrigger value="reports" data-testid="tab-reports">Reports</TabsTrigger>
            <TabsTrigger value="plans" data-testid="tab-plans">Connection Plans</TabsTrigger>
            <TabsTrigger value="items" data-testid="tab-items">Item Master</TabsTrigger>
          </TabsList>

          {/* INVOICES TAB */}
          <TabsContent value="invoices" className="space-y-4">
            {/* Filters */}
            <Card>
              <CardContent className="p-4">
                <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
                  <div className="md:col-span-2 relative">
                    <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <Input
                      placeholder="Search invoice no, memo no, customer, phone..."
                      value={search}
                      onChange={e => { setSearch(e.target.value); setPage(1); }}
                      className="pl-9"
                      data-testid="search-input"
                    />
                  </div>
                  {/* Warehouse (per-tab) — shares state with the header filter */}
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button
                        variant="outline"
                        className="justify-between gap-2 font-normal"
                        data-testid="invoice-warehouse-filter"
                      >
                        <span className="flex items-center gap-2 truncate">
                          <Warehouse className="w-4 h-4 text-blue-700 shrink-0" />
                          <span className="truncate">{warehouseFilterLabel}</span>
                        </span>
                        <ChevronDown className="w-4 h-4 opacity-60 shrink-0" />
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent align="start" className="w-72 p-0">
                      <div className="flex items-center justify-between px-3 py-2 border-b">
                        <span className="text-sm font-medium">Warehouse</span>
                        {selectedWarehouseIds.length > 0 && (
                          <button
                            type="button"
                            onClick={clearWarehouseSelection}
                            className="text-xs text-blue-700 hover:underline"
                            data-testid="invoice-warehouse-clear"
                          >
                            Clear
                          </button>
                        )}
                      </div>
                      <div className="max-h-64 overflow-y-auto py-1">
                        {warehouses.length === 0 && (
                          <div className="px-3 py-4 text-xs text-slate-500">No warehouses found.</div>
                        )}
                        {warehouses.map(w => {
                          const checked = selectedWarehouseIds.includes(w.id);
                          return (
                            <label
                              key={w.id}
                              className="flex items-start gap-2 px-3 py-2 hover:bg-slate-50 cursor-pointer"
                              data-testid={`invoice-warehouse-item-${w.id}`}
                            >
                              <Checkbox
                                checked={checked}
                                onCheckedChange={() => toggleWarehouseId(w.id)}
                                className="mt-0.5"
                              />
                              <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium truncate">
                                  {w.name}{w.code ? ` (${w.code})` : ''}
                                </div>
                                <div className="text-[10px] text-slate-500 truncate">
                                  {w.location || '—'}{w.is_plant ? ' · Plant' : ''}
                                </div>
                              </div>
                            </label>
                          );
                        })}
                      </div>
                      <div className="px-3 py-2 border-t text-[11px] text-slate-500">
                        Empty selection = all warehouses.
                      </div>
                    </PopoverContent>
                  </Popover>
                  <Select value={statusFilter} onValueChange={v => { setStatusFilter(v); setPage(1); }}>
                    <SelectTrigger data-testid="status-filter"><SelectValue placeholder="Status" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="cancelled">Cancelled</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={paymentStatusFilter} onValueChange={v => { setPaymentStatusFilter(v); setPage(1); }}>
                    <SelectTrigger data-testid="payment-status-filter"><SelectValue placeholder="Payment" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Payments</SelectItem>
                      <SelectItem value="Paid">Paid</SelectItem>
                      <SelectItem value="Partial">Partial</SelectItem>
                      <SelectItem value="Pending">Pending</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={billTypeFilter} onValueChange={v => { setBillTypeFilter(v); setPage(1); }}>
                    <SelectTrigger data-testid="bill-type-filter"><SelectValue placeholder="Type" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Types</SelectItem>
                      <SelectItem value="new_connection">New Connection</SelectItem>
                      <SelectItem value="refill">Refill</SelectItem>
                      <SelectItem value="accessory">Accessory</SelectItem>
                      <SelectItem value="manual">Manual</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-6 gap-3 mt-3">
                  <Select value={fyFilter} onValueChange={v => { setFyFilter(v); if (v !== 'all') setMonthFilter('all'); setPage(1); }}>
                    <SelectTrigger data-testid="fy-filter"><SelectValue placeholder="Financial Year" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All FYs</SelectItem>
                      {fyOptions().map(o => (
                        <SelectItem key={o.value} value={o.value}>FY {o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={monthFilter} onValueChange={v => { setMonthFilter(v); if (v !== 'all') setFyFilter('all'); setPage(1); }}>
                    <SelectTrigger data-testid="month-filter"><SelectValue placeholder="Month" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Months</SelectItem>
                      {MONTH_LABELS.map(m => (
                        <SelectItem key={m.v} value={m.v}>{m.l}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input
                    type="date"
                    value={startDate}
                    onChange={e => { setStartDate(e.target.value); setMonthFilter('all'); setFyFilter('all'); setPage(1); }}
                    data-testid="start-date"
                    disabled={monthFilter !== 'all' || fyFilter !== 'all'}
                  />
                  <Input
                    type="date"
                    value={endDate}
                    onChange={e => { setEndDate(e.target.value); setMonthFilter('all'); setFyFilter('all'); setPage(1); }}
                    data-testid="end-date"
                    disabled={monthFilter !== 'all' || fyFilter !== 'all'}
                  />
                  <div className="md:col-span-2 flex justify-end items-center gap-2">
                    {(monthFilter !== 'all' || fyFilter !== 'all' || paymentStatusFilter !== 'all' || selectedWarehouseIds.length > 0 || search) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setMonthFilter('all');
                          setFyFilter('all');
                          setPaymentStatusFilter('all');
                          setBillTypeFilter('all');
                          setStatusFilter('all');
                          setSearch('');
                          setSelectedWarehouseIds([]);
                          setStartDate(monthStartISO());
                          setEndDate(todayISO());
                          setPage(1);
                        }}
                        data-testid="reset-filters-btn"
                      >
                        <XCircle className="w-4 h-4 mr-1" /> Reset
                      </Button>
                    )}
                    <Button variant="outline" onClick={handleExcelExport} data-testid="export-excel-btn">
                      <FileSpreadsheet className="w-4 h-4 mr-1" /> Export Excel
                    </Button>
                  </div>
                </div>

                <div className="mt-2 text-xs text-slate-500" data-testid="invoice-results-count">
                  Showing <strong>{invoices.length}</strong> of <strong>{totalInvoices}</strong> invoice{totalInvoices !== 1 ? 's' : ''}
                  {selectedWarehouseIds.length > 0 && (
                    <> · Warehouse: <strong>{warehouseFilterLabel}</strong></>
                  )}
                  {fyFilter !== 'all' && <> · FY <strong>{fyFilter}</strong></>}
                  {monthFilter !== 'all' && <> · Month: <strong>{MONTH_LABELS.find(m => m.v === monthFilter)?.l}</strong></>}
                  {paymentStatusFilter !== 'all' && <> · Payment: <strong>{paymentStatusFilter}</strong></>}
                </div>
              </CardContent>
            </Card>

            {/* Table */}
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b">
                      <tr>
                        <th className="text-left p-3 font-medium">Invoice No.</th>
                        <th className="text-left p-3 font-medium">Memo No.</th>
                        <th className="text-left p-3 font-medium">Date</th>
                        <th className="text-left p-3 font-medium">Customer</th>
                        <th className="text-left p-3 font-medium">Type</th>
                        <th className="text-right p-3 font-medium">Sub Total</th>
                        <th className="text-right p-3 font-medium">GST</th>
                        <th className="text-right p-3 font-medium">Total</th>
                        <th className="text-center p-3 font-medium">Payment</th>
                        <th className="text-center p-3 font-medium">Status</th>
                        <th className="text-center p-3 font-medium">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {!loading && invoices.length > 0 && invoices.map(inv => (
                        <tr key={inv.id} className={`border-b hover:bg-slate-50 ${inv.status === 'cancelled' ? 'opacity-60' : ''}`} data-testid={`invoice-row-${inv.id}`}>
                          <td className="p-3 font-mono text-xs">{inv.invoice_number}</td>
                          <td className="p-3 font-mono text-xs text-slate-600" data-testid={`memo-${inv.id}`}>{inv.memo_no || inv.invoice_number}</td>
                          <td className="p-3">{inv.invoice_date}</td>
                          <td className="p-3">
                            <div className="font-medium">{inv.customer_name}</div>
                            <div className="text-xs text-slate-500">{inv.customer_phone}</div>
                          </td>
                          <td className="p-3">
                            <div className="flex items-center gap-1 flex-wrap">
                              <Badge variant="outline">{(inv.bill_type || '-').replace('_', ' ')}</Badge>
                              {inv.is_discrepancy && (
                                <Badge
                                  className={
                                    inv.discrepancy_status === 'approved' ? 'bg-green-100 text-green-700' :
                                    inv.discrepancy_status === 'rejected' ? 'bg-red-100 text-red-700' :
                                    inv.discrepancy_status === 'corrected' ? 'bg-blue-100 text-blue-700' :
                                    'bg-amber-100 text-amber-700'
                                  }
                                  title={`Discrepancy: ${inv.discrepancy_reason || ''} | Diff: ${inv.discrepancy_amount}`}
                                  data-testid={`disc-badge-${inv.id}`}
                                >
                                  <AlertTriangle className="w-3 h-3 mr-0.5" /> Discrepancy
                                </Badge>
                              )}
                            </div>
                          </td>
                          <td className="p-3 text-right">{formatRs(inv.sub_total)}</td>
                          <td className="p-3 text-right text-blue-700">{formatRs(inv.total_gst)}</td>
                          <td className="p-3 text-right font-semibold">{formatRs(inv.grand_total)}</td>
                          <td className="p-3 text-center" data-testid={`payment-status-${inv.id}`}>
                            {inv.payment_status === 'Paid' && <Badge className="bg-green-100 text-green-700">Paid</Badge>}
                            {inv.payment_status === 'Partial' && (
                              <Badge className="bg-amber-100 text-amber-700" title={`Pending ₹${Number(inv.pending_amount || 0).toFixed(2)}`}>Partial</Badge>
                            )}
                            {inv.payment_status === 'Pending' && (
                              <Badge className="bg-red-100 text-red-700" title={`Pending ₹${Number(inv.pending_amount || 0).toFixed(2)}`}>Pending</Badge>
                            )}
                            {!inv.payment_status && <Badge variant="outline">—</Badge>}
                          </td>
                          <td className="p-3 text-center">
                            {inv.status === 'cancelled'
                              ? <Badge className="bg-red-100 text-red-700">Cancelled</Badge>
                              : <Badge className="bg-green-100 text-green-700">Active</Badge>}
                          </td>
                          <td className="p-3">
                            <div className="flex justify-center gap-1">
                              <Button size="icon" variant="ghost" title="View" onClick={() => { setViewingInvoice(inv); setShowViewDialog(true); }} data-testid={`view-${inv.id}`}>
                                <Eye className="w-4 h-4" />
                              </Button>
                              <Button size="icon" variant="ghost" title="PDF" onClick={() => handlePdf(inv)} data-testid={`pdf-${inv.id}`}>
                                <FileDown className="w-4 h-4" />
                              </Button>
                              {inv.status === 'active' && (
                                <>
                                  <Button size="icon" variant="ghost" title="Edit" onClick={() => openInvoiceDialog(inv)} data-testid={`edit-${inv.id}`}>
                                    <Edit2 className="w-4 h-4" />
                                  </Button>
                                  <Button size="icon" variant="ghost" title="Cancel" onClick={() => { setCancelTarget(inv); setShowCancelDialog(true); }} data-testid={`cancel-${inv.id}`}>
                                    <XCircle className="w-4 h-4 text-red-600" />
                                  </Button>
                                </>
                              )}
                              <Button size="icon" variant="ghost" title="Delete" onClick={() => handleDelete(inv)} data-testid={`delete-${inv.id}`}>
                                <Trash2 className="w-4 h-4 text-red-600" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {loading && (
                    <div className="p-8 text-center text-slate-500" data-testid="invoices-loading">Loading...</div>
                  )}
                  {!loading && invoices.length === 0 && (
                    <div className="p-8 text-center text-slate-500" data-testid="invoices-empty">No invoices found.</div>
                  )}
                </div>
                {/* Pagination */}
                <div className="flex items-center justify-between p-3 border-t">
                  <span className="text-xs text-slate-500">
                    Page {page} of {totalPages} · {totalInvoices} invoices
                  </span>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage(p => p - 1)}>
                      <ChevronLeft className="w-4 h-4" /> Prev
                    </Button>
                    <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
                      Next <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* WAREHOUSES TAB */}
          <TabsContent value="warehouses" className="space-y-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-2">
                  <Warehouse className="w-5 h-5 text-blue-700" />
                  <div>
                    <CardTitle className="text-base">Warehouse-wise Summary</CardTitle>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Per-warehouse KPIs for the selected date range. Use the header filter to focus on one or more warehouses.
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <div>
                    <Label className="text-[10px]">From</Label>
                    <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="h-8 text-xs" data-testid="wh-start-date" />
                  </div>
                  <div>
                    <Label className="text-[10px]">To</Label>
                    <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="h-8 text-xs" data-testid="wh-end-date" />
                  </div>
                  <Button size="sm" variant="outline" onClick={loadWarehouseSummary} disabled={warehouseSummaryLoading} data-testid="wh-refresh-btn">
                    <RefreshCw className={`w-4 h-4 mr-1 ${warehouseSummaryLoading ? 'animate-spin' : ''}`} />
                    Refresh
                  </Button>
                  <Button size="sm" onClick={handleWarehouseSummaryExcel} className="bg-emerald-700 hover:bg-emerald-800" data-testid="wh-excel-btn">
                    <FileSpreadsheet className="w-4 h-4 mr-1" /> Download Excel
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {warehouseSummaryLoading && (
                  <div className="p-6 text-center text-slate-500" data-testid="wh-loading">Loading warehouse summary…</div>
                )}
                {!warehouseSummaryLoading && (warehouseSummary.rows || []).length === 0 && (
                  <div className="p-6 text-center text-slate-500" data-testid="wh-empty">
                    No warehouse data for the selected period.
                  </div>
                )}
                {!warehouseSummaryLoading && (warehouseSummary.rows || []).length > 0 && (
                  <>
                    {/* Grand totals strip */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2" data-testid="wh-grand-totals">
                      <div className="bg-slate-50 rounded p-2 text-center">
                        <p className="text-[10px] text-slate-500 uppercase">Total Invoices</p>
                        <p className="text-lg font-bold text-slate-800">{warehouseSummary.totals?.total_invoices || 0}</p>
                      </div>
                      <div className="bg-blue-50 rounded p-2 text-center">
                        <p className="text-[10px] text-blue-700 uppercase">Total Sales</p>
                        <p className="text-base font-bold text-blue-700">{formatRs(warehouseSummary.totals?.total_sales || 0)}</p>
                      </div>
                      <div className="bg-emerald-50 rounded p-2 text-center">
                        <p className="text-[10px] text-emerald-700 uppercase">Collections (Cash+Online)</p>
                        <p className="text-base font-bold text-emerald-700">{formatRs((warehouseSummary.totals?.cash_collections || 0) + (warehouseSummary.totals?.online_collections || 0))}</p>
                      </div>
                      <div className="bg-amber-50 rounded p-2 text-center">
                        <p className="text-[10px] text-amber-700 uppercase">Pending</p>
                        <p className="text-base font-bold text-amber-700">{formatRs(warehouseSummary.totals?.pending_amount || 0)}</p>
                      </div>
                    </div>

                    {/* Per-warehouse cards grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3" data-testid="wh-cards-grid">
                      {warehouseSummary.rows.map(row => (
                        <Card
                          key={row.warehouse_id || row.warehouse_name}
                          className="border-slate-200 hover:shadow-md transition-shadow"
                          data-testid={`wh-card-${row.warehouse_id || 'unassigned'}`}
                        >
                          <CardContent className="p-4 space-y-3">
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                  <Warehouse className="w-4 h-4 text-blue-700" />
                                  <h4 className="font-semibold text-slate-800 truncate">{row.warehouse_name}</h4>
                                  {row.is_plant && (
                                    <Badge variant="outline" className="text-[10px]">Plant</Badge>
                                  )}
                                </div>
                                {row.warehouse_code && (
                                  <p className="text-[10px] text-slate-500 mt-0.5 font-mono">Code: {row.warehouse_code}</p>
                                )}
                              </div>
                              {row.discrepancy_count > 0 && (
                                <Badge className="bg-amber-100 text-amber-700 border-amber-200">
                                  <AlertTriangle className="w-3 h-3 mr-1" />
                                  {row.discrepancy_count} disc.
                                </Badge>
                              )}
                            </div>

                            <div className="grid grid-cols-2 gap-2 text-xs">
                              <div>
                                <p className="text-slate-500 text-[10px] uppercase">Invoices</p>
                                <p className="font-semibold text-slate-800">{row.total_invoices}</p>
                              </div>
                              <div>
                                <p className="text-slate-500 text-[10px] uppercase">Total Sales</p>
                                <p className="font-semibold text-blue-700">{formatRs(row.total_sales)}</p>
                              </div>
                              <div>
                                <p className="text-slate-500 text-[10px] uppercase">Taxable</p>
                                <p className="font-medium">{formatRs(row.taxable_value)}</p>
                              </div>
                              <div>
                                <p className="text-slate-500 text-[10px] uppercase">GST Collected</p>
                                <p className="font-medium text-purple-700">{formatRs(row.gst_collected)}</p>
                              </div>
                              <div>
                                <p className="text-slate-500 text-[10px] uppercase">Cash</p>
                                <p className="font-medium text-emerald-700">{formatRs(row.cash_collections)}</p>
                              </div>
                              <div>
                                <p className="text-slate-500 text-[10px] uppercase">Online</p>
                                <p className="font-medium text-emerald-700">{formatRs(row.online_collections)}</p>
                              </div>
                              <div className="col-span-2 pt-2 border-t border-slate-100 flex items-center justify-between">
                                <span className="text-[10px] uppercase text-amber-700">Pending Balance</span>
                                <span className="font-bold text-amber-700">{formatRs(row.pending_amount)}</span>
                              </div>
                            </div>

                            {row.warehouse_id && (
                              <div className="pt-1 flex gap-1">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="text-[11px] h-7 flex-1"
                                  onClick={() => {
                                    setSelectedWarehouseIds([row.warehouse_id]);
                                    setActiveTab('invoices');
                                  }}
                                  data-testid={`wh-view-invoices-${row.warehouse_id}`}
                                >
                                  <FileText className="w-3 h-3 mr-1" /> Invoices
                                </Button>
                                {row.discrepancy_count > 0 && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="text-[11px] h-7 flex-1"
                                    onClick={() => {
                                      setSelectedWarehouseIds([row.warehouse_id]);
                                      setActiveTab('discrepancies');
                                    }}
                                    data-testid={`wh-view-disc-${row.warehouse_id}`}
                                  >
                                    <AlertTriangle className="w-3 h-3 mr-1" /> Disc.
                                  </Button>
                                )}
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* DISCREPANCIES TAB */}
          <TabsContent value="discrepancies" className="space-y-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-600" />
                  <CardTitle className="text-base">Discrepancy Invoices</CardTitle>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <Select value={discStatusFilter} onValueChange={setDiscStatusFilter}>
                    <SelectTrigger className="w-40" data-testid="disc-status-filter">
                      <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All ({discrepancySummary.total || 0})</SelectItem>
                      <SelectItem value="pending">Pending ({discrepancySummary.pending || 0})</SelectItem>
                      <SelectItem value="approved">Approved ({discrepancySummary.approved || 0})</SelectItem>
                      <SelectItem value="rejected">Rejected ({discrepancySummary.rejected || 0})</SelectItem>
                      <SelectItem value="corrected">Corrected ({discrepancySummary.corrected || 0})</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button size="sm" variant="outline" onClick={loadDiscrepancies} data-testid="disc-refresh-btn">
                    <RefreshCw className="w-4 h-4 mr-1" /> Refresh
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {/* Summary tiles */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2 px-4 pb-3 pt-1">
                  <div className="bg-slate-50 rounded p-2 text-center" data-testid="disc-tile-total">
                    <p className="text-[10px] text-slate-500 uppercase tracking-wide">Total</p>
                    <p className="text-lg font-bold text-slate-800">{discrepancySummary.total || 0}</p>
                  </div>
                  <div className="bg-amber-50 rounded p-2 text-center" data-testid="disc-tile-pending">
                    <p className="text-[10px] text-amber-700 uppercase tracking-wide">Pending</p>
                    <p className="text-lg font-bold text-amber-700">{discrepancySummary.pending || 0}</p>
                  </div>
                  <div className="bg-green-50 rounded p-2 text-center" data-testid="disc-tile-approved">
                    <p className="text-[10px] text-green-700 uppercase tracking-wide">Approved</p>
                    <p className="text-lg font-bold text-green-700">{discrepancySummary.approved || 0}</p>
                  </div>
                  <div className="bg-red-50 rounded p-2 text-center" data-testid="disc-tile-rejected">
                    <p className="text-[10px] text-red-700 uppercase tracking-wide">Rejected</p>
                    <p className="text-lg font-bold text-red-700">{discrepancySummary.rejected || 0}</p>
                  </div>
                  <div className="bg-blue-50 rounded p-2 text-center" data-testid="disc-tile-diff">
                    <p className="text-[10px] text-blue-700 uppercase tracking-wide">Net Difference</p>
                    <p className={`text-lg font-bold ${(discrepancySummary.total_difference || 0) >= 0 ? 'text-blue-700' : 'text-red-700'}`}>
                      {formatRs(discrepancySummary.total_difference || 0)}
                    </p>
                  </div>
                </div>

                <div className="overflow-x-auto border-t">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b">
                      <tr>
                        <th className="p-3 text-left font-medium">Invoice No.</th>
                        <th className="p-3 text-left font-medium">Date</th>
                        <th className="p-3 text-left font-medium">Customer</th>
                        <th className="p-3 text-right font-medium">Expected (₹)</th>
                        <th className="p-3 text-right font-medium">Actual (₹)</th>
                        <th className="p-3 text-right font-medium">Difference</th>
                        <th className="p-3 text-left font-medium">Reason</th>
                        <th className="p-3 text-center font-medium">Status</th>
                        <th className="p-3 text-center font-medium">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {!discLoading && discrepancyRows.length > 0 && discrepancyRows.map(d => (
                        <tr key={d.id} className="border-b hover:bg-slate-50" data-testid={`disc-row-${d.id}`}>
                          <td className="p-3 font-mono text-xs">{d.invoice_number}</td>
                          <td className="p-3">{d.invoice_date}</td>
                          <td className="p-3">
                            <div className="font-medium">{d.customer_name}</div>
                            <div className="text-xs text-slate-500">{(d.bill_type || '').replace('_', ' ')}</div>
                          </td>
                          <td className="p-3 text-right">{formatRs(d.expected_amount)}</td>
                          <td className="p-3 text-right">{formatRs(d.actual_amount)}</td>
                          <td className={`p-3 text-right font-semibold ${Number(d.discrepancy_amount) >= 0 ? 'text-blue-700' : 'text-red-700'}`}>
                            {Number(d.discrepancy_amount) >= 0 ? '+' : ''}{formatRs(d.discrepancy_amount)}
                          </td>
                          <td className="p-3 max-w-[260px] text-xs text-slate-600">
                            <div className="line-clamp-2" title={d.discrepancy_reason}>{d.discrepancy_reason || '-'}</div>
                            {d.discrepancy_review_note && (
                              <div className="text-[11px] text-slate-400 mt-1 italic" title={d.discrepancy_review_note}>
                                Review: {d.discrepancy_review_note}
                              </div>
                            )}
                          </td>
                          <td className="p-3 text-center">
                            {d.discrepancy_status === 'pending' && <Badge className="bg-amber-100 text-amber-700">Pending</Badge>}
                            {d.discrepancy_status === 'approved' && <Badge className="bg-green-100 text-green-700">Approved</Badge>}
                            {d.discrepancy_status === 'rejected' && <Badge className="bg-red-100 text-red-700">Rejected</Badge>}
                            {d.discrepancy_status === 'corrected' && <Badge className="bg-blue-100 text-blue-700">Corrected</Badge>}
                            {!d.discrepancy_status && <Badge variant="outline">-</Badge>}
                          </td>
                          <td className="p-3 text-center">
                            <div className="flex gap-1 justify-center">
                              <Button size="icon" variant="ghost" title="View" onClick={() => { setViewingInvoice(d); setShowViewDialog(true); }} data-testid={`disc-view-${d.id}`}>
                                <Eye className="w-4 h-4" />
                              </Button>
                              {d.discrepancy_status === 'pending' && (
                                <>
                                  <Button size="icon" variant="ghost" title="Approve" onClick={() => openReviewDialog(d, 'approve')} data-testid={`disc-approve-${d.id}`}>
                                    <CheckCircle2 className="w-4 h-4 text-green-700" />
                                  </Button>
                                  <Button size="icon" variant="ghost" title="Reject" onClick={() => openReviewDialog(d, 'reject')} data-testid={`disc-reject-${d.id}`}>
                                    <Ban className="w-4 h-4 text-red-700" />
                                  </Button>
                                  <Button size="icon" variant="ghost" title="Correct (edit invoice)" onClick={() => openInvoiceDialog(d)} data-testid={`disc-correct-${d.id}`}>
                                    <Edit2 className="w-4 h-4 text-blue-700" />
                                  </Button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {discLoading && (
                    <div className="p-8 text-center text-slate-500" data-testid="disc-loading">Loading discrepancies…</div>
                  )}
                  {!discLoading && discrepancyRows.length === 0 && (
                    <div className="p-8 text-center text-slate-500" data-testid="disc-empty">
                      No discrepancy invoices {discStatusFilter !== 'all' ? `in status "${discStatusFilter}"` : 'yet'}. All amounts match the configured rates 🎉
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* PARTY LEDGER TAB */}
          <TabsContent value="ledger" className="space-y-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-2">
                  <Users className="w-5 h-5 text-blue-700" />
                  <CardTitle className="text-base">Party Ledger</CardTitle>
                  {ledgerSelected && (
                    <Badge variant="outline" className="ml-2" data-testid="ledger-current-customer">
                      {ledgerSelected.customer_name}{ledgerSelected.customer_phone ? ` · ${ledgerSelected.customer_phone}` : ''}
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {ledgerSelected && (
                    <Button size="sm" variant="outline" onClick={loadLedger} disabled={ledgerLoading} data-testid="ledger-refresh-btn">
                      <RefreshCw className="w-4 h-4 mr-1" /> Refresh
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Customer picker + filters */}
                <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
                  <div className="md:col-span-5">
                    <Label>Customer</Label>
                    <Input
                      placeholder="Search by name or phone..."
                      value={ledgerSearch}
                      onChange={(e) => setLedgerSearch(e.target.value)}
                      data-testid="ledger-customer-search"
                    />
                    <div className="border rounded mt-1 max-h-40 overflow-y-auto bg-white">
                      {ledgerCustomers
                        .filter(c => {
                          const s = ledgerSearch.trim().toLowerCase();
                          if (!s) return true;
                          return (c.customer_name || '').toLowerCase().includes(s)
                              || (c.customer_phone || '').toLowerCase().includes(s);
                        })
                        .slice(0, 20)
                        .map((c, i) => (
                          <button
                            key={`${c.customer_name}-${c.customer_phone}-${i}`}
                            onClick={() => setLedgerSelected(c)}
                            className={`w-full text-left px-2 py-1 text-sm hover:bg-blue-50 ${ledgerSelected && ledgerSelected.customer_name === c.customer_name && ledgerSelected.customer_phone === c.customer_phone ? 'bg-blue-100' : ''}`}
                            data-testid={`ledger-customer-${i}`}
                          >
                            <div className="font-medium">{c.customer_name || '(no name)'}</div>
                            <div className="text-xs text-slate-500">
                              {c.customer_phone || '—'} · {c.invoice_count} invoice(s) · last {c.last_invoice_date || '-'}
                            </div>
                          </button>
                        ))}
                      {ledgerCustomers.length === 0 && (
                        <div className="px-2 py-2 text-xs text-slate-500">No customers with invoices yet.</div>
                      )}
                    </div>
                  </div>
                  <div className="md:col-span-3">
                    <Label>Period</Label>
                    <Select value={ledgerPeriod} onValueChange={setLedgerPeriod}>
                      <SelectTrigger data-testid="ledger-period"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All records</SelectItem>
                        <SelectItem value="today">Today</SelectItem>
                        <SelectItem value="this_month">This Month</SelectItem>
                        <SelectItem value="this_year">This Year</SelectItem>
                        <SelectItem value="custom">Custom range</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {ledgerPeriod === 'custom' && (
                    <>
                      <div className="md:col-span-2">
                        <Label>From</Label>
                        <Input type="date" value={ledgerStartDate} onChange={(e) => setLedgerStartDate(e.target.value)} data-testid="ledger-start-date" />
                      </div>
                      <div className="md:col-span-2">
                        <Label>To</Label>
                        <Input type="date" value={ledgerEndDate} onChange={(e) => setLedgerEndDate(e.target.value)} data-testid="ledger-end-date" />
                      </div>
                    </>
                  )}
                </div>

                {/* Totals card */}
                {ledgerSelected && (
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-2" data-testid="ledger-totals">
                    <div className="bg-slate-50 rounded p-2 text-center">
                      <p className="text-[10px] text-slate-500 uppercase">Invoices</p>
                      <p className="text-lg font-bold text-slate-800">{ledgerTotals.count || 0}</p>
                    </div>
                    <div className="bg-blue-50 rounded p-2 text-center">
                      <p className="text-[10px] text-blue-700 uppercase">Invoice Value</p>
                      <p className="text-base font-bold text-blue-700">{formatRs(ledgerTotals.total_invoice_value || 0)}</p>
                    </div>
                    <div className="bg-emerald-50 rounded p-2 text-center">
                      <p className="text-[10px] text-emerald-700 uppercase">Cash + Online</p>
                      <p className="text-base font-bold text-emerald-700">{formatRs(ledgerTotals.total_paid || 0)}</p>
                      <p className="text-[10px] text-slate-500">
                        ₹{Number(ledgerTotals.total_cash_received || 0).toFixed(0)} cash + ₹{Number(ledgerTotals.total_online_received || 0).toFixed(0)} online
                      </p>
                    </div>
                    <div className="bg-amber-50 rounded p-2 text-center">
                      <p className="text-[10px] text-amber-700 uppercase">Pending</p>
                      <p className="text-base font-bold text-amber-700">{formatRs(ledgerTotals.total_pending_balance || 0)}</p>
                    </div>
                    <div className="bg-purple-50 rounded p-2 text-center">
                      <p className="text-[10px] text-purple-700 uppercase">GST Collected</p>
                      <p className="text-base font-bold text-purple-700">{formatRs(ledgerTotals.total_gst || 0)}</p>
                    </div>
                  </div>
                )}

                {/* Ledger table */}
                <div className="overflow-x-auto border rounded">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-50 border-b">
                      <tr>
                        <th className="p-2 text-left font-medium">Memo No.</th>
                        <th className="p-2 text-left font-medium">Invoice No.</th>
                        <th className="p-2 text-left font-medium">Date / Time</th>
                        <th className="p-2 text-left font-medium">Type</th>
                        <th className="p-2 text-right font-medium">Taxable</th>
                        <th className="p-2 text-right font-medium">GST</th>
                        <th className="p-2 text-right font-medium">Invoice Total</th>
                        <th className="p-2 text-right font-medium">Cash</th>
                        <th className="p-2 text-right font-medium">Online</th>
                        <th className="p-2 text-right font-medium">Paid</th>
                        <th className="p-2 text-right font-medium">Pending</th>
                        <th className="p-2 text-center font-medium">Status</th>
                        <th className="p-2 text-left font-medium">Created By</th>
                      </tr>
                    </thead>
                    <tbody>
                      {!ledgerLoading && ledgerSelected && ledgerRows.length > 0 && ledgerRows.map(r => (
                        <tr key={r.id} className="border-b hover:bg-slate-50" data-testid={`ledger-row-${r.id}`}>
                          <td className="p-2 font-mono">{r.memo_no}</td>
                          <td className="p-2 font-mono text-blue-700">{r.invoice_number}</td>
                          <td className="p-2">
                            {r.invoice_date}
                            <div className="text-[10px] text-slate-400">{r.created_at ? new Date(r.created_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}) : ''}</div>
                          </td>
                          <td className="p-2 capitalize">{r.invoice_type}</td>
                          <td className="p-2 text-right">{formatRs(r.taxable_amount)}</td>
                          <td className="p-2 text-right">{formatRs(r.gst_amount)}</td>
                          <td className="p-2 text-right font-semibold">{formatRs(r.total_invoice_amount)}</td>
                          <td className="p-2 text-right">{formatRs(r.cash_received)}</td>
                          <td className="p-2 text-right">{formatRs(r.online_received)}</td>
                          <td className="p-2 text-right text-emerald-700">{formatRs(r.total_paid)}</td>
                          <td className="p-2 text-right text-amber-700 font-semibold">{formatRs(r.pending_balance)}</td>
                          <td className="p-2 text-center">
                            {r.payment_status === 'Paid' && <Badge className="bg-green-100 text-green-700">Paid</Badge>}
                            {r.payment_status === 'Partial' && <Badge className="bg-amber-100 text-amber-700">Partial</Badge>}
                            {r.payment_status === 'Pending' && <Badge className="bg-red-100 text-red-700">Pending</Badge>}
                            {!r.payment_status && <Badge variant="outline">—</Badge>}
                          </td>
                          <td className="p-2 text-slate-600">{r.created_by || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {ledgerLoading && (
                    <div className="p-6 text-center text-slate-500" data-testid="ledger-loading">Loading ledger…</div>
                  )}
                  {!ledgerLoading && !ledgerSelected && (
                    <div className="p-8 text-center text-slate-500" data-testid="ledger-no-selection">
                      Pick a customer on the left to view their ledger.
                    </div>
                  )}
                  {!ledgerLoading && ledgerSelected && ledgerRows.length === 0 && (
                    <div className="p-8 text-center text-slate-500" data-testid="ledger-empty">
                      No invoices found for {ledgerSelected.customer_name} in the selected period.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* REPORTS TAB */}
          <TabsContent value="reports" className="space-y-4">
            <Card>
              <CardContent className="p-4 space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                  <div className="md:col-span-2">
                    <Label>Report Type</Label>
                    <Select value={reportType} onValueChange={setReportType}>
                      <SelectTrigger data-testid="report-type-select"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {reportsList.map(r => (
                          <SelectItem key={r.key} value={r.key}>{r.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Start Date</Label>
                    <Input type="date" value={reportStart} onChange={e => setReportStart(e.target.value)} data-testid="report-start" />
                  </div>
                  <div>
                    <Label>End Date</Label>
                    <Input type="date" value={reportEnd} onChange={e => setReportEnd(e.target.value)} data-testid="report-end" />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 justify-end">
                  <Button variant="outline" onClick={runReport} disabled={reportLoading} data-testid="report-refresh">
                    <RefreshCw className={`w-4 h-4 mr-1 ${reportLoading ? 'animate-spin' : ''}`} />
                    {reportLoading ? 'Loading...' : 'Refresh'}
                  </Button>
                  <Button variant="outline" onClick={handleExportReportExcel} data-testid="report-excel-btn">
                    <FileSpreadsheet className="w-4 h-4 mr-1" /> Export Excel
                  </Button>
                  <Button variant="outline" onClick={handleExportReportPdf} data-testid="report-pdf-btn">
                    <FileDown className="w-4 h-4 mr-1" /> Export PDF
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Report data */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center justify-between">
                  <span>{reportData?.label || 'Report'}</span>
                  <span className="text-xs font-normal text-slate-500">
                    {reportData ? `${reportData.rows.length} rows` : ''}
                  </span>
                </CardTitle>
                <p className="text-xs text-slate-500">
                  Period: {reportStart || 'All'} to {reportEnd || 'All'}
                </p>
              </CardHeader>
              <CardContent className="p-0">
                {reportLoading ? (
                  <div className="p-8 text-center text-slate-500">Loading report...</div>
                ) : !reportData || reportData.rows.length === 0 ? (
                  <div className="p-8 text-center text-slate-500">No data for selected period.</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs" data-testid="report-table">
                      <thead className="bg-blue-700 text-white sticky top-0">
                        <tr>
                          {reportData.columns.map(c => (
                            <th key={c.key} className={`p-2 ${c.align === 'amount' ? 'text-right' : c.align === 'center' ? 'text-center' : 'text-left'} font-medium`}>
                              {c.label}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {reportData.rows.map((r, idx) => (
                          <tr key={idx} className="border-b hover:bg-slate-50 align-top">
                            {reportData.columns.map(c => {
                              const val = r[c.key];
                              const isAmount = c.align === 'amount';
                              return (
                                <td key={c.key} className={`p-2 ${isAmount ? 'text-right font-mono' : c.align === 'center' ? 'text-center' : 'text-left'} break-words max-w-[260px]`}>
                                  {isAmount && typeof val === 'number' ? val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : (val ?? '—')}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-blue-50 font-semibold border-t-2 border-blue-300">
                        <tr>
                          {reportData.columns.map((c, idx) => {
                            if (idx === 0) {
                              return <td key={c.key} className="p-2 text-right">TOTAL</td>;
                            }
                            const val = reportData.summary?.[c.key];
                            if (c.align === 'amount' && typeof val === 'number') {
                              return <td key={c.key} className="p-2 text-right font-mono text-blue-800">{val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>;
                            }
                            if (c.key === 'invoices' && reportData.summary?.invoices != null) {
                              return <td key={c.key} className="p-2 text-center">{reportData.summary.invoices}</td>;
                            }
                            return <td key={c.key} className="p-2"></td>;
                          })}
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                )}
                {/* GST Report summary footer (B2B/B2C counts) */}
                {reportData && reportType === 'gst_report' && (
                  <div className="p-3 border-t bg-slate-50 text-xs flex flex-wrap gap-4">
                    <span><strong>B2B Invoices:</strong> {reportData.summary?.b2b_count || 0}</span>
                    <span><strong>B2C Invoices:</strong> {reportData.summary?.b2c_count || 0}</span>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* CONNECTION PLANS TAB */}
          <TabsContent value="plans">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-base">Connection Plans (Item-wise Billing Templates)</CardTitle>
                  <p className="text-xs text-slate-500 mt-1">
                    Set unit prices per item per plan. Once all items have prices, new connection sales will auto-itemize using the matching plan.
                  </p>
                </div>
                <Button size="sm" onClick={() => {
                  setEditingPlan({
                    name: '', plan_type: 'custom', connection_type: 'domestic',
                    cylinder_count: 1, has_accessories: false,
                    items: [{ item_name: '', hsn: '', unit: 'Nos', quantity: 1, gst_rate: 18, unit_price: 0 }],
                  });
                  setShowPlanDialog(true);
                }} data-testid="add-plan-btn">
                  <Plus className="w-4 h-4 mr-1" /> Add Plan
                </Button>
              </CardHeader>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b">
                    <tr>
                      <th className="text-left p-3 font-medium">Plan Name</th>
                      <th className="text-left p-3 font-medium">Type</th>
                      <th className="text-center p-3 font-medium">Cylinders</th>
                      <th className="text-center p-3 font-medium">Accessories</th>
                      <th className="text-center p-3 font-medium">Items</th>
                      <th className="text-center p-3 font-medium">Rates Set</th>
                      <th className="text-center p-3 font-medium">Status</th>
                      <th className="text-center p-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plans.length > 0 && plans.map(p => {
                      const ratesSet = p.items?.every(i => Number(i.unit_price) > 0);
                      return (
                        <tr key={p.id} className="border-b hover:bg-slate-50" data-testid={`plan-row-${p.id}`}>
                          <td className="p-3 font-medium">{p.name}</td>
                          <td className="p-3"><Badge variant="outline">{p.connection_type}</Badge></td>
                          <td className="p-3 text-center">{p.cylinder_count}</td>
                          <td className="p-3 text-center">{p.has_accessories ? 'Yes' : 'No'}</td>
                          <td className="p-3 text-center">{p.items?.length || 0}</td>
                          <td className="p-3 text-center">
                            {ratesSet
                              ? <Badge className="bg-green-100 text-green-700">All set</Badge>
                              : <Badge className="bg-amber-100 text-amber-700">Set rates</Badge>}
                          </td>
                          <td className="p-3 text-center">
                            {p.is_active
                              ? <Badge className="bg-green-100 text-green-700">Active</Badge>
                              : <Badge variant="outline">Inactive</Badge>}
                          </td>
                          <td className="p-3 text-center">
                            <Button size="icon" variant="ghost" onClick={() => {
                              setEditingPlan({ ...p, items: p.items.map(it => ({ ...it })) });
                              setShowPlanDialog(true);
                            }} data-testid={`edit-plan-${p.id}`}>
                              <Edit2 className="w-4 h-4" />
                            </Button>
                            <Button size="icon" variant="ghost" onClick={() => handleDeletePlan(p)}>
                              <Trash2 className="w-4 h-4 text-red-600" />
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {plans.length === 0 && (
                  <div className="p-8 text-center text-slate-500" data-testid="plans-empty">No plans yet.</div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ITEM MASTER TAB */}
          <TabsContent value="items">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between flex-wrap gap-2">
                <CardTitle className="text-base">Item Master (HSN + GST Rates)</CardTitle>
                <div className="flex flex-wrap items-center gap-2">
                  <Button size="sm" variant="outline" onClick={handleDownloadTemplate} data-testid="download-template-btn">
                    <FileSpreadsheet className="w-4 h-4 mr-1" /> Download Template
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => { setBulkFile(null); setBulkResult(null); setBulkEffectiveFrom(todayISO()); setShowBulkUploadDialog(true); }} data-testid="bulk-upload-btn">
                    <Upload className="w-4 h-4 mr-1" /> Bulk Upload
                  </Button>
                  <Button size="sm" variant="outline" onClick={openHistoryDialog} data-testid="rate-history-btn">
                    <History className="w-4 h-4 mr-1" /> Rate History
                  </Button>
                  <Button size="sm" onClick={() => { setEditingItem({ name: '', hsn: '', unit: 'Nos', gst_rate: 18, default_rate: 0 }); setShowItemDialog(true); }} data-testid="add-item-btn">
                    <Plus className="w-4 h-4 mr-1" /> Add Item
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 border-b">
                    <tr>
                      <th className="text-left p-3 font-medium">Name</th>
                      <th className="text-left p-3 font-medium">HSN</th>
                      <th className="text-left p-3 font-medium">Unit</th>
                      <th className="text-right p-3 font-medium">GST %</th>
                      <th className="text-right p-3 font-medium">Default Rate</th>
                      <th className="text-center p-3 font-medium">Status</th>
                      <th className="text-center p-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map(it => (
                      <tr key={it.id} className="border-b">
                        <td className="p-3 font-medium">{it.name}</td>
                        <td className="p-3 font-mono text-xs">{it.hsn}</td>
                        <td className="p-3">{it.unit}</td>
                        <td className="p-3 text-right">{it.gst_rate}%</td>
                        <td className="p-3 text-right">{formatRs(it.default_rate)}</td>
                        <td className="p-3 text-center">
                          {it.is_active
                            ? <Badge className="bg-green-100 text-green-700">Active</Badge>
                            : <Badge variant="outline">Inactive</Badge>}
                        </td>
                        <td className="p-3 text-center">
                          <Button size="icon" variant="ghost" onClick={() => { setEditingItem({ ...it }); setShowItemDialog(true); }} title="Edit" data-testid={`edit-item-${it.id}`}>
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          {it.is_active ? (
                            <Button size="icon" variant="ghost" onClick={() => handleDeleteItem(it)} title="Deactivate" data-testid={`deactivate-item-${it.id}`}>
                              <XCircle className="w-4 h-4 text-red-600" />
                            </Button>
                          ) : (
                            <Button size="sm" variant="outline" className="h-8 ml-1 text-green-700 border-green-300" onClick={() => handleActivateItem(it)} title="Reactivate" data-testid={`activate-item-${it.id}`}>
                              Activate
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* SETTINGS DIALOG */}
        <Dialog open={showConfigDialog} onOpenChange={setShowConfigDialog}>
          <DialogContent className="w-[95vw] sm:max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="config-dialog">
            <DialogHeader>
              <DialogTitle>GST Billing Settings</DialogTitle>
              <DialogDescription>
                Configure invoice numbering, company branding, bank details and terms shown on every invoice PDF.
              </DialogDescription>
            </DialogHeader>
            <Tabs defaultValue="numbering">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="numbering" data-testid="cfg-tab-numbering">Numbering</TabsTrigger>
                <TabsTrigger value="company" data-testid="cfg-tab-company">Company</TabsTrigger>
                <TabsTrigger value="bank" data-testid="cfg-tab-bank">Bank</TabsTrigger>
                <TabsTrigger value="terms" data-testid="cfg-tab-terms">Terms &amp; Signatory</TabsTrigger>
              </TabsList>

              {/* NUMBERING */}
              <TabsContent value="numbering" className="space-y-3 mt-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <Label>Invoice Prefix</Label>
                    <Input value={config.prefix || ''} onChange={e => setConfig({ ...config, prefix: e.target.value })} data-testid="config-prefix" />
                    <p className="text-xs text-slate-500 mt-1">Letters/digits only, e.g. <span className="font-mono">K3</span> or <span className="font-mono">INV</span>. <strong>Do NOT include <span className="font-mono">/</span> or the FY.</strong></p>
                  </div>
                  <div>
                    <Label>Invoice Suffix</Label>
                    <Input value={config.suffix || ''} onChange={e => setConfig({ ...config, suffix: e.target.value })} data-testid="config-suffix" />
                    <p className="text-xs text-slate-500 mt-1">Optional short tag (no <span className="font-mono">/</span>, no FY).</p>
                  </div>
                  <div>
                    <Label>Default Tax Mode</Label>
                    <Select value={config.default_tax_mode || 'intra_state'} onValueChange={v => setConfig({ ...config, default_tax_mode: v })}>
                      <SelectTrigger data-testid="config-tax-mode"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="intra_state">Intra-state (CGST + SGST)</SelectItem>
                        <SelectItem value="inter_state">Inter-state (IGST)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Place of Supply</Label>
                    <Input value={config.place_of_supply || ''} onChange={e => setConfig({ ...config, place_of_supply: e.target.value })} data-testid="config-place" />
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="auto-gen"
                    checked={!!config.auto_generate}
                    onChange={e => setConfig({ ...config, auto_generate: e.target.checked })}
                    data-testid="config-auto-gen"
                  />
                  <Label htmlFor="auto-gen" className="cursor-pointer">Auto-generate invoice on new sales</Label>
                </div>
                <div className="text-xs text-slate-600 p-3 bg-blue-50 border border-blue-100 rounded">
                  <div><strong>Format preview:</strong> {config.prefix || 'INV'}/{config.current_fy || 'YYYY-YY'}/0001{config.suffix ? `/${config.suffix}` : ''}</div>
                  <div className="mt-1">Next invoice number: <strong>{config.next_seq || 1}</strong> (FY {config.current_fy || '-'})</div>
                </div>
                <div className="rounded border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs text-amber-900 font-medium">Repair Malformed Invoice Numbers</p>
                  <p className="text-[11px] text-amber-800 mt-0.5">
                    If some invoices show a duplicated pattern like <span className="font-mono">K3/2026-27/0001/2026-27/0037</span>,
                    click below to normalize them to <span className="font-mono">K3/2026-27/0037</span>. Correctly-formed numbers are left untouched.
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-2 border-amber-300 text-amber-900 hover:bg-amber-100"
                    data-testid="repair-invoice-numbers-btn"
                    onClick={async () => {
                      if (!window.confirm('Scan and repair all malformed invoice numbers?')) return;
                      try {
                        const { data } = await repairGstInvoiceNumbers();
                        toast.success(`Repaired ${data.repaired} invoice number(s).`);
                        loadInvoices();
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || 'Repair failed');
                      }
                    }}
                  >
                    <RefreshCw className="w-3.5 h-3.5 mr-1" /> Repair Now
                  </Button>
                </div>
              </TabsContent>

              {/* COMPANY */}
              <TabsContent value="company" className="space-y-3 mt-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="md:col-span-2">
                    <Label>Company Name *</Label>
                    <Input value={config.company_name || ''} onChange={e => setConfig({ ...config, company_name: e.target.value })} data-testid="cfg-co-name" />
                  </div>
                  <div className="md:col-span-2">
                    <Label>Tagline</Label>
                    <Input value={config.company_tagline || ''} onChange={e => setConfig({ ...config, company_tagline: e.target.value })} />
                  </div>
                  <div className="md:col-span-2">
                    <Label>GST Registered Address</Label>
                    <Textarea rows={2} value={config.company_address || ''} onChange={e => setConfig({ ...config, company_address: e.target.value })} data-testid="cfg-co-address" />
                  </div>
                  <div>
                    <Label>Company GSTIN</Label>
                    <Input value={config.company_gstin || ''} onChange={e => setConfig({ ...config, company_gstin: e.target.value.toUpperCase() })} data-testid="cfg-co-gstin" />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label>State</Label>
                      <Input value={config.company_state || ''} onChange={e => setConfig({ ...config, company_state: e.target.value })} />
                    </div>
                    <div>
                      <Label>State Code</Label>
                      <Input value={config.company_state_code || ''} onChange={e => setConfig({ ...config, company_state_code: e.target.value })} />
                    </div>
                  </div>
                  <div>
                    <Label>Phone</Label>
                    <Input value={config.company_phone || ''} onChange={e => setConfig({ ...config, company_phone: e.target.value })} />
                  </div>
                  <div>
                    <Label>Email</Label>
                    <Input value={config.company_email || ''} onChange={e => setConfig({ ...config, company_email: e.target.value })} />
                  </div>
                  <div className="md:col-span-2">
                    <Label>Logo URL</Label>
                    <Input placeholder="https://..." value={config.company_logo_url || ''} onChange={e => setConfig({ ...config, company_logo_url: e.target.value })} data-testid="cfg-co-logo" />
                    {config.company_logo_url && (
                      <img src={config.company_logo_url} alt="logo preview" className="mt-2 h-16 object-contain border rounded p-1 bg-white" onError={(e) => { e.target.style.display = 'none'; }} />
                    )}
                  </div>
                </div>
              </TabsContent>

              {/* BANK */}
              <TabsContent value="bank" className="space-y-3 mt-4">
                <p className="text-xs text-slate-500">Bank details printed in the footer of every invoice PDF.</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="md:col-span-2">
                    <Label>Bank Name</Label>
                    <Input value={config.bank_name || ''} onChange={e => setConfig({ ...config, bank_name: e.target.value })} data-testid="cfg-bank-name" />
                  </div>
                  <div className="md:col-span-2">
                    <Label>Account Holder Name</Label>
                    <Input value={config.bank_account_holder || ''} onChange={e => setConfig({ ...config, bank_account_holder: e.target.value })} />
                  </div>
                  <div>
                    <Label>Account Number</Label>
                    <Input value={config.bank_account_no || ''} onChange={e => setConfig({ ...config, bank_account_no: e.target.value })} data-testid="cfg-bank-acc" />
                  </div>
                  <div>
                    <Label>IFSC Code</Label>
                    <Input value={config.bank_ifsc || ''} onChange={e => setConfig({ ...config, bank_ifsc: e.target.value.toUpperCase() })} data-testid="cfg-bank-ifsc" />
                  </div>
                  <div className="md:col-span-2">
                    <Label>Branch</Label>
                    <Input value={config.bank_branch || ''} onChange={e => setConfig({ ...config, bank_branch: e.target.value })} />
                  </div>
                </div>
              </TabsContent>

              {/* TERMS & SIGNATORY */}
              <TabsContent value="terms" className="space-y-3 mt-4">
                <div>
                  <Label>Terms &amp; Conditions</Label>
                  <Textarea rows={6} placeholder="Enter one term per line" value={config.terms_conditions || ''} onChange={e => setConfig({ ...config, terms_conditions: e.target.value })} data-testid="cfg-terms" />
                  <p className="text-xs text-slate-500 mt-1">These print at the bottom of every invoice PDF. One term per line.</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <Label>Authorized Signatory Name</Label>
                    <Input value={config.signatory_name || ''} onChange={e => setConfig({ ...config, signatory_name: e.target.value })} data-testid="cfg-sig-name" />
                  </div>
                  <div>
                    <Label>Designation</Label>
                    <Input value={config.signatory_designation || ''} onChange={e => setConfig({ ...config, signatory_designation: e.target.value })} />
                  </div>
                </div>
              </TabsContent>
            </Tabs>
            <DialogFooter className="mt-4">
              <Button variant="outline" onClick={() => setShowConfigDialog(false)}>Cancel</Button>
              <Button onClick={handleSaveConfig} className="bg-blue-700 hover:bg-blue-800" data-testid="save-config-btn">Save Settings</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* DISCREPANCY REASON DIALOG (triggered when create/edit invoice fails amount validation) */}
        <Dialog open={showDiscReasonDialog} onOpenChange={(o) => { if (!o) { setShowDiscReasonDialog(false); setDiscReasonInfo(null); setDiscReasonInput(''); } }}>
          <DialogContent className="w-[95vw] sm:max-w-xl" data-testid="discrepancy-reason-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
                Amount Mismatch Detected
              </DialogTitle>
              <DialogDescription>
                The entered total does not match the configured rate. A justification is mandatory to save this as a <strong>Discrepancy Invoice</strong> for admin review.
              </DialogDescription>
            </DialogHeader>
            {discReasonInfo && (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-2 bg-amber-50 border border-amber-200 rounded p-3">
                  <div className="text-center">
                    <p className="text-[10px] text-amber-700 uppercase">Expected</p>
                    <p className="text-base font-bold text-slate-800" data-testid="disc-reason-expected">{formatRs(discReasonInfo.expected)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-[10px] text-amber-700 uppercase">Entered</p>
                    <p className="text-base font-bold text-slate-800" data-testid="disc-reason-actual">{formatRs(discReasonInfo.actual)}</p>
                  </div>
                  <div className="text-center">
                    <p className="text-[10px] text-amber-700 uppercase">Difference</p>
                    <p className={`text-base font-bold ${Number(discReasonInfo.diff) >= 0 ? 'text-blue-700' : 'text-red-700'}`} data-testid="disc-reason-diff">
                      {Number(discReasonInfo.diff) >= 0 ? '+' : ''}{formatRs(discReasonInfo.diff)}
                    </p>
                  </div>
                </div>
                <div>
                  <Label htmlFor="disc-reason-input">Justification / Reason *</Label>
                  <Textarea
                    id="disc-reason-input"
                    rows={4}
                    value={discReasonInput}
                    onChange={(e) => setDiscReasonInput(e.target.value)}
                    placeholder="e.g., Customer overpaid for early adopter bonus, agreed-upon discount, delivery surcharge..."
                    data-testid="disc-reason-input"
                  />
                  <p className="text-xs text-slate-500 mt-1">This will be saved with the invoice and reviewed by an admin in the Discrepancies tab.</p>
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => { setShowDiscReasonDialog(false); setDiscReasonInfo(null); setDiscReasonInput(''); }} data-testid="disc-reason-cancel">
                Go back & edit
              </Button>
              <Button
                onClick={handleConfirmDiscrepancyReason}
                disabled={!discReasonInput.trim() || discReasonSaving}
                className="bg-amber-600 hover:bg-amber-700"
                data-testid="disc-reason-confirm"
              >
                {discReasonSaving ? 'Saving…' : 'Save as Discrepancy'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* DISCREPANCY REVIEW DIALOG (Approve / Reject) */}
        <Dialog open={showReviewDialog} onOpenChange={(o) => { setShowReviewDialog(o); if (!o) { setReviewTarget(null); setReviewNote(''); } }}>
          <DialogContent className="w-[95vw] sm:max-w-lg" data-testid="discrepancy-review-dialog">
            <DialogHeader>
              <DialogTitle>
                {reviewAction === 'approve' ? 'Approve' : 'Reject'} Discrepancy — {reviewTarget?.invoice_number}
              </DialogTitle>
              <DialogDescription>
                {reviewAction === 'approve'
                  ? 'Approving accepts the recorded reason and closes the discrepancy for audit.'
                  : 'Rejecting flags this discrepancy as invalid. The invoice stays as-is — you may also choose to correct it instead.'}
              </DialogDescription>
            </DialogHeader>
            {reviewTarget && (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-2 text-xs bg-slate-50 rounded p-2">
                  <div><span className="text-slate-500">Customer:</span> <span className="font-medium">{reviewTarget.customer_name}</span></div>
                  <div><span className="text-slate-500">Expected:</span> <span className="font-medium">{formatRs(reviewTarget.expected_amount)}</span></div>
                  <div><span className="text-slate-500">Actual:</span> <span className="font-medium">{formatRs(reviewTarget.actual_amount)}</span></div>
                  <div className="col-span-3"><span className="text-slate-500">Stated reason:</span> <span className="italic">{reviewTarget.discrepancy_reason || '-'}</span></div>
                </div>
                <div>
                  <Label htmlFor="review-note">Review Note {reviewAction === 'reject' ? '*' : '(optional)'}</Label>
                  <Textarea
                    id="review-note"
                    rows={3}
                    value={reviewNote}
                    onChange={(e) => setReviewNote(e.target.value)}
                    placeholder={reviewAction === 'approve' ? 'Optional: add any context for the audit log.' : 'Required: explain why this reason is rejected.'}
                    data-testid="disc-review-note"
                  />
                </div>
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowReviewDialog(false)} data-testid="disc-review-cancel">Cancel</Button>
              <Button
                onClick={handleSubmitReview}
                disabled={reviewing || (reviewAction === 'reject' && !reviewNote.trim())}
                className={reviewAction === 'approve' ? 'bg-green-700 hover:bg-green-800' : 'bg-red-700 hover:bg-red-800'}
                data-testid="disc-review-submit"
              >
                {reviewing ? 'Submitting…' : (reviewAction === 'approve' ? 'Approve' : 'Reject')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* CANCEL DIALOG */}
        <Dialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
          <DialogContent className="w-[95vw] sm:max-w-md" data-testid="cancel-dialog">
            <DialogHeader>
              <DialogTitle>Cancel Invoice {cancelTarget?.invoice_number}</DialogTitle>
              <DialogDescription>
                Cancelled invoices remain in records but are marked CANCELLED.
              </DialogDescription>
            </DialogHeader>
            <Textarea
              placeholder="Reason for cancellation (optional)"
              value={cancelReason}
              onChange={e => setCancelReason(e.target.value)}
              data-testid="cancel-reason"
            />
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCancelDialog(false)}>Back</Button>
              <Button variant="destructive" onClick={handleCancel} data-testid="confirm-cancel-btn">Cancel Invoice</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* GENERATE FROM SALE DIALOG */}
        <Dialog open={showGenerateDialog} onOpenChange={setShowGenerateDialog}>
          <DialogContent className="w-[95vw] sm:max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="generate-dialog">
            <DialogHeader>
              <DialogTitle>Generate Invoice from Existing Sale</DialogTitle>
              <DialogDescription>
                For legacy/old sales that don&apos;t yet have an invoice. Pick a sale below and click Generate.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <div className="flex gap-2">
                <Select value={genSaleType} onValueChange={setGenSaleType}>
                  <SelectTrigger className="w-48" data-testid="gen-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sales_entry">Cylinder Sales</SelectItem>
                    <SelectItem value="accessory_sale">Accessory Sales</SelectItem>
                  </SelectContent>
                </Select>
                <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
                <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
                <Button onClick={loadLegacySales} disabled={legacyLoading}>
                  {legacyLoading ? 'Loading...' : 'Reload'}
                </Button>
              </div>
              <div className="max-h-96 overflow-y-auto border rounded">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 sticky top-0">
                    <tr>
                      <th className="text-left p-2">Date</th>
                      <th className="text-left p-2">Customer</th>
                      <th className="text-left p-2">Memo</th>
                      <th className="text-left p-2">Type</th>
                      <th className="text-right p-2">Amount</th>
                      <th className="text-center p-2">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {legacySales.length === 0 ? (
                      <tr><td colSpan="6" className="p-6 text-center text-slate-500">No sales in selected range.</td></tr>
                    ) : legacySales.map(s => (
                      <tr key={s.id} className="border-t" data-testid={`legacy-row-${s.id}`}>
                        <td className="p-2">{s.date}</td>
                        <td className="p-2">{s.consumer_name}</td>
                        <td className="p-2 font-mono text-xs">{s.memo_no || '-'}</td>
                        <td className="p-2"><Badge variant="outline">{(s.connection_type || '-').replace('_', ' ')}</Badge></td>
                        <td className="p-2 text-right">{formatRs(s.amount)}</td>
                        <td className="p-2 text-center">
                          <Button size="sm" onClick={() => handleGenerateFromSale(s)} data-testid={`gen-btn-${s.id}`}>
                            Generate
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowGenerateDialog(false)}>Close</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* INVOICE CREATE/EDIT DIALOG */}
        {invForm && (
          <Dialog open={showInvoiceDialog} onOpenChange={(o) => { setShowInvoiceDialog(o); if (!o) { setInvForm(null); setEditingInvoice(null); } }}>
            <DialogContent className="w-[95vw] sm:max-w-5xl max-h-[90vh] overflow-y-auto" data-testid="invoice-dialog">
              <DialogHeader>
                <DialogTitle>{editingInvoice ? `Edit Invoice ${editingInvoice.invoice_number}` : 'New Manual Invoice'}</DialogTitle>
              </DialogHeader>

              <div className="space-y-4">
                {/* Customer Master picker — auto-fills customer details from Customer DB */}
                <div className="rounded-md border border-blue-100 bg-blue-50/40 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="flex items-center gap-2 text-blue-900">
                      <UserIcon className="w-4 h-4" /> Link to Customer Master
                    </Label>
                    {invForm.customer_id && (
                      <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200" data-testid="inv-customer-linked-badge">
                        <CheckCircle2 className="w-3 h-3 mr-1" />
                        Linked{invForm.customer_source === 'master' ? ' · Customer DB' : ''}
                      </Badge>
                    )}
                  </div>
                  <div className="relative">
                    <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <Input
                      placeholder="Search Customer Master by Name, Consumer No., or Phone (min 2 chars)…"
                      value={custLookupQuery}
                      onChange={e => { setCustLookupQuery(e.target.value); setCustLookupOpen(true); }}
                      onFocus={() => setCustLookupOpen(true)}
                      className="pl-9"
                      data-testid="inv-customer-lookup-input"
                    />
                    {custLookupOpen && custLookupQuery.trim().length >= 2 && (
                      <div className="absolute z-50 left-0 right-0 mt-1 bg-white border rounded-md shadow-lg max-h-64 overflow-y-auto" data-testid="inv-customer-lookup-dropdown">
                        {custLookupLoading && (
                          <div className="p-3 text-xs text-slate-500">Searching…</div>
                        )}
                        {!custLookupLoading && custLookupResults.length === 0 && (
                          <div className="p-3 text-xs text-slate-500" data-testid="inv-customer-lookup-empty">
                            No matches found. You can still type customer details manually below.
                          </div>
                        )}
                        {!custLookupLoading && custLookupResults.map(c => (
                          <button
                            key={c.id}
                            type="button"
                            onClick={() => applyCustomerFromMaster(c)}
                            className="w-full text-left px-3 py-2 hover:bg-blue-50 border-b last:border-b-0"
                            data-testid={`inv-customer-lookup-item-${c.id}`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="min-w-0">
                                <div className="text-sm font-medium truncate">{c.customer_name}</div>
                                <div className="text-[11px] text-slate-500 truncate">
                                  {c.phone ? (
                                    <span className="text-emerald-700">📞 {c.phone}</span>
                                  ) : (
                                    <span className="text-amber-700">📞 not on file</span>
                                  )}
                                  {c.consumer_no && <> · CN: <span className="font-mono">{c.consumer_no}</span></>}
                                  {c.connection_type && <> · {c.connection_type}</>}
                                  {c.warehouse_name && <> · {c.warehouse_name}</>}
                                </div>
                              </div>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  {invForm.customer_id && (
                    <div className="flex items-center gap-3 flex-wrap text-xs text-slate-600">
                      <span>Customer ID: <span className="font-mono">{invForm.customer_id.slice(0, 8)}…</span></span>
                      {invForm.customer_consumer_no && <span>· Consumer No.: <span className="font-mono">{invForm.customer_consumer_no}</span></span>}
                      {invForm.customer_connection_type && <span>· Category: <span className="capitalize">{invForm.customer_connection_type}</span></span>}
                      <button
                        type="button"
                        onClick={clearCustomerLink}
                        className="text-red-600 hover:underline ml-auto"
                        data-testid="inv-customer-unlink"
                      >
                        Unlink
                      </button>
                    </div>
                  )}
                  {invForm.customer_id && !invForm.customer_phone && (
                    <div className="flex items-start gap-2 p-2 rounded bg-amber-50 border border-amber-200 text-xs" data-testid="inv-customer-phone-warning">
                      <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
                      <div className="flex-1">
                        <p className="text-amber-800 font-medium">Customer mobile number is not available in the Customer Database.</p>
                        <p className="text-amber-700 mt-0.5">
                          You can enter the phone manually below for this invoice, or
                          <a href="/customers" target="_blank" rel="noreferrer" className="text-blue-700 hover:underline ml-1">
                            update the Customer Master record →
                          </a>
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Customer block */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div>
                    <Label>Invoice Date *</Label>
                    <Input type="date" value={invForm.invoice_date} onChange={e => setInvForm({ ...invForm, invoice_date: e.target.value })} data-testid="inv-date" />
                  </div>
                  <div>
                    <Label>Memo No.</Label>
                    <Input
                      value={invForm.memo_no || ''}
                      placeholder="(optional — defaults to invoice no)"
                      onChange={e => setInvForm({ ...invForm, memo_no: e.target.value })}
                      data-testid="inv-memo-no"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <Label>Customer Name *</Label>
                    <Input value={invForm.customer_name} onChange={e => setInvForm({ ...invForm, customer_name: e.target.value })} data-testid="inv-customer-name" />
                  </div>
                  <div>
                    <Label>Phone</Label>
                    <Input value={invForm.customer_phone} onChange={e => setInvForm({ ...invForm, customer_phone: e.target.value })} data-testid="inv-customer-phone" />
                  </div>
                  <div className="md:col-span-2">
                    <Label>Address</Label>
                    <Input value={invForm.customer_address} onChange={e => setInvForm({ ...invForm, customer_address: e.target.value })} data-testid="inv-customer-address" />
                  </div>
                  <div>
                    <Label>Customer GSTIN</Label>
                    <Input value={invForm.customer_gstin} onChange={e => setInvForm({ ...invForm, customer_gstin: e.target.value.toUpperCase() })} data-testid="inv-customer-gstin" />
                  </div>
                  <div>
                    <Label>Payment Mode</Label>
                    <Select value={invForm.payment_mode} onValueChange={v => setInvForm({ ...invForm, payment_mode: v })}>
                      <SelectTrigger data-testid="inv-payment-mode"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="cash">Cash</SelectItem>
                        <SelectItem value="online">Online</SelectItem>
                        <SelectItem value="pending">Credit/Pending</SelectItem>
                        <SelectItem value="split">Split</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Cash Received</Label>
                    <Input
                      type="number" min="0" step="0.01"
                      value={invForm.cash_received ?? 0}
                      onChange={e => setInvForm({ ...invForm, cash_received: parseFloat(e.target.value) || 0 })}
                      data-testid="inv-cash-received"
                    />
                  </div>
                  <div>
                    <Label>Online Received</Label>
                    <Input
                      type="number" min="0" step="0.01"
                      value={invForm.online_received ?? 0}
                      onChange={e => setInvForm({ ...invForm, online_received: parseFloat(e.target.value) || 0 })}
                      data-testid="inv-online-received"
                    />
                  </div>
                  <div>
                    <Label>Tax Mode</Label>
                    <Select value={invForm.tax_mode} onValueChange={v => setInvForm({ ...invForm, tax_mode: v })}>
                      <SelectTrigger data-testid="inv-tax-mode"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="intra_state">Intra-state (CGST+SGST)</SelectItem>
                        <SelectItem value="inter_state">Inter-state (IGST)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Bill Type</Label>
                    <Select value={invForm.bill_type} onValueChange={v => setInvForm({ ...invForm, bill_type: v })}>
                      <SelectTrigger data-testid="inv-bill-type"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="new_connection">New Connection</SelectItem>
                        <SelectItem value="refill">Refill</SelectItem>
                        <SelectItem value="accessory">Accessory</SelectItem>
                        <SelectItem value="manual">Manual</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Line items */}
                <div>
                  <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                    <Label className="text-base">Line Items</Label>
                    <div className="flex gap-2 items-center">
                      <Select value="" onValueChange={loadInvoiceFromPlan}>
                        <SelectTrigger className="w-64 h-9" data-testid="load-from-plan-select">
                          <SelectValue placeholder="Load from Connection Plan..." />
                        </SelectTrigger>
                        <SelectContent>
                          {plans.filter(p => p.is_active).map(p => (
                            <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button size="sm" variant="outline" onClick={addLineItem} data-testid="add-line-item-btn">
                        <Plus className="w-4 h-4 mr-1" /> Add Line
                      </Button>
                    </div>
                  </div>
                  <div className="overflow-x-auto border rounded">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-50">
                        <tr>
                          <th className="text-left p-2">Item</th>
                          <th className="text-left p-2 w-24">HSN</th>
                          <th className="text-left p-2 w-20">Unit</th>
                          <th className="text-right p-2 w-20">Qty</th>
                          <th className="text-right p-2 w-24">Rate</th>
                          <th className="text-right p-2 w-16">GST%</th>
                          <th className="text-right p-2 w-24">Total</th>
                          <th className="w-8"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {invForm.line_items.map((li, idx) => {
                          const qty = Number(li.quantity) || 0;
                          const rate = Number(li.rate) || 0;
                          const gst = Number(li.gst_rate) || 0;
                          const lineTotal = qty * rate * (1 + gst / 100);
                          return (
                            <tr key={idx} className="border-t">
                              <td className="p-1">
                                <div className="flex gap-1">
                                  <Select value={li.item_id || ''} onValueChange={(v) => setLineItemFromMaster(idx, v)}>
                                    <SelectTrigger className="h-8 w-32"><SelectValue placeholder="Master" /></SelectTrigger>
                                    <SelectContent>
                                      {items.filter(i => i.is_active).map(i => (
                                        <SelectItem key={i.id} value={i.id}>{i.name}</SelectItem>
                                      ))}
                                    </SelectContent>
                                  </Select>
                                  <Input className="h-8" placeholder="or custom name" value={li.item_name} onChange={e => updateLineItem(idx, 'item_name', e.target.value)} data-testid={`line-name-${idx}`} />
                                </div>
                              </td>
                              <td className="p-1"><Input className="h-8" value={li.hsn || ''} onChange={e => updateLineItem(idx, 'hsn', e.target.value)} /></td>
                              <td className="p-1"><Input className="h-8" value={li.unit || ''} onChange={e => updateLineItem(idx, 'unit', e.target.value)} /></td>
                              <td className="p-1"><Input className="h-8 text-right" type="number" value={li.quantity} onChange={e => updateLineItem(idx, 'quantity', e.target.value)} data-testid={`line-qty-${idx}`} /></td>
                              <td className="p-1"><Input className="h-8 text-right" type="number" value={li.rate} onChange={e => updateLineItem(idx, 'rate', e.target.value)} data-testid={`line-rate-${idx}`} /></td>
                              <td className="p-1"><Input className="h-8 text-right" type="number" value={li.gst_rate} onChange={e => updateLineItem(idx, 'gst_rate', e.target.value)} /></td>
                              <td className="p-2 text-right">{formatRs(lineTotal)}</td>
                              <td className="p-1">
                                <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => removeLineItem(idx)}>
                                  <Trash2 className="w-3 h-3 text-red-600" />
                                </Button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Preview totals */}
                <div className="bg-slate-50 p-3 rounded grid grid-cols-2 md:grid-cols-6 gap-2 text-sm">
                  <div><span className="text-slate-500">Sub Total:</span> <strong>{formatRs(preview.sub_total)}</strong></div>
                  <div><span className="text-slate-500">CGST:</span> <strong>{formatRs(preview.total_cgst)}</strong></div>
                  <div><span className="text-slate-500">SGST:</span> <strong>{formatRs(preview.total_sgst)}</strong></div>
                  <div><span className="text-slate-500">IGST:</span> <strong>{formatRs(preview.total_igst)}</strong></div>
                  <div>
                    <span className="text-slate-500">Round Off:</span>{' '}
                    <strong className={preview.round_off >= 0 ? 'text-green-700' : 'text-amber-700'}>
                      {preview.round_off >= 0 ? '+ ' : '− '}{formatRs(Math.abs(preview.round_off))}
                    </strong>
                  </div>
                  <div className="text-blue-700"><span className="text-slate-500">Grand Total:</span> <strong>{formatRs(preview.grand_total)}</strong></div>
                </div>

                <div>
                  <Label>Remarks</Label>
                  <Textarea value={invForm.remarks || ''} onChange={e => setInvForm({ ...invForm, remarks: e.target.value })} />
                </div>
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => { setShowInvoiceDialog(false); setInvForm(null); setEditingInvoice(null); }}>Cancel</Button>
                <Button onClick={handleSaveInvoice} className="bg-blue-700 hover:bg-blue-800" data-testid="save-invoice-btn">
                  {editingInvoice ? 'Update Invoice' : 'Create Invoice'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}

        {/* VIEW INVOICE DIALOG - Print-Preview Style */}
        {viewingInvoice && (
          <Dialog open={showViewDialog} onOpenChange={(o) => { setShowViewDialog(o); if (!o) setViewingInvoice(null); }}>
            <DialogContent className="w-[95vw] sm:max-w-5xl max-h-[92vh] overflow-y-auto p-0 print:max-w-full print:max-h-none print:overflow-visible" data-testid="view-dialog">
              <div className="sticky top-0 z-10 bg-white border-b px-6 py-3 flex flex-wrap items-center justify-between gap-2 print:hidden">
                <div>
                  <DialogTitle className="text-base">
                    Invoice {viewingInvoice.invoice_number}
                    {viewingInvoice.status === 'cancelled' && <Badge className="bg-red-100 text-red-700 ml-2">CANCELLED</Badge>}
                  </DialogTitle>
                  <DialogDescription className="text-xs">Tax Invoice — Print preview</DialogDescription>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => window.print()} data-testid="view-print-btn">
                    <FileText className="w-4 h-4 mr-1" /> Print
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => handlePdf(viewingInvoice)} data-testid="view-pdf-btn">
                    <FileDown className="w-4 h-4 mr-1" /> Download PDF
                  </Button>
                  {viewingInvoice.status === 'active' && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => { setShowViewDialog(false); openInvoiceDialog(viewingInvoice); }} data-testid="view-edit-btn">
                        <Edit2 className="w-4 h-4 mr-1" /> Edit
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => { setShowViewDialog(false); setCancelTarget(viewingInvoice); setShowCancelDialog(true); }} data-testid="view-cancel-btn">
                        <XCircle className="w-4 h-4 mr-1 text-red-600" /> Cancel
                      </Button>
                    </>
                  )}
                  <Button size="sm" onClick={() => { setShowViewDialog(false); setViewingInvoice(null); }}>Close</Button>
                </div>
              </div>

              {/* Print-preview body */}
              <div className="bg-white px-4 sm:px-8 py-6 print:px-0 print:py-0" id="invoice-print-area">
                {/* Company header */}
                <div className="flex flex-col sm:flex-row gap-4 items-start border-b-2 border-blue-700 pb-4">
                  {config.company_logo_url && (
                    <img src={config.company_logo_url} alt="logo" className="h-20 w-20 object-contain" onError={(e) => { e.target.style.display = 'none'; }} />
                  )}
                  <div className="flex-1 min-w-0">
                    <h2 className="text-2xl font-bold text-blue-800 break-words">{config.company_name || 'K3 GAS SERVICE'}</h2>
                    {config.company_tagline && <p className="text-xs italic text-slate-600">{config.company_tagline}</p>}
                    {config.company_address && <p className="text-xs text-slate-700 mt-1 whitespace-pre-line">{config.company_address}</p>}
                    <div className="text-xs text-slate-700 mt-1 flex flex-wrap gap-x-3 gap-y-1">
                      {config.company_phone && <span><strong>Phone:</strong> {config.company_phone}</span>}
                      {config.company_email && <span><strong>Email:</strong> {config.company_email}</span>}
                    </div>
                    {config.company_gstin && (
                      <p className="text-xs text-slate-700 mt-1">
                        <strong>GSTIN:</strong> {config.company_gstin} &nbsp; <strong>State:</strong> {config.company_state} ({config.company_state_code})
                      </p>
                    )}
                  </div>
                </div>

                {viewingInvoice.status === 'cancelled' && (
                  <div className="bg-red-50 border border-red-300 text-red-700 text-center py-2 font-bold text-sm my-3">
                    ** THIS INVOICE HAS BEEN CANCELLED **
                  </div>
                )}

                <div className="text-center my-3">
                  <h3 className="text-lg font-bold text-blue-800 bg-blue-50 inline-block px-6 py-1 border border-blue-200 rounded">
                    TAX INVOICE
                  </h3>
                </div>

                {/* Meta + Customer */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 border border-slate-300 rounded text-xs">
                  <div className="p-3 border-r border-slate-300">
                    <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
                      <strong>Invoice No:</strong><span className="break-all">{viewingInvoice.invoice_number}</span>
                      <strong>Invoice Date:</strong><span>{viewingInvoice.invoice_date}</span>
                      <strong>Place of Supply:</strong><span>{viewingInvoice.place_of_supply || config.place_of_supply || '-'}</span>
                      <strong>Tax Mode:</strong><span>{viewingInvoice.tax_mode === 'intra_state' ? 'Intra-state (CGST+SGST)' : 'Inter-state (IGST)'}</span>
                      <strong>Payment:</strong><span className="uppercase">{viewingInvoice.payment_mode || '-'}</span>
                    </div>
                  </div>
                  <div className="p-3">
                    <div className="font-semibold text-slate-500 text-[10px] uppercase mb-1">Bill To</div>
                    <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
                      <strong>Name:</strong><span className="break-words">{viewingInvoice.customer_name}</span>
                      <strong>Address:</strong><span className="break-words">{viewingInvoice.customer_address || '-'}</span>
                      <strong>Mobile:</strong>
                      <span data-testid="view-customer-phone" className={viewingInvoice.customer_phone ? '' : 'text-amber-700'}>
                        {viewingInvoice.customer_phone || 'Not available in Customer DB'}
                      </span>
                      {viewingInvoice.customer_consumer_no && (
                        <>
                          <strong>Consumer No.:</strong>
                          <span className="font-mono" data-testid="view-customer-consumer-no">{viewingInvoice.customer_consumer_no}</span>
                        </>
                      )}
                      {viewingInvoice.customer_connection_type && (
                        <>
                          <strong>Category:</strong>
                          <span className="capitalize" data-testid="view-customer-connection-type">{viewingInvoice.customer_connection_type}</span>
                        </>
                      )}
                      <strong>GSTIN:</strong><span>{viewingInvoice.customer_gstin || '-'}</span>
                      <strong>Warehouse:</strong><span>{viewingInvoice.warehouse_name || '-'}</span>
                    </div>
                  </div>
                </div>

                {/* Items table */}
                <div className="overflow-x-auto mt-3 border border-slate-300 rounded">
                  <table className="w-full text-[11px]">
                    <thead className="bg-blue-700 text-white">
                      <tr>
                        <th className="p-2 text-center">#</th>
                        <th className="p-2 text-left">Item Description</th>
                        <th className="p-2 text-center">HSN</th>
                        <th className="p-2 text-center">Unit</th>
                        <th className="p-2 text-right">Qty</th>
                        <th className="p-2 text-right">Rate</th>
                        <th className="p-2 text-right">Taxable</th>
                        {viewingInvoice.tax_mode === 'intra_state' ? (
                          <>
                            <th className="p-2 text-right">CGST</th>
                            <th className="p-2 text-right">SGST</th>
                          </>
                        ) : (
                          <th className="p-2 text-right">IGST</th>
                        )}
                        <th className="p-2 text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(viewingInvoice.line_items || []).map((li, idx) => (
                        <tr key={idx} className="border-t border-slate-200 align-top">
                          <td className="p-2 text-center">{idx + 1}</td>
                          <td className="p-2 break-words max-w-[260px]">{li.item_name}</td>
                          <td className="p-2 text-center font-mono">{li.hsn}</td>
                          <td className="p-2 text-center">{li.unit}</td>
                          <td className="p-2 text-right">{li.quantity}</td>
                          <td className="p-2 text-right">{Number(li.rate).toFixed(2)}</td>
                          <td className="p-2 text-right">{Number(li.taxable_value).toFixed(2)}</td>
                          {viewingInvoice.tax_mode === 'intra_state' ? (
                            <>
                              <td className="p-2 text-right">{Number(li.cgst).toFixed(2)} <span className="text-slate-400 text-[9px]">({li.gst_rate / 2}%)</span></td>
                              <td className="p-2 text-right">{Number(li.sgst).toFixed(2)} <span className="text-slate-400 text-[9px]">({li.gst_rate / 2}%)</span></td>
                            </>
                          ) : (
                            <td className="p-2 text-right">{Number(li.igst).toFixed(2)} <span className="text-slate-400 text-[9px]">({li.gst_rate}%)</span></td>
                          )}
                          <td className="p-2 text-right font-semibold">{Number(li.line_total).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-blue-50 font-semibold">
                      <tr className="border-t-2 border-blue-300">
                        <td colSpan={viewingInvoice.tax_mode === 'intra_state' ? 6 : 6} className="p-2 text-right">TOTAL</td>
                        <td className="p-2 text-right">{Number(viewingInvoice.sub_total).toFixed(2)}</td>
                        {viewingInvoice.tax_mode === 'intra_state' ? (
                          <>
                            <td className="p-2 text-right">{Number(viewingInvoice.total_cgst).toFixed(2)}</td>
                            <td className="p-2 text-right">{Number(viewingInvoice.total_sgst).toFixed(2)}</td>
                          </>
                        ) : (
                          <td className="p-2 text-right">{Number(viewingInvoice.total_igst).toFixed(2)}</td>
                        )}
                        <td className="p-2 text-right text-blue-800">{Number(viewingInvoice.grand_total).toFixed(2)}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>

                {/* Amount in Words + Summary */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
                  <div className="md:col-span-2 border border-slate-300 rounded p-3 text-xs">
                    <strong>Amount in Words:</strong>{' '}
                    <span className="italic">{amountInWords(viewingInvoice.grand_total)}</span>
                  </div>
                  <div className="border border-slate-300 rounded p-3 text-xs space-y-1">
                    <div className="flex justify-between"><span>Sub Total:</span><strong>{formatRs(viewingInvoice.sub_total)}</strong></div>
                    {viewingInvoice.tax_mode === 'intra_state' ? (
                      <>
                        <div className="flex justify-between"><span>CGST:</span><strong>{formatRs(viewingInvoice.total_cgst)}</strong></div>
                        <div className="flex justify-between"><span>SGST:</span><strong>{formatRs(viewingInvoice.total_sgst)}</strong></div>
                      </>
                    ) : (
                      <div className="flex justify-between"><span>IGST:</span><strong>{formatRs(viewingInvoice.total_igst)}</strong></div>
                    )}
                    {viewingInvoice.round_off != null && (
                      <>
                        <div className="flex justify-between border-t border-slate-200 pt-1 mt-1">
                          <span>Total Before Round Off:</span>
                          <strong>{formatRs(viewingInvoice.total_before_roundoff ?? (Number(viewingInvoice.grand_total) - Number(viewingInvoice.round_off || 0)))}</strong>
                        </div>
                        <div className="flex justify-between">
                          <span>Round Off:</span>
                          <strong className={Number(viewingInvoice.round_off) >= 0 ? 'text-green-700' : 'text-amber-700'}>
                            {Number(viewingInvoice.round_off) >= 0 ? '+ ' : '− '}{formatRs(Math.abs(Number(viewingInvoice.round_off)))}
                          </strong>
                        </div>
                      </>
                    )}
                    <div className="flex justify-between bg-blue-50 -mx-3 px-3 py-1 mt-2 font-bold text-blue-800 border-t border-blue-200">
                      <span>Grand Total:</span><strong>{formatRs(viewingInvoice.grand_total)}</strong>
                    </div>
                    {(viewingInvoice.payment_status || Number(viewingInvoice.cash_received || 0) > 0 || Number(viewingInvoice.online_received || 0) > 0 || Number(viewingInvoice.pending_amount || 0) > 0) && (
                      <div className="mt-2 pt-2 border-t border-slate-200 space-y-1" data-testid="view-payment-block">
                        <div className="flex justify-between"><span>Cash Received:</span><span>{formatRs(viewingInvoice.cash_received || 0)}</span></div>
                        <div className="flex justify-between"><span>Online Received:</span><span>{formatRs(viewingInvoice.online_received || 0)}</span></div>
                        <div className="flex justify-between"><span>Pending Amount:</span><strong className="text-amber-700">{formatRs(viewingInvoice.pending_amount || 0)}</strong></div>
                        <div className="flex justify-between items-center pt-1">
                          <span>Payment Status:</span>
                          {viewingInvoice.payment_status === 'Paid' && <Badge className="bg-green-100 text-green-700">Paid</Badge>}
                          {viewingInvoice.payment_status === 'Partial' && <Badge className="bg-amber-100 text-amber-700">Partial</Badge>}
                          {viewingInvoice.payment_status === 'Pending' && <Badge className="bg-red-100 text-red-700">Pending</Badge>}
                          {!viewingInvoice.payment_status && <Badge variant="outline">—</Badge>}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Bank + Terms + Signatory */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3 text-xs">
                  <div className="border border-slate-300 rounded p-3">
                    <div className="font-bold text-slate-700 mb-1">Bank Details</div>
                    {config.bank_name ? (
                      <div className="space-y-0.5">
                        <div><strong>Bank:</strong> {config.bank_name}</div>
                        {config.bank_account_holder && <div><strong>A/c Holder:</strong> {config.bank_account_holder}</div>}
                        {config.bank_account_no && <div><strong>A/c No:</strong> {config.bank_account_no}</div>}
                        {config.bank_ifsc && <div><strong>IFSC:</strong> {config.bank_ifsc}</div>}
                        {config.bank_branch && <div><strong>Branch:</strong> {config.bank_branch}</div>}
                      </div>
                    ) : <span className="text-slate-400 italic">Not configured (Settings → Bank)</span>}
                  </div>
                  <div className="border border-slate-300 rounded p-3">
                    <div className="font-bold text-slate-700 mb-1">Terms &amp; Conditions</div>
                    {config.terms_conditions ? (
                      <div className="space-y-0.5 whitespace-pre-line text-[10px] text-slate-600">{config.terms_conditions}</div>
                    ) : <span className="text-slate-400 italic">Not configured</span>}
                    {viewingInvoice.remarks && (
                      <div className="mt-2 pt-2 border-t border-slate-200">
                        <strong>Remarks:</strong> {viewingInvoice.remarks}
                      </div>
                    )}
                  </div>
                  <div className="border border-slate-300 rounded p-3 flex flex-col items-end">
                    <div className="text-slate-700 text-xs mb-1">For <strong>{config.company_name}</strong></div>
                    <div className="h-14"></div>
                    <div className="text-right">
                      <div className="font-semibold">{config.signatory_name || '__________'}</div>
                      <div className="italic text-slate-500 text-[10px]">{config.signatory_designation || 'Authorized Signatory'}</div>
                    </div>
                  </div>
                </div>

                {viewingInvoice.status === 'cancelled' && (
                  <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2 mt-3">
                    <strong>Cancellation:</strong> {viewingInvoice.cancellation_reason || 'No reason given'} · {viewingInvoice.cancelled_at?.slice(0, 10)} · by {viewingInvoice.cancelled_by_name || '-'}
                  </div>
                )}

                <div className="text-center text-[9px] text-slate-400 mt-4 print:mt-2">
                  Computer-generated invoice. Subject to {config.company_state || 'Arunachal Pradesh'} jurisdiction.
                </div>
              </div>
            </DialogContent>
          </Dialog>
        )}

        {/* ITEM DIALOG */}
        {editingItem && (
          <Dialog open={showItemDialog} onOpenChange={(o) => { setShowItemDialog(o); if (!o) setEditingItem(null); }}>
            <DialogContent className="w-[95vw] sm:max-w-md max-h-[90vh] overflow-y-auto" data-testid="item-dialog">
              <DialogHeader>
                <DialogTitle>{editingItem.id ? 'Edit Item' : 'New Item'}</DialogTitle>
              </DialogHeader>
              <div className="space-y-3">
                <div>
                  <Label>Name *</Label>
                  <Input value={editingItem.name} onChange={e => setEditingItem({ ...editingItem, name: e.target.value })} data-testid="item-name" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>HSN Code</Label>
                    <Input value={editingItem.hsn || ''} onChange={e => setEditingItem({ ...editingItem, hsn: e.target.value })} />
                  </div>
                  <div>
                    <Label>Unit</Label>
                    <Input value={editingItem.unit || ''} onChange={e => setEditingItem({ ...editingItem, unit: e.target.value })} />
                  </div>
                  <div>
                    <Label>GST Rate (%)</Label>
                    <Input type="number" value={editingItem.gst_rate} onChange={e => setEditingItem({ ...editingItem, gst_rate: e.target.value })} />
                  </div>
                  <div>
                    <Label>Default Rate (Rs.)</Label>
                    <Input type="number" value={editingItem.default_rate || 0} onChange={e => setEditingItem({ ...editingItem, default_rate: e.target.value })} />
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => { setShowItemDialog(false); setEditingItem(null); }}>Cancel</Button>
                <Button onClick={handleSaveItem} data-testid="save-item-btn">Save</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}

        {/* PLAN DIALOG */}
        {editingPlan && (
          <Dialog open={showPlanDialog} onOpenChange={(o) => { setShowPlanDialog(o); if (!o) setEditingPlan(null); }}>
            <DialogContent className="w-[95vw] sm:max-w-5xl max-h-[90vh] overflow-y-auto" data-testid="plan-dialog">
              <DialogHeader>
                <DialogTitle>{editingPlan.id ? `Edit Plan: ${editingPlan.name}` : 'New Connection Plan'}</DialogTitle>
                <DialogDescription>Set unit prices for each item. Plans with all rates set will auto-itemize matching new-connection invoices.</DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="md:col-span-2">
                    <Label>Plan Name *</Label>
                    <Input value={editingPlan.name} onChange={e => setEditingPlan({ ...editingPlan, name: e.target.value })} data-testid="plan-name" />
                  </div>
                  <div>
                    <Label>Connection Type</Label>
                    <Select value={editingPlan.connection_type} onValueChange={v => setEditingPlan({ ...editingPlan, connection_type: v })}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="domestic">Domestic</SelectItem>
                        <SelectItem value="commercial">Commercial</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Cylinder Count</Label>
                    <Input type="number" value={editingPlan.cylinder_count} onChange={e => setEditingPlan({ ...editingPlan, cylinder_count: e.target.value })} />
                  </div>
                  <div>
                    <Label>Plan Code</Label>
                    <Input value={editingPlan.plan_type || ''} onChange={e => setEditingPlan({ ...editingPlan, plan_type: e.target.value })} />
                  </div>
                  <div className="flex items-end gap-2">
                    <input
                      type="checkbox"
                      id="plan-acc"
                      checked={!!editingPlan.has_accessories}
                      onChange={e => setEditingPlan({ ...editingPlan, has_accessories: e.target.checked })}
                      data-testid="plan-accessories"
                    />
                    <Label htmlFor="plan-acc" className="cursor-pointer">Includes Accessories (Stove Burner etc.)</Label>
                  </div>
                  <div className="flex items-end gap-2">
                    <input
                      type="checkbox"
                      id="plan-active"
                      checked={!!editingPlan.is_active}
                      onChange={e => setEditingPlan({ ...editingPlan, is_active: e.target.checked })}
                    />
                    <Label htmlFor="plan-active" className="cursor-pointer">Active</Label>
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-base">Plan Items</Label>
                    <Button size="sm" variant="outline" onClick={addPlanItem} data-testid="add-plan-item-btn">
                      <Plus className="w-4 h-4 mr-1" /> Add Item
                    </Button>
                  </div>
                  <div className="overflow-x-auto border rounded">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-50">
                        <tr>
                          <th className="text-left p-2 min-w-[200px]">Item (synced from Master)</th>
                          <th className="text-left p-2 w-20">HSN</th>
                          <th className="text-left p-2 w-16">Unit</th>
                          <th className="text-right p-2 w-16">Qty</th>
                          <th className="text-right p-2 w-24">Unit Price *</th>
                          <th className="text-right p-2 w-16">GST%</th>
                          <th className="text-right p-2 w-20">Line Total</th>
                          <th className="w-8"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {editingPlan.items.map((it, idx) => {
                          const q = Number(it.quantity) || 0;
                          const r = Number(it.unit_price) || 0;
                          const g = Number(it.gst_rate) || 0;
                          const total = q * r * (1 + g / 100);
                          // Look up the master entry for this row (if linked)
                          const linkedMaster = items.find(m => m.id === it.item_id);
                          const isLinked = !!linkedMaster;
                          const isInactive = isLinked && linkedMaster.is_active === false;
                          return (
                            <tr key={idx} className={`border-t ${isInactive ? 'bg-amber-50' : ''}`}>
                              <td className="p-1">
                                <Select value={it.item_id || ''} onValueChange={(v) => selectMasterForPlanItem(idx, v)}>
                                  <SelectTrigger className="h-8" data-testid={`plan-line-master-${idx}`}>
                                    <SelectValue placeholder="Pick from Item Master..." />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {items.filter(m => m.is_active || m.id === it.item_id).map(m => (
                                      <SelectItem key={m.id} value={m.id}>
                                        {m.name}{m.is_active === false ? ' (Inactive)' : ''}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                                {!isLinked && (
                                  <Input className="h-7 mt-1 text-[10px]" placeholder="or custom name (not synced)"
                                         value={it.item_name} onChange={e => updatePlanItem(idx, 'item_name', e.target.value)}
                                         data-testid={`plan-line-name-${idx}`} />
                                )}
                                {isInactive && (
                                  <p className="text-[10px] text-amber-700 mt-1">⚠ Master item is Inactive – kept for history</p>
                                )}
                              </td>
                              <td className="p-1">
                                <Input className="h-8" value={it.hsn || ''}
                                       onChange={e => updatePlanItem(idx, 'hsn', e.target.value)}
                                       readOnly={isLinked} title={isLinked ? 'Synced from master' : ''} />
                              </td>
                              <td className="p-1">
                                <Input className="h-8" value={it.unit || ''}
                                       onChange={e => updatePlanItem(idx, 'unit', e.target.value)}
                                       readOnly={isLinked} title={isLinked ? 'Synced from master' : ''} />
                              </td>
                              <td className="p-1">
                                <Input className="h-8 text-right" type="number" value={it.quantity}
                                       onChange={e => updatePlanItem(idx, 'quantity', e.target.value)} />
                              </td>
                              <td className="p-1">
                                <Input className="h-8 text-right" type="number" value={it.unit_price || 0}
                                       onChange={e => updatePlanItem(idx, 'unit_price', e.target.value)}
                                       data-testid={`plan-line-price-${idx}`} />
                              </td>
                              <td className="p-1">
                                <Input className="h-8 text-right" type="number" value={it.gst_rate}
                                       onChange={e => updatePlanItem(idx, 'gst_rate', e.target.value)}
                                       readOnly={isLinked} title={isLinked ? 'Synced from master' : ''} />
                              </td>
                              <td className="p-2 text-right">{formatRs(total)}</td>
                              <td className="p-1">
                                <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => removePlanItem(idx)}>
                                  <Trash2 className="w-3 h-3 text-red-600" />
                                </Button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                      <tfoot className="bg-slate-100">
                        <tr>
                          <td colSpan="6" className="p-2 text-right font-semibold">Total Plan Value (with GST):</td>
                          <td className="p-2 text-right font-bold text-blue-700">
                            {formatRs(editingPlan.items.reduce((s, it) => {
                              const q = Number(it.quantity) || 0, r = Number(it.unit_price) || 0, g = Number(it.gst_rate) || 0;
                              return s + q * r * (1 + g / 100);
                            }, 0))}
                          </td>
                          <td></td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => { setShowPlanDialog(false); setEditingPlan(null); }}>Cancel</Button>
                <Button onClick={handleSavePlan} className="bg-blue-700 hover:bg-blue-800" data-testid="save-plan-btn">Save Plan</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}

        {/* BULK UPLOAD DIALOG */}
        <Dialog open={showBulkUploadDialog} onOpenChange={setShowBulkUploadDialog}>
          <DialogContent className="sm:max-w-2xl" data-testid="bulk-upload-dialog">
            <DialogHeader>
              <DialogTitle>Bulk Update Item Master</DialogTitle>
              <DialogDescription>
                Upload the filled Excel/CSV template. Existing rows (with id) are updated, blank-id rows are created. Rate changes are recorded in history with the effective date below.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="bulk-file">Excel / CSV File</Label>
                  <Input
                    id="bulk-file"
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    onChange={(e) => setBulkFile(e.target.files?.[0] || null)}
                    data-testid="bulk-upload-file"
                  />
                  {bulkFile && <p className="text-xs text-slate-500 mt-1">{bulkFile.name} • {(bulkFile.size / 1024).toFixed(1)} KB</p>}
                </div>
                <div>
                  <Label htmlFor="bulk-eff-from">Effective From (default)</Label>
                  <Input
                    id="bulk-eff-from"
                    type="date"
                    value={bulkEffectiveFrom}
                    onChange={(e) => setBulkEffectiveFrom(e.target.value)}
                    data-testid="bulk-upload-effective-from"
                  />
                  <p className="text-xs text-slate-500 mt-1">Applied to rows where effective_from column is blank.</p>
                </div>
              </div>

              <div className="bg-slate-50 border rounded p-3 text-xs space-y-1">
                <p className="font-medium text-slate-700">Template columns:</p>
                <p className="text-slate-600">id (blank = create), name, hsn, unit, gst_rate, default_rate, is_active (active/inactive), effective_from (YYYY-MM-DD, optional)</p>
                <Button size="sm" variant="link" className="px-0 h-auto" onClick={handleDownloadTemplate} data-testid="bulk-download-template-link">
                  Download a pre-filled template →
                </Button>
              </div>

              {bulkResult && (
                <div className="border rounded p-3 text-sm" data-testid="bulk-upload-result">
                  <p className="font-medium mb-2">Result</p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-2">
                    <Badge className="bg-green-100 text-green-700">Created: {bulkResult.created}</Badge>
                    <Badge className="bg-blue-100 text-blue-700">Updated: {bulkResult.updated}</Badge>
                    <Badge className="bg-amber-100 text-amber-700">Rate changes: {bulkResult.rate_changes}</Badge>
                    <Badge variant="outline">Skipped: {bulkResult.skipped}</Badge>
                  </div>
                  {bulkResult.errors?.length > 0 && (
                    <div className="max-h-32 overflow-y-auto text-xs">
                      <p className="text-red-700 font-medium mb-1">Errors:</p>
                      <ul className="list-disc list-inside text-red-600 space-y-0.5">
                        {bulkResult.errors.slice(0, 20).map((er, i) => (
                          <li key={i}>Row {er.row}: {er.error}</li>
                        ))}
                        {bulkResult.errors.length > 20 && <li>... and {bulkResult.errors.length - 20} more</li>}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowBulkUploadDialog(false)} data-testid="bulk-upload-cancel">Close</Button>
              <Button
                onClick={handleBulkUpload}
                disabled={!bulkFile || bulkUploading}
                className="bg-blue-700 hover:bg-blue-800"
                data-testid="bulk-upload-submit"
              >
                {bulkUploading ? 'Uploading…' : 'Upload & Apply'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* RATE HISTORY DIALOG */}
        <Dialog open={showHistoryDialog} onOpenChange={setShowHistoryDialog}>
          <DialogContent className="sm:max-w-5xl" data-testid="rate-history-dialog">
            <DialogHeader>
              <DialogTitle>Item Rate History</DialogTitle>
              <DialogDescription>
                Read-only audit of rate / status / GST changes. Historical invoices are unaffected by future rate updates.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                <div>
                  <Label>Item</Label>
                  <Select value={histItemId} onValueChange={setHistItemId}>
                    <SelectTrigger data-testid="history-item-filter"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All items</SelectItem>
                      {items.map(it => (
                        <SelectItem key={it.id} value={it.id}>{it.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>From</Label>
                  <Input type="date" value={histStart} onChange={(e) => setHistStart(e.target.value)} data-testid="history-start-date" />
                </div>
                <div>
                  <Label>To</Label>
                  <Input type="date" value={histEnd} onChange={(e) => setHistEnd(e.target.value)} data-testid="history-end-date" />
                </div>
                <div className="flex items-end gap-2">
                  <Button variant="outline" onClick={loadHistory} disabled={historyLoading} data-testid="history-apply-filter">
                    <RefreshCw className="w-4 h-4 mr-1" /> Apply
                  </Button>
                  <Button onClick={handleDownloadHistoryExcel} className="bg-emerald-700 hover:bg-emerald-800" data-testid="history-download-excel">
                    <FileSpreadsheet className="w-4 h-4 mr-1" /> Excel
                  </Button>
                </div>
              </div>

              <div className="border rounded max-h-[55vh] overflow-auto">
                <table className="w-full text-xs">
                  <thead className="bg-slate-50 border-b sticky top-0">
                    <tr>
                      <th className="text-left p-2 font-medium">Item</th>
                      <th className="text-left p-2 font-medium">HSN</th>
                      <th className="text-right p-2 font-medium">Prev Rate</th>
                      <th className="text-right p-2 font-medium">New Rate</th>
                      <th className="text-right p-2 font-medium">GST %</th>
                      <th className="text-center p-2 font-medium">Status</th>
                      <th className="text-left p-2 font-medium">Effective From</th>
                      <th className="text-left p-2 font-medium">Updated By</th>
                      <th className="text-left p-2 font-medium">Reason</th>
                      <th className="text-left p-2 font-medium">Updated At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!historyLoading && historyRows.length > 0 && historyRows.map((r, i) => (
                      <tr key={i} className="border-b hover:bg-slate-50" data-testid={`history-row-${i}`}>
                        <td className="p-2 font-medium">{r.item_name}</td>
                        <td className="p-2 font-mono">{r.hsn || '-'}</td>
                        <td className="p-2 text-right">{formatRs(r.prev_rate)}</td>
                        <td className="p-2 text-right font-semibold">{formatRs(r.new_rate)}</td>
                        <td className="p-2 text-right">{r.gst_rate}%</td>
                        <td className="p-2 text-center">
                          {r.is_active
                            ? <Badge className="bg-green-100 text-green-700">Active</Badge>
                            : <Badge variant="outline">Inactive</Badge>}
                        </td>
                        <td className="p-2">{r.effective_from}</td>
                        <td className="p-2">{r.updated_by_name || r.updated_by || '-'}</td>
                        <td className="p-2 text-slate-600">{r.reason || '-'}</td>
                        <td className="p-2 text-slate-500">{r.updated_at ? new Date(r.updated_at).toLocaleString() : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {historyLoading && (
                  <div className="p-4 text-center text-slate-500" data-testid="history-loading">Loading…</div>
                )}
                {!historyLoading && historyRows.length === 0 && (
                  <div className="p-4 text-center text-slate-500" data-testid="history-empty">No history found for the selected filters.</div>
                )}
              </div>
              <p className="text-xs text-slate-500">Showing {historyRows.length} record(s).</p>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowHistoryDialog(false)} data-testid="history-close">Close</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default GSTBilling;
