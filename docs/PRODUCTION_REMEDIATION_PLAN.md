# Production Remediation Plan

**Created:** January 16, 2026  
**Purpose:** Fix all conditional/needs-work items from Production Readiness Audit V2  
**Target:** Achieve full PRODUCTION-READY status

---

## Summary of Required Fixes

| ID | Issue | Priority | Effort | Status |
|----|-------|----------|--------|--------|
| REM-001 | Create `.env.example` file | HIGH | 30 min | TODO |
| REM-002 | Implement React Error Boundaries | HIGH | 2 hrs | TODO |
| REM-003 | Add Redis rate limiting documentation | MEDIUM | 1 hr | TODO |
| REM-004 | Add APM/monitoring integration | MEDIUM | 3 hrs | TODO |
| REM-005 | Clean up dead code in highergov_service.py | LOW | 15 min | TODO |

---

## REM-001: Create `.env.example` File

### Problem
The deployment documentation references `cp .env.example .env` but the file does not exist.

### Location
Create file at: `/.env.example` (repository root)

### Implementation

Create this file with the following content:

```bash
# OutPace B2B Intelligence - Environment Configuration
# ====================================================
# Copy to .env and fill in your values.
# DO NOT commit .env to version control.
#
# Generate secrets: openssl rand -hex 32

# ═══════════════════════════════════════════════════
# REQUIRED - Server will NOT start without these
# ═══════════════════════════════════════════════════

# MongoDB Connection
MONGO_URL=mongodb://outpace_app:YOUR_PASSWORD@localhost:27017/outpace_intelligence?authSource=admin
DB_NAME=outpace_intelligence

# JWT Authentication (MUST be 32+ chars, unique per environment)
JWT_SECRET=CHANGE_ME_run_openssl_rand_hex_32
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# ═══════════════════════════════════════════════════
# ENVIRONMENT & SECURITY
# ═══════════════════════════════════════════════════

# Environment mode - "production" enforces strict security
ENV=development
ENVIRONMENT=development

# CORS - Set to actual domain(s) in production
# Wildcard (*) or localhost BLOCKED when ENV=production
CORS_ORIGINS=http://localhost:3000,http://localhost:3333

# ═══════════════════════════════════════════════════
# EXTERNAL API KEYS
# ═══════════════════════════════════════════════════

# HigherGov (required for opportunity sync)
HIGHERGOV_API_KEY=your-highergov-api-key

# Mistral AI (required for AI scoring)
MISTRAL_API_KEY=your-mistral-api-key

# Perplexity AI (optional - for intelligence reports)
PERPLEXITY_API_KEY=your-perplexity-api-key

# ═══════════════════════════════════════════════════
# RATE LIMITING
# ═══════════════════════════════════════════════════

RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_AUTH=10/minute
RATE_LIMIT_UPLOAD=20/minute

# Storage backend - USE REDIS IN PRODUCTION
# memory:// = resets on restart, per-instance limits
# redis://host:port = persistent, global across instances
RATE_LIMIT_STORAGE=memory://

# ═══════════════════════════════════════════════════
# SECRETS MANAGEMENT (PRODUCTION)
# ═══════════════════════════════════════════════════

# Backend: env (default), aws, gcp, vault
SECRETS_BACKEND=env

# AWS Secrets Manager
# AWS_REGION=us-east-1

# GCP Secret Manager
# GCP_PROJECT_ID=your-project-id
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# HashiCorp Vault
# VAULT_ADDR=http://localhost:8200
# VAULT_TOKEN=your-vault-token

# ═══════════════════════════════════════════════════
# ERROR ALERTS (OPTIONAL BUT RECOMMENDED)
# ═══════════════════════════════════════════════════

# ERROR_EMAIL_TO=your-email@example.com
# ERROR_EMAIL_FROM=alerts@yourdomain.com
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-smtp-user
# SMTP_PASS=your-smtp-app-password

# ═══════════════════════════════════════════════════
# DOCKER COMPOSE
# ═══════════════════════════════════════════════════

MONGO_INITDB_ROOT_USERNAME=admin
MONGO_INITDB_ROOT_PASSWORD=CHANGE_ME_secure_admin_password
MONGO_APP_USERNAME=outpace_app
MONGO_APP_PASSWORD=CHANGE_ME_secure_app_password
```

### Verification
```bash
# File should exist and contain all required vars
grep -E "^(MONGO_URL|DB_NAME|JWT_SECRET)=" .env.example
```

### Acceptance Criteria
- [ ] File exists at repository root
- [ ] Contains all variables from `preflight.py` REQUIRED_ENV_VARS
- [ ] Contains clear comments explaining each section
- [ ] Contains warnings about production values
- [ ] Is NOT in `.gitignore` (should be committed)

