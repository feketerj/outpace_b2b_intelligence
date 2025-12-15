import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    const result = await login(email, password);

    if (result.success) {
      toast.success('Login successful!');
      // Navigate based on role (will be handled by ProtectedRoute)
      navigate('/dashboard');
    } else {
      toast.error(result.error || 'Login failed');
    }

    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[hsl(var(--background))] flex items-center justify-center p-4">
      <Card className="w-full max-w-md bg-[hsl(var(--background-secondary))] border-[hsl(var(--border))]">
        <CardHeader className="space-y-3">
          <div className="text-center">
            <h1 className="text-3xl font-heading font-bold text-[hsl(var(--foreground))]">
              OutPace Intelligence
            </h1>
            <p className="text-sm text-[hsl(var(--foreground-secondary))] mt-2">
              Enterprise Intelligence Platform
            </p>
          </div>
          <CardTitle className="text-2xl">Sign In</CardTitle>
          <CardDescription>Enter your credentials to access the platform</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4" data-testid="login-form">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="admin@outpace.ai"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="login-email-input"
                className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                data-testid="login-password-input"
                className="bg-[hsl(var(--background-tertiary))] border-[hsl(var(--border))]"
              />
            </div>
            <Button
              type="submit"
              className="w-full bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
              disabled={loading}
              data-testid="login-submit-button"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>
          <div className="mt-6 text-xs text-center text-[hsl(var(--foreground-muted))]">
            Default Super Admin: admin@outpace.ai / outpace2025
          </div>
        </CardContent>
      </Card>
      <div className="fixed bottom-4 right-4 text-xs text-[hsl(var(--foreground-muted))]">
        Powered by OutPace Intelligence
      </div>
    </div>
  );
}