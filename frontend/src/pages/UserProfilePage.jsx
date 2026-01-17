import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { apiClient, showApiError } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Separator } from '../components/ui/separator';
import { ArrowLeft, User, Mail, Shield, Building2, Calendar, Lock, Save } from 'lucide-react';

export default function UserProfilePage() {
  const { user, token, logout } = useAuth();
  const navigate = useNavigate();

  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  // Password change state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await apiClient.get('/api/auth/me');
        setProfile(response.data);
      } catch (error) {
        toast.error('Failed to load profile');
        if (error.response?.status === 401) {
          logout();
        }
      }
      setLoading(false);
    };

    if (token) {
      fetchProfile();
    }
  }, [token, logout]);

  const handlePasswordChange = async (e) => {
    e.preventDefault();

    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match');
      return;
    }

    if (newPassword.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }

    setChangingPassword(true);

    try {
      await apiClient.post('/api/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword
      });
      toast.success('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      showApiError(error, 'Failed to change password');
    }

    setChangingPassword(false);
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getRoleDisplay = (role) => {
    const roleMap = {
      super_admin: 'Super Administrator',
      tenant_admin: 'Tenant Administrator',
      tenant_user: 'User'
    };
    return roleMap[role] || role;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[hsl(var(--background))] flex items-center justify-center">
        <div className="text-[hsl(var(--foreground-secondary))]">Loading profile...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[hsl(var(--background))] p-6">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate(-1)}
            data-testid="back-button"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-[hsl(var(--foreground))]">Profile Settings</h1>
            <p className="text-sm text-[hsl(var(--foreground-secondary))]">
              Manage your account information and security
            </p>
          </div>
        </div>

        {/* Profile Information Card */}
        <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="w-5 h-5" />
              Account Information
            </CardTitle>
            <CardDescription>Your personal details and account settings</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label className="flex items-center gap-2 text-[hsl(var(--foreground-secondary))]">
                  <User className="w-4 h-4" />
                  Full Name
                </Label>
                <div
                  className="px-3 py-2 rounded-md bg-[hsl(var(--background-tertiary))] text-[hsl(var(--foreground))]"
                  data-testid="profile-name"
                >
                  {profile?.full_name || 'Not set'}
                </div>
              </div>

              <div className="space-y-2">
                <Label className="flex items-center gap-2 text-[hsl(var(--foreground-secondary))]">
                  <Mail className="w-4 h-4" />
                  Email Address
                </Label>
                <div
                  className="px-3 py-2 rounded-md bg-[hsl(var(--background-tertiary))] text-[hsl(var(--foreground))]"
                  data-testid="profile-email"
                >
                  {profile?.email}
                </div>
              </div>

              <div className="space-y-2">
                <Label className="flex items-center gap-2 text-[hsl(var(--foreground-secondary))]">
                  <Shield className="w-4 h-4" />
                  Role
                </Label>
                <div
                  className="px-3 py-2 rounded-md bg-[hsl(var(--background-tertiary))] text-[hsl(var(--foreground))]"
                  data-testid="profile-role"
                >
                  {getRoleDisplay(profile?.role)}
                </div>
              </div>

              {profile?.tenant_id && (
                <div className="space-y-2">
                  <Label className="flex items-center gap-2 text-[hsl(var(--foreground-secondary))]">
                    <Building2 className="w-4 h-4" />
                    Tenant ID
                  </Label>
                  <div
                    className="px-3 py-2 rounded-md bg-[hsl(var(--background-tertiary))] text-[hsl(var(--foreground))] font-mono text-sm"
                    data-testid="profile-tenant"
                  >
                    {profile.tenant_id}
                  </div>
                </div>
              )}
            </div>

            <Separator className="my-4" />

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label className="flex items-center gap-2 text-[hsl(var(--foreground-secondary))]">
                  <Calendar className="w-4 h-4" />
                  Account Created
                </Label>
                <div className="px-3 py-2 rounded-md bg-[hsl(var(--background-tertiary))] text-[hsl(var(--foreground))] text-sm">
                  {formatDate(profile?.created_at)}
                </div>
              </div>

              <div className="space-y-2">
                <Label className="flex items-center gap-2 text-[hsl(var(--foreground-secondary))]">
                  <Calendar className="w-4 h-4" />
                  Last Login
                </Label>
                <div className="px-3 py-2 rounded-md bg-[hsl(var(--background-tertiary))] text-[hsl(var(--foreground))] text-sm">
                  {formatDate(profile?.last_login)}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Change Password Card */}
        <Card className="bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="w-5 h-5" />
              Change Password
            </CardTitle>
            <CardDescription>Update your password to keep your account secure</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handlePasswordChange} className="space-y-4" data-testid="change-password-form">
              <div className="space-y-2">
                <Label htmlFor="currentPassword">Current Password</Label>
                <Input
                  id="currentPassword"
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                  data-testid="current-password-input"
                  className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="newPassword">New Password</Label>
                <Input
                  id="newPassword"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                  data-testid="new-password-input"
                  className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm New Password</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={8}
                  data-testid="confirm-password-input"
                  className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
                />
              </div>
              {newPassword && confirmPassword && newPassword !== confirmPassword && (
                <p className="text-sm text-red-500">Passwords do not match</p>
              )}
              <Button
                type="submit"
                disabled={changingPassword || (newPassword && confirmPassword && newPassword !== confirmPassword)}
                className="bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                data-testid="change-password-button"
              >
                {changingPassword ? (
                  'Changing Password...'
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    Change Password
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
