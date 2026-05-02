import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, FileText, Plus, TrendingUp, Users } from 'lucide-react';
import { SuperAdminLayout } from '../components/layout/SuperAdminLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { apiClient } from '../lib/api';

export default function SuperAdminDashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState({
    database: 'Loading...',
    api: 'Loading...',
    scheduler: 'Loading...',
  });

  useEffect(() => {
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

    const fetchHealth = async () => {
      try {
        const response = await apiClient.get('/api/admin/system/health');
        const data = response.data;
        setHealth({
          database: data.services?.database ?? 'unknown',
          api: data.status ?? 'unknown',
          scheduler: data.services?.scheduler ?? 'unknown',
        });
      } catch {
        setHealth({ database: 'unknown', api: 'unknown', scheduler: 'unknown' });
      }
    };

    fetchDashboardStats();
    fetchHealth();
  }, []);

  if (loading) {
    return (
      <SuperAdminLayout>
        <div className="flex items-center justify-center h-full">
          <div className="text-[hsl(var(--foreground-secondary))]">Loading dashboard...</div>
        </div>
      </SuperAdminLayout>
    );
  }

  const summary = stats?.summary ?? {};
  const statCards = [
    {
      title: 'Total Tenants',
      value: summary.total_tenants || 0,
      detail: `${summary.active_tenants || 0} active`,
      icon: Building2,
      iconClass: 'text-[hsl(var(--primary))]',
      testId: 'tenants-stat-card',
    },
    {
      title: 'Total Users',
      value: summary.total_users || 0,
      icon: Users,
      iconClass: 'text-[hsl(var(--secondary))]',
    },
    {
      title: 'Opportunities',
      value: summary.total_opportunities || 0,
      icon: FileText,
      iconClass: 'text-[hsl(var(--accent-success))]',
    },
    {
      title: 'Intelligence Reports',
      value: summary.total_intelligence || 0,
      icon: TrendingUp,
      iconClass: 'text-[hsl(var(--accent-info))]',
    },
  ];

  return (
    <SuperAdminLayout>
      <div className="p-6 md:p-8 max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
            Dashboard
          </h1>
          <p className="text-[hsl(var(--foreground-secondary))] mt-1">
            System overview and quick actions
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {statCards.map(({ title, value, detail, icon: Icon, iconClass, testId }) => (
            <Card
              key={title}
              className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]"
              data-testid={testId}
            >
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-[hsl(var(--foreground-secondary))]">
                  {title}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="text-3xl font-bold font-mono text-[hsl(var(--foreground))]">
                    {value}
                  </div>
                  <Icon className={`h-8 w-8 ${iconClass}`} />
                </div>
                {detail && (
                  <p className="text-xs text-[hsl(var(--foreground-muted))] mt-2">{detail}</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>

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
                {[
                  { label: 'Database', value: health.database },
                  { label: 'API', value: health.api },
                  { label: 'Scheduler', value: health.scheduler },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between">
                    <span className="text-sm text-[hsl(var(--foreground-secondary))]">{label}</span>
                    <span className="text-sm font-medium text-[hsl(var(--accent-success))]">
                      {value}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </SuperAdminLayout>
  );
}
