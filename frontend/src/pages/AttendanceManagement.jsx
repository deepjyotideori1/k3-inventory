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
  AlertTriangle, Sun, ChevronLeft, ChevronRight, BarChart3
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

  const fetchDepartments = useCallback(async () => {
    try {
      const res = await api.get('/hrms/departments');
      setDepartments(res.data);
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

  useEffect(() => { fetchDepartments(); }, [fetchDepartments]);

  useEffect(() => {
    if (activeTab === 'daily') fetchDailyAttendance();
    else fetchMonthlySummary();
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

  const markedCount = Object.values(attendanceMap).filter(v => v.status).length;
  const presentCount = Object.values(attendanceMap).filter(v => ['present', 'late'].includes(v.status)).length;
  const absentCount = Object.values(attendanceMap).filter(v => v.status === 'absent').length;

  const displayDate = new Date(selectedDate + 'T00:00:00');
  const dateLabel = displayDate.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  const MONTH_NAMES = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const [smY, smM] = summaryMonth.split('-').map(Number);
  const summaryLabel = `${MONTH_NAMES[smM - 1]} ${smY}`;

  return (
    <HRMSLayout>
      <div className="space-y-5" data-testid="attendance-management">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Attendance</h1>
            <p className="text-slate-500 text-sm mt-1">Mark daily attendance and view monthly summaries</p>
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
        </div>

        {/* Department Filter */}
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

        {/* DAILY TAB */}
        {activeTab === 'daily' && (
          <>
            {/* Date Picker Row */}
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

            {/* Quick Stats */}
            <div className="grid grid-cols-3 gap-3">
              <Card><CardContent className="p-3 text-center"><p className="text-xs text-slate-500">Present</p><p className="text-lg font-bold text-green-700">{presentCount}</p></CardContent></Card>
              <Card><CardContent className="p-3 text-center"><p className="text-xs text-slate-500">Absent</p><p className="text-lg font-bold text-red-600">{absentCount}</p></CardContent></Card>
              <Card><CardContent className="p-3 text-center"><p className="text-xs text-slate-500">Total</p><p className="text-lg font-bold text-slate-700">{employees.length}</p></CardContent></Card>
            </div>

            {/* Attendance Table */}
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
                                <Input
                                  type="time"
                                  value={att.check_in || ''}
                                  onChange={e => updateAttendance(emp.employee_id, 'check_in', e.target.value)}
                                  className="w-28 h-8 text-xs"
                                />
                              </td>
                              <td className="p-3">
                                <Input
                                  type="time"
                                  value={att.check_out || ''}
                                  onChange={e => updateAttendance(emp.employee_id, 'check_out', e.target.value)}
                                  className="w-28 h-8 text-xs"
                                />
                              </td>
                              <td className="p-3">
                                <Input
                                  type="number"
                                  min="0"
                                  step="0.5"
                                  value={att.overtime_hours || ''}
                                  onChange={e => updateAttendance(emp.employee_id, 'overtime_hours', e.target.value)}
                                  className="w-16 h-8 text-xs"
                                  placeholder="0"
                                />
                              </td>
                              <td className="p-3">
                                {att.status === 'leave' ? (
                                  <Select
                                    value={att.leave_type || 'casual'}
                                    onValueChange={v => updateAttendance(emp.employee_id, 'leave_type', v)}
                                  >
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
                                <Input
                                  value={att.remarks || ''}
                                  onChange={e => updateAttendance(emp.employee_id, 'remarks', e.target.value)}
                                  className="w-32 h-8 text-xs"
                                  placeholder="Note..."
                                />
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

            {/* Save Button */}
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
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => navigateMonth(-1)}><ChevronLeft className="w-4 h-4" /></Button>
              <span className="font-medium text-slate-700 min-w-[160px] text-center">{summaryLabel}</span>
              <Button variant="outline" size="sm" onClick={() => navigateMonth(1)}><ChevronRight className="w-4 h-4" /></Button>
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
