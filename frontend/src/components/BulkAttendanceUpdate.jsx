import React, { useState, useEffect, useCallback, useMemo } from 'react';
import api from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import { formatDate } from '../lib/utils';
import {
  Loader2, Search, CheckCircle2, ArrowRight, ArrowLeft,
  AlertTriangle, Undo2, Calendar, Users, Grid3X3
} from 'lucide-react';

const STATUS_OPTIONS = [
  { value: 'present', label: 'Present', short: 'P', color: 'bg-green-500', cellColor: 'bg-green-100 text-green-700 border-green-300' },
  { value: 'absent', label: 'Absent', short: 'A', color: 'bg-red-500', cellColor: 'bg-red-100 text-red-700 border-red-300' },
  { value: 'half_day', label: 'Half Day', short: 'HD', color: 'bg-amber-500', cellColor: 'bg-amber-100 text-amber-700 border-amber-300' },
  { value: 'leave', label: 'Leave', short: 'L', color: 'bg-purple-500', cellColor: 'bg-purple-100 text-purple-700 border-purple-300' },
  { value: 'holiday', label: 'Holiday', short: 'H', color: 'bg-blue-500', cellColor: 'bg-blue-100 text-blue-700 border-blue-300' },
  { value: 'week_off', label: 'Week Off', short: 'WO', color: 'bg-slate-400', cellColor: 'bg-slate-100 text-slate-600 border-slate-300' },
];

const LEAVE_TYPES = [
  { value: 'casual', label: 'Casual Leave' },
  { value: 'sick', label: 'Sick Leave' },
  { value: 'earned', label: 'Earned Leave' },
  { value: 'unpaid', label: 'Unpaid Leave' },
];

const getCellStyle = (status) => {
  const opt = STATUS_OPTIONS.find(s => s.value === status);
  return opt ? opt.cellColor : 'bg-slate-50 text-slate-300 border-slate-200';
};

const getShortLabel = (status) => {
  const opt = STATUS_OPTIONS.find(s => s.value === status);
  return opt ? opt.short : '-';
};

