import React, { useEffect, useState } from 'react';
import { SuperAdminLayout } from '../components/layout/SuperAdminLayout';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { apiClient } from '../lib/api';
import { Building2, Users, FileText, TrendingUp, Plus } from 'lucide-react';

export default function SuperAdminDashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardStats();
  }, []);

  const fetchDashboardStats = async () => {
    try {
      const response = await apiClient.get('/api/admin/dashboard');
      setStats(response.data);
    } catch (error) {
      console.error('Failed to fetch dashboard stats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <SuperAdminLayout>
        <div className="flex items-center justify-center h-full">
          <div className="text-[hsl(var(--foreground-secondary))]">Loading dashboard...</div>
        </div>
      </SuperAdminLayout>
    );
  }

  return (
    <SuperAdminLayout>
      <div className="p-6 md:p-8 max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
            Dashboard
          </h1>
          <p className="text-[hsl(var(--foreground-secondary))] mt-1">
            System overview and quick actions
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]" data-testid="tenants-stat-card">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-[hsl(var(--foreground-secondary))]">
                Total Tenants
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="text-3xl font-bold font-mono text-[hsl(var(--foreground))]">
                  {stats?.summary?.total_tenants || 0}
                </div>
                <Building2 className="h-8 w-8 text-[hsl(var(--primary))]" />
              </div>
              <p className="text-xs text-[hsl(var(--foreground-muted))] mt-2">
                {stats?.summary?.active_tenants || 0} active
              </p>
            </CardContent>
          </Card>

          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-[hsl(var(--foreground-secondary))]">
                Total Users
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="text-3xl font-bold font-mono text-[hsl(var(--foreground))]">
                  {stats?.summary?.total_users || 0}
                </div>
                <Users className="h-8 w-8 text-[hsl(var(--secondary))]" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-[hsl(var(--foreground-secondary))]">
                Opportunities
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="text-3xl font-bold font-mono text-[hsl(var(--foreground))]">
                  {stats?.summary?.total_opportunities || 0}
                </div>
                <FileText className="h-8 w-8 text-[hsl(var(--accent-success))]" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-[hsl(var(--foreground-secondary))]">
                Intelligence Reports
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="text-3xl font-bold font-mono text-[hsl(var(--foreground))]">
                  {stats?.summary?.total_intelligence || 0}
                </div>
                <TrendingUp className="h-8 w-8 text-[hsl(var(--accent-info))]" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardHeader>
              <CardTitle className="text-[hsl(var(--foreground))]">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button 
                className="w-full justify-start bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                onClick={() => navigate('/admin/tenants')}
                data-testid="manage-tenants-button"
              >
                <Plus className="h-4 w-4 mr-2" />
                Create New Tenant
              </Button>
              <Button 
                className="w-full justify-start bg-[hsl(var(--background-tertiary))] border border-[hsl(var(--border))] hover:bg-[hsl(var(--background-elevated))] text-[hsl(var(--foreground))]"
                onClick={() => navigate('/admin/users')}
                variant="outline"
              >
                <Users className="h-4 w-4 mr-2" />
                Manage Users
              </Button>
            </CardContent>
          </Card>

          <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
            <CardHeader>
              <CardTitle className="text-[hsl(var(--foreground))]">System Health</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-[hsl(var(--foreground-secondary))]">Database</span>
                  <span className="text-sm font-medium text-[hsl(var(--accent-success))]">● Healthy</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-[hsl(var(--foreground-secondary))]">API</span>
                  <span className="text-sm font-medium text-[hsl(var(--accent-success))]">● Running</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-[hsl(var(--foreground-secondary))]">Scheduler</span>
                  <span className="text-sm font-medium text-[hsl(var(--accent-success))]">● Active</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </SuperAdminLayout>
  );
}