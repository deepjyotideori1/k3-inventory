import React, { useState, useEffect, useCallback } from 'react';
import HRMSLayout from '../components/HRMSLayout';
import api from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { toast } from 'sonner';
import { formatDate } from '../lib/utils';
import {
  CalendarDays, Save, Loader2, Clock, UserCheck, UserX,
  AlertTriangle, Sun, ChevronLeft, ChevronRight, BarChart3, Download, FileText, User, Search,
  FileSpreadsheet, Upload, CheckCircle2, XCircle, AlertCircle
} from 'lucide-react';

const STATUS_OPTIONS = [
  { value: 'present', label: 'Present', color: 'bg-green-100 text-green-700', icon: UserCheck },
  { value: 'absent', label: 'Absent', color: 'bg-red-100 text-red-700', icon: UserX },
  { value: 'half_day', label: 'Half Day', color: 'bg-amber-100 text-amber-700', icon: Sun },
  { value: 'late', label: 'Late', color: 'bg-orange-100 text-orange-700', icon: Clock },
  { value: 'leave', label: 'Leave', color: 'bg-purple-100 text-purple-700', icon: CalendarDays },
  { value: 'holiday', label: 'Holiday', color: 'bg-blue-100 text-blue-700', icon: CalendarDays },
  { value: 'week_off', label: 'Week Off', color: 'bg-slate-100 text-slate-600', icon: CalendarDays },
];

const LEAVE_TYPES = [
  { value: 'casual', label: 'Casual Leave' },
  { value: 'sick', label: 'Sick Leave' },
  { value: 'earned', label: 'Earned Leave' },
  { value: 'unpaid', label: 'Unpaid Leave' },
];

