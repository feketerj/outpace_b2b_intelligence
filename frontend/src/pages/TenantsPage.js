import React, { useEffect, useState } from 'react';
import { SuperAdminLayout } from '../components/layout/SuperAdminLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import axios from 'axios';
import { toast } from 'sonner';
import { Plus, Edit2, Trash2, Building2 } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function TenantsPage() {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    status: 'active'
  });

  useEffect(() => {
    fetchTenants();
  }, []);

  const fetchTenants = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/tenants`);
      setTenants(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch tenants:', error);
      toast.error('Failed to load tenants');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTenant = async (e) => {
    e.preventDefault();
    
    try {
      await axios.post(`${API_URL}/api/tenants`, formData);
      toast.success('Tenant created successfully!');
      setShowCreateDialog(false);
      setFormData({ name: '', slug: '', status: 'active' });
      fetchTenants();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create tenant');
    }
  };

  const handleDeleteTenant = async (tenantId, tenantName) => {
    if (!window.confirm(`Are you sure you want to delete tenant "${tenantName}"? This will delete all associated data.`)) {
      return;
    }

    try {
      await axios.delete(`${API_URL}/api/tenants/${tenantId}`);
      toast.success('Tenant deleted successfully');
      fetchTenants();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete tenant');
    }
  };

  return (
    <SuperAdminLayout>
      <div className="p-6 md:p-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
              Tenant Management
            </h1>
            <p className="text-[hsl(var(--foreground-secondary))] mt-1">
              Manage client organizations and their configurations
            </p>
          </div>
          
          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button 
                className="bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                data-testid="create-tenant-button"
              >
                <Plus className="h-4 w-4 mr-2" />
                Create Tenant
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
              <DialogHeader>
                <DialogTitle className="text-[hsl(var(--foreground))]">Create New Tenant</DialogTitle>
                <DialogDescription className="text-[hsl(var(--foreground-secondary))]">
                  Add a new client organization to the platform
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleCreateTenant} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name" className="text-[hsl(var(--foreground))]">Company Name</Label>
                  <Input
                    id="name"
                    placeholder="Acme Corporation"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    required
                    className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="slug" className="text-[hsl(var(--foreground))]">Slug (URL identifier)</Label>
                  <Input
                    id="slug"
                    placeholder="acme"
                    value={formData.slug}
                    onChange={(e) => setFormData({...formData, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '')})}
                    required
                    className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                  />
                  <p className="text-xs text-[hsl(var(--foreground-muted))]">Only lowercase letters, numbers, and hyphens</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="status" className="text-[hsl(var(--foreground))]">Status</Label>
                  <Select value={formData.status} onValueChange={(value) => setFormData({...formData, status: value})}>
                    <SelectTrigger className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]">
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="suspended">Suspended</SelectItem>
                      <SelectItem value="inactive">Inactive</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex gap-2 pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowCreateDialog(false)}
                    className="flex-1 border-[hsl(var(--border))] hover:bg-[hsl(var(--background-tertiary))]"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    className="flex-1 bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                  >
                    Create Tenant
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {/* Tenants List */}
        {loading ? (
          <div className="text-center py-12 text-[hsl(var(--foreground-secondary))]">Loading tenants...</div>
        ) : tenants.length === 0 ? (
          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardContent className="py-12 text-center">
              <Building2 className="h-12 w-12 mx-auto mb-4 text-[hsl(var(--foreground-muted))]" />
              <h3 className="text-lg font-semibold text-[hsl(var(--foreground))] mb-2">No tenants yet</h3>
              <p className="text-[hsl(var(--foreground-secondary))] mb-4">Create your first tenant to get started</p>
              <Button 
                onClick={() => setShowCreateDialog(true)}
                className="bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
              >
                <Plus className="h-4 w-4 mr-2" />
                Create Tenant
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {tenants.map((tenant) => (
              <Card 
                key={tenant.id} 
                className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))] hover:border-[hsl(var(--border-light))] transition-colors duration-150"
                data-testid={`tenant-card-${tenant.slug}`}
              >
                <CardContent className="p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-xl font-semibold text-[hsl(var(--foreground))]">
                          {tenant.name}
                        </h3>
                        <Badge 
                          variant={tenant.status === 'active' ? 'default' : 'secondary'}
                          className={tenant.status === 'active' ? 'bg-[hsl(var(--accent-success))]' : 'bg-[hsl(var(--foreground-muted))]'}
                        >
                          {tenant.status}
                        </Badge>
                      </div>
                      <p className="text-sm text-[hsl(var(--foreground-secondary))]">
                        Slug: <span className="font-mono">{tenant.slug}</span>
                      </p>
                      <p className="text-xs text-[hsl(var(--foreground-muted))] mt-2">
                        Created: {new Date(tenant.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-[hsl(var(--border))] hover:bg-[hsl(var(--background-tertiary))]"
                        data-testid={`edit-tenant-${tenant.slug}`}
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeleteTenant(tenant.id, tenant.name)}
                        className="border-[hsl(var(--accent-danger))] text-[hsl(var(--accent-danger))] hover:bg-[hsl(var(--accent-danger))]/10"
                        data-testid={`delete-tenant-${tenant.slug}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </SuperAdminLayout>
  );
}