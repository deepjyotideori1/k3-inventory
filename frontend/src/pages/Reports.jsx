import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { getDailyReports, getPlantReports, getWarehouses, exportPDF, exportExcel } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
  FileText,
  Download,
  Filter,
  Loader2,
  Calendar,
  RefreshCw,
  FileEdit
} from 'lucide-react';
import { formatDate, getDateRange } from '../lib/utils';
import { toast } from 'sonner';

const Reports = () => {
  const { isAdmin, user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [dailyReports, setDailyReports] = useState([]);
  const [plantReports, setPlantReports] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [activeTab, setActiveTab] = useState('daily');
  
  const [filters, setFilters] = useState({
    warehouse_id: 'all',
    period: 'weekly',
    start_date: '',
    end_date: ''
  });

  useEffect(() => {
    fetchWarehouses();
    const range = getDateRange('weekly');
    setFilters(prev => ({ ...prev, start_date: range.startDate, end_date: range.endDate }));
  }, []);

  useEffect(() => {
    if (filters.start_date && filters.end_date) {
      fetchReports();
    }
  }, [filters, activeTab]);

  const fetchWarehouses = async () => {
    try {
      const response = await getWarehouses();
      setWarehouses(response.data.filter(w => !w.is_plant));
    } catch (error) {
      console.error('Failed to fetch warehouses:', error);
    }
  };

  const fetchReports = async () => {
    setLoading(true);
    try {
      if (activeTab === 'daily') {
        const params = {
          start_date: filters.start_date,
          end_date: filters.end_date
        };
        if (filters.warehouse_id && filters.warehouse_id !== 'all') {
          params.warehouse_id = filters.warehouse_id;
        }
        if (!isAdmin && user?.warehouse_id) {
          params.warehouse_id = user.warehouse_id;
        }
        const response = await getDailyReports(params);
        setDailyReports(response.data);
      } else {
        const params = {
          start_date: filters.start_date,
          end_date: filters.end_date
        };
        const response = await getPlantReports(params);
        setPlantReports(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch reports:', error);
      toast.error('Failed to load reports');
    } finally {
      setLoading(false);
    }
  };

  const handlePeriodChange = (period) => {
    const range = getDateRange(period);
    setFilters(prev => ({
      ...prev,
      period,
      start_date: range.startDate,
      end_date: range.endDate
    }));
  };

  const handleExportPDF = async () => {
    const params = {
      report_type: activeTab,
      start_date: filters.start_date,
      end_date: filters.end_date
    };
    if (filters.warehouse_id && filters.warehouse_id !== 'all') {
      params.warehouse_id = filters.warehouse_id;
    }
    try {
      await exportPDF(params);
      toast.success('PDF downloaded successfully');
    } catch (error) {
      toast.error('Failed to download PDF');
    }
  };

  const handleExportExcel = async () => {
    const params = {
      report_type: activeTab,
      start_date: filters.start_date,
      end_date: filters.end_date
    };
    if (filters.warehouse_id && filters.warehouse_id !== 'all') {
      params.warehouse_id = filters.warehouse_id;
    }
    try {
      await exportExcel(params);
      toast.success('Excel downloaded successfully');
    } catch (error) {
      toast.error('Failed to download Excel');
    }
  };

  return (
    <Layout>
      <div className="space-y-6" data-testid="reports-page">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-800 flex items-center gap-2">
              <FileText className="w-8 h-8 text-green-700" />
              {isAdmin ? 'Reports' : 'My Reports'}
            </h1>
            <p className="text-slate-500 mt-1">View and export inventory reports</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={handleExportPDF} className="gap-2" data-testid="export-pdf-btn">
              <Download className="w-4 h-4" />
              PDF
            </Button>
            <Button variant="outline" onClick={handleExportExcel} className="gap-2" data-testid="export-excel-btn">
              <Download className="w-4 h-4" />
              Excel
            </Button>
          </div>
        </div>

        {/* Filters */}
        <Card data-testid="filters-card">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Filter className="w-5 h-5" />
              Filters
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div>
                <Label className="text-slate-600">Period</Label>
                <Select value={filters.period} onValueChange={handlePeriodChange}>
                  <SelectTrigger className="mt-1" data-testid="period-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">Daily</SelectItem>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="yearly">Yearly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              {isAdmin && (
                <div>
                  <Label className="text-slate-600">Warehouse</Label>
                  <Select 
                    value={filters.warehouse_id} 
                    onValueChange={(val) => setFilters(prev => ({ ...prev, warehouse_id: val }))}
                  >
                    <SelectTrigger className="mt-1" data-testid="warehouse-select">
                      <SelectValue placeholder="All Warehouses" />
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
                <Label className="text-slate-600">Start Date</Label>
                <Input 
                  type="date" 
                  value={filters.start_date}
                  onChange={(e) => setFilters(prev => ({ ...prev, start_date: e.target.value }))}
                  className="mt-1"
                  data-testid="start-date-input"
                />
              </div>
              
              <div>
                <Label className="text-slate-600">End Date</Label>
                <Input 
                  type="date" 
                  value={filters.end_date}
                  onChange={(e) => setFilters(prev => ({ ...prev, end_date: e.target.value }))}
                  className="mt-1"
                  data-testid="end-date-input"
                />
              </div>
            </div>
            
            <div className="mt-4 flex justify-end">
              <Button onClick={fetchReports} className="gap-2 bg-green-700 hover:bg-green-800" data-testid="apply-filters-btn">
                <RefreshCw className="w-4 h-4" />
                Apply Filters
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Tabs */}
        {isAdmin && (
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="daily" data-testid="daily-tab">Daily Reports</TabsTrigger>
              <TabsTrigger value="plant" data-testid="plant-tab">Plant Hollongi</TabsTrigger>
            </TabsList>

            <TabsContent value="daily" className="mt-4">
              <Card data-testid="daily-reports-card">
                <CardContent className="p-0">
                  {loading ? (
                    <div className="flex items-center justify-center h-64">
                      <Loader2 className="w-8 h-8 animate-spin text-green-700" />
                    </div>
                  ) : dailyReports.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Warehouse</th>
                            <th>15kg Filled</th>
                            <th>21kg Filled</th>
                            <th>15kg Empty</th>
                            <th>21kg Empty</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dailyReports.map((report) => (
                            <tr key={report.id} data-testid={`report-row-${report.id}`}>
                              <td>{formatDate(report.date)}</td>
                              <td className="font-medium">{report.warehouse_name}</td>
                              <td>{report.closing_15kg_filled}</td>
                              <td>{report.closing_21kg_filled}</td>
                              <td>{report.closing_15kg_empty}</td>
                              <td>{report.closing_21kg_empty}</td>
                              <td>
                                {report.has_discrepancy ? (
                                  <Badge variant="destructive" className="bg-red-100 text-red-700">
                                    Discrepancy
                                  </Badge>
                                ) : (
                                  <Badge className="bg-green-100 text-green-700">OK</Badge>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-12">
                      <Calendar className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                      <p className="text-slate-500">No reports found for the selected period</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="plant" className="mt-4">
              <Card data-testid="plant-reports-card">
                <CardContent className="p-0">
                  {loading ? (
                    <div className="flex items-center justify-center h-64">
                      <Loader2 className="w-8 h-8 animate-spin text-green-700" />
                    </div>
                  ) : plantReports.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Date</th>
                            <th>Bullet Tank (kg)</th>
                            <th>15kg Filled</th>
                            <th>21kg Filled</th>
                            <th>15kg Empty</th>
                            <th>21kg Empty</th>
                            <th>Refilled 15kg</th>
                            <th>Refilled 21kg</th>
                          </tr>
                        </thead>
                        <tbody>
                          {plantReports.map((report) => (
                            <tr key={report.id} data-testid={`plant-report-row-${report.id}`}>
                              <td>{formatDate(report.date)}</td>
                              <td className="font-medium">{report.closing_bullet_tank_kg}</td>
                              <td>{report.closing_15kg_filled}</td>
                              <td>{report.closing_21kg_filled}</td>
                              <td>{report.closing_15kg_empty}</td>
                              <td>{report.closing_21kg_empty}</td>
                              <td>{report.day_refilled_15kg}</td>
                              <td>{report.day_refilled_21kg}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-12">
                      <Calendar className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                      <p className="text-slate-500">No plant reports found for the selected period</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        )}

        {/* Non-admin view */}
        {!isAdmin && (
          <Card data-testid="my-reports-card">
            <CardContent className="p-0">
              {loading ? (
                <div className="flex items-center justify-center h-64">
                  <Loader2 className="w-8 h-8 animate-spin text-green-700" />
                </div>
              ) : dailyReports.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>15kg Filled</th>
                        <th>21kg Filled</th>
                        <th>15kg Empty</th>
                        <th>21kg Empty</th>
                        <th>Status</th>
                        <th>Submitted By</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dailyReports.map((report) => (
                        <tr key={report.id} data-testid={`report-row-${report.id}`}>
                          <td>{formatDate(report.date)}</td>
                          <td>{report.closing_15kg_filled}</td>
                          <td>{report.closing_21kg_filled}</td>
                          <td>{report.closing_15kg_empty}</td>
                          <td>{report.closing_21kg_empty}</td>
                          <td>
                            {report.has_discrepancy ? (
                              <Badge variant="destructive" className="bg-red-100 text-red-700">
                                Discrepancy
                              </Badge>
                            ) : (
                              <Badge className="bg-green-100 text-green-700">OK</Badge>
                            )}
                          </td>
                          <td className="text-slate-500 text-sm">{report.submitted_by}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <Calendar className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                  <p className="text-slate-500">No reports found for the selected period</p>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default Reports;
