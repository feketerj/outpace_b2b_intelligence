import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';

export default function NotFoundPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-6 px-4">
        {/* 404 heading */}
        <div className="space-y-2">
          <h1
            className="text-8xl font-bold"
            style={{ color: 'hsl(var(--primary))' }}
          >
            404
          </h1>
          <h2
            className="text-2xl font-semibold"
            style={{ color: 'hsl(var(--foreground))' }}
          >
            Page Not Found
          </h2>
          <p
            className="text-base max-w-sm mx-auto"
            style={{ color: 'hsl(var(--muted-foreground))' }}
          >
            The page you&apos;re looking for doesn&apos;t exist or has been moved.
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Button asChild>
            <Link to="/dashboard">Go to Dashboard</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/login">Go to Login</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
