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
import { toast } from 'sonner';
import {
  Receipt, Search, Plus, FileDown, FileSpreadsheet, Settings as SettingsIcon,
  Edit2, XCircle, Trash2, Eye, RefreshCw, ChevronLeft, ChevronRight, FileText, AlertCircle
} from 'lucide-react';
import {
  getGstInvoices, getGstSummary, getGstConfig, updateGstConfig,
  getGstItems, createGstItem, updateGstItem, deleteGstItem,
  getGstPlans, createGstPlan, updateGstPlan, deleteGstPlan,
  createGstInvoice, updateGstInvoice, cancelGstInvoice, deleteGstInvoice,
  generateGstFromSale, downloadGstInvoicePdf, exportGstInvoicesExcel,
  getSalesEntries, getAccessorySales
} from '../lib/api';

const formatRs = (n) => {
  const num = Number(n) || 0;
  return 'Rs. ' + num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const todayISO = () => new Date().toISOString().split('T')[0];
const monthStartISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
};

const GSTBilling = () => {
  const { user, isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState('invoices');

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [billTypeFilter, setBillTypeFilter] = useState('all');
  const [startDate, setStartDate] = useState(monthStartISO());
  const [endDate, setEndDate] = useState(todayISO());
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

  // Manual invoice form state
  const [invForm, setInvForm] = useState(null);

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
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      const { data } = await getGstInvoices(params);
      setInvoices(data.invoices || []);
      setTotalPages(data.pages || 1);
      setTotalInvoices(data.total || 0);
    } catch (e) {
      toast.error('Failed to load invoices');
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, billTypeFilter, startDate, endDate, redirectIfNotAdmin]);

  const loadSummary = useCallback(async () => {
    if (redirectIfNotAdmin()) return;
    try {
      const { data } = await getGstSummary({ start_date: startDate, end_date: endDate });
      setSummary(data || {});
    } catch (e) { /* swallow */ }
  }, [startDate, endDate, redirectIfNotAdmin]);

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

  useEffect(() => {
    loadInvoices();
    loadSummary();
  }, [loadInvoices, loadSummary]);

  useEffect(() => {
    loadConfig();
    loadItems();
    loadPlans();
  }, [loadConfig, loadItems, loadPlans]);

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
      await exportGstInvoicesExcel({
        search: search || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        start_date: startDate,
        end_date: endDate,
      });
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
        customer_name: '',
        customer_phone: '',
        customer_address: '',
        customer_gstin: '',
        tax_mode: config.default_tax_mode || 'intra_state',
        payment_mode: 'cash',
        bill_type: 'manual',
        place_of_supply: config.place_of_supply || '',
        remarks: '',
        line_items: [emptyLineItem()],
      });
    }
    setShowInvoiceDialog(true);
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
    if (!invForm) return { sub_total: 0, total_cgst: 0, total_sgst: 0, total_igst: 0, total_gst: 0, grand_total: 0 };
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
    return {
      sub_total: sub,
      total_cgst: cgst,
      total_sgst: sgst,
      total_igst: igst,
      total_gst: cgst + sgst + igst,
      grand_total: sub + cgst + sgst + igst,
    };
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
      if (editingInvoice) {
        await updateGstInvoice(editingInvoice.id, invForm);
        toast.success('Invoice updated');
      } else {
        await createGstInvoice(invForm);
        toast.success('Invoice created');
      }
      setShowInvoiceDialog(false);
      setInvForm(null);
      setEditingInvoice(null);
      loadInvoices();
      loadSummary();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to save invoice');
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
    if (!window.confirm(`Deactivate ${item.name}?`)) return;
    try {
      await deleteGstItem(item.id);
      toast.success('Item deactivated');
      loadItems();
    } catch (e) {
      toast.error('Failed to deactivate');
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

  const addPlanItem = () => {
    setEditingPlan(prev => ({
      ...prev,
      items: [...(prev.items || []), { item_name: '', hsn: '', unit: 'Nos', quantity: 1, gst_rate: 18, unit_price: 0 }],
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
                      placeholder="Search invoice no, customer, phone..."
                      value={search}
                      onChange={e => { setSearch(e.target.value); setPage(1); }}
                      className="pl-9"
                      data-testid="search-input"
                    />
                  </div>
                  <Select value={statusFilter} onValueChange={v => { setStatusFilter(v); setPage(1); }}>
                    <SelectTrigger data-testid="status-filter"><SelectValue placeholder="Status" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="cancelled">Cancelled</SelectItem>
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
                  <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} data-testid="start-date" />
                  <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} data-testid="end-date" />
                </div>
                <div className="flex justify-end mt-3">
                  <Button variant="outline" onClick={handleExcelExport} data-testid="export-excel-btn">
                    <FileSpreadsheet className="w-4 h-4 mr-1" /> Export Excel
                  </Button>
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
                        <th className="text-left p-3 font-medium">Date</th>
                        <th className="text-left p-3 font-medium">Customer</th>
                        <th className="text-left p-3 font-medium">Type</th>
                        <th className="text-right p-3 font-medium">Sub Total</th>
                        <th className="text-right p-3 font-medium">GST</th>
                        <th className="text-right p-3 font-medium">Total</th>
                        <th className="text-center p-3 font-medium">Status</th>
                        <th className="text-center p-3 font-medium">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {loading ? (
                        <tr><td colSpan="9" className="p-8 text-center text-slate-500">Loading...</td></tr>
                      ) : invoices.length === 0 ? (
                        <tr><td colSpan="9" className="p-8 text-center text-slate-500">No invoices found.</td></tr>
                      ) : invoices.map(inv => (
                        <tr key={inv.id} className={`border-b hover:bg-slate-50 ${inv.status === 'cancelled' ? 'opacity-60' : ''}`} data-testid={`invoice-row-${inv.id}`}>
                          <td className="p-3 font-mono text-xs">{inv.invoice_number}</td>
                          <td className="p-3">{inv.invoice_date}</td>
                          <td className="p-3">
                            <div className="font-medium">{inv.customer_name}</div>
                            <div className="text-xs text-slate-500">{inv.customer_phone}</div>
                          </td>
                          <td className="p-3">
                            <Badge variant="outline">{(inv.bill_type || '-').replace('_', ' ')}</Badge>
                          </td>
                          <td className="p-3 text-right">{formatRs(inv.sub_total)}</td>
                          <td className="p-3 text-right text-blue-700">{formatRs(inv.total_gst)}</td>
                          <td className="p-3 text-right font-semibold">{formatRs(inv.grand_total)}</td>
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
                    {plans.length === 0 ? (
                      <tr><td colSpan="8" className="p-8 text-center text-slate-500">No plans yet.</td></tr>
                    ) : plans.map(p => {
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
              </CardContent>
            </Card>
          </TabsContent>

          {/* ITEM MASTER TAB */}
          <TabsContent value="items">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-base">Item Master (HSN + GST Rates)</CardTitle>
                <Button size="sm" onClick={() => { setEditingItem({ name: '', hsn: '', unit: 'Nos', gst_rate: 18, default_rate: 0 }); setShowItemDialog(true); }} data-testid="add-item-btn">
                  <Plus className="w-4 h-4 mr-1" /> Add Item
                </Button>
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
                          <Button size="icon" variant="ghost" onClick={() => { setEditingItem({ ...it }); setShowItemDialog(true); }}>
                            <Edit2 className="w-4 h-4" />
                          </Button>
                          <Button size="icon" variant="ghost" onClick={() => handleDeleteItem(it)}>
                            <Trash2 className="w-4 h-4 text-red-600" />
                          </Button>
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
          <DialogContent className="max-w-md" data-testid="config-dialog">
            <DialogHeader>
              <DialogTitle>GST Billing Settings</DialogTitle>
              <DialogDescription>Changes apply to new invoices only. Existing invoices keep their original number.</DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Invoice Prefix</Label>
                  <Input value={config.prefix || ''} onChange={e => setConfig({ ...config, prefix: e.target.value })} data-testid="config-prefix" />
                  <p className="text-xs text-slate-500 mt-1">Default: INV</p>
                </div>
                <div>
                  <Label>Invoice Suffix</Label>
                  <Input value={config.suffix || ''} onChange={e => setConfig({ ...config, suffix: e.target.value })} data-testid="config-suffix" />
                  <p className="text-xs text-slate-500 mt-1">Optional</p>
                </div>
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
              <div className="text-xs text-slate-500 p-2 bg-slate-50 rounded">
                <strong>Format preview:</strong> {config.prefix || 'INV'}/{config.current_fy || 'YYYY-YY'}/0001{config.suffix ? `/${config.suffix}` : ''}
              </div>
              <div className="text-xs text-slate-500">
                Next invoice number: <strong>{config.next_seq || 1}</strong> (FY {config.current_fy || '-'})
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowConfigDialog(false)}>Cancel</Button>
              <Button onClick={handleSaveConfig} data-testid="save-config-btn">Save</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* CANCEL DIALOG */}
        <Dialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
          <DialogContent className="max-w-md" data-testid="cancel-dialog">
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
          <DialogContent className="max-w-3xl" data-testid="generate-dialog">
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
            <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto" data-testid="invoice-dialog">
              <DialogHeader>
                <DialogTitle>{editingInvoice ? `Edit Invoice ${editingInvoice.invoice_number}` : 'New Manual Invoice'}</DialogTitle>
              </DialogHeader>

              <div className="space-y-4">
                {/* Customer block */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div>
                    <Label>Invoice Date *</Label>
                    <Input type="date" value={invForm.invoice_date} onChange={e => setInvForm({ ...invForm, invoice_date: e.target.value })} data-testid="inv-date" />
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
                <div className="bg-slate-50 p-3 rounded grid grid-cols-2 md:grid-cols-5 gap-2 text-sm">
                  <div><span className="text-slate-500">Sub Total:</span> <strong>{formatRs(preview.sub_total)}</strong></div>
                  <div><span className="text-slate-500">CGST:</span> <strong>{formatRs(preview.total_cgst)}</strong></div>
                  <div><span className="text-slate-500">SGST:</span> <strong>{formatRs(preview.total_sgst)}</strong></div>
                  <div><span className="text-slate-500">IGST:</span> <strong>{formatRs(preview.total_igst)}</strong></div>
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

        {/* VIEW INVOICE DIALOG */}
        {viewingInvoice && (
          <Dialog open={showViewDialog} onOpenChange={(o) => { setShowViewDialog(o); if (!o) setViewingInvoice(null); }}>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="view-dialog">
              <DialogHeader>
                <DialogTitle>
                  Invoice {viewingInvoice.invoice_number}
                  {viewingInvoice.status === 'cancelled' && <Badge className="bg-red-100 text-red-700 ml-2">CANCELLED</Badge>}
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-3 text-sm">
                <div className="grid grid-cols-2 gap-4 p-3 bg-slate-50 rounded">
                  <div><span className="text-slate-500">Date:</span> <strong>{viewingInvoice.invoice_date}</strong></div>
                  <div><span className="text-slate-500">FY:</span> <strong>{viewingInvoice.fy}</strong></div>
                  <div><span className="text-slate-500">Customer:</span> <strong>{viewingInvoice.customer_name}</strong></div>
                  <div><span className="text-slate-500">Phone:</span> <strong>{viewingInvoice.customer_phone || '-'}</strong></div>
                  <div className="col-span-2"><span className="text-slate-500">Address:</span> <strong>{viewingInvoice.customer_address || '-'}</strong></div>
                  <div><span className="text-slate-500">GSTIN:</span> <strong>{viewingInvoice.customer_gstin || '-'}</strong></div>
                  <div><span className="text-slate-500">Tax Mode:</span> <strong>{viewingInvoice.tax_mode}</strong></div>
                </div>

                <table className="w-full text-xs border">
                  <thead className="bg-blue-700 text-white">
                    <tr>
                      <th className="p-2 text-left">Item</th>
                      <th className="p-2 text-left">HSN</th>
                      <th className="p-2 text-right">Qty</th>
                      <th className="p-2 text-right">Rate</th>
                      <th className="p-2 text-right">Taxable</th>
                      <th className="p-2 text-right">GST%</th>
                      <th className="p-2 text-right">CGST</th>
                      <th className="p-2 text-right">SGST</th>
                      <th className="p-2 text-right">IGST</th>
                      <th className="p-2 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(viewingInvoice.line_items || []).map((li, idx) => (
                      <tr key={idx} className="border-t">
                        <td className="p-2">{li.item_name}</td>
                        <td className="p-2 font-mono">{li.hsn}</td>
                        <td className="p-2 text-right">{li.quantity}</td>
                        <td className="p-2 text-right">{formatRs(li.rate)}</td>
                        <td className="p-2 text-right">{formatRs(li.taxable_value)}</td>
                        <td className="p-2 text-right">{li.gst_rate}%</td>
                        <td className="p-2 text-right">{formatRs(li.cgst)}</td>
                        <td className="p-2 text-right">{formatRs(li.sgst)}</td>
                        <td className="p-2 text-right">{formatRs(li.igst)}</td>
                        <td className="p-2 text-right font-semibold">{formatRs(li.line_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-slate-100">
                    <tr>
                      <td colSpan="4" className="p-2 text-right font-semibold">TOTAL</td>
                      <td className="p-2 text-right">{formatRs(viewingInvoice.sub_total)}</td>
                      <td></td>
                      <td className="p-2 text-right">{formatRs(viewingInvoice.total_cgst)}</td>
                      <td className="p-2 text-right">{formatRs(viewingInvoice.total_sgst)}</td>
                      <td className="p-2 text-right">{formatRs(viewingInvoice.total_igst)}</td>
                      <td className="p-2 text-right font-bold text-blue-700">{formatRs(viewingInvoice.grand_total)}</td>
                    </tr>
                  </tfoot>
                </table>

                {viewingInvoice.remarks && (
                  <div className="text-xs"><strong>Remarks:</strong> {viewingInvoice.remarks}</div>
                )}
                {viewingInvoice.status === 'cancelled' && (
                  <div className="text-xs text-red-600">
                    <strong>Cancellation:</strong> {viewingInvoice.cancellation_reason || 'No reason given'} ({viewingInvoice.cancelled_at?.slice(0, 10)})
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => handlePdf(viewingInvoice)}>
                  <FileDown className="w-4 h-4 mr-1" /> Download PDF
                </Button>
                <Button onClick={() => { setShowViewDialog(false); setViewingInvoice(null); }}>Close</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}

        {/* ITEM DIALOG */}
        {editingItem && (
          <Dialog open={showItemDialog} onOpenChange={(o) => { setShowItemDialog(o); if (!o) setEditingItem(null); }}>
            <DialogContent className="max-w-md" data-testid="item-dialog">
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
            <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto" data-testid="plan-dialog">
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
                          <th className="text-left p-2">Item Name *</th>
                          <th className="text-left p-2 w-24">HSN</th>
                          <th className="text-left p-2 w-20">Unit</th>
                          <th className="text-right p-2 w-20">Qty</th>
                          <th className="text-right p-2 w-24">Unit Price *</th>
                          <th className="text-right p-2 w-20">GST%</th>
                          <th className="text-right p-2 w-24">Line Total</th>
                          <th className="w-8"></th>
                        </tr>
                      </thead>
                      <tbody>
                        {editingPlan.items.map((it, idx) => {
                          const q = Number(it.quantity) || 0;
                          const r = Number(it.unit_price) || 0;
                          const g = Number(it.gst_rate) || 0;
                          const total = q * r * (1 + g / 100);
                          return (
                            <tr key={idx} className="border-t">
                              <td className="p-1">
                                <Input className="h-8" value={it.item_name} onChange={e => updatePlanItem(idx, 'item_name', e.target.value)} data-testid={`plan-line-name-${idx}`} />
                              </td>
                              <td className="p-1"><Input className="h-8" value={it.hsn || ''} onChange={e => updatePlanItem(idx, 'hsn', e.target.value)} /></td>
                              <td className="p-1"><Input className="h-8" value={it.unit || ''} onChange={e => updatePlanItem(idx, 'unit', e.target.value)} /></td>
                              <td className="p-1"><Input className="h-8 text-right" type="number" value={it.quantity} onChange={e => updatePlanItem(idx, 'quantity', e.target.value)} /></td>
                              <td className="p-1"><Input className="h-8 text-right" type="number" value={it.unit_price || 0} onChange={e => updatePlanItem(idx, 'unit_price', e.target.value)} data-testid={`plan-line-price-${idx}`} /></td>
                              <td className="p-1"><Input className="h-8 text-right" type="number" value={it.gst_rate} onChange={e => updatePlanItem(idx, 'gst_rate', e.target.value)} /></td>
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
      </div>
    </Layout>
  );
};

export default GSTBilling;
