import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { apiClient } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { ArrowLeft, Mail, CheckCircle } from 'lucide-react';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await apiClient.post('/api/auth/forgot-password', { email });
      setSubmitted(true);
      toast.success('Password reset instructions sent');
    } catch (error) {
      // Show success even on error to prevent email enumeration
      // In production, backend should always return 200 regardless of email existence
      setSubmitted(true);
      toast.success('If this email exists, reset instructions have been sent');
    }

    setLoading(false);
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-[hsl(var(--background))] flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
          <CardHeader className="space-y-3 text-center">
            <div className="mx-auto w-12 h-12 bg-green-500/10 rounded-full flex items-center justify-center">
              <CheckCircle className="w-6 h-6 text-green-500" />
            </div>
            <CardTitle className="text-2xl">Check Your Email</CardTitle>
            <CardDescription>
              If an account exists for <span className="font-medium text-[hsl(var(--foreground))]">{email}</span>,
              you will receive password reset instructions shortly.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-[hsl(var(--foreground-secondary))] text-center">
              Didn't receive an email? Check your spam folder or try again.
            </p>
            <div className="flex flex-col gap-2">
              <Button
                variant="outline"
                className="w-full"
                onClick={() => setSubmitted(false)}
                data-testid="try-again-button"
              >
                Try Another Email
              </Button>
              <Link to="/login" className="w-full">
                <Button variant="ghost" className="w-full" data-testid="back-to-login-button">
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
            <Mail className="w-6 h-6 text-[hsl(var(--primary))]" />
          </div>
          <CardTitle className="text-2xl text-center">Forgot Password?</CardTitle>
          <CardDescription className="text-center">
            Enter your email address and we'll send you instructions to reset your password.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4" data-testid="forgot-password-form">
            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <Input
                id="email"
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="forgot-password-email-input"
                className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
              />
            </div>
            <Button
              type="submit"
              className="w-full bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
              disabled={loading}
              data-testid="forgot-password-submit-button"
            >
              {loading ? 'Sending...' : 'Send Reset Instructions'}
            </Button>
          </form>
          <div className="mt-6 text-center">
            <Link
              to="/login"
              className="text-sm text-[hsl(var(--primary))] hover:underline inline-flex items-center"
              data-testid="back-to-login-link"
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
