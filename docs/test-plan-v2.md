# B2B INTELLIGENCE DASHBOARD - COMPREHENSIVE TEST PLAN
## Version 2.0 - December 2025
## PRODUCTION-GRADE

---

## 1. EXECUTIVE SUMMARY

| Metric | Current | Target |
|--------|---------|--------|
| Line Coverage | 29% | 95% |
| Statements Covered | 656 | 2,115 |
| Categories | 12 | 12 |
| Strata per Category | 6 | 6 |
| Total Strata | 72 | 72 |
| Estimated Tests | — | 432 |
| Monte Carlo Runs/Stratum | — | 59 |
| **Total Executions** | — | **25,488** |

---

## 2. TEST ARCHITECTURE

### 2.1 Structure

```
CATEGORY (functional area / route file)
├── HAPPY     — Baseline functionality works
├── BOUNDARY  — Edge cases, limits, transitions
├── INVALID   — Bad inputs, malformed data, unauthorized
├── EMPTY     — Null, missing, zero-length inputs
├── PERFORMANCE — Timing, load, concurrency
└── FAILURE   — External service failures, recovery paths
```

### 2.2 Monte Carlo Confidence

- **59 runs** of each stratum = 95% confidence (p<0.05)
- Zero failures required for confidence claim
- Each stratum is an independent unit of analysis
- Categories × Strata × 59 = Total executions

### 2.3 Categories (12)

| # | Category | Route File | Endpoints | Stmts | Current | Target |
|---|----------|------------|-----------|-------|---------|--------|
| 1 | Auth | routes/auth.py | 3 | 45 | 38% | 95% |
| 2 | Tenants | routes/tenants.py | 8 | 188 | 19% | 95% |
| 3 | Chat | routes/chat.py | 4 | 211 | 13% | 95% |
| 4 | Opportunities | routes/opportunities.py | 5 | 112 | 23% | 95% |
| 5 | Intelligence | routes/intelligence.py | 5 | 81 | 27% | 95% |
| 6 | Exports | routes/exports.py | 2 | 145 | 17% | 95% |
| 7 | Upload | routes/upload.py | 2 | 94 | 21% | 95% |
| 8 | Sync | routes/sync.py | 2 | 72 | 19% | 95% |
| 9 | Config | routes/config.py | 2 | 62 | 24% | 95% |
| 10 | Admin | routes/admin.py | 3 | 67 | 22% | 95% |
| 11 | Users | routes/users.py | 5 | 87 | 24% | 95% |
| 12 | RAG | routes/rag.py | 4 | 191 | 16% | 95% |

### 2.4 Services (Mocks Required)

| Service | File | Stmts | Current | Purpose |
|---------|------|-------|---------|---------|
| HigherGov | services/highergov_service.py | 162 | 8% | External opportunity data |
| Mistral | services/mistral_service.py | 65 | 12% | LLM chat completions |
| Perplexity | services/perplexity_service.py | 75 | 13% | LLM intelligence |

---

## 3. TEST INFRASTRUCTURE

### 3.1 Docker Compose Test Environment

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  test-mongo:
    image: mongo:7
    ports:
      - "27018:27017"
    environment:
      MONGO_INITDB_DATABASE: outpace_test
    volumes:
      - ./scripts/seed_test_data.js:/docker-entrypoint-initdb.d/seed.js:ro
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 5s
      timeout: 5s
      retries: 5

  mock-highergov:
    build: ./mocks/highergov
    ports:
      - "8081:8081"
    environment:
      CHAOS_ENABLED: "true"
      CHAOS_LATENCY_MIN_MS: 50
      CHAOS_LATENCY_MAX_MS: 200
      CHAOS_FAILURE_RATE: 0.02
      CHAOS_TIMEOUT_RATE: 0.01

  mock-mistral:
    build: ./mocks/mistral
    ports:
      - "8082:8082"
    environment:
      CHAOS_ENABLED: "true"
      CHAOS_LATENCY_MIN_MS: 100
      CHAOS_LATENCY_MAX_MS: 500
      CHAOS_FAILURE_RATE: 0.02
      CHAOS_RATE_LIMIT_RATE: 0.01

  mock-perplexity:
    build: ./mocks/perplexity
    ports:
      - "8083:8083"
    environment:
      CHAOS_ENABLED: "true"
      CHAOS_LATENCY_MIN_MS: 100
      CHAOS_LATENCY_MAX_MS: 500
      CHAOS_FAILURE_RATE: 0.02

  api:
    build: ./backend
    ports:
      - "8001:8000"
    environment:
      MONGO_URL: mongodb://test-mongo:27017
      DB_NAME: outpace_test
      JWT_SECRET: test-secret-key-12345
      HIGHERGOV_API_URL: http://mock-highergov:8081
      MISTRAL_API_URL: http://mock-mistral:8082
      PERPLEXITY_API_URL: http://mock-perplexity:8083
      ENVIRONMENT: test
    depends_on:
      test-mongo:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  test-runner:
    build:
      context: .
      dockerfile: Dockerfile.test
    environment:
      API_URL: http://api:8000
    depends_on:
      api:
        condition: service_healthy
    volumes:
      - ./carfax_reports:/app/carfax_reports