---

## REM-002: Implement React Error Boundaries

### Problem
The frontend has no crash recovery. Any unhandled JavaScript error crashes the entire application.

### Location
- Create: `frontend/src/components/ErrorBoundary.jsx`
- Modify: `frontend/src/App.jsx`

### Implementation

#### Step 1: Create ErrorBoundary Component

Create `frontend/src/components/ErrorBoundary.jsx`:

```jsx
import React from 'react';
import PropTypes from 'prop-types';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    
    // Log error for debugging
    console.error('ErrorBoundary caught:', error, errorInfo);
    
    // TODO: Send to error tracking service (Sentry, etc.)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[hsl(var(--background))] flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-[hsl(var(--background-elevated))] rounded-lg shadow-lg p-6 text-center">
            <div className="text-6xl mb-4">⚠️</div>
            <h1 className="text-xl font-semibold text-[hsl(var(--foreground))] mb-2">
              Something went wrong
            </h1>
            <p className="text-[hsl(var(--foreground-secondary))] mb-4">
              We encountered an unexpected error. Please try again.
            </p>
            
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="text-left mb-4 p-3 bg-red-500/10 rounded text-sm">
                <summary className="cursor-pointer text-red-400 font-medium">
                  Error Details
                </summary>
                <pre className="mt-2 text-red-300 overflow-auto text-xs">
                  {this.state.error.toString()}
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}
            
            <div className="flex gap-3 justify-center">
              <button
                onClick={this.handleRetry}
                className="px-4 py-2 bg-[hsl(var(--primary))] text-white rounded hover:opacity-90 transition"
              >
                Try Again
              </button>
              <button
                onClick={() => window.location.href = '/'}
                className="px-4 py-2 border border-[hsl(var(--border))] text-[hsl(var(--foreground))] rounded hover:bg-[hsl(var(--background-hover))] transition"
              >
                Go Home
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

ErrorBoundary.propTypes = {
  children: PropTypes.node.isRequired
};

export default ErrorBoundary;
```

#### Step 2: Create API Error Handler

Create `frontend/src/utils/apiErrorHandler.js`:

```javascript
import axios from 'axios';
import { toast } from 'sonner';

/**
 * Configure global axios interceptors for error handling
 */
export function setupApiErrorHandler() {
  // Response interceptor
  axios.interceptors.response.use(
    (response) => response,
    (error) => {
      const status = error.response?.status;
      const data = error.response?.data;
      const traceId = data?.trace_id || error.response?.headers?.['x-trace-id'];

      // Handle specific error codes
      switch (status) {
        case 401:
          // Token expired or invalid - handled by AuthContext
          break;
          
        case 429:
          // Rate limited
          const retryAfter = data?.retry_after_seconds || 60;
          toast.error(`Too many requests. Please wait ${retryAfter} seconds.`, {
            duration: 5000,
          });
          break;
          
        case 500:
        case 502:
        case 503:
          // Server error - show trace ID for support
          toast.error(
            <div>
              <p>Server error occurred</p>
              {traceId && (
                <p className="text-xs mt-1 opacity-70">
                  Reference: {traceId}
                </p>
              )}
            </div>,
            { duration: 8000 }
          );
          break;
          
        default:
          // Other errors - let components handle
          break;
      }

      return Promise.reject(error);
    }
  );
}
```

#### Step 3: Update App.jsx

Modify `frontend/src/App.jsx`:

```jsx
import React from 'react';
import PropTypes from 'prop-types';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import { TenantProvider } from './context/TenantContext';
import ErrorBoundary from './components/ErrorBoundary';
import { setupApiErrorHandler } from './utils/apiErrorHandler';

// ... (existing imports)

// Initialize API error handler
setupApiErrorHandler();

// ... (existing ProtectedRoute and AppRoutes)

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <TenantProvider>
            <AppRoutes />
            <Toaster
              position="bottom-right"
              toastOptions={{
                style: {
                  background: 'hsl(var(--background-elevated))',
                  color: 'hsl(var(--foreground))',
                  border: '1px solid hsl(var(--border))'
                }
              }}
            />
          </TenantProvider>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
```

#### Step 4: Fix AuthContext Silent Logout

Modify `frontend/src/context/AuthContext.jsx` - update the `fetchUser` function:

```javascript
const fetchUser = async () => {
  try {
    const response = await axios.get(`${API_URL}/api/auth/me`);
    setUser(response.data);
  } catch (error) {
    const status = error.response?.status;
    
    // Only logout on auth errors (401, 403), not on server errors
    if (status === 401 || status === 403) {
      console.error('Authentication failed:', error);
      logout();
    } else {
      // Server error - keep user logged in, show error
      console.error('Failed to fetch user (server error):', error);
      // User state remains, they can retry
    }
  } finally {
    setLoading(false);
  }
};
```

