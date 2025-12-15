import React, { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from './AuthContext';

const TenantContext = createContext(null);

export const TenantProvider = ({ children }) => {
  const { user } = useAuth();
  const [currentTenant, setCurrentTenant] = useState(null);
  const [brandingStyles, setBrandingStyles] = useState(null);

  useEffect(() => {
    if (user?.tenant_id) {
      fetchTenantBranding(user.tenant_id);
    }
  }, [user]);

  const fetchTenantBranding = async (tenantId) => {
    try {
      const API_URL = process.env.REACT_APP_BACKEND_URL;
      const response = await fetch(`${API_URL}/api/tenants/${tenantId}`);
      const tenant = await response.json();
      
      setCurrentTenant(tenant);
      applyBranding(tenant.branding);
    } catch (error) {
      console.error('Failed to fetch tenant branding:', error);
    }
  };

  const applyBranding = (branding) => {
    if (!branding) return;

    // Apply dynamic CSS variables
    const root = document.documentElement;
    
    if (branding.primary_color) {
      // Parse HSL string and set CSS variable
      root.style.setProperty('--tenant-primary', branding.primary_color.replace('hsl(', '').replace(')', ''));
    }
    
    if (branding.secondary_color) {
      root.style.setProperty('--tenant-secondary', branding.secondary_color.replace('hsl(', '').replace(')', ''));
    }

    setBrandingStyles(branding);
  };

  return (
    <TenantContext.Provider value={{
      currentTenant,
      brandingStyles,
      setCurrentTenant,
      applyBranding
    }}>
      {children}
    </TenantContext.Provider>
  );
};

export const useTenant = () => {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error('useTenant must be used within TenantProvider');
  }
  return context;
};