import React, { useState, useEffect, useCallback } from 'react';
import HRMSLayout from '../components/HRMSLayout';
import api from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Plus, Search, Edit, Trash2, Eye, Upload, ChevronLeft, ChevronRight, UserCircle, IndianRupee, History, Download, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { formatINR } from '../lib/utils';

const emptyForm = {
  name: '', email: '', phone: '', date_of_birth: '', gender: '', address: '',
  department_id: '', designation: '', date_of_joining: '', employment_type: 'full_time',
  basic_salary: '', hra: '', da: '', other_allowances: '',
  pf_number: '', esi_number: '', pan_number: '', aadhar_number: '',
  bank_name: '', bank_account_no: '', ifsc_code: '',
  emergency_contact_name: '', emergency_contact_phone: '',
};

const EmployeeManagement = () => {
  const [employees, setEmployees] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterDept, setFilterDept] = useState('all');
  const [filterStatus, setFilterStatus] = useState('active');

  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState('add');
  const [form, setForm] = useState({ ...emptyForm });
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [incrementDialogOpen, setIncrementDialogOpen] = useState(false);
  const [incrementForm, setIncrementForm] = useState({ new_salary: '', reason: '', date: '' });
  const [saving, setSaving] = useState(false);

  const fetchDepartments = useCallback(async () => {
    try {
      const res = await api.get('/hrms/departments');
      setDepartments(res.data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchEmployees = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, limit: 15 };
      if (search) params.search = search;
      if (filterDept !== 'all') params.department_id = filterDept;
      if (filterStatus !== 'all') params.status = filterStatus;
      const res = await api.get('/hrms/employees', { params });
      setEmployees(res.data.employees);
      setTotal(res.data.total);
      setTotalPages(res.data.total_pages);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [page, search, filterDept, filterStatus]);

  useEffect(() => { fetchDepartments(); }, [fetchDepartments]);
  useEffect(() => { fetchEmployees(); }, [fetchEmployees]);

  useEffect(() => {
    const timer = setTimeout(() => { setPage(1); }, 300);
    return () => clearTimeout(timer);
  }, [search, filterDept, filterStatus]);

  const openAdd = () => { setDialogMode('add'); setForm({ ...emptyForm }); setDialogOpen(true); };
  const openEdit = (emp) => {
    setDialogMode('edit');
    setSelectedEmployee(emp);
    setForm({
      name: emp.name || '', email: emp.email || '', phone: emp.phone || '',
      date_of_birth: emp.date_of_birth || '', gender: emp.gender || '', address: emp.address || '',
      department_id: emp.department_id || '', designation: emp.designation || '',
      date_of_joining: emp.date_of_joining || '', employment_type: emp.employment_type || 'full_time',
      basic_salary: emp.basic_salary || '', hra: emp.hra || '', da: emp.da || '',
      other_allowances: emp.other_allowances || '', pf_number: emp.pf_number || '',
      esi_number: emp.esi_number || '', pan_number: emp.pan_number || '', aadhar_number: emp.aadhar_number || '',
      bank_name: emp.bank_name || '', bank_account_no: emp.bank_account_no || '', ifsc_code: emp.ifsc_code || '',
      emergency_contact_name: emp.emergency_contact_name || '', emergency_contact_phone: emp.emergency_contact_phone || '',
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name || !form.email || !form.phone || !form.department_id || !form.designation || !form.date_of_joining) {
      toast.error('Please fill all required fields');
      return;
    }
    setSaving(true);
    try {
      if (dialogMode === 'add') {
        await api.post('/hrms/employees', form);
        toast.success('Employee added');
      } else {
        await api.put(`/hrms/employees/${selectedEmployee.id}`, form);
        toast.success('Employee updated');
      }
      setDialogOpen(false);
      fetchEmployees();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    }
    setSaving(false);
  };

  const handleDelete = async (emp) => {
    if (!window.confirm(`Deactivate ${emp.name}?`)) return;
    try {
      await api.delete(`/hrms/employees/${emp.id}`);
      toast.success('Employee deactivated');
      fetchEmployees();
    } catch (e) { toast.error('Failed to deactivate'); }
  };

  const handleView = async (emp) => {
    try {
      const res = await api.get(`/hrms/employees/${emp.id}`);
      setSelectedEmployee(res.data);
      setViewDialogOpen(true);
    } catch (e) { toast.error('Failed to load employee details'); }
  };

  const handlePhotoUpload = async (emp, file) => {
    const fd = new FormData();
    fd.append('file', file);
    try {
      await api.post(`/hrms/employees/${emp.id}/photo`, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      toast.success('Photo uploaded');
      fetchEmployees();
    } catch (e) { toast.error('Failed to upload photo'); }
  };

  const openIncrement = (emp) => {
    setSelectedEmployee(emp);
    setIncrementForm({ new_salary: '', reason: '', date: new Date().toISOString().split('T')[0] });
    setIncrementDialogOpen(true);
  };

  const handleIncrement = async () => {
    if (!incrementForm.new_salary) { toast.error('Enter new salary'); return; }
    try {
      await api.post(`/hrms/employees/${selectedEmployee.id}/increment`, incrementForm);
      toast.success('Increment added');
      setIncrementDialogOpen(false);
      fetchEmployees();
    } catch (e) { toast.error('Failed to add increment'); }
  };

  const updateField = (field, value) => setForm(f => ({ ...f, [field]: value }));

  const downloadReport = async (format) => {
    try {
      const params = {};
      if (filterDept !== 'all') params.department_id = filterDept;
      if (filterStatus !== 'all') params.status = filterStatus;
      const res = await api.get(`/hrms/reports/employees/${format}`, { params, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = `Employee_Directory.${format === 'pdf' ? 'pdf' : 'xlsx'}`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (e) { toast.error(`Failed to export ${format.toUpperCase()}`); }
  };

  return (
    <HRMSLayout>
      <div className="space-y-4" data-testid="employee-management">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Employees</h1>
            <p className="text-slate-500 text-sm">{total} total employees</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => downloadReport('pdf')} data-testid="export-employees-pdf"><FileText className="w-4 h-4 mr-1" /> PDF</Button>
            <Button variant="outline" size="sm" onClick={() => downloadReport('excel')} data-testid="export-employees-excel"><Download className="w-4 h-4 mr-1" /> Excel</Button>
            <Button onClick={openAdd} className="gap-2 bg-blue-600 hover:bg-blue-700" data-testid="add-employee-btn">
              <Plus className="w-4 h-4" /> Add Employee
            </Button>
          </div>
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="p-4 flex flex-col sm:flex-row gap-3 items-end">
            <div className="flex-1">
              <Label className="text-xs">Search</Label>
              <div className="relative mt-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Name, ID, email, phone..." className="pl-9" data-testid="employee-search" />
              </div>
            </div>
            <div>
              <Label className="text-xs">Department</Label>
              <Select value={filterDept} onValueChange={setFilterDept}>
                <SelectTrigger className="w-40 mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Departments</SelectItem>
                  {departments.map(d => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">Status</Label>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="w-32 mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Table */}
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12"></TableHead>
                    <TableHead>Employee ID</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Department</TableHead>
                    <TableHead>Designation</TableHead>
                    <TableHead>Phone</TableHead>
                    <TableHead>Joining Date</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow><TableCell colSpan={9} className="text-center py-8 text-slate-400">Loading...</TableCell></TableRow>
                  ) : employees.length === 0 ? (
                    <TableRow><TableCell colSpan={9} className="text-center py-8 text-slate-400">No employees found</TableCell></TableRow>
                  ) : employees.map(emp => (
                    <TableRow key={emp.id} className="hover:bg-slate-50">
                      <TableCell>
                        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-xs font-bold text-blue-700 overflow-hidden">
                          {emp.photo_url ? <img src={emp.photo_url} alt="" className="w-full h-full object-cover" /> : emp.name?.charAt(0)}
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{emp.employee_id}</TableCell>
                      <TableCell className="font-medium">{emp.name}</TableCell>
                      <TableCell>{emp.department_name}</TableCell>
                      <TableCell>{emp.designation}</TableCell>
                      <TableCell>{emp.phone}</TableCell>
                      <TableCell>{emp.date_of_joining}</TableCell>
                      <TableCell>
                        <Badge variant={emp.is_active ? 'default' : 'secondary'} className={emp.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                          {emp.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="sm" onClick={() => handleView(emp)} title="View" data-testid={`view-${emp.employee_id}`}>
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => openEdit(emp)} title="Edit" data-testid={`edit-${emp.employee_id}`}>
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => openIncrement(emp)} title="Increment" data-testid={`increment-${emp.employee_id}`}>
                            <IndianRupee className="w-4 h-4" />
                          </Button>
                          <label className="cursor-pointer" title="Upload Photo">
                            <input type="file" accept="image/*" className="hidden" onChange={e => e.target.files[0] && handlePhotoUpload(emp, e.target.files[0])} />
                            <Upload className="w-4 h-4 text-slate-400 hover:text-slate-700" />
                          </label>
                          {emp.is_active && (
                            <Button variant="ghost" size="sm" onClick={() => handleDelete(emp)} title="Deactivate" data-testid={`delete-${emp.employee_id}`}>
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t">
                <span className="text-sm text-slate-500">Page {page} of {totalPages} ({total} total)</span>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="w-4 h-4" /></Button>
                  <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}><ChevronRight className="w-4 h-4" /></Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Add/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="employee-form-dialog">
          <DialogHeader>
            <DialogTitle>{dialogMode === 'add' ? 'Add New Employee' : 'Edit Employee'}</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 py-2">
            <h3 className="col-span-full text-sm font-semibold text-slate-500 uppercase tracking-wider border-b pb-1">Personal Information</h3>
            <div><Label>Name *</Label><Input value={form.name} onChange={e => updateField('name', e.target.value)} data-testid="emp-name" /></div>
            <div><Label>Email *</Label><Input type="email" value={form.email} onChange={e => updateField('email', e.target.value)} data-testid="emp-email" /></div>
            <div><Label>Phone *</Label><Input value={form.phone} onChange={e => updateField('phone', e.target.value)} data-testid="emp-phone" /></div>
            <div><Label>Date of Birth</Label><Input type="date" value={form.date_of_birth} onChange={e => updateField('date_of_birth', e.target.value)} /></div>
            <div>
              <Label>Gender</Label>
              <Select value={form.gender} onValueChange={v => updateField('gender', v)}>
                <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="male">Male</SelectItem>
                  <SelectItem value="female">Female</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="md:col-span-2"><Label>Address</Label><Input value={form.address} onChange={e => updateField('address', e.target.value)} /></div>

            <h3 className="col-span-full text-sm font-semibold text-slate-500 uppercase tracking-wider border-b pb-1 mt-2">Job Details</h3>
            <div>
              <Label>Department *</Label>
              <Select value={form.department_id} onValueChange={v => updateField('department_id', v)}>
                <SelectTrigger data-testid="emp-department"><SelectValue placeholder="Select" /></SelectTrigger>
                <SelectContent>{departments.map(d => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Designation *</Label><Input value={form.designation} onChange={e => updateField('designation', e.target.value)} data-testid="emp-designation" /></div>
            <div><Label>Date of Joining *</Label><Input type="date" value={form.date_of_joining} onChange={e => updateField('date_of_joining', e.target.value)} data-testid="emp-doj" /></div>
            <div>
              <Label>Employment Type</Label>
              <Select value={form.employment_type} onValueChange={v => updateField('employment_type', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="full_time">Full Time</SelectItem>
                  <SelectItem value="part_time">Part Time</SelectItem>
                  <SelectItem value="contract">Contract</SelectItem>
                  <SelectItem value="intern">Intern</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <h3 className="col-span-full text-sm font-semibold text-slate-500 uppercase tracking-wider border-b pb-1 mt-2">Salary Structure</h3>
            <div><Label>Basic Salary</Label><Input type="number" value={form.basic_salary} onChange={e => updateField('basic_salary', e.target.value)} data-testid="emp-basic-salary" /></div>
            <div><Label>HRA</Label><Input type="number" value={form.hra} onChange={e => updateField('hra', e.target.value)} /></div>
            <div><Label>DA</Label><Input type="number" value={form.da} onChange={e => updateField('da', e.target.value)} /></div>
            <div><Label>Other Allowances</Label><Input type="number" value={form.other_allowances} onChange={e => updateField('other_allowances', e.target.value)} /></div>

            <h3 className="col-span-full text-sm font-semibold text-slate-500 uppercase tracking-wider border-b pb-1 mt-2">Statutory & Banking</h3>
            <div><Label>PF Number</Label><Input value={form.pf_number} onChange={e => updateField('pf_number', e.target.value)} /></div>
            <div><Label>ESI Number</Label><Input value={form.esi_number} onChange={e => updateField('esi_number', e.target.value)} /></div>
            <div><Label>PAN Number</Label><Input value={form.pan_number} onChange={e => updateField('pan_number', e.target.value)} /></div>
            <div><Label>Aadhar Number</Label><Input value={form.aadhar_number} onChange={e => updateField('aadhar_number', e.target.value)} /></div>
            <div><Label>Bank Name</Label><Input value={form.bank_name} onChange={e => updateField('bank_name', e.target.value)} /></div>
            <div><Label>Account Number</Label><Input value={form.bank_account_no} onChange={e => updateField('bank_account_no', e.target.value)} /></div>
            <div><Label>IFSC Code</Label><Input value={form.ifsc_code} onChange={e => updateField('ifsc_code', e.target.value)} /></div>

            <h3 className="col-span-full text-sm font-semibold text-slate-500 uppercase tracking-wider border-b pb-1 mt-2">Emergency Contact</h3>
            <div><Label>Contact Name</Label><Input value={form.emergency_contact_name} onChange={e => updateField('emergency_contact_name', e.target.value)} /></div>
            <div><Label>Contact Phone</Label><Input value={form.emergency_contact_phone} onChange={e => updateField('emergency_contact_phone', e.target.value)} /></div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="save-employee-btn">
              {saving ? 'Saving...' : dialogMode === 'add' ? 'Add Employee' : 'Update Employee'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* View Dialog */}
      <Dialog open={viewDialogOpen} onOpenChange={setViewDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="employee-view-dialog">
          <DialogHeader>
            <DialogTitle>Employee Details</DialogTitle>
          </DialogHeader>
          {selectedEmployee && (
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="w-20 h-20 rounded-full bg-blue-100 flex items-center justify-center text-2xl font-bold text-blue-700 overflow-hidden flex-shrink-0">
                  {selectedEmployee.photo_url ? <img src={selectedEmployee.photo_url} alt="" className="w-full h-full object-cover" /> : selectedEmployee.name?.charAt(0)}
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-800">{selectedEmployee.name}</h3>
                  <p className="text-slate-500">{selectedEmployee.designation} &middot; {selectedEmployee.department_name}</p>
                  <Badge className="mt-1">{selectedEmployee.employee_id}</Badge>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                {[
                  ['Email', selectedEmployee.email], ['Phone', selectedEmployee.phone],
                  ['DOB', selectedEmployee.date_of_birth], ['Gender', selectedEmployee.gender],
                  ['Address', selectedEmployee.address], ['Joining Date', selectedEmployee.date_of_joining],
                  ['Type', selectedEmployee.employment_type], ['Basic Salary', `Rs.${selectedEmployee.basic_salary}`],
                  ['HRA', `Rs.${selectedEmployee.hra}`], ['DA', `Rs.${selectedEmployee.da}`],
                  ['PF No.', selectedEmployee.pf_number], ['ESI No.', selectedEmployee.esi_number],
                  ['PAN', selectedEmployee.pan_number], ['Aadhar', selectedEmployee.aadhar_number],
                  ['Bank', selectedEmployee.bank_name], ['Account', selectedEmployee.bank_account_no],
                ].map(([label, val], i) => val ? (
                  <div key={i}><span className="text-slate-400">{label}:</span> <span className="font-medium text-slate-700">{val}</span></div>
                ) : null)}
              </div>
              {selectedEmployee.increment_history?.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-slate-600 flex items-center gap-2 mb-2"><History className="w-4 h-4" /> Increment History</h4>
                  <div className="space-y-2">
                    {selectedEmployee.increment_history.map((inc, i) => (
                      <div key={i} className="flex items-center justify-between text-sm bg-slate-50 p-2 rounded">
                        <span>{inc.date}</span>
                        <span>Rs.{inc.previous_salary} &rarr; Rs.{inc.new_salary}</span>
                        <span className="text-green-600 font-medium">+Rs.{inc.increment_amount}</span>
                        <span className="text-slate-400 text-xs">{inc.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Certificates & Documents */}
              <div className="border-t pt-3">
                <h4 className="text-sm font-semibold text-slate-600 flex items-center gap-2 mb-3"><FileText className="w-4 h-4" /> Certificates & Documents</h4>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" className="text-xs gap-1" onClick={() => {
                    api.get(`/hrms/certificates/salary/${selectedEmployee.id}/pdf`, { responseType: 'blob' })
                      .then(r => { const u = window.URL.createObjectURL(new Blob([r.data])); const a = document.createElement('a'); a.href = u; a.download = `Salary_Certificate_${selectedEmployee.name.replace(/\s/g, '_')}.pdf`; a.click(); })
                      .catch(() => toast.error('Failed'));
                  }} data-testid="salary-cert-btn"><Download className="w-3 h-3" /> Salary Certificate</Button>
                  <Button variant="outline" size="sm" className="text-xs gap-1" onClick={() => {
                    api.get(`/hrms/certificates/experience/${selectedEmployee.id}/pdf`, { responseType: 'blob' })
                      .then(r => { const u = window.URL.createObjectURL(new Blob([r.data])); const a = document.createElement('a'); a.href = u; a.download = `Experience_Certificate_${selectedEmployee.name.replace(/\s/g, '_')}.pdf`; a.click(); })
                      .catch(() => toast.error('Failed'));
                  }} data-testid="exp-cert-btn"><Download className="w-3 h-3" /> Experience Certificate</Button>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Increment Dialog */}
      <Dialog open={incrementDialogOpen} onOpenChange={setIncrementDialogOpen}>
        <DialogContent className="max-w-md" data-testid="increment-dialog">
          <DialogHeader>
            <DialogTitle>Add Salary Increment</DialogTitle>
          </DialogHeader>
          {selectedEmployee && (
            <div className="space-y-4">
              <p className="text-sm text-slate-500">Current Salary: <span className="font-bold text-slate-700">Rs.{selectedEmployee.basic_salary}</span></p>
              <div><Label>New Basic Salary *</Label><Input type="number" value={incrementForm.new_salary} onChange={e => setIncrementForm(f => ({ ...f, new_salary: e.target.value }))} data-testid="increment-salary" /></div>
              <div><Label>Effective Date</Label><Input type="date" value={incrementForm.date} onChange={e => setIncrementForm(f => ({ ...f, date: e.target.value }))} /></div>
              <div><Label>Reason</Label><Input value={incrementForm.reason} onChange={e => setIncrementForm(f => ({ ...f, reason: e.target.value }))} placeholder="e.g. Annual appraisal" /></div>
              <div className="flex justify-end gap-3">
                <Button variant="outline" onClick={() => setIncrementDialogOpen(false)}>Cancel</Button>
                <Button onClick={handleIncrement} className="bg-blue-600 hover:bg-blue-700" data-testid="save-increment-btn">Add Increment</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </HRMSLayout>
  );
};

export default EmployeeManagement;
