import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import apiClient from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

// Health indicator dot colors
const STATUS_COLORS = {
  healthy: 'text-green-500',
  running: 'text-green-500',
  active: 'text-green-500',
  degraded: 'text-yellow-500',
  unknown: 'text-yellow-500',
  down: 'text-red-500',
  error: 'text-red-500',
};

function StatusDot({ status }) {
  const colorClass = STATUS_COLORS[status?.toLowerCase()] ?? STATUS_COLORS.unknown;
  return (
    <span className={`inline-block mr-2 ${colorClass}`} aria-hidden="true">
      ●
    </span>
  );
}

export default function SuperAdminDashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();

  // Dashboard stats
  const [stats, setStats] = useState({
    totalTenants: null,
    totalUsers: null,
    opportunities: null,
    intelligenceReports: null,
  });
  const [statsLoading, setStatsLoading] = useState(true);

  // FIX: Real system health state (previously hardcoded)
  const [health, setHealth] = useState({
    database: null,
    api: null,
    scheduler: null,
  });
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState(false);

  // Fetch dashboard stats
  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const response = await apiClient.get('/api/admin/dashboard');
      const data = response.data;
      setStats({
        totalTenants: data.total_tenants ?? data.tenants ?? 0,
        totalUsers: data.total_users ?? data.users ?? 0,
        opportunities: data.opportunities ?? 0,
        intelligenceReports: data.intelligence_reports ?? 0,
      });
    } catch (err) {
      console.error('Failed to fetch dashboard stats:', err);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  // FIX: Fetch real system health from GET /api/health
  const fetchHealth = useCallback(async () => {
    setHealthLoading(true);
    setHealthError(false);
    try {
      const response = await apiClient.get('/api/health');
      const data = response.data;

      // Normalize: backend may return { status, database, scheduler } or nested { services: { ... } }
      const services = data.services ?? data;
      setHealth({
        database: services.database?.status ?? services.database ?? data.database ?? 'unknown',
        api: services.api?.status ?? services.api ?? data.api ?? data.status ?? 'unknown',
        scheduler: services.scheduler?.status ?? services.scheduler ?? data.scheduler ?? 'unknown',
      });
    } catch (err) {
      console.error('Failed to fetch health status:', err);
      setHealthError(true);
      setHealth({ database: 'unknown', api: 'unknown', scheduler: 'unknown' });
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    fetchHealth();
  }, [fetchStats, fetchHealth]);

  const statCards = [
    { label: 'Total Tenants', value: stats.totalTenants, testId: 'tenants-stat-card' },
    { label: 'Total Users', value: stats.totalUsers, testId: 'users-stat-card' },
    { label: 'Opportunities', value: stats.opportunities, testId: 'opportunities-stat-card' },
    { label: 'Intelligence Reports', value: stats.intelligenceReports, testId: 'intelligence-stat-card' },
  ];

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1
          className="text-3xl font-bold"
          style={{ color: 'hsl(var(--foreground))' }}
        >
          Super Admin Dashboard
        </h1>
        <p style={{ color: 'hsl(var(--muted-foreground))' }}>
          Welcome, {user?.name ?? user?.email}
        </p>
      </div>

      {/* Stats Cards */}
      <section>
        <h2
          className="text-xl font-semibold mb-4"
          style={{ color: 'hsl(var(--foreground))' }}
        >
          Overview
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map(({ label, value, testId }) => (
            <Card key={testId} data-testid={testId}>
              <CardHeader className="pb-2">
                <CardTitle
                  className="text-sm font-medium"
                  style={{ color: 'hsl(var(--muted-foreground))' }}
                >
                  {label}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p
                  className="text-3xl font-bold"
                  style={{ color: 'hsl(var(--foreground))' }}
                >
                  {statsLoading ? (
                    <span className="animate-pulse">—</span>
                  ) : (
                    value?.toLocaleString() ?? '—'
                  )}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Quick Actions */}
      <section>
        <h2
          className="text-xl font-semibold mb-4"
          style={{ color: 'hsl(var(--foreground))' }}
        >
          Quick Actions
        </h2>
        <div className="flex flex-wrap gap-3">
          <Button
            data-testid="manage-tenants-button"
            onClick={() => navigate('/admin/tenants')}
          >
            Create Tenant
          </Button>
          <Button
            variant="outline"
            onClick={() => navigate('/admin/users')}
          >
            Manage Users
          </Button>
          <Button
            variant="outline"
            onClick={() => navigate('/admin/database')}
          >
            Database Manager
          </Button>
        </div>
      </section>

      {/* System Health — FIX: real data from /api/health */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2
            className="text-xl font-semibold"
            style={{ color: 'hsl(var(--foreground))' }}
          >
            System Health
          </h2>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchHealth}
            disabled={healthLoading}
          >
            {healthLoading ? 'Refreshing…' : 'Refresh'}
          </Button>
        </div>

        <Card>
          <CardContent className="pt-6">
            {healthLoading ? (
              <div className="space-y-3">
                {['Database', 'API', 'Scheduler'].map((label) => (
                  <div key={label} className="flex items-center justify-between">
                    <span style={{ color: 'hsl(var(--foreground))' }}>{label}</span>
                    <span
                      className="animate-pulse text-sm"
                      style={{ color: 'hsl(var(--muted-foreground))' }}
                    >
                      Loading…
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {healthError && (
                  <p
                    className="text-sm mb-3"
                    style={{ color: 'hsl(var(--destructive))' }}
                  >
                    Could not reach health endpoint. Showing last known status.
                  </p>
                )}

                {[
                  { label: 'Database', status: health.database },
                  { label: 'API', status: health.api },
                  { label: 'Scheduler', status: health.scheduler },
                ].map(({ label, status }) => {
                  const displayStatus = status
                    ? status.charAt(0).toUpperCase() + status.slice(1)
                    : 'Unknown';
                  return (
                    <div key={label} className="flex items-center justify-between">
                      <span style={{ color: 'hsl(var(--foreground))' }}>{label}</span>
                      <span
                        className="text-sm font-medium"
                        style={{ color: 'hsl(var(--foreground))' }}
                      >
                        <StatusDot status={status ?? 'unknown'} />
                        {displayStatus}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