```

### 3.2 Seed Data Requirements

#### 3.2.1 Tenants (6 canonical)

| ID | Slug | Name | Purpose | Expected State |
|----|------|------|---------|----------------|
| 8aa521eb-56ad-4727-8f09-c01fc7921c21 | tenant-a | Tenant A | Primary test tenant | Active, all features enabled |
| e4e0b3b4-90ec-4c32-88d8-534aa563ed5d | tenant-b | Tenant B | Cross-tenant isolation | Active, separate data |
| 00000000-0000-0000-0000-000000000001 | tenant-expired | Expired Tenant | Subscription tests | subscription_end = yesterday |
| 00000000-0000-0000-0000-000000000002 | tenant-noquota | No Quota Tenant | Quota exhaustion | chat_quota = 0 |
| 00000000-0000-0000-0000-000000000003 | tenant-disabled | Disabled Tenant | Feature toggle tests | All features disabled |
| 00000000-0000-0000-0000-000000000004 | tenant-norag | No RAG Tenant | RAG disabled tests | rag_enabled = false |

#### 3.2.2 Users (12 canonical)

| ID | Email | Password | Role | Tenant | Purpose |
|----|-------|----------|------|--------|---------|
| USR-001 | admin@example.com | REDACTED_ADMIN_PASSWORD | super_admin | None | Super admin operations |
| USR-002 | admin-a@test.com | REDACTED_TEST_PASSWORD | tenant_admin | tenant-a | Tenant A admin |
| USR-003 | admin-b@test.com | REDACTED_TEST_PASSWORD | tenant_admin | tenant-b | Tenant B admin |
| USR-004 | user-a@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-a | Regular user A |
| USR-005 | user-b@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-b | Regular user B |
| USR-006 | inactive@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-a | is_active = false |
| USR-007 | expired@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-expired | Expired tenant user |
| USR-008 | noquota@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-noquota | No quota user |
| USR-009 | user2-a@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-a | Second user A (concurrency) |
| USR-010 | admin-disabled@test.com | REDACTED_TEST_PASSWORD | tenant_admin | tenant-disabled | Disabled tenant admin |
| USR-011 | norag@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-norag | No RAG user |
| USR-012 | readonly@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-a | Read-only tests |

#### 3.2.3 Opportunities (12 canonical)

| ID | Name | Tenant | Purpose | Expected State |
|----|------|--------|---------|----------------|
| OPP-001 | Clean Opportunity | tenant-a | Happy path CRUD | All fields valid |
| OPP-002 | Minimal Fields | tenant-a | Empty handling | Only required fields |
| OPP-003 | Max Fields | tenant-a | Boundary | All optional fields |
| OPP-004 | Tenant B Opp | tenant-b | Isolation | Only visible to B |
| OPP-005 | Expired Opp | tenant-a | Date boundary | due_date = yesterday |
| OPP-006 | Future Opp | tenant-a | Date boundary | due_date = +30 days |
| OPP-007 | Unicode Opp | tenant-a | Encoding | Unicode in text fields |
| OPP-008 | Large Description | tenant-a | Size boundary | 50KB description |
| OPP-009 | With Intelligence | tenant-a | Relationships | Has linked intelligence |
| OPP-010 | With Documents | tenant-a | Upload relation | Has uploaded files |
| OPP-011 | Synced Opp | tenant-a | Sync tests | source = highergov |
| OPP-012 | Archived Opp | tenant-a | Status tests | status = archived |

#### 3.2.4 Intelligence Records (6 canonical)

| ID | Opportunity | Tenant | Purpose |
|----|-------------|--------|---------|
| INT-001 | OPP-009 | tenant-a | Happy path |
| INT-002 | OPP-001 | tenant-a | CRUD tests |
| INT-003 | OPP-004 | tenant-b | Isolation |
| INT-004 | OPP-001 | tenant-a | Update tests |
| INT-005 | OPP-001 | tenant-a | Delete tests |
| INT-006 | OPP-007 | tenant-a | Unicode content |

#### 3.2.5 Test Documents

| File | Type | Size | Purpose |
|------|------|------|---------|
| test_clean.csv | CSV | 5KB | Normal upload |
| test_large.csv | CSV | 2MB | Size boundary |
| test_unicode.csv | CSV | 10KB | UTF-8 encoding |
| test_malformed.csv | CSV | 1KB | Parse errors |
| test_empty.csv | CSV | 0B | Empty handling |
| test_headers_only.csv | CSV | 100B | No data rows |
| test_10k_rows.csv | CSV | 1MB | Performance |
| test_logo.png | PNG | 50KB | Logo upload |
| test_logo_large.png | PNG | 5MB | Size limit |
| test_rag_doc.txt | TXT | 10KB | RAG indexing |
| test_rag_large.txt | TXT | 100KB | Chunking test |

### 3.3 Mock Services with Chaos Configuration

#### 3.3.1 HigherGov Mock

```json
{
  "base_url": "http://mock-highergov:8081",
  "endpoints": {
    "/api/opportunities": {
      "method": "GET",
      "normal_response": {"status": 200, "body": "opportunity_list.json"},
      "chaos": {
        "latency": {"min_ms": 50, "max_ms": 200, "spike_prob": 0.05, "spike_ms": 3000},
        "errors": {"rate_401": 0.01, "rate_404": 0.02, "rate_500": 0.02, "rate_timeout": 0.01}
      }
    },
    "/api/opportunities/{id}": {
      "method": "GET",
      "normal_response": {"status": 200, "body": "opportunity_detail.json"},
      "chaos": {
        "errors": {"rate_404": 0.05, "rate_500": 0.02}
      }
    },
    "/api/sync": {
      "method": "POST",
      "normal_response": {"status": 200, "body": "sync_result.json"},
      "chaos": {
        "latency": {"min_ms": 500, "max_ms": 2000},
        "errors": {"rate_500": 0.03, "rate_timeout": 0.02}
      }
    }
  },
  "scenarios": {
    "key_rotation": {"trigger_after_requests": 50, "return": 401},
    "schema_drift": {"probability": 0.01, "rename": {"source_id": "sourceId"}},
    "rate_limit": {"requests_per_minute": 100, "return": 429}
  }
}
```

#### 3.3.2 Mistral Mock

```json
{
  "base_url": "http://mock-mistral:8082",
  "endpoints": {
    "/v1/chat/completions": {
      "method": "POST",
      "normal_response": {"status": 200, "body": "chat_completion.json"},
      "chaos": {
        "latency": {"min_ms": 100, "max_ms": 500, "spike_prob": 0.03, "spike_ms": 5000},
        "errors": {
          "rate_429": 0.02,
          "rate_500": 0.01,
          "rate_timeout": 0.01,
          "rate_malformed_json": 0.005,
          "rate_partial_response": 0.005
        }
      }
    }
  },
  "deterministic_responses": {
    "test_echo": {"trigger": "ECHO:", "response": "echo back input"},
    "test_error": {"trigger": "FORCE_ERROR", "return": 500},
    "test_timeout": {"trigger": "FORCE_TIMEOUT", "delay_ms": 30000}
  }
}
```

#### 3.3.3 Perplexity Mock

```json
{
  "base_url": "http://mock-perplexity:8083",
  "endpoints": {
    "/chat/completions": {
      "method": "POST",
      "normal_response": {"status": 200, "body": "perplexity_completion.json"},
      "chaos": {
        "latency": {"min_ms": 200, "max_ms": 1000},
        "errors": {"rate_429": 0.02, "rate_500": 0.01}
      }
    }
  }
}
```

### 3.4 Environment Configuration

```bash
# .env.test
MONGO_URL=mongodb://localhost:27018
DB_NAME=outpace_test
JWT_SECRET=test-secret-key-12345
API_URL=http://localhost:8001

# Mock service URLs
HIGHERGOV_API_URL=http://localhost:8081
MISTRAL_API_URL=http://localhost:8082
PERPLEXITY_API_URL=http://localhost:8083

