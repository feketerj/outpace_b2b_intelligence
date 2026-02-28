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
    // FIX: Real system health from /api/admin/system/health
  // which returns { status, services: { database, scheduler } }.
  // Do NOT call /api/health — that endpoint only returns { status, database (string), timestamp }
  // with no api or scheduler fields.
  const [health, setHealth] = useState({
        database: 'Loading...',
        api: 'Loading...',
        scheduler: 'Loading...',
  });

  useEffect(() => {
        fetchDashboardStats();
        fetchHealth();
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

  if (loading) {
        return (
                <SuperAdminLayout>
                        <div className="flex items-center justify-center h-full">
                                  <div className="text-[hsl(var(--foreground-secondary))]">Loading dashboard...</div>div>
                        </div>div>
                </SuperAdminLayout>SuperAdminLayout>
              );
  }
  
    return (
          <SuperAdminLayout>
                <div className="p-6 md:p-8 max-w-7xl mx-auto">
                        <div className="mb-8">
                                  <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
                                              Dashboard
                                  </h1>h1>
                                  <p className="text-[hsl(var(--foreground-secondary))] mt-1">
                                              System overview and quick actions
                                  </p>p>
                        </div>div>
                
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                                  <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]" data-testid="tenants-stat-card">
                                              <CardHeader className="pb-3">
                                                            <CardTitle className="text-sm font-medium text-[hsl(var(--foreground-secondary))]">Total Tenants</CardTitle>CardTitle>
                                              </CardHeader>CardHeader>
                                              <CardContent>
                                                            <div className="flex items-center justify-between">
                                                                            <div className="text-3xl font-bold font-mono text-[hsl(var(--foreground))]">{stats?.summary?.total_tenants || 0}</div>div>
                                                                            <Building2 className="h-8 w-8 text-[hsl(var(--primary))]" />
                                                            </div>div>
                                                            <p className="text-xs text-[hsl(var(--foreground-muted))] mt-2">{stats?.summary?.active_tenants || 0} active</p>p>
                                              </CardContent>CardContent>
                                  </Card>Card>
                        
                                  <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                                              <CardHeader className="pb-3">
                                                            <CardTitle className="text-sm font-medium text-[hsl(var(--foreground-secondary))]">Total Users</CardTitle>CardTitle>
                                              </CardHeader>CardHeader>
                                              <CardContent>
                                                            <div className="flex items-center justify-between">
                                                                            <div className="text-3xl font-bold font-mono text-[hsl(var(--foreground))]">{stats?.summary?.total_users || 0}</div>div>
                                                                            <Users className="h-8 w-8 text-[hsl(var(--secondary))]" />
                                                            </div>div>
                                              </CardContent>CardContent>
                                  </Card>Card>
                        
                                  <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                                              <CardHeader className="pb-3">
                                                            <CardTitle className="text-sm font-medium text-[hsl(var(--foreground-secondary))]">Opportunities</CardTitle>CardTitle>
                                              </CardHeader>CardHeader>
                                              <CardContent>
                                                            <div className="flex items-center justify-between">
                                                                            <div className="text-3xl font-bold font-mono text-[hsl(var(--foreground))]">{stats?.summary?.total_opportunities || 0}</div>div>
                                                                            <FileText className="h-8 w-8 text-[hsl(var(--accent-success))]" />
                                                            </div>div>
                                              </CardContent>CardContent>
                                  </Card>Card>
                        
                                  <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                                              <CardHeader className="pb-3">
                                                            <CardTitle className="text-sm font-medium text-[hsl(var(--foreground-secondary))]">Intelligence Reports</CardTitle>CardTitle>
                                              </CardHeader>CardHeader>
                                              <CardContent>
                                                            <div className="flex items-center justify-between">
                                                                            <div className="text-3xl font-bold font-mono text-[hsl(var(--foreground))]">{stats?.summary?.total_intelligence || 0}</div>div>
                                                                            <TrendingUp className="h-8 w-8 text-[hsl(var(--accent-info))]" />
                                                            </div>div>
                                              </CardContent>CardContent>
                                  </Card>Card>
                        </div>div>
                
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                  <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                                              <CardHeader>
                                                            <CardTitle className="text-[hsl(var(--foreground))]">Quick Actions</CardTitle>CardTitle>
                                              </CardHeader>CardHeader>
                                              <CardContent className="space-y-3">
                                                            <Button
                                                                              className="w-full justify-start bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                                                                              onClick={() => navigate('/admin/tenants')}
                                                                              data-testid="manage-tenants-button"
                                                                            >
                                                                            <Plus className="h-4 w-4 mr-2" />
                                                                            Create New Tenant
                                                            </Button>Button>
                                                            <Button
                                                                              className="w-full justify-start bg-[hsl(var(--background-tertiary))] border border-[hsl(var(--border))] hover:bg-[hsl(var(--background-elevated))] text-[hsl(var(--foreground))]"
                                                                              onClick={() => navigate('/admin/users')}
                                                                              variant="outline"
                                                                            >
                                                                            <Users className="h-4 w-4 mr-2" />
                                                                            Manage Users
                                                            </Button>Button>
                                              </CardContent>CardContent>
                                  </Card>Card>
                        
                                  <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
                                              <CardHeader>
                                                            <CardTitle className="text-[hsl(var(--foreground))]">System Health</CardTitle>CardTitle>
                                              </CardHeader>CardHeader>
                                              <CardContent>
                                                            <div className="space-y-2">
                                                              {[
            { label: 'Database', value: health.database },
            { label: 'API', value: health.api },
            { label: 'Scheduler', value: health.scheduler },
                            ].map(({ label, value }) => (
                                                <div key={label} className="flex items-center justify-between">
                                                                    <span className="text-sm text-[hsl(var(--foreground-secondary))]">{label}</span>span>
                                                                    <span className="text-sm font-medium text-[hsl(var(--accent-success))]">
                                                                      {value}
                                                                    </span>span>
                                                </div>div>
                                              ))}
                                                            </div>div>
                                              </CardContent>CardContent>
                                  </Card>Card>
                        </div>div>
                </div>div>
          </SuperAdminLayout>SuperAdminLayout>
        );
}
</SuperAdminLayout>
