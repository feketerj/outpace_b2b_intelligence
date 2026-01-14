import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTenant } from '../../context/TenantContext';
import { FileText, TrendingUp, LogOut, Menu, X } from 'lucide-react';
import { Button } from '../ui/button';
import { useState } from 'react';

export const TenantLayout = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { currentTenant, brandingStyles } = useTenant();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const navItems = [
    { path: '/dashboard', icon: FileText, label: 'Opportunities' },
    { path: '/intelligence', icon: TrendingUp, label: 'Intelligence' },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Get branding - use master's branding if this is a sub-client
  const effectiveBranding = currentTenant?.master_branding || brandingStyles || {};
  const primaryColor = effectiveBranding?.primary_color || 'hsl(210, 85%, 52%)';
  const secondaryColor = effectiveBranding?.secondary_color || 'hsl(265, 60%, 55%)';
  const logo = effectiveBranding?.logo_base64 || effectiveBranding?.logo_url;
  const poweredByText = currentTenant?.master_client_id 
    ? `Powered by ${currentTenant.master_client_name || 'Partner'}` 
    : 'Powered by OutPace Intelligence';

  return (
    <div className="flex h-screen overflow-hidden bg-[hsl(var(--background))]">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-0'} transition-all duration-300 bg-[hsl(var(--background-secondary))] border-r border-[hsl(var(--border))] flex flex-col overflow-hidden`}>
        {/* Logo & Client Name */}
        <div className="p-6 border-b border-[hsl(var(--border))]">
          {logo && (
            <img 
              src={logo} 
              alt={currentTenant?.name} 
              className="h-10 object-contain mb-3"
            />
          )}
          <h1 className="text-xl font-heading font-bold text-[hsl(var(--foreground))]">
            {currentTenant?.name || 'Dashboard'}
          </h1>
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
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors duration-150`}
                style={{
                  background: isActive ? primaryColor : 'transparent',
                  color: isActive ? 'white' : 'hsl(var(--foreground-secondary))'
                }}
              >
                <Icon className="h-5 w-5" />
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Powered By Footer */}
        <div className="p-4 border-t border-[hsl(var(--border))]">
          <div className="flex items-center gap-3 mb-3">
            <div 
              className="h-10 w-10 rounded-full flex items-center justify-center text-white font-semibold"
              style={{background: primaryColor}}
            >
              {user?.full_name?.charAt(0) || 'U'}
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
            className="w-full border-[hsl(var(--border))] hover:bg-[hsl(var(--background-tertiary))] mb-3"
          >
            <LogOut className="h-4 w-4 mr-2" />
            Logout
          </Button>
          <div className="text-center text-xs text-[hsl(var(--foreground-muted))] pt-2 border-t border-[hsl(var(--border))]">
            {poweredByText}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile Menu Toggle */}
        <div className="md:hidden p-4 border-b border-[hsl(var(--border))]">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="border-[hsl(var(--border))]"
          >
            {sidebarOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </Button>
        </div>
        
        {/* Content Area */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
};