# Test configuration
TEST_TIMEOUT_MS=30000
CHAOS_ENABLED=true
SEED_ON_STARTUP=true
```

---

## 4. FILE-TO-TEST MAPPING

| Source File | Test Category | Strata Count | Est. Tests |
|-------------|---------------|--------------|------------|
| routes/auth.py | AUTH | 6 | 34 |
| routes/tenants.py | TENANTS | 6 | 39 |
| routes/chat.py | CHAT | 6 | 39 |
| routes/opportunities.py | OPPORTUNITIES | 6 | 31 |
| routes/intelligence.py | INTELLIGENCE | 6 | 35 |
| routes/exports.py | EXPORTS | 6 | 28 |
| routes/upload.py | UPLOAD | 6 | 30 |
| routes/sync.py | SYNC | 6 | 28 |
| routes/config.py | CONFIG | 6 | 26 |
| routes/admin.py | ADMIN | 6 | 27 |
| routes/users.py | USERS | 6 | 35 |
| routes/rag.py | RAG | 6 | 38 |
| services/highergov_service.py | SYNC (via mocks) | — | — |
| services/mistral_service.py | CHAT (via mocks) | — | — |
| services/perplexity_service.py | INTELLIGENCE (via mocks) | — | — |
| **TOTAL** | **12** | **72** | **~390** |

---

## 5. CATEGORY TEST SPECIFICATIONS

### 5.1 AUTH (routes/auth.py) — 34 tests

**Endpoints:**
- `POST /api/auth/login` (line 20-49)
- `GET /api/auth/me` (line 54-91)
- `POST /api/auth/logout` (line 96-105)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| AUTH-H-001 | Super admin login | admin@example.com / REDACTED_ADMIN_PASSWORD | 200, access_token | L20-49 |
| AUTH-H-002 | Tenant admin login | admin-a@test.com / REDACTED_TEST_PASSWORD | 200, access_token | L20-49 |
| AUTH-H-003 | Tenant user login | user-a@test.com / REDACTED_TEST_PASSWORD | 200, access_token | L20-49 |
| AUTH-H-004 | Get current user | valid token | 200, user object | L54-91 |
| AUTH-H-005 | Logout | valid token | 200, success | L96-105 |
| AUTH-H-006 | Token contains correct claims | login response | sub, role, tenant_id present | L20-49 |

#### BOUNDARY Stratum (6 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| AUTH-B-001 | Token 1 second from expiry | near-expiry token | 200 (still valid) | L54-91 |
| AUTH-B-002 | Password at min length (8) | 8 char password | 200 | L20-49 |
| AUTH-B-003 | Password at max length (128) | 128 char password | 200 | L20-49 |
| AUTH-B-004 | Email at max length (254) | 254 char email | 200 or 422 | L20-49 |
| AUTH-B-005 | Concurrent logins same user | 5 simultaneous | All succeed | L20-49 |
| AUTH-B-006 | Case insensitive email | Admin@Outpace.AI | 200 | L20-49 |

#### INVALID Stratum (8 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| AUTH-I-001 | Wrong password | valid email, bad pass | 401 | L20-49 |
| AUTH-I-002 | Unknown email | unknown@test.com | 401 | L20-49 |
| AUTH-I-003 | Malformed email | "not-an-email" | 422 | L20-49 |
| AUTH-I-004 | SQL injection email | "' OR 1=1 --" | 401 or 422 | L20-49 |
| AUTH-I-005 | XSS in password | "<script>alert(1)</script>" | 401 | L20-49 |
| AUTH-I-006 | Expired token | token from yesterday | 401 | L54-91 |
| AUTH-I-007 | Tampered token | modified JWT signature | 401 | L54-91 |
| AUTH-I-008 | Wrong algorithm token | HS256 vs RS256 | 401 | L54-91 |

#### EMPTY Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| AUTH-E-001 | No email | {"password": "x"} | 422 | L20-49 |
| AUTH-E-002 | No password | {"email": "x"} | 422 | L20-49 |
| AUTH-E-003 | Empty body | {} | 422 | L20-49 |
| AUTH-E-004 | No auth header | GET /me without token | 401 | L54-91 |
| AUTH-E-005 | Empty Bearer token | "Authorization: Bearer " | 401 | L54-91 |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| AUTH-P-001 | Login under 1000ms | valid creds | 200 in <1000ms | L20-49 |
| AUTH-P-002 | Token validation under 100ms | valid token | 200 in <100ms | L54-91 |
| AUTH-P-003 | 10 concurrent logins | 10 parallel | All <2000ms | L20-49 |
| AUTH-P-004 | 100 sequential logins | loop 100x | All succeed, <60s total | L20-49 |

#### FAILURE Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| AUTH-F-001 | DB down during login | valid creds, DB dead | 503 | L20-49 |
| AUTH-F-002 | DB timeout | valid creds, DB slow | 504 or graceful | L20-49 |
| AUTH-F-003 | Inactive user login | inactive@test.com | 403 | L20-49 |
| AUTH-F-004 | Expired tenant user | expired@test.com | 403 | L20-49 |
| AUTH-F-005 | Deleted user token | token for deleted user | 401 | L54-91 |

---

### 5.2 TENANTS (routes/tenants.py) — 39 tests

**Endpoints:**
- `GET /api/tenants` — List tenants
- `GET /api/tenants/{id}` — Get tenant
- `POST /api/tenants` — Create tenant
- `PUT /api/tenants/{id}` — Update tenant
- `DELETE /api/tenants/{id}` — Delete tenant
- `PUT /api/tenants/{id}/policy` — Update policy
- `PUT /api/tenants/{id}/quota` — Update quota
- `GET /api/tenants/{id}/usage` — Get usage

#### HAPPY Stratum (8 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| TEN-H-001 | List tenants (super) | super_admin token | 200, list |
| TEN-H-002 | Get tenant by ID | valid tenant_id | 200, tenant |
| TEN-H-003 | Create tenant | valid tenant data | 201, tenant |
| TEN-H-004 | Update tenant | valid update | 200, updated |
| TEN-H-005 | Delete tenant | valid tenant_id | 200, deleted |
| TEN-H-006 | Update policy | valid policy | 200, updated |
| TEN-H-007 | Update quota | valid quota | 200, updated |
| TEN-H-008 | Tenant admin sees own | tenant_admin token | 200, own tenant only |

#### BOUNDARY Stratum (7 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| TEN-B-001 | Name at max length (255) | 255 char name | 200 |
| TEN-B-002 | Slug at max length (63) | 63 char slug | 200 |
| TEN-B-003 | Quota at zero | quota=0 | 200 |
| TEN-B-004 | Quota at max int | quota=2147483647 | 200 |
| TEN-B-005 | 100 tenants list | paginated list | 200, pagination works |
| TEN-B-006 | Policy all features disabled | all=false | 200 |
| TEN-B-007 | Subscription expires today | subscription_end=today | 200, still active |

#### INVALID Stratum (8 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| TEN-I-001 | Duplicate slug | existing slug | 409 |
| TEN-I-002 | Invalid UUID format | "not-a-uuid" | 422 |
| TEN-I-003 | Negative quota | quota=-1 | 422 |
| TEN-I-004 | Invalid policy field | unknown_field=true | 422 |
| TEN-I-005 | Tenant admin creates tenant | tenant_admin token | 403 |
| TEN-I-006 | User reads other tenant | cross-tenant request | 403 |
| TEN-I-007 | SQL injection in slug | "'; DROP TABLE--" | 422 |
| TEN-I-008 | Update non-existent tenant | fake UUID | 404 |

#### EMPTY Stratum (6 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| TEN-E-001 | Create tenant no name | name missing | 422 |
| TEN-E-002 | Create tenant no slug | slug missing | 422 |
| TEN-E-003 | Empty update body | {} | 200 (no-op) or 422 |
| TEN-E-004 | List tenants (none exist) | empty DB | 200, [] |
| TEN-E-005 | Null policy values | policy: null | 422 |
| TEN-E-006 | Empty string name | name: "" | 422 |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| TEN-P-001 | List 100 tenants < 500ms | 100 tenants | 200 in <500ms |
| TEN-P-002 | Create tenant < 200ms | valid data | 201 in <200ms |
| TEN-P-003 | Update tenant < 200ms | valid update | 200 in <200ms |
| TEN-P-004 | 10 concurrent updates | parallel | All succeed |

#### FAILURE Stratum (6 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| TEN-F-001 | DB down | any request | 503 |
| TEN-F-002 | Unique index collision | race condition | 409 |
| TEN-F-003 | Delete tenant with users | tenant has users | 409 or cascade |
| TEN-F-004 | Delete tenant with data | tenant has opps | 409 or cascade |
| TEN-F-005 | Partial update failure | DB fail mid-update | rollback |
| TEN-F-006 | Connection pool exhausted | high load | 503 or queue |

---

### 5.3 CHAT (routes/chat.py) — 39 tests

**Endpoints:**
- `POST /api/chat` — Send message (line 51-127)
- `GET /api/chat/history` — Get chat history (line 152-432)
- `GET /api/chat/turns/{chat_id}` — Get turns (line 444-509)
- `DELETE /api/chat/{chat_id}` — Delete chat (line 521-529)

#### HAPPY Stratum (8 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| CHAT-H-001 | Send chat message | valid message | 200, response | L51-127 |
| CHAT-H-002 | Get chat history | valid token | 200, list | L152-432 |
| CHAT-H-003 | Get chat turns | valid chat_id | 200, turns | L444-509 |
| CHAT-H-004 | Delete chat | valid chat_id | 200, deleted | L521-529 |
| CHAT-H-005 | Multi-turn conversation | 3 sequential messages | 200, context preserved | L51-127 |
| CHAT-H-006 | Chat with opportunity context | opp_id in request | 200, contextual | L51-127 |
| CHAT-H-007 | Super admin chats | super_admin token | 200 | L51-127 |
| CHAT-H-008 | Different users same tenant | user-a, user2-a | Isolated histories | L152-432 |

#### BOUNDARY Stratum (8 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| CHAT-B-001 | Message at max tokens | 4096 tokens | 200 | L51-127 |
| CHAT-B-002 | Quota at 1 remaining | last allowed message | 200 | L51-127 |
| CHAT-B-003 | Quota exhausted (0) | quota=0 user | 429 | L51-127 |
| CHAT-B-004 | History 1000 chats | pagination | 200 | L152-432 |
| CHAT-B-005 | Month boundary quota reset | new UTC month | quota resets | L51-127 |
| CHAT-B-006 | UTC month key alignment | 23:59 vs 00:01 UTC | correct bucket | L51-127 |
| CHAT-B-007 | 100 turn conversation | long context | 200 | L444-509 |
| CHAT-B-008 | Concurrent same user | 2 parallel chats | both succeed | L51-127 |

#### INVALID Stratum (8 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| CHAT-I-001 | Empty message | message: "" | 422 | L51-127 |
| CHAT-I-002 | Chat disabled policy | chat_enabled=false | 403 | L51-127 |
| CHAT-I-003 | Cross-tenant chat_id | other tenant's chat | 403 | L444-509 |
| CHAT-I-004 | Invalid chat_id format | "not-a-uuid" | 422 | L444-509 |
| CHAT-I-005 | Delete other tenant's chat | wrong tenant | 403 | L521-529 |
| CHAT-I-006 | Prompt injection attempt | "ignore all instructions" | handled | L51-127 |
| CHAT-I-007 | Oversized message (1MB) | 1MB string | 413 | L51-127 |
| CHAT-I-008 | Invalid opportunity reference | fake opp_id | 404 | L51-127 |

#### EMPTY Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| CHAT-E-001 | No message in body | {} | 422 | L51-127 |
| CHAT-E-002 | Empty chat history | new user | 200, [] | L152-432 |
| CHAT-E-003 | Chat with 0 turns | empty chat | 200, [] | L444-509 |
| CHAT-E-004 | Null opportunity context | opp_id: null | 200 (no context) | L51-127 |
| CHAT-E-005 | Whitespace-only message | "   " | 422 | L51-127 |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| CHAT-P-001 | Response under 5000ms | simple message | 200 in <5000ms | L51-127 |
| CHAT-P-002 | History list under 500ms | 100 chats | 200 in <500ms | L152-432 |
| CHAT-P-003 | Turns list under 200ms | 50 turns | 200 in <200ms | L444-509 |
| CHAT-P-004 | 5 concurrent chats | parallel requests | All complete | L51-127 |

#### FAILURE Stratum (6 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| CHAT-F-001 | LLM service down | valid message | 503 | L51-127 |
| CHAT-F-002 | LLM timeout | valid message | 504 or retry | L51-127 |
| CHAT-F-003 | LLM rate limited | burst messages | 429 or queue | L51-127 |
| CHAT-F-004 | DB down during save | valid message | 503 | L51-127 |
| CHAT-F-005 | Partial LLM response | streaming cut | graceful handling | L51-127 |
| CHAT-F-006 | Malformed LLM response | bad JSON | error handling | L51-127 |

---

### 5.4 OPPORTUNITIES (routes/opportunities.py) — 31 tests

**Endpoints:**
- `GET /api/opportunities` — List (line 31-77)
- `GET /api/opportunities/{id}` — Get (line 89-93)
- `POST /api/opportunities` — Create (line 107-140)
- `PUT /api/opportunities/{id}` — Update (line 156-178)
- `DELETE /api/opportunities/{id}` — Delete (line 186-203)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| OPP-H-001 | List opportunities | valid token | 200, list |
| OPP-H-002 | Get opportunity by ID | valid opp_id | 200, opportunity |
| OPP-H-003 | Create opportunity | valid data | 201, opportunity |
| OPP-H-004 | Update opportunity | valid update | 200, updated |
| OPP-H-005 | Delete opportunity | valid opp_id | 200, deleted |
| OPP-H-006 | Filter by status | status=active | 200, filtered |

#### BOUNDARY Stratum (6 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| OPP-B-001 | List 1000 opportunities | pagination | 200, paginated |
| OPP-B-002 | Title at max length (500) | 500 chars | 200 |
| OPP-B-003 | Description max size (100KB) | 100KB | 200 |
| OPP-B-004 | Due date is today | expires today | 200, active |
| OPP-B-005 | Due date was yesterday | expired | 200, marked expired |
| OPP-B-006 | All optional fields populated | max fields | 200 |

#### INVALID Stratum (6 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| OPP-I-001 | Cross-tenant access | other tenant's opp | 403 |
| OPP-I-002 | Invalid status value | status="fake" | 422 |
| OPP-I-003 | Invalid UUID format | "not-a-uuid" | 422 |
| OPP-I-004 | Update non-existent | fake UUID | 404 |
| OPP-I-005 | Delete non-existent | fake UUID | 404 |
| OPP-I-006 | Invalid date format | date="not-a-date" | 422 |

#### EMPTY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| OPP-E-001 | Create no title | title missing | 422 |
| OPP-E-002 | List empty tenant | no opps | 200, [] |
| OPP-E-003 | Empty update body | {} | 200 or 422 |
| OPP-E-004 | Null optional fields | all nulls | 200 |
| OPP-E-005 | Empty string title | title: "" | 422 |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| OPP-P-001 | List 100 opps < 500ms | 100 opps | 200 in <500ms |
| OPP-P-002 | Create < 200ms | valid data | 201 in <200ms |
| OPP-P-003 | Bulk create 50 sequential | 50 creates | All <30s |
| OPP-P-004 | 10 concurrent reads | parallel | All succeed |

#### FAILURE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| OPP-F-001 | DB down | any request | 503 |
| OPP-F-002 | Partial create failure | DB fail mid-insert | rollback |
| OPP-F-003 | Index conflict | duplicate unique | 409 |
| OPP-F-004 | Connection pool exhausted | high load | 503 or queue |

---

### 5.5 INTELLIGENCE (routes/intelligence.py) — 35 tests

**Endpoints:**
- `POST /api/intelligence` — Create (line 25)
- `GET /api/intelligence` — List (line 51)
- `GET /api/intelligence/{intel_id}` — Get (line 101)
- `DELETE /api/intelligence/{intel_id}` — Delete (line 127)
- `PATCH /api/intelligence/{intel_id}` — Update (line 152)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| INT-H-001 | Create intelligence | valid opp_id | 201, intel | L25-49 |
| INT-H-002 | List intelligence | valid token | 200, list | L51-99 |
| INT-H-003 | Get intelligence by ID | valid intel_id | 200, intel | L101-125 |
| INT-H-004 | Delete intelligence | valid intel_id | 204 | L127-149 |
| INT-H-005 | Update intelligence | valid update | 200, updated | L152-192 |
| INT-H-006 | Filter by opportunity | opp_id param | 200, filtered | L51-99 |

#### BOUNDARY Stratum (6 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| INT-B-001 | Large intelligence content | 100KB text | 201 |
| INT-B-002 | List 500 records | pagination | 200, paginated |
| INT-B-003 | Unicode content | UTF-8 special chars | 201 |
| INT-B-004 | Multiple intel per opportunity | 10 records | all returned |
| INT-B-005 | Max field lengths | all at max | 201 |
| INT-B-006 | Filter with pagination | page 2 | correct offset |

#### INVALID Stratum (7 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| INT-I-001 | Create for other tenant's opp | cross-tenant | 403 | L34 |
| INT-I-002 | Get other tenant's intel | cross-tenant | 403 | L118 |
| INT-I-003 | Delete other tenant's intel | cross-tenant | 403 | L143 |
| INT-I-004 | Update other tenant's intel | cross-tenant | 403 | L168 |
| INT-I-005 | Invalid intel_id format | "not-a-uuid" | 422 | L101 |
| INT-I-006 | Get non-existent | fake UUID | 404 | L111 |
| INT-I-007 | Invalid opportunity reference | fake opp_id | 404 | L25 |

#### EMPTY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| INT-E-001 | Create no opportunity | opp_id missing | 422 |
| INT-E-002 | List empty tenant | no intel | 200, [] |
| INT-E-003 | Empty update body | {} | 200 (no-op) |
| INT-E-004 | Null content | content: null | 422 |
| INT-E-005 | Whitespace content | "   " | 422 or accepted |

#### PERFORMANCE Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| INT-P-001 | Create under 3000ms | valid request | 201 in <3000ms |
| INT-P-002 | List 100 under 500ms | 100 records | 200 in <500ms |
| INT-P-003 | Get single under 100ms | valid id | 200 in <100ms |
| INT-P-004 | 5 concurrent creates | parallel | All succeed |
| INT-P-005 | Bulk generate 10 | sequential | All <60s |

#### FAILURE Stratum (6 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| INT-F-001 | LLM service down | create request | 503 |
| INT-F-002 | LLM timeout | create request | 504 or retry |
| INT-F-003 | DB down | any request | 503 |
| INT-F-004 | Partial generation failure | LLM fails mid-stream | graceful |
| INT-F-005 | Malformed LLM response | bad JSON | error handling |
| INT-F-006 | Rate limited by LLM | burst creates | 429 or queue |

---

### 5.6 EXPORTS (routes/exports.py) — 28 tests

**Endpoints:**
- `POST /api/exports/pdf` — Export PDF (line 28)
- `POST /api/exports/excel` — Export Excel (line 174)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| EXP-H-001 | Export opportunities PDF | tenant_id | 200, PDF file | L28-169 |
| EXP-H-002 | Export opportunities Excel | tenant_id | 200, Excel file | L174-247 |
| EXP-H-003 | Export with filters | status filter | 200, filtered | L28 |
| EXP-H-004 | Export determinism | same input 2x | identical output | L28 |
| EXP-H-005 | Tenant scoped export | tenant data only | 200, own data | L51 |
| EXP-H-006 | Super admin export any | super token | 200 | L51 |

#### BOUNDARY Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| EXP-B-001 | Export 1000 records | large dataset | 200, complete | L28 |
| EXP-B-002 | Unicode in data | special chars | 200, correct encoding | L28 |
| EXP-B-003 | Max columns/fields | all fields | 200 | L28 |
| EXP-B-004 | Large text fields | 50KB descriptions | 200 | L28 |
| EXP-B-005 | Empty optional fields | nulls in data | 200, handled | L28 |

#### INVALID Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| EXP-I-001 | Missing tenant_id | no tenant | 400 | L47 |
| EXP-I-002 | Cross-tenant export | other tenant | 403 | L51 |
| EXP-I-003 | Non-existent tenant | fake UUID | 404 | L56 |
| EXP-I-004 | Invalid format param | format="fake" | 422 | L28 |
| EXP-I-005 | User exports other tenant | tenant_user | 403 | L51 |

#### EMPTY Stratum (4 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| EXP-E-001 | Export empty tenant | no data | 404 | L75 |
| EXP-E-002 | Export with no matching filter | filter matches none | 404 | L75 |
| EXP-E-003 | Null tenant_id | tenant_id: null | 400 | L47 |
| EXP-E-004 | Empty request body | {} | 400 | L47 |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| EXP-P-001 | Export 100 records < 5s | 100 records | 200 in <5s |
| EXP-P-002 | Export 500 records < 15s | 500 records | 200 in <15s |
| EXP-P-003 | 3 concurrent exports | parallel | All succeed |
| EXP-P-004 | Memory stable large export | 1000 records | No OOM |

#### FAILURE Stratum (4 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| EXP-F-001 | DB down | any export | 503 | L28 |
| EXP-F-002 | Partial read failure | DB fails mid-read | error handling | L120 |
| EXP-F-003 | File generation failure | PDF lib error | 500 | L120 |
| EXP-F-004 | Timeout during generation | slow DB | 504 | L28 |

---

### 5.7 UPLOAD (routes/upload.py) — 30 tests

**Endpoints:**
- `POST /api/upload/opportunities/csv/{tenant_id}` (line 45)
- `POST /api/upload/logo/{tenant_id}` (line 137)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| UPL-H-001 | Upload valid CSV | test_clean.csv | 200, processed | L45-134 |
| UPL-H-002 | Upload creates opportunities | new opps in CSV | 201, created | L45-134 |
| UPL-H-003 | Upload updates existing | matching opps | 200, updated | L45-134 |
| UPL-H-004 | Upload tenant logo | test_logo.png | 200, saved | L137-217 |
| UPL-H-005 | Upload with column mapping | mapped CSV | 200 | L45-134 |
| UPL-H-006 | Super admin uploads | super token | 200 | L58 |

#### BOUNDARY Stratum (6 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| UPL-B-001 | 2MB file | test_large.csv | 200 | L45 |
| UPL-B-002 | 10000 rows | test_10k_rows.csv | 200 | L45 |
| UPL-B-003 | 100 columns | wide CSV | 200 | L45 |
| UPL-B-004 | Unicode content | test_unicode.csv | 200, correct | L45 |
| UPL-B-005 | Quoted commas in fields | CSV escaping | 200, parsed | L45 |
| UPL-B-006 | CRLF line endings | Windows CSV | 200 | L45 |

#### INVALID Stratum (6 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| UPL-I-001 | Not a CSV file | binary file | 400 | L65 |
| UPL-I-002 | Malformed CSV | unclosed quotes | 422 | L45 |
| UPL-I-003 | Missing required column | no title | 422 | L45 |
| UPL-I-004 | Wrong file extension | .exe file | 400 | L158 |
| UPL-I-005 | File too large (100MB) | huge file | 400 | L168 |
| UPL-I-006 | Non-super admin upload CSV | tenant_user | 403 | L58 |

#### EMPTY Stratum (4 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| UPL-E-001 | Empty file (0 bytes) | empty.csv | 422 | L45 |
| UPL-E-002 | Headers only, no data | headers_only.csv | 200, 0 created | L45 |
| UPL-E-003 | No file in request | missing file | 422 | L45 |
| UPL-E-004 | All empty cell values | blank rows | handled | L45 |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| UPL-P-001 | 1000 rows < 10s | 1000 rows | 200 in <10s |
| UPL-P-002 | Logo upload < 2s | 50KB PNG | 200 in <2s |
| UPL-P-003 | 3 concurrent uploads | parallel | All succeed |
| UPL-P-004 | Memory stable large file | 2MB file | No OOM |

#### FAILURE Stratum (4 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| UPL-F-001 | DB down mid-upload | valid file | 503, rollback | L129 |
| UPL-F-002 | Partial row failures | some bad rows | report errors | L45 |
| UPL-F-003 | Tenant not found | fake tenant_id | 404 | L78, L208 |
| UPL-F-004 | BSON encoding failure | numpy types | handled | L20-41 |

---

### 5.8 SYNC (routes/sync.py) — 28 tests

**Endpoints:**
- `POST /api/sync/manual/{tenant_id}` (line 16)
- `POST /api/sync/opportunity/{tenant_id}` (line 89)

#### HAPPY Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| SYN-H-001 | Manual sync tenant | valid tenant_id | 200, results | L16-86 |
| SYN-H-002 | Sync single opportunity | opp_id param | 200, synced | L89-133 |
| SYN-H-003 | Sync creates new opps | new from HigherGov | created | L16-86 |
| SYN-H-004 | Sync updates existing | matching opps | updated | L16-86 |
| SYN-H-005 | Super admin sync | super token | 200 | L16 |

#### BOUNDARY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| SYN-B-001 | Sync 100 opportunities | large batch | 200 |
| SYN-B-002 | Sync with rate limiting | near API limit | handled |
| SYN-B-003 | Unicode in synced data | special chars | preserved |
| SYN-B-004 | Concurrent syncs same tenant | 2 parallel | handled |
| SYN-B-005 | Sync empty response | no new opps | 200, 0 created |

#### INVALID Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| SYN-I-001 | Non-existent tenant | fake UUID | 404 | L31, L110 |
| SYN-I-002 | Cross-tenant sync | other tenant | 403 | L103 |
| SYN-I-003 | Missing opportunity_id | no opp_id param | 400 | L117 |
| SYN-I-004 | Invalid tenant_id format | "not-uuid" | 422 | L16 |
| SYN-I-005 | Tenant user triggers sync | tenant_user | 403 | L16 |

#### EMPTY Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| SYN-E-001 | Sync tenant with no config | no HigherGov setup | handled |
| SYN-E-002 | Empty sync response | API returns [] | 200, 0 synced |
| SYN-E-003 | Null opportunity_id | opp_id: null | 400 |
| SYN-E-004 | New tenant first sync | no existing data | 200 |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| SYN-P-001 | Sync 50 opps < 30s | 50 opportunities | 200 in <30s |
| SYN-P-002 | Single opp sync < 5s | 1 opportunity | 200 in <5s |
| SYN-P-003 | 3 concurrent syncs | parallel tenants | All succeed |
| SYN-P-004 | Memory stable large sync | 100 opps | No OOM |

#### FAILURE Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| SYN-F-001 | HigherGov down | sync request | 503 | L56, L68 |
| SYN-F-002 | HigherGov timeout | sync request | handled | L56 |
| SYN-F-003 | HigherGov 401 | bad API key | logged, error | L56 |
| SYN-F-004 | Partial sync failure | some opps fail | partial success | L56, L68 |
| SYN-F-005 | DB down during sync | sync request | rollback | L82 |

---

### 5.9 CONFIG (routes/config.py) — 26 tests

**Endpoints:**
- `PUT /api/config/tenants/{tenant_id}/intelligence-config` (line 34)
- `GET /api/config/tenants/{tenant_id}/intelligence-config` (line 136)

#### HAPPY Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| CFG-H-001 | Get intelligence config | valid tenant_id | 200, config | L136-161 |
| CFG-H-002 | Update intelligence config | valid config | 200, updated | L34-133 |
| CFG-H-003 | Update cron expression | valid cron | 200 | L97 |
| CFG-H-004 | Super admin updates | super token | 200 | L80 |
| CFG-H-005 | Tenant admin updates own | tenant_admin | 200 | L80 |

#### BOUNDARY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| CFG-B-001 | All config fields set | max config | 200 |
| CFG-B-002 | Complex cron expression | "0 0 * * MON-FRI" | 200 |
| CFG-B-003 | Config at max string length | long values | 200 |
| CFG-B-004 | Frequent cron (every minute) | "* * * * *" | 200 |
| CFG-B-005 | All boolean permutations | all true/false combos | 200 |

#### INVALID Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| CFG-I-001 | Invalid JSON body | malformed JSON | 400 | L51 |
| CFG-I-002 | Empty JSON body | {} | 400 | L58 |
| CFG-I-003 | Unknown fields | extra_field=true | 400 | L73 |
| CFG-I-004 | Cross-tenant update | other tenant | 403 | L80 |
| CFG-I-005 | Invalid cron expression | "not-a-cron" | 400 | L97 |

#### EMPTY Stratum (3 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| CFG-E-001 | Get config for new tenant | no config yet | 200, defaults |
| CFG-E-002 | Non-existent tenant | fake UUID | 404 |
| CFG-E-003 | Null config values | field: null | handled |

#### PERFORMANCE Stratum (3 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| CFG-P-001 | Get config < 100ms | valid request | 200 in <100ms |
| CFG-P-002 | Update config < 200ms | valid update | 200 in <200ms |
| CFG-P-003 | 10 concurrent gets | parallel | All succeed |

#### FAILURE Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| CFG-F-001 | DB down | any request | 503 | L126 |
| CFG-F-002 | Tenant not found | fake UUID | 404 | L88, L152 |
| CFG-F-003 | Partial update failure | DB fail mid-update | rollback | L126 |
| CFG-F-004 | Concurrent update race | 2 parallel updates | last-write-wins | L34 |
| CFG-F-005 | Invalid scheduler state | bad cron saves | handled | L97 |

---

### 5.10 ADMIN (routes/admin.py) — 27 tests

**Endpoints:**
- `GET /api/admin/dashboard` (line 16)
- `POST /api/admin/sync/{tenant_id}` (line 61)
- `GET /api/admin/system/health` (line 134)

#### HAPPY Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| ADM-H-001 | Get admin dashboard | super_admin token | 200, dashboard | L16-58 |
| ADM-H-002 | Trigger manual sync | valid tenant_id | 200, results | L61-130 |
| ADM-H-003 | Get system health | super_admin token | 200, health | L134-156 |
| ADM-H-004 | Dashboard shows all tenants | super_admin | all tenants | L16-58 |
| ADM-H-005 | Sync creates/updates | valid tenant | opps synced | L61-130 |

#### BOUNDARY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| ADM-B-001 | Dashboard 100 tenants | large dataset | 200 |
| ADM-B-002 | Sync 100 opportunities | large batch | 200 |
| ADM-B-003 | Health check all services | all connected | healthy |
| ADM-B-004 | Concurrent dashboard access | 5 parallel | All succeed |
| ADM-B-005 | Sync with rate limiting | near limit | handled |

#### INVALID Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| ADM-I-001 | Non-super admin dashboard | tenant_admin | 403 | L16 |
| ADM-I-002 | Non-super admin sync | tenant_admin | 403 | L61 |
| ADM-I-003 | Sync non-existent tenant | fake UUID | 404 | L76 |
| ADM-I-004 | Non-super admin health | tenant_user | 403 | L134 |
| ADM-I-005 | Invalid tenant_id format | "not-uuid" | 422 | L61 |

#### EMPTY Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| ADM-E-001 | Dashboard no tenants | empty system | 200, empty stats |
| ADM-E-002 | Sync empty response | no opps from API | 200, 0 synced |
| ADM-E-003 | Health no DB | DB down | unhealthy |
| ADM-E-004 | Dashboard null stats | missing data | handled |

#### PERFORMANCE Stratum (3 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| ADM-P-001 | Dashboard < 1s | valid request | 200 in <1s |
| ADM-P-002 | Health check < 500ms | valid request | 200 in <500ms |
| ADM-P-003 | Sync 50 opps < 30s | 50 opps | 200 in <30s |

#### FAILURE Stratum (5 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| ADM-F-001 | DB down dashboard | dashboard request | 503 | L16 |
| ADM-F-002 | HigherGov down sync | sync request | error in results | L101, L113 |
| ADM-F-003 | Partial sync failure | some opps fail | partial results | L101, L113 |
| ADM-F-004 | Health DB unreachable | health request | unhealthy | L152 |
| ADM-F-005 | Sync timeout | slow API | handled | L127 |

---

### 5.11 USERS (routes/users.py) — 35 tests

**Endpoints:**
- `POST /api/users` — Create (line 18)
- `GET /api/users` — List (line 73)
- `GET /api/users/{user_id}` — Get (line 124)
- `PUT /api/users/{user_id}` — Update (line 146)
- `DELETE /api/users/{user_id}` — Delete (line 188)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| USR-H-001 | Create user | valid data | 201, user | L18-70 |
| USR-H-002 | List users | tenant_admin token | 200, list | L73-122 |
| USR-H-003 | Get user by ID | valid user_id | 200, user | L124-143 |
| USR-H-004 | Update user | valid update | 200, updated | L146-185 |
| USR-H-005 | Delete user | valid user_id | 204 | L188-217 |
| USR-H-006 | Deactivate user | is_active=false | 200 | L146-185 |

#### BOUNDARY Stratum (6 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| USR-B-001 | Email at max length (254) | 254 chars | 201 |
| USR-B-002 | Full name max length | 255 chars | 201 |
| USR-B-003 | List 100 users | pagination | 200 |
| USR-B-004 | Password at min (8) | 8 chars | 201 |
| USR-B-005 | Password at max (128) | 128 chars | 201 |
| USR-B-006 | Concurrent user creates | 5 parallel | All succeed |

#### INVALID Stratum (7 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| USR-I-001 | Duplicate email | existing email | 400 | L28 |
| USR-I-002 | Create for other tenant | cross-tenant | 403 | L36 |
| USR-I-003 | Create super_admin | role=super_admin | 403 | L41 |
| USR-I-004 | Get other tenant's user | cross-tenant | 403 | L138 |
| USR-I-005 | Update other tenant's user | cross-tenant | 403 | L164 |
| USR-I-006 | Delete other tenant's user | cross-tenant | 403 | L205 |
| USR-I-007 | Delete yourself | own user_id | 400 | L212 |

#### EMPTY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| USR-E-001 | Create no email | email missing | 422 |
| USR-E-002 | Create no password | password missing | 422 |
| USR-E-003 | List empty tenant | no users | 200, [] |
| USR-E-004 | Empty update body | {} | 200 (no-op) |
| USR-E-005 | Null full_name | full_name: null | handled |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| USR-P-001 | Create user < 300ms | valid data | 201 in <300ms |
| USR-P-002 | List 50 users < 500ms | 50 users | 200 in <500ms |
| USR-P-003 | 10 concurrent reads | parallel | All succeed |
| USR-P-004 | Bulk create 20 | sequential | All <30s |

#### FAILURE Stratum (7 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| USR-F-001 | DB down | any request | 503 | L18 |
| USR-F-002 | Email index conflict | race condition | 400 | L28 |
| USR-F-003 | Tenant not found | fake tenant_id | 404 | L50 |
| USR-F-004 | User not found (get) | fake user_id | 404 | L131 |
| USR-F-005 | User not found (update) | fake user_id | 404 | L157 |
| USR-F-006 | User not found (delete) | fake user_id | 404 | L198 |
| USR-F-007 | Password hash failure | bcrypt error | 500 | L18 |

---

### 5.12 RAG (routes/rag.py) — 38 tests

**Endpoints:**
- `GET /api/tenants/{tenant_id}/rag/status` (line 75)
- `POST /api/tenants/{tenant_id}/rag/documents` (line 106)
- `DELETE /api/tenants/{tenant_id}/rag/documents/{doc_id}` (line 224)
- `GET /api/tenants/{tenant_id}/rag/documents` (line 246)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| RAG-H-001 | Get RAG status | valid tenant | 200, status | L75-103 |
| RAG-H-002 | Ingest document | valid content | 200, doc_id | L106-221 |
| RAG-H-003 | Delete document | valid doc_id | 204 | L224-243 |
| RAG-H-004 | List documents | valid tenant | 200, list | L246-268 |
| RAG-H-005 | Document gets chunked | 10KB doc | chunks created | L106-221 |
| RAG-H-006 | Retrieve RAG context | search query | 200, results | L270+ |

#### BOUNDARY Stratum (7 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| RAG-B-001 | Document at max size | 100KB | 200 | L106 |
| RAG-B-002 | Max documents per tenant | at limit | 200 | L144 |
| RAG-B-003 | Max chunks per tenant | at limit | 200 | L154 |
| RAG-B-004 | Unicode content | UTF-8 special | 200, correct | L106 |
| RAG-B-005 | List 100 documents | pagination | 200 | L246 |
| RAG-B-006 | Large chunk count | many chunks | handled | L33-46 |
| RAG-B-007 | Concurrent ingests | 3 parallel | All succeed | L106 |

#### INVALID Stratum (7 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| RAG-I-001 | Non-existent tenant | fake UUID | 404 | L84, L120 |
| RAG-I-002 | Master tenant RAG | master tenant | 403 | L123 |
| RAG-I-003 | RAG disabled tenant | rag_enabled=false | 403 | L127 |
| RAG-I-004 | Empty document content | content: "" | 400 | L133 |
| RAG-I-005 | Document limit exceeded | over limit | 409 | L144 |
| RAG-I-006 | Chunk limit exceeded | would exceed | 409 | L154 |
| RAG-I-007 | Non-existent document | fake doc_id | 404 | L235 |

#### EMPTY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| RAG-E-001 | List empty documents | no docs | 200, [] |
| RAG-E-002 | Status no documents | 0 indexed | 200, count=0 |
| RAG-E-003 | Search no results | unmatched query | 200, [] |
| RAG-E-004 | Whitespace content | "   " | 400 |
| RAG-E-005 | New tenant RAG status | no prior use | 200, defaults |

#### PERFORMANCE Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| RAG-P-001 | Ingest 10KB < 5s | 10KB doc | 200 in <5s |
| RAG-P-002 | Ingest 100KB < 30s | 100KB doc | 200 in <30s |
| RAG-P-003 | List 50 docs < 500ms | 50 docs | 200 in <500ms |
| RAG-P-004 | Search < 1s | valid query | 200 in <1s |
| RAG-P-005 | 5 concurrent searches | parallel | All succeed |

#### FAILURE Stratum (8 tests)

| ID | Test | Input | Expected | Covers |
|----|------|-------|----------|--------|
| RAG-F-001 | Embedding service down | ingest request | 503 | L51 |
| RAG-F-002 | Embedding timeout | ingest request | handled | L48-62 |
| RAG-F-003 | DB down | any request | 503 | L106 |
| RAG-F-004 | Partial ingest failure | fails mid-chunk | cleanup | L212 |
| RAG-F-005 | Malformed embedding response | bad vector | handled | L319 |
| RAG-F-006 | Document parse failure | corrupt content | error | L106 |
| RAG-F-007 | Vector search failure | DB error | handled | L270 |
| RAG-F-008 | Concurrent delete race | 2 deletes same | handled | L224 |

---

## 6. FAILURE RESPONSE MATRIX

| Status | Pass Rate | Criteria | Action | Blocks Deploy? |
|--------|-----------|----------|--------|----------------|
| **PASS** | 100% | 59/59 | None required | No |
| **FLAKY** | 97-99% | 57-58/59 | Investigate within 48h, flag in report | No |
| **UNSTABLE** | 80-96% | 47-56/59 | Block, investigate immediately | **Yes** |
| **FAIL** | <80% | <47/59 | Block, incident created, rollback if in prod | **Yes** |

### Automatic Actions

```yaml
on_status:
  PASS:
    - log_success
    - update_dashboard
  FLAKY:
    - create_investigation_ticket
    - notify_slack_channel
    - allow_deploy_with_warning
  UNSTABLE:
    - block_deploy
    - page_on_call
    - create_incident_ticket
  FAIL:
    - block_deploy
    - page_on_call
    - trigger_rollback_if_prod
    - create_p1_incident
