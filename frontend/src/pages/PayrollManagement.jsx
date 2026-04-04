import React, { useState, useEffect, useCallback } from 'react';
import HRMSLayout from '../components/HRMSLayout';
import api from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { formatINR } from '../lib/utils';
import { toast } from 'sonner';
import {
  DollarSign, Play, CheckCircle, FileText, Trash2, Eye,
  Download, Loader2, Calculator, ChevronDown, ChevronUp
} from 'lucide-react';

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

const PayrollManagement = () => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [runDialogOpen, setRunDialogOpen] = useState(false);
  const [detailDialog, setDetailDialog] = useState(null);
  const [configDialog, setConfigDialog] = useState(false);
  const [config, setConfig] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [runMonth, setRunMonth] = useState(new Date().getMonth() + 1);
  const [runYear, setRunYear] = useState(new Date().getFullYear());
  const [workingDays, setWorkingDays] = useState(26);
  const [expandedPayroll, setExpandedPayroll] = useState(null);
  const [payrollDetail, setPayrollDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await api.get('/hrms/payroll/history');
      setHistory(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchConfig = async () => {
    try {
      const res = await api.get('/hrms/payroll/config');
      setConfig(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => { fetchHistory(); }, [fetchHistory]);

  const handleRunPayroll = async () => {
    setProcessing(true);
    try {
      const res = await api.post('/hrms/payroll/run', { month: runMonth, year: runYear, working_days: workingDays });
      toast.success(`Payroll processed for ${MONTHS[runMonth - 1]} ${runYear}`);
      setRunDialogOpen(false);
      fetchHistory();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to run payroll');
    } finally {
      setProcessing(false);
    }
  };

  const handleFinalize = async (id) => {
    if (!window.confirm('Finalize this payroll? This cannot be undone.')) return;
    try {
      await api.post(`/hrms/payroll/${id}/finalize`);
      toast.success('Payroll finalized');
      fetchHistory();
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
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to delete');
    }
  };

  const toggleExpand = async (id) => {
    if (expandedPayroll === id) {
      setExpandedPayroll(null);
      setPayrollDetail(null);
      return;
    }
    setExpandedPayroll(id);
    setDetailLoading(true);
    try {
      const res = await api.get(`/hrms/payroll/${id}`);
      setPayrollDetail(res.data);
    } catch (e) {
      toast.error('Failed to load payroll details');
    } finally {
      setDetailLoading(false);
    }
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
    } catch (e) {
      toast.error('Failed to download payslip');
    }
  };

  const handleSaveConfig = async () => {
    try {
      await api.put('/hrms/payroll/config', config);
      toast.success('Payroll configuration saved');
      setConfigDialog(false);
    } catch (e) {
      toast.error('Failed to save configuration');
    }
  };

  const totalGross = history.reduce((s, p) => s + (p.total_gross || 0), 0);
  const totalNet = history.reduce((s, p) => s + (p.total_net_pay || 0), 0);
  const latestPayroll = history[0];

  return (
    <HRMSLayout>
      <div className="space-y-6" data-testid="payroll-management">
        {/* Header */}
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
              <p className="text-2xl font-bold text-green-700 mt-1">{formatINR(latestPayroll?.total_net_pay || 0)}</p>
              <p className="text-xs text-slate-400">{latestPayroll ? `${MONTHS[(latestPayroll.month || 1) - 1]} ${latestPayroll.year}` : '-'}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-5">
              <p className="text-xs text-slate-500 font-medium uppercase">Latest Employees</p>
              <p className="text-2xl font-bold text-slate-800 mt-1">{latestPayroll?.total_employees || 0}</p>
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
                    {history.map(p => (
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
                                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => handleFinalize(p.id)} data-testid={`finalize-${p.id}`}>
                                    <CheckCircle className="w-3 h-3 mr-1" /> Finalize
                                  </Button>
                                  <Button size="sm" variant="ghost" className="h-7 text-xs text-red-500" onClick={() => handleDelete(p.id)}>
                                    <Trash2 className="w-3 h-3" />
                                  </Button>
                                </>
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
                                    <span className="text-xs text-slate-400">PF Employer: {formatINR(payrollDetail.total_pf_employer)} | ESI Employer: {formatINR(payrollDetail.total_esi_employer)}</span>
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
                                        {payrollDetail.employees?.map(emp => (
                                          <tr key={emp.employee_id} className="border-b border-slate-100" data-testid={`payroll-emp-${emp.employee_code}`}>
                                            <td className="py-2 font-medium">{emp.employee_code} - {emp.name}</td>
                                            <td className="py-2">{emp.department}</td>
                                            <td className="py-2 text-right">{emp.days_present}/{emp.working_days}</td>
                                            <td className="py-2 text-right">{formatINR(emp.gross_salary)}</td>
                                            <td className="py-2 text-right text-red-500">{formatINR(emp.pf_employee)}</td>
                                            <td className="py-2 text-right text-red-500">{formatINR(emp.esi_employee)}</td>
                                            <td className="py-2 text-right text-red-500">{formatINR(emp.professional_tax)}</td>
                                            <td className="py-2 text-right text-red-500">{formatINR(emp.tds)}</td>
                                            <td className="py-2 text-right font-semibold text-green-700">{formatINR(emp.net_pay)}</td>
                                            <td className="py-2 text-center">
                                              <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => downloadPayslip(p.id, emp.employee_id, emp.name)} data-testid={`payslip-${emp.employee_code}`}>
                                                <Download className="w-3 h-3" />
                                              </Button>
                                            </td>
                                          </tr>
                                        ))}
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
              {/* PF */}
              <div className="p-3 bg-blue-50 rounded-lg">
                <h4 className="font-semibold text-sm text-blue-800 mb-3">Provident Fund (PF)</h4>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <Label className="text-xs">Employee %</Label>
                    <Input type="number" step="0.1" value={config.pf_employee_rate} onChange={e => setConfig({ ...config, pf_employee_rate: Number(e.target.value) })} />
                  </div>
                  <div>
                    <Label className="text-xs">Employer %</Label>
                    <Input type="number" step="0.1" value={config.pf_employer_rate} onChange={e => setConfig({ ...config, pf_employer_rate: Number(e.target.value) })} />
                  </div>
                  <div>
                    <Label className="text-xs">Wage Ceiling</Label>
                    <Input type="number" value={config.pf_wage_ceiling} onChange={e => setConfig({ ...config, pf_wage_ceiling: Number(e.target.value) })} />
                  </div>
                </div>
              </div>

              {/* ESI */}
              <div className="p-3 bg-green-50 rounded-lg">
                <h4 className="font-semibold text-sm text-green-800 mb-3">ESI</h4>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <Label className="text-xs">Employee %</Label>
                    <Input type="number" step="0.01" value={config.esi_employee_rate} onChange={e => setConfig({ ...config, esi_employee_rate: Number(e.target.value) })} />
                  </div>
                  <div>
                    <Label className="text-xs">Employer %</Label>
                    <Input type="number" step="0.01" value={config.esi_employer_rate} onChange={e => setConfig({ ...config, esi_employer_rate: Number(e.target.value) })} />
                  </div>
                  <div>
                    <Label className="text-xs">Wage Ceiling</Label>
                    <Input type="number" value={config.esi_wage_ceiling} onChange={e => setConfig({ ...config, esi_wage_ceiling: Number(e.target.value) })} />
                  </div>
                </div>
              </div>

              {/* Professional Tax Slabs */}
              <div className="p-3 bg-amber-50 rounded-lg">
                <h4 className="font-semibold text-sm text-amber-800 mb-3">Professional Tax Slabs</h4>
                {config.professional_tax_slabs?.map((slab, i) => (
                  <div key={i} className="grid grid-cols-3 gap-2 mb-2 text-xs">
                    <Input placeholder="Min" type="number" value={slab.min} onChange={e => {
                      const s = [...config.professional_tax_slabs];
                      s[i].min = Number(e.target.value);
                      setConfig({ ...config, professional_tax_slabs: s });
                    }} />
                    <Input placeholder="Max" type="number" value={slab.max} onChange={e => {
                      const s = [...config.professional_tax_slabs];
                      s[i].max = Number(e.target.value);
                      setConfig({ ...config, professional_tax_slabs: s });
                    }} />
                    <Input placeholder="Tax" type="number" value={slab.tax} onChange={e => {
                      const s = [...config.professional_tax_slabs];
                      s[i].tax = Number(e.target.value);
                      setConfig({ ...config, professional_tax_slabs: s });
                    }} />
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
