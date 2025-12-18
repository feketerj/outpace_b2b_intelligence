# OutPace Intelligence - Failure Modes Runbook

**Production Status:** Live  
**Active Clients:** 20  
**Generated:** 2025-12-18  
**Assumptions:** One tenant is adversarial, one is careless, one is unlucky

---

## FM-001: JWT Secret Compromise or Rotation Failure

### Trigger Conditions
- JWT_SECRET exposed in logs, repo, or error messages
- Secret rotation without coordinated token invalidation
- Weak secret (< 32 chars) allows brute-force

### Manifestation
- Unauthorized API access with forged tokens
- Valid users suddenly get 401 on all endpoints
- Tenant A user impersonates Tenant B user

### Blast Radius
- **All tenants affected** (shared secret)
- Full read/write access to any tenant's data
- Chat history, opportunities, intelligence all exposed

### Detection Signals
```yaml
http:
  status_codes: [401, 403]
  endpoints: ["/api/auth/*", "/api/opportunities", "/api/chat/*"]
logs:
  logger_names: ["utils.auth", "routes.auth"]
  patterns: ["Invalid token", "Token expired", "decode error"]
db:
  collections: ["users"]
  queries: "db.users.find({last_login: {$gte: ISODate('...')}}) - spike in new sessions"
metrics: null  # No metrics currently
```

### Immediate Mitigation
1. Rotate JWT_SECRET in `/app/backend/.env`
2. `sudo supervisorctl restart backend`
3. All existing tokens invalidated (users must re-login)

### Rollback Plan
- Restore previous JWT_SECRET from backup
- Restart backend
- Time: ~30 seconds

### Time to Contain
**< 2 minutes** (env change + restart)

### Evidence Links
- Config: `/app/backend/.env` (JWT_SECRET, JWT_ALGORITHM=HS256)
- Auth logic: `/app/backend/utils/auth.py`

---

## FM-002: Cross-Tenant Data Leakage via Missing tenant_id Filter

### Trigger Conditions
- New endpoint added without `tenant_id` filter in query
- Query uses user-supplied ID without tenant validation
- Aggregation pipeline missing `$match` on tenant_id

### Manifestation
- Tenant B sees Tenant A's opportunities/intelligence
- Export contains cross-tenant data
- RAG retrieval returns other tenant's chunks

### Blast Radius
- **Two tenants** (victim + attacker)
- Confidential business data exposed
- Compliance violation (SOC2, etc.)

### Detection Signals
```yaml
http:
  status_codes: [200]  # Silent success is the danger
  endpoints: ["/api/opportunities", "/api/intelligence", "/api/exports/*"]
logs:
  logger_names: ["routes.rag"]
  patterns: ["[rag.audit] tenant_id=X ... used=Y"]  # Cross-check tenant_id vs chunks_used
db:
  collections: ["opportunities", "intelligence", "kb_chunks"]
  queries: |
    # Detect orphaned or mismatched tenant_id
    db.opportunities.find({tenant_id: {$nin: db.tenants.distinct("id")}})
    db.kb_chunks.aggregate([{$group: {_id: "$tenant_id", count: {$sum: 1}}}])
metrics: null
```

### Immediate Mitigation
1. Add `tenant_id` filter to affected query (one-line fix)
2. Audit: `grep -rn "find(" /app/backend/routes/ | grep -v "tenant_id"`

### Rollback Plan
- Revert specific route file via git
- Restart backend
- Time: ~1 minute

### Time to Contain
**< 5 minutes** (identify + hotfix + restart)

### Evidence Links
- Proven isolated: `[rag.audit] tenant_id=8aa521eb... reason=no_chunks searched=0 used=0`
- Export guard: `/app/backend/routes/exports.py:67` - `{"tenant_id": tenant_id}`
- RAG guard: `/app/backend/routes/rag.py:298` - `{"tenant_id": tenant_id}`

---

## FM-003: Chat Quota Bypass via Race Condition

### Trigger Conditions
- Concurrent requests from same tenant before atomic increment completes
- `monthly_message_limit` set but `chat_usage` update fails silently
- Clock skew causes month boundary issues

