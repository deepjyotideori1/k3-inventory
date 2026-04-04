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
import {
  CalendarDays, Save, Loader2, Clock, UserCheck, UserX,
  AlertTriangle, Sun, ChevronLeft, ChevronRight, BarChart3, Download, FileText, User, Search
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
        </div>

        {/* Department Filter (for daily/summary tabs) */}
        {activeTab !== 'overview' && (
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
                        <p className="text-sm font-medium text-slate-700">{overviewData.date_range.start} to {overviewData.date_range.end}</p>
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
                                  <td className="p-2 font-medium">{rec.date}</td>
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
