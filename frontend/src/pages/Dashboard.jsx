import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import { getDashboardStats, getDailyReports } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
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
  PackageOpen
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

  useEffect(() => {
    fetchStats();
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