### Manifestation
- Tenant exceeds paid quota without 429
- `chat_usage.messages_used` doesn't match actual `chat_turns` count
- Billing disputes from customers

### Blast Radius
- **Single tenant** (over-consumer)
- Revenue leakage
- Resource exhaustion if extreme

### Detection Signals
```yaml
http:
  status_codes: [200, 429]
  endpoints: ["/api/chat/message"]
logs:
  logger_names: ["routes.chat"]
  patterns: ["[quota] New month reservation", "[quota] Incremented usage", "[quota] Released reservation"]
db:
  collections: ["tenants", "chat_turns"]
  queries: |
    # Compare declared usage vs actual turns
    db.tenants.find({}, {chat_usage: 1, id: 1}).forEach(t => {
      actual = db.chat_turns.count({tenant_id: t.id, created_at: {$regex: "^2025-12"}})
      print(t.id, "declared:", t.chat_usage?.messages_used, "actual:", actual)
    })
metrics: null
```

### Immediate Mitigation
1. Set `monthly_message_limit: 0` to block all chat
2. Reconcile: Update `chat_usage.messages_used` to actual count
3. Investigate: Check for duplicate `[quota]` log entries at same timestamp

### Rollback Plan
- Reset `chat_usage` to null (fresh start next request)
- Re-enable chat with correct limit
- Time: ~1 minute

### Time to Contain
**< 3 minutes** (disable + reconcile)

### Evidence Links
- Quota enforcement: `/app/backend/routes/chat.py:210-250`
- Proven working: `HTTP 429` on second message with `limit=1`
- Atomic increment: `$inc: {"chat_usage.messages_used": 1}`

---

## FM-004: RAG Embedding Service Failure Leaves Orphaned Documents

### Trigger Conditions
- MISTRAL_API_KEY invalid or rate-limited
- Network timeout during embedding batch
- Partial chunk insertion before error

### Manifestation
- `kb_documents.status = "processing"` stuck indefinitely
- `kb_chunks` has some but not all chunks for a document
- RAG retrieval returns incomplete context
- 503 errors on chat for affected tenant

### Blast Radius
- **Single tenant** (the one ingesting)
- Chat degraded (embed_error fallback)
- Data inconsistency in knowledge base

### Detection Signals
```yaml
http:
  status_codes: [500, 503]
  endpoints: ["/api/tenants/*/rag/documents"]
logs:
  logger_names: ["routes.rag", "routes.chat"]
  patterns: |
    "[rag] Ingestion failed"
    "[rag.audit] ... reason=embed_error"
    "401" in Mistral errors
db:
  collections: ["kb_documents", "kb_chunks"]
  queries: |
    # Find stuck documents
    db.kb_documents.find({status: "processing"})
    # Find orphaned chunks
    db.kb_chunks.aggregate([
      {$group: {_id: "$document_id", count: {$sum: 1}}},
      {$lookup: {from: "kb_documents", localField: "_id", foreignField: "id", as: "doc"}},
      {$match: {"doc.status": {$ne: "ready"}}}
    ])
metrics: null
```

### Immediate Mitigation
1. Delete stuck document: `db.kb_documents.deleteOne({id: "...", status: "processing"})`
2. Delete orphaned chunks: `db.kb_chunks.deleteMany({document_id: "..."})`
3. Verify MISTRAL_API_KEY in `/app/backend/.env`
4. Restart backend

### Rollback Plan
- Re-ingest document after fixing root cause
- Time: ~2 minutes + re-embed time

### Time to Contain
**< 5 minutes** (cleanup + restart)

### Evidence Links
- Cleanup on failure: `/app/backend/routes/rag.py:195-201`
- Embed error handling: `[rag.audit] ... reason=embed_error searched=0 used=0 chars=0`
- Atomicity: Proven BEFORE=0, AFTER=0 on LLM failure

---

## FM-005: Master Tenant Misconfiguration Enables Forbidden Features

### Trigger Conditions
- Direct DB manipulation bypasses API guards
- Migration script sets `is_master_client=true` on wrong tenant
- API bug allows `is_master_client` to be toggled

