import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import { getDashboardStats, getDailyReports } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
  Warehouse, 
  Package, 
  AlertTriangle, 
  TrendingUp,
  RefreshCw,
  Factory,
  ChevronRight,
  Loader2,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';
import { formatDate } from '../lib/utils';
import { toast } from 'sonner';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [discrepancyReports, setDiscrepancyReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const [statsRes, reportsRes] = await Promise.all([
        getDashboardStats(),
        getDailyReports({})
      ]);
      setStats(statsRes.data);
      
      // Filter reports with discrepancies
      const discReports = reportsRes.data.filter(r => r.has_discrepancy);
      setDiscrepancyReports(discReports);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      toast.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

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
          <Button onClick={fetchStats} variant="outline" className="gap-2" data-testid="refresh-btn">
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

          <Card className="card-hover" data-testid="stat-15kg-filled">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-slate-500 text-sm font-medium">15kg Filled Total</p>
                  <p className="text-3xl font-bold text-slate-800 mt-1">{stats?.total_15kg_filled || 0}</p>
                </div>
                <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
                  <Package className="w-6 h-6 text-blue-700" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="card-hover" data-testid="stat-21kg-filled">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-slate-500 text-sm font-medium">21kg Filled Total</p>
                  <p className="text-3xl font-bold text-slate-800 mt-1">{stats?.total_21kg_filled || 0}</p>
                </div>
                <div className="w-12 h-12 rounded-xl bg-purple-100 flex items-center justify-center">
                  <Package className="w-6 h-6 text-purple-700" />
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
