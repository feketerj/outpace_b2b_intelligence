# Operations Runbook

**OutPace B2B Intelligence Platform**
Last Updated: 2026-01-15

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Common Issues](#common-issues)
3. [Incident Response](#incident-response)
4. [Maintenance Tasks](#maintenance-tasks)
5. [Backup & Recovery](#backup--recovery)
6. [Secret Rotation](#secret-rotation)
7. [Scaling](#scaling)
8. [Monitoring](#monitoring)

---

## Quick Reference

### Health Check
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","database":"healthy","timestamp":"..."}
# 503 = database unreachable
```

### Service Status
```bash
docker compose ps                    # All containers
docker logs outpace-api --tail 100   # Backend logs
docker logs mongo-b2b --tail 100     # MongoDB logs
docker logs redis --tail 100         # Redis logs
```

### Key Ports
| Service | Port | Purpose |
|---------|------|---------|
| API | 8000 | FastAPI backend |
| Frontend | 3000 | React dev / 80 production |
| MongoDB | 27017 | Database (internal only) |
| Redis | 6379 | Rate limiting (internal only) |
| Proxy | 443 | TLS termination |

### Log Locations
```
backend/logs/server.log   # All INFO+ logs, 10MB rotating
backend/logs/errors.log   # ERROR only, 5MB rotating
```

---

## Common Issues

### Issue: API returns 503 "degraded"

**Symptoms:** Health check returns `{"status":"degraded","database":"unhealthy: ..."}`

**Cause:** MongoDB connection failed

**Resolution:**
1. Check MongoDB container: `docker ps | grep mongo`
2. If stopped: `docker start mongo-b2b`
3. Check MongoDB logs: `docker logs mongo-b2b --tail 50`
4. Verify connection: `docker exec -it mongo-b2b mongosh --eval "db.adminCommand('ping')"`

### Issue: 401 Unauthorized on all requests

**Symptoms:** Every authenticated request returns 401

**Cause:** JWT_SECRET mismatch between server and tokens

**Resolution:**
1. Check server JWT_SECRET: `docker exec outpace-api env | grep JWT_SECRET`
2. Ensure all instances use same secret
3. If changed, all existing tokens are invalid - users must re-login

### Issue: 429 Too Many Requests

**Symptoms:** Auth endpoints returning 429

**Cause:** Rate limiter triggered (10/minute on auth, 100/minute default)

**Resolution:**
- This is expected behavior - wait 60 seconds
- If legitimate traffic: increase limits in `backend/utils/rate_limit.py`
- If attack: block IP at proxy level

### Issue: Circuit Breaker Open

**Symptoms:** External sync returns "Circuit 'highergov' is open"

**Cause:** HigherGov/Perplexity/Mistral API had 5+ consecutive failures

**Resolution:**
1. Check external API status
2. Wait 60 seconds for auto-recovery
3. Monitor: `grep "circuit" backend/logs/server.log`
4. If API is up but circuit stays open, restart backend

### Issue: Redis Connection Failed

**Symptoms:** Rate limiting not working, or errors mentioning Redis connection

**Cause:** Redis container down or network issue

**Resolution:**
1. Check Redis container: `docker ps | grep redis`
2. If stopped: `docker compose up -d redis`
3. Check Redis logs: `docker logs redis --tail 50`
4. Verify connection: `docker exec -it redis redis-cli ping` (expect: PONG)
5. If Redis is down and cannot recover, temporarily switch to memory storage:
   - Set `RATE_LIMIT_STORAGE=memory://` in environment
   - Note: This disables rate limit sharing across instances

### Issue: Chat quota exceeded

**Symptoms:** Chat returns 429 "Monthly chat limit exceeded"

**Cause:** Tenant hit monthly message limit

**Resolution:**
1. Check current usage:
   ```javascript
   db.tenants.findOne({id: "<tenant_id>"}, {chat_usage: 1})
   ```
2. Reset if needed (billing/support decision):
   ```javascript
   db.tenants.updateOne({id: "<tenant_id>"}, {$set: {"chat_usage.messages_used": 0}})
   ```

### Issue: Sync returns 0 opportunities

**Symptoms:** Manual sync completes but syncs 0 records

**Cause:** Missing API key or search ID configuration

**Resolution:**
1. Check tenant config:
   ```javascript
   db.tenants.findOne({id: "<tenant_id>"}, {search_profile: 1})
   ```
2. Verify `highergov_api_key` and `highergov_search_id` are set
3. Test API key directly: `curl -H "x-api-key: <key>" https://www.highergov.com/api-external/...`

---

## Incident Response

### Severity Levels

| Level | Response Time | Examples |
|-------|--------------|----------|
| P1 - Critical | 15 min | Full outage, data breach, auth broken |
| P2 - High | 1 hour | Partial outage, sync failures, performance degraded |
| P3 - Medium | 4 hours | Non-critical feature broken, single tenant affected |
| P4 - Low | 24 hours | UI bug, documentation issue |

### P1 Response Checklist

1. **Acknowledge** - Note start time
2. **Assess** - What's broken? Who's affected?
3. **Communicate** - Notify stakeholders
4. **Mitigate** - Restore service (even partial)
5. **Investigate** - Find root cause
6. **Resolve** - Permanent fix
7. **Document** - Post-incident review

### Service Restart Procedure

```bash
# Graceful restart (preserves connections)
docker compose restart api

# Full restart (if graceful fails)
docker compose down api
docker compose up -d api

# Nuclear option (full stack restart)
docker compose down
docker compose up -d
```

### Database Recovery (if corrupted)

```bash
# Stop services
docker compose stop api

# Restore from backup
mongorestore --uri="mongodb://localhost:27017" --db=outpace_intelligence /path/to/backup/

# Restart
docker compose start api
```

---

## Maintenance Tasks

### Daily
- [ ] Check health endpoint
- [ ] Review error logs: `grep ERROR backend/logs/errors.log | tail -50`
- [ ] Verify sync jobs completed

### Weekly
- [ ] Review rate limit hits
- [ ] Check disk space: `df -h`
- [ ] Review circuit breaker trips: `grep "circuit.*OPEN" backend/logs/server.log`

### Monthly
- [ ] Rotate logs (automatic if < 10MB)
- [ ] Review and archive old carfax reports
- [ ] Update dependencies (security patches)
- [ ] Test backup restoration

### Quarterly
- [ ] Rotate API keys (HigherGov, Perplexity, Mistral)
- [ ] Review rate limit thresholds
- [ ] Performance baseline comparison
- [ ] Security audit

---

## Backup & Recovery

### MongoDB Backup

```bash
# Manual backup
mongodump --uri="mongodb://localhost:27017" --db=outpace_intelligence --out=/backup/$(date +%Y%m%d)

# Automated (add to cron)
0 2 * * * mongodump --uri="mongodb://localhost:27017" --db=outpace_intelligence --out=/backup/$(date +\%Y\%m\%d) --gzip
```

### Backup Retention
- Daily: Keep 7 days
- Weekly: Keep 4 weeks
- Monthly: Keep 12 months

### Restore Procedure

```bash
# 1. Stop API
docker compose stop api

# 2. Restore (replace existing)
mongorestore --uri="mongodb://localhost:27017" --db=outpace_intelligence --drop /backup/YYYYMMDD/outpace_intelligence/

# 3. Verify
docker exec -it mongo-b2b mongosh outpace_intelligence --eval "db.tenants.countDocuments()"

# 4. Restart API
docker compose start api

# 5. Verify health
curl http://localhost:8000/health
```

---

## Secret Rotation

### JWT_SECRET Rotation

**Impact:** All existing sessions invalidated, users must re-login

```bash
# 1. Generate new secret
NEW_SECRET=$(openssl rand -base64 32)

# 2. Update .env
sed -i "s/JWT_SECRET=.*/JWT_SECRET=$NEW_SECRET/" .env

# 3. Restart API
docker compose restart api

# 4. Verify
curl http://localhost:8000/health
```

### API Key Rotation (HigherGov, Perplexity, Mistral)

**Impact:** Sync/chat will fail until updated

```bash
# 1. Get new key from provider
# 2. Update .env
# 3. Restart API
docker compose restart api

# 4. Test sync
curl -X POST http://localhost:8000/api/admin/sync/<tenant_id>?sync_type=opportunities \
  -H "Authorization: Bearer <admin_token>"
```

### Per-Tenant API Key Update

```javascript
// In MongoDB shell
db.tenants.updateOne(
  {id: "<tenant_id>"},
  {$set: {"search_profile.highergov_api_key": "<new_key>"}}
)
```

---

## Scaling

### Horizontal Scaling (Multiple API Instances)

**Prerequisites:**
- Redis for rate limit storage (currently memory-based)
- Load balancer (nginx/HAProxy)

```yaml
# docker-compose.override.yml
services:
  api:
    deploy:
      replicas: 3
```

**Note:** Rate limiting uses memory storage by default. For multi-instance, configure Redis:
```python
# backend/utils/rate_limit.py
storage_uri=os.environ.get("RATE_LIMIT_STORAGE", "redis://redis:6379")
```

### Vertical Scaling

```yaml
# docker-compose.override.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

### MongoDB Scaling

For production with transactions, use replica set:
```bash
# See MongoDB documentation for replica set setup
# Current: Standalone (no transactions)
```

---

## Monitoring

### Key Metrics to Monitor

| Metric | Warning | Critical | Check |
|--------|---------|----------|-------|
| API Response Time | >1s | >5s | `/health` latency |
| Error Rate | >1% | >5% | `grep ERROR logs/errors.log | wc -l` |
| MongoDB Connections | >40 | >50 | Pool exhaustion |
| Disk Usage | >80% | >90% | `df -h` |
| Memory Usage | >80% | >90% | `docker stats` |

### Log Search Patterns

```bash
# Find all errors for a request
grep "trace=<trace_id>" backend/logs/server.log

# Find quota-related issues
grep "quota" backend/logs/server.log

# Find circuit breaker events
grep "circuit" backend/logs/server.log

# Find rate limit hits
grep "429\|rate" backend/logs/server.log
```

### Alerting Setup (External Integration Required)

Recommended tools:
- **Prometheus + Grafana** - Metrics and dashboards
- **PagerDuty / OpsGenie** - Incident management
- **ELK Stack** - Log aggregation

Integration points:
- Health endpoint: `GET /health` (returns 503 on issues)
- Error notifications: Configure `ERROR_EMAIL_*` env vars
- Log files: `backend/logs/*.log`

---

## Emergency Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| On-Call Engineer | TBD | P1: Immediate |
| Backend Lead | TBD | P1/P2 |
| Infrastructure | TBD | P1 |
| Product Owner | TBD | P1 (comms) |

---

## Appendix: Environment Variables

```bash
# Required
MONGO_URL=mongodb://localhost:27017
DB_NAME=outpace_intelligence
JWT_SECRET=<min-32-chars>

# External APIs
HIGHERGOV_API_KEY=<key>
PERPLEXITY_API_KEY=<key>
MISTRAL_API_KEY=<key>

# Optional
CORS_ORIGINS=http://localhost:3000
ENVIRONMENT=production
ERROR_EMAIL_TO=admin@example.com
RATE_LIMIT_STORAGE=memory://  # or redis://redis:6379
```
