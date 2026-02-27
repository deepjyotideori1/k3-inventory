import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { getUsers, createUser, deleteUser, getWarehouses, changePassword, resetUserPassword } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { 
  Users,
  Plus,
  Trash2,
  Loader2,
  Shield,
  Warehouse,
  Key,
  RefreshCw,
  Eye,
  EyeOff,
  Copy,
  Check
} from 'lucide-react';
import { formatDate } from '../lib/utils';
import { toast } from 'sonner';

const UsersPage = () => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [showResetDialog, setShowResetDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [showPasswords, setShowPasswords] = useState({});
  const [copiedId, setCopiedId] = useState(null);

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: '',
    role: 'warehouse_manager',
    warehouse_id: ''
  });

  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });

  const [resetPasswordForm, setResetPasswordForm] = useState({
    new_password: '',
    auto_generate: true
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [usersRes, warehousesRes] = await Promise.all([
        getUsers(),
        getWarehouses()
      ]);
      setUsers(usersRes.data);
      setWarehouses(warehousesRes.data);
    } catch (error) {
      console.error('Failed to fetch data:', error);
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const handleAddUser = async () => {
    if (!formData.email || !formData.password || !formData.name) {
      toast.error('Please fill in all required fields');
      return;
    }
    if (formData.role === 'warehouse_manager' && !formData.warehouse_id) {
      toast.error('Please select a warehouse for the manager');
      return;
    }
    
    setSubmitting(true);
    try {
      await createUser(formData);
      toast.success('User created successfully');
      setShowAddDialog(false);
      setFormData({ email: '', password: '', name: '', role: 'warehouse_manager', warehouse_id: '' });
      fetchData();
    } catch (error) {
      console.error('Failed to create user:', error);
      toast.error(error.response?.data?.detail || 'Failed to create user');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteUser = async (user) => {
    if (user.id === currentUser?.id) {
      toast.error('You cannot delete your own account');
      return;
    }
    if (!window.confirm(`Are you sure you want to delete ${user.name}?`)) return;
    
    try {
      await deleteUser(user.id);
      toast.success('User deleted successfully');
      fetchData();
    } catch (error) {
      console.error('Failed to delete user:', error);
      toast.error('Failed to delete user');
    }
  };

  const handleChangePassword = async () => {
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast.error('New passwords do not match');
      return;
    }
    if (passwordForm.new_password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }
    
    setSubmitting(true);
    try {
      await changePassword(passwordForm.current_password, passwordForm.new_password);
      toast.success('Password changed successfully');
      setShowPasswordDialog(false);
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
    } catch (error) {
      console.error('Failed to change password:', error);
      toast.error(error.response?.data?.detail || 'Failed to change password');
    } finally {
      setSubmitting(false);
    }
  };

  const handleResetPassword = async () => {
    if (!selectedUser) return;
    
    if (!resetPasswordForm.auto_generate && resetPasswordForm.new_password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }
    
    setSubmitting(true);
    try {
      const newPassword = resetPasswordForm.auto_generate ? null : resetPasswordForm.new_password;
      const response = await resetUserPassword(selectedUser.id, newPassword);
      toast.success(`Password reset successfully! New password: ${response.data.new_password}`);
      setShowResetDialog(false);
      setSelectedUser(null);
      setResetPasswordForm({ new_password: '', auto_generate: true });
      fetchData();
    } catch (error) {
      console.error('Failed to reset password:', error);
      toast.error(error.response?.data?.detail || 'Failed to reset password');
    } finally {
      setSubmitting(false);
    }
  };

  const openResetDialog = (user) => {
    setSelectedUser(user);
    setResetPasswordForm({ new_password: '', auto_generate: true });
    setShowResetDialog(true);
  };

  const togglePasswordVisibility = (userId) => {
    setShowPasswords(prev => ({
      ...prev,
      [userId]: !prev[userId]
    }));
  };

  const copyToClipboard = async (text, userId) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(userId);
      toast.success('Password copied to clipboard');
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      toast.error('Failed to copy');
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-green-700" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6" data-testid="users-page">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-800 flex items-center gap-2">
              <Users className="w-8 h-8 text-green-700" />
              User Management
            </h1>
            <p className="text-slate-500 mt-1">Manage user accounts and permissions</p>
          </div>
          <div className="flex gap-2">
            <Dialog open={showPasswordDialog} onOpenChange={setShowPasswordDialog}>
              <DialogTrigger asChild>
                <Button variant="outline" className="gap-2" data-testid="change-password-btn">
                  <Key className="w-4 h-4" />
                  Change My Password
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Change Password</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div>
                    <Label>Current Password</Label>
                    <Input 
                      type="password"
                      value={passwordForm.current_password}
                      onChange={(e) => setPasswordForm(prev => ({ ...prev, current_password: e.target.value }))}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label>New Password</Label>
                    <Input 
                      type="password"
                      value={passwordForm.new_password}
                      onChange={(e) => setPasswordForm(prev => ({ ...prev, new_password: e.target.value }))}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label>Confirm New Password</Label>
                    <Input 
                      type="password"
                      value={passwordForm.confirm_password}
                      onChange={(e) => setPasswordForm(prev => ({ ...prev, confirm_password: e.target.value }))}
                      className="mt-1"
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowPasswordDialog(false)}>Cancel</Button>
                    <Button onClick={handleChangePassword} disabled={submitting} className="bg-green-700 hover:bg-green-800">
                      {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Change Password'}
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>

            <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
              <DialogTrigger asChild>
                <Button className="bg-green-700 hover:bg-green-800 gap-2" data-testid="add-user-btn">
                  <Plus className="w-4 h-4" />
                  Add User
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add New User</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div>
                    <Label>Name *</Label>
                    <Input 
                      value={formData.name}
                      onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Enter full name"
                      className="mt-1"
                      data-testid="user-name-input"
                    />
                  </div>
                  <div>
                    <Label>Email *</Label>
                    <Input 
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                      placeholder="Enter email address"
                      className="mt-1"
                      data-testid="user-email-input"
                    />
                  </div>
                  <div>
                    <Label>Password *</Label>
                    <Input 
                      type="password"
                      value={formData.password}
                      onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
                      placeholder="Enter password"
                      className="mt-1"
                      data-testid="user-password-input"
                    />
                  </div>
                  <div>
                    <Label>Role</Label>
                    <Select 
                      value={formData.role} 
                      onValueChange={(val) => setFormData(prev => ({ ...prev, role: val }))}
                    >
                      <SelectTrigger className="mt-1" data-testid="user-role-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="admin">Admin</SelectItem>
                        <SelectItem value="warehouse_manager">Warehouse Manager</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {formData.role === 'warehouse_manager' && (
                    <div>
                      <Label>Warehouse *</Label>
                      <Select 
                        value={formData.warehouse_id} 
                        onValueChange={(val) => setFormData(prev => ({ ...prev, warehouse_id: val }))}
                      >
                        <SelectTrigger className="mt-1" data-testid="user-warehouse-select">
                          <SelectValue placeholder="Select warehouse" />
                        </SelectTrigger>
                        <SelectContent>
                          {warehouses.map(w => (
                            <SelectItem key={w.id} value={w.id}>{w.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setShowAddDialog(false)}>Cancel</Button>
                    <Button onClick={handleAddUser} disabled={submitting} className="bg-green-700 hover:bg-green-800" data-testid="save-user-btn">
                      {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create User'}
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Reset Password Dialog */}
        <Dialog open={showResetDialog} onOpenChange={setShowResetDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <RefreshCw className="w-5 h-5 text-orange-600" />
                Reset Password for {selectedUser?.name}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                <p className="text-sm text-amber-800">
                  <strong>Email:</strong> {selectedUser?.email}
                </p>
              </div>
              
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="autoGenerate"
                  checked={resetPasswordForm.auto_generate}
                  onChange={(e) => setResetPasswordForm(prev => ({ ...prev, auto_generate: e.target.checked }))}
                  className="w-4 h-4"
                />
                <Label htmlFor="autoGenerate">Auto-generate password (Name@123 format)</Label>
              </div>
              
              {!resetPasswordForm.auto_generate && (
                <div>
                  <Label>New Password *</Label>
                  <Input 
                    type="text"
                    value={resetPasswordForm.new_password}
                    onChange={(e) => setResetPasswordForm(prev => ({ ...prev, new_password: e.target.value }))}
                    placeholder="Enter new password"
                    className="mt-1"
                  />
                </div>
              )}
              
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowResetDialog(false)}>Cancel</Button>
                <Button 
                  onClick={handleResetPassword} 
                  disabled={submitting} 
                  className="bg-orange-600 hover:bg-orange-700 gap-2"
                >
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <><RefreshCw className="w-4 h-4" /> Reset Password</>}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Users List */}
        <Card data-testid="users-list-card">
          <CardHeader>
            <CardTitle className="text-lg flex items-center justify-between">
              <span>All Users</span>
              <Badge variant="outline" className="text-green-700 border-green-700">
                {users.length} users
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Password</th>
                    <th>Role</th>
                    <th>Warehouse</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id} data-testid={`user-row-${user.id}`}>
                      <td className="font-medium">{user.name}</td>
                      <td>{user.email}</td>
                      <td>
                        {user.visible_password ? (
                          <div className="flex items-center gap-2">
                            <code className="px-2 py-1 bg-slate-100 rounded text-sm font-mono">
                              {showPasswords[user.id] ? user.visible_password : '••••••••'}
                            </code>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="h-7 w-7"
                              onClick={() => togglePasswordVisibility(user.id)}
                            >
                              {showPasswords[user.id] ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="h-7 w-7"
                              onClick={() => copyToClipboard(user.visible_password, user.id)}
                            >
                              {copiedId === user.id ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
                            </Button>
                          </div>
                        ) : (
                          <span className="text-slate-400 text-sm italic">Not set</span>
                        )}
                      </td>
                      <td>
                        <Badge className={user.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}>
                          {user.role === 'admin' ? (
                            <><Shield className="w-3 h-3 mr-1" /> Admin</>
                          ) : (
                            <><Warehouse className="w-3 h-3 mr-1" /> Manager</>
                          )}
                        </Badge>
                      </td>
                      <td>{user.warehouse_name || '-'}</td>
                      <td className="text-slate-500 text-sm">{formatDate(user.created_at)}</td>
                      <td>
                        <div className="flex items-center gap-1">
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={() => openResetDialog(user)}
                            title="Reset Password"
                            className="text-orange-600 hover:text-orange-700 hover:bg-orange-50"
                          >
                            <RefreshCw className="w-4 h-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="icon" 
                            onClick={() => handleDeleteUser(user)}
                            disabled={user.id === currentUser?.id}
                            title="Delete User"
                          >
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Default Credentials Info */}
        <Card data-testid="credentials-info-card">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Key className="w-5 h-5 text-amber-600" />
              Default Credentials Reference
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                <p className="font-medium text-purple-800">Master Admin</p>
                <p className="text-sm text-purple-600 font-mono mt-1">admin@k3gas.com</p>
                <p className="text-sm text-purple-600 font-mono">Admin@123</p>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                <p className="font-medium text-blue-800">Jullang Manager</p>
                <p className="text-sm text-blue-600 font-mono mt-1">jullang@k3gas.com</p>
                <p className="text-sm text-blue-600 font-mono">Jullang@123</p>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                <p className="font-medium text-blue-800">Naharlagun Manager</p>
                <p className="text-sm text-blue-600 font-mono mt-1">naharlagun@k3gas.com</p>
                <p className="text-sm text-blue-600 font-mono">Naharlagun@123</p>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                <p className="font-medium text-blue-800">Doimukh Manager</p>
                <p className="text-sm text-blue-600 font-mono mt-1">doimukh@k3gas.com</p>
                <p className="text-sm text-blue-600 font-mono">Doimukh@123</p>
              </div>
              <div className="p-4 bg-amber-50 rounded-lg border border-amber-200">
                <p className="font-medium text-amber-800">Plant Hollongi Manager</p>
                <p className="text-sm text-amber-600 font-mono mt-1">hollongi@k3gas.com</p>
                <p className="text-sm text-amber-600 font-mono">Hollongi@123</p>
              </div>
            </div>
            <p className="text-sm text-slate-500 mt-4 flex items-center gap-2">
              <Shield className="w-4 h-4" />
              Use the Reset Password button to regenerate passwords for any user. The new password will be displayed in the table above.
            </p>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default UsersPage;
