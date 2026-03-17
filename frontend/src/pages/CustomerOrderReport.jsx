import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { getCustomerOrderReport, getWarehouses, exportCustomerOrderReportPDF, exportCustomerOrderReportExcel } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  Users, ShoppingCart, RefreshCw, Loader2, Download, FileSpreadsheet, Search, Calendar, ChevronDown, Package, Phone, MapPin, Hash, Home, Building2
} from 'lucide-react';
import { toast } from 'sonner';

const CustomerOrderReport = () => {
  const { user, isAdmin } = useAuth();
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [report, setReport] = useState(null);
  const [warehouses, setWarehouses] = useState([]);
  const [filterWarehouse, setFilterWarehouse] = useState('all');
  const [filterStartDate, setFilterStartDate] = useState('');
  const [filterEndDate, setFilterEndDate] = useState('');
  const [search, setSearch] = useState('');
  const [expandedCustomers, setExpandedCustomers] = useState({});

  useEffect(() => {
    if (isAdmin) {
      getWarehouses().then(r => setWarehouses(r.data || [])).catch(() => {});
    }
  }, [isAdmin]);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filterWarehouse !== 'all') params.warehouse_id = filterWarehouse;
      if (filterStartDate) params.start_date = filterStartDate;
      if (filterEndDate) params.end_date = filterEndDate;
      if (search) params.search = search;
      const res = await getCustomerOrderReport(params);
      setReport(res.data);
      // Auto-expand all
      const exp = {};
      (res.data.customers || []).forEach(c => { exp[c.customer_id] = true; });
      setExpandedCustomers(exp);
    } catch (error) {
      toast.error('Failed to load report');
    } finally {
      setLoading(false);
    }
  }, [filterWarehouse, filterStartDate, filterEndDate, search]);

  useEffect(() => { fetchReport(); }, [fetchReport]);

  const toggleCustomer = (id) => {
    setExpandedCustomers(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleExportPDF = async () => {
    setExporting(true);
    try {
      const params = {};
      if (filterWarehouse !== 'all') params.warehouse_id = filterWarehouse;
      if (filterStartDate) params.start_date = filterStartDate;
      if (filterEndDate) params.end_date = filterEndDate;
      await exportCustomerOrderReportPDF(params);
      toast.success('PDF exported');
    } catch { toast.error('Export failed'); }
    finally { setExporting(false); }
  };

  const handleExportExcel = async () => {
    setExporting(true);
    try {
      const params = {};
      if (filterWarehouse !== 'all') params.warehouse_id = filterWarehouse;
      if (filterStartDate) params.start_date = filterStartDate;
      if (filterEndDate) params.end_date = filterEndDate;
      await exportCustomerOrderReportExcel(params);
      toast.success('Excel exported');
    } catch { toast.error('Export failed'); }
    finally { setExporting(false); }
  };

  const formatDate = (d) => {
    if (!d) return '-';
    try { return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: '2-digit', year: 'numeric' }); }
    catch { return d; }
  };

  if (!isAdmin) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <Users className="w-16 h-16 text-slate-300 mb-4" />
          <h2 className="text-2xl font-bold text-slate-700 mb-2">Access Restricted</h2>
          <p className="text-slate-500">Customer Order Reports are available for admins only.</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-5" data-testid="customer-order-report-page">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Customer Order Report</h1>
            <p className="text-sm text-slate-500">Warehouse-wise customer order history</p>
          </div>
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-wrap items-center gap-3">
              <Select value={filterWarehouse} onValueChange={setFilterWarehouse}>
                <SelectTrigger className="w-44 h-9 text-sm" data-testid="report-warehouse-filter">
                  <SelectValue placeholder="Warehouse" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Warehouses</SelectItem>
                  {warehouses.map(w => (
                    <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="flex items-center gap-1">
                <Calendar className="w-4 h-4 text-slate-400" />
                <Input type="date" value={filterStartDate} onChange={e => setFilterStartDate(e.target.value)} className="w-36 h-9 text-sm" placeholder="From" data-testid="report-start-date" />
                <span className="text-slate-400 text-sm">to</span>
                <Input type="date" value={filterEndDate} onChange={e => setFilterEndDate(e.target.value)} className="w-36 h-9 text-sm" placeholder="To" data-testid="report-end-date" />
              </div>
              <div className="relative flex-1 min-w-[180px]">
                <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-slate-400" />
                <Input
                  placeholder="Search customers..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="pl-9 h-9 text-sm"
                  data-testid="report-search"
                />
              </div>
              <Button variant="outline" size="sm" onClick={fetchReport} className="h-9 gap-1" data-testid="report-refresh-btn">
                <RefreshCw className="w-3.5 h-3.5" /> View Report
              </Button>
              <Button variant="outline" size="sm" onClick={handleExportPDF} disabled={exporting} className="h-9 gap-1 border-red-300 text-red-700 hover:bg-red-50" data-testid="report-export-pdf">
                {exporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} PDF
              </Button>
              <Button variant="outline" size="sm" onClick={handleExportExcel} disabled={exporting} className="h-9 gap-1 border-green-300 text-green-700 hover:bg-green-50" data-testid="report-export-excel">
                {exporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileSpreadsheet className="w-3.5 h-3.5" />} Excel
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Summary Cards */}
        {report && (
          <div className="grid grid-cols-3 gap-4">
            <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200" data-testid="report-total-customers">
              <CardContent className="p-4">
                <p className="text-sm text-blue-600 font-medium flex items-center gap-1"><Users className="w-4 h-4" /> Total Customers</p>
                <p className="text-3xl font-bold text-blue-800 mt-1">{report.summary.total_customers}</p>
              </CardContent>
            </Card>
            <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200" data-testid="report-total-orders">
              <CardContent className="p-4">
                <p className="text-sm text-green-600 font-medium flex items-center gap-1"><ShoppingCart className="w-4 h-4" /> Total Orders</p>
                <p className="text-3xl font-bold text-green-800 mt-1">{report.summary.total_orders}</p>
              </CardContent>
            </Card>
            <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200" data-testid="report-total-refills">
              <CardContent className="p-4">
                <p className="text-sm text-purple-600 font-medium flex items-center gap-1"><Package className="w-4 h-4" /> Total Refills</p>
                <p className="text-3xl font-bold text-purple-800 mt-1">{report.summary.total_refills}</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Customer Groups */}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        ) : report && report.customers.length > 0 ? (
          <div className="space-y-3">
            {report.customers.map(c => (
              <Card key={c.customer_id} data-testid={`customer-group-${c.customer_id}`}>
                <button
                  className="w-full text-left p-4 hover:bg-slate-50 transition-colors"
                  onClick={() => toggleCustomer(c.customer_id)}
                  data-testid={`customer-toggle-${c.customer_id}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                        <Users className="w-5 h-5 text-blue-700" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-slate-800">{c.customer_name}</h3>
                        <div className="flex items-center gap-3 text-xs text-slate-500 mt-0.5">
                          {c.phone && <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{c.phone}</span>}
                          {c.consumer_no && <span className="flex items-center gap-1"><Hash className="w-3 h-3" />{c.consumer_no}</span>}
                          {c.address && <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{c.address.slice(0, 30)}</span>}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge variant="outline" className="text-xs">{c.warehouse_name}</Badge>
                      {c.connection_date && (
                        <Badge className="bg-emerald-100 text-emerald-800 text-xs">Connected: {formatDate(c.connection_date)}</Badge>
                      )}
                      <Badge className="bg-blue-100 text-blue-800 text-xs">{c.total_entries} entries</Badge>
                      <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${expandedCustomers[c.customer_id] ? 'rotate-180' : ''}`} />
                    </div>
                  </div>
                </button>

                {expandedCustomers[c.customer_id] && c.entries.length > 0 && (
                  <div className="px-4 pb-4">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-slate-200 bg-slate-50">
                            <th className="text-left py-2 px-3 text-xs font-medium text-slate-600">SL</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-slate-600">Date</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-slate-600">Order ID</th>
                            <th className="text-center py-2 px-3 text-xs font-medium text-slate-600">Type</th>
                            <th className="text-center py-2 px-3 text-xs font-medium text-slate-600">Cylinder</th>
                            <th className="text-left py-2 px-3 text-xs font-medium text-slate-600">Cyl Nos</th>
                            <th className="text-center py-2 px-3 text-xs font-medium text-slate-600">Qty</th>
                            <th className="text-center py-2 px-3 text-xs font-medium text-slate-600">Status</th>
                            <th className="text-center py-2 px-3 text-xs font-medium text-slate-600">Payment</th>
                          </tr>
                        </thead>
                        <tbody>
                          {c.entries.map((e, idx) => (
                            <tr key={`${e.id}-${idx}`} className={`border-b border-slate-100 hover:bg-slate-50 ${e.type === 'New Connection' ? 'bg-emerald-50/40' : ''}`}>
                              <td className="py-2 px-3 text-xs text-slate-500">{idx + 1}</td>
                              <td className="py-2 px-3 text-sm font-medium">{formatDate(e.date)}</td>
                              <td className="py-2 px-3 text-sm text-blue-700 font-medium">{e.id || '-'}</td>
                              <td className="text-center py-2 px-3">
                                {e.type === 'New Connection' ? (
                                  <Badge className="bg-emerald-100 text-emerald-800 text-xs"><Home className="w-3 h-3 mr-0.5" />Connection</Badge>
                                ) : (
                                  <Badge className="bg-blue-100 text-blue-800 text-xs"><Package className="w-3 h-3 mr-0.5" />Refill</Badge>
                                )}
                              </td>
                              <td className="text-center py-2 px-3">
                                <Badge variant="outline" className="text-xs">
                                  {e.cylinder_type === 'Commercial' ? <Building2 className="w-3 h-3 mr-0.5" /> : <Home className="w-3 h-3 mr-0.5" />}
                                  {e.cylinder_type}
                                </Badge>
                              </td>
                              <td className="py-2 px-3 text-xs text-slate-600">{e.cylinder_nos || '-'}</td>
                              <td className="text-center py-2 px-3 font-semibold">{e.quantity}</td>
                              <td className="text-center py-2 px-3">
                                {e.status === 'Completed' || e.status === 'Delivered' ? (
                                  <Badge className="bg-green-100 text-green-800 text-xs">{e.status}</Badge>
                                ) : (
                                  <Badge className="bg-amber-100 text-amber-800 text-xs">{e.status}</Badge>
                                )}
                              </td>
                              <td className="text-center py-2 px-3">
                                <Badge variant="outline" className="text-xs">{e.payment || '-'}</Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </Card>
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="py-16 text-center">
              <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500 font-medium">No customers with orders found</p>
            </CardContent>
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default CustomerOrderReport;