const BulkAttendanceUpdate = ({ onClose, onSuccess }) => {
  const [step, setStep] = useState(1); // 1=Select Emps, 2=Select Dates, 3=Grid Edit, 4=Review
  const [employees, setEmployees] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);

  // Selections
  const [selectedEmpIds, setSelectedEmpIds] = useState(new Set());
  const [empSearch, setEmpSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('all');
  const [dateMode, setDateMode] = useState('range'); // range | custom
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [customDates, setCustomDates] = useState('');
  const [applyMode, setApplyMode] = useState('same'); // same | grid
  const [bulkStatus, setBulkStatus] = useState('present');
  const [leaveType, setLeaveType] = useState('casual');
  const [reason, setReason] = useState('');

  // Grid data: { [empId_date]: status }
  const [gridData, setGridData] = useState({});
  const [gridLeaveTypes, setGridLeaveTypes] = useState({});

  // Preview & submit
  const [submitting, setSubmitting] = useState(false);
  const [lastLogId, setLastLogId] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [empRes, deptRes] = await Promise.all([
        api.get('/hrms/employees?limit=500'),
        api.get('/hrms/departments'),
      ]);
      setEmployees((empRes.data.employees || []).filter(e => e.is_active));
      setDepartments(deptRes.data || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Computed dates array
  const selectedDates = useMemo(() => {
    if (dateMode === 'range' && startDate && endDate) {
      const dates = [];
      const d = new Date(startDate);
      const end = new Date(endDate);
      while (d <= end) {
        dates.push(d.toISOString().split('T')[0]);
        d.setDate(d.getDate() + 1);
      }
      return dates;
    }
    if (dateMode === 'custom' && customDates) {
      return customDates.split(',').map(d => d.trim()).filter(d => /^\d{4}-\d{2}-\d{2}$/.test(d));
    }
    return [];
  }, [dateMode, startDate, endDate, customDates]);

  const filteredEmps = useMemo(() => {
    let list = employees;
    if (deptFilter !== 'all') list = list.filter(e => e.department_id === deptFilter);
    if (empSearch) {
      const q = empSearch.toLowerCase();
      list = list.filter(e => e.name.toLowerCase().includes(q) || (e.employee_id || '').toLowerCase().includes(q));
    }
    return list;
  }, [employees, deptFilter, empSearch]);

  const selectedEmps = useMemo(() => employees.filter(e => selectedEmpIds.has(e.id)), [employees, selectedEmpIds]);

  const toggleEmp = (id) => {
    setSelectedEmpIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const selectAllFiltered = () => {
    setSelectedEmpIds(prev => {
      const next = new Set(prev);
      filteredEmps.forEach(e => next.add(e.id));
      return next;
    });
  };

  const deselectAllFiltered = () => {
    setSelectedEmpIds(prev => {
      const next = new Set(prev);
      filteredEmps.forEach(e => next.delete(e.id));
      return next;
    });
  };

  // Initialize grid when entering grid step
  const initGrid = useCallback(async () => {
    if (selectedEmps.length === 0 || selectedDates.length === 0) return;
    // Fetch existing attendance for all selected employees and dates
    const newGrid = {};
    for (const emp of selectedEmps) {
      for (const date of selectedDates) {
        const key = `${emp.id}_${date}`;
        if (applyMode === 'same') {
          newGrid[key] = bulkStatus;
        } else {
          newGrid[key] = ''; // empty = keep existing or not marked
        }
      }
    }
    // Load existing data
    try {
      if (selectedDates.length > 0) {
        const res = await api.get('/hrms/attendance', {
          params: {
            start_date: selectedDates[0],
            end_date: selectedDates[selectedDates.length - 1],
            limit: 5000,
          }
        });
        for (const rec of (res.data.records || [])) {
          const key = `${rec.employee_id}_${rec.date}`;
          if (key in newGrid && applyMode === 'grid') {
            newGrid[key] = rec.status || '';
          }
        }
      }
    } catch (e) { console.error(e); }
    setGridData(newGrid);
  }, [selectedEmps, selectedDates, applyMode, bulkStatus]);

  const setCellStatus = (empId, date, status) => {
    setGridData(prev => ({ ...prev, [`${empId}_${date}`]: status }));
  };

  const setColumnStatus = (date, status) => {
    setGridData(prev => {
      const next = { ...prev };
      selectedEmps.forEach(emp => { next[`${emp.id}_${date}`] = status; });
      return next;
    });
  };

  const setRowStatus = (empId, status) => {
    setGridData(prev => {
      const next = { ...prev };
      selectedDates.forEach(date => { next[`${empId}_${date}`] = status; });
      return next;
    });
  };

  // Build entries for submission
  const buildEntries = () => {
    const entries = [];
    selectedEmps.forEach(emp => {
      selectedDates.forEach(date => {
        const key = `${emp.id}_${date}`;
        const status = gridData[key] || bulkStatus;
        if (status) {
          entries.push({
            employee_id: emp.id,
            date,
            status,
            leave_type: status === 'leave' ? (gridLeaveTypes[key] || leaveType) : '',
          });
        }
      });
    });
    return entries;
  };

  const handleSubmit = async () => {
    if (!reason.trim()) {
      toast.error('Reason is mandatory for bulk updates');
      return;
    }
    const entries = buildEntries();
    if (entries.length === 0) {
      toast.error('No entries to update');
      return;
    }
    setSubmitting(true);
    try {
      const res = await api.post('/hrms/attendance/bulk-update/apply', { entries, reason });
      toast.success(res.data.message);
      setLastLogId(res.data.log_id);
      onSuccess?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to apply bulk update');
    } finally { setSubmitting(false); }
  };

  const handleUndo = async () => {
    if (!lastLogId) return;
    if (!window.confirm('Undo the last bulk update? This will revert all changes.')) return;
    try {
      const res = await api.post('/hrms/attendance/bulk-update/undo', { log_id: lastLogId });
      toast.success(res.data.message);
      setLastLogId(null);
      onSuccess?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to undo');
    }
  };

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>;

  // =========== STEP 1: Select Employees ===========
  if (step === 1) return (
    <div className="space-y-4" data-testid="bulk-step-1">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-800">Step 1: Select Employees</h3>
          <p className="text-xs text-slate-500">Choose employees for bulk attendance update</p>
        </div>
        <span className="text-xs text-slate-400">Step 1 of 4</span>
      </div>
      <div className="flex flex-col sm:flex-row gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-slate-400" />
          <Input placeholder="Search employees..." value={empSearch} onChange={e => setEmpSearch(e.target.value)} className="pl-8" data-testid="emp-search" />
        </div>
        <Select value={deptFilter} onValueChange={setDeptFilter}>
          <SelectTrigger className="w-full sm:w-48" data-testid="dept-filter"><SelectValue placeholder="All Departments" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Departments</SelectItem>
            {departments.map(d => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <Button size="sm" variant="outline" className="h-7 text-xs" onClick={selectAllFiltered} data-testid="select-all">Select All ({filteredEmps.length})</Button>
          <Button size="sm" variant="outline" className="h-7 text-xs" onClick={deselectAllFiltered}>Deselect All</Button>
        </div>
        <span className="text-sm font-medium text-blue-700">{selectedEmpIds.size} selected</span>
      </div>
      <div className="max-h-60 overflow-y-auto border rounded-lg divide-y">
        {filteredEmps.map(emp => (
          <label key={emp.id} className={`flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-slate-50 ${selectedEmpIds.has(emp.id) ? 'bg-blue-50/50' : ''}`} data-testid={`emp-check-${emp.employee_id}`}>
            <Checkbox checked={selectedEmpIds.has(emp.id)} onCheckedChange={() => toggleEmp(emp.id)} />
            <span className="text-xs text-slate-400 w-16">{emp.employee_id}</span>
            <span className="text-sm font-medium flex-1">{emp.name}</span>
            <span className="text-xs text-slate-400">{emp.department_name}</span>
          </label>
        ))}
        {filteredEmps.length === 0 && <p className="text-sm text-slate-400 text-center py-4">No employees found</p>}
      </div>
      <div className="flex justify-between pt-2">
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button disabled={selectedEmpIds.size === 0} onClick={() => setStep(2)} data-testid="step1-next">
          Next: Select Dates <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  );

  // =========== STEP 2: Select Dates ===========
  if (step === 2) return (
    <div className="space-y-4" data-testid="bulk-step-2">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-slate-800">Step 2: Select Dates</h3>
          <p className="text-xs text-slate-500">{selectedEmpIds.size} employees selected</p>
        </div>
        <span className="text-xs text-slate-400">Step 2 of 4</span>
      </div>
      <div className="flex gap-3">
        <Button size="sm" variant={dateMode === 'range' ? 'default' : 'outline'} onClick={() => setDateMode('range')} data-testid="mode-range">
          <Calendar className="w-3.5 h-3.5 mr-1" /> Date Range
        </Button>
        <Button size="sm" variant={dateMode === 'custom' ? 'default' : 'outline'} onClick={() => setDateMode('custom')} data-testid="mode-custom">
          <Grid3X3 className="w-3.5 h-3.5 mr-1" /> Custom Dates
        </Button>
      </div>
      {dateMode === 'range' ? (
        <div className="grid grid-cols-2 gap-4">
          <div><Label>Start Date</Label><Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} data-testid="start-date" /></div>
          <div><Label>End Date</Label><Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} data-testid="end-date" /></div>
        </div>
      ) : (
        <div>
          <Label>Enter dates (YYYY-MM-DD, comma-separated)</Label>
          <Textarea placeholder="2026-04-01, 2026-04-05, 2026-04-10" value={customDates} onChange={e => setCustomDates(e.target.value)} rows={3} data-testid="custom-dates" />
        </div>
      )}
      {selectedDates.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {selectedDates.slice(0, 15).map(d => <span key={d} className="px-2 py-0.5 bg-blue-50 text-blue-700 text-[10px] rounded-full border border-blue-200">{formatDate(d)}</span>)}
          {selectedDates.length > 15 && <span className="text-xs text-slate-400">+{selectedDates.length - 15} more</span>}
        </div>
      )}
      <p className="text-sm text-slate-600">{selectedDates.length} date(s) selected</p>

      <div className="border-t pt-4 space-y-3">
        <h4 className="font-semibold text-sm">Apply Mode</h4>
        <div className="flex gap-3">
          <Button size="sm" variant={applyMode === 'same' ? 'default' : 'outline'} onClick={() => setApplyMode('same')} data-testid="mode-same">
            <Users className="w-3.5 h-3.5 mr-1" /> Same Status for All
          </Button>
          <Button size="sm" variant={applyMode === 'grid' ? 'default' : 'outline'} onClick={() => setApplyMode('grid')} data-testid="mode-grid">
            <Grid3X3 className="w-3.5 h-3.5 mr-1" /> Grid Editing
          </Button>
        </div>
        {applyMode === 'same' && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Status</Label>
              <Select value={bulkStatus} onValueChange={setBulkStatus}>
                <SelectTrigger data-testid="bulk-status-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map(s => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {bulkStatus === 'leave' && (
              <div>
                <Label>Leave Type</Label>
                <Select value={leaveType} onValueChange={setLeaveType}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {LEAVE_TYPES.map(l => <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex justify-between pt-2">
        <Button variant="outline" onClick={() => setStep(1)}><ArrowLeft className="w-4 h-4 mr-1" /> Back</Button>
        <Button disabled={selectedDates.length === 0} onClick={() => { initGrid(); setStep(3); }} data-testid="step2-next">
          Next: {applyMode === 'grid' ? 'Edit Grid' : 'Review'} <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  );

  // =========== STEP 3: Grid Edit / Preview ===========
  if (step === 3) {
    const totalEntries = selectedEmps.length * selectedDates.length;
    return (
      <div className="space-y-4" data-testid="bulk-step-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-slate-800">Step 3: {applyMode === 'grid' ? 'Edit Grid' : 'Preview'}</h3>
            <p className="text-xs text-slate-500">{selectedEmps.length} employees x {selectedDates.length} dates = {totalEntries} entries</p>
          </div>
          <span className="text-xs text-slate-400">Step 3 of 4</span>
        </div>

        {/* Status legend */}
        <div className="flex flex-wrap gap-2">
          {STATUS_OPTIONS.map(s => (
            <span key={s.value} className={`px-2 py-0.5 text-[10px] rounded font-medium border ${s.cellColor}`}>{s.short} = {s.label}</span>
          ))}
        </div>

        {/* Grid */}
        <div className="overflow-auto border rounded-lg max-h-[50vh]">
          <table className="text-xs w-full" data-testid="attendance-grid">
            <thead className="sticky top-0 z-10 bg-white">
              <tr>
                <th className="sticky left-0 bg-slate-100 z-20 px-3 py-2 text-left font-medium text-slate-600 min-w-[160px] border-b border-r">Employee</th>
                {selectedDates.map(date => {
                  const dayName = new Date(date + 'T00:00:00').toLocaleDateString('en', { weekday: 'short' });
                  const dayNum = date.split('-')[2];
                  return (
                    <th key={date} className="px-1 py-1 text-center font-medium text-slate-600 min-w-[44px] border-b cursor-pointer hover:bg-blue-50"
                      title={`Click to set all ${dayName} ${dayNum}`}>
                      <div className="text-[10px] text-slate-400">{dayName}</div>
                      <div>{dayNum}</div>
                      {applyMode === 'grid' && (
                        <select className="mt-0.5 text-[9px] w-full bg-transparent border-0 p-0 text-center cursor-pointer"
                          value="" onChange={e => { if (e.target.value) setColumnStatus(date, e.target.value); e.target.value = ''; }}>
                          <option value="">-</option>
                          {STATUS_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.short}</option>)}
                        </select>
                      )}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {selectedEmps.map(emp => (
                <tr key={emp.id} className="hover:bg-slate-50/50">
                  <td className="sticky left-0 bg-white z-10 px-3 py-1.5 border-r border-b font-medium min-w-[160px]">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-slate-400 text-[10px] mr-1">{emp.employee_id}</span>
                        <span className="text-slate-700">{emp.name}</span>
                      </div>
                      {applyMode === 'grid' && (
                        <select className="text-[9px] bg-transparent border-0 p-0 cursor-pointer"
                          value="" onChange={e => { if (e.target.value) setRowStatus(emp.id, e.target.value); e.target.value = ''; }}>
                          <option value="">Row</option>
                          {STATUS_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.short}</option>)}
                        </select>
                      )}
                    </div>
                  </td>
                  {selectedDates.map(date => {
                    const key = `${emp.id}_${date}`;
                    const val = gridData[key] || '';
                    return (
                      <td key={date} className="border-b p-0 text-center min-w-[44px]">
                        {applyMode === 'grid' ? (
                          <select
                            className={`w-full h-full py-1.5 px-0.5 text-[10px] font-bold text-center border-0 cursor-pointer ${getCellStyle(val)}`}
                            value={val}
                            onChange={e => setCellStatus(emp.id, date, e.target.value)}
                            data-testid={`cell-${emp.employee_id}-${date}`}
                          >
                            <option value="">-</option>
                            {STATUS_OPTIONS.map(s => <option key={s.value} value={s.value}>{s.short}</option>)}
                          </select>
                        ) : (
                          <span className={`block py-1.5 text-[10px] font-bold ${getCellStyle(val)}`}>
                            {getShortLabel(val)}
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex justify-between pt-2">
          <Button variant="outline" onClick={() => setStep(2)}><ArrowLeft className="w-4 h-4 mr-1" /> Back</Button>
          <Button onClick={() => setStep(4)} data-testid="step3-next">
            Next: Confirm <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </div>
    );
  }

  // =========== STEP 4: Review & Submit ===========
  if (step === 4) {
    const entries = buildEntries();
    return (
      <div className="space-y-4" data-testid="bulk-step-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-slate-800">Step 4: Review & Submit</h3>
            <p className="text-xs text-slate-500">Verify changes before applying</p>
          </div>
          <span className="text-xs text-slate-400">Step 4 of 4</span>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <Card><CardContent className="p-3 text-center"><p className="text-[10px] text-slate-500 uppercase">Employees</p><p className="text-xl font-bold text-blue-700">{selectedEmps.length}</p></CardContent></Card>
          <Card><CardContent className="p-3 text-center"><p className="text-[10px] text-slate-500 uppercase">Dates</p><p className="text-xl font-bold text-purple-700">{selectedDates.length}</p></CardContent></Card>
          <Card><CardContent className="p-3 text-center"><p className="text-[10px] text-slate-500 uppercase">Total Entries</p><p className="text-xl font-bold text-green-700">{entries.length}</p></CardContent></Card>
        </div>

        {/* Status breakdown */}
        <div className="flex flex-wrap gap-2">
          {STATUS_OPTIONS.map(s => {
            const count = entries.filter(e => e.status === s.value).length;
            if (count === 0) return null;
            return <span key={s.value} className={`px-2 py-1 text-xs rounded-full border font-medium ${s.cellColor}`}>{s.label}: {count}</span>;
          })}
        </div>

        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="text-xs text-amber-800">
            <p className="font-medium">This will update {entries.length} attendance records.</p>
            <p>Existing records will be overwritten. Locked payroll periods will be skipped.</p>
          </div>
        </div>

        <div>
          <Label>Reason for Bulk Update <span className="text-red-500">*</span></Label>
          <Textarea
            placeholder="Provide a reason for this bulk attendance change (mandatory for audit trail)"
            value={reason}
            onChange={e => setReason(e.target.value)}
            rows={3}
            data-testid="bulk-reason"
          />
        </div>

        <div className="flex justify-between pt-2">
          <Button variant="outline" onClick={() => setStep(3)}><ArrowLeft className="w-4 h-4 mr-1" /> Back</Button>
          <div className="flex gap-2">
            {lastLogId && (
              <Button variant="outline" className="text-amber-700 border-amber-300" onClick={handleUndo} data-testid="undo-btn">
                <Undo2 className="w-4 h-4 mr-1" /> Undo Last
              </Button>
            )}
            <Button className="bg-green-700 hover:bg-green-800" onClick={handleSubmit} disabled={submitting || !reason.trim()} data-testid="bulk-submit">
              {submitting ? <><Loader2 className="w-4 h-4 mr-1 animate-spin" /> Applying...</> : <><CheckCircle2 className="w-4 h-4 mr-1" /> Apply {entries.length} Updates</>}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default BulkAttendanceUpdate;
