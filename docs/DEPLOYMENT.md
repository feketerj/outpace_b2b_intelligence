# OutPace B2B Intelligence - Production Deployment Guide

This guide covers deploying OutPace to a production environment using Docker Compose.

## Prerequisites

- Docker Engine 24.0+ and Docker Compose v2
- A server with at least 2GB RAM, 2 CPU cores
- A domain name (for HTTPS)
- SSL certificates (Let's Encrypt recommended)

## Quick Start (Development/Testing)

```bash
# 1. Clone the repository
git clone <repo-url>
cd outpace_b2b_intelligence

# 2. Create environment file
cp .env.example .env

# 3. Edit .env with your values (especially passwords!)
# Generate JWT secret: openssl rand -hex 32

# 4. Start all services
docker compose up -d

# 5. Check status
docker compose ps
docker compose logs -f
```

## Production Deployment

### Step 1: Configure Environment Variables

```bash
cp .env.example .env
```

**Required variables:**

| Variable | Description | Example |
|----------|-------------|---------|
| `MONGO_INITDB_ROOT_USERNAME` | MongoDB admin username | `admin` |
| `MONGO_INITDB_ROOT_PASSWORD` | MongoDB admin password | (generate strong password) |
| `MONGO_APP_USERNAME` | App database user | `outpace_app` |
| `MONGO_APP_PASSWORD` | App database password | (generate strong password) |
| `JWT_SECRET` | JWT signing key | `openssl rand -hex 32` |
| `CORS_ALLOWED_ORIGINS` | Allowed origins | `https://your-domain.com` |
| `ENV` | Environment mode | `production` |

**Production-specific variables:**

| Variable | Description | Production Value |
|----------|-------------|------------------|
| `ENV` | Environment mode (enables strict security checks) | `production` |
| `RATE_LIMIT_STORAGE` | Rate limit backend (Redis for multi-instance) | `redis://redis:6379/0` |
| `SECRETS_BACKEND` | Secrets provider (`gcp`, `aws`, `vault`) | `gcp` |
| `GCP_PROJECT_ID` | GCP project (if using GCP secrets) | `your-project-id` |

See `.env.example` for a complete list of all configuration options with documentation.

### Step 2: SSL Certificates

**Option A: Let's Encrypt (Recommended)**

```bash
# Install certbot
sudo apt install certbot

# Get certificates (stop any service using port 80 first)
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem docker/certs/
cp /etc/letsencrypt/live/your-domain.com/privkey.pem docker/certs/
```

**Option B: Self-signed (Testing only)**

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/certs/privkey.pem \
  -out docker/certs/fullchain.pem \
  -subj "/CN=localhost"
```

### Step 3: Enable HTTPS

Edit `docker/nginx-proxy.conf`:

1. Uncomment the `return 301 https://$host$request_uri;` line in the HTTP server block
2. Uncomment the entire HTTPS server block
3. Update `server_name` to your domain

### Step 4: Deploy

```bash
# Build and start
docker compose up -d --build

# Verify all services are healthy
docker compose ps

# Check logs
docker compose logs -f api
docker compose logs -f mongodb
```

### Step 5: Create Initial Admin User

```bash
# Connect to the API container
docker compose exec api python -c "
from init_super_admin import create_super_admin
import asyncio
asyncio.run(create_super_admin())
"
```

Or seed with test data:

```bash
docker compose exec api python scripts/seed_carfax_users.py
```

## Architecture

```
                    ┌─────────────────┐
                    │   Internet      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Nginx Proxy    │ :80, :443
                    │  (TLS termination)
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
     ┌────────▼────────┐          ┌────────▼────────┐
     │    Frontend     │          │      API        │
     │  (Nginx static) │          │   (FastAPI)     │
     └─────────────────┘          └────────┬────────┘
                                           │
                                  ┌────────▼────────┐
                                  │    MongoDB      │
                                  │  (authenticated)│
                                  └─────────────────┘
```

## Security Measures

| Layer | Protection |
|-------|------------|
| Network | Only ports 80/443 exposed; internal services isolated |
| TLS | HTTPS with modern cipher suites |
| Authentication | JWT tokens with configurable expiry |
| Rate Limiting | 10/min auth, 100/min API, 20/min uploads |
| MongoDB | Authenticated connections, app user has limited permissions |
| Containers | Non-root users, minimal base images |
| Headers | X-Frame-Options, X-Content-Type-Options, HSTS |

## Monitoring

### Health Checks

```bash
# Overall health
curl http://localhost/health

# API health
curl http://localhost/api/health

# Check service status
docker compose ps
```

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api

# Last 100 lines
docker compose logs --tail=100 api
```

### MongoDB

```bash
# Connect to MongoDB shell
docker compose exec mongodb mongosh -u admin -p <password> --authenticationDatabase admin

# Check database stats
use outpace_intelligence
db.stats()
```

## Maintenance

### Backups

```bash
# Backup MongoDB
docker compose exec mongodb mongodump \
  -u admin -p <password> \
  --authenticationDatabase admin \
  --out /data/backup

# Copy backup to host
docker cp $(docker compose ps -q mongodb):/data/backup ./backup
```

### Updates

```bash
# Pull latest code
git pull

# Rebuild and restart
docker compose up -d --build

# Watch logs for issues
docker compose logs -f
```

### Certificate Renewal

```bash
# Renew Let's Encrypt certificates
sudo certbot renew

# Copy new certificates
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem docker/certs/
cp /etc/letsencrypt/live/your-domain.com/privkey.pem docker/certs/

# Reload nginx
docker compose exec proxy nginx -s reload
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose logs <service-name>

# Check if ports are in use
netstat -tlnp | grep -E ':(80|443|8000|27017)'
```

### MongoDB Connection Errors

1. Verify credentials in `.env` match what's in the database
2. Check MongoDB logs: `docker compose logs mongodb`
3. Ensure MongoDB is healthy: `docker compose ps`

### API Errors

1. Check API logs: `docker compose logs api`
2. Verify environment variables: `docker compose exec api env`
3. Test health endpoint: `curl http://localhost:8000/health`

### Frontend Not Loading

1. Check if build succeeded: `docker compose logs frontend`
2. Verify nginx config: `docker compose exec frontend nginx -t`
3. Check browser console for errors

## APM / Monitoring

The platform supports OpenTelemetry for distributed tracing and APM integration. Enable it via environment variables.

### Configuration

```bash
# Enable OpenTelemetry
OTEL_ENABLED=true

# Service name for traces
OTEL_SERVICE_NAME=outpace-api

# OTLP collector endpoint
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Sampling ratio (0.0-1.0, 1.0 = all traces)
OTEL_TRACES_SAMPLER_ARG=1.0
```

### Supported Backends

OpenTelemetry exports via OTLP, which is supported by:

| Backend | OTLP Endpoint | Notes |
|---------|---------------|-------|
| **GCP Cloud Trace** | Built-in via OpenTelemetry Collector | Deploy collector with GCP exporter |
| **Datadog** | `http://datadog-agent:4317` | Use Datadog Agent with OTLP receiver |
| **New Relic** | `https://otlp.nr-data.net:4317` | Set `api-key` header in exporter |
| **Jaeger** | `http://jaeger:4317` | Self-hosted Jaeger with OTLP |

### Example: GCP Cloud Trace Setup

1. Deploy OpenTelemetry Collector as sidecar:

```yaml
# docker-compose.override.yml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    environment:
      - GOOGLE_APPLICATION_CREDENTIALS=/etc/gcp/credentials.json
    volumes:
      - ./gcp-credentials.json:/etc/gcp/credentials.json:ro
```

2. Update API environment:

```bash
OTEL_ENABLED=true
OTEL_SERVICE_NAME=outpace-api
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### Metrics and Dashboards

For production, consider adding:
- Response time percentiles (p50, p95, p99)
- Error rate by endpoint
- External API latency (HigherGov, Mistral, Perplexity)
- Database query performance

## Scaling

For higher traffic:

1. **API Workers**: Edit `backend/Dockerfile` CMD to increase `--workers`
2. **MongoDB Replica Set**: See MongoDB documentation for replica set setup
3. **Load Balancer**: Put multiple API instances behind nginx upstream
4. **Redis for Rate Limiting**: Set `RATE_LIMIT_STORAGE=redis://redis:6379`
