import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import apiClient from '@/lib/api';
import { injectThemeStyles } from '@/utils/themeEffects';
import { useAuth } from './AuthContext';

const TenantContext = createContext(null);

export function TenantProvider({ children }) {
  const { user, isAuthenticated } = useAuth();
  const [currentTenant, setCurrentTenant] = useState(null);
  const [brandingStyles, setBrandingStyles] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const applyBranding = useCallback((branding) => {
    if (!branding) return;

    const styles = {
      '--tenant-primary': branding.primary_color || '',
      '--tenant-secondary': branding.secondary_color || '',
      '--tenant-accent': branding.accent_color || '',
    };

    setBrandingStyles(styles);

    // Inject CSS custom properties into document root
    const root = document.documentElement;
    Object.entries(styles).forEach(([property, value]) => {
      if (value) {
        root.style.setProperty(property, value);
      }
    });

    // Call utility to inject any additional theme effects (fonts, shadows, etc.)
    injectThemeStyles(branding);
  }, []);

  const fetchTenant = useCallback(async (tenantId) => {
    if (!tenantId) return;

    setLoading(true);
    setError(null);

    try {
      // FIX: Use apiClient (with token refresh interceptor) instead of raw fetch()
      const response = await apiClient.get(`/api/tenants/${tenantId}`);
      const tenant = response.data;

      setCurrentTenant(tenant);

      // Sub-clients inherit parent (master) branding if present
      // master_branding overrides branding
      const effectiveBranding = tenant.master_branding || tenant.branding;
      if (effectiveBranding) {
        applyBranding(effectiveBranding);
      }
    } catch (err) {
      console.error('Failed to fetch tenant:', err);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [applyBranding]);

  // Fetch tenant whenever a user logs in and has a tenant_id
  useEffect(() => {
    if (isAuthenticated && user?.tenant_id) {
      fetchTenant(user.tenant_id);
    } else if (!isAuthenticated) {
      // Clear tenant state on logout
      setCurrentTenant(null);
      setBrandingStyles({});
    }
  }, [isAuthenticated, user?.tenant_id, fetchTenant]);

  const value = {
    currentTenant,
    brandingStyles,
    loading,
    error,
    refetchTenant: () => user?.tenant_id ? fetchTenant(user.tenant_id) : null,
  };

  return (
    <TenantContext.Provider value={value}>
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant() {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error('useTenant must be used within a TenantProvider');
  }
  return context;
}

export default TenantContext;
