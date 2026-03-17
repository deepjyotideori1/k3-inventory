import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import { getDashboardStats, getDailyReports, getOrderAnalysis, getWarehouses, exportOrderAnalysisPDF, exportOrderAnalysisExcel, getConnectionRefillAnalytics, exportConnectionRefillPDF, exportConnectionRefillExcel } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Input } from '../components/ui/input';
import { 
  Warehouse, 
  Package, 
  AlertTriangle, 
  TrendingUp,
  RefreshCw,
  Factory,
  ChevronRight,
  ChevronDown,
  Loader2,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
  Timer,
  Filter,
  PackageOpen,
  ShoppingCart,
  Download,
  FileSpreadsheet,
  Search,
  Calendar,
  CheckCircle2,
  Clock,
  Truck,
  BarChart3,
  Home,
  Flame
} from 'lucide-react';
import { formatDate } from '../lib/utils';
import { toast } from 'sonner';

const AUTO_REFRESH_INTERVAL = 30; // seconds

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [discrepancyReports, setDiscrepancyReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  
  // Cylinder Stock Summary state
  const [stockExpanded, setStockExpanded] = useState(false);
  const [stockFilterType, setStockFilterType] = useState('all'); // all, 15kg, 21kg
  const [stockFilterWarehouse, setStockFilterWarehouse] = useState('all');
  
  // Auto-refresh
  const [countdown, setCountdown] = useState(AUTO_REFRESH_INTERVAL);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
  const intervalRef = useRef(null);
  const countdownRef = useRef(null);

  // Order Analysis state
  const [orderAnalysis, setOrderAnalysis] = useState(null);
  const [orderLoading, setOrderLoading] = useState(false);
  const [orderExporting, setOrderExporting] = useState(false);
  const [orderFilterWarehouse, setOrderFilterWarehouse] = useState('all');
  const [orderFilterStatus, setOrderFilterStatus] = useState('all');
  const [orderFilterDateRange, setOrderFilterDateRange] = useState('month');
  const [orderStartDate, setOrderStartDate] = useState('');
  const [orderEndDate, setOrderEndDate] = useState('');
  const [orderSearch, setOrderSearch] = useState('');
  const [allWarehouses, setAllWarehouses] = useState([]);

  // Connection & Refill Analytics state
  const [analyticsData, setAnalyticsData] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsExporting, setAnalyticsExporting] = useState(false);
  const [analyticsPeriod, setAnalyticsPeriod] = useState('monthly');
  const [analyticsWarehouse, setAnalyticsWarehouse] = useState('all');
  const [analyticsStartDate, setAnalyticsStartDate] = useState('');
  const [analyticsEndDate, setAnalyticsEndDate] = useState('');

  useEffect(() => {
    fetchStats();
    loadWarehouses();
  }, []);

  // Auto-refresh logic
  useEffect(() => {
    if (!autoRefreshEnabled) {
      clearInterval(intervalRef.current);
      clearInterval(countdownRef.current);
      return;
    }
    setCountdown(AUTO_REFRESH_INTERVAL);
    intervalRef.current = setInterval(() => {
      fetchStats(true);
      setCountdown(AUTO_REFRESH_INTERVAL);
    }, AUTO_REFRESH_INTERVAL * 1000);
    countdownRef.current = setInterval(() => {
      setCountdown(prev => (prev > 0 ? prev - 1 : AUTO_REFRESH_INTERVAL));
    }, 1000);
    return () => {
      clearInterval(intervalRef.current);
      clearInterval(countdownRef.current);
    };
  }, [autoRefreshEnabled]);

  const fetchStats = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [statsRes, reportsRes] = await Promise.all([
        getDashboardStats(),
        getDailyReports({})
      ]);
      setStats(statsRes.data);
      const discReports = reportsRes.data.filter(r => r.has_discrepancy);
      setDiscrepancyReports(discReports);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      if (!silent) toast.error('Failed to load dashboard data');
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const loadWarehouses = async () => {
    try {
      const res = await getWarehouses();
      setAllWarehouses(res.data || []);
    } catch {}
  };

  const fetchOrderAnalysis = useCallback(async () => {
    setOrderLoading(true);
    try {
      const today = new Date();
      let sd = '', ed = '';
      if (orderFilterDateRange === 'today') {
        sd = ed = today.toISOString().split('T')[0];
      } else if (orderFilterDateRange === 'week') {
        const w = new Date(today); w.setDate(w.getDate() - 7);
        sd = w.toISOString().split('T')[0]; ed = today.toISOString().split('T')[0];
      } else if (orderFilterDateRange === 'month') {
        const m = new Date(today); m.setDate(m.getDate() - 30);
        sd = m.toISOString().split('T')[0]; ed = today.toISOString().split('T')[0];
      } else if (orderFilterDateRange === 'year') {
        const y = new Date(today); y.setFullYear(y.getFullYear() - 1);
        sd = y.toISOString().split('T')[0]; ed = today.toISOString().split('T')[0];
      } else if (orderFilterDateRange === 'custom') {
        sd = orderStartDate; ed = orderEndDate;
      }
      const params = {};
      if (orderFilterWarehouse !== 'all') params.warehouse_id = orderFilterWarehouse;
      if (orderFilterStatus !== 'all') params.status = orderFilterStatus;
      if (sd) params.start_date = sd;
      if (ed) params.end_date = ed;
      if (orderSearch) params.search = orderSearch;
      const res = await getOrderAnalysis(params);
      setOrderAnalysis(res.data);
    } catch (error) {
      console.error('Failed to fetch order analysis:', error);
      toast.error('Failed to load order analysis');
    } finally {
      setOrderLoading(false);
    }
  }, [orderFilterWarehouse, orderFilterStatus, orderFilterDateRange, orderStartDate, orderEndDate, orderSearch]);

  useEffect(() => {
    if (activeTab === 'orders') fetchOrderAnalysis();
  }, [activeTab, fetchOrderAnalysis]);

  const handleExportOrderPDF = async () => {
    setOrderExporting(true);
    try {
      const params = {};
      if (orderFilterWarehouse !== 'all') params.warehouse_id = orderFilterWarehouse;
      if (orderFilterStatus !== 'all') params.status = orderFilterStatus;
      const today = new Date();
      if (orderFilterDateRange === 'today') { params.start_date = params.end_date = today.toISOString().split('T')[0]; }
      else if (orderFilterDateRange === 'week') { const w = new Date(today); w.setDate(w.getDate() - 7); params.start_date = w.toISOString().split('T')[0]; params.end_date = today.toISOString().split('T')[0]; }
      else if (orderFilterDateRange === 'month') { const m = new Date(today); m.setDate(m.getDate() - 30); params.start_date = m.toISOString().split('T')[0]; params.end_date = today.toISOString().split('T')[0]; }
      else if (orderFilterDateRange === 'year') { const y = new Date(today); y.setFullYear(y.getFullYear() - 1); params.start_date = y.toISOString().split('T')[0]; params.end_date = today.toISOString().split('T')[0]; }
      else if (orderFilterDateRange === 'custom') { params.start_date = orderStartDate; params.end_date = orderEndDate; }
      await exportOrderAnalysisPDF(params);
      toast.success('Order analysis PDF exported');
    } catch { toast.error('Failed to export PDF'); }
    finally { setOrderExporting(false); }
  };

  const handleExportOrderExcel = async () => {
    setOrderExporting(true);
    try {
      const params = {};
      if (orderFilterWarehouse !== 'all') params.warehouse_id = orderFilterWarehouse;
      if (orderFilterStatus !== 'all') params.status = orderFilterStatus;
      const today = new Date();
      if (orderFilterDateRange === 'today') { params.start_date = params.end_date = today.toISOString().split('T')[0]; }
      else if (orderFilterDateRange === 'week') { const w = new Date(today); w.setDate(w.getDate() - 7); params.start_date = w.toISOString().split('T')[0]; params.end_date = today.toISOString().split('T')[0]; }
      else if (orderFilterDateRange === 'month') { const m = new Date(today); m.setDate(m.getDate() - 30); params.start_date = m.toISOString().split('T')[0]; params.end_date = today.toISOString().split('T')[0]; }
      else if (orderFilterDateRange === 'year') { const y = new Date(today); y.setFullYear(y.getFullYear() - 1); params.start_date = y.toISOString().split('T')[0]; params.end_date = today.toISOString().split('T')[0]; }
      else if (orderFilterDateRange === 'custom') { params.start_date = orderStartDate; params.end_date = orderEndDate; }
      await exportOrderAnalysisExcel(params);
      toast.success('Order analysis Excel exported');
    } catch { toast.error('Failed to export Excel'); }
    finally { setOrderExporting(false); }
  };

  // Connection & Refill Analytics
  const fetchAnalytics = useCallback(async () => {
    setAnalyticsLoading(true);
    try {
      const params = { period: analyticsPeriod };
      if (analyticsWarehouse !== 'all') params.warehouse_id = analyticsWarehouse;
      if (analyticsPeriod === 'custom') {
        if (analyticsStartDate) params.start_date = analyticsStartDate;
        if (analyticsEndDate) params.end_date = analyticsEndDate;
      }
      const res = await getConnectionRefillAnalytics(params);
      setAnalyticsData(res.data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
      toast.error('Failed to load analytics');
    } finally {
      setAnalyticsLoading(false);
    }
  }, [analyticsPeriod, analyticsWarehouse, analyticsStartDate, analyticsEndDate]);

  useEffect(() => {
    if (activeTab === 'analytics') fetchAnalytics();
  }, [activeTab, fetchAnalytics]);

  const getAnalyticsExportParams = () => {
    const params = { period: analyticsPeriod };
    if (analyticsWarehouse !== 'all') params.warehouse_id = analyticsWarehouse;
    if (analyticsPeriod === 'custom') {
      if (analyticsStartDate) params.start_date = analyticsStartDate;
      if (analyticsEndDate) params.end_date = analyticsEndDate;
    }
    return params;
  };

  const handleExportAnalyticsPDF = async () => {
    setAnalyticsExporting(true);
    try {
      await exportConnectionRefillPDF(getAnalyticsExportParams());
      toast.success('Analytics PDF exported');
    } catch { toast.error('Failed to export PDF'); }
    finally { setAnalyticsExporting(false); }
  };

  const handleExportAnalyticsExcel = async () => {
    setAnalyticsExporting(true);
    try {
      await exportConnectionRefillExcel(getAnalyticsExportParams());
      toast.success('Analytics Excel exported');
    } catch { toast.error('Failed to export Excel'); }
    finally { setAnalyticsExporting(false); }
  };

  // Filtered stock data based on selected filters
  const filteredStock = useMemo(() => {
    if (!stats) return { filled: 0, empty: 0, filled15: 0, filled21: 0, empty15: 0, empty21: 0, warehouses: [] };
    
    let warehouses = stats.warehouses || [];
    if (stockFilterWarehouse !== 'all') {
      warehouses = warehouses.filter(w => w.id === stockFilterWarehouse);
    }
    
    let filled15 = 0, filled21 = 0, empty15 = 0, empty21 = 0;
    warehouses.forEach(w => {
      filled15 += w.closing_15kg_filled || 0;
      filled21 += w.closing_21kg_filled || 0;
      empty15 += w.closing_15kg_empty || 0;
      empty21 += w.closing_21kg_empty || 0;
    });

    // Include plant if "all" warehouses and plant data exists
    if (stockFilterWarehouse === 'all' && stats.plant) {
      filled15 += stats.plant.closing_15kg_filled || 0;
      filled21 += stats.plant.closing_21kg_filled || 0;
      empty15 += stats.plant.closing_15kg_empty || 0;
      empty21 += stats.plant.closing_21kg_empty || 0;
    }

    let filled = 0, empty = 0;
    if (stockFilterType === 'all' || stockFilterType === '15kg') { filled += filled15; empty += empty15; }
    if (stockFilterType === 'all' || stockFilterType === '21kg') { filled += filled21; empty += empty21; }

    return { filled, empty, filled15, filled21, empty15, empty21, warehouses };
  }, [stats, stockFilterWarehouse, stockFilterType]);

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-green-700" />
        </div>
      </Layout>
    );
  }

  const totalDiscrepancies = discrepancyReports.length;

  return (
    <Layout>
      <div className="space-y-6" data-testid="admin-dashboard">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-800">Master Dashboard</h1>
            <p className="text-slate-500 mt-1">Overview of all warehouses and inventory</p>
          </div>
          <Button onClick={() => { fetchStats(); setCountdown(AUTO_REFRESH_INTERVAL); }} variant="outline" className="gap-2" data-testid="refresh-btn">
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card className="card-hover" data-testid="stat-total-warehouses">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-slate-500 text-sm font-medium">Total Warehouses</p>
                  <p className="text-3xl font-bold text-slate-800 mt-1">{stats?.total_warehouses || 0}</p>
                </div>
                <div className="w-12 h-12 rounded-xl bg-green-100 flex items-center justify-center">
                  <Warehouse className="w-6 h-6 text-green-700" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="card-hover border-green-200 bg-gradient-to-br from-green-50 to-emerald-50" data-testid="stat-total-filled">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-green-700 text-sm font-medium flex items-center gap-1">
                    <Package className="w-4 h-4" /> Total Filled Cylinders
                  </p>
                  <p className="text-3xl font-bold text-green-800 mt-1">
                    {(stats?.total_15kg_filled || 0) + (stats?.total_21kg_filled || 0)}
                  </p>
                  <div className="flex gap-3 mt-1">
                    <span className="text-xs text-green-600 font-medium">15kg: {stats?.total_15kg_filled || 0}</span>
                    <span className="text-xs text-green-600 font-medium">21kg: {stats?.total_21kg_filled || 0}</span>
                  </div>
                </div>
                <div className="w-12 h-12 rounded-xl bg-green-200 flex items-center justify-center">
                  <Package className="w-6 h-6 text-green-800" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="card-hover border-orange-200 bg-gradient-to-br from-orange-50 to-amber-50" data-testid="stat-total-empty">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-orange-700 text-sm font-medium flex items-center gap-1">
                    <PackageOpen className="w-4 h-4" /> Total Empty Cylinders
                  </p>
                  <p className="text-3xl font-bold text-orange-800 mt-1">
                    {(stats?.total_15kg_empty || 0) + (stats?.total_21kg_empty || 0)}
                  </p>
                  <div className="flex gap-3 mt-1">
                    <span className="text-xs text-orange-600 font-medium">15kg: {stats?.total_15kg_empty || 0}</span>
                    <span className="text-xs text-orange-600 font-medium">21kg: {stats?.total_21kg_empty || 0}</span>
                  </div>
                </div>
                <div className="w-12 h-12 rounded-xl bg-orange-200 flex items-center justify-center">
                  <PackageOpen className="w-6 h-6 text-orange-800" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className={`card-hover ${totalDiscrepancies > 0 ? 'border-red-300 bg-red-50' : ''}`} data-testid="stat-discrepancies">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-slate-500 text-sm font-medium">Stock Discrepancies</p>
                  <p className={`text-3xl font-bold mt-1 ${totalDiscrepancies > 0 ? 'text-red-700' : 'text-slate-800'}`}>
                    {totalDiscrepancies}
                  </p>
                </div>
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${totalDiscrepancies > 0 ? 'bg-red-100' : 'bg-orange-100'}`}>
                  <AlertTriangle className={`w-6 h-6 ${totalDiscrepancies > 0 ? 'text-red-700' : 'text-orange-700'}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Cylinder Stock Summary Widget */}
        <Card data-testid="cylinder-stock-summary">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <Package className="w-5 h-5 text-green-700" />
                Cylinder Stock Summary
                {autoRefreshEnabled && (
                  <Badge variant="outline" className="text-xs font-normal text-slate-500 border-slate-300 ml-2 gap-1">
                    <Timer className="w-3 h-3" />
                    {countdown}s
                  </Badge>
                )}
              </CardTitle>
              <div className="flex flex-wrap items-center gap-2">
                <Select value={stockFilterType} onValueChange={setStockFilterType}>
                  <SelectTrigger className="w-28 h-8 text-xs" data-testid="stock-filter-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="15kg">15kg Only</SelectItem>
                    <SelectItem value="21kg">21kg Only</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={stockFilterWarehouse} onValueChange={setStockFilterWarehouse}>
                  <SelectTrigger className="w-40 h-8 text-xs" data-testid="stock-filter-warehouse">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Warehouses</SelectItem>
                    {(stats?.warehouses || []).map(w => (
                      <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant={autoRefreshEnabled ? "default" : "outline"}
                  size="sm"
                  className={`h-8 text-xs gap-1 ${autoRefreshEnabled ? 'bg-green-700 hover:bg-green-800' : ''}`}
                  onClick={() => setAutoRefreshEnabled(!autoRefreshEnabled)}
                  data-testid="auto-refresh-toggle"
                >
                  <RefreshCw className={`w-3 h-3 ${autoRefreshEnabled ? 'animate-spin' : ''}`} style={autoRefreshEnabled ? { animationDuration: '3s' } : {}} />
                  {autoRefreshEnabled ? 'Auto' : 'Paused'}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {/* Main Filled / Empty Counters */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="p-5 bg-gradient-to-br from-green-50 to-emerald-100 rounded-xl border border-green-200" data-testid="stock-filled-counter">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-8 h-8 rounded-lg bg-green-200 flex items-center justify-center">
                    <Package className="w-4 h-4 text-green-800" />
                  </div>
                  <p className="text-sm font-semibold text-green-800">Filled Cylinders</p>
                </div>
                <p className="text-4xl font-bold text-green-900">{filteredStock.filled}</p>
                {stockFilterType === 'all' && (
                  <div className="flex gap-4 mt-2">
                    <span className="text-sm text-green-700">15kg: <strong>{filteredStock.filled15}</strong></span>
                    <span className="text-sm text-green-700">21kg: <strong>{filteredStock.filled21}</strong></span>
                  </div>
                )}
                {/* Fill ratio bar */}
                <div className="mt-3 h-2 bg-green-200 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-green-600 rounded-full transition-all duration-700"
                    style={{ width: `${filteredStock.filled + filteredStock.empty > 0 ? (filteredStock.filled / (filteredStock.filled + filteredStock.empty)) * 100 : 0}%` }}
                  />
                </div>
                <p className="text-xs text-green-600 mt-1">
                  {filteredStock.filled + filteredStock.empty > 0 
                    ? `${Math.round((filteredStock.filled / (filteredStock.filled + filteredStock.empty)) * 100)}% of total stock`
                    : 'No data'}
                </p>
              </div>

              <div className="p-5 bg-gradient-to-br from-orange-50 to-amber-100 rounded-xl border border-orange-200" data-testid="stock-empty-counter">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-8 h-8 rounded-lg bg-orange-200 flex items-center justify-center">
                    <PackageOpen className="w-4 h-4 text-orange-800" />
                  </div>
                  <p className="text-sm font-semibold text-orange-800">Empty Cylinders</p>
                </div>
                <p className="text-4xl font-bold text-orange-900">{filteredStock.empty}</p>
                {stockFilterType === 'all' && (
                  <div className="flex gap-4 mt-2">
                    <span className="text-sm text-orange-700">15kg: <strong>{filteredStock.empty15}</strong></span>
                    <span className="text-sm text-orange-700">21kg: <strong>{filteredStock.empty21}</strong></span>
                  </div>
                )}
                <div className="mt-3 h-2 bg-orange-200 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-orange-500 rounded-full transition-all duration-700"
                    style={{ width: `${filteredStock.filled + filteredStock.empty > 0 ? (filteredStock.empty / (filteredStock.filled + filteredStock.empty)) * 100 : 0}%` }}
                  />
                </div>
                <p className="text-xs text-orange-600 mt-1">
                  {filteredStock.filled + filteredStock.empty > 0 
                    ? `${Math.round((filteredStock.empty / (filteredStock.filled + filteredStock.empty)) * 100)}% of total stock`
                    : 'No data'}
                </p>
              </div>
            </div>

            {/* Expandable Warehouse Breakdown */}
            <button
              className="w-full flex items-center justify-between p-3 bg-slate-50 hover:bg-slate-100 rounded-lg transition-colors text-sm font-medium text-slate-700"
              onClick={() => setStockExpanded(!stockExpanded)}
              data-testid="stock-breakdown-toggle"
            >
              <span className="flex items-center gap-2">
                <Warehouse className="w-4 h-4" />
                Warehouse-wise Breakdown
              </span>
              <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${stockExpanded ? 'rotate-180' : ''}`} />
            </button>

            {stockExpanded && (
              <div className="mt-3 overflow-x-auto" data-testid="stock-breakdown-table">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200">
                      <th className="text-left py-2 px-3 text-slate-600 font-medium">Warehouse</th>
                      {(stockFilterType === 'all' || stockFilterType === '15kg') && (
                        <>
                          <th className="text-center py-2 px-3 text-green-700 font-medium">15kg Filled</th>
                          <th className="text-center py-2 px-3 text-orange-700 font-medium">15kg Empty</th>
                        </>
                      )}
                      {(stockFilterType === 'all' || stockFilterType === '21kg') && (
                        <>
                          <th className="text-center py-2 px-3 text-green-700 font-medium">21kg Filled</th>
                          <th className="text-center py-2 px-3 text-orange-700 font-medium">21kg Empty</th>
                        </>
                      )}
                      <th className="text-center py-2 px-3 text-slate-600 font-medium">Last Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredStock.warehouses.map(w => (
                      <tr key={w.id} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="py-2 px-3 font-medium text-slate-800">{w.name}</td>
                        {(stockFilterType === 'all' || stockFilterType === '15kg') && (
                          <>
                            <td className="text-center py-2 px-3">
                              <span className="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 bg-green-100 text-green-800 rounded font-semibold">
                                {w.closing_15kg_filled}
                              </span>
                            </td>
                            <td className="text-center py-2 px-3">
                              <span className="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 bg-orange-100 text-orange-800 rounded font-semibold">
                                {w.closing_15kg_empty}
                              </span>
                            </td>
                          </>
                        )}
                        {(stockFilterType === 'all' || stockFilterType === '21kg') && (
                          <>
                            <td className="text-center py-2 px-3">
                              <span className="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 bg-green-100 text-green-800 rounded font-semibold">
                                {w.closing_21kg_filled}
                              </span>
                            </td>
                            <td className="text-center py-2 px-3">
                              <span className="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 bg-orange-100 text-orange-800 rounded font-semibold">
                                {w.closing_21kg_empty}
                              </span>
                            </td>
                          </>
                        )}
                        <td className="text-center py-2 px-3 text-xs text-slate-500">
                          {w.last_report_date ? formatDate(w.last_report_date) : 'No data'}
                        </td>
                      </tr>
                    ))}
                    {/* Plant row if viewing all */}
                    {stockFilterWarehouse === 'all' && stats?.plant && (
                      <tr className="border-b border-slate-100 hover:bg-slate-50 bg-green-50/30">
                        <td className="py-2 px-3 font-medium text-slate-800 flex items-center gap-1">
                          <Factory className="w-3 h-3 text-green-700" /> Plant Hollongi
                        </td>
                        {(stockFilterType === 'all' || stockFilterType === '15kg') && (
                          <>
                            <td className="text-center py-2 px-3">
                              <span className="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 bg-green-100 text-green-800 rounded font-semibold">
                                {stats.plant.closing_15kg_filled}
                              </span>
                            </td>
                            <td className="text-center py-2 px-3">
                              <span className="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 bg-orange-100 text-orange-800 rounded font-semibold">
                                {stats.plant.closing_15kg_empty}
                              </span>
                            </td>
                          </>
                        )}
                        {(stockFilterType === 'all' || stockFilterType === '21kg') && (
                          <>
                            <td className="text-center py-2 px-3">
                              <span className="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 bg-green-100 text-green-800 rounded font-semibold">
                                {stats.plant.closing_21kg_filled}
                              </span>
                            </td>
                            <td className="text-center py-2 px-3">
                              <span className="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 bg-orange-100 text-orange-800 rounded font-semibold">
                                {stats.plant.closing_21kg_empty}
                              </span>
                            </td>
                          </>
                        )}
                        <td className="text-center py-2 px-3 text-xs text-slate-500">
                          {stats.plant.last_report_date ? formatDate(stats.plant.last_report_date) : 'No data'}
                        </td>
                      </tr>
                    )}
                    {/* Totals row */}
                    <tr className="bg-slate-100 font-bold">
                      <td className="py-2 px-3 text-slate-800">TOTAL</td>
                      {(stockFilterType === 'all' || stockFilterType === '15kg') && (
                        <>
                          <td className="text-center py-2 px-3 text-green-800">{filteredStock.filled15}</td>
                          <td className="text-center py-2 px-3 text-orange-800">{filteredStock.empty15}</td>
                        </>
                      )}
                      {(stockFilterType === 'all' || stockFilterType === '21kg') && (
                        <>
                          <td className="text-center py-2 px-3 text-green-800">{filteredStock.filled21}</td>
                          <td className="text-center py-2 px-3 text-orange-800">{filteredStock.empty21}</td>
                        </>
                      )}
                      <td></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Tabs for Overview and Discrepancies */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList>
            <TabsTrigger value="overview" data-testid="overview-tab">Warehouse Overview</TabsTrigger>
            <TabsTrigger value="analytics" data-testid="analytics-tab">
              <BarChart3 className="w-4 h-4 mr-1" /> Analytics
            </TabsTrigger>
            <TabsTrigger value="orders" data-testid="orders-tab">Order Analysis</TabsTrigger>
            <TabsTrigger value="discrepancies" data-testid="discrepancies-tab" className="relative">
              Stock Discrepancies
              {totalDiscrepancies > 0 && (
                <span className="ml-2 px-2 py-0.5 text-xs bg-red-500 text-white rounded-full">
                  {totalDiscrepancies}
                </span>
              )}
            </TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Warehouse Status */}
              <Card className="lg:col-span-2" data-testid="warehouse-status-card">
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-lg font-semibold">Warehouse Status</CardTitle>
                  <Link to="/warehouses">
                    <Button variant="ghost" size="sm" className="text-green-700">
                      View All <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  </Link>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {stats?.warehouses?.map((warehouse) => (
                      <div 
                        key={warehouse.id} 
                        className={`p-4 rounded-lg transition-colors ${warehouse.has_discrepancy ? 'bg-red-50 border border-red-200' : 'bg-slate-50 hover:bg-slate-100'}`}
                        data-testid={`warehouse-row-${warehouse.id}`}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${warehouse.has_discrepancy ? 'bg-red-100' : 'bg-green-100'}`}>
                              <Warehouse className={`w-5 h-5 ${warehouse.has_discrepancy ? 'text-red-700' : 'text-green-700'}`} />
                            </div>
                            <div>
                              <p className="font-semibold text-slate-800">{warehouse.name}</p>
                              <p className="text-xs text-slate-500">
                                {warehouse.last_report_date ? `Last update: ${formatDate(warehouse.last_report_date)}` : 'No reports yet'}
                              </p>
                            </div>
                          </div>
                          {warehouse.has_discrepancy && (
                            <Badge variant="destructive" className="bg-red-100 text-red-700 border-red-200">
                              <AlertCircle className="w-3 h-3 mr-1" />
                              Discrepancy
                            </Badge>
                          )}
                        </div>
                        <div className="grid grid-cols-4 gap-4 text-center">
                          <div>
                            <p className="text-xs text-slate-500">15kg Filled</p>
                            <p className="font-semibold text-slate-800">{warehouse.closing_15kg_filled}</p>
                          </div>
                          <div>
                            <p className="text-xs text-slate-500">21kg Filled</p>
                            <p className="font-semibold text-slate-800">{warehouse.closing_21kg_filled}</p>
                          </div>
                          <div>
                            <p className="text-xs text-slate-500">15kg Empty</p>
                            <p className="font-semibold text-slate-800">{warehouse.closing_15kg_empty}</p>
                          </div>
                          <div>
                            <p className="text-xs text-slate-500">21kg Empty</p>
                            <p className="font-semibold text-slate-800">{warehouse.closing_21kg_empty}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                    {(!stats?.warehouses || stats.warehouses.length === 0) && (
                      <p className="text-slate-500 text-center py-8">No warehouse data available</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Right Column */}
              <div className="space-y-6">
                {/* Plant Hollongi Status */}
                <Card data-testid="plant-status-card">
                  <CardHeader>
                    <CardTitle className="text-lg font-semibold flex items-center gap-2">
                      <Factory className="w-5 h-5 text-green-700" />
                      Plant Hollongi
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {stats?.plant ? (
                      <div className="space-y-4">
                        <div className="p-4 bg-green-50 rounded-lg">
                          <p className="text-sm text-green-700 font-medium">Bullet Tank</p>
                          <p className="text-2xl font-bold text-green-800">{stats.plant.bullet_tank_kg} kg</p>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="p-3 bg-slate-50 rounded-lg text-center">
                            <p className="text-xs text-slate-500">15kg Filled</p>
                            <p className="font-bold text-slate-800">{stats.plant.closing_15kg_filled}</p>
                          </div>
                          <div className="p-3 bg-slate-50 rounded-lg text-center">
                            <p className="text-xs text-slate-500">21kg Filled</p>
                            <p className="font-bold text-slate-800">{stats.plant.closing_21kg_filled}</p>
                          </div>
                          <div className="p-3 bg-slate-50 rounded-lg text-center">
                            <p className="text-xs text-slate-500">15kg Empty</p>
                            <p className="font-bold text-slate-800">{stats.plant.closing_15kg_empty}</p>
                          </div>
                          <div className="p-3 bg-slate-50 rounded-lg text-center">
                            <p className="text-xs text-slate-500">21kg Empty</p>
                            <p className="font-bold text-slate-800">{stats.plant.closing_21kg_empty}</p>
                          </div>
                        </div>
                        <p className="text-xs text-slate-500 text-center">
                          Last update: {formatDate(stats.plant.last_report_date)}
                        </p>
                      </div>
                    ) : (
                      <p className="text-slate-500 text-center py-4">No plant data available</p>
                    )}
                  </CardContent>
                </Card>

                {/* Quick Discrepancy Summary */}
                <Card data-testid="quick-discrepancy-card">
                  <CardHeader>
                    <CardTitle className="text-lg font-semibold flex items-center gap-2">
                      <AlertTriangle className="w-5 h-5 text-orange-600" />
                      Quick Alerts
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {totalDiscrepancies > 0 ? (
                      <div className="space-y-3">
                        {discrepancyReports.slice(0, 3).map((report) => (
                          <div key={report.id} className="p-3 bg-red-50 border border-red-200 rounded-lg">
                            <div className="flex items-center justify-between mb-2">
                              <p className="font-medium text-red-800">{report.warehouse_name}</p>
                              <span className="text-xs text-red-600">{formatDate(report.date)}</span>
                            </div>
                            <div className="text-xs text-red-700">
                              Click "Stock Discrepancies" tab for details
                            </div>
                          </div>
                        ))}
                        {totalDiscrepancies > 3 && (
                          <Button 
                            variant="ghost" 
                            className="w-full text-red-700"
                            onClick={() => setActiveTab('discrepancies')}
                          >
                            View all {totalDiscrepancies} discrepancies
                          </Button>
                        )}
                      </div>
                    ) : (
                      <div className="text-center py-4">
                        <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-2">
                          <TrendingUp className="w-6 h-6 text-green-600" />
                        </div>
                        <p className="text-slate-600 font-medium">All Clear!</p>
                        <p className="text-slate-500 text-sm">No discrepancies found</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          </TabsContent>

          {/* Connection & Refill Analytics Tab */}
          <TabsContent value="analytics">
            <div className="space-y-4" data-testid="analytics-section">
              {/* Filters */}
              <Card>
                <CardContent className="p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <Select value={analyticsPeriod} onValueChange={setAnalyticsPeriod}>
                      <SelectTrigger className="w-36 h-9 text-sm" data-testid="analytics-period-filter">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="daily">Daily</SelectItem>
                        <SelectItem value="monthly">Monthly</SelectItem>
                        <SelectItem value="quarterly">Quarterly</SelectItem>
                        <SelectItem value="yearly">Yearly</SelectItem>
                        <SelectItem value="custom">Custom Range</SelectItem>
                      </SelectContent>
                    </Select>

                    <Select value={analyticsWarehouse} onValueChange={setAnalyticsWarehouse}>
                      <SelectTrigger className="w-44 h-9 text-sm" data-testid="analytics-warehouse-filter">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Warehouses</SelectItem>
                        {allWarehouses.map(w => (
                          <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>

                    {analyticsPeriod === 'custom' && (
                      <>
                        <Input type="date" value={analyticsStartDate} onChange={e => setAnalyticsStartDate(e.target.value)} className="w-36 h-9 text-sm" data-testid="analytics-start-date" />
                        <Input type="date" value={analyticsEndDate} onChange={e => setAnalyticsEndDate(e.target.value)} className="w-36 h-9 text-sm" data-testid="analytics-end-date" />
                      </>
                    )}

                    <Button variant="outline" size="sm" onClick={fetchAnalytics} className="h-9 gap-1" data-testid="analytics-refresh-btn">
                      <RefreshCw className="w-3.5 h-3.5" /> Refresh
                    </Button>

                    <div className="ml-auto flex gap-2">
                      <Button variant="outline" size="sm" onClick={handleExportAnalyticsPDF} disabled={analyticsExporting} className="h-9 gap-1 text-red-700 border-red-200 hover:bg-red-50" data-testid="analytics-export-pdf">
                        <Download className="w-3.5 h-3.5" /> PDF
                      </Button>
                      <Button variant="outline" size="sm" onClick={handleExportAnalyticsExcel} disabled={analyticsExporting} className="h-9 gap-1 text-green-700 border-green-200 hover:bg-green-50" data-testid="analytics-export-excel">
                        <FileSpreadsheet className="w-3.5 h-3.5" /> Excel
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {analyticsLoading ? (
                <div className="flex items-center justify-center h-40">
                  <Loader2 className="w-8 h-8 animate-spin text-green-600" />
                </div>
              ) : analyticsData ? (
                <>
                  {/* Date Range Info */}
                  {analyticsData.date_range && (
                    <p className="text-xs text-slate-500">
                      <Calendar className="w-3 h-3 inline mr-1" />
                      {analyticsData.date_range.start} to {analyticsData.date_range.end}
                    </p>
                  )}

                  {/* Summary Cards - New Connections */}
                  <div>
                    <h3 className="text-sm font-semibold text-slate-600 mb-2 flex items-center gap-1.5">
                      <Home className="w-4 h-4 text-blue-600" /> New Connections
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                      <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200" data-testid="card-total-new">
                        <CardContent className="p-3 text-center">
                          <p className="text-xs text-blue-700 font-medium">Total New</p>
                          <p className="text-2xl font-bold text-blue-800">{analyticsData.summary.total_new_connections}</p>
                          <p className="text-xs text-blue-500">{analyticsData.summary.domestic_new_cylinders + analyticsData.summary.commercial_new_cylinders} cylinders</p>
                        </CardContent>
                      </Card>
                      <Card className="bg-gradient-to-br from-cyan-50 to-sky-50 border-cyan-200" data-testid="card-domestic-new">
                        <CardContent className="p-3 text-center">
                          <p className="text-xs text-cyan-700 font-medium">Domestic New</p>
                          <p className="text-2xl font-bold text-cyan-800">{analyticsData.summary.domestic_new_connections}</p>
                          <p className="text-xs text-cyan-500">{analyticsData.summary.domestic_new_cylinders} cylinders</p>
                        </CardContent>
                      </Card>
                      <Card className="bg-gradient-to-br from-violet-50 to-purple-50 border-violet-200" data-testid="card-commercial-new">
                        <CardContent className="p-3 text-center">
                          <p className="text-xs text-violet-700 font-medium">Commercial New</p>
                          <p className="text-2xl font-bold text-violet-800">{analyticsData.summary.commercial_new_connections}</p>
                          <p className="text-xs text-violet-500">{analyticsData.summary.commercial_new_cylinders} cylinders</p>
                        </CardContent>
                      </Card>
                    </div>
                  </div>

                  {/* Refill Cards */}
                  <div>
                    <h3 className="text-sm font-semibold text-slate-600 mb-2 flex items-center gap-1.5">
                      <Flame className="w-4 h-4 text-orange-600" /> Refill Activity
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                      <Card className="bg-gradient-to-br from-orange-50 to-amber-50 border-orange-200" data-testid="card-total-refills">
                        <CardContent className="p-3 text-center">
                          <p className="text-xs text-orange-700 font-medium">Total Refills</p>
                          <p className="text-2xl font-bold text-orange-800">{analyticsData.summary.total_refills}</p>
                          <p className="text-xs text-orange-500">{analyticsData.summary.domestic_refill_cylinders + analyticsData.summary.commercial_refill_cylinders} cylinders</p>
                        </CardContent>
                      </Card>
                      <Card className="bg-gradient-to-br from-yellow-50 to-amber-50 border-yellow-200" data-testid="card-domestic-refills">
                        <CardContent className="p-3 text-center">
                          <p className="text-xs text-yellow-700 font-medium">Domestic Refills</p>
                          <p className="text-2xl font-bold text-yellow-800">{analyticsData.summary.domestic_refills}</p>
                          <p className="text-xs text-yellow-500">{analyticsData.summary.domestic_refill_cylinders} cylinders</p>
                        </CardContent>
                      </Card>
                      <Card className="bg-gradient-to-br from-rose-50 to-pink-50 border-rose-200" data-testid="card-commercial-refills">
                        <CardContent className="p-3 text-center">
                          <p className="text-xs text-rose-700 font-medium">Commercial Refills</p>
                          <p className="text-2xl font-bold text-rose-800">{analyticsData.summary.commercial_refills}</p>
                          <p className="text-xs text-rose-500">{analyticsData.summary.commercial_refill_cylinders} cylinders</p>
                        </CardContent>
                      </Card>
                    </div>
                  </div>

                  {/* Warehouse Breakdown Table */}
                  {analyticsData.warehouse_breakdown?.length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
                          <Warehouse className="w-4 h-4" /> Warehouse Breakdown
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="p-0">
                        <div className="overflow-x-auto">
                          <table className="w-full text-xs" data-testid="analytics-warehouse-table">
                            <thead>
                              <tr className="bg-slate-50 border-b">
                                <th className="px-3 py-2 text-left font-semibold text-slate-600">Warehouse</th>
                                <th className="px-2 py-2 text-center font-semibold text-cyan-700">Dom. New</th>
                                <th className="px-2 py-2 text-center font-semibold text-cyan-600">Cyl</th>
                                <th className="px-2 py-2 text-center font-semibold text-violet-700">Com. New</th>
                                <th className="px-2 py-2 text-center font-semibold text-violet-600">Cyl</th>
                                <th className="px-2 py-2 text-center font-semibold text-yellow-700">Dom. Refill</th>
                                <th className="px-2 py-2 text-center font-semibold text-yellow-600">Cyl</th>
                                <th className="px-2 py-2 text-center font-semibold text-rose-700">Com. Refill</th>
                                <th className="px-2 py-2 text-center font-semibold text-rose-600">Cyl</th>
                                <th className="px-2 py-2 text-center font-semibold text-slate-700">Total</th>
                              </tr>
                            </thead>
                            <tbody>
                              {analyticsData.warehouse_breakdown.map((w, i) => {
                                const total = w.domestic_new + w.commercial_new + w.domestic_refill + w.commercial_refill;
                                return (
                                  <tr key={i} className="border-b hover:bg-slate-50/50">
                                    <td className="px-3 py-2 font-medium text-slate-800">{w.warehouse_name}</td>
                                    <td className="px-2 py-2 text-center">{w.domestic_new}</td>
                                    <td className="px-2 py-2 text-center text-slate-500">{w.domestic_new_cyl}</td>
                                    <td className="px-2 py-2 text-center">{w.commercial_new}</td>
                                    <td className="px-2 py-2 text-center text-slate-500">{w.commercial_new_cyl}</td>
                                    <td className="px-2 py-2 text-center">{w.domestic_refill}</td>
                                    <td className="px-2 py-2 text-center text-slate-500">{w.domestic_refill_cyl}</td>
                                    <td className="px-2 py-2 text-center">{w.commercial_refill}</td>
                                    <td className="px-2 py-2 text-center text-slate-500">{w.commercial_refill_cyl}</td>
                                    <td className="px-2 py-2 text-center font-semibold">{total}</td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Date-wise Breakdown Table */}
                  {analyticsData.date_breakdown?.length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-semibold flex items-center gap-1.5">
                          <Calendar className="w-4 h-4" /> Date-wise Breakdown
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="p-0">
                        <div className="overflow-x-auto">
                          <table className="w-full text-xs" data-testid="analytics-date-table">
                            <thead>
                              <tr className="bg-slate-50 border-b">
                                <th className="px-3 py-2 text-left font-semibold text-slate-600">Date</th>
                                <th className="px-2 py-2 text-center font-semibold text-cyan-700">Dom. New</th>
                                <th className="px-2 py-2 text-center font-semibold text-cyan-600">Cyl</th>
                                <th className="px-2 py-2 text-center font-semibold text-violet-700">Com. New</th>
                                <th className="px-2 py-2 text-center font-semibold text-violet-600">Cyl</th>
                                <th className="px-2 py-2 text-center font-semibold text-yellow-700">Dom. Refill</th>
                                <th className="px-2 py-2 text-center font-semibold text-yellow-600">Cyl</th>
                                <th className="px-2 py-2 text-center font-semibold text-rose-700">Com. Refill</th>
                                <th className="px-2 py-2 text-center font-semibold text-rose-600">Cyl</th>
                              </tr>
                            </thead>
                            <tbody>
                              {analyticsData.date_breakdown.map((d, i) => (
                                <tr key={i} className="border-b hover:bg-slate-50/50">
                                  <td className="px-3 py-2 font-medium text-slate-800">{d.date}</td>
                                  <td className="px-2 py-2 text-center">{d.domestic_new}</td>
                                  <td className="px-2 py-2 text-center text-slate-500">{d.domestic_new_cyl}</td>
                                  <td className="px-2 py-2 text-center">{d.commercial_new}</td>
                                  <td className="px-2 py-2 text-center text-slate-500">{d.commercial_new_cyl}</td>
                                  <td className="px-2 py-2 text-center">{d.domestic_refill}</td>
                                  <td className="px-2 py-2 text-center text-slate-500">{d.domestic_refill_cyl}</td>
                                  <td className="px-2 py-2 text-center">{d.commercial_refill}</td>
                                  <td className="px-2 py-2 text-center text-slate-500">{d.commercial_refill_cyl}</td>
                                </tr>
                              ))}
                              {/* Totals row */}
                              <tr className="bg-amber-50 font-semibold border-t-2">
                                <td className="px-3 py-2">TOTAL</td>
                                <td className="px-2 py-2 text-center">{analyticsData.summary.domestic_new_connections}</td>
                                <td className="px-2 py-2 text-center">{analyticsData.summary.domestic_new_cylinders}</td>
                                <td className="px-2 py-2 text-center">{analyticsData.summary.commercial_new_connections}</td>
                                <td className="px-2 py-2 text-center">{analyticsData.summary.commercial_new_cylinders}</td>
                                <td className="px-2 py-2 text-center">{analyticsData.summary.domestic_refills}</td>
                                <td className="px-2 py-2 text-center">{analyticsData.summary.domestic_refill_cylinders}</td>
                                <td className="px-2 py-2 text-center">{analyticsData.summary.commercial_refills}</td>
                                <td className="px-2 py-2 text-center">{analyticsData.summary.commercial_refill_cylinders}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </>
              ) : (
                <div className="flex flex-col items-center justify-center h-40 text-slate-400">
                  <BarChart3 className="w-12 h-12 mb-2" />
                  <p className="text-sm">Select filters and click Refresh to load analytics</p>
                </div>
              )}
            </div>
          </TabsContent>

          {/* Order Analysis Tab */}
          <TabsContent value="orders">
            <div className="space-y-4">
              {/* Filters */}
              <Card>
                <CardContent className="p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <Select value={orderFilterWarehouse} onValueChange={setOrderFilterWarehouse}>
                      <SelectTrigger className="w-44 h-9 text-sm" data-testid="order-warehouse-filter">
                        <SelectValue placeholder="Warehouse" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Warehouses</SelectItem>
                        {allWarehouses.map(w => (
                          <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Select value={orderFilterStatus} onValueChange={setOrderFilterStatus}>
                      <SelectTrigger className="w-36 h-9 text-sm" data-testid="order-status-filter">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Status</SelectItem>
                        <SelectItem value="pending">Pending</SelectItem>
                        <SelectItem value="delivered">Delivered</SelectItem>
                        <SelectItem value="cancelled">Cancelled</SelectItem>
                      </SelectContent>
                    </Select>
                    <Select value={orderFilterDateRange} onValueChange={setOrderFilterDateRange}>
                      <SelectTrigger className="w-32 h-9 text-sm" data-testid="order-date-filter">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="today">Today</SelectItem>
                        <SelectItem value="week">This Week</SelectItem>
                        <SelectItem value="month">This Month</SelectItem>
                        <SelectItem value="year">This Year</SelectItem>
                        <SelectItem value="custom">Custom</SelectItem>
                      </SelectContent>
                    </Select>
                    {orderFilterDateRange === 'custom' && (
                      <>
                        <Input type="date" value={orderStartDate} onChange={e => setOrderStartDate(e.target.value)} className="w-36 h-9 text-sm" />
                        <Input type="date" value={orderEndDate} onChange={e => setOrderEndDate(e.target.value)} className="w-36 h-9 text-sm" />
                      </>
                    )}
                    <div className="relative flex-1 min-w-[180px]">
                      <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-slate-400" />
                      <Input 
                        placeholder="Search orders..." 
                        value={orderSearch} 
                        onChange={e => setOrderSearch(e.target.value)}
                        className="pl-9 h-9 text-sm"
                        data-testid="order-search-input"
                      />
                    </div>
                    <Button variant="outline" size="sm" onClick={fetchOrderAnalysis} className="h-9 gap-1" data-testid="order-refresh-btn">
                      <RefreshCw className="w-3.5 h-3.5" /> Refresh
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleExportOrderPDF} disabled={orderExporting} className="h-9 gap-1 border-red-300 text-red-700 hover:bg-red-50" data-testid="order-export-pdf">
                      {orderExporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} PDF
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleExportOrderExcel} disabled={orderExporting} className="h-9 gap-1 border-green-300 text-green-700 hover:bg-green-50" data-testid="order-export-excel">
                      {orderExporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileSpreadsheet className="w-3.5 h-3.5" />} Excel
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Summary Cards */}
              {orderAnalysis && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200" data-testid="order-total-card">
                    <CardContent className="p-4">
                      <p className="text-sm text-blue-600 font-medium flex items-center gap-1"><ShoppingCart className="w-4 h-4" /> Total Orders</p>
                      <p className="text-3xl font-bold text-blue-800 mt-1">{orderAnalysis.summary.total_orders}</p>
                      <p className="text-xs text-blue-500 mt-1">Qty: {orderAnalysis.summary.total_quantity}</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200" data-testid="order-pending-card">
                    <CardContent className="p-4">
                      <p className="text-sm text-amber-600 font-medium flex items-center gap-1"><Clock className="w-4 h-4" /> Pending</p>
                      <p className="text-3xl font-bold text-amber-800 mt-1">{orderAnalysis.summary.total_pending}</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200" data-testid="order-delivered-card">
                    <CardContent className="p-4">
                      <p className="text-sm text-green-600 font-medium flex items-center gap-1"><CheckCircle2 className="w-4 h-4" /> Delivered</p>
                      <p className="text-3xl font-bold text-green-800 mt-1">{orderAnalysis.summary.total_delivered}</p>
                    </CardContent>
                  </Card>
                  <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200" data-testid="order-breakdown-card">
                    <CardContent className="p-4">
                      <p className="text-sm text-purple-600 font-medium flex items-center gap-1"><Warehouse className="w-4 h-4" /> Warehouse Split</p>
                      <div className="mt-1 space-y-0.5">
                        {Object.entries(orderAnalysis.summary.warehouse_breakdown || {}).map(([wh, cnt]) => (
                          <div key={wh} className="flex justify-between text-xs">
                            <span className="text-purple-700 font-medium">{wh}</span>
                            <span className="text-purple-800 font-bold">{cnt}</span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}

              {/* Date-grouped Orders */}
              {orderLoading ? (
                <div className="flex items-center justify-center py-16">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                </div>
              ) : orderAnalysis && orderAnalysis.groups.length > 0 ? (
                <div className="space-y-4">
                  {orderAnalysis.groups.map(group => (
                    <Card key={group.date} data-testid={`order-group-${group.date}`}>
                      <CardHeader className="py-3 px-4 bg-blue-50 border-b border-blue-100">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-sm font-semibold text-blue-800 flex items-center gap-2">
                            <Calendar className="w-4 h-4" />
                            {(() => { try { return new Date(group.date).toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }); } catch { return group.date; } })()}
                          </CardTitle>
                          <Badge className="bg-blue-100 text-blue-800 text-xs">{group.count} orders</Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="p-0">
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b border-slate-200 bg-slate-50">
                                <th className="text-left py-2 px-3 text-xs font-medium text-slate-600">Order No</th>
                                <th className="text-left py-2 px-3 text-xs font-medium text-slate-600">Customer</th>
                                <th className="text-left py-2 px-3 text-xs font-medium text-slate-600">Product</th>
                                <th className="text-center py-2 px-3 text-xs font-medium text-slate-600">Qty</th>
                                <th className="text-center py-2 px-3 text-xs font-medium text-slate-600">Status</th>
                                <th className="text-center py-2 px-3 text-xs font-medium text-slate-600">Payment</th>
                                <th className="text-left py-2 px-3 text-xs font-medium text-slate-600">Warehouse</th>
                                <th className="text-left py-2 px-3 text-xs font-medium text-slate-600">Delivery</th>
                              </tr>
                            </thead>
                            <tbody>
                              {group.orders.map(o => (
                                <tr key={o.id} className="border-b border-slate-100 hover:bg-slate-50">
                                  <td className="py-2 px-3 font-medium text-blue-700">{o.order_no}</td>
                                  <td className="py-2 px-3">
                                    <div className="font-medium text-slate-800">{o.customer_name}</div>
                                    {o.mobile_number && <div className="text-xs text-slate-400">{o.mobile_number}</div>}
                                  </td>
                                  <td className="py-2 px-3">
                                    <Badge variant="outline" className="text-xs">{o.product}</Badge>
                                  </td>
                                  <td className="text-center py-2 px-3 font-semibold">{o.quantity}</td>
                                  <td className="text-center py-2 px-3">
                                    {o.status === 'delivered' ? (
                                      <Badge className="bg-green-100 text-green-800 text-xs"><CheckCircle2 className="w-3 h-3 mr-0.5" />Delivered</Badge>
                                    ) : o.status === 'cancelled' ? (
                                      <Badge className="bg-red-100 text-red-800 text-xs">Cancelled</Badge>
                                    ) : (
                                      <Badge className="bg-amber-100 text-amber-800 text-xs"><Clock className="w-3 h-3 mr-0.5" />Pending</Badge>
                                    )}
                                  </td>
                                  <td className="text-center py-2 px-3">
                                    <Badge variant="outline" className="text-xs">{o.payment_mode?.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</Badge>
                                  </td>
                                  <td className="py-2 px-3 text-xs font-medium text-slate-600">{o.warehouse_name}</td>
                                  <td className="py-2 px-3 text-xs text-slate-500">
                                    {o.delivered_at ? (() => { try { return new Date(o.delivered_at).toLocaleDateString('en-IN', { day: '2-digit', month: '2-digit', year: 'numeric' }); } catch { return '-'; } })() : '-'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <Card>
                  <CardContent className="py-16 text-center">
                    <ShoppingCart className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                    <p className="text-slate-500 font-medium">No orders found for the selected filters</p>
                  </CardContent>
                </Card>
              )}
            </div>
          </TabsContent>


          {/* Discrepancies Tab */}
          <TabsContent value="discrepancies">
            <Card data-testid="discrepancies-detail-card">
              <CardHeader>
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-600" />
                  Stock Discrepancies - Detailed View
                </CardTitle>
              </CardHeader>
              <CardContent>
                {discrepancyReports.length > 0 ? (
                  <div className="space-y-4">
                    {discrepancyReports.map((report) => (
                      <div key={report.id} className="p-4 bg-red-50 border border-red-200 rounded-lg" data-testid={`discrepancy-${report.id}`}>
                        <div className="flex items-center justify-between mb-4">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
                              <AlertCircle className="w-5 h-5 text-red-700" />
                            </div>
                            <div>
                              <p className="font-bold text-red-800 text-lg">{report.warehouse_name}</p>
                              <p className="text-sm text-red-600">Report Date: {formatDate(report.date)}</p>
                            </div>
                          </div>
                          <Badge variant="destructive" className="bg-red-600 text-white">
                            Stock Mismatch
                          </Badge>
                        </div>
                        
                        {/* Discrepancy Details Table */}
                        <div className="bg-white rounded-lg p-4 border border-red-100">
                          <h4 className="font-semibold text-slate-700 mb-3">Difference in Stock (Actual vs Expected)</h4>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            {/* 15kg Filled */}
                            <div className={`p-3 rounded-lg ${report.discrepancy_15kg_filled !== 0 ? 'bg-red-100' : 'bg-slate-50'}`}>
                              <p className="text-xs text-slate-600 mb-1">15kg Filled</p>
                              <div className="flex items-center gap-1">
                                {report.discrepancy_15kg_filled !== 0 ? (
                                  <>
                                    {report.discrepancy_15kg_filled > 0 ? (
                                      <ArrowUpRight className="w-4 h-4 text-green-600" />
                                    ) : (
                                      <ArrowDownRight className="w-4 h-4 text-red-600" />
                                    )}
                                    <span className={`font-bold text-lg ${report.discrepancy_15kg_filled > 0 ? 'text-green-700' : 'text-red-700'}`}>
                                      {report.discrepancy_15kg_filled > 0 ? '+' : ''}{report.discrepancy_15kg_filled}
                                    </span>
                                    <span className="text-xs text-slate-500">units</span>
                                  </>
                                ) : (
                                  <span className="text-slate-500 text-sm">No difference</span>
                                )}
                              </div>
                            </div>

                            {/* 21kg Filled */}
                            <div className={`p-3 rounded-lg ${report.discrepancy_21kg_filled !== 0 ? 'bg-red-100' : 'bg-slate-50'}`}>
                              <p className="text-xs text-slate-600 mb-1">21kg Filled</p>
                              <div className="flex items-center gap-1">
                                {report.discrepancy_21kg_filled !== 0 ? (
                                  <>
                                    {report.discrepancy_21kg_filled > 0 ? (
                                      <ArrowUpRight className="w-4 h-4 text-green-600" />
                                    ) : (
                                      <ArrowDownRight className="w-4 h-4 text-red-600" />
                                    )}
                                    <span className={`font-bold text-lg ${report.discrepancy_21kg_filled > 0 ? 'text-green-700' : 'text-red-700'}`}>
                                      {report.discrepancy_21kg_filled > 0 ? '+' : ''}{report.discrepancy_21kg_filled}
                                    </span>
                                    <span className="text-xs text-slate-500">units</span>
                                  </>
                                ) : (
                                  <span className="text-slate-500 text-sm">No difference</span>
                                )}
                              </div>
                            </div>

                            {/* 15kg Empty */}
                            <div className={`p-3 rounded-lg ${report.discrepancy_15kg_empty !== 0 ? 'bg-red-100' : 'bg-slate-50'}`}>
                              <p className="text-xs text-slate-600 mb-1">15kg Empty</p>
                              <div className="flex items-center gap-1">
                                {report.discrepancy_15kg_empty !== 0 ? (
                                  <>
                                    {report.discrepancy_15kg_empty > 0 ? (
                                      <ArrowUpRight className="w-4 h-4 text-green-600" />
                                    ) : (
                                      <ArrowDownRight className="w-4 h-4 text-red-600" />
                                    )}
                                    <span className={`font-bold text-lg ${report.discrepancy_15kg_empty > 0 ? 'text-green-700' : 'text-red-700'}`}>
                                      {report.discrepancy_15kg_empty > 0 ? '+' : ''}{report.discrepancy_15kg_empty}
                                    </span>
                                    <span className="text-xs text-slate-500">units</span>
                                  </>
                                ) : (
                                  <span className="text-slate-500 text-sm">No difference</span>
                                )}
                              </div>
                            </div>

                            {/* 21kg Empty */}
                            <div className={`p-3 rounded-lg ${report.discrepancy_21kg_empty !== 0 ? 'bg-red-100' : 'bg-slate-50'}`}>
                              <p className="text-xs text-slate-600 mb-1">21kg Empty</p>
                              <div className="flex items-center gap-1">
                                {report.discrepancy_21kg_empty !== 0 ? (
                                  <>
                                    {report.discrepancy_21kg_empty > 0 ? (
                                      <ArrowUpRight className="w-4 h-4 text-green-600" />
                                    ) : (
                                      <ArrowDownRight className="w-4 h-4 text-red-600" />
                                    )}
                                    <span className={`font-bold text-lg ${report.discrepancy_21kg_empty > 0 ? 'text-green-700' : 'text-red-700'}`}>
                                      {report.discrepancy_21kg_empty > 0 ? '+' : ''}{report.discrepancy_21kg_empty}
                                    </span>
                                    <span className="text-xs text-slate-500">units</span>
                                  </>
                                ) : (
                                  <span className="text-slate-500 text-sm">No difference</span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Remarks if any */}
                        {report.remarks && (
                          <div className="mt-3 p-3 bg-white rounded-lg border border-red-100">
                            <p className="text-xs text-slate-500 mb-1">Warehouse Manager Remarks:</p>
                            <p className="text-sm text-slate-700">{report.remarks}</p>
                          </div>
                        )}

                        {/* Submitted info */}
                        <div className="mt-3 text-xs text-red-600">
                          Submitted by: {report.submitted_by} on {formatDate(report.submitted_at)}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                      <TrendingUp className="w-8 h-8 text-green-600" />
                    </div>
                    <p className="text-slate-700 font-semibold text-lg">No Stock Discrepancies</p>
                    <p className="text-slate-500 mt-1">All warehouse reports are matching expected stock levels.</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
};

export default Dashboard;
