# FAILURE PATTERNS

Updated: 2026-01-12

Machine-readable failure catalog. **Signal → Check → Fix.**

---

## FP-001: Connection Refused on Port 8000

**Signal:**
```
curl: (7) Failed to connect to localhost port 8000: Connection refused
```

**Check:**
```bash
docker ps | grep -E "outpace|fastapi"    # Is container running?
netstat -an | grep 8000                   # Is port listening?
```

**Fix:**
```bash
docker-compose up -d
# OR
MONGO_URL=mongodb://localhost:27017 DB_NAME=outpace_intelligence JWT_SECRET=REPLACE_WITH_LOCAL_JWT_SECRET python -m uvicorn backend.server:app --port 8000
```

---

## FP-002: 401 Unauthorized on Valid Credentials

**Signal:**
```
HTTP 401 - {"detail": "Invalid token"}
HTTP 401 - {"detail": "Token expired"}
```

**Check:**
```bash
echo $JWT_SECRET                          # What secret is test using?
grep JWT_SECRET backend/.env              # What secret is server using?
# Must match exactly
```

**Fix:**
```bash
export JWT_SECRET=REPLACE_WITH_LOCAL_JWT_SECRET
# Restart server with same secret
```

---

## FP-003: 404 Not Found on Tenant Operations

**Signal:**
```
HTTP 404 - {"detail": "Tenant not found"}
```

**Check:**
```bash
# Check if tenant exists in DB
mongo outpace_intelligence --eval 'db.tenants.find({id: "YOUR-UUID"}).pretty()'

# Check UUID format (must be RFC 4122)
echo "YOUR-UUID" | grep -E '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
```

**Fix:**
```bash
# Re-seed tenants
python scripts/seed_carfax_tenants.py
```

---

## FP-004: Cross-Tenant Data Leakage (SILENT - HTTP 200)

**Signal:**
```
# No obvious error - data from wrong tenant returned
# Check RAG audit logs for mismatch
grep "\[rag.audit\]" /var/log/supervisor/backend.err.log | tail -50
```

**Check:**
```bash
# Audit: Find queries missing tenant_id filter
grep -rn "find(" backend/routes/ | grep -v "tenant_id"

# DB: Check for orphaned data
mongo outpace_intelligence --eval 'db.opportunities.find({tenant_id: {$nin: db.tenants.distinct("id")}})'
```

**Fix:**
```python
# Add tenant_id filter to query
{"tenant_id": tenant_id, ...}  # ALWAYS include tenant_id
```

---

## FP-005: Chat Quota Exceeded Returns 429

**Signal:**
```
HTTP 429 - {"detail": "Monthly message limit exceeded"}
```

**Check:**
```bash
# Compare declared vs actual usage
mongo outpace_intelligence --eval '
db.tenants.find({}, {chat_usage: 1, id: 1}).forEach(t => {
  actual = db.chat_turns.countDocuments({tenant_id: t.id})
  print(t.id, "declared:", t.chat_usage?.messages_used, "actual:", actual)
})'
```

**Fix:**
```bash
# Reset quota for tenant
mongo outpace_intelligence --eval 'db.tenants.updateOne({id: "TENANT-UUID"}, {$set: {"chat_usage.messages_used": 0}})'
```

---

## FP-006: RAG Document Stuck in "processing"

**Signal:**
```
kb_documents.status = "processing" indefinitely
503 errors on chat for affected tenant
```

**Check:**
```bash
# Find stuck documents
mongo outpace_intelligence --eval 'db.kb_documents.find({status: "processing"})'

# Check Mistral API key
grep MISTRAL_API_KEY backend/.env
```

**Fix:**
```bash
# Delete stuck document and orphaned chunks
mongo outpace_intelligence --eval 'db.kb_documents.deleteOne({id: "DOC-ID", status: "processing"})'
mongo outpace_intelligence --eval 'db.kb_chunks.deleteMany({document_id: "DOC-ID"})'
```

---

## FP-007: WSL Cannot Reach localhost:8000

**Signal:**
```
curl: (7) Failed to connect to localhost port 8000
# But server IS running on Windows
```

**Check:**
```bash
# From Windows PowerShell - works:
curl http://localhost:8000/health

# From WSL - fails with localhost, works with host.docker.internal
curl http://host.docker.internal:8000/health
```

**Fix:**
```bash
# In WSL, use host.docker.internal
export API_URL=http://host.docker.internal:8000
```

---

## FP-008: Test Harness Fails Before First Test

**Signal:**
```
carfax.sh exits early with "Tenant not found" or "401 Unauthorized"
```

**Check:**
```bash
# Is server running?
curl -s http://localhost:8000/health

# Are fixtures seeded?
mongo outpace_intelligence --eval 'db.tenants.countDocuments()'
mongo outpace_intelligence --eval 'db.users.countDocuments()'
```

