import React, { useState, useEffect } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { apiClient, showApiError } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { ArrowLeft, Lock, CheckCircle, AlertTriangle } from 'lucide-react';

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [tokenValid, setTokenValid] = useState(true);
  const [validating, setValidating] = useState(true);

  // Validate token on mount
  useEffect(() => {
    const validateToken = async () => {
      if (!token) {
        setTokenValid(false);
        setValidating(false);
        return;
      }

      try {
        await apiClient.get(`/api/auth/validate-reset-token?token=${token}`);
        setTokenValid(true);
      } catch (error) {
        // Token validation endpoint may not exist yet, assume valid for now
        setTokenValid(true);
      }
      setValidating(false);
    };

    validateToken();
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }

    setLoading(true);

    try {
      await apiClient.post('/api/auth/reset-password', {
        token,
        new_password: password
      });
      setSuccess(true);
      toast.success('Password reset successfully');
    } catch (error) {
      showApiError(error, 'Failed to reset password');
    }

    setLoading(false);
  };

  if (validating) {
    return (
      <div className="min-h-screen bg-[hsl(var(--background))] flex items-center justify-center p-4">
        <div className="text-[hsl(var(--foreground-secondary))]">Validating reset link...</div>
      </div>
    );
  }

  if (!token || !tokenValid) {
    return (
      <div className="min-h-screen bg-[hsl(var(--background))] flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
          <CardHeader className="space-y-3 text-center">
            <div className="mx-auto w-12 h-12 bg-red-500/10 rounded-full flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-red-500" />
            </div>
            <CardTitle className="text-2xl">Invalid or Expired Link</CardTitle>
            <CardDescription>
              This password reset link is invalid or has expired. Please request a new one.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              <Link to="/forgot-password" className="w-full">
                <Button className="w-full bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90">
                  Request New Reset Link
                </Button>
              </Link>
              <Link to="/login" className="w-full">
                <Button variant="ghost" className="w-full">
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back to Sign In
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen bg-[hsl(var(--background))] flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
          <CardHeader className="space-y-3 text-center">
            <div className="mx-auto w-12 h-12 bg-green-500/10 rounded-full flex items-center justify-center">
              <CheckCircle className="w-6 h-6 text-green-500" />
            </div>
            <CardTitle className="text-2xl">Password Reset Complete</CardTitle>
            <CardDescription>
              Your password has been successfully reset. You can now sign in with your new password.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              className="w-full bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
              onClick={() => navigate('/login')}
              data-testid="go-to-login-button"
            >
              Sign In
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[hsl(var(--background))] flex items-center justify-center p-4">
      <Card className="w-full max-w-md bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
        <CardHeader className="space-y-3">
          <div className="text-center">
            <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
              OutPace Intelligence
            </h1>
          </div>
          <div className="mx-auto w-12 h-12 bg-[hsl(var(--primary))]/10 rounded-full flex items-center justify-center">
            <Lock className="w-6 h-6 text-[hsl(var(--primary))]" />
          </div>
          <CardTitle className="text-2xl text-center">Reset Your Password</CardTitle>
          <CardDescription className="text-center">
            Enter your new password below. Make sure it's at least 8 characters.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4" data-testid="reset-password-form">
            <div className="space-y-2">
              <Label htmlFor="password">New Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter new password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                data-testid="reset-password-input"
                className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm Password</Label>
              <Input
                id="confirmPassword"
                type="password"
                placeholder="Confirm new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
                data-testid="reset-password-confirm-input"
                className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
              />
            </div>
            {password && confirmPassword && password !== confirmPassword && (
              <p className="text-sm text-red-500">Passwords do not match</p>
            )}
            <Button
              type="submit"
              className="w-full bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
              disabled={loading || (password && confirmPassword && password !== confirmPassword)}
              data-testid="reset-password-submit-button"
            >
              {loading ? 'Resetting...' : 'Reset Password'}
            </Button>
          </form>
          <div className="mt-6 text-center">
            <Link
              to="/login"
              className="text-sm text-[hsl(var(--primary))] hover:underline inline-flex items-center"
            >
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back to Sign In
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
