import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import { getDashboardStats, getWarehouses } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { 
  Warehouse, 
  Package, 
  AlertTriangle, 
  TrendingUp,
  RefreshCw,
  Factory,
  ChevronRight,
  Loader2
} from 'lucide-react';
import { formatDate } from '../lib/utils';
import { toast } from 'sonner';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const response = await getDashboardStats();
      setStats(response.data);
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

          <Card className="card-hover" data-testid="stat-discrepancies">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-slate-500 text-sm font-medium">Active Alerts</p>
                  <p className="text-3xl font-bold text-slate-800 mt-1">{stats?.discrepancies?.length || 0}</p>
                </div>
                <div className="w-12 h-12 rounded-xl bg-orange-100 flex items-center justify-center">
                  <AlertTriangle className="w-6 h-6 text-orange-700" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

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
                    className="p-4 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors"
                    data-testid={`warehouse-row-${warehouse.id}`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                          <Warehouse className="w-5 h-5 text-green-700" />
                        </div>
                        <div>
                          <p className="font-semibold text-slate-800">{warehouse.name}</p>
                          <p className="text-xs text-slate-500">Last update: {formatDate(warehouse.last_report_date)}</p>
                        </div>
                      </div>
                      {warehouse.has_discrepancy && (
                        <Badge variant="destructive" className="bg-red-100 text-red-700 border-red-200">
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

            {/* Discrepancy Alerts */}
            <Card data-testid="discrepancy-alerts-card">
              <CardHeader>
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-orange-600" />
                  Discrepancy Alerts
                </CardTitle>
              </CardHeader>
              <CardContent>
                {stats?.discrepancies?.length > 0 ? (
                  <div className="space-y-3">
                    {stats.discrepancies.map((d, i) => (
                      <div key={i} className="p-3 bg-orange-50 border border-orange-200 rounded-lg">
                        <p className="font-medium text-orange-800">{d.warehouse_name}</p>
                        <p className="text-xs text-orange-600">{formatDate(d.date)}</p>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                          {d.discrepancy_15kg_filled !== 0 && (
                            <span className={d.discrepancy_15kg_filled > 0 ? 'text-green-600' : 'text-red-600'}>
                              15kg F: {d.discrepancy_15kg_filled > 0 ? '+' : ''}{d.discrepancy_15kg_filled}
                            </span>
                          )}
                          {d.discrepancy_21kg_filled !== 0 && (
                            <span className={d.discrepancy_21kg_filled > 0 ? 'text-green-600' : 'text-red-600'}>
                              21kg F: {d.discrepancy_21kg_filled > 0 ? '+' : ''}{d.discrepancy_21kg_filled}
                            </span>
                          )}
                          {d.discrepancy_15kg_empty !== 0 && (
                            <span className={d.discrepancy_15kg_empty > 0 ? 'text-green-600' : 'text-red-600'}>
                              15kg E: {d.discrepancy_15kg_empty > 0 ? '+' : ''}{d.discrepancy_15kg_empty}
                            </span>
                          )}
                          {d.discrepancy_21kg_empty !== 0 && (
                            <span className={d.discrepancy_21kg_empty > 0 ? 'text-green-600' : 'text-red-600'}>
                              21kg E: {d.discrepancy_21kg_empty > 0 ? '+' : ''}{d.discrepancy_21kg_empty}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
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
      </div>
    </Layout>
  );
};

export default Dashboard;
