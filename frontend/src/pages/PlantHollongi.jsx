import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import { getPlantReports, getWarehouses, exportPDF, exportExcel, getPlantIssuanceHistory } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { 
  Factory,
  Download,
  Filter,
  Loader2,
  Calendar,
  RefreshCw,
  Truck,
  ArrowDownToLine,
  Send,
  Package
} from 'lucide-react';
import { formatDate, getDateRange } from '../lib/utils';
import { toast } from 'sonner';

const PlantHollongi = () => {
  const [loading, setLoading] = useState(true);
  const [reports, setReports] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [issuanceHistory, setIssuanceHistory] = useState([]);
  
  const [filters, setFilters] = useState({
    start_date: '',
    end_date: ''
  });

  useEffect(() => {
    const range = getDateRange('monthly');
    setFilters({ start_date: range.startDate, end_date: range.endDate });
    fetchWarehouses();
  }, []);

  useEffect(() => {
    if (filters.start_date && filters.end_date) {
      fetchReports();
      fetchIssuanceHistory();
    }
  }, [filters]);

  const fetchIssuanceHistory = async () => {
    try {
      const response = await getPlantIssuanceHistory({ start_date: filters.start_date, end_date: filters.end_date });
      setIssuanceHistory(response.data || []);
    } catch (error) {
      console.error('Failed to fetch issuance history:', error);
    }
  };

  // Group issuance history by dealer
  const dealerIssuanceSummary = issuanceHistory.reduce((acc, entry) => {
    const key = entry.dealer_name || entry.dealer_id;
    if (!acc[key]) acc[key] = { dealer_name: key, total_15kg: 0, total_21kg: 0, entries: [] };
    acc[key].total_15kg += entry.qty_15kg || 0;
    acc[key].total_21kg += entry.qty_21kg || 0;
    acc[key].entries.push(entry);
    return acc;
  }, {});

  const grandIssuance15 = issuanceHistory.reduce((s, e) => s + (e.qty_15kg || 0), 0);
  const grandIssuance21 = issuanceHistory.reduce((s, e) => s + (e.qty_21kg || 0), 0);

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
      const response = await getPlantReports(filters);
      setReports(response.data);
      if (response.data.length > 0) {
        setSelectedReport(response.data[0]);
      }
    } catch (error) {
      console.error('Failed to fetch reports:', error);
      toast.error('Failed to load plant reports');
    } finally {
      setLoading(false);
    }
  };

  const getWarehouseName = (warehouseId) => {
    const warehouse = warehouses.find(w => w.id === warehouseId);
    return warehouse?.name || 'Unknown';
  };

  const handleExportPDF = () => {
    exportPDF({
      report_type: 'plant',
      start_date: filters.start_date,
      end_date: filters.end_date
    });
    toast.success('PDF export started');
  };

  const handleExportExcel = () => {
    exportExcel({
      report_type: 'plant',
      start_date: filters.start_date,
      end_date: filters.end_date
    });
    toast.success('Excel export started');
  };

  return (
    <Layout>
      <div className="space-y-6" data-testid="plant-hollongi-page">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-800 flex items-center gap-2">
              <Factory className="w-8 h-8 text-amber-600" />
              Plant Hollongi
            </h1>
            <p className="text-slate-500 mt-1">View and manage plant operations</p>
          </div>
          <div className="flex gap-2">
            <Link to="/plant-entry?tab=issuance">
              <Button className="gap-2 bg-blue-700 hover:bg-blue-800" data-testid="issue-cylinders-link">
                <Send className="w-4 h-4" />
                Issue Cylinders
              </Button>
            </Link>
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
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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
              <div className="flex items-end">
                <Button onClick={fetchReports} className="gap-2 bg-green-700 hover:bg-green-800" data-testid="apply-filters-btn">
                  <RefreshCw className="w-4 h-4" />
                  Apply
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Reports List */}
          <Card className="lg:col-span-1" data-testid="reports-list-card">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Calendar className="w-5 h-5" />
                Reports
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {loading ? (
                <div className="flex items-center justify-center h-48">
                  <Loader2 className="w-8 h-8 animate-spin text-green-700" />
                </div>
              ) : reports.length > 0 ? (
                <div className="max-h-[500px] overflow-y-auto">
                  {reports.map((report) => (
                    <button
                      key={report.id}
                      onClick={() => setSelectedReport(report)}
                      className={`w-full p-4 text-left border-b hover:bg-slate-50 transition-colors ${selectedReport?.id === report.id ? 'bg-green-50 border-l-4 border-l-green-700' : ''}`}
                      data-testid={`report-item-${report.id}`}
                    >
                      <p className="font-medium text-slate-800">{formatDate(report.date)}</p>
                      <p className="text-sm text-slate-500">
                        Tank: {report.closing_bullet_tank_kg} kg
                      </p>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Calendar className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                  <p className="text-slate-500">No reports found</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Report Details */}
          <Card className="lg:col-span-2" data-testid="report-details-card">
            <CardHeader>
              <CardTitle className="text-lg">Report Details</CardTitle>
            </CardHeader>
            <CardContent>
              {selectedReport ? (
                <div className="space-y-6">
                  {/* Opening Stock */}
                  <div>
                    <h4 className="font-medium text-slate-700 mb-3">Opening Stock</h4>
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                      <div className="p-3 bg-amber-50 rounded-lg text-center">
                        <p className="text-xs text-amber-700">Bullet Tank</p>
                        <p className="font-bold text-amber-800">{selectedReport.opening_bullet_tank_kg} kg</p>
                      </div>
                      <div className="p-3 bg-slate-50 rounded-lg text-center">
                        <p className="text-xs text-slate-600">15kg Filled</p>
                        <p className="font-bold text-slate-800">{selectedReport.opening_15kg_filled}</p>
                      </div>
                      <div className="p-3 bg-slate-50 rounded-lg text-center">
                        <p className="text-xs text-slate-600">21kg Filled</p>
                        <p className="font-bold text-slate-800">{selectedReport.opening_21kg_filled}</p>
                      </div>
                      <div className="p-3 bg-slate-50 rounded-lg text-center">
                        <p className="text-xs text-slate-600">15kg Empty</p>
                        <p className="font-bold text-slate-800">{selectedReport.opening_15kg_empty}</p>
                      </div>
                      <div className="p-3 bg-slate-50 rounded-lg text-center">
                        <p className="text-xs text-slate-600">21kg Empty</p>
                        <p className="font-bold text-slate-800">{selectedReport.opening_21kg_empty}</p>
                      </div>
                    </div>
                  </div>

                  {/* Day Activity */}
                  <div>
                    <h4 className="font-medium text-slate-700 mb-3">Day Activity</h4>
                    <div className="grid grid-cols-2 gap-3 mb-4">
                      <div className="p-3 bg-green-50 rounded-lg text-center">
                        <p className="text-xs text-green-700">15kg Refilled</p>
                        <p className="font-bold text-green-800">{selectedReport.day_refilled_15kg}</p>
                      </div>
                      <div className="p-3 bg-green-50 rounded-lg text-center">
                        <p className="text-xs text-green-700">21kg Refilled</p>
                        <p className="font-bold text-green-800">{selectedReport.day_refilled_21kg}</p>
                      </div>
                    </div>

                    {/* Deliveries */}
                    {(selectedReport.delivery_15kg?.length > 0 || selectedReport.delivery_21kg?.length > 0) && (
                      <div className="mb-4">
                        <div className="flex items-center gap-2 mb-2">
                          <Truck className="w-4 h-4 text-blue-600" />
                          <span className="text-sm font-medium text-slate-700">Deliveries</span>
                        </div>
                        <div className="space-y-2">
                          {selectedReport.delivery_15kg?.map((d, i) => (
                            <div key={i} className="flex items-center justify-between p-2 bg-blue-50 rounded text-sm">
                              <span>15kg → {d.warehouse_name || getWarehouseName(d.warehouse_id)}</span>
                              <Badge className="bg-blue-100 text-blue-700">{d.quantity}</Badge>
                            </div>
                          ))}
                          {selectedReport.delivery_21kg?.map((d, i) => (
                            <div key={i} className="flex items-center justify-between p-2 bg-blue-50 rounded text-sm">
                              <span>21kg → {d.warehouse_name || getWarehouseName(d.warehouse_id)}</span>
                              <Badge className="bg-blue-100 text-blue-700">{d.quantity}</Badge>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Received Empties */}
                    {(selectedReport.received_empty_15kg?.length > 0 || selectedReport.received_empty_21kg?.length > 0) && (
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <ArrowDownToLine className="w-4 h-4 text-orange-600" />
                          <span className="text-sm font-medium text-slate-700">Empties Received</span>
                        </div>
                        <div className="space-y-2">
                          {selectedReport.received_empty_15kg?.map((r, i) => (
                            <div key={i} className="flex items-center justify-between p-2 bg-orange-50 rounded text-sm">
                              <span>15kg ← {r.warehouse_name || getWarehouseName(r.warehouse_id)}</span>
                              <Badge className="bg-orange-100 text-orange-700">{r.quantity}</Badge>
                            </div>
                          ))}
                          {selectedReport.received_empty_21kg?.map((r, i) => (
                            <div key={i} className="flex items-center justify-between p-2 bg-orange-50 rounded text-sm">
                              <span>21kg ← {r.warehouse_name || getWarehouseName(r.warehouse_id)}</span>
                              <Badge className="bg-orange-100 text-orange-700">{r.quantity}</Badge>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Closing Stock */}
                  <div>
                    <h4 className="font-medium text-slate-700 mb-3">Closing Stock</h4>
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                      <div className="p-3 bg-amber-100 rounded-lg text-center">
                        <p className="text-xs text-amber-700">Bullet Tank</p>
                        <p className="font-bold text-amber-800">{selectedReport.closing_bullet_tank_kg} kg</p>
                      </div>
                      <div className="p-3 bg-green-100 rounded-lg text-center">
                        <p className="text-xs text-green-700">15kg Filled</p>
                        <p className="font-bold text-green-800">{selectedReport.closing_15kg_filled}</p>
                      </div>
                      <div className="p-3 bg-green-100 rounded-lg text-center">
                        <p className="text-xs text-green-700">21kg Filled</p>
                        <p className="font-bold text-green-800">{selectedReport.closing_21kg_filled}</p>
                      </div>
                      <div className="p-3 bg-slate-100 rounded-lg text-center">
                        <p className="text-xs text-slate-600">15kg Empty</p>
                        <p className="font-bold text-slate-800">{selectedReport.closing_15kg_empty}</p>
                      </div>
                      <div className="p-3 bg-slate-100 rounded-lg text-center">
                        <p className="text-xs text-slate-600">21kg Empty</p>
                        <p className="font-bold text-slate-800">{selectedReport.closing_21kg_empty}</p>
                      </div>
                    </div>
                  </div>

                  {/* Remarks */}
                  {selectedReport.remarks && (
                    <div>
                      <h4 className="font-medium text-slate-700 mb-2">Remarks</h4>
                      <p className="text-sm text-slate-600 p-3 bg-slate-50 rounded-lg">{selectedReport.remarks}</p>
                    </div>
                  )}

                  {/* Meta */}
                  <div className="text-xs text-slate-500 pt-4 border-t">
                    Submitted by {selectedReport.submitted_by} on {formatDate(selectedReport.submitted_at)}
                  </div>
                </div>
              ) : (
                <div className="text-center py-12">
                  <Factory className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                  <p className="text-slate-500">Select a report to view details</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Dealer-wise Issuance Breakdown */}
        <Card data-testid="issuance-breakdown-card">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Send className="w-5 h-5 text-blue-600" />
              Dealer-wise Cylinder Issuance
              {issuanceHistory.length > 0 && (
                <Badge className="ml-2 bg-blue-100 text-blue-700">{issuanceHistory.length} entries</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {issuanceHistory.length > 0 ? (
              <div className="space-y-4">
                {/* Grand Totals */}
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div className="p-3 bg-blue-50 rounded-lg text-center border border-blue-200">
                    <p className="text-xs text-blue-600 font-medium">Total 15kg Issued</p>
                    <p className="text-2xl font-bold text-blue-800">{grandIssuance15}</p>
                  </div>
                  <div className="p-3 bg-blue-50 rounded-lg text-center border border-blue-200">
                    <p className="text-xs text-blue-600 font-medium">Total 21kg Issued</p>
                    <p className="text-2xl font-bold text-blue-800">{grandIssuance21}</p>
                  </div>
                </div>

                {/* Dealer-wise breakdown */}
                {Object.values(dealerIssuanceSummary).map((dealer) => (
                  <div key={dealer.dealer_name} className="border rounded-lg overflow-hidden">
                    <div className="bg-slate-50 p-3 flex items-center justify-between">
                      <span className="font-medium text-slate-800 flex items-center gap-2">
                        <Package className="w-4 h-4 text-slate-500" />
                        {dealer.dealer_name}
                      </span>
                      <div className="flex gap-3 text-sm">
                        <span className="text-blue-700">15kg: <strong>{dealer.total_15kg}</strong></span>
                        <span className="text-blue-700">21kg: <strong>{dealer.total_21kg}</strong></span>
                      </div>
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-white">
                          <th className="text-left p-2 font-medium text-slate-500">Date</th>
                          <th className="text-center p-2 font-medium text-slate-500">15 Kg</th>
                          <th className="text-center p-2 font-medium text-slate-500">21 Kg</th>
                          <th className="text-left p-2 font-medium text-slate-500">Remarks</th>
                          <th className="text-left p-2 font-medium text-slate-500">By</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dealer.entries.sort((a, b) => a.date.localeCompare(b.date)).map((e) => (
                          <tr key={e.id} className="border-b hover:bg-slate-50">
                            <td className="p-2">{formatDate(e.date)}</td>
                            <td className="p-2 text-center">{e.qty_15kg}</td>
                            <td className="p-2 text-center">{e.qty_21kg}</td>
                            <td className="p-2 text-slate-500">{e.remarks || '-'}</td>
                            <td className="p-2 text-slate-500">{e.submitted_by}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Send className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                <p className="text-slate-400 text-sm">No cylinder issuances recorded for this period</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default PlantHollongi;