### Verification
```bash
# Build should succeed
cd frontend && npm run build

# No console errors on page load
# Errors should show friendly UI, not crash
```

### Acceptance Criteria
- [ ] ErrorBoundary component exists
- [ ] App.jsx wraps content in ErrorBoundary
- [ ] API errors show toast with trace_id for 500s
- [ ] Rate limit (429) shows retry information
- [ ] AuthContext only logs out on 401/403, not 500
- [ ] Error UI has "Try Again" and "Go Home" buttons

---

## REM-003: Rate Limiting Redis Documentation

### Problem
In-memory rate limiting doesn't work for multi-instance deployments.

### Location
- Update: `docs/DEPLOYMENT.md`
- Optional: Add Redis to `docker-compose.yml`

### Implementation

#### Step 1: Update DEPLOYMENT.md

Add section after "Security Measures":

```markdown
## Rate Limiting Configuration

### Single Instance (Development)

The default in-memory storage works for development:

```bash
RATE_LIMIT_STORAGE=memory://
```

⚠️ **WARNING**: In-memory storage:
- Resets on server restart
- Does not share limits across instances
- NOT suitable for production with auto-scaling

### Multi-Instance (Production)

For Cloud Run, Kubernetes, or any horizontally-scaled deployment:

```bash
RATE_LIMIT_STORAGE=redis://redis:6379
```

### Adding Redis to Docker Compose

Add to `docker-compose.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  redis_data:
```

Update API service environment:

```yaml
  api:
    environment:
      - RATE_LIMIT_STORAGE=redis://redis:6379
    depends_on:
      redis:
        condition: service_healthy
```

### Verifying Rate Limits

```bash
# Test rate limiting is working
for i in {1..15}; do
  curl -w "%{http_code}\n" -s -o /dev/null http://localhost:8000/api/auth/login
done
# Should see 429 after 10 requests

# Check Redis is storing limits
docker exec -it <redis-container> redis-cli KEYS "LIMITER:*"
```
```

#### Step 2: Add Redis to docker-compose.yml

Add to `docker-compose.yml`:

```yaml
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - outpace-network

volumes:
  # ... existing volumes
  redis_data:
```

### Acceptance Criteria
- [ ] DEPLOYMENT.md has rate limiting section
- [ ] Warning about in-memory storage for production
- [ ] Redis configuration example provided
- [ ] docker-compose.yml includes Redis service (optional)
- [ ] Verification commands documented

---

## REM-004: APM/Monitoring Integration

### Problem
No application performance monitoring - can't track response times, error rates, or trends.

### Location
- Create: `backend/utils/telemetry.py`
- Modify: `backend/server.py`
- Update: `docs/DEPLOYMENT.md`

### Implementation

#### Option A: Google Cloud Trace (Recommended for GCP)

Create `backend/utils/telemetry.py`:

```python
"""
Application Performance Monitoring integration.

Supports:
- Google Cloud Trace (GCP)
- OpenTelemetry (vendor-agnostic)

Configuration:
    APM_BACKEND=gcp|otel|none
    GCP_PROJECT_ID=your-project (for GCP)
    OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4317 (for OTEL)
"""

import os
import logging
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger(__name__)

APM_BACKEND = os.environ.get("APM_BACKEND", "none").lower()


def init_telemetry():
    """Initialize APM based on configuration."""
    if APM_BACKEND == "gcp":
        _init_gcp_trace()
    elif APM_BACKEND == "otel":
        _init_opentelemetry()
    else:
        logger.info("[telemetry] APM disabled (APM_BACKEND=none)")


def _init_gcp_trace():
    """Initialize Google Cloud Trace."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        provider = TracerProvider()
        processor = BatchSpanProcessor(CloudTraceSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        # Auto-instrument FastAPI and httpx
        FastAPIInstrumentor.instrument()
        HTTPXClientInstrumentor.instrument()

        logger.info("[telemetry] Google Cloud Trace initialized")
    except ImportError as e:
        logger.warning(f"[telemetry] GCP trace packages not installed: {e}")
    except Exception as e:
        logger.error(f"[telemetry] Failed to init GCP trace: {e}")


def _init_opentelemetry():
    """Initialize OpenTelemetry with OTLP exporter."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        provider = TracerProvider()
        exporter = OTLPSpanExporter()
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument()

        logger.info("[telemetry] OpenTelemetry initialized")
    except ImportError as e:
        logger.warning(f"[telemetry] OTEL packages not installed: {e}")


@contextmanager
def trace_span(name: str, attributes: dict = None):
    """Create a trace span for custom instrumentation."""
    if APM_BACKEND == "none":
        yield None
        return

    try:
        from opentelemetry import trace
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(name, attributes=attributes) as span:
            yield span
    except Exception:
        yield None


def trace_function(name: str = None):
    """Decorator to trace a function."""
    def decorator(func):
        span_name = name or func.__name__

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with trace_span(span_name):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with trace_span(span_name):
                return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
```

