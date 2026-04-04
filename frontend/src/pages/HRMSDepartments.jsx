import React, { useState, useEffect, useCallback } from 'react';
import HRMSLayout from '../components/HRMSLayout';
import api from '../lib/api';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Plus, Trash2, Building2 } from 'lucide-react';
import { toast } from 'sonner';

const HRMSDepartments = () => {
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({ name: '', description: '' });
  const [saving, setSaving] = useState(false);

  const fetchDepartments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/hrms/departments');
      setDepartments(res.data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchDepartments(); }, [fetchDepartments]);

  const handleAdd = async () => {
    if (!form.name.trim()) { toast.error('Department name is required'); return; }
    setSaving(true);
    try {
      await api.post('/hrms/departments', form);
      toast.success('Department created');
      setDialogOpen(false);
      setForm({ name: '', description: '' });
      fetchDepartments();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to create'); }
    setSaving(false);
  };

  const handleDelete = async (dept) => {
    if (!window.confirm(`Delete department "${dept.name}"?`)) return;
    try {
      await api.delete(`/hrms/departments/${dept.id}`);
      toast.success('Department deleted');
      fetchDepartments();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to delete'); }
  };

  return (
    <HRMSLayout>
      <div className="space-y-4" data-testid="hrms-departments">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Departments</h1>
            <p className="text-slate-500 text-sm">{departments.length} departments</p>
          </div>
          <Button onClick={() => setDialogOpen(true)} className="gap-2 bg-blue-600 hover:bg-blue-700" data-testid="add-department-btn">
            <Plus className="w-4 h-4" /> Add Department
          </Button>
        </div>

        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow><TableCell colSpan={4} className="text-center py-8 text-slate-400">Loading...</TableCell></TableRow>
                ) : departments.length === 0 ? (
                  <TableRow><TableCell colSpan={4} className="text-center py-8 text-slate-400">No departments yet</TableCell></TableRow>
                ) : departments.map(dept => (
                  <TableRow key={dept.id}>
                    <TableCell className="font-medium flex items-center gap-2"><Building2 className="w-4 h-4 text-blue-500" />{dept.name}</TableCell>
                    <TableCell className="text-slate-500">{dept.description || '-'}</TableCell>
                    <TableCell className="text-slate-400 text-sm">{dept.created_at?.split('T')[0]}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => handleDelete(dept)} data-testid={`delete-dept-${dept.name}`}>
                        <Trash2 className="w-4 h-4 text-red-500" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md" data-testid="add-department-dialog">
          <DialogHeader><DialogTitle>Add Department</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div><Label>Name *</Label><Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} data-testid="dept-name" /></div>
            <div><Label>Description</Label><Input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} /></div>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleAdd} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="save-dept-btn">{saving ? 'Saving...' : 'Add Department'}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </HRMSLayout>
  );
};

export default HRMSDepartments;
