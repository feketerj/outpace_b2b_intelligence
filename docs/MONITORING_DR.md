# Monitoring & Disaster Recovery Guide

**OutPace B2B Intelligence Platform**
Last Updated: 2026-01-15

---

## Table of Contents

1. [Monitoring Architecture](#monitoring-architecture)
2. [Metrics & Instrumentation](#metrics--instrumentation)
3. [Alerting Configuration](#alerting-configuration)
4. [Log Aggregation](#log-aggregation)
5. [Disaster Recovery](#disaster-recovery)
6. [Business Continuity](#business-continuity)

---

## Monitoring Architecture

### Recommended Stack

```
┌──────────────────────────────────────────────────────────────┐
│                     Observability Stack                       │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │  Prometheus │───▶│   Grafana   │───▶│  PagerDuty  │       │
│  │   (Metrics) │    │ (Dashboards)│    │  (Alerts)   │       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
│         ▲                                                     │
│         │                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │   OutPace   │───▶│    Loki     │───▶│   Grafana   │       │
│  │     API     │    │   (Logs)    │    │ (Log View)  │       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Alternative Stacks

| Stack | Pros | Cons | Best For |
|-------|------|------|----------|
| Prometheus + Grafana | Open source, flexible | Self-managed | Teams with DevOps |
| Datadog | All-in-one, easy setup | Cost at scale | Fast deployment |
| New Relic | APM focus, AI insights | Complex pricing | Performance tuning |
| AWS CloudWatch | Native AWS integration | Limited customization | AWS-heavy stacks |

---

## Metrics & Instrumentation

### Application Metrics to Track

#### API Health Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `http_requests_total` | Counter | Total HTTP requests | - |
| `http_request_duration_seconds` | Histogram | Request latency | p99 > 5s |
| `http_requests_errors_total` | Counter | 4xx/5xx responses | > 5% of traffic |
| `active_connections` | Gauge | Current connections | > 80% of pool |

#### Business Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `opportunities_synced_total` | Counter | Synced opportunities | 0 for 24h |
| `chat_messages_total` | Counter | Chat interactions | Anomaly detection |
| `quota_exhaustion_events` | Counter | Quota exceeded | > 10/hour |
| `export_requests_total` | Counter | Export operations | - |

#### External Service Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|-----------------|
| `external_api_latency_seconds` | Histogram | HigherGov/Perplexity/Mistral | p95 > 10s |
| `circuit_breaker_state` | Gauge | 0=closed, 1=open | Any open > 5min |
| `external_api_errors_total` | Counter | External failures | > 10/5min |

### Prometheus Integration

Add to `backend/server.py`:

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

# Metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)
ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    ACTIVE_CONNECTIONS.inc()
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    ACTIVE_CONNECTIONS.dec()

    return response

@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

### Prometheus Scrape Config

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'outpace-api'
    scrape_interval: 15s
    static_configs:
      - targets: ['outpace-api:8000']
    metrics_path: '/metrics'
```

---

## Alerting Configuration

### Critical Alerts (P1 - Immediate Response)

```yaml
# alert_rules.yml
groups:
  - name: outpace-critical
    rules:
      - alert: APIDown
        expr: up{job="outpace-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "OutPace API is down"
          description: "API has been unreachable for > 1 minute"

      - alert: DatabaseUnreachable
        expr: mongodb_up == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "MongoDB is unreachable"

      - alert: HighErrorRate
        expr: rate(http_requests_errors_total[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Error rate > 5%"
```

### High Priority Alerts (P2 - 1 Hour Response)

```yaml
      - alert: HighLatency
        expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 5
        for: 10m
        labels:
          severity: high
        annotations:
          summary: "p99 latency > 5 seconds"

      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state == 1
        for: 5m
        labels:
          severity: high
        annotations:
          summary: "Circuit breaker open for external service"

      - alert: SyncFailure
        expr: increase(sync_errors_total[1h]) > 0
        labels:
          severity: high
        annotations:
          summary: "Sync job failed"
```

### Warning Alerts (P3 - 4 Hour Response)

```yaml
      - alert: DiskSpaceWarning
        expr: node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.2
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Disk space < 20%"

      - alert: MemoryWarning
        expr: node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes < 0.2
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Available memory < 20%"
```

### PagerDuty Integration

```yaml
# alertmanager.yml
global:
  pagerduty_url: 'https://events.pagerduty.com/v2/enqueue'

route:
  receiver: 'pagerduty-critical'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
    - match:
        severity: high
      receiver: 'pagerduty-high'
    - match:
        severity: warning
      receiver: 'slack-warnings'

receivers:
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '<PAGERDUTY_SERVICE_KEY>'
        severity: critical

  - name: 'pagerduty-high'
    pagerduty_configs:
      - service_key: '<PAGERDUTY_SERVICE_KEY>'
        severity: error

  - name: 'slack-warnings'
    slack_configs:
      - api_url: '<SLACK_WEBHOOK_URL>'
        channel: '#outpace-alerts'
```

---

## Log Aggregation

### Structured Logging Format

All logs follow this JSON structure:

```json
{
  "timestamp": "2026-01-15T12:00:00Z",
  "level": "INFO",
  "trace_id": "abc123",
  "tenant_id": "tenant-uuid",
  "message": "Operation completed",
  "context": {
    "endpoint": "/api/opportunities",
    "method": "GET",
    "duration_ms": 45
  }
}
```

### Loki Integration

```yaml
# docker-compose.monitoring.yml
services:
  loki:
    image: grafana/loki:2.9.0
    ports:
      - "3100:3100"
    volumes:
      - ./loki-config.yml:/etc/loki/config.yml
    command: -config.file=/etc/loki/config.yml

  promtail:
    image: grafana/promtail:2.9.0
    volumes:
      - ./promtail-config.yml:/etc/promtail/config.yml
      - ./backend/logs:/var/log/outpace:ro
    command: -config.file=/etc/promtail/config.yml
```

### Promtail Configuration

```yaml
# promtail-config.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: outpace
    static_configs:
      - targets:
          - localhost
        labels:
          job: outpace
          __path__: /var/log/outpace/*.log
    pipeline_stages:
      - json:
          expressions:
            level: level
            trace_id: trace_id
            tenant_id: tenant_id
      - labels:
          level:
          trace_id:
          tenant_id:
```

### Useful LogQL Queries

```logql
# All errors in last hour
{job="outpace"} |= "ERROR" | json

# Errors for specific tenant
{job="outpace", tenant_id="abc123"} |= "ERROR"

# Slow requests (>1s)
{job="outpace"} | json | duration_ms > 1000

# Rate limit hits
{job="outpace"} |= "rate_limit_exceeded"

# Circuit breaker events
{job="outpace"} |= "circuit"

# Auth failures
{job="outpace"} |= "401" or |= "Unauthorized"
```

---

## Disaster Recovery

### Recovery Point Objective (RPO)

| Data Type | RPO | Backup Frequency |
|-----------|-----|------------------|
| User data | 1 hour | Hourly incremental |
| Opportunities | 4 hours | 4-hour snapshots |
| Config/tenants | 15 minutes | Continuous replication |

### Recovery Time Objective (RTO)

| Scenario | RTO | Procedure |
|----------|-----|-----------|
| Single service failure | 5 min | Auto-restart via Docker |
| Database corruption | 30 min | Restore from backup |
| Full infrastructure loss | 4 hours | DR site activation |
| Region-wide outage | 8 hours | Cross-region failover |

### Backup Strategy

#### Automated Backups

```bash
#!/bin/bash
# /scripts/backup.sh

BACKUP_DIR="/backup/mongodb"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
mongodump --uri="$MONGO_URL" \
    --db=outpace_intelligence \
    --out="$BACKUP_DIR/$DATE" \
    --gzip

# Upload to S3
aws s3 sync "$BACKUP_DIR/$DATE" \
    "s3://outpace-backups/mongodb/$DATE/" \
    --storage-class STANDARD_IA

# Cleanup old backups
find "$BACKUP_DIR" -type d -mtime +$RETENTION_DAYS -exec rm -rf {} +

# Verify backup integrity
mongorestore --uri="$MONGO_URL" \
    --db=outpace_verify \
    --drop \
    --gzip \
    "$BACKUP_DIR/$DATE/outpace_intelligence/"

# Cleanup verification DB
mongosh --eval "db.getSiblingDB('outpace_verify').dropDatabase()"
```

#### Cron Schedule

```cron
# Hourly incremental
0 * * * * /scripts/backup.sh incremental >> /var/log/backup.log 2>&1

# Daily full backup
0 2 * * * /scripts/backup.sh full >> /var/log/backup.log 2>&1

# Weekly integrity check
0 3 * * 0 /scripts/backup.sh verify >> /var/log/backup.log 2>&1
```

### Recovery Procedures

#### Scenario 1: Database Corruption

```bash
# 1. Stop API
docker compose stop api

# 2. Identify last good backup
aws s3 ls s3://outpace-backups/mongodb/ --recursive | tail -10

# 3. Download backup
aws s3 sync s3://outpace-backups/mongodb/20260115_020000/ /restore/

# 4. Restore
mongorestore --uri="$MONGO_URL" \
    --db=outpace_intelligence \
    --drop \
    --gzip \
    /restore/outpace_intelligence/

# 5. Verify data
mongosh outpace_intelligence --eval "db.tenants.countDocuments()"
mongosh outpace_intelligence --eval "db.opportunities.countDocuments()"

# 6. Restart API
docker compose start api

# 7. Verify health
curl http://localhost:8000/health
```

#### Scenario 2: Complete Infrastructure Loss

```bash
# 1. Provision new infrastructure
terraform apply -target=module.outpace_dr

# 2. Configure DNS failover (if not automatic)
aws route53 change-resource-record-sets \
    --hosted-zone-id $ZONE_ID \
    --change-batch file://dns-failover.json

# 3. Restore database from S3
aws s3 sync s3://outpace-backups/mongodb/latest/ /restore/
mongorestore --uri="$DR_MONGO_URL" --gzip /restore/

# 4. Deploy application
docker compose -f docker-compose.dr.yml up -d

# 5. Verify services
./scripts/verify_dr.sh
```

#### Scenario 3: Secret Compromise

```bash
# 1. Rotate JWT_SECRET immediately
NEW_SECRET=$(openssl rand -base64 32)
echo "JWT_SECRET=$NEW_SECRET" >> .env.new

# 2. Rotate all API keys
# - HigherGov: Generate new in portal
# - Perplexity: Generate new in portal
# - Mistral: Generate new in portal

# 3. Update secrets in vault/env
# 4. Deploy with new secrets
docker compose down
docker compose up -d

# 5. Invalidate all existing sessions
# (Users will need to re-authenticate)

# 6. Audit access logs for suspicious activity
grep "JWT" backend/logs/server.log | grep -v "$(date +%Y-%m-%d)"
```

---

## Business Continuity

### Service Dependencies

```
┌────────────────────────────────────────────────────────────┐
│                    Dependency Map                           │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Critical (Service stops without):                          │
│  ├── MongoDB (data storage)                                 │
│  └── JWT_SECRET (authentication)                            │
│                                                             │
│  Degraded (Partial functionality):                          │
│  ├── HigherGov API (sync disabled)                          │
│  ├── Perplexity API (intelligence disabled)                 │
│  └── Mistral API (chat disabled)                            │
│                                                             │
│  Non-Critical (Monitoring only):                            │
│  ├── Prometheus (metrics)                                   │
│  ├── Loki (logs)                                            │
│  └── Grafana (dashboards)                                   │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### Graceful Degradation

When external services fail, the platform continues operating:

| Service Down | Impact | User Message |
|--------------|--------|--------------|
| HigherGov | No new sync data | "Sync temporarily unavailable" |
| Perplexity | No intelligence | "Intelligence generation unavailable" |
| Mistral | No chat | "Chat assistant unavailable" |
| All external | Core CRUD works | "Some features temporarily unavailable" |

### Communication Templates

#### Incident Start

```
Subject: [INCIDENT] OutPace Platform - {Service} Degraded

Status: Investigating
Impact: {Description of user impact}
Start Time: {UTC timestamp}

We are aware of issues affecting {service}. Our team is actively investigating.

Updates will be provided every 30 minutes until resolution.
```

#### Incident Update

```
Subject: [UPDATE] OutPace Platform - {Service} Degraded

Status: Identified / Mitigating
Root Cause: {Brief description}
ETA: {Estimated resolution time}

Current workarounds: {If applicable}

Next update in 30 minutes.
```

#### Incident Resolved

```
Subject: [RESOLVED] OutPace Platform - {Service} Restored

Status: Resolved
Duration: {X hours Y minutes}
Root Cause: {Description}
Resolution: {What was done}

A post-incident review will be conducted and shared within 48 hours.
```

### Post-Incident Review Template

```markdown
# Post-Incident Review: {Incident Title}

**Date:** {Date}
**Duration:** {Duration}
**Severity:** P{1-4}
**Author:** {Name}

## Summary
{2-3 sentence summary of what happened}

## Timeline
| Time (UTC) | Event |
|------------|-------|
| HH:MM | First alert fired |
| HH:MM | On-call acknowledged |
| HH:MM | Root cause identified |
| HH:MM | Mitigation applied |
| HH:MM | Service restored |

## Root Cause
{Detailed technical explanation}

## Impact
- Users affected: {Number/percentage}
- Duration: {Time}
- Data loss: {Yes/No, details}

## What Went Well
- {Item 1}
- {Item 2}

## What Went Poorly
- {Item 1}
- {Item 2}

## Action Items
| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| {Action} | {Name} | {Date} | Open |

## Lessons Learned
{Key takeaways to prevent recurrence}
```

---

## Quick Reference Card

### Health Check Commands

```bash
# API health
curl http://localhost:8000/health

# MongoDB status
docker exec -it mongo-b2b mongosh --eval "db.adminCommand('ping')"

# Container status
docker compose ps

# Recent errors
grep ERROR backend/logs/errors.log | tail -20

# Circuit breaker status
grep "circuit" backend/logs/server.log | tail -10
```

### Emergency Contacts

| Role | Primary | Backup |
|------|---------|--------|
| On-Call | {Phone} | {Phone} |
| Database Admin | {Phone} | {Phone} |
| Security | {Email} | {Email} |

### Escalation Path

```
L1: On-Call Engineer (0-15 min)
    ↓
L2: Team Lead (15-30 min)
    ↓
L3: Engineering Manager (30-60 min)
    ↓
L4: VP Engineering (Critical only)
```