#### Step 2: Add to server.py lifespan

```python
from backend.utils.telemetry import init_telemetry

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize APM early
    init_telemetry()
    
    # ... rest of lifespan
```

#### Step 3: Add dependencies to requirements.txt

```
# APM - GCP Cloud Trace
opentelemetry-api>=1.20.0
opentelemetry-sdk>=1.20.0
opentelemetry-exporter-gcp-trace>=1.5.0
opentelemetry-instrumentation-fastapi>=0.41b0
opentelemetry-instrumentation-httpx>=0.41b0

# APM - OpenTelemetry (vendor-agnostic)
opentelemetry-exporter-otlp>=1.20.0
```

#### Step 4: Update DEPLOYMENT.md

```markdown
## Application Performance Monitoring (APM)

### Google Cloud Trace (GCP)

For GCP deployments, enable Cloud Trace:

```bash
APM_BACKEND=gcp
GCP_PROJECT_ID=your-project-id
```

View traces at: https://console.cloud.google.com/traces

### OpenTelemetry (Vendor-Agnostic)

For self-hosted or other cloud providers:

```bash
APM_BACKEND=otel
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

Compatible with: Jaeger, Zipkin, Datadog, New Relic, etc.

### Disabling APM

```bash
APM_BACKEND=none  # Default
```
```

### Acceptance Criteria
- [ ] `backend/utils/telemetry.py` created
- [ ] GCP Cloud Trace integration works
- [ ] OpenTelemetry fallback works
- [ ] Graceful degradation when packages not installed
- [ ] DEPLOYMENT.md documents APM options
- [ ] requirements.txt includes optional APM packages

---

## REM-005: Clean Up Dead Code

### Problem
`highergov_service.py` has unreachable code after a `return` statement.

### Location
`backend/services/highergov_service.py` lines 253-387

### Implementation

Delete lines 253-387 in `highergov_service.py`. These lines are after the `return` statement in `fetch_single_opportunity` and can never execute.

The function ends at line 251:
```python
    except Exception as e:
        logger.error(f"Failed to fetch opportunity {opportunity_id}: {e}")
        raise
```

Everything after this is dead code (appears to be a duplicate/old version of `sync_highergov_opportunities`).

### Verification
```bash
# Run tests to ensure nothing breaks
cd backend && pytest tests/ -v

# Check function still works
python -c "from backend.services.highergov_service import fetch_single_opportunity; print('OK')"
```

### Acceptance Criteria
- [ ] Lines 253-387 deleted from highergov_service.py
- [ ] All tests still pass
- [ ] No import errors

---

## Execution Order

1. **REM-001** (30 min) - Create `.env.example` - blocks nothing, high value
2. **REM-002** (2 hrs) - Error Boundaries - improves user experience significantly  
3. **REM-005** (15 min) - Dead code cleanup - quick win
4. **REM-003** (1 hr) - Redis documentation - operational readiness
5. **REM-004** (3 hrs) - APM integration - can be done in parallel

## Verification Checklist

After completing all items:

```bash
# 1. .env.example exists
test -f .env.example && echo "✅ .env.example exists"

# 2. ErrorBoundary exists
test -f frontend/src/components/ErrorBoundary.jsx && echo "✅ ErrorBoundary exists"

# 3. Frontend builds
cd frontend && npm run build && echo "✅ Frontend builds"

# 4. Backend tests pass
cd ../backend && pytest tests/ -v && echo "✅ Tests pass"

# 5. No dead code
! grep -A5 "raise$" backend/services/highergov_service.py | grep -q "naics_codes" && echo "✅ Dead code removed"
```

---

## Post-Remediation

After all items are complete, re-run the audit verification:

```bash
# Verify all conditional items are now PASS
curl http://localhost:8000/api/health/deep

# Update PRODUCTION_READINESS_AUDIT_V2.md status table
```

Expected final status:

| Category | Before | After |
|----------|--------|-------|
| Rate Limiting | ⚠️ CONDITIONAL | ✅ PASS |
| Frontend Error Handling | ⚠️ CONDITIONAL | ✅ PASS |
| Environment Configuration | ⚠️ NEEDS WORK | ✅ PASS |
| Monitoring & Observability | ⚠️ CONDITIONAL | ✅ PASS |
