import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Building2, Users, LayoutDashboard, LogOut, Settings } from 'lucide-react';
import { Button } from '../ui/button';

export const SuperAdminLayout = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const navItems = [
    { path: '/admin', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/admin/tenants', icon: Building2, label: 'Tenants' },
    { path: '/admin/users', icon: Users, label: 'Users' },
    { path: '/admin/database', icon: Settings, label: 'Database' },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[hsl(var(--background))]">
      {/* Sidebar */}
      <div className="w-64 bg-[hsl(var(--background-secondary))] border-r border-[hsl(var(--border))] flex flex-col">
        {/* Logo */}
        <div className="p-6 border-b border-[hsl(var(--border))]">
          <h1 className="text-xl font-heading font-bold text-[hsl(var(--foreground))]">
            OutPace Intelligence
          </h1>
          <p className="text-xs text-[hsl(var(--foreground-secondary))] mt-1">
            Super Admin
          </p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                data-testid={`nav-${item.label.toLowerCase()}`}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors duration-150 ${
                  isActive
                    ? 'bg-[hsl(var(--primary))] text-white'
                    : 'text-[hsl(var(--foreground-secondary))] hover:bg-[hsl(var(--background-tertiary))] hover:text-[hsl(var(--foreground))]'
                }`}
              >
                <Icon className="h-5 w-5" />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* User Info & Logout */}
        <div className="p-4 border-t border-[hsl(var(--border))]">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-10 w-10 rounded-full bg-[hsl(var(--primary))] flex items-center justify-center text-white font-semibold">
              {user?.full_name?.charAt(0) || 'A'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[hsl(var(--foreground))] truncate">
                {user?.full_name}
              </p>
              <p className="text-xs text-[hsl(var(--foreground-secondary))] truncate">
                {user?.email}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleLogout}
            className="w-full border-[hsl(var(--border))] hover:bg-[hsl(var(--background-tertiary))]" data-testid="sidebar-logout-button"
          >
            <LogOut className="h-4 w-4 mr-2" />
            Logout
          </Button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        {children}
      </div>
    </div>
  );
};