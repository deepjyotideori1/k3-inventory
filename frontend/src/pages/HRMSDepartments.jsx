import React, { useState, useEffect, useCallback } from 'react';
import HRMSLayout from '../components/HRMSLayout';
import api from '../lib/api';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import {
  Plus, Pencil, Building2, Power, PowerOff, GitMerge, History, Users
} from 'lucide-react';
import { toast } from 'sonner';

const emptyForm = { name: '', code: '', description: '', hod_employee_id: '' };

const HRMSDepartments = () => {
  const [departments, setDepartments] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);

  const [addOpen, setAddOpen] = useState(false);
  const [editDept, setEditDept] = useState(null);
  const [mergeDept, setMergeDept] = useState(null);
  const [historyDept, setHistoryDept] = useState(null);
  const [historyEntries, setHistoryEntries] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [form, setForm] = useState(emptyForm);
  const [mergeTargetId, setMergeTargetId] = useState('');
  const [mergeReason, setMergeReason] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchDepartments = useCallback(async () => {
    setLoading(true);
    try {
      const [deptRes, empRes] = await Promise.all([
        api.get('/hrms/departments', { params: { status: 'all' } }),
        api.get('/hrms/employees', { params: { limit: 500 } }),
      ]);
      setDepartments(deptRes.data || []);
      setEmployees((empRes.data?.employees ?? empRes.data ?? []).filter(e => e.is_active));
    } catch (e) { console.error(e); toast.error('Failed to load departments'); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchDepartments(); }, [fetchDepartments]);

  const handleAdd = async () => {
    if (!form.name.trim()) { toast.error('Department name is required'); return; }
    setSaving(true);
    try {
      await api.post('/hrms/departments', { ...form, hod_employee_id: form.hod_employee_id || null });
      toast.success('Department created');
      setAddOpen(false);
      setForm(emptyForm);
      fetchDepartments();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to create'); }
    setSaving(false);
  };

  const openEdit = (dept) => {
    setEditDept(dept);
    setForm({
      name: dept.name || '',
      code: dept.code || '',
      description: dept.description || '',
      hod_employee_id: dept.hod_employee_id || '',
    });
  };

  const handleUpdate = async () => {
    if (!form.name.trim()) { toast.error('Name is required'); return; }
    setSaving(true);
    try {
      await api.put(`/hrms/departments/${editDept.id}`, {
        ...form,
        hod_employee_id: form.hod_employee_id || null,
      });
      toast.success('Department updated');
      setEditDept(null);
      setForm(emptyForm);
      fetchDepartments();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to update'); }
    setSaving(false);
  };

  const handleToggleStatus = async (dept) => {
    const action = dept.is_active ? 'deactivate' : 'activate';
    const reason = window.prompt(`Reason to ${action} "${dept.name}" (optional):`) ?? null;
    if (reason === null) return; // user cancelled
    try {
      await api.post(`/hrms/departments/${dept.id}/toggle-status`, { reason });
      toast.success(`Department ${action}d`);
      fetchDepartments();
    } catch (e) { toast.error(e.response?.data?.detail || `Failed to ${action}`); }
  };

  const handleMerge = async () => {
    if (!mergeTargetId) { toast.error('Pick a target department'); return; }
    setSaving(true);
    try {
      const res = await api.post(`/hrms/departments/${mergeDept.id}/merge`, {
        target_dept_id: mergeTargetId,
        reason: mergeReason,
      });
      toast.success(res.data.message);
      setMergeDept(null);
      setMergeTargetId('');
      setMergeReason('');
      fetchDepartments();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to merge'); }
    setSaving(false);
  };

  const openHistory = async (dept) => {
    setHistoryDept(dept);
    setHistoryLoading(true);
    try {
      const res = await api.get(`/hrms/departments/${dept.id}/history`);
      setHistoryEntries(res.data || []);
    } catch (e) { toast.error('Failed to load history'); }
    setHistoryLoading(false);
  };

  return (
    <HRMSLayout>
      <div className="space-y-4" data-testid="hrms-departments">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Departments</h1>
            <p className="text-slate-500 text-sm">{departments.length} total · {departments.filter(d => d.is_active).length} active</p>
          </div>
          <Button onClick={() => { setForm(emptyForm); setAddOpen(true); }} className="gap-2 bg-blue-600 hover:bg-blue-700" data-testid="add-department-btn">
            <Plus className="w-4 h-4" /> Add Department
          </Button>
        </div>

        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>HOD</TableHead>
                  <TableHead>Employees</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow><TableCell colSpan={6} className="text-center py-8 text-slate-400">Loading...</TableCell></TableRow>
                ) : departments.length === 0 ? (
                  <TableRow><TableCell colSpan={6} className="text-center py-8 text-slate-400">No departments yet</TableCell></TableRow>
                ) : departments.map(dept => (
                  <TableRow key={dept.id} className={!dept.is_active ? 'opacity-60' : ''} data-testid={`dept-row-${dept.id}`}>
                    <TableCell>
                      <div className="flex items-center gap-2 font-medium">
                        <Building2 className="w-4 h-4 text-blue-500" />
                        {dept.name}
                      </div>
                      {dept.description && <div className="text-xs text-slate-500 mt-0.5">{dept.description}</div>}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-600">{dept.code || '—'}</TableCell>
                    <TableCell className="text-xs text-slate-600">
                      {dept.hod_name ? (
                        <span className="inline-flex items-center gap-1"><Users className="w-3 h-3" />{dept.hod_name}</span>
                      ) : <span className="text-slate-400">—</span>}
                    </TableCell>
                    <TableCell className="text-sm">
                      <span className="font-medium text-slate-700">{dept.active_employee_count ?? 0}</span>
                      <span className="text-slate-400"> / {dept.total_employee_count ?? 0}</span>
                    </TableCell>
                    <TableCell>
                      {dept.is_active ? (
                        <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100 border-emerald-200">Active</Badge>
                      ) : (
                        <Badge variant="outline" className="bg-slate-100 text-slate-500">Inactive</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => openEdit(dept)} data-testid={`edit-dept-${dept.id}`} title="Edit">
                          <Pencil className="w-4 h-4 text-slate-600" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleToggleStatus(dept)} data-testid={`toggle-dept-${dept.id}`} title={dept.is_active ? 'Deactivate' : 'Activate'}>
                          {dept.is_active ? <PowerOff className="w-4 h-4 text-amber-600" /> : <Power className="w-4 h-4 text-emerald-600" />}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => { setMergeDept(dept); setMergeTargetId(''); setMergeReason(''); }} disabled={!dept.is_active} data-testid={`merge-dept-${dept.id}`} title="Merge into another">
                          <GitMerge className="w-4 h-4 text-indigo-600" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => openHistory(dept)} data-testid={`history-dept-${dept.id}`} title="Change history">
                          <History className="w-4 h-4 text-violet-600" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {/* ADD dialog */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-md" data-testid="add-department-dialog">
          <DialogHeader><DialogTitle>Add Department</DialogTitle></DialogHeader>
          <DeptForm form={form} setForm={setForm} employees={employees} />
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button onClick={handleAdd} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="save-dept-btn">
              {saving ? 'Saving...' : 'Add Department'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* EDIT dialog */}
      <Dialog open={!!editDept} onOpenChange={(o) => !o && setEditDept(null)}>
        <DialogContent className="max-w-md" data-testid="edit-department-dialog">
          <DialogHeader>
            <DialogTitle>Edit Department</DialogTitle>
            <DialogDescription>Changes are versioned and logged for audit.</DialogDescription>
          </DialogHeader>
          <DeptForm form={form} setForm={setForm} employees={employees} />
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setEditDept(null)}>Cancel</Button>
            <Button onClick={handleUpdate} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="save-edit-dept-btn">
              {saving ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* MERGE dialog */}
      <Dialog open={!!mergeDept} onOpenChange={(o) => !o && setMergeDept(null)}>
        <DialogContent className="max-w-md" data-testid="merge-department-dialog">
          <DialogHeader>
            <DialogTitle>Merge “{mergeDept?.name}”</DialogTitle>
            <DialogDescription>
              All employees ({mergeDept?.total_employee_count || 0}) will be reassigned to the target and this department will be deactivated.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label className="text-sm">Target Department</Label>
              <Select value={mergeTargetId} onValueChange={setMergeTargetId}>
                <SelectTrigger className="mt-1" data-testid="merge-target-select"><SelectValue placeholder="Choose target..." /></SelectTrigger>
                <SelectContent>
                  {departments.filter(d => d.id !== mergeDept?.id && d.is_active).map(d => (
                    <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-sm">Reason</Label>
              <Textarea value={mergeReason} onChange={e => setMergeReason(e.target.value)} placeholder="Why are you merging?" className="mt-1" rows={2} data-testid="merge-reason" />
            </div>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setMergeDept(null)}>Cancel</Button>
            <Button onClick={handleMerge} disabled={saving} className="bg-indigo-600 hover:bg-indigo-700" data-testid="confirm-merge-btn">
              {saving ? 'Merging...' : 'Merge'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* HISTORY dialog */}
      <Dialog open={!!historyDept} onOpenChange={(o) => !o && setHistoryDept(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto" data-testid="history-dialog">
          <DialogHeader>
            <DialogTitle>Change History — {historyDept?.name}</DialogTitle>
            <DialogDescription>Every change is versioned, timestamped, and attributed.</DialogDescription>
          </DialogHeader>
          {historyLoading ? (
            <div className="py-8 text-center text-slate-400 text-sm">Loading...</div>
          ) : historyEntries.length === 0 ? (
            <div className="py-8 text-center text-slate-400 text-sm">No history yet</div>
          ) : (
            <div className="space-y-3">
              {historyEntries.map(h => (
                <div key={h.id} className="border border-slate-200 rounded-lg p-3 bg-slate-50/50">
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <Badge variant="outline" className="text-xs">v{h.version}</Badge>
                    <Badge className={`text-xs uppercase ${
                      h.action === 'updated' ? 'bg-blue-100 text-blue-700' :
                      h.action === 'merged' ? 'bg-indigo-100 text-indigo-700' :
                      h.action === 'activated' ? 'bg-emerald-100 text-emerald-700' :
                      h.action === 'deactivated' ? 'bg-amber-100 text-amber-700' :
                      'bg-slate-100 text-slate-700'
                    }`}>{h.action}</Badge>
                    <span className="text-xs text-slate-500">by <span className="font-medium text-slate-700">{h.changed_by_name || '—'}</span></span>
                    <span className="text-xs text-slate-400 ml-auto font-mono">{h.timestamp?.replace('T', ' ').slice(0, 19)}</span>
                  </div>
                  {h.reason && <p className="text-xs text-slate-600 mb-2 italic">"{h.reason}"</p>}
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-rose-50 rounded p-2">
                      <p className="font-semibold text-rose-600 mb-1">Before</p>
                      <pre className="whitespace-pre-wrap break-words text-slate-700">{h.old ? JSON.stringify(h.old, null, 1) : '—'}</pre>
                    </div>
                    <div className="bg-emerald-50 rounded p-2">
                      <p className="font-semibold text-emerald-600 mb-1">After</p>
                      <pre className="whitespace-pre-wrap break-words text-slate-700">{h.new ? JSON.stringify(h.new, null, 1) : '—'}</pre>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </HRMSLayout>
  );
};

// Reusable form fragment for Add and Edit dialogs.
const DeptForm = ({ form, setForm, employees }) => (
  <div className="space-y-3 py-2">
    <div>
      <Label className="text-sm">Name *</Label>
      <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="mt-1" data-testid="dept-name" />
    </div>
    <div>
      <Label className="text-sm">Code</Label>
      <Input value={form.code} onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))} className="mt-1 font-mono uppercase" placeholder="e.g., ADM, OPS" data-testid="dept-code" maxLength={10} />
    </div>
    <div>
      <Label className="text-sm">Description</Label>
      <Textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} className="mt-1" rows={2} data-testid="dept-description" />
    </div>
    <div>
      <Label className="text-sm">Head of Department (HOD)</Label>
      <Select value={form.hod_employee_id || 'none'} onValueChange={v => setForm(f => ({ ...f, hod_employee_id: v === 'none' ? '' : v }))}>
        <SelectTrigger className="mt-1" data-testid="dept-hod-select"><SelectValue placeholder="Select HOD (optional)" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="none">— None —</SelectItem>
          {employees.map(e => (
            <SelectItem key={e.id} value={e.id}>{e.name} {e.employee_id ? `(${e.employee_id})` : ''}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  </div>
);

export default HRMSDepartments;
