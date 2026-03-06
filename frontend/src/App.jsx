import React from 'react';
import PropTypes from 'prop-types';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import { TenantProvider } from './context/TenantContext';
import ErrorBoundary from './components/ErrorBoundary';

// Pages
import LoginPage from './pages/LoginPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import SuperAdminDashboard from './pages/SuperAdminDashboard';
import TenantDashboard from './pages/TenantDashboard';
import OpportunityDetail from './pages/OpportunityDetail';
import IntelligenceFeed from './pages/IntelligenceFeed';
import UsersPage from './pages/UsersPage';
import TenantsPage from './pages/tenants';
import DatabaseManager from './pages/DatabaseManager';
import TenantPreview from './pages/TenantPreview';
import UserProfilePage from './pages/UserProfilePage';
import NotFoundPage from './pages/NotFoundPage';

// Protected Route Component
const ProtectedRoute = ({ children, requireSuperAdmin = false }) => {
    const { isAuthenticated, loading, user } = useAuth();
    if (loading) {
          return (
                  <div className="min-h-screen bg-[hsl(var(--background))] flex items-center justify-center">
                          <div className="text-[hsl(var(--foreground-secondary))]">Loading...</div>div>
                  </div>div>
                );
    }
    if (!isAuthenticated) {
          return <Navigate to="/login" replace />;
    }
    if (requireSuperAdmin && user?.role !== 'super_admin') {
          return <Navigate to="/dashboard" replace />;
    }
    return children;
};

ProtectedRoute.propTypes = {
    children: PropTypes.node.isRequired,
    requireSuperAdmin: PropTypes.bool,
};

function AppRoutes() {
    return (
          <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                <Route path="/reset-password" element={<ResetPasswordPage />} />
          
            {/* Super Admin Routes */}
                <Route path="/admin" element={<ProtectedRoute requireSuperAdmin><SuperAdminDashboard /></ProtectedRoute>ProtectedRoute>} />
                      <Route path="/admin/tenants" element={<ProtectedRoute requireSuperAdmin><TenantsPage /></ProtectedRoute>ProtectedRoute>} />
                            <Route path="/admin/users" element={<ProtectedRoute requireSuperAdmin><UsersPage /></ProtectedRoute>ProtectedRoute>} />
                                  <Route path="/admin/database" element={<ProtectedRoute requireSuperAdmin><DatabaseManager /></ProtectedRoute>ProtectedRoute>} />
                                        <Route path="/preview" element={<ProtectedRoute requireSuperAdmin><TenantPreview /></ProtectedRoute>ProtectedRoute>} />
                                        
                                          {/* Tenant User Routes */}
                                              <Route path="/dashboard" element={<ProtectedRoute><TenantDashboard /></ProtectedRoute>ProtectedRoute>} />
                                                    <Route path="/opportunities/:id" element={<ProtectedRoute><OpportunityDetail /></ProtectedRoute>ProtectedRoute>} />
                                                          <Route path="/intelligence" element={<ProtectedRoute><IntelligenceFeed /></ProtectedRoute>ProtectedRoute>} />
                                                                <Route path="/profile" element={<ProtectedRoute><UserProfilePage /></ProtectedRoute>ProtectedRoute>} />
                                                                
                                                                  {/* Default Route */}
                                                                      <Route path="/" element={<Navigate to="/login" replace />} />
                                                                
                                                                  {/* FIX: 404 catch-all route — must be last */}
                                                                      <Route path="*" element={<NotFoundPage />} />
                                                                </Route>Routes>
                                                            );
                                                            }
                                                          
                                                          function App() {
                                                              return (
                                                              <ErrorBoundary>
                                                                    <BrowserRouter>
                                                                            <AuthProvider>
                                                                                      <TenantProvider>
                                                                                                  <ErrorBoundary>
                                                                                                                <AppRoutes />
                                                                                                    </ErrorBoundary>ErrorBoundary>
                                                                                                  <Toaster
                                                                                                                  position="bottom-right"
                                                                                                                  toastOptions={{
                                                                                                                                    style: {
                                                                                                                                                        background: 'hsl(var(--background-elevated))',
                                                                                                                                                        color: 'hsl(var(--foreground))',
                                                                                                                                                        border: '1px solid hsl(var(--border))',
                                                                                                                                      },
                                                                                                                    }}
                                                                                                                />
                                                                                      </TenantProvider>TenantProvider>
                                                                            </AuthProvider>AuthProvider>
                                                                    </BrowserRouter>BrowserRouter>
                                                              </ErrorBoundary>ErrorBoundary>
                                                            );
                                                            }
                                                          
                                                          export default App;
                                                          </div>
