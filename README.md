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
- Node.js 18+ (for frontend)

### Backend Setup

```bash
cd backend
pip install -r requirements.txt

# Set environment variables
export MONGO_URL=mongodb://localhost:27017
export DB_NAME=outpace_intelligence
export JWT_SECRET=your-secret-key

# Run the server
uvicorn main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## Testing

See [TESTING.md](TESTING.md) for the complete testing guide.

Run the test suite:

```bash
./carfax.sh all
```

Run tests in Docker:

```bash
docker build -f Dockerfile.test -t test-runner .
docker run --rm -e API_URL=http://host.docker.internal:8000 test-runner all
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
