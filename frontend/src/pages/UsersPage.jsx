import React, { useEffect, useState } from 'react';
import { SuperAdminLayout } from '../components/layout/SuperAdminLayout';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import axios from 'axios';
import { toast } from 'sonner';
import { Users as UsersIcon, Mail, Shield } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/users`);
      setUsers(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch users:', error);
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const getRoleBadgeColor = (role) => {
    if (role === 'super_admin') return 'bg-[hsl(var(--accent-danger))]';
    if (role === 'tenant_admin') return 'bg-[hsl(var(--primary))]';
    return 'bg-[hsl(var(--foreground-muted))]';
  };

  return (
    <SuperAdminLayout>
      <div className="p-6 md:p-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
            User Management
          </h1>
          <p className="text-[hsl(var(--foreground-secondary))] mt-1">
            View and manage all platform users
          </p>
        </div>

        {/* Users List */}
        {loading ? (
          <div className="text-center py-12 text-[hsl(var(--foreground-secondary))]">Loading users...</div>
        ) : users.length === 0 ? (
          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardContent className="py-12 text-center">
              <UsersIcon className="h-12 w-12 mx-auto mb-4 text-[hsl(var(--foreground-muted))]" />
              <h3 className="text-lg font-semibold text-[hsl(var(--foreground))] mb-2">No users found</h3>
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
                              Tenant: {user.tenant_id.slice(0, 8)}...
                            </span>
                          )}
                        </div>
                      </div>
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
