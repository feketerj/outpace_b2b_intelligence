# OutPace B2B Intelligence Platform

![CI](https://github.com/feketerj/outpace_b2b_intelligence/actions/workflows/ci.yml/badge.svg)

A B2B intelligence platform for tracking government contracting opportunities, generating AI-powered intelligence reports, and managing multi-tenant workflows.

## Features

- Multi-tenant architecture with strict data isolation
- Government contracting opportunity tracking (SAM.gov integration)
- AI-powered intelligence report generation
- Chat interface with configurable policies and quotas
- PDF export functionality
- Role-based access control (super_admin, tenant_admin, tenant_user)

## Quick Start

### Prerequisites

- Python 3.11+
- MongoDB
- Node.js 20.19+ or 22.12+ (for frontend)

### Backend Setup

```bash
cd backend
pip install -r requirements.txt

# Required environment variables
export MONGO_URL=mongodb://localhost:27017
export DB_NAME=outpace_intelligence
export JWT_SECRET=REPLACE_WITH_STRONG_JWT_SECRET

# Optional: CORS (defaults to localhost origins if unset)
export CORS_ALLOWED_ORIGINS="https://your-domain.com,https://app.your-domain.com"

# Optional: GCP Secret Manager (omit or leave unset to read secrets from env vars only)
# export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"

# Optional: MongoDB write concern (defaults to "majority")
export WRITE_CONCERN="majority"

# Run the server
uvicorn server:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm ci
npm run dev
```

### Test Credentials (Integration Tests)

The integration test harness (`carfax.sh`) reads credentials from environment variables. Set these before running tests:

```bash
# Admin credentials for test harness
export CARFAX_ADMIN_EMAIL="admin@example.com"
export CARFAX_ADMIN_PASSWORD="<your-admin-password>"

# Tenant test accounts (optional — used by tenant-isolation tests)
export CARFAX_TENANT_A_EMAIL="tenant-a@example.com"
export CARFAX_TENANT_A_PASSWORD="<tenant-a-password>"
export CARFAX_TENANT_B_EMAIL="tenant-b@example.com"
export CARFAX_TENANT_B_PASSWORD="<tenant-b-password>"

# E2E browser tests (Playwright)
export E2E_ADMIN_PASSWORD="<your-admin-password>"
```

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
# Edit .env with your values
```

> **Note**: Never commit `.env` to source control. `.gitignore` excludes it by default.

## Testing

See [TESTING.md](TESTING.md) for the complete testing guide.

Run the test suite:

```bash
./carfax.sh all
```

Run tests in Docker:

```bash
docker build -f Dockerfile.test -t test-runner .
docker run --rm \
  -e API_URL=http://host.docker.internal:8000 \
  -e CARFAX_ADMIN_EMAIL="$CARFAX_ADMIN_EMAIL" \
  -e CARFAX_ADMIN_PASSWORD="$CARFAX_ADMIN_PASSWORD" \
  -e CARFAX_TENANT_A_PASSWORD="$CARFAX_TENANT_A_PASSWORD" \
  -e CARFAX_TENANT_B_PASSWORD="$CARFAX_TENANT_B_PASSWORD" \
  test-runner all
```

## Project Structure

```
.
├── backend/           # FastAPI backend
├── frontend/          # React frontend
├── scripts/           # Utility scripts
├── carfax.sh          # Integration test runner
├── Dockerfile.test    # Test runner container
└── docs/              # Documentation
```

## License

Proprietary - All rights reserved.