```

---

## 7. CI/CD INTEGRATION

### 7.1 Before Merge to Main

```yaml
# Required checks
- name: Unit Tests
  run: pytest backend/tests/unit --cov=backend --cov-fail-under=50
  
- name: CARFAX Smoke
  run: ./carfax.sh happy
  
- name: Coverage Check
  run: |
    coverage report --fail-under=50
    # Coverage must not decrease from main
```

### 7.2 Before Deploy to Staging

```yaml
# Required checks
- name: All Strata Pass
  run: |
    for stratum in happy boundary invalid empty performance failure; do
      ./carfax.sh $stratum || exit 1
    done

- name: Coverage Gate
  run: coverage report --fail-under=70

- name: Docker Build
  run: docker-compose -f docker-compose.test.yml build

- name: Integration Health
  run: |
    docker-compose -f docker-compose.test.yml up -d
    sleep 30
    curl -f http://localhost:8001/health
    docker-compose -f docker-compose.test.yml down
```

### 7.3 Before Deploy to Production

```yaml
# Required checks
- name: Monte Carlo Full
  run: |
    for category in auth tenants chat opportunities intelligence exports upload sync config admin users rag; do
      for stratum in happy boundary invalid empty performance failure; do
        for i in $(seq 1 59); do
          ./carfax.sh $category $stratum || exit 1
        done
      done
    done

