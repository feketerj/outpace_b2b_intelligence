import React from 'react';
import { useAuth } from '../context/AuthContext';

export default function SuperAdminDashboard() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-[hsl(var(--background))]">
      <div className="glass-header sticky top-0 z-10 px-6 py-4">
        <h1 className="text-2xl font-heading font-bold">Super Admin Dashboard</h1>
      </div>
      <div className="p-6">
        <p className="text-[hsl(var(--foreground-secondary))]">Welcome, {user?.full_name}!</p>
        <p className="text-sm mt-2">Super Admin functionality - Manage tenants, users, and system settings</p>
      </div>
    </div>
  );
}