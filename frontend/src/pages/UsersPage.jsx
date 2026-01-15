import React, { useEffect, useState } from 'react';
import { SuperAdminLayout } from '../components/layout/SuperAdminLayout';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import axios from 'axios';
import { toast } from 'sonner';
import { showApiError } from '../lib/api';
import { Users as UsersIcon, Mail, Shield, Plus, Pencil, Trash2 } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [userToDelete, setUserToDelete] = useState(null);
  const [saving, setSaving] = useState(false);

  const [formData, setFormData] = useState({
    email: '',
    full_name: '',
    password: '',
    role: 'tenant_user',
    tenant_id: '',
  });

  useEffect(() => {
    fetchUsers();
    fetchTenants();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/users`);
      setUsers(response.data.data || []);
    } catch (error) {
      showApiError(error, 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const fetchTenants = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/tenants`);
      setTenants(response.data.data || []);
    } catch (error) {
      showApiError(error, 'Failed to load tenants');
    }
  };

  const openCreateModal = () => {
    setEditingUser(null);
    setFormData({
      email: '',
      full_name: '',
      password: '',
      role: 'tenant_user',
      tenant_id: '',
    });
    setModalOpen(true);
  };

  const openEditModal = (user) => {
    setEditingUser(user);
    setFormData({
      email: user.email,
      full_name: user.full_name,
      password: '',
      role: user.role,
      tenant_id: user.tenant_id || '',
    });
    setModalOpen(true);
  };

  const openDeleteModal = (user) => {
    setUserToDelete(user);
    setDeleteModalOpen(true);
  };

  const handleSave = async () => {
    if (!formData.email || !formData.full_name) {
      toast.error('Email and name are required');
      return;
    }
    if (!editingUser && !formData.password) {
      toast.error('Password is required for new users');
      return;
    }

    setSaving(true);
    try {
      if (editingUser) {
        const updateData = { ...formData };
        if (!updateData.password) delete updateData.password;
        await axios.put(`${API_URL}/api/users/${editingUser.id}`, updateData);
        toast.success('User updated successfully');
      } else {
        await axios.post(`${API_URL}/api/users`, formData);
        toast.success('User created successfully');
      }
      setModalOpen(false);
      fetchUsers();
    } catch (error) {
      showApiError(error, 'Failed to save user');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!userToDelete) return;
    setSaving(true);
    try {
      await axios.delete(`${API_URL}/api/users/${userToDelete.id}`);
      toast.success('User deleted successfully');
      setDeleteModalOpen(false);
      setUserToDelete(null);
      fetchUsers();
    } catch (error) {
      showApiError(error, 'Failed to delete user');
    } finally {
      setSaving(false);
    }
  };

  const getRoleBadgeColor = (role) => {
    if (role === 'super_admin') return 'bg-[hsl(var(--accent-danger))]';
    if (role === 'tenant_admin') return 'bg-[hsl(var(--primary))]';
    return 'bg-[hsl(var(--foreground-muted))]';
  };

  const getTenantName = (tenantId) => {
    const tenant = tenants.find(t => t.id === tenantId);
    return tenant?.name || tenantId?.slice(0, 8) + '...';
  };

  return (
    <SuperAdminLayout>
      <div className="p-6 md:p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
              User Management
            </h1>
            <p className="text-[hsl(var(--foreground-secondary))] mt-1">
              View and manage all platform users
            </p>
          </div>
          <Button onClick={openCreateModal} className="gap-2">
            <Plus className="h-4 w-4" />
            Add User
          </Button>
        </div>

        {/* Users List */}
        {loading ? (
          <div className="text-center py-12 text-[hsl(var(--foreground-secondary))]">Loading users...</div>
        ) : users.length === 0 ? (
          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardContent className="py-12 text-center">
              <UsersIcon className="h-12 w-12 mx-auto mb-4 text-[hsl(var(--foreground-muted))]" />
              <h3 className="text-lg font-semibold text-[hsl(var(--foreground))] mb-2">No users found</h3>
              <Button onClick={openCreateModal} className="mt-4">
                <Plus className="h-4 w-4 mr-2" />
                Create your first user
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {users.map((user) => (
              <Card
                key={user.id}
                className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]"
                data-testid={`user-card-${user.email}`}
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div className="h-12 w-12 rounded-full bg-[hsl(var(--primary))] flex items-center justify-center text-white font-semibold text-lg">
                        {user.full_name?.charAt(0) || 'U'}
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold text-[hsl(var(--foreground))]">
                          {user.full_name}
                        </h3>
                        <div className="flex items-center gap-2 mt-1">
                          <Mail className="h-3 w-3 text-[hsl(var(--foreground-muted))]" />
                          <p className="text-sm text-[hsl(var(--foreground-secondary))]">
                            {user.email}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 mt-2">
                          <Badge className={getRoleBadgeColor(user.role)}>
                            <Shield className="h-3 w-3 mr-1" />
                            {user.role.replace('_', ' ')}
                          </Badge>
                          {user.tenant_id && (
                            <span className="text-xs text-[hsl(var(--foreground-muted))]">
                              Tenant: {getTenantName(user.tenant_id)}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openEditModal(user)}
                        className="gap-1"
                      >
                        <Pencil className="h-3 w-3" />
                        Edit
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => openDeleteModal(user)}
                        className="gap-1"
                      >
                        <Trash2 className="h-3 w-3" />
                        Delete
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Create/Edit User Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>
              {editingUser ? 'Edit User' : 'Create New User'}
            </DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="full_name">Full Name</Label>
              <Input
                id="full_name"
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                placeholder="John Doe"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="john@example.com"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">
                Password {editingUser && '(leave blank to keep current)'}
              </Label>
              <Input
                id="password"
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder={editingUser ? '********' : 'Enter password'}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="role">Role</Label>
              <Select
                value={formData.role}
                onValueChange={(value) => setFormData({ ...formData, role: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select role" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="tenant_user">Tenant User</SelectItem>
                  <SelectItem value="tenant_admin">Tenant Admin</SelectItem>
                  <SelectItem value="super_admin">Super Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {formData.role !== 'super_admin' && (
              <div className="grid gap-2">
                <Label htmlFor="tenant">Tenant</Label>
                <Select
                  value={formData.tenant_id}
                  onValueChange={(value) => setFormData({ ...formData, tenant_id: value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select tenant" />
                  </SelectTrigger>
                  <SelectContent>
                    {tenants.map((tenant) => (
                      <SelectItem key={tenant.id} value={tenant.id}>
                        {tenant.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : editingUser ? 'Update User' : 'Create User'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Modal */}
      <Dialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Delete User</DialogTitle>
          </DialogHeader>
          <p className="text-[hsl(var(--foreground-secondary))]">
            Are you sure you want to delete <strong>{userToDelete?.full_name}</strong>?
            This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={saving}>
              {saving ? 'Deleting...' : 'Delete User'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SuperAdminLayout>
  );
}