- name: Coverage Gate
  run: coverage report --fail-under=95

- name: Critical Path 100%
  run: |
    coverage report --include="routes/auth.py,routes/chat.py,routes/tenants.py,utils/auth.py,models.py" --fail-under=100

- name: Manual Sign-off
  type: manual_approval
  approvers: [tech_lead, qa_lead]
```

---

## 8. ROLLBACK TRIGGERS

### Automatic Rollback Conditions

| Trigger | Threshold | Action |
|---------|-----------|--------|
| Health check fails | >5 minutes | Rollback |
| Error rate | >5% of requests | Rollback |
| P99 latency | >10 seconds | Rollback |
| DB connection failures | >10 in 1 minute | Rollback |
| Auth failures | >20% of attempts | Rollback |
| Monte Carlo regression | UNSTABLE or FAIL | Block + investigate |

### Rollback Procedure

```bash
# 1. Immediate
kubectl rollout undo deployment/b2b-api

# 2. Verify
kubectl rollout status deployment/b2b-api
curl -f https://api.example.com/health

# 3. Document
# Create incident with:
# - Deployment commit hash
# - Time of rollback
# - Symptoms observed
# - Monte Carlo status before deploy
```

---

## 9. COVERAGE GATES BY PHASE

| Phase | Line % | Branch % | Target Date | Gate |
|-------|--------|----------|-------------|------|
| 1 - Current | 29% | — | Baseline | — |
| 2 - Foundation | 50% | 30% | +1 week | Merge block |
| 3 - Growth | 70% | 50% | +2 weeks | Staging block |
| 4 - Maturity | 85% | 65% | +3 weeks | Staging block |
| 5 - Production | 95% | 75% | +4 weeks | Prod block |

### Critical Path Files (100% Required)

| File | Lines | Current | Reason |
|------|-------|---------|--------|
| routes/auth.py | 45 | 38% | Security critical |
| routes/chat.py | 211 | 13% | Revenue/quota critical |
| routes/tenants.py | 188 | 19% | Multi-tenant isolation |
| utils/auth.py | 52 | 46% | JWT handling |
| models.py | 262 | 100% | Data integrity |

---

## 10. EXECUTION TIMELINE

### Week 1: Infrastructure + Core Categories

| Day | Task | Tests | Coverage |
|-----|------|-------|----------|
| Mon | Docker compose, mocks, seed data | — | — |
| Tue | AUTH all strata (34 tests) | 34 | 35% |
| Wed | TENANTS all strata (39 tests) | 73 | 45% |
| Thu | CHAT all strata (39 tests) | 112 | 52% |
| Fri | Harness restructure + Monte Carlo validation | — | 52% |

### Week 2: Core Categories Continued

| Day | Task | Tests | Coverage |
|-----|------|-------|----------|
| Mon | OPPORTUNITIES all strata (31 tests) | 143 | 58% |
| Tue | INTELLIGENCE all strata (35 tests) | 178 | 65% |
| Wed | USERS all strata (35 tests) | 213 | 70% |
| Thu | Bug fixes from findings | — | 72% |
| Fri | Monte Carlo run (Week 2) | — | 72% |

### Week 3: Remaining Categories

| Day | Task | Tests | Coverage |
|-----|------|-------|----------|
| Mon | EXPORTS all strata (28 tests) | 241 | 76% |
| Tue | UPLOAD all strata (30 tests) | 271 | 80% |
| Wed | SYNC all strata (28 tests) | 299 | 84% |
| Thu | CONFIG all strata (26 tests) | 325 | 87% |
| Fri | Monte Carlo run (Week 3) | — | 87% |

### Week 4: Final Categories + Polish

| Day | Task | Tests | Coverage |
|-----|------|-------|----------|
| Mon | ADMIN all strata (27 tests) | 352 | 90% |
| Tue | RAG all strata (38 tests) | 390 | 93% |
| Wed | Gap analysis + critical path 100% | +~20 | 95% |
| Thu | Full Monte Carlo (25,488 executions) | — | 95% |
| Fri | Documentation + sign-off | — | 95% |

---

## 11. SUMMARY

| Metric | Value |
|--------|-------|
| Categories | 12 |
| Strata per Category | 6 |
| Total Strata | 72 |
| Total Tests | ~390 |
| Monte Carlo Runs/Stratum | 59 |
| **Total Executions** | **~25,488** |
| Current Coverage | 29% |
| Target Coverage | 95% |
| Critical Path Coverage | 100% |
| Timeline | 4 weeks |

### Invariants Verified

| ID | Invariant | Test Categories |
|----|-----------|-----------------|
| INV-1 | Tenant Isolation | All (cross-tenant tests in INVALID strata) |
| INV-2 | Chat Atomicity | CHAT (FAILURE stratum) |
| INV-3 | Paid Chat Enforcement | CHAT (BOUNDARY quota tests) |
| INV-4 | Master Tenant Restriction | TENANTS, RAG (INVALID strata) |
| INV-5 | Export Determinism | EXPORTS (HAPPY stratum) |

---

## 12. APPENDIX: TEST RUNNER STRUCTURE

### carfax.sh Category/Stratum Mode

```bash
#!/usr/bin/env bash
# Usage: ./carfax.sh <category> <stratum>
# Example: ./carfax.sh auth happy
# Example: ./carfax.sh chat boundary

