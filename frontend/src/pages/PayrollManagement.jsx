import React, { useState, useEffect, useCallback } from 'react';
import HRMSLayout from '../components/HRMSLayout';
import api from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { formatINR } from '../lib/utils';
import { toast } from 'sonner';
import {
  DollarSign, Play, CheckCircle, FileText, Trash2, Eye,
  Download, Loader2, Calculator, ChevronDown, ChevronUp,
  Edit3, PlusCircle, ArrowLeft, AlertTriangle, X
} from 'lucide-react';

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const ITEMS_PER_PAGE = 10;

const PayrollManagement = () => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runDialogOpen, setRunDialogOpen] = useState(false);
  const [configDialog, setConfigDialog] = useState(false);
  const [config, setConfig] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [runMonth, setRunMonth] = useState(new Date().getMonth() + 1);
  const [runYear, setRunYear] = useState(new Date().getFullYear());
  const [workingDays, setWorkingDays] = useState(26);
  const [expandedPayroll, setExpandedPayroll] = useState(null);
  const [payrollDetail, setPayrollDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

  // Review & Adjust state
  const [reviewMode, setReviewMode] = useState(null); // payroll_id when in review
  const [reviewData, setReviewData] = useState(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [adjDialog, setAdjDialog] = useState(null); // { employee_id, employee_name }
  const [adjForm, setAdjForm] = useState({ name: '', type: 'deduction', amount: '', reason: '' });
  const [adjSaving, setAdjSaving] = useState(false);
  const [editAdj, setEditAdj] = useState(null); // adjustment object being edited

  const fetchHistory = useCallback(async () => {
    try {
      const res = await api.get('/hrms/payroll/history');
      setHistory(res.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  const fetchConfig = async () => {
    try {
      const res = await api.get('/hrms/payroll/config');
      setConfig(res.data);
    } catch (e) { console.error(e); }
  };

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  const handleRunPayroll = async () => {
    setProcessing(true);
    try {
      const res = await api.post('/hrms/payroll/run', { month: runMonth, year: runYear, working_days: workingDays });
      toast.success(`Payroll processed for ${MONTHS[runMonth - 1]} ${runYear}`);
      setRunDialogOpen(false);
      fetchHistory();
      // Auto-open review mode
      if (res.data?.id) {
        openReview(res.data.id);
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to run payroll');
    } finally { setProcessing(false); }
  };

  const openReview = async (payrollId) => {
    setReviewMode(payrollId);
    setReviewLoading(true);
    try {
      const res = await api.get(`/hrms/payroll/${payrollId}/review`);
      setReviewData(res.data);
    } catch (e) {
      toast.error('Failed to load payroll review');
      setReviewMode(null);
    } finally { setReviewLoading(false); }
  };

  const refreshReview = async () => {
    if (!reviewMode) return;
    try {
      const res = await api.get(`/hrms/payroll/${reviewMode}/review`);
      setReviewData(res.data);
    } catch (e) { console.error(e); }
  };

  const handleFinalize = async (id) => {
    if (!window.confirm('Finalize this payroll? This will lock all data and adjustments. This cannot be undone.')) return;
    try {
      await api.post(`/hrms/payroll/${id}/finalize`);
      toast.success('Payroll finalized and locked');
      fetchHistory();
      if (reviewMode === id) {
        setReviewMode(null);
        setReviewData(null);
      }
      if (payrollDetail?.id === id) {
        setPayrollDetail({ ...payrollDetail, status: 'finalized' });
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to finalize');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this payroll draft?')) return;
    try {
      await api.delete(`/hrms/payroll/${id}`);
      toast.success('Payroll draft deleted');
      fetchHistory();
      if (expandedPayroll === id) { setExpandedPayroll(null); setPayrollDetail(null); }
      if (reviewMode === id) { setReviewMode(null); setReviewData(null); }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to delete');
    }
  };

  const toggleExpand = async (id) => {
    if (expandedPayroll === id) {
      setExpandedPayroll(null); setPayrollDetail(null); return;
    }
    setExpandedPayroll(id);
    setDetailLoading(true);
    try {
      const res = await api.get(`/hrms/payroll/${id}`);
      setPayrollDetail(res.data);
    } catch (e) { toast.error('Failed to load payroll details'); }
    finally { setDetailLoading(false); }
  };

  const downloadPayslip = async (payrollId, empId, empName) => {
    try {
      const res = await api.get(`/hrms/payroll/${payrollId}/payslip/${empId}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `Payslip_${empName.replace(/\s/g, '_')}.pdf`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (e) { toast.error('Failed to download payslip'); }
  };

  const handleSaveConfig = async () => {
    try {
      await api.put('/hrms/payroll/config', config);
      toast.success('Payroll configuration saved');
      setConfigDialog(false);
    } catch (e) { toast.error('Failed to save configuration'); }
  };

  // Adjustment CRUD
  const handleAddAdjustment = async () => {
    if (!adjForm.name.trim() || !adjForm.reason.trim()) {
      toast.error('Name and reason are required'); return;
    }
    if (!adjForm.amount || parseFloat(adjForm.amount) <= 0) {
      toast.error('Amount must be greater than 0'); return;
    }
    setAdjSaving(true);
    try {
      if (editAdj) {
        await api.put(`/hrms/payroll/${reviewMode}/adjustments/${editAdj.id}`, {
          name: adjForm.name, type: adjForm.type, amount: parseFloat(adjForm.amount), reason: adjForm.reason,
        });
        toast.success('Adjustment updated');
      } else {
        await api.post(`/hrms/payroll/${reviewMode}/adjustments`, {
          employee_id: adjDialog.employee_id,
          name: adjForm.name, type: adjForm.type, amount: parseFloat(adjForm.amount), reason: adjForm.reason,
        });
        toast.success('Adjustment added');
      }
      setAdjDialog(null);
      setEditAdj(null);
      setAdjForm({ name: '', type: 'deduction', amount: '', reason: '' });
      refreshReview();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save adjustment');
    } finally { setAdjSaving(false); }
  };

  const handleDeleteAdjustment = async (adjId) => {
    if (!window.confirm('Remove this adjustment?')) return;
    try {
      await api.delete(`/hrms/payroll/${reviewMode}/adjustments/${adjId}`);
      toast.success('Adjustment removed');
      refreshReview();
    } catch (e) { toast.error('Failed to remove adjustment'); }
  };

  const openEditAdj = (emp, adj) => {
    setAdjDialog({ employee_id: emp.employee_id, employee_name: emp.name });
    setEditAdj(adj);
    setAdjForm({ name: adj.name, type: adj.type, amount: String(adj.amount), reason: adj.reason });
  };

  // Computed
  const totalPages = Math.max(1, Math.ceil(history.length / ITEMS_PER_PAGE));
  const paginatedHistory = history.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'ArrowLeft' && currentPage > 1) { e.preventDefault(); setCurrentPage(p => p - 1); }
      if (e.key === 'ArrowRight' && currentPage < totalPages) { e.preventDefault(); setCurrentPage(p => p + 1); }
      if (e.key === 'Escape' && reviewMode) { setReviewMode(null); setReviewData(null); }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentPage, totalPages, reviewMode]);

  // ========== REVIEW & ADJUST VIEW ==========
  if (reviewMode && reviewData) {
    const isDraft = reviewData.status === 'draft';
    return (
      <HRMSLayout>
        <div className="space-y-5" data-testid="payroll-review">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" onClick={() => { setReviewMode(null); setReviewData(null); fetchHistory(); }} data-testid="back-to-payroll">
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
              </Button>
              <div>
                <h1 className="text-xl font-bold text-slate-800">Review & Adjust Payroll</h1>
                <p className="text-slate-500 text-xs">{MONTHS[(reviewData.month || 1) - 1]} {reviewData.year} &middot; {reviewData.total_employees} employees</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`px-2 py-1 rounded text-xs font-medium ${isDraft ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'}`}>
                {isDraft ? 'Draft — Review in progress' : 'Finalized'}
              </span>
              {isDraft && (
                <Button size="sm" className="bg-green-700 hover:bg-green-800" onClick={() => handleFinalize(reviewMode)} data-testid="finalize-from-review">
                  <CheckCircle className="w-4 h-4 mr-1" /> Finalize Payroll
                </Button>
              )}
            </div>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Card>
              <CardContent className="p-4">
                <p className="text-[10px] text-slate-500 uppercase font-medium">Original Net Pay</p>
                <p className="text-lg font-bold text-slate-700">{formatINR(reviewData.total_net_pay)}</p>
              </CardContent>
            </Card>
            <Card className={reviewData.total_adjustments !== 0 ? 'border-amber-200 bg-amber-50/50' : ''}>
              <CardContent className="p-4">
                <p className="text-[10px] text-slate-500 uppercase font-medium">Total Adjustments</p>
                <p className={`text-lg font-bold ${reviewData.total_adjustments >= 0 ? 'text-green-700' : 'text-red-600'}`}>
                  {reviewData.total_adjustments >= 0 ? '+' : ''}{formatINR(reviewData.total_adjustments)}
                </p>
              </CardContent>
            </Card>
            <Card className="border-green-200">
              <CardContent className="p-4">
                <p className="text-[10px] text-slate-500 uppercase font-medium">Final Net Payout</p>
                <p className="text-lg font-bold text-green-700">{formatINR(reviewData.total_final_net_pay)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="text-[10px] text-slate-500 uppercase font-medium">Modified Employees</p>
                <p className="text-lg font-bold text-amber-600">
                  {reviewData.employees?.filter(e => e.is_modified).length || 0}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Employee Review Table */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold">Employee Payroll Review</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="review-table">
                  <thead>
                    <tr className="border-b text-slate-500 text-xs">
                      <th className="pb-2 text-left font-medium">Employee</th>
                      <th className="pb-2 text-left font-medium">Dept</th>
                      <th className="pb-2 text-right font-medium">Gross</th>
                      <th className="pb-2 text-right font-medium">Deductions</th>
                      <th className="pb-2 text-right font-medium">Original Net</th>
                      <th className="pb-2 text-right font-medium">Adjustments</th>
                      <th className="pb-2 text-right font-medium">Final Net</th>
                      {isDraft && <th className="pb-2 text-center font-medium">Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {reviewData.employees?.map(emp => (
                      <React.Fragment key={emp.employee_id}>
                        <tr
                          className={`border-b text-xs ${emp.is_modified ? 'bg-amber-50/70' : 'hover:bg-slate-50'}`}
                          data-testid={`review-emp-${emp.employee_code}`}
                        >
                          <td className="py-2.5 font-medium">
                            <span className="text-slate-400 text-[10px] mr-1">{emp.employee_code}</span>
                            {emp.name}
                            {emp.is_modified && <span className="ml-1 w-1.5 h-1.5 rounded-full bg-amber-500 inline-block" title="Modified" />}
                          </td>
                          <td className="py-2.5 text-slate-500">{emp.department}</td>
                          <td className="py-2.5 text-right">{formatINR(emp.gross_salary)}</td>
                          <td className="py-2.5 text-right text-red-500">{formatINR(emp.total_deductions)}</td>
                          <td className="py-2.5 text-right">{formatINR(emp.net_pay)}</td>
                          <td className="py-2.5 text-right">
                            {emp.adjustment_net !== 0 ? (
                              <span className={emp.adjustment_net >= 0 ? 'text-green-700 font-medium' : 'text-red-600 font-medium'}>
                                {emp.adjustment_net >= 0 ? '+' : ''}{formatINR(emp.adjustment_net)}
                              </span>
                            ) : <span className="text-slate-300">-</span>}
                          </td>
                          <td className="py-2.5 text-right font-semibold text-green-700">{formatINR(emp.final_net_pay)}</td>
                          {isDraft && (
                            <td className="py-2.5 text-center">
                              <Button
                                size="sm" variant="outline" className="h-7 text-xs"
                                onClick={() => {
                                  setAdjDialog({ employee_id: emp.employee_id, employee_name: emp.name });
                                  setEditAdj(null);
                                  setAdjForm({ name: '', type: 'deduction', amount: '', reason: '' });
                                }}
                                data-testid={`adjust-btn-${emp.employee_code}`}
                              >
                                <Edit3 className="w-3 h-3 mr-1" /> Adjust
                              </Button>
                            </td>
                          )}
                        </tr>
                        {/* Inline adjustment details */}
                        {emp.adjustments?.length > 0 && (
                          <tr>
                            <td colSpan={isDraft ? 8 : 7} className="p-0">
                              <div className="bg-slate-50 px-4 py-2 border-b">
                                <div className="flex flex-wrap gap-2">
                                  {emp.adjustments.map(adj => (
                                    <div
                                      key={adj.id}
                                      className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs border ${
                                        adj.type === 'earning' ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-800'
                                      }`}
                                      data-testid={`adj-chip-${adj.id}`}
                                    >
                                      <span className="font-medium">{adj.name}</span>
                                      <span>{adj.type === 'earning' ? '+' : '-'}{formatINR(adj.amount)}</span>
                                      <span className="text-[10px] opacity-60" title={adj.reason}>{adj.reason.length > 20 ? adj.reason.slice(0, 20) + '...' : adj.reason}</span>
                                      {isDraft && (
                                        <div className="flex items-center gap-0.5 ml-1 border-l pl-1">
                                          <button className="hover:text-blue-600" onClick={() => openEditAdj(emp, adj)} title="Edit"><Edit3 className="w-3 h-3" /></button>
                                          <button className="hover:text-red-600" onClick={() => handleDeleteAdjustment(adj.id)} title="Remove"><X className="w-3 h-3" /></button>
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Add/Edit Adjustment Dialog */}
        <Dialog open={!!adjDialog} onOpenChange={() => { setAdjDialog(null); setEditAdj(null); }}>
          <DialogContent className="sm:max-w-md" data-testid="adjustment-dialog">
            <DialogHeader>
              <DialogTitle>{editAdj ? 'Edit Adjustment' : 'Add Adjustment'}</DialogTitle>
            </DialogHeader>
            {adjDialog && (
              <div className="space-y-4 pt-2">
                <div className="text-sm text-slate-600 bg-slate-50 p-2 rounded">
                  Employee: <strong>{adjDialog.employee_name}</strong>
                </div>
                <div>
                  <Label>Type</Label>
                  <Select value={adjForm.type} onValueChange={v => setAdjForm({ ...adjForm, type: v })}>
                    <SelectTrigger data-testid="adj-type-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="deduction">Deduction (Penalty, Recovery, Advance, etc.)</SelectItem>
                      <SelectItem value="earning">Earning (Bonus, Incentive, Reimbursement, etc.)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Description / Name</Label>
                  <Input
                    placeholder="e.g., Late penalty, Performance bonus, Travel reimbursement"
                    value={adjForm.name}
                    onChange={e => setAdjForm({ ...adjForm, name: e.target.value })}
                    data-testid="adj-name-input"
                  />
                </div>
                <div>
                  <Label>Amount (Rs)</Label>
                  <Input
                    type="number"
                    placeholder="Enter amount"
                    value={adjForm.amount}
                    onChange={e => setAdjForm({ ...adjForm, amount: e.target.value })}
                    min="0"
                    data-testid="adj-amount-input"
                  />
                </div>
                <div>
                  <Label>Reason / Remarks <span className="text-red-500">*</span></Label>
                  <Textarea
                    placeholder="Mandatory: Provide reason for this adjustment (for audit trail)"
                    value={adjForm.reason}
                    onChange={e => setAdjForm({ ...adjForm, reason: e.target.value })}
                    rows={3}
                    data-testid="adj-reason-input"
                  />
                </div>
                {adjForm.type === 'deduction' && adjForm.amount && (
                  <div className="flex items-center gap-2 text-xs text-amber-600 bg-amber-50 p-2 rounded">
                    <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                    <span>Deduction of Rs.{parseFloat(adjForm.amount || 0).toLocaleString()} will be subtracted from net pay</span>
                  </div>
                )}
                <Button
                  className="w-full"
                  onClick={handleAddAdjustment}
                  disabled={adjSaving}
                  data-testid="save-adjustment-btn"
                >
                  {adjSaving ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...</> : editAdj ? 'Update Adjustment' : 'Add Adjustment'}
                </Button>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </HRMSLayout>
    );
  }

  // ========== MAIN PAYROLL VIEW ==========
  return (
    <HRMSLayout>
      <div className="space-y-6" data-testid="payroll-management">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Payroll Management</h1>
            <p className="text-slate-500 text-sm mt-1">Process salaries and manage payroll runs</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => { fetchConfig(); setConfigDialog(true); }} data-testid="payroll-config-btn">
              <Calculator className="w-4 h-4 mr-1" /> Statutory Config
            </Button>
            <Button size="sm" className="bg-blue-700 hover:bg-blue-800" onClick={() => setRunDialogOpen(true)} data-testid="run-payroll-btn">
              <Play className="w-4 h-4 mr-1" /> Run Payroll
            </Button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card>
            <CardContent className="p-5">
              <p className="text-xs text-slate-500 font-medium uppercase">Total Payroll Runs</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{history.length}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5">
              <p className="text-xs text-slate-500 font-medium uppercase">Latest Net Payout</p>
              <p className="text-2xl font-bold text-green-700 mt-1">{formatINR(history[0]?.total_net_pay || 0)}</p>
              <p className="text-xs text-slate-400">{history[0] ? `${MONTHS[(history[0].month || 1) - 1]} ${history[0].year}` : '-'}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5">
              <p className="text-xs text-slate-500 font-medium uppercase">Latest Employees</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{history[0]?.total_employees || 0}</p>
            </CardContent>
          </Card>
        </div>

        {/* History Table */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Payroll History</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
            ) : history.length === 0 ? (
              <p className="text-slate-400 text-sm text-center py-8">No payroll runs yet. Click "Run Payroll" to process your first payroll.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-slate-500">
                      <th className="pb-2 pr-4 font-medium">Period</th>
                      <th className="pb-2 pr-4 font-medium">Employees</th>
                      <th className="pb-2 pr-4 font-medium">Gross</th>
                      <th className="pb-2 pr-4 font-medium">Deductions</th>
                      <th className="pb-2 pr-4 font-medium">Net Pay</th>
                      <th className="pb-2 pr-4 font-medium">Status</th>
                      <th className="pb-2 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedHistory.map(p => (
                      <React.Fragment key={p.id}>
                        <tr className="border-b hover:bg-slate-50 cursor-pointer" onClick={() => toggleExpand(p.id)} data-testid={`payroll-row-${p.period}`}>
                          <td className="py-3 pr-4 font-medium">{MONTHS[(p.month || 1) - 1]} {p.year}</td>
                          <td className="py-3 pr-4">{p.total_employees}</td>
                          <td className="py-3 pr-4">{formatINR(p.total_gross)}</td>
                          <td className="py-3 pr-4 text-red-600">{formatINR(p.total_deductions)}</td>
                          <td className="py-3 pr-4 font-semibold text-green-700">{formatINR(p.total_net_pay)}</td>
                          <td className="py-3 pr-4">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${p.status === 'finalized' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                              {p.status === 'finalized' ? 'Finalized' : 'Draft'}
                            </span>
                          </td>
                          <td className="py-3">
                            <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                              {p.status === 'draft' && (
                                <>
                                  <Button size="sm" variant="outline" className="h-7 text-xs bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100" onClick={() => openReview(p.id)} data-testid={`review-btn-${p.id}`}>
                                    <Eye className="w-3 h-3 mr-1" /> Review & Adjust
                                  </Button>
                                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => handleFinalize(p.id)} data-testid={`finalize-${p.id}`}>
                                    <CheckCircle className="w-3 h-3 mr-1" /> Finalize
                                  </Button>
                                  <Button size="sm" variant="ghost" className="h-7 text-xs text-red-500" onClick={() => handleDelete(p.id)}>
                                    <Trash2 className="w-3 h-3" />
                                  </Button>
                                </>
                              )}
                              {p.status === 'finalized' && (
                                <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => openReview(p.id)} data-testid={`view-review-${p.id}`}>
                                  <Eye className="w-3 h-3 mr-1" /> View
                                </Button>
                              )}
                              <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => toggleExpand(p.id)}>
                                {expandedPayroll === p.id ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                              </Button>
                            </div>
                          </td>
                        </tr>
                        {expandedPayroll === p.id && (
                          <tr>
                            <td colSpan={7} className="p-0">
                              {detailLoading ? (
                                <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-blue-500" /></div>
                              ) : payrollDetail ? (
                                <div className="bg-slate-50 p-4 border-t">
                                  <div className="flex items-center justify-between mb-3">
                                    <h4 className="font-semibold text-sm text-slate-700">Employee Breakdown</h4>
                                    <div className="flex items-center gap-3">
                                      <span className="text-xs text-slate-400">PF Employer: {formatINR(payrollDetail.total_pf_employer)} | ESI Employer: {formatINR(payrollDetail.total_esi_employer)}</span>
                                      <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => {
                                        api.get(`/hrms/reports/payroll/${p.id}/pdf`, { responseType: 'blob' })
                                          .then(r => { const u = window.URL.createObjectURL(new Blob([r.data])); const a = document.createElement('a'); a.href = u; a.download = `Payroll_${p.period}.pdf`; a.click(); })
                                          .catch(() => toast.error('Failed'));
                                      }} data-testid={`export-payroll-pdf-${p.id}`}><FileText className="w-3 h-3 mr-1" /> PDF</Button>
                                      <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => {
                                        api.get(`/hrms/reports/payroll/${p.id}/excel`, { responseType: 'blob' })
                                          .then(r => { const u = window.URL.createObjectURL(new Blob([r.data])); const a = document.createElement('a'); a.href = u; a.download = `Payroll_${p.period}.xlsx`; a.click(); })
                                          .catch(() => toast.error('Failed'));
                                      }} data-testid={`export-payroll-excel-${p.id}`}><Download className="w-3 h-3 mr-1" /> Excel</Button>
                                    </div>
                                  </div>
                                  <div className="overflow-x-auto">
                                    <table className="w-full text-xs">
                                      <thead>
                                        <tr className="border-b text-slate-500">
                                          <th className="pb-2 text-left font-medium">Employee</th>
                                          <th className="pb-2 text-left font-medium">Dept</th>
                                          <th className="pb-2 text-right font-medium">Days</th>
                                          <th className="pb-2 text-right font-medium">Gross</th>
                                          <th className="pb-2 text-right font-medium">PF</th>
                                          <th className="pb-2 text-right font-medium">ESI</th>
                                          <th className="pb-2 text-right font-medium">PT</th>
                                          <th className="pb-2 text-right font-medium">TDS</th>
                                          <th className="pb-2 text-right font-medium">Net Pay</th>
                                          <th className="pb-2 text-center font-medium">Payslip</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {payrollDetail.employees?.map(emp => {
                                          const adjNet = (emp.adjustments || []).reduce((s, a) => s + (a.type === 'earning' ? a.amount : -a.amount), 0);
                                          const finalNet = emp.net_pay + adjNet;
                                          const hasAdj = (emp.adjustments || []).length > 0;
                                          return (
                                            <tr key={emp.employee_id} className={`border-b border-slate-100 ${hasAdj ? 'bg-amber-50/50' : ''}`} data-testid={`payroll-emp-${emp.employee_code}`}>
                                              <td className="py-2 font-medium">{emp.employee_code} - {emp.name}</td>
                                              <td className="py-2">{emp.department}</td>
                                              <td className="py-2 text-right">{emp.days_present}/{emp.working_days}</td>
                                              <td className="py-2 text-right">{formatINR(emp.gross_salary)}</td>
                                              <td className="py-2 text-right text-red-500">{formatINR(emp.pf_employee)}</td>
                                              <td className="py-2 text-right text-red-500">{formatINR(emp.esi_employee)}</td>
                                              <td className="py-2 text-right text-red-500">{formatINR(emp.professional_tax)}</td>
                                              <td className="py-2 text-right text-red-500">{formatINR(emp.tds)}</td>
                                              <td className="py-2 text-right font-semibold text-green-700">
                                                {formatINR(finalNet)}
                                                {hasAdj && <span className="text-[9px] text-amber-500 block">adj: {adjNet >= 0 ? '+' : ''}{formatINR(adjNet)}</span>}
                                              </td>
                                              <td className="py-2 text-center">
                                                <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => downloadPayslip(p.id, emp.employee_id, emp.name)} data-testid={`payslip-${emp.employee_code}`}>
                                                  <Download className="w-3 h-3" />
                                                </Button>
                                              </td>
                                            </tr>
                                          );
                                        })}
                                      </tbody>
                                    </table>
                                  </div>
                                </div>
                              ) : null}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t" data-testid="payroll-pagination">
                <span className="text-xs text-slate-500">Page {currentPage} of {totalPages} ({history.length} total)</span>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" disabled={currentPage <= 1} onClick={() => setCurrentPage(p => p - 1)} data-testid="payroll-prev-page">
                    <ChevronUp className="w-4 h-4 rotate-[-90deg]" />
                  </Button>
                  <Button variant="outline" size="sm" disabled={currentPage >= totalPages} onClick={() => setCurrentPage(p => p + 1)} data-testid="payroll-next-page">
                    <ChevronDown className="w-4 h-4 rotate-[-90deg]" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Run Payroll Dialog */}
      <Dialog open={runDialogOpen} onOpenChange={setRunDialogOpen}>
        <DialogContent className="sm:max-w-md" data-testid="run-payroll-dialog">
          <DialogHeader>
            <DialogTitle>Run Payroll</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Month</Label>
                <Select value={String(runMonth)} onValueChange={v => setRunMonth(Number(v))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {MONTHS.map((m, i) => (
                      <SelectItem key={i + 1} value={String(i + 1)}>{m}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Year</Label>
                <Input type="number" value={runYear} onChange={e => setRunYear(Number(e.target.value))} data-testid="payroll-year" />
              </div>
            </div>
            <div>
              <Label>Working Days</Label>
              <Input type="number" value={workingDays} onChange={e => setWorkingDays(Number(e.target.value))} min={1} max={31} data-testid="working-days" />
              <p className="text-xs text-slate-400 mt-1">Used for pro-rata salary calculation based on attendance</p>
            </div>
            <Button className="w-full bg-blue-700 hover:bg-blue-800" onClick={handleRunPayroll} disabled={processing} data-testid="confirm-run-payroll">
              {processing ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Processing...</> : <><Play className="w-4 h-4 mr-2" /> Process Payroll</>}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Statutory Config Dialog */}
      <Dialog open={configDialog} onOpenChange={setConfigDialog}>
        <DialogContent className="sm:max-w-lg max-h-[80vh] overflow-y-auto" data-testid="payroll-config-dialog">
          <DialogHeader>
            <DialogTitle>Statutory Configuration</DialogTitle>
          </DialogHeader>
          {config ? (
            <div className="space-y-5 pt-2">
              <div className="p-3 bg-blue-50 rounded-lg">
                <h4 className="font-semibold text-sm text-blue-800 mb-3">Provident Fund (PF)</h4>
                <div className="grid grid-cols-3 gap-3">
                  <div><Label className="text-xs">Employee %</Label><Input type="number" step="0.1" value={config.pf_employee_rate} onChange={e => setConfig({ ...config, pf_employee_rate: Number(e.target.value) })} /></div>
                  <div><Label className="text-xs">Employer %</Label><Input type="number" step="0.1" value={config.pf_employer_rate} onChange={e => setConfig({ ...config, pf_employer_rate: Number(e.target.value) })} /></div>
                  <div><Label className="text-xs">Wage Ceiling</Label><Input type="number" value={config.pf_wage_ceiling} onChange={e => setConfig({ ...config, pf_wage_ceiling: Number(e.target.value) })} /></div>
                </div>
              </div>
              <div className="p-3 bg-green-50 rounded-lg">
                <h4 className="font-semibold text-sm text-green-800 mb-3">ESI</h4>
                <div className="grid grid-cols-3 gap-3">
                  <div><Label className="text-xs">Employee %</Label><Input type="number" step="0.01" value={config.esi_employee_rate} onChange={e => setConfig({ ...config, esi_employee_rate: Number(e.target.value) })} /></div>
                  <div><Label className="text-xs">Employer %</Label><Input type="number" step="0.01" value={config.esi_employer_rate} onChange={e => setConfig({ ...config, esi_employer_rate: Number(e.target.value) })} /></div>
                  <div><Label className="text-xs">Wage Ceiling</Label><Input type="number" value={config.esi_wage_ceiling} onChange={e => setConfig({ ...config, esi_wage_ceiling: Number(e.target.value) })} /></div>
                </div>
              </div>
              <div className="p-3 bg-amber-50 rounded-lg">
                <h4 className="font-semibold text-sm text-amber-800 mb-3">Professional Tax Slabs</h4>
                {config.professional_tax_slabs?.map((slab, i) => (
                  <div key={i} className="grid grid-cols-3 gap-2 mb-2 text-xs">
                    <Input placeholder="Min" type="number" value={slab.min} onChange={e => { const s = [...config.professional_tax_slabs]; s[i].min = Number(e.target.value); setConfig({ ...config, professional_tax_slabs: s }); }} />
                    <Input placeholder="Max" type="number" value={slab.max} onChange={e => { const s = [...config.professional_tax_slabs]; s[i].max = Number(e.target.value); setConfig({ ...config, professional_tax_slabs: s }); }} />
                    <Input placeholder="Tax" type="number" value={slab.tax} onChange={e => { const s = [...config.professional_tax_slabs]; s[i].tax = Number(e.target.value); setConfig({ ...config, professional_tax_slabs: s }); }} />
                  </div>
                ))}
              </div>
              <Button className="w-full" onClick={handleSaveConfig} data-testid="save-config-btn">Save Configuration</Button>
            </div>
          ) : (
            <div className="py-6 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>
          )}
        </DialogContent>
      </Dialog>
    </HRMSLayout>
  );
};

export default PayrollManagement;
