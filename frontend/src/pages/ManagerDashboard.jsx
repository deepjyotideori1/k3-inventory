import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { getLatestClosing, getDailyReports, getLatestPlantClosing } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { 
  Package, 
  ClipboardList,
  FileText,
  TrendingUp,
  RefreshCw,
  Loader2,
  Calendar
} from 'lucide-react';
import { formatDate, getTodayDate } from '../lib/utils';
import { toast } from 'sonner';

const ManagerDashboard = () => {
  const { user } = useAuth();
  const [stock, setStock] = useState(null);
  const [recentReports, setRecentReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const isPlantManager = user?.warehouse_name === 'Plant Hollongi';

  useEffect(() => {
    fetchData();
  }, [user]);

  const fetchData = async () => {
    if (!user?.warehouse_id) return;
    
    setLoading(true);
    try {
      if (isPlantManager) {
        const stockRes = await getLatestPlantClosing();
        setStock(stockRes.data);
      } else {
        const stockRes = await getLatestClosing(user.warehouse_id);
        setStock(stockRes.data);
      }
      
      const reportsRes = await getDailyReports({ warehouse_id: user.warehouse_id });
      setRecentReports(reportsRes.data.slice(0, 5));
    } catch (error) {
      console.error('Failed to fetch data:', error);
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
      <div className="space-y-6" data-testid="manager-dashboard">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-800">
              {user?.warehouse_name || 'Warehouse'} Dashboard
            </h1>
            <p className="text-slate-500 mt-1">Welcome back, {user?.name}</p>
          </div>
          <Button onClick={fetchData} variant="outline" className="gap-2" data-testid="refresh-btn">
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link to={isPlantManager ? '/plant-entry' : '/daily-entry'} data-testid="daily-entry-link">
            <Card className="card-hover cursor-pointer border-2 border-green-200 bg-green-50">
              <CardContent className="p-6 flex items-center gap-4">
                <div className="w-14 h-14 rounded-xl bg-green-700 flex items-center justify-center">
                  <ClipboardList className="w-7 h-7 text-white" />
                </div>
                <div>
                  <p className="font-bold text-lg text-green-800">
                    {isPlantManager ? 'Plant Entry' : 'Daily Entry'}
                  </p>
                  <p className="text-green-600 text-sm">Submit today's stock report</p>
                </div>
              </CardContent>
            </Card>
          </Link>

          <Link to="/my-reports" data-testid="my-reports-link">
            <Card className="card-hover cursor-pointer">
              <CardContent className="p-6 flex items-center gap-4">
                <div className="w-14 h-14 rounded-xl bg-blue-100 flex items-center justify-center">
                  <FileText className="w-7 h-7 text-blue-700" />
                </div>
                <div>
                  <p className="font-bold text-lg text-slate-800">View Reports</p>
                  <p className="text-slate-500 text-sm">Check your submitted reports</p>
                </div>
              </CardContent>
            </Card>
          </Link>
        </div>

        {/* Current Stock */}
        <Card data-testid="current-stock-card">
          <CardHeader>
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Package className="w-5 h-5 text-green-700" />
              Current Stock (Opening for Today)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {stock?.last_date ? (
              <>
                <p className="text-sm text-slate-500 mb-4">
                  Based on closing stock of {formatDate(stock.last_date)}
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-4 bg-green-50 rounded-lg text-center">
                    <p className="text-sm text-green-700 font-medium">15kg Filled</p>
                    <p className="text-3xl font-bold text-green-800 mt-1">{stock.opening_15kg_filled}</p>
                  </div>
                  <div className="p-4 bg-blue-50 rounded-lg text-center">
                    <p className="text-sm text-blue-700 font-medium">21kg Filled</p>
                    <p className="text-3xl font-bold text-blue-800 mt-1">{stock.opening_21kg_filled}</p>
                  </div>
                  <div className="p-4 bg-slate-100 rounded-lg text-center">
                    <p className="text-sm text-slate-600 font-medium">15kg Empty</p>
                    <p className="text-3xl font-bold text-slate-800 mt-1">{stock.opening_15kg_empty}</p>
                  </div>
                  <div className="p-4 bg-slate-100 rounded-lg text-center">
                    <p className="text-sm text-slate-600 font-medium">21kg Empty</p>
                    <p className="text-3xl font-bold text-slate-800 mt-1">{stock.opening_21kg_empty}</p>
                  </div>
                </div>
                {isPlantManager && stock.opening_bullet_tank_kg !== undefined && (
                  <div className="mt-4 p-4 bg-amber-50 rounded-lg text-center">
                    <p className="text-sm text-amber-700 font-medium">Bullet Tank</p>
                    <p className="text-3xl font-bold text-amber-800 mt-1">{stock.opening_bullet_tank_kg} kg</p>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-8">
                <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-3">
                  <Package className="w-8 h-8 text-slate-400" />
                </div>
                <p className="text-slate-600 font-medium">No previous stock data</p>
                <p className="text-slate-500 text-sm mt-1">Submit your first daily entry to start tracking</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Reports */}
        <Card data-testid="recent-reports-card">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Calendar className="w-5 h-5 text-green-700" />
              Recent Reports
            </CardTitle>
            <Link to="/my-reports">
              <Button variant="ghost" size="sm" className="text-green-700">
                View All
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {recentReports.length > 0 ? (
              <div className="space-y-3">
                {recentReports.map((report) => (
                  <div 
                    key={report.id} 
                    className="p-4 bg-slate-50 rounded-lg flex items-center justify-between"
                    data-testid={`report-row-${report.id}`}
                  >
                    <div>
                      <p className="font-medium text-slate-800">{formatDate(report.date)}</p>
                      <p className="text-sm text-slate-500">
                        15kg: {report.closing_15kg_filled} filled, {report.closing_15kg_empty} empty | 
                        21kg: {report.closing_21kg_filled} filled, {report.closing_21kg_empty} empty
                      </p>
                    </div>
                    {report.has_discrepancy ? (
                      <Badge variant="destructive" className="bg-red-100 text-red-700 border-red-200">
                        Discrepancy
                      </Badge>
                    ) : (
                      <Badge className="bg-green-100 text-green-700 border-green-200">
                        <TrendingUp className="w-3 h-3 mr-1" />
                        OK
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <p className="text-slate-500">No reports submitted yet</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default ManagerDashboard;