CATEGORY=$1
STRATUM=$2

case "$CATEGORY" in
  auth) run_auth_tests "$STRATUM" ;;
  tenants) run_tenants_tests "$STRATUM" ;;
  chat) run_chat_tests "$STRATUM" ;;
  opportunities) run_opportunities_tests "$STRATUM" ;;
  intelligence) run_intelligence_tests "$STRATUM" ;;
  exports) run_exports_tests "$STRATUM" ;;
  upload) run_upload_tests "$STRATUM" ;;
  sync) run_sync_tests "$STRATUM" ;;
  config) run_config_tests "$STRATUM" ;;
  admin) run_admin_tests "$STRATUM" ;;
  users) run_users_tests "$STRATUM" ;;
  rag) run_rag_tests "$STRATUM" ;;
  all) run_all_categories "$STRATUM" ;;
  *) echo "Unknown category: $CATEGORY" && exit 1 ;;
esac
```

### monte_carlo_full.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

RUNS=59
CATEGORIES=(auth tenants chat opportunities intelligence exports upload sync config admin users rag)
STRATA=(happy boundary invalid empty performance failure)
PASS=0
FAIL=0

for cat in "${CATEGORIES[@]}"; do
  for stratum in "${STRATA[@]}"; do
    echo "=== $cat/$stratum: Starting 59 runs ==="
    stratum_pass=0
    stratum_fail=0
    
    for i in $(seq 1 $RUNS); do
      if ./carfax.sh "$cat" "$stratum" > /dev/null 2>&1; then
        stratum_pass=$((stratum_pass + 1))
      else
        stratum_fail=$((stratum_fail + 1))
      fi
    done
    
    echo "$cat/$stratum: $stratum_pass/$RUNS PASS"
    PASS=$((PASS + stratum_pass))
    FAIL=$((FAIL + stratum_fail))
    
    # Fail fast on UNSTABLE
    if [ $stratum_fail -gt 12 ]; then
      echo "UNSTABLE: $cat/$stratum failed $stratum_fail/59 - aborting"
      exit 1
    fi
  done
done

echo "=== MONTE CARLO COMPLETE ==="
echo "TOTAL: $PASS PASS, $FAIL FAIL"
echo "CONFIDENCE: $([ $FAIL -eq 0 ] && echo '95% (p<0.05)' || echo 'NOT MET')"
```

---

END OF TEST PLAN