import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { TenantProvider } from '@/context/TenantContext';
import ErrorBoundary from '@/components/ErrorBoundary';
import { Toaster } from '@/components/ui/sonner';

// ProtectedRoute HOC — redirects unauthenticated users to /login
// and non-super-admins away from admin routes
function ProtectedRoute({ children, requireSuperAdmin = false }) {
  const { isAuthenticated, user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p style={{ color: 'hsl(var(--muted-foreground))' }}>Loading...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requireSuperAdmin && user?.role !== 'super_admin') {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}

// Pages
import LoginPage from '@/pages/LoginPage';
import ForgotPasswordPage from '@/pages/ForgotPasswordPage';
import ResetPasswordPage from '@/pages/ResetPasswordPage';
import SuperAdminDashboard from '@/pages/SuperAdminDashboard';
import TenantsPage from '@/pages/TenantsPage';
import UsersPage from '@/pages/UsersPage';
import DatabaseManager from '@/pages/DatabaseManager';
import TenantPreview from '@/pages/TenantPreview';
import TenantDashboard from '@/pages/TenantDashboard';
import OpportunityDetail from '@/pages/OpportunityDetail';
import IntelligenceFeed from '@/pages/IntelligenceFeed';
import UserProfilePage from '@/pages/UserProfilePage';
import NotFoundPage from '@/pages/NotFoundPage';

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <TenantProvider>
            <ErrorBoundary>
              <Routes>
                {/* Public routes */}
                <Route path="/login" element={<LoginPage />} />
                <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                <Route path="/reset-password" element={<ResetPasswordPage />} />

                {/* Super-admin only routes */}
                <Route
                  path="/admin"
                  element={
                    <ProtectedRoute isAuthenticated requireSuperAdmin>
                      <SuperAdminDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/tenants"
                  element={
                    <ProtectedRoute isAuthenticated requireSuperAdmin>
                      <TenantsPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/users"
                  element={
                    <ProtectedRoute isAuthenticated requireSuperAdmin>
                      <UsersPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/admin/database"
                  element={
                    <ProtectedRoute isAuthenticated requireSuperAdmin>
                      <DatabaseManager />
                    </ProtectedRoute>
                  }
                />

                {/* Preview route */}
                <Route
                  path="/preview"
                  element={
                    <ProtectedRoute isAuthenticated>
                      <TenantPreview />
                    </ProtectedRoute>
                  }
                />

                {/* Main app routes */}
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute isAuthenticated>
                      <TenantDashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/opportunities/:id"
                  element={
                    <ProtectedRoute isAuthenticated>
                      <OpportunityDetail />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/intelligence"
                  element={
                    <ProtectedRoute isAuthenticated>
                      <IntelligenceFeed />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/profile"
                  element={
                    <ProtectedRoute isAuthenticated>
                      <UserProfilePage />
                    </ProtectedRoute>
                  }
                />

                {/* Default redirect */}
                <Route path="/" element={<Navigate to="/login" replace />} />

                {/* FIX: 404 catch-all route — must be last */}
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </ErrorBoundary>
            <Toaster />
          </TenantProvider>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
