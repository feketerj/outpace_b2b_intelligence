# Testing Guide

This document describes how to run tests for the OutPace Intelligence Platform.

## Test Framework

The project uses **CARFAX** (Comprehensive Auditable Report For Application eXecution) as its primary test runner. CARFAX is a bash-based integration test suite that validates system invariants through stratified Monte Carlo testing.

## Test Plan

For the complete test plan including all 390 tests across 12 categories and 72 strata, see [docs/test-plan-v2.md](docs/test-plan-v2.md).

## Running Tests Locally

### Prerequisites

- bash
- curl
- jq
- Python 3.11+
- Running API server (default: `http://localhost:8000`)

### Basic Usage

Run the full test suite:

```bash
./carfax.sh all
```

### Stratified Test Execution

CARFAX supports stratified Monte Carlo testing. Run specific strata:

```bash
# Happy path tests (baseline functionality)
./carfax.sh happy

# Boundary tests (isolation, limits, edge cases)
./carfax.sh boundary

# Invalid input tests (validation, rejection)
./carfax.sh invalid

# Empty input tests (missing data handling)
./carfax.sh empty

# Performance tests (concurrency, load)
./carfax.sh performance

# Full suite (all strata)
./carfax.sh all
```

### Custom API URL

Set the `API_URL` environment variable to test against a different server:

```bash
API_URL=http://localhost:8000 ./carfax.sh all
```

## Monte Carlo Confidence Testing

For statistical confidence in test results, use the Monte Carlo runner which executes 59 full test suite runs (95% confidence, p<0.05):

```bash
./scripts/monte_carlo_runner.sh
```

## Running Tests in Docker

### Build the Test Image

```bash
docker build -f Dockerfile.test -t test-runner .
```

### Run Tests

```bash
# Against remote API
docker run --rm -e API_URL=https://your-api.example.com test-runner all

# Run specific stratum
docker run --rm -e API_URL=https://your-api.example.com test-runner happy
```

Pass the CARFAX credential environment variables when running the containerized test runner:

```bash
docker run --rm \
  -e API_URL=http://host.docker.internal:8000 \
  -e CARFAX_ADMIN_EMAIL="$CARFAX_ADMIN_EMAIL" \
  -e CARFAX_ADMIN_PASSWORD="$CARFAX_ADMIN_PASSWORD" \
  -e CARFAX_TENANT_A_PASSWORD="$CARFAX_TENANT_A_PASSWORD" \
  -e CARFAX_TENANT_B_PASSWORD="$CARFAX_TENANT_B_PASSWORD" \
  test-runner all
```

### WSL/Docker Desktop Networking

When running Docker on Windows with WSL2, use `host.docker.internal` to reach services running on the host:

```bash
docker run --rm \
  -e API_URL=http://host.docker.internal:8000 \
  -e CARFAX_ADMIN_EMAIL="$CARFAX_ADMIN_EMAIL" \
  -e CARFAX_ADMIN_PASSWORD="$CARFAX_ADMIN_PASSWORD" \
  -e CARFAX_TENANT_A_PASSWORD="$CARFAX_TENANT_A_PASSWORD" \
  -e CARFAX_TENANT_B_PASSWORD="$CARFAX_TENANT_B_PASSWORD" \
  test-runner all
```

## Test Reports

CARFAX generates JSON reports in the `carfax_reports/` directory with:

- Timestamp and API URL
- Pass/fail counts and rate
- Invariants coverage status
- Raw evidence from each test

## Invariants Covered

The test suite validates these system invariants:

| ID | Invariant | Description |
|----|-----------|-------------|
| INV-1 | Tenant Isolation | Cross-tenant data access blocked |
| INV-2 | Chat Atomicity | Failed chat attempts leave no artifacts |
| INV-3 | Paid Chat Enforcement | Chat disabled returns 403, no persistence |
| INV-4 | Master Tenant Restriction | Master tenant policy controls enforced |
| INV-5 | Export Determinism | Exports produce consistent, valid output |

## Two-Step Containerized Flow

Due to Docker Compose lifecycle requirements with `--abort-on-container-exit`, run containerized tests in two steps:

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

## CI Integration

Tests run automatically on pull requests via GitHub Actions. See `.github/workflows/ci.yml` for configuration.
