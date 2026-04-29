import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Layout from '../components/Layout';
import { getAuditLogs } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import {
  ScrollText, RefreshCw, Search, Filter, ChevronLeft, ChevronRight,
  Loader2, User, Clock, Eye, X
} from 'lucide-react';
import { toast } from 'sonner';

const ACTION_COLORS = {
  create: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  update: 'bg-blue-100 text-blue-700 border-blue-200',
  delete: 'bg-rose-100 text-rose-700 border-rose-200',
  finalize: 'bg-violet-100 text-violet-700 border-violet-200',
  bulk_update: 'bg-amber-100 text-amber-700 border-amber-200',
  bulk_upload: 'bg-amber-100 text-amber-700 border-amber-200',
  undo: 'bg-orange-100 text-orange-700 border-orange-200',
  reset: 'bg-fuchsia-100 text-fuchsia-700 border-fuchsia-200',
  login: 'bg-slate-100 text-slate-700 border-slate-200',
};

const RESOURCE_TYPES = [
  { value: 'all', label: 'All Resources' },
  { value: 'employee', label: 'Employee' },
  { value: 'attendance', label: 'Attendance' },
  { value: 'payroll', label: 'Payroll' },
  { value: 'payroll_adjustment', label: 'Payroll Adjustment' },
  { value: 'performance_review', label: 'Performance Review' },
  { value: 'customer', label: 'Customer' },
  { value: 'order', label: 'Order' },
  { value: 'user', label: 'User' },
  { value: 'hrms_user', label: 'HRMS User' },
];

const PAGE_SIZE = 50;

const formatTimestamp = (iso) => {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: true,
    });
  } catch { return iso; }
};