**Fix:**
```bash
# Seed fixtures first
python scripts/seed_carfax_tenants.py
python scripts/seed_carfax_users.py
# Then run harness
bash carfax.sh
```

---

## Emergency Commands

```bash
# Disable all chat (nuclear)
mongo outpace_intelligence --eval 'db.tenants.updateMany({}, {$set: {"chat_policy.enabled": false}})'

# Disable all RAG (nuclear)
mongo outpace_intelligence --eval 'db.tenants.updateMany({}, {$set: {"rag_policy.enabled": false}})'

# Restart backend
sudo supervisorctl restart backend
# OR locally:
# Kill and restart uvicorn

# Check all audit logs
grep "\[rag.audit\]" /var/log/supervisor/backend.err.log | tail -50
grep "\[tenant.audit\]" /var/log/supervisor/backend.err.log | tail -50
grep "\[quota\]" /var/log/supervisor/backend.err.log | tail -50
```

---

## FP-009: Windows Tilde (~) Path Expansion Fails

**Signal:**
```
python: can't open file 'c:\Projects\...\~\.claude\hooks\script.py': [Errno 2] No such file or directory
```

**Check:**
```bash
# The hook config uses ~ which doesn't expand on Windows
cat ~/.claude/settings.json | grep "command"
# Shows: "python ~/.claude/hooks/script.py"
```

**Fix:**
```bash
# Replace ~ with absolute path in ~/.claude/settings.json
# WRONG: "python ~/.claude/hooks/session_start.py"
# RIGHT: "python C:/Users/USERNAME/.claude/hooks/session_start.py"
```

**Root Cause:** Python on Windows doesn't expand `~` like Unix shells. When Claude Code invokes `python ~/.claude/hooks/script.py`, Python tries to open a literal file named `~/.claude/...` relative to the current working directory.

---

## Secrets Discipline

**NEVER print full secret values.** Safe check:
```bash
JWT=$(grep JWT_SECRET backend/.env | cut -d= -f2)
echo "JWT_SECRET: ${JWT:+SET}...${JWT: -4}"
```

**If secret printed anywhere:** ROTATE IMMEDIATELY.

---

## FP-010: Stop Hook Feedback Loop (Infinite Agent Cycling)

**Signal:**
```
Agent responds 97+ times in a row without completing
Each response is minimal (1-2 sentences)
Hook fires repeatedly, never exits
```

**Check:**
```bash
# Does the Stop hook inject additionalContext?
cat ~/.claude/hooks/session_stop.py | grep -i "additionalContext"
```

**Fix:**
```python
# WRONG - causes feedback loop:
print(json.dumps({
    "decision": "approve",
    "additionalContext": "Remember to update PROJECT_MEMORY.md..."
}))

# RIGHT - silent approval only:
print(json.dumps({"decision": "approve"}))
```

**Root Cause:** When a Stop hook injects `additionalContext`, the agent responds to that context. The response triggers another Stop event, which fires the hook again, injecting more context, causing another response, ad infinitum.

**Rule:** Stop hooks must be SILENT. Never inject prompts or reminders via `additionalContext` on Stop events.

---

## FP-011: Dead Code - Function Without Route Decorator

**Signal:**
```
HTTP 404 on endpoint that "should" exist
Function appears in code with auth guards but doesn't respond
```

**Check:**
```bash
# Find functions with Depends() that might be missing decorators
grep -B3 "Depends(get_current" backend/routes/*.py | grep -A1 "async def"
# Look for "async def" NOT preceded by "@router"
```

**Fix:**
```python
# Add the missing route decorator BEFORE the function
@router.get("/endpoint/{param}")  # <-- MISSING
async def some_function(
    param: str,
    current_user: TokenData = Depends(get_current_user)  # Auth exists
):
```

**Root Cause:** FastAPI requires explicit route decorators. A function with `Depends(get_current_user)` but no `@router.get/post/patch/delete` is dead code - properly secured but never exposed.

**Detected:** 2026-01-12 audit found `sync.get_sync_status()` with auth guards but no decorator.

---

## FP-012: Inconsistent Unknown Field Handling

**Signal:**
```
# Some PATCH endpoints log unknown fields, others reject with 400
# Potential security: client can probe for field names
```

**Check:**
```bash
# Find PATCH handlers and check for unknown field handling
grep -A30 "@router.patch" backend/routes/*.py | grep -E "(unknown|allowed_fields|400)"
```

**Fix:**
```python
# CONSISTENT pattern - REJECT unknown fields:
allowed_fields = {"field1", "field2"}
unknown = set(data.keys()) - allowed_fields
if unknown:
    raise HTTPException(400, detail=f"Unknown fields: {list(unknown)}")
```

**Root Cause:** Inconsistent error handling across routes. Some routes logged unknown fields (silent), others rejected (loud). Silent handling violates fail-loud contract.

**Detected:** 2026-01-12 audit found `intelligence.py` PATCH using `[audit.patch_ignored]` instead of HTTP 400.
