# Testing Guide

This document describes how to run tests for the OutPace B2B Intelligence Platform.

## Environment Variables

Before running any tests, set the required environment variables:

```bash
export MONGO_URL=mongodb://localhost:27017
export DB_NAME=outpace_intelligence
export JWT_SECRET=your-secret-key
```

Copy `.env.example` to get started:

```bash
cp .env.example .env
# Edit .env with your values
```

The test harness (`carfax.sh`) also reads these optional credentials:

```bash
export CARFAX_ADMIN_EMAIL="admin@outpace.ai"
export CARFAX_ADMIN_PASSWORD="<your-admin-password>"

# Tenant test accounts (used by tenant-isolation tests)
export CARFAX_TENANT_A_EMAIL="tenant-a@example.com"
export CARFAX_TENANT_A_PASSWORD="<tenant-a-password>"
export CARFAX_TENANT_B_EMAIL="tenant-b@example.com"
export CARFAX_TENANT_B_PASSWORD="<tenant-b-password>"
```

## Unit Tests (pytest)

The project uses **pytest** for unit and integration tests located in `backend/tests/`.

### Run all unit tests

```bash
pytest backend/tests/ -v
```

### Run with coverage

```bash
pytest backend/tests/ -v \
  --cov=backend \
  --cov-config=.coveragerc \
  --cov-report=term-missing
```

### Coverage gate (80% minimum)

CI enforces an 80% minimum coverage threshold:

```bash
pytest backend/tests/ -v \
  --cov=backend \
  --cov-config=.coveragerc \
  --cov-fail-under=80
```

If coverage drops below 80%, the command exits non-zero and CI fails.

### Seed test data before running tests

```bash
pip install pymongo bcrypt
python scripts/seed_carfax_tenants.py
python scripts/seed_carfax_users.py
```

## Integration Tests (carfax.sh)

**CARFAX** (Comprehensive Auditable Report For Application eXecution) is the primary integration test runner. It validates system invariants through a stratified test suite.

### Prerequisites

- bash, curl, jq
- Python 3.11+
- Running API server (default: `http://localhost:8000`)

### Run the full suite

```bash
./carfax.sh all
```

### Run specific strata

```bash
./carfax.sh happy        # Happy path (baseline functionality)
./carfax.sh boundary     # Boundary tests (isolation, limits, edge cases)
./carfax.sh invalid      # Invalid input tests (validation, rejection)
./carfax.sh empty        # Empty input tests (missing data handling)
./carfax.sh performance  # Performance tests (concurrency, load)
```

### Custom API URL

```bash
API_URL=http://localhost:8000 ./carfax.sh all
```

## Docker Testing

### Build the test image

```bash
docker build -f Dockerfile.test -t test-runner .
```

### Run tests against a running API

```bash
docker run --rm -e API_URL=http://host.docker.internal:8000 test-runner all
```

### Two-step containerized flow (Docker Compose)

**Step 1: Seed the database**

```bash
docker-compose -f docker-compose.test.yml --profile seed up -d mongodb
docker-compose -f docker-compose.test.yml --profile seed up seeder
```

**Step 2: Run tests**

```bash
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

**Cleanup**

```bash
docker-compose -f docker-compose.test.yml down -v
```

### WSL/Docker Desktop networking

When running on Windows with WSL2, use `host.docker.internal` to reach services on the host:

```bash
docker run --rm -e API_URL=http://host.docker.internal:8000 test-runner all
```

## CI Integration

Tests run automatically on pull requests and pushes to `main` via GitHub Actions (`.github/workflows/ci.yml`).

The CI pipeline:
1. Starts a MongoDB service container
2. Seeds test data
3. Runs `pytest` with the 80% coverage gate
4. Fails the build if coverage drops below threshold

## Test Reports

CARFAX generates JSON reports in `carfax_reports/` with:

- Timestamp and API URL
- Pass/fail counts and rate
- Invariant coverage status
- Raw evidence from each test
