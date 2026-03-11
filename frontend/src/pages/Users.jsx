import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { getUsers, createUser, deleteUser, getWarehouses, changePassword } from '../lib/api';
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
  Key
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
  const [submitting, setSubmitting] = useState(false);

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

        {/* Users List */}
        <Card data-testid="users-list-card">
          <CardHeader>
            <CardTitle className="text-lg">All Users</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
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
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          onClick={() => handleDeleteUser(user)}
                          disabled={user.id === currentUser?.id}
                        >
                          <Trash2 className="w-4 h-4 text-red-500" />
                        </Button>
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
            <CardTitle className="text-lg">Default Credentials</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-purple-50 rounded-lg">
                <p className="font-medium text-purple-800">Master Admin</p>
                <p className="text-sm text-purple-600">admin@k3gas.com / Admin@123</p>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg">
                <p className="font-medium text-blue-800">Jullang Manager</p>
                <p className="text-sm text-blue-600">jullang@k3gas.com / Jullang@123</p>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg">
                <p className="font-medium text-blue-800">Naharlagun Manager</p>
                <p className="text-sm text-blue-600">naharlagun@k3gas.com / Naharlagun@123</p>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg">
                <p className="font-medium text-blue-800">Doimukh Manager</p>
                <p className="text-sm text-blue-600">doimukh@k3gas.com / Doimukh@123</p>
              </div>
              <div className="p-4 bg-amber-50 rounded-lg">
                <p className="font-medium text-amber-800">Plant Hollongi Manager</p>
                <p className="text-sm text-amber-600">hollongi@k3gas.com / Hollongi@123</p>
              </div>
            </div>
            <p className="text-sm text-slate-500 mt-4">
              Note: Please change these default passwords after first login for security.
            </p>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
};

export default UsersPage;
