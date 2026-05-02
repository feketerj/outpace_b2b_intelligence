import React, { createContext, useContext, useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { useAuth } from './AuthContext';
import { injectThemeStyles } from '../utils/themeEffects';
import { apiClient } from '../lib/api';

const TenantContext = createContext(null);

export const TenantProvider = ({ children }) => {
  const { user } = useAuth();
  const [currentTenant, setCurrentTenant] = useState(null);
  const [brandingStyles, setBrandingStyles] = useState(null);

  const applyBranding = (branding, masterBranding) => {
    if (!branding && !masterBranding) return;

    const effectiveBranding = masterBranding || branding;
    const root = document.documentElement;

    if (effectiveBranding.primary_color) {
      root.style.setProperty(
        '--tenant-primary',
        effectiveBranding.primary_color.replace('hsl(', '').replace(')', '')
      );
    }

    if (effectiveBranding.secondary_color) {
      root.style.setProperty(
        '--tenant-secondary',
        effectiveBranding.secondary_color.replace('hsl(', '').replace(')', '')
      );
    }

    if (effectiveBranding.accent_color) {
      root.style.setProperty(
        '--tenant-accent',
        effectiveBranding.accent_color.replace('hsl(', '').replace(')', '')
      );
    }

    if (effectiveBranding.visual_theme) {
      injectThemeStyles(effectiveBranding.visual_theme, effectiveBranding);
    }

    setBrandingStyles(effectiveBranding);
  };

  useEffect(() => {
    const fetchTenantBranding = async (tenantId) => {
      try {
        const response = await apiClient.get(`/api/tenants/${tenantId}`);
        const tenant = response.data;
        setCurrentTenant(tenant);
        applyBranding(tenant.branding, tenant.master_branding);
      } catch (error) {
        console.error('Failed to fetch tenant branding:', error);
      }
    };

    if (user?.tenant_id) {
      fetchTenantBranding(user.tenant_id);
    } else {
      setCurrentTenant(null);
      setBrandingStyles(null);
    }
  }, [user?.tenant_id]);

  return (
    <TenantContext.Provider value={{ currentTenant, brandingStyles, setCurrentTenant, applyBranding }}>
      {children}
    </TenantContext.Provider>
  );
};

TenantProvider.propTypes = {
  children: PropTypes.node.isRequired,
};

export const useTenant = () => {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error('useTenant must be used within TenantProvider');
  }
  return context;
};
