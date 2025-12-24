# Testing

## Overview

The test system is organized around **categories** (functional areas/route files) and **strata** (test intent bands). Each category (auth, tenants, chat, opportunities, intelligence, exports, upload, sync, config, admin, users, rag) is exercised across six strata: **happy**, **boundary**, **invalid**, **empty**, **performance**, and **failure**. This stratified approach keeps coverage balanced across normal flows, edge cases, error handling, and performance.

Monte Carlo execution repeats each category/stratum combination **59 times** to reach 95% confidence (p < 0.05) when zero failures are observed. The full Monte Carlo run therefore executes 12 categories × 6 strata × 59 iterations for a comprehensive confidence sweep.

## Prerequisites

- **Docker Desktop** (required for Docker-based runs)
- **WSL 2** on Windows (recommended/required by Docker Desktop for Linux containers)

## Quick start

Run a single category in the happy stratum:

```bash
./carfax.sh auth happy
```

Run all categories in the happy stratum:

```bash
./carfax.sh all happy
```

Run the full suite across all strata:

```bash
./carfax.sh all
```

Run the full Monte Carlo sweep:

```bash
./scripts/monte_carlo_full.sh
```

## Docker-based testing

The docker-compose test stack mirrors the test plan architecture (MongoDB, mock services, API, and the test runner). Start the full test environment with:

```bash
docker-compose -f docker-compose.test.yml up
```

The `test-runner` service uses `Dockerfile.test` and runs `./carfax.sh` as its entrypoint.

## Environment variables reference

These environment variables are used by the test runner and the Docker Compose stack:

| Variable | Purpose | Default/Example |
| --- | --- | --- |
| `API_URL` | Base URL for the API under test | `http://api:8000` (Docker), `http://localhost:8001` (host) |
| `MONGO_URL` | MongoDB connection string | `mongodb://test-mongo:27017` or `mongodb://localhost:27018` |
| `DB_NAME` | MongoDB database name | `outpace_test` |
| `JWT_SECRET` | JWT signing secret for test env | `test-secret-key-12345` |
| `HIGHERGOV_API_URL` | HigherGov mock base URL | `http://mock-highergov:8081` |
| `MISTRAL_API_URL` | Mistral mock base URL | `http://mock-mistral:8082` |
| `PERPLEXITY_API_URL` | Perplexity mock base URL | `http://mock-perplexity:8083` |
| `TEST_TIMEOUT_MS` | Timeout for individual test operations | `30000` |
| `CHAOS_ENABLED` | Enable mock chaos behaviors | `true` |
| `SEED_ON_STARTUP` | Seed test data on startup | `true` |

## Troubleshooting

- **WSL networking**: When running Docker Desktop on Windows, use `localhost` from WSL for published ports, and prefer the Docker-provided service names (like `api`, `test-mongo`) inside compose networks. If the API is unreachable from WSL, confirm that Docker Desktop is using WSL 2 integration and that the ports are published (e.g., `8001`, `27018`).
- **Docker build issues**: If the test-runner image fails to build, clear any stale caches (`docker builder prune`) and retry `docker build -f Dockerfile.test -t test-runner .`.
- **Service health checks**: If `docker-compose.test.yml` fails while waiting for the API, check the `api` container logs and verify the mock service ports (8081–8083) are not in use by another process.

## Full test plan

For the complete test matrix and Monte Carlo confidence model, see the full test plan: [docs/test-plan.md](docs/test-plan.md).