const getStatusBadge = (status) => {
  const opt = STATUS_OPTIONS.find(s => s.value === status);
  if (!opt) return <span className="text-xs text-slate-400">Not Marked</span>;
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${opt.color}`}>{opt.label}</span>;
};

const AttendanceManagement = () => {
  const [activeTab, setActiveTab] = useState('daily');
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [employees, setEmployees] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [selectedDept, setSelectedDept] = useState('all');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [attendanceMap, setAttendanceMap] = useState({});

  // Monthly summary state
  const [summaryMonth, setSummaryMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  const [summaryData, setSummaryData] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  // Leave balance dialog
  const [leaveDialog, setLeaveDialog] = useState(null);
  const [leaveBalance, setLeaveBalance] = useState(null);

  // Employee Overview state
  const [allEmployees, setAllEmployees] = useState([]);
  const [overviewEmpId, setOverviewEmpId] = useState('');
  const [overviewStartDate, setOverviewStartDate] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
  });
  const [overviewEndDate, setOverviewEndDate] = useState(new Date().toISOString().split('T')[0]);
  const [overviewData, setOverviewData] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(false);

  // Bulk Upload state
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkStep, setBulkStep] = useState(1);
  const [bulkFile, setBulkFile] = useState(null);
  const [bulkValidating, setBulkValidating] = useState(false);
  const [bulkData, setBulkData] = useState(null);
  const [bulkMode, setBulkMode] = useState('skip');
  const [bulkConfirming, setBulkConfirming] = useState(false);
  const [bulkResult, setBulkResult] = useState(null);

  const fetchDepartments = useCallback(async () => {
    try {
      const res = await api.get('/hrms/departments');
      setDepartments(res.data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchAllEmployees = useCallback(async () => {
    try {
      const res = await api.get('/hrms/employees', { params: { limit: 200 } });
      setAllEmployees(res.data.employees || []);
    } catch (e) { console.error(e); }
  }, []);

  const fetchDailyAttendance = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/hrms/attendance/daily', { params: { date: selectedDate, department_id: selectedDept } });
      const emps = res.data.employees || [];
      setEmployees(emps);
      const map = {};
      emps.forEach(e => {
        map[e.employee_id] = {
          status: e.status || '',
          check_in: e.check_in || '',
          check_out: e.check_out || '',
          overtime_hours: e.overtime_hours || 0,
          leave_type: e.leave_type || '',
          remarks: e.remarks || '',
        };
      });
      setAttendanceMap(map);
    } catch (e) {
      toast.error('Failed to load attendance');
    } finally {
      setLoading(false);
    }
  }, [selectedDate, selectedDept]);

  const fetchMonthlySummary = useCallback(async () => {
    setSummaryLoading(true);
    try {
      const res = await api.get('/hrms/attendance/monthly-summary', { params: { month: summaryMonth, department_id: selectedDept } });
      setSummaryData(res.data);
    } catch (e) {
      toast.error('Failed to load summary');
    } finally {
      setSummaryLoading(false);
    }
  }, [summaryMonth, selectedDept]);

  useEffect(() => {
    fetchDepartments();
    fetchAllEmployees();
  }, [fetchDepartments, fetchAllEmployees]);

  useEffect(() => {
    if (activeTab === 'daily') fetchDailyAttendance();
    else if (activeTab === 'summary') fetchMonthlySummary();
  }, [activeTab, fetchDailyAttendance, fetchMonthlySummary]);

  const updateAttendance = (empId, field, value) => {
    setAttendanceMap(prev => ({
      ...prev,
      [empId]: { ...prev[empId], [field]: value }
    }));
  };

  const markAll = (status) => {
    const updated = {};
    employees.forEach(e => {
      updated[e.employee_id] = { ...attendanceMap[e.employee_id], status };
    });
    setAttendanceMap(updated);
  };

  const saveAttendance = async () => {
    const records = Object.entries(attendanceMap)
      .filter(([, v]) => v.status)
      .map(([empId, v]) => ({
        employee_id: empId,
        status: v.status,
        check_in: v.check_in,
        check_out: v.check_out,
        overtime_hours: v.overtime_hours,
        leave_type: v.leave_type,
        remarks: v.remarks,
      }));

    if (records.length === 0) {
      toast.error('Please mark attendance for at least one employee');
      return;
    }

    setSaving(true);
    try {
      const res = await api.post('/hrms/attendance/mark', { date: selectedDate, records });
      toast.success(res.data.message);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const navigateDate = (dir) => {
    const d = new Date(selectedDate);
    d.setDate(d.getDate() + dir);
    setSelectedDate(d.toISOString().split('T')[0]);
  };

  const navigateMonth = (dir) => {
    const [y, m] = summaryMonth.split('-').map(Number);
    const d = new Date(y, m - 1 + dir, 1);
    setSummaryMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  };

  const showLeaveBalance = async (empId) => {
    try {
      const res = await api.get(`/hrms/leave/balance/${empId}`);
      setLeaveBalance(res.data);
      setLeaveDialog(empId);
    } catch (e) {
      toast.error('Failed to fetch leave balance');
    }
  };

  // Employee Overview functions
  const fetchEmployeeOverview = async () => {
    if (!overviewEmpId) {
      toast.error('Please select an employee');
      return;
    }
    if (!overviewStartDate || !overviewEndDate) {
      toast.error('Please select a date range');
      return;
    }
    if (overviewStartDate > overviewEndDate) {
      toast.error('Start date must be before end date');
      return;
    }
    setOverviewLoading(true);
    try {
      const res = await api.get('/hrms/attendance/employee-overview', {
        params: { employee_id: overviewEmpId, start_date: overviewStartDate, end_date: overviewEndDate }
      });
      setOverviewData(res.data);
    } catch (e) {
      toast.error('Failed to load employee overview');
    } finally {
      setOverviewLoading(false);
    }
  };

  const exportOverview = (format) => {
    if (!overviewEmpId || !overviewStartDate || !overviewEndDate) {
      toast.error('Please search first');
      return;
    }
    const url = `/hrms/reports/attendance-employee/${format}?employee_id=${overviewEmpId}&start_date=${overviewStartDate}&end_date=${overviewEndDate}`;
    api.get(url, { responseType: 'blob' })
      .then(r => {
        const blob = new Blob([r.data]);
        const a = document.createElement('a');
        a.href = window.URL.createObjectURL(blob);
        const ext = format === 'pdf' ? 'pdf' : 'xlsx';
        a.download = `Attendance_${overviewData?.employee?.name || 'Employee'}_${overviewStartDate}_to_${overviewEndDate}.${ext}`;
        a.click();
        toast.success(`${format.toUpperCase()} downloaded`);
      })
      .catch(() => toast.error(`Failed to export ${format.toUpperCase()}`));
  };

  const markedCount = Object.values(attendanceMap).filter(v => v.status).length;

  // ===== BULK UPLOAD HANDLERS =====
  const openBulkUpload = () => {
    setBulkStep(1); setBulkFile(null); setBulkData(null); setBulkResult(null); setBulkMode('skip'); setBulkOpen(true);
  };

  const downloadAttTemplate = async () => {
    try {
      const res = await api.get('/hrms/attendance/bulk-upload/template', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a'); a.href = url; a.download = 'Attendance_Upload_Template.xlsx'; a.click();
      window.URL.revokeObjectURL(url);
      toast.success('Template downloaded');
    } catch (e) { toast.error('Failed to download template'); }
  };

  const handleBulkFileChange = (e) => {
    const f = e.target.files[0];
    if (f) {
      if (!f.name.endsWith('.xlsx')) { toast.error('Only .xlsx files are accepted'); return; }
      setBulkFile(f);
    }
  };

  const validateBulkFile = async () => {
    if (!bulkFile) { toast.error('Select a file first'); return; }
    setBulkValidating(true);
    try {
      const fd = new FormData(); fd.append('file', bulkFile);
      const res = await api.post('/hrms/attendance/bulk-upload/validate', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setBulkData(res.data); setBulkStep(2);
    } catch (e) { toast.error(e.response?.data?.detail || 'Validation failed'); }
    setBulkValidating(false);
  };

  const confirmBulkUpload = async () => {
    if (!bulkData) return;
    setBulkConfirming(true);
    try {
      const res = await api.post('/hrms/attendance/bulk-upload/confirm', { rows: bulkData.rows.filter(r => !r.has_errors), mode: bulkMode });
      setBulkResult(res.data); setBulkStep(3);
      toast.success(res.data.message);
    } catch (e) { toast.error(e.response?.data?.detail || 'Import failed'); }
    setBulkConfirming(false);
  };

  const downloadBulkErrorReport = async () => {
    if (!bulkData?.errors?.length) return;
    try {
      const res = await api.post('/hrms/attendance/bulk-upload/error-report', { errors: bulkData.errors }, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a'); a.href = url; a.download = 'Attendance_Upload_Error_Report.xlsx'; a.click();
      window.URL.revokeObjectURL(url);
    } catch (e) { toast.error('Failed to download error report'); }
  };
  const presentCount = Object.values(attendanceMap).filter(v => ['present', 'late'].includes(v.status)).length;
  const absentCount = Object.values(attendanceMap).filter(v => v.status === 'absent').length;

  const displayDate = new Date(selectedDate + 'T00:00:00');
  const dateLabel = displayDate.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  const MONTH_NAMES = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const [smY, smM] = summaryMonth.split('-').map(Number);
  const summaryLabel = `${MONTH_NAMES[smM - 1]} ${smY}`;

  const STATUS_LABELS = { present: 'Present', absent: 'Absent', half_day: 'Half Day', late: 'Late', leave: 'Leave', holiday: 'Holiday', week_off: 'Week Off' };
  const LEAVE_LABELS = { casual: 'Casual', sick: 'Sick', earned: 'Earned', unpaid: 'Unpaid' };

  return (
    <HRMSLayout>
      <div className="space-y-5" data-testid="attendance-management">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Attendance</h1>
            <p className="text-slate-500 text-sm mt-1">Mark daily attendance, view summaries and employee reports</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit">
          <button
            className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === 'daily' ? 'bg-white shadow text-slate-800' : 'text-slate-500'}`}
            onClick={() => setActiveTab('daily')}
            data-testid="daily-tab"
          >
            <CalendarDays className="w-4 h-4 inline mr-1" /> Daily Entry
          </button>
          <button
            className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === 'summary' ? 'bg-white shadow text-slate-800' : 'text-slate-500'}`}
            onClick={() => setActiveTab('summary')}
            data-testid="summary-tab"
          >
            <BarChart3 className="w-4 h-4 inline mr-1" /> Monthly Summary
          </button>
          <button
            className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === 'overview' ? 'bg-white shadow text-slate-800' : 'text-slate-500'}`}
            onClick={() => setActiveTab('overview')}
            data-testid="overview-tab"
          >
            <User className="w-4 h-4 inline mr-1" /> Employee Overview
          </button>
          <button
            className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === 'bulk' ? 'bg-white shadow text-slate-800' : 'text-slate-500'}`}
            onClick={() => setActiveTab('bulk')}
            data-testid="bulk-upload-tab"
          >
            <FileSpreadsheet className="w-4 h-4 inline mr-1" /> Bulk Upload
          </button>
        </div>

        {/* Department Filter (for daily/summary tabs) */}
        {activeTab !== 'overview' && activeTab !== 'bulk' && (
          <div className="flex gap-3 items-end">
            <div>
              <Label className="text-xs text-slate-500">Department</Label>
              <Select value={selectedDept} onValueChange={setSelectedDept}>
                <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Departments</SelectItem>
                  {departments.map(d => (
                    <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        {/* DAILY TAB */}
        {activeTab === 'daily' && (
          <>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => navigateDate(-1)}><ChevronLeft className="w-4 h-4" /></Button>
                <div className="flex items-center gap-2">
                  <Input
                    type="date"
                    value={selectedDate}
                    onChange={e => setSelectedDate(e.target.value)}
                    className="w-40"
                    data-testid="attendance-date"
                  />
                  <span className="text-sm text-slate-600 hidden sm:inline">{dateLabel}</span>
                </div>
                <Button variant="outline" size="sm" onClick={() => navigateDate(1)}><ChevronRight className="w-4 h-4" /></Button>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-400">{markedCount}/{employees.length} marked</span>
                <div className="flex gap-1">
                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => markAll('present')} data-testid="mark-all-present">All Present</Button>
                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => markAll('absent')}>All Absent</Button>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <Card><CardContent className="p-3 text-center"><p className="text-xs text-slate-500">Present</p><p className="text-lg font-bold text-green-700">{presentCount}</p></CardContent></Card>
              <Card><CardContent className="p-3 text-center"><p className="text-xs text-slate-500">Absent</p><p className="text-lg font-bold text-red-600">{absentCount}</p></CardContent></Card>
              <Card><CardContent className="p-3 text-center"><p className="text-xs text-slate-500">Total</p><p className="text-lg font-bold text-slate-700">{employees.length}</p></CardContent></Card>
            </div>

            <Card>
              <CardContent className="p-0">
                {loading ? (
                  <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
                ) : employees.length === 0 ? (
                  <p className="text-slate-400 text-sm text-center py-12">No active employees found</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-slate-50 text-left text-slate-500 text-xs">
                          <th className="p-3 font-medium">Employee</th>
                          <th className="p-3 font-medium">Department</th>
                          <th className="p-3 font-medium">Status</th>
                          <th className="p-3 font-medium">Check In</th>
                          <th className="p-3 font-medium">Check Out</th>
                          <th className="p-3 font-medium">OT (hrs)</th>
                          <th className="p-3 font-medium">Leave Type</th>
                          <th className="p-3 font-medium">Remarks</th>
                        </tr>
                      </thead>
                      <tbody>
                        {employees.map(emp => {
                          const att = attendanceMap[emp.employee_id] || {};
                          return (
                            <tr key={emp.employee_id} className="border-b hover:bg-slate-50" data-testid={`att-row-${emp.employee_code}`}>
                              <td className="p-3">
                                <div>
                                  <p className="font-medium text-slate-700">{emp.name}</p>
                                  <p className="text-xs text-slate-400">{emp.employee_code}</p>
                                </div>
                              </td>
                              <td className="p-3 text-slate-600 text-xs">{emp.department}</td>
                              <td className="p-3">
                                <Select
                                  value={att.status || 'not_marked'}
                                  onValueChange={v => updateAttendance(emp.employee_id, 'status', v === 'not_marked' ? '' : v)}
                                >
                                  <SelectTrigger className="w-28 h-8 text-xs">
                                    <SelectValue placeholder="Select" />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="not_marked">-- Select --</SelectItem>
                                    {STATUS_OPTIONS.map(s => (
                                      <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </td>
                              <td className="p-3">
                                <Input type="time" value={att.check_in || ''} onChange={e => updateAttendance(emp.employee_id, 'check_in', e.target.value)} className="w-28 h-8 text-xs" />
                              </td>
                              <td className="p-3">
                                <Input type="time" value={att.check_out || ''} onChange={e => updateAttendance(emp.employee_id, 'check_out', e.target.value)} className="w-28 h-8 text-xs" />
                              </td>
                              <td className="p-3">
                                <Input type="number" min="0" step="0.5" value={att.overtime_hours || ''} onChange={e => updateAttendance(emp.employee_id, 'overtime_hours', e.target.value)} className="w-16 h-8 text-xs" placeholder="0" />
                              </td>
                              <td className="p-3">
                                {att.status === 'leave' ? (
                                  <Select value={att.leave_type || 'casual'} onValueChange={v => updateAttendance(emp.employee_id, 'leave_type', v)}>
                                    <SelectTrigger className="w-32 h-8 text-xs"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                      {LEAVE_TYPES.map(lt => (
                                        <SelectItem key={lt.value} value={lt.value}>{lt.label}</SelectItem>
                                      ))}
                                    </SelectContent>
                                  </Select>
                                ) : (
                                  <span className="text-xs text-slate-300">-</span>
                                )}
                              </td>
                              <td className="p-3">
                                <Input value={att.remarks || ''} onChange={e => updateAttendance(emp.employee_id, 'remarks', e.target.value)} className="w-32 h-8 text-xs" placeholder="Note..." />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            {employees.length > 0 && (
              <div className="flex justify-end">
                <Button className="bg-blue-700 hover:bg-blue-800 gap-2" onClick={saveAttendance} disabled={saving} data-testid="save-attendance-btn">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save Attendance
                </Button>
              </div>
            )}
          </>
        )}

        {/* SUMMARY TAB */}
        {activeTab === 'summary' && (
          <>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => navigateMonth(-1)}><ChevronLeft className="w-4 h-4" /></Button>
                <span className="font-medium text-slate-700 min-w-[160px] text-center">{summaryLabel}</span>
                <Button variant="outline" size="sm" onClick={() => navigateMonth(1)}><ChevronRight className="w-4 h-4" /></Button>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => {
                  api.get(`/hrms/reports/attendance/pdf?month=${summaryMonth}${selectedDept !== 'all' ? `&department_id=${selectedDept}` : ''}`, { responseType: 'blob' })
                    .then(r => { const u = window.URL.createObjectURL(new Blob([r.data])); const a = document.createElement('a'); a.href = u; a.download = `Attendance_${summaryMonth}.pdf`; a.click(); })
                    .catch(() => toast.error('Failed to export PDF'));
                }} data-testid="export-attendance-pdf"><FileText className="w-4 h-4 mr-1" /> PDF</Button>
                <Button variant="outline" size="sm" onClick={() => {
                  api.get(`/hrms/reports/attendance/excel?month=${summaryMonth}${selectedDept !== 'all' ? `&department_id=${selectedDept}` : ''}`, { responseType: 'blob' })
                    .then(r => { const u = window.URL.createObjectURL(new Blob([r.data])); const a = document.createElement('a'); a.href = u; a.download = `Attendance_${summaryMonth}.xlsx`; a.click(); })
                    .catch(() => toast.error('Failed to export Excel'));
                }} data-testid="export-attendance-excel"><Download className="w-4 h-4 mr-1" /> Excel</Button>
              </div>
            </div>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Monthly Attendance Summary</CardTitle>
              </CardHeader>
              <CardContent>
                {summaryLoading ? (
                  <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
                ) : !summaryData || summaryData.summaries?.length === 0 ? (
                  <p className="text-slate-400 text-sm text-center py-8">No attendance data for this month</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b bg-slate-50 text-left text-slate-500">
                          <th className="p-2 font-medium">Employee</th>
                          <th className="p-2 font-medium">Dept</th>
                          <th className="p-2 text-center font-medium text-green-700">Present</th>
                          <th className="p-2 text-center font-medium text-red-600">Absent</th>
                          <th className="p-2 text-center font-medium text-amber-600">Half Day</th>
                          <th className="p-2 text-center font-medium text-orange-600">Late</th>
                          <th className="p-2 text-center font-medium text-purple-600">Leave</th>
                          <th className="p-2 text-center font-medium text-blue-600">Holiday</th>
                          <th className="p-2 text-center font-medium">Week Off</th>
                          <th className="p-2 text-center font-medium">OT Hrs</th>
                          <th className="p-2 text-center font-medium">Effective</th>
                          <th className="p-2 text-center font-medium">Leave Bal.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summaryData.summaries.map(s => (
                          <tr key={s.employee_id} className="border-b hover:bg-slate-50" data-testid={`summary-row-${s.employee_code}`}>
                            <td className="p-2">
                              <p className="font-medium">{s.name}</p>
                              <p className="text-slate-400">{s.employee_code}</p>
                            </td>
                            <td className="p-2 text-slate-500">{s.department}</td>
                            <td className="p-2 text-center font-medium text-green-700">{s.present}</td>
                            <td className="p-2 text-center font-medium text-red-600">{s.absent}</td>
                            <td className="p-2 text-center text-amber-600">{s.half_day}</td>
                            <td className="p-2 text-center text-orange-600">{s.late}</td>
                            <td className="p-2 text-center text-purple-600">{s.leave}</td>
                            <td className="p-2 text-center text-blue-600">{s.holiday}</td>
                            <td className="p-2 text-center">{s.week_off}</td>
                            <td className="p-2 text-center">{s.overtime_hours}</td>
                            <td className="p-2 text-center font-bold text-slate-700">{s.effective_present}</td>
                            <td className="p-2 text-center">
                              <Button size="sm" variant="ghost" className="h-6 text-xs text-blue-600" onClick={() => showLeaveBalance(s.employee_id)} data-testid={`leave-bal-${s.employee_code}`}>
                                View
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
          </>
        )}

        {/* EMPLOYEE OVERVIEW TAB */}
        {activeTab === 'overview' && (
          <>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Employee Attendance Overview</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-3 items-end">
                  <div className="flex-1 min-w-[200px]">
                    <Label className="text-xs text-slate-500">Employee</Label>
                    <Select value={overviewEmpId} onValueChange={setOverviewEmpId}>
                      <SelectTrigger data-testid="overview-employee-select"><SelectValue placeholder="Select Employee" /></SelectTrigger>
                      <SelectContent>
                        {allEmployees.map(e => (
                          <SelectItem key={e.id} value={e.id}>{e.name} ({e.employee_id})</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs text-slate-500">Start Date</Label>
                    <Input type="date" value={overviewStartDate} onChange={e => setOverviewStartDate(e.target.value)} className="w-40" data-testid="overview-start-date" />
                  </div>
                  <div>
                    <Label className="text-xs text-slate-500">End Date</Label>
                    <Input type="date" value={overviewEndDate} onChange={e => setOverviewEndDate(e.target.value)} className="w-40" data-testid="overview-end-date" />
                  </div>
                  <Button className="bg-blue-700 hover:bg-blue-800 gap-1" onClick={fetchEmployeeOverview} disabled={overviewLoading} data-testid="overview-search-btn">
                    {overviewLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                    Search
                  </Button>
                  {overviewData && (
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={() => exportOverview('pdf')} data-testid="overview-export-pdf">
                        <FileText className="w-4 h-4 mr-1" /> PDF
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => exportOverview('excel')} data-testid="overview-export-excel">
                        <Download className="w-4 h-4 mr-1" /> Excel
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {overviewLoading && (
              <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
            )}

            {overviewData && !overviewLoading && (
              <>
                {/* Employee Info */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex flex-wrap gap-6 items-center">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                          <User className="w-5 h-5 text-blue-700" />
                        </div>
                        <div>
                          <p className="font-semibold text-slate-800" data-testid="overview-emp-name">{overviewData.employee.name}</p>
                          <p className="text-xs text-slate-400">{overviewData.employee.employee_code} | {overviewData.employee.department} | {overviewData.employee.designation}</p>
                        </div>
                      </div>
                      <div className="ml-auto text-right">
                        <p className="text-xs text-slate-500">Period</p>
                        <p className="text-sm font-medium text-slate-700">{formatDate(overviewData.date_range.start)} to {formatDate(overviewData.date_range.end)}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Summary Cards */}
                <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2">
                  {[
                    { label: 'Present', value: overviewData.summary.present, color: 'text-green-700 bg-green-50' },
                    { label: 'Absent', value: overviewData.summary.absent, color: 'text-red-600 bg-red-50' },
                    { label: 'Half Day', value: overviewData.summary.half_day, color: 'text-amber-600 bg-amber-50' },
                    { label: 'Late', value: overviewData.summary.late, color: 'text-orange-600 bg-orange-50' },
                    { label: 'Leave', value: overviewData.summary.leave, color: 'text-purple-600 bg-purple-50' },
                    { label: 'Holiday', value: overviewData.summary.holiday, color: 'text-blue-600 bg-blue-50' },
                    { label: 'Week Off', value: overviewData.summary.week_off, color: 'text-slate-600 bg-slate-50' },
                    { label: 'OT Hrs', value: overviewData.summary.overtime_hours, color: 'text-cyan-700 bg-cyan-50' },
                    { label: 'Effective', value: overviewData.summary.effective_present, color: 'text-indigo-700 bg-indigo-50' },
                  ].map(item => (
                    <Card key={item.label} className={item.color}>
                      <CardContent className="p-2 text-center" data-testid={`overview-stat-${item.label.toLowerCase().replace(' ', '-')}`}>
                        <p className="text-[10px] font-medium opacity-80">{item.label}</p>
                        <p className="text-lg font-bold">{item.value}</p>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                {/* Leave Breakdown (if any leaves) */}
                {Object.keys(overviewData.summary.leave_breakdown || {}).length > 0 && (
                  <Card>
                    <CardContent className="p-3">
                      <p className="text-xs font-medium text-slate-600 mb-2">Leave Breakdown</p>
                      <div className="flex gap-4">
                        {Object.entries(overviewData.summary.leave_breakdown).map(([type, count]) => (
                          <span key={type} className="text-xs bg-purple-50 text-purple-700 px-2 py-1 rounded">
                            {LEAVE_LABELS[type] || type}: <strong>{count}</strong>
                          </span>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Detail Records */}
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Day-wise Attendance ({overviewData.summary.total_records} records)</CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    {overviewData.records.length === 0 ? (
                      <p className="text-slate-400 text-sm text-center py-8">No records found for this period</p>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b bg-slate-50 text-left text-slate-500">
                              <th className="p-2 font-medium">#</th>
                              <th className="p-2 font-medium">Date</th>
                              <th className="p-2 font-medium">Day</th>
                              <th className="p-2 font-medium">Status</th>
                              <th className="p-2 font-medium text-center">Check In</th>
                              <th className="p-2 font-medium text-center">Check Out</th>
                              <th className="p-2 font-medium text-center">OT Hrs</th>
                              <th className="p-2 font-medium">Leave Type</th>
                              <th className="p-2 font-medium">Remarks</th>
                            </tr>
                          </thead>
                          <tbody>
                            {overviewData.records.map((rec, i) => {
                              let dayName = '';
                              try { dayName = new Date(rec.date + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'short' }); } catch {}
                              return (
                                <tr key={rec.date} className="border-b hover:bg-slate-50" data-testid={`overview-row-${rec.date}`}>
                                  <td className="p-2 text-slate-400">{i + 1}</td>
                                  <td className="p-2 font-medium">{formatDate(rec.date)}</td>
                                  <td className="p-2 text-slate-500">{dayName}</td>
                                  <td className="p-2">{getStatusBadge(rec.status)}</td>
                                  <td className="p-2 text-center">{rec.check_in || '-'}</td>
                                  <td className="p-2 text-center">{rec.check_out || '-'}</td>
                                  <td className="p-2 text-center">{rec.overtime_hours || '-'}</td>
                                  <td className="p-2">{rec.status === 'leave' ? (LEAVE_LABELS[rec.leave_type] || rec.leave_type || '-') : '-'}</td>
                                  <td className="p-2 text-slate-500">{rec.remarks || '-'}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </>
            )}
          </>
        )}
        {/* BULK UPLOAD TAB */}
        {activeTab === 'bulk' && (
          <div className="space-y-4">
            {/* Step 1: Upload */}
            {bulkStep === 1 && !bulkOpen && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <FileSpreadsheet className="w-5 h-5 text-blue-600" />
                    Bulk Attendance Upload
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="border-2 border-dashed border-slate-200 rounded-lg p-6 text-center">
                    <FileSpreadsheet className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                    <p className="text-sm text-slate-600 mb-3">Upload .xlsx file with daily attendance records for multiple employees</p>
                    <div className="flex items-center justify-center gap-3 flex-wrap">
                      <label className="cursor-pointer">
                        <input type="file" accept=".xlsx" className="hidden" onChange={handleBulkFileChange} data-testid="att-bulk-file-input" />
                        <span className="inline-flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 transition cursor-pointer">
                          <Upload className="w-4 h-4" /> Choose File
                        </span>
                      </label>
                      {bulkFile && <span className="text-sm text-slate-600">{bulkFile.name}</span>}
                    </div>
                  </div>

                  <div className="bg-slate-50 rounded-lg p-4">
                    <p className="text-sm font-medium text-slate-700 mb-2">First time? Download the template</p>
                    <Button variant="outline" size="sm" onClick={downloadAttTemplate} className="gap-1" data-testid="att-download-template-btn">
                      <Download className="w-4 h-4" /> Download Attendance Template
                    </Button>
                    <ul className="text-xs text-slate-500 mt-3 space-y-1 list-disc list-inside">
                      <li>Required: Employee_ID, Date (DD-MM-YYYY), Status</li>
                      <li>Status values: Present / Absent / Late / Leave / Half Day / Holiday / Week Off</li>
                      <li>Leave_Type required when Status = Leave (Casual / Sick / Earned / Unpaid)</li>
                      <li>Template includes employee list for reference</li>
                    </ul>
                  </div>

                  <div className="flex justify-end">
                    <Button onClick={validateBulkFile} disabled={!bulkFile || bulkValidating} className="bg-blue-600 hover:bg-blue-700 gap-1" data-testid="att-validate-btn">
                      {bulkValidating ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                      {bulkValidating ? 'Validating...' : 'Validate & Preview'}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Step 2: Preview */}
            {bulkStep === 2 && bulkData && (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  <Card><CardContent className="p-3 text-center">
                    <p className="text-[10px] text-slate-500 font-medium">Total Rows</p>
                    <p className="text-lg font-bold text-slate-700" data-testid="att-bulk-total">{bulkData.total_rows}</p>
                  </CardContent></Card>
                  <Card className="bg-green-50"><CardContent className="p-3 text-center">
                    <p className="text-[10px] text-green-600 font-medium">Valid</p>
                    <p className="text-lg font-bold text-green-700" data-testid="att-bulk-valid">{bulkData.valid_count}</p>
                  </CardContent></Card>
                  <Card className="bg-red-50"><CardContent className="p-3 text-center">
                    <p className="text-[10px] text-red-600 font-medium">Errors</p>
                    <p className="text-lg font-bold text-red-600" data-testid="att-bulk-errors">{bulkData.error_count}</p>
                  </CardContent></Card>
                  <Card className="bg-blue-50"><CardContent className="p-3 text-center">
                    <p className="text-[10px] text-blue-600 font-medium">New</p>
                    <p className="text-lg font-bold text-blue-700">{bulkData.new_count}</p>
                  </CardContent></Card>
                  <Card className="bg-amber-50"><CardContent className="p-3 text-center">
                    <p className="text-[10px] text-amber-600 font-medium">Existing</p>
                    <p className="text-lg font-bold text-amber-700">{bulkData.update_count}</p>
                  </CardContent></Card>
                </div>

                {bulkData.error_count > 0 && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-red-700">{bulkData.error_count} row(s) have errors and will be skipped</p>
                      <Button variant="outline" size="sm" className="mt-2 text-xs border-red-300 text-red-700" onClick={downloadBulkErrorReport} data-testid="att-download-error-report">
                        <Download className="w-3 h-3 mr-1" /> Download Error Report
                      </Button>
                    </div>
                  </div>
                )}

                {bulkData.update_count > 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                    <p className="text-sm font-medium text-amber-800 mb-2">{bulkData.update_count} attendance record(s) already exist for these employee+date combinations</p>
                    <div className="flex gap-4">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="radio" name="attBulkMode" value="skip" checked={bulkMode === 'skip'} onChange={() => setBulkMode('skip')} className="accent-amber-600" />
                        <span className="text-sm text-slate-700">Skip duplicates</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="radio" name="attBulkMode" value="overwrite" checked={bulkMode === 'overwrite'} onChange={() => setBulkMode('overwrite')} className="accent-amber-600" />
                        <span className="text-sm text-slate-700">Overwrite existing</span>
                      </label>
                    </div>
                  </div>
                )}

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Preview ({bulkData.total_rows} records)</CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    <div className="max-h-[400px] overflow-auto">
                      <table className="w-full text-xs">
                        <thead className="sticky top-0 z-10">
                          <tr className="bg-slate-100 text-left text-slate-600">
                            <th className="p-2 font-medium">Row</th>
                            <th className="p-2 font-medium">Status</th>
                            <th className="p-2 font-medium">Employee</th>
                            <th className="p-2 font-medium">Date</th>
                            <th className="p-2 font-medium">Att. Status</th>
                            <th className="p-2 font-medium">In</th>
                            <th className="p-2 font-medium">Out</th>
                            <th className="p-2 font-medium">OT</th>
                            <th className="p-2 font-medium">Leave</th>
                            <th className="p-2 font-medium">Issues</th>
                          </tr>
                        </thead>
                        <tbody>
                          {bulkData.rows.map((row, i) => (
                            <tr key={i} className={`border-b ${row.has_errors ? 'bg-red-50' : row.is_existing ? 'bg-amber-50' : 'hover:bg-slate-50'}`} data-testid={`att-bulk-row-${i}`}>
                              <td className="p-2 text-slate-400">{row.row_num}</td>
                              <td className="p-2">
                                {row.has_errors ? <XCircle className="w-4 h-4 text-red-500" /> : row.is_existing ? <AlertCircle className="w-4 h-4 text-amber-500" /> : <CheckCircle2 className="w-4 h-4 text-green-500" />}
                              </td>
                              <td className="p-2">
                                <span className="font-medium">{row.employee_name || row.employee_code}</span>
                                <span className="text-slate-400 ml-1">({row.employee_code})</span>
                              </td>
                              <td className="p-2 font-mono">{formatDate(row.date)}</td>
                              <td className="p-2">{getStatusBadge(row.status)}</td>
                              <td className="p-2">{row.check_in || '-'}</td>
                              <td className="p-2">{row.check_out || '-'}</td>
                              <td className="p-2 text-center">{row.overtime_hours || '-'}</td>
                              <td className="p-2">{row.leave_type || '-'}</td>
                              <td className="p-2">
                                {row.has_errors && <span className="text-red-600">{row.errors.join('; ')}</span>}
                                {!row.has_errors && row.is_existing && <span className="text-amber-600">Exists</span>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>

                <div className="flex justify-between">
                  <Button variant="outline" onClick={() => { setBulkStep(1); setBulkFile(null); setBulkData(null); }}>
                    <ChevronLeft className="w-4 h-4 mr-1" /> Back
                  </Button>
                  <Button onClick={confirmBulkUpload} disabled={bulkConfirming || bulkData.valid_count === 0} className="bg-green-600 hover:bg-green-700 gap-1" data-testid="att-confirm-btn">
                    {bulkConfirming ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                    {bulkConfirming ? 'Importing...' : `Confirm Import (${bulkData.valid_count} records)`}
                  </Button>
                </div>
              </>
            )}

            {/* Step 3: Result */}
            {bulkStep === 3 && bulkResult && (
              <Card>
                <CardContent className="p-8 text-center space-y-4">
                  <CheckCircle2 className="w-14 h-14 text-green-500 mx-auto" />
                  <h3 className="text-lg font-bold text-slate-800">Attendance Import Complete</h3>
                  <div className="grid grid-cols-3 gap-3 max-w-sm mx-auto">
                    <Card className="bg-green-50"><CardContent className="p-3 text-center">
                      <p className="text-[10px] text-green-600 font-medium">Created</p>
                      <p className="text-xl font-bold text-green-700" data-testid="att-bulk-created">{bulkResult.created}</p>
                    </CardContent></Card>
                    <Card className="bg-blue-50"><CardContent className="p-3 text-center">
                      <p className="text-[10px] text-blue-600 font-medium">Updated</p>
                      <p className="text-xl font-bold text-blue-700" data-testid="att-bulk-updated">{bulkResult.updated}</p>
                    </CardContent></Card>
                    <Card className="bg-slate-50"><CardContent className="p-3 text-center">
                      <p className="text-[10px] text-slate-500 font-medium">Skipped</p>
                      <p className="text-xl font-bold text-slate-600" data-testid="att-bulk-skipped">{bulkResult.skipped}</p>
                    </CardContent></Card>
                  </div>
                  <Button onClick={() => { setBulkStep(1); setBulkFile(null); setBulkData(null); setBulkResult(null); }} className="bg-blue-600 hover:bg-blue-700" data-testid="att-bulk-done-btn">
                    Upload More
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>

      {/* Leave Balance Dialog */}
      <Dialog open={!!leaveDialog} onOpenChange={() => { setLeaveDialog(null); setLeaveBalance(null); }}>
        <DialogContent className="sm:max-w-md" data-testid="leave-balance-dialog">
          <DialogHeader>
            <DialogTitle>Leave Balance - {leaveBalance?.employee_name}</DialogTitle>
          </DialogHeader>
          {leaveBalance ? (
            <div className="space-y-3 pt-2">
              <p className="text-xs text-slate-500">Year: {leaveBalance.year}</p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-slate-500">
                    <th className="pb-2 font-medium">Leave Type</th>
                    <th className="pb-2 text-center font-medium">Quota</th>
                    <th className="pb-2 text-center font-medium">Taken</th>
                    <th className="pb-2 text-center font-medium">Remaining</th>
                  </tr>
                </thead>
                <tbody>
                  {leaveBalance.balances?.map(b => (
                    <tr key={b.leave_type_id} className="border-b">
                      <td className="py-2">{b.leave_type_name}</td>
                      <td className="py-2 text-center">{b.annual_quota || '-'}</td>
                      <td className="py-2 text-center text-red-600">{b.taken}</td>
                      <td className="py-2 text-center font-medium text-green-700">{b.remaining}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-6 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto" /></div>
          )}
        </DialogContent>
      </Dialog>
    </HRMSLayout>
  );
};

export default AttendanceManagement;
