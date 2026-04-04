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
import { Upload, Save, Building2, Users, Plus, Edit, Trash2, KeyRound, Loader2, Shield, UserCircle } from 'lucide-react';
import { toast } from 'sonner';
import { formatDate } from '../lib/utils';

const ROLE_LABELS = { hr_admin: 'HR Admin', hrms_employee: 'Employee' };
const ROLE_COLORS = { hr_admin: 'bg-blue-100 text-blue-700', hrms_employee: 'bg-green-100 text-green-700' };

const HRMSSettings = () => {
  const [activeTab, setActiveTab] = useState('company');

  // Company settings
  const [settings, setSettings] = useState({ company_name: '', tagline: '', address: '', email: '', helpline: '', logo_url: '' });
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // User management
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [employees, setEmployees] = useState([]);
  const [userDialog, setUserDialog] = useState(false);
  const [userMode, setUserMode] = useState('add');
  const [selectedUser, setSelectedUser] = useState(null);
  const [userForm, setUserForm] = useState({ email: '', password: '', name: '', role: 'hrms_employee', linked_employee_id: '' });
  const [userSaving, setUserSaving] = useState(false);
  const [resetDialog, setResetDialog] = useState(null);
  const [newPassword, setNewPassword] = useState('');

  useEffect(() => { fetchSettings(); }, []);

  useEffect(() => {
    if (activeTab === 'users') {
      fetchUsers();
      fetchEmployees();
    }
  }, [activeTab]);

  const fetchSettings = async () => {
    try {
      const res = await api.get('/hrms/company-settings');
      setSettings(res.data);
    } catch (e) { console.error(e); }
    setSettingsLoading(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/hrms/company-settings', settings);
      toast.success('Company settings updated');
    } catch (e) { toast.error('Failed to update settings'); }
    setSaving(false);
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await api.post('/hrms/company-logo', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setSettings(s => ({ ...s, logo_url: res.data.logo_url }));
      toast.success('Logo uploaded');
    } catch (e) { toast.error('Failed to upload logo'); }
  };

  // User management functions
  const fetchUsers = useCallback(async () => {
    setUsersLoading(true);
    try {
      const res = await api.get('/hrms/users');
      setUsers(res.data);
    } catch (e) { toast.error('Failed to load users'); }
    setUsersLoading(false);
  }, []);

  const fetchEmployees = useCallback(async () => {
    try {
      const res = await api.get('/hrms/employees', { params: { limit: 200, status: 'active' } });
      setEmployees(res.data.employees || []);
    } catch (e) { console.error(e); }
  }, []);

  const openAddUser = () => {
    setUserMode('add');
    setUserForm({ email: '', password: '', name: '', role: 'hrms_employee', linked_employee_id: '' });
    setUserDialog(true);
  };

  const openEditUser = (u) => {
    setUserMode('edit');
    setSelectedUser(u);
    setUserForm({ email: u.email, password: '', name: u.name, role: u.role, linked_employee_id: u.linked_employee_id || '' });
    setUserDialog(true);
  };

  const handleUserSave = async () => {
    if (!userForm.email || !userForm.name || !userForm.role) {
      toast.error('Email, name, and role are required'); return;
    }
    if (userMode === 'add' && !userForm.password) {
      toast.error('Password is required for new users'); return;
    }
    setUserSaving(true);
    try {
      if (userMode === 'add') {
        await api.post('/hrms/users', userForm);
        toast.success('User created');
      } else {
        const payload = { name: userForm.name, role: userForm.role, linked_employee_id: userForm.linked_employee_id, email: userForm.email };
        await api.put(`/hrms/users/${selectedUser.id}`, payload);
        toast.success('User updated');
      }
      setUserDialog(false);
      fetchUsers();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save user');
    }
    setUserSaving(false);
  };

  const handleResetPassword = async () => {
    if (!newPassword || newPassword.length < 6) {
      toast.error('Password must be at least 6 characters'); return;
    }
    try {
      await api.post(`/hrms/users/${resetDialog}/reset-password`, { password: newPassword });
      toast.success('Password reset successfully');
      setResetDialog(null);
      setNewPassword('');
      fetchUsers();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to reset password'); }
  };

  const handleDeactivate = async (u) => {
    if (!window.confirm(`Deactivate user "${u.name}"?`)) return;
    try {
      await api.delete(`/hrms/users/${u.id}`);
      toast.success('User deactivated');
      fetchUsers();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to deactivate'); }
  };

  if (settingsLoading) {
    return <HRMSLayout><div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 animate-spin text-blue-600" /></div></HRMSLayout>;
  }

  return (
    <HRMSLayout>
      <div className="space-y-5" data-testid="hrms-settings">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Settings</h1>
          <p className="text-slate-500 text-sm">Company settings and user management</p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg w-fit">
          <button
            className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === 'company' ? 'bg-white shadow text-slate-800' : 'text-slate-500'}`}
            onClick={() => setActiveTab('company')}
            data-testid="company-settings-tab"
          >
            <Building2 className="w-4 h-4 inline mr-1" /> Company Info
          </button>
          <button
            className={`px-4 py-2 rounded-md text-sm font-medium transition ${activeTab === 'users' ? 'bg-white shadow text-slate-800' : 'text-slate-500'}`}
            onClick={() => setActiveTab('users')}
            data-testid="user-management-tab"
          >
            <Users className="w-4 h-4 inline mr-1" /> User Management
          </button>
        </div>

        {/* COMPANY TAB */}
        {activeTab === 'company' && (
          <div className="space-y-6 max-w-2xl">
            <Card>
              <CardHeader className="pb-3"><CardTitle className="text-base">Company Logo</CardTitle></CardHeader>
              <CardContent>
                <div className="flex items-center gap-6">
                  <div className="w-24 h-24 rounded-xl border-2 border-dashed border-slate-200 flex items-center justify-center overflow-hidden bg-slate-50">
                    {settings.logo_url ? <img src={settings.logo_url} alt="Logo" className="w-full h-full object-contain" /> : <Building2 className="w-8 h-8 text-slate-300" />}
                  </div>
                  <div>
                    <label className="cursor-pointer">
                      <input type="file" accept="image/*" className="hidden" onChange={handleLogoUpload} />
                      <Button variant="outline" className="gap-2" asChild><span><Upload className="w-4 h-4" /> Upload Logo</span></Button>
                    </label>
                    <p className="text-xs text-slate-400 mt-2">Max 2MB. PNG, JPG, or SVG</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3"><CardTitle className="text-base">Company Details</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div><Label>Company Name</Label><Input value={settings.company_name} onChange={e => setSettings(s => ({ ...s, company_name: e.target.value }))} data-testid="company-name" /></div>
                <div><Label>Tagline</Label><Input value={settings.tagline} onChange={e => setSettings(s => ({ ...s, tagline: e.target.value }))} data-testid="company-tagline" /></div>
                <div><Label>Address</Label><Input value={settings.address} onChange={e => setSettings(s => ({ ...s, address: e.target.value }))} data-testid="company-address" /></div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div><Label>Email</Label><Input type="email" value={settings.email} onChange={e => setSettings(s => ({ ...s, email: e.target.value }))} data-testid="company-email" /></div>
                  <div><Label>Helpline</Label><Input value={settings.helpline} onChange={e => setSettings(s => ({ ...s, helpline: e.target.value }))} data-testid="company-helpline" /></div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3"><CardTitle className="text-base">Report Header Preview</CardTitle></CardHeader>
              <CardContent>
                <div className="text-center p-6 border rounded-lg bg-white">
                  {settings.logo_url && <img src={settings.logo_url} alt="Logo" className="w-16 h-16 mx-auto mb-2 object-contain" />}
                  <h2 className="text-lg font-bold text-slate-800">{settings.company_name || 'Company Name'}</h2>
                  <p className="text-sm text-slate-500 italic">{settings.tagline || 'Tagline'}</p>
                  <p className="text-xs text-slate-400 mt-1">{settings.address || 'Address'}</p>
                  <p className="text-xs text-slate-400">{settings.email} | {settings.helpline}</p>
                </div>
              </CardContent>
            </Card>

            <div className="flex justify-end">
              <Button onClick={handleSave} disabled={saving} className="gap-2 bg-blue-600 hover:bg-blue-700" data-testid="save-settings-btn">
                <Save className="w-4 h-4" /> {saving ? 'Saving...' : 'Save Settings'}
              </Button>
            </div>
          </div>
        )}

        {/* USER MANAGEMENT TAB */}
        {activeTab === 'users' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-slate-500">Manage HR Admin and Employee login accounts</p>
              <Button onClick={openAddUser} className="gap-2 bg-blue-600 hover:bg-blue-700" data-testid="add-hrms-user-btn">
                <Plus className="w-4 h-4" /> Add User
              </Button>
            </div>

            <Card>
              <CardContent className="p-0">
                {usersLoading ? (
                  <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>
                ) : users.length === 0 ? (
                  <div className="text-center py-12 text-slate-400">
                    <Users className="w-10 h-10 mx-auto mb-3 text-slate-200" />
                    <p className="text-sm">No HRMS users yet</p>
                    <p className="text-xs mt-1">Create user accounts for HR team and employees</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-slate-50 text-left text-slate-500 text-xs">
                          <th className="p-3 font-medium">User</th>
                          <th className="p-3 font-medium">Role</th>
                          <th className="p-3 font-medium">Linked Employee</th>
                          <th className="p-3 font-medium">Password</th>
                          <th className="p-3 font-medium">Created</th>
                          <th className="p-3 font-medium">Status</th>
                          <th className="p-3 text-right font-medium">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {users.map(u => (
                          <tr key={u.id} className="border-b hover:bg-slate-50" data-testid={`user-row-${u.email}`}>
                            <td className="p-3">
                              <div className="flex items-center gap-2">
                                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-xs font-bold text-blue-700">
                                  {u.name?.charAt(0)}
                                </div>
                                <div>
                                  <p className="font-medium text-slate-700">{u.name}</p>
                                  <p className="text-xs text-slate-400">{u.email}</p>
                                </div>
                              </div>
                            </td>
                            <td className="p-3">
                              <Badge className={ROLE_COLORS[u.role] || 'bg-slate-100 text-slate-700'}>
                                {ROLE_LABELS[u.role] || u.role}
                              </Badge>
                            </td>
                            <td className="p-3">
                              {u.linked_employee_name ? (
                                <div>
                                  <p className="text-slate-700 text-xs font-medium">{u.linked_employee_name}</p>
                                  <p className="text-slate-400 text-[10px]">{u.linked_employee_code}</p>
                                </div>
                              ) : (
                                <span className="text-slate-300 text-xs">Not linked</span>
                              )}
                            </td>
                            <td className="p-3">
                              <span className="font-mono text-xs text-slate-400 bg-slate-50 px-2 py-0.5 rounded">{u.visible_password || '***'}</span>
                            </td>
                            <td className="p-3 text-xs text-slate-500">{formatDate(u.created_at)}</td>
                            <td className="p-3">
                              <Badge className={u.is_active !== false ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                                {u.is_active !== false ? 'Active' : 'Inactive'}
                              </Badge>
                            </td>
                            <td className="p-3 text-right">
                              <div className="flex items-center justify-end gap-1">
                                <Button variant="ghost" size="sm" onClick={() => openEditUser(u)} title="Edit" data-testid={`edit-user-${u.email}`}>
                                  <Edit className="w-4 h-4" />
                                </Button>
                                <Button variant="ghost" size="sm" onClick={() => { setResetDialog(u.id); setNewPassword(''); }} title="Reset Password" data-testid={`reset-pwd-${u.email}`}>
                                  <KeyRound className="w-4 h-4 text-amber-600" />
                                </Button>
                                {u.is_active !== false && (
                                  <Button variant="ghost" size="sm" onClick={() => handleDeactivate(u)} title="Deactivate" data-testid={`deactivate-${u.email}`}>
                                    <Trash2 className="w-4 h-4 text-red-500" />
                                  </Button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Info card */}
            <Card className="bg-blue-50 border-blue-200">
              <CardContent className="p-4">
                <div className="flex gap-3">
                  <Shield className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div className="text-xs text-blue-800 space-y-1">
                    <p className="font-medium">Role Permissions</p>
                    <p><strong>HR Admin</strong> — Full HRMS access: manage employees, payroll, attendance, reports, hiring, settings</p>
                    <p><strong>Employee</strong> — Self-service: view own attendance, payroll. Must be linked to an employee record.</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* Add/Edit User Dialog */}
      <Dialog open={userDialog} onOpenChange={setUserDialog}>
        <DialogContent className="max-w-md" data-testid="user-form-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <UserCircle className="w-5 h-5 text-blue-600" />
              {userMode === 'add' ? 'Create HRMS User' : 'Edit User'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Full Name *</Label>
              <Input value={userForm.name} onChange={e => setUserForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Rajesh Kumar" data-testid="user-name-input" />
            </div>
            <div>
              <Label>Email *</Label>
              <Input type="email" value={userForm.email} onChange={e => setUserForm(f => ({ ...f, email: e.target.value }))} placeholder="e.g. rajesh@k3gas.com" data-testid="user-email-input" />
            </div>
            {userMode === 'add' && (
              <div>
                <Label>Password *</Label>
                <Input type="text" value={userForm.password} onChange={e => setUserForm(f => ({ ...f, password: e.target.value }))} placeholder="Min 6 characters" data-testid="user-password-input" />
              </div>
            )}
            <div>
              <Label>Role *</Label>
              <Select value={userForm.role} onValueChange={v => setUserForm(f => ({ ...f, role: v }))}>
                <SelectTrigger data-testid="user-role-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="hr_admin">HR Admin</SelectItem>
                  <SelectItem value="hrms_employee">Employee</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Link to Employee {userForm.role === 'hrms_employee' && <span className="text-red-500">*</span>}</Label>
              <Select value={userForm.linked_employee_id || 'none'} onValueChange={v => setUserForm(f => ({ ...f, linked_employee_id: v === 'none' ? '' : v }))}>
                <SelectTrigger data-testid="user-employee-select"><SelectValue placeholder="Select employee" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">-- No link --</SelectItem>
                  {employees.map(e => (
                    <SelectItem key={e.id} value={e.id}>{e.name} ({e.employee_id})</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-[10px] text-slate-400 mt-1">Employee users must be linked to see their own attendance & payroll</p>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={() => setUserDialog(false)}>Cancel</Button>
            <Button onClick={handleUserSave} disabled={userSaving} className="bg-blue-600 hover:bg-blue-700 gap-1" data-testid="save-user-btn">
              {userSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {userSaving ? 'Saving...' : userMode === 'add' ? 'Create User' : 'Update User'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Reset Password Dialog */}
      <Dialog open={!!resetDialog} onOpenChange={() => { setResetDialog(null); setNewPassword(''); }}>
        <DialogContent className="max-w-sm" data-testid="reset-password-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-amber-600" /> Reset Password
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>New Password *</Label>
              <Input type="text" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="Min 6 characters" data-testid="new-password-input" />
            </div>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setResetDialog(null)}>Cancel</Button>
            <Button onClick={handleResetPassword} className="bg-amber-600 hover:bg-amber-700 gap-1" data-testid="confirm-reset-btn">
              <KeyRound className="w-4 h-4" /> Reset Password
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </HRMSLayout>
  );
};

export default HRMSSettings;