const AuditLogs = () => {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [resourceType, setResourceType] = useState('all');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedLog, setSelectedLog] = useState(null);

  const fetchLogs = useCallback(async (showSpinner = true) => {
    if (showSpinner) setLoading(true); else setRefreshing(true);
    try {
      const params = { page, limit: PAGE_SIZE };
      if (resourceType !== 'all') params.resource_type = resourceType;
      const res = await getAuditLogs(params);
      setLogs(res.data.logs || []);
      setTotal(res.data.total || 0);
      setPages(res.data.pages || 1);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load audit logs');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, resourceType]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  // Reset to page 1 when filter changes
  useEffect(() => { setPage(1); }, [resourceType]);

  const filteredLogs = useMemo(() => {
    if (!search.trim()) return logs;
    const q = search.toLowerCase();
    return logs.filter(l =>
      (l.user_name || '').toLowerCase().includes(q) ||
      (l.action || '').toLowerCase().includes(q) ||
      (l.resource_type || '').toLowerCase().includes(q) ||
      (l.details || '').toLowerCase().includes(q) ||
      (l.resource_id || '').toLowerCase().includes(q)
    );
  }, [logs, search]);

  const actionClass = (action) => ACTION_COLORS[action] || 'bg-slate-100 text-slate-700 border-slate-200';

  return (
    <Layout>
      <div className="space-y-4 max-w-7xl mx-auto" data-testid="audit-logs-page">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-slate-900 text-white flex items-center justify-center">
              <ScrollText className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-800">Audit Logs</h1>
              <p className="text-xs text-slate-500">Track every change across the system</p>
            </div>
          </div>
          <Button
            variant="outline"
            onClick={() => fetchLogs(false)}
            disabled={refreshing}
            data-testid="audit-refresh-btn"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col md:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
                <Input
                  placeholder="Search by user, action, details, resource ID..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="pl-9"
                  data-testid="audit-search"
                />
              </div>
              <Select value={resourceType} onValueChange={setResourceType}>
                <SelectTrigger className="w-full md:w-56" data-testid="audit-resource-filter">
                  <Filter className="w-3.5 h-3.5 mr-2 text-slate-400" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RESOURCE_TYPES.map(r => (
                    <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between mt-3 text-xs text-slate-500">
              <span>
                Showing <span className="font-semibold text-slate-700">{filteredLogs.length}</span> of <span className="font-semibold text-slate-700">{total}</span> entries
              </span>
              <span>Page {page} of {pages}</span>
            </div>
          </CardContent>
        </Card>

        {/* Logs Table */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-500" /> Recent Activity
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="flex justify-center items-center py-16">
                <Loader2 className="w-6 h-6 text-slate-400 animate-spin" />
              </div>
            ) : filteredLogs.length === 0 ? (
              <div className="text-center py-16 text-slate-400 text-sm">
                No audit logs found{search ? ` for "${search}"` : ''}.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="audit-logs-table">
                  <thead className="bg-slate-50 border-y border-slate-200">
                    <tr className="text-left text-xs uppercase text-slate-500">
                      <th className="px-4 py-2.5 font-semibold">When</th>
                      <th className="px-4 py-2.5 font-semibold">User</th>
                      <th className="px-4 py-2.5 font-semibold">Action</th>
                      <th className="px-4 py-2.5 font-semibold">Resource</th>
                      <th className="px-4 py-2.5 font-semibold">Details</th>
                      <th className="px-4 py-2.5 font-semibold w-12"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredLogs.map((log, idx) => (
                      <tr key={`${log.timestamp}-${idx}`} className="hover:bg-slate-50/60 transition-colors" data-testid={`audit-row-${idx}`}>
                        <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">
                          {formatTimestamp(log.timestamp)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <div className="w-6 h-6 rounded-full bg-slate-200 flex items-center justify-center">
                              <User className="w-3 h-3 text-slate-500" />
                            </div>
                            <span className="text-slate-700 text-xs font-medium">{log.user_name || 'System'}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <Badge variant="outline" className={`${actionClass(log.action)} text-[10px] uppercase font-semibold`}>
                            {log.action || '-'}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-xs text-slate-600">
                          <span className="font-medium text-slate-700">{log.resource_type || '-'}</span>
                          {log.resource_id && (
                            <div className="text-[10px] text-slate-400 font-mono mt-0.5 truncate max-w-[180px]" title={log.resource_id}>
                              {log.resource_id.slice(0, 12)}{log.resource_id.length > 12 ? '...' : ''}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-600 max-w-md">
                          <div className="line-clamp-2">{log.details || '-'}</div>
                        </td>
                        <td className="px-4 py-3">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setSelectedLog(log)}
                            className="h-7 w-7 p-0"
                            data-testid={`audit-view-${idx}`}
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-between">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1 || loading}
              data-testid="audit-prev-btn"
            >
              <ChevronLeft className="w-4 h-4 mr-1" /> Previous
            </Button>
            <span className="text-sm text-slate-600">
              Page {page} of {pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.min(pages, p + 1))}
              disabled={page >= pages || loading}
              data-testid="audit-next-btn"
            >
              Next <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        )}
      </div>

      {/* Detail Dialog */}
      <Dialog open={!!selectedLog} onOpenChange={(o) => !o && setSelectedLog(null)}>
        <DialogContent className="sm:max-w-lg" data-testid="audit-detail-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ScrollText className="w-4 h-4" /> Audit Entry Details
            </DialogTitle>
          </DialogHeader>
          {selectedLog && (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-3 gap-2 py-2 border-b">
                <span className="text-slate-500 text-xs">Timestamp</span>
                <span className="col-span-2 font-mono text-xs">{formatTimestamp(selectedLog.timestamp)}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 py-2 border-b">
                <span className="text-slate-500 text-xs">User</span>
                <span className="col-span-2 font-medium">{selectedLog.user_name || '-'}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 py-2 border-b">
                <span className="text-slate-500 text-xs">User ID</span>
                <span className="col-span-2 font-mono text-[10px] text-slate-600 break-all">{selectedLog.user_id || '-'}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 py-2 border-b">
                <span className="text-slate-500 text-xs">Action</span>
                <span className="col-span-2">
                  <Badge variant="outline" className={`${actionClass(selectedLog.action)} uppercase text-[10px] font-semibold`}>
                    {selectedLog.action || '-'}
                  </Badge>
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 py-2 border-b">
                <span className="text-slate-500 text-xs">Resource Type</span>
                <span className="col-span-2 font-medium">{selectedLog.resource_type || '-'}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 py-2 border-b">
                <span className="text-slate-500 text-xs">Resource ID</span>
                <span className="col-span-2 font-mono text-[10px] text-slate-600 break-all">{selectedLog.resource_id || '-'}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 py-2">
                <span className="text-slate-500 text-xs">Details</span>
                <span className="col-span-2 text-slate-700 whitespace-pre-wrap break-words">{selectedLog.details || '-'}</span>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Layout>
  );
};

export default AuditLogs;
