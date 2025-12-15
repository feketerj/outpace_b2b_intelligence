import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import { TenantProvider } from './context/TenantContext';

// Pages
import LoginPage from './pages/LoginPage';
import SuperAdminDashboard from './pages/SuperAdminDashboard';
import TenantDashboard from './pages/TenantDashboard';
import OpportunityDetail from './pages/OpportunityDetail';
import IntelligenceFeed from './pages/IntelligenceFeed';
import UsersPage from './pages/UsersPage';
import TenantsPage from './pages/TenantsPage';

// Protected Route Component
const ProtectedRoute = ({ children, requireSuperAdmin = false }) => {
  const { isAuthenticated, loading, user } = useAuth();\n\n  if (loading) {\n    return (\n      <div className=\"min-h-screen bg-[hsl(var(--background))] flex items-center justify-center\">\n        <div className=\"text-[hsl(var(--foreground-secondary))]\">Loading...</div>\n      </div>\n    );\n  }\n\n  if (!isAuthenticated) {\n    return <Navigate to=\"/login\" replace />;\n  }\n\n  if (requireSuperAdmin && user?.role !== 'super_admin') {\n    return <Navigate to=\"/dashboard\" replace />;\n  }\n\n  return children;\n};\n\nfunction AppRoutes() {\n  return (\n    <Routes>\n      <Route path=\"/login\" element={<LoginPage />} />\n      \n      {/* Super Admin Routes */}\n      <Route\n        path=\"/admin\"\n        element={\n          <ProtectedRoute requireSuperAdmin>\n            <SuperAdminDashboard />\n          </ProtectedRoute>\n        }\n      />\n      <Route\n        path=\"/admin/tenants\"\n        element={\n          <ProtectedRoute requireSuperAdmin>\n            <TenantsPage />\n          </ProtectedRoute>\n        }\n      />\n      \n      {/* Tenant User Routes */}\n      <Route\n        path=\"/dashboard\"\n        element={\n          <ProtectedRoute>\n            <TenantDashboard />\n          </ProtectedRoute>\n        }\n      />\n      <Route\n        path=\"/opportunities/:id\"\n        element={\n          <ProtectedRoute>\n            <OpportunityDetail />\n          </ProtectedRoute>\n        }\n      />\n      <Route\n        path=\"/intelligence\"\n        element={\n          <ProtectedRoute>\n            <IntelligenceFeed />\n          </ProtectedRoute>\n        }\n      />\n      <Route\n        path=\"/users\"\n        element={\n          <ProtectedRoute>\n            <UsersPage />\n          </ProtectedRoute>\n        }\n      />\n      \n      {/* Default Route */}\n      <Route path=\"/\" element={<Navigate to=\"/login\" replace />} />\n    </Routes>\n  );\n}\n\nfunction App() {\n  return (\n    <BrowserRouter>\n      <AuthProvider>\n        <TenantProvider>\n          <AppRoutes />\n          <Toaster\n            position=\"bottom-right\"\n            toastOptions={{\n              style: {\n                background: 'hsl(var(--background-elevated))',\n                color: 'hsl(var(--foreground))',\n                border: '1px solid hsl(var(--border))'\n              }\n            }}\n          />\n        </TenantProvider>\n      </AuthProvider>\n    </BrowserRouter>\n  );\n}\n\nexport default App;
