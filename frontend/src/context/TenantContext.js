import React, { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from './AuthContext';
import { injectThemeStyles } from '../utils/themeEffects';

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
      applyBranding(tenant.branding, tenant.master_branding);
    } catch (error) {
      console.error('Failed to fetch tenant branding:', error);
    }
  };

  const applyBranding = (branding, masterBranding) => {
    if (!branding && !masterBranding) return;
    
    // Use master branding if available (for sub-clients)
    const effectiveBranding = masterBranding || branding;

    // Apply dynamic CSS variables
    const root = document.documentElement;
    
    if (effectiveBranding.primary_color) {
      root.style.setProperty('--tenant-primary', effectiveBranding.primary_color.replace('hsl(', '').replace(')', ''));
    }
    
    if (effectiveBranding.secondary_color) {
      root.style.setProperty('--tenant-secondary', effectiveBranding.secondary_color.replace('hsl(', '').replace(')', ''));
    }
    
    if (effectiveBranding.accent_color) {
      root.style.setProperty('--tenant-accent', effectiveBranding.accent_color.replace('hsl(', '').replace(')', ''));
    }
    
    // Apply visual theme effects
    if (effectiveBranding.visual_theme) {
      injectThemeStyles(effectiveBranding.visual_theme, effectiveBranding);
    }

    setBrandingStyles(effectiveBranding);
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