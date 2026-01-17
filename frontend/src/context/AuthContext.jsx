import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient, setAuthTokens, clearAuthTokens, getRefreshToken } from '../lib/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  // Handle logout triggered by API interceptor (e.g., refresh token expired)
  const handleAuthLogout = useCallback(() => {
    setToken(null);
    setUser(null);
    clearAuthTokens();
  }, []);

  useEffect(() => {
    // Listen for auth:logout events from API interceptor
    window.addEventListener('auth:logout', handleAuthLogout);
    return () => {
      window.removeEventListener('auth:logout', handleAuthLogout);
    };
  }, [handleAuthLogout]);

  useEffect(() => {
    if (token) {
      // Fetch user info
      fetchUser();
    } else {
      setLoading(false);
    }
  }, [token]);

  const fetchUser = async () => {
    try {
      const response = await apiClient.get('/api/auth/me');
      setUser(response.data);
    } catch (error) {
      // Only logout on 401 (unauthorized)
      // Other errors (network, 500) should not trigger logout
      if (error.response?.status === 401) {
        console.error('Auth token invalid:', error);
        handleAuthLogout();
      } else {
        console.error('Failed to fetch user (non-auth error):', error);
        // Keep the user logged in but mark as potentially stale
        // The user can retry or the page will show an error state
      }
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      const response = await apiClient.post('/api/auth/login', {
        email,
        password
      });
      
      const { access_token, refresh_token, user: userData } = response.data;
      
      // Store tokens
      setAuthTokens(access_token, refresh_token);
      setToken(access_token);
      setUser(userData);
      
      return { success: true, user: userData };
    } catch (error) {
      const detail = error.response?.data?.detail || 'Login failed';
      const traceId = error.response?.data?.trace_id || error.response?.headers?.['x-trace-id'];
      
      // Handle structured error responses (e.g., password policy)
      let errorMessage = detail;
      if (typeof detail === 'object' && detail !== null) {
        errorMessage = detail.message || JSON.stringify(detail);
      }
      
      return {
        success: false,
        error: errorMessage,
        traceId: traceId || null
      };
    }
  };

  const logout = async () => {
    // Try to revoke refresh token on server
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        await apiClient.post('/api/auth/logout', {
          refresh_token: refreshToken
        });
      } catch (error) {
        // Ignore errors - we're logging out anyway
        console.debug('Logout API call failed (ignored):', error);
      }
    }
    
    // Clear local state
    setToken(null);
    setUser(null);
    clearAuthTokens();
  };

  const logoutAllDevices = async () => {
    try {
      await apiClient.post('/api/auth/logout-all');
    } catch (error) {
      console.error('Failed to logout all devices:', error);
    }
    
    // Clear local state
    setToken(null);
    setUser(null);
    clearAuthTokens();
  };

  const isSuperAdmin = () => user?.role === 'super_admin';
  const isTenantAdmin = () => user?.role === 'tenant_admin' || user?.role === 'super_admin';

  return (
    <AuthContext.Provider value={{
      user,
      token,
      loading,
      login,
      logout,
      logoutAllDevices,
      isSuperAdmin,
      isTenantAdmin,
      isAuthenticated: !!token,
      refreshUser: fetchUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};