### Manifestation
- Master tenant suddenly has Chat/RAG/Knowledge tabs
- Or: Regular tenant loses these features unexpectedly
- API returns 403 for legitimate operations

### Blast Radius
- **Single tenant** (misconfigured one)
- Feature access incorrect
- Potential data model corruption if RAG enabled on master

### Detection Signals
```yaml
http:
  status_codes: [403]
  endpoints: ["/api/tenants/*/rag/*", "/api/chat/message"]
logs:
  logger_names: ["routes.tenants"]
  patterns: |
    "chat_policy cannot be modified for master tenants"
    "rag_policy cannot be modified for master tenants"
db:
  collections: ["tenants"]
  queries: |
    # Verify master tenant flags
    db.tenants.find({is_master_client: true}, {name: 1, chat_policy: 1, rag_policy: 1})
    # Should have chat_policy.enabled=false, rag_policy=null or disabled
metrics: null
```

### Immediate Mitigation
1. Fix in DB: `db.tenants.updateOne({id: "..."}, {$set: {is_master_client: false}})`
2. Or disable features: `db.tenants.updateOne({id: "..."}, {$set: {"chat_policy.enabled": false, "rag_policy.enabled": false}})`

### Rollback Plan
- Restore correct `is_master_client` flag
- Time: ~30 seconds

### Time to Contain
**< 1 minute** (single DB update)

### Evidence Links
- Guard: `/app/backend/routes/tenants.py:144-161`
- Proven blocked: `HTTP 403 "rag_policy cannot be modified for master tenants"`
- Current masters: `db.tenants.count({is_master_client: true}) = 1`

---

## 3AM RISK ASSESSMENT

### Risk Title
**Silent Cross-Tenant RAG Chunk Leakage via Future Endpoint Bug**

### Why Most Dangerous Now
- RAG is new code (higher bug probability)
- Cross-tenant leakage is **silent** (HTTP 200, correct-looking response)
- 20 active clients means high probability of sensitive data
- No runtime metrics to detect anomalous retrieval patterns
- Audit log exists but requires manual grep to correlate

### How Detected Today
```bash
# Manual audit - run periodically
tail -n 10000 /var/log/supervisor/backend.err.log | grep "\[rag.audit\]" | \
  awk '{print $5, $7, $8}' | sort | uniq -c | sort -rn

# Expected: Each tenant_id should only have used>0 for their own chunks
# Red flag: tenant_id=X with used>0 but X has 0 chunks in DB
```

**Detection status: POSSIBLE but requires manual correlation**

### Fastest Containment Action
```bash
# Disable RAG for ALL tenants (nuclear option)
cd /app/backend && python3 << 'EOF'
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
async def main():
    c = AsyncIOMotorClient(os.getenv("MONGO_URL"))
    db = c[os.getenv("DB_NAME", "outpace_intelligence")]
    result = await db.tenants.update_many({}, {"$set": {"rag_policy.enabled": False}})
    print(f"Disabled RAG for {result.modified_count} tenants")
    c.close()
asyncio.run(main())
EOF

sudo supervisorctl restart backend
```

**Time to execute: < 30 seconds**

---

## Quick Reference Commands

```bash
# Check all RAG audit logs
grep "\[rag.audit\]" /var/log/supervisor/backend.err.log | tail -50

# Check quota logs
grep "\[quota\]" /var/log/supervisor/backend.err.log | tail -50

# Count chat turns per tenant this month
mongo outpace_intelligence --eval 'db.chat_turns.aggregate([{$match: {created_at: {$regex: "^2025-12"}}}, {$group: {_id: "$tenant_id", count: {$sum: 1}}}])'

# Check for stuck RAG documents
mongo outpace_intelligence --eval 'db.kb_documents.find({status: "processing"})'

# Emergency: Disable all chat
mongo outpace_intelligence --eval 'db.tenants.updateMany({}, {$set: {"chat_policy.enabled": false}})'

# Emergency: Disable all RAG
mongo outpace_intelligence --eval 'db.tenants.updateMany({}, {$set: {"rag_policy.enabled": false}})'

# Restart backend
sudo supervisorctl restart backend
```
