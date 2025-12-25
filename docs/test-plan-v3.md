# B2B INTELLIGENCE DASHBOARD - COMPREHENSIVE TEST PLAN
## Version 3.0 - December 2025
## PRODUCTION-GRADE - GROUND TRUTH ALIGNED

---

## 1. EXECUTIVE SUMMARY

| Metric | Actual | Source |
|--------|--------|--------|
| Route Files | 12 | `backend/routes/*.py` |
| Total Lines | 3,194 | `wc -l` output |
| Total Endpoints | **47** | `@router.*` grep |
| MongoDB Collections | 10 | Code analysis |
| External Services | 3 | Mistral, HigherGov, Perplexity |
| Categories | 12 | 1 per route file |
| Strata per Category | 6 | Happy/Boundary/Invalid/Empty/Performance/Failure |
| Total Strata | 72 | 12 × 6 |
| Tests per Category | ~30-40 | Based on endpoint complexity |
| **Total Tests** | **~420** | Sum across all strata |
| Monte Carlo Runs/Stratum | 59 | 95% confidence (p<0.05) |
| **Total Executions** | **~24,780** | 72 × 59 × ~5.8 avg tests |

### Proof of Endpoint Count (47)
```
admin.py:        3 endpoints
auth.py:         3 endpoints
chat.py:         3 endpoints
config.py:       2 endpoints
exports.py:      2 endpoints
intelligence.py: 5 endpoints
opportunities.py: 6 endpoints
rag.py:          4 endpoints
sync.py:         2 endpoints
tenants.py:     10 endpoints
upload.py:       2 endpoints
users.py:        5 endpoints
─────────────────────────────
TOTAL:          47 endpoints
```

---

## 2. TEST ARCHITECTURE

### 2.1 Category → 6 Strata Structure

```
CATEGORY (1 per route file)
├── HAPPY     — Baseline functionality works (expected success paths)
├── BOUNDARY  — Edge cases, limits, transitions (min/max values, pagination)
├── INVALID   — Bad inputs, malformed data, unauthorized access
├── EMPTY     — Null, missing, zero-length inputs
├── PERFORMANCE — Timing, load, concurrency requirements
└── FAILURE   — External service failures, DB errors, recovery paths
```

### 2.2 Monte Carlo Confidence Definition

- **59 runs** of each stratum = 95% confidence (p<0.05)
- **Zero failures** required to claim confidence
- Each stratum is an independent unit of analysis
- Formula: Categories (12) × Strata (6) × Runs (59) = 4,248 stratum executions

### 2.3 Categories (12) with Actual Metrics

| # | Category | Route File | Lines | Endpoints | Auth Type |
|---|----------|------------|-------|-----------|-----------|
| 1 | AUTH | auth.py | 104 | 3 | mixed (none/get_current_user) |
| 2 | TENANTS | tenants.py | 506 | 10 | mixed (super_admin/user) |
| 3 | CHAT | chat.py | 529 | 3 | get_current_user |
| 4 | OPPORTUNITIES | opportunities.py | 282 | 6 | get_current_user |
| 5 | INTELLIGENCE | intelligence.py | 191 | 5 | get_current_user |
| 6 | EXPORTS | exports.py | 247 | 2 | get_current_user |
| 7 | UPLOAD | upload.py | 217 | 2 | mixed (user/tenant_admin) |
| 8 | SYNC | sync.py | 172 | 2 | mixed (super_admin/user) |
| 9 | CONFIG | config.py | 161 | 2 | get_current_tenant_admin |
| 10 | ADMIN | admin.py | 155 | 3 | get_current_super_admin |
| 11 | USERS | users.py | 217 | 5 | mixed (tenant_admin/user) |
| 12 | RAG | rag.py | 413 | 4 | get_current_super_admin |

---

## 3. FILE-TO-TEST MAPPING

### Verified Line Numbers from Actual Code

| Source File | Endpoints | Line Numbers | Test Category |
|-------------|-----------|--------------|---------------|
| routes/admin.py | 3 | L15, L60, L133 | ADMIN |
| routes/auth.py | 3 | L17, L51, L93 | AUTH |
| routes/chat.py | 3 | L130, L435, L512 | CHAT |
| routes/config.py | 2 | L33, L135 | CONFIG |
| routes/exports.py | 2 | L27, L173 | EXPORTS |
| routes/intelligence.py | 5 | L24, L50, L100, L126, L151 | INTELLIGENCE |
| routes/opportunities.py | 6 | L25, L96, L150, L180, L205, L253 | OPPORTUNITIES |
| routes/rag.py | 4 | L74, L105, L223, L245 | RAG |
| routes/sync.py | 2 | L15, L88 | SYNC |
| routes/tenants.py | 10 | L20, L48, L93, L194, L262, L340, L368, L389, L442, L494 | TENANTS |
| routes/upload.py | 2 | L44, L136 | UPLOAD |
| routes/users.py | 5 | L17, L72, L123, L145, L187 | USERS |

### Service Dependencies

| Service | Route Files Using | Import Lines |
|---------|-------------------|--------------|
| Mistral API | chat.py, rag.py | chat.py:8, rag.py:14 |
| HigherGov | admin.py, sync.py | admin.py:82, sync.py:37,122 |
| Perplexity | admin.py, sync.py | admin.py:83, sync.py:38 |

---

## 4. SEED DATA SPECIFICATION

### 4.1 Tenants (6 canonical)

| ID | Slug | Name | Purpose | Config |
|----|------|------|---------|--------|
| `8aa521eb-56ad-4727-8f09-c01fc7921c21` | tenant-a | Tenant A | Primary test tenant | `chat_policy.enabled=true`, `rag_policy.enabled=true` |
| `e4e0b3b4-90ec-4c32-88d8-534aa563ed5d` | tenant-b | Tenant B | Cross-tenant isolation | Separate data silo |
| `00000000-0000-0000-0000-000000000001` | tenant-expired | Expired Tenant | Subscription tests | `subscription_end=yesterday` |
| `00000000-0000-0000-0000-000000000002` | tenant-noquota | No Quota Tenant | Quota exhaustion | `chat_policy.monthly_message_limit=0` |
| `00000000-0000-0000-0000-000000000003` | tenant-master | Master Tenant | Master restrictions | `is_master_client=true` |
| `00000000-0000-0000-0000-000000000004` | tenant-norag | No RAG Tenant | RAG disabled | `rag_policy.enabled=false` |

### 4.2 Users (12 canonical)

| ID | Email | Password | Role | Tenant | Purpose |
|----|-------|----------|------|--------|---------|
| `super_admin_001` | admin@example.com | REDACTED_ADMIN_PASSWORD | super_admin | null | Super admin operations |
| `tenant_admin_a` | admin-a@test.com | REDACTED_TEST_PASSWORD | tenant_admin | tenant-a | Tenant A admin |
| `tenant_admin_b` | admin-b@test.com | REDACTED_TEST_PASSWORD | tenant_admin | tenant-b | Tenant B admin |
| `tenant_user_a1` | user-a@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-a | Regular user A |
| `tenant_user_b1` | user-b@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-b | Regular user B |
| `tenant_user_a2` | user2-a@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-a | Second user A (concurrency) |
| `inactive_user` | inactive@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-a | `is_active=false` |
| `expired_user` | expired@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-expired | Expired tenant user |
| `noquota_user` | noquota@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-noquota | No quota user |
| `master_admin` | master@test.com | REDACTED_TEST_PASSWORD | tenant_admin | tenant-master | Master tenant admin |
| `norag_user` | norag@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-norag | No RAG user |
| `readonly_user` | readonly@test.com | REDACTED_TEST_PASSWORD | tenant_user | tenant-a | Read-only tests |

### 4.3 Opportunities (12 canonical)

| ID | Title | Tenant | Purpose | State |
|----|-------|--------|---------|-------|
| `opp-001` | Clean Opportunity | tenant-a | Happy path CRUD | All fields valid |
| `opp-002` | Minimal Fields | tenant-a | Empty handling | Only required fields |
| `opp-003` | Max Fields | tenant-a | Boundary | All optional fields populated |
| `opp-004` | Tenant B Opp | tenant-b | Isolation | Only visible to B |
| `opp-005` | Expired Opp | tenant-a | Date boundary | `due_date=yesterday` |
| `opp-006` | Future Opp | tenant-a | Date boundary | `due_date=+30days` |
| `opp-007` | Unicode Opp | tenant-a | Encoding | Unicode in title/description |
| `opp-008` | Large Description | tenant-a | Size boundary | 50KB description |
| `opp-009` | With Intelligence | tenant-a | Relationships | Has linked intelligence |
| `opp-010` | With Documents | tenant-a | Upload relation | Has uploaded files |
| `opp-011` | Synced Opp | tenant-a | Sync tests | `source_type=highergov` |
| `opp-012` | Archived Opp | tenant-a | Status tests | `is_archived=true` |

### 4.4 Intelligence Records (6 canonical)

| ID | Linked Opportunity | Tenant | Purpose |
|----|-------------------|--------|---------|
| `intel-001` | opp-009 | tenant-a | Happy path |
| `intel-002` | opp-001 | tenant-a | CRUD tests |
| `intel-003` | opp-004 | tenant-b | Isolation |
| `intel-004` | opp-001 | tenant-a | Update tests |
| `intel-005` | opp-001 | tenant-a | Delete tests |
| `intel-006` | opp-007 | tenant-a | Unicode content |

### 4.5 RAG Documents (4 canonical)

| ID | Title | Tenant | Purpose |
|----|-------|--------|---------|
| `doc-001` | Company Profile | tenant-a | Happy path ingest |
| `doc-002` | Large Document | tenant-a | Chunking test (100KB) |
| `doc-003` | Unicode Document | tenant-a | Encoding test |
| `doc-004` | Tenant B Doc | tenant-b | Isolation |

### 4.6 Test Files

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

---

## 5. MOCK SERVICES WITH CHAOS CONFIG

### 5.1 Mistral Mock (chat.py:8, rag.py:14)

```json
{
  "base_url": "http://mock-mistral:8082",
  "endpoints": {
    "/v1/chat/completions": {
      "method": "POST",
      "used_by": ["chat.py:send_chat_message"],
      "normal_response": {"status": 200, "body": "chat_completion.json"},
      "chaos": {
        "latency": {
          "min_ms": 100,
          "max_ms": 500,
          "spike_probability": 0.03,
          "spike_ms": 5000
        },
        "errors": {
          "rate_429": 0.02,
          "rate_500": 0.01,
          "rate_timeout": 0.01,
          "rate_malformed_json": 0.005,
          "rate_partial_response": 0.005
        }
      }
    },
    "/v1/embeddings": {
      "method": "POST",
      "used_by": ["rag.py:_get_embeddings"],
      "normal_response": {"status": 200, "body": "embeddings.json"},
      "chaos": {
        "latency": {"min_ms": 50, "max_ms": 200},
        "errors": {"rate_500": 0.02, "rate_timeout": 0.01}
      }
    }
  },
  "deterministic_triggers": {
    "ECHO:": "echo_input",
    "FORCE_ERROR": {"status": 500},
    "FORCE_TIMEOUT": {"delay_ms": 30000}
  },
  "scenarios": {
    "key_rotation": {"trigger_after_requests": 100, "return": 401},
    "rate_limit_burst": {"requests_per_second": 10, "return": 429}
  }
}
```

### 5.2 HigherGov Mock (admin.py:82, sync.py:37,122)

```json
{
  "base_url": "http://mock-highergov:8081",
  "endpoints": {
    "/api/opportunities": {
      "method": "GET",
      "used_by": ["sync.py:sync_highergov_opportunities"],
      "normal_response": {"status": 200, "body": "opportunity_list.json"},
      "chaos": {
        "latency": {
          "min_ms": 50,
          "max_ms": 200,
          "spike_probability": 0.05,
          "spike_ms": 3000
        },
        "errors": {
          "rate_401": 0.01,
          "rate_404": 0.02,
          "rate_500": 0.02,
          "rate_timeout": 0.01
        }
      }
    },
    "/api/opportunities/{id}": {
      "method": "GET",
      "used_by": ["sync.py:fetch_single_opportunity"],
      "normal_response": {"status": 200, "body": "opportunity_detail.json"},
      "chaos": {
        "errors": {"rate_404": 0.05, "rate_500": 0.02}
      }
    }
  },
  "scenarios": {
    "key_rotation": {"trigger_after_requests": 50, "return": 401},
    "schema_drift": {
      "probability": 0.01,
      "field_renames": {"source_id": "sourceId", "notice_id": "noticeId"}
    },
    "rate_limit": {"requests_per_minute": 100, "return": 429}
  }
}
```

### 5.3 Perplexity Mock (admin.py:83, sync.py:38)

```json
{
  "base_url": "http://mock-perplexity:8083",
  "endpoints": {
    "/chat/completions": {
      "method": "POST",
      "used_by": ["perplexity_service.py:sync_perplexity_intelligence"],
      "normal_response": {"status": 200, "body": "perplexity_completion.json"},
      "chaos": {
        "latency": {"min_ms": 200, "max_ms": 1000},
        "errors": {"rate_429": 0.02, "rate_500": 0.01}
      }
    }
  }
}
```

---

## 6. CATEGORY TEST SPECIFICATIONS

### 6.1 AUTH (routes/auth.py) — 3 endpoints, ~30 tests

**Endpoints (verified line numbers):**
| Method | Path | Function | Line |
|--------|------|----------|------|
| POST | /api/auth/login | login | L17 |
| POST | /api/auth/register | register | L51 |
| GET | /api/auth/me | get_current_user_info | L93 |

**DB Operations:** users (find_one, update_one, insert_one), tenants (find_one)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| AUTH-H-001 | Super admin login | admin@example.com / REDACTED_ADMIN_PASSWORD | 200, access_token | L17-49 |
| AUTH-H-002 | Tenant admin login | admin-a@test.com / REDACTED_TEST_PASSWORD | 200, access_token | L17-49 |
| AUTH-H-003 | Tenant user login | user-a@test.com / REDACTED_TEST_PASSWORD | 200, access_token | L17-49 |
| AUTH-H-004 | Get current user | valid token | 200, user object | L93-105 |
| AUTH-H-005 | Register new user | valid user data | 200, user created | L51-91 |
| AUTH-H-006 | Token contains correct claims | login response | sub, role, tenant_id present | L38-44 |

#### BOUNDARY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| AUTH-B-001 | Token near expiry | 1s from expiry | 200 (still valid) |
| AUTH-B-002 | Password at min length (8) | 8 char password | 200 |
| AUTH-B-003 | Email at max length (254) | 254 char email | 200/422 |
| AUTH-B-004 | Concurrent logins same user | 5 simultaneous | All succeed |
| AUTH-B-005 | Case insensitive email | Admin@Outpace.AI | 200 |

#### INVALID Stratum (7 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| AUTH-I-001 | Wrong password | valid email, bad pass | 401 |
| AUTH-I-002 | Unknown email | unknown@test.com | 401 |
| AUTH-I-003 | Malformed email | "not-an-email" | 422 |
| AUTH-I-004 | SQL injection email | "' OR 1=1 --" | 401/422 |
| AUTH-I-005 | Expired token | token from yesterday | 401 |
| AUTH-I-006 | Tampered token | modified JWT signature | 401 |
| AUTH-I-007 | Duplicate email register | existing email | 400 (L58-62) |

#### EMPTY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| AUTH-E-001 | No email | {"password": "x"} | 422 |
| AUTH-E-002 | No password | {"email": "x"} | 422 |
| AUTH-E-003 | Empty body | {} | 422 |
| AUTH-E-004 | No auth header | GET /me without token | 401 |
| AUTH-E-005 | Empty Bearer token | "Authorization: Bearer " | 401 |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| AUTH-P-001 | Login under 1000ms | valid creds | 200 in <1000ms |
| AUTH-P-002 | Token validation under 100ms | valid token | 200 in <100ms |
| AUTH-P-003 | 10 concurrent logins | parallel | All <2000ms |
| AUTH-P-004 | 100 sequential logins | loop | All succeed, <60s total |

#### FAILURE Stratum (3 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| AUTH-F-001 | DB down during login | valid creds, DB dead | 503 |
| AUTH-F-002 | Inactive user login | inactive@test.com | 401 |
| AUTH-F-003 | Deleted user token | token for deleted user | 401 |

---

### 6.2 TENANTS (routes/tenants.py) — 10 endpoints, ~45 tests

**Endpoints (verified line numbers):**
| Method | Path | Function | Line |
|--------|------|----------|------|
| POST | /api/tenants | create_tenant | L20 |
| GET | /api/tenants | list_tenants | L48 |
| GET | /api/tenants/{tenant_id} | get_tenant | L93 |
| PATCH | /api/tenants/{tenant_id} | patch_tenant | L194 |
| PUT | /api/tenants/{tenant_id} | update_tenant | L262 |
| DELETE | /api/tenants/{tenant_id} | delete_tenant | L340 |
| GET | /api/tenants/{tenant_id}/knowledge-snippets | list_knowledge_snippets | L368 |
| POST | /api/tenants/{tenant_id}/knowledge-snippets | create_knowledge_snippet | L389 |
| PUT | /api/tenants/{tenant_id}/knowledge-snippets/{snippet_id} | update_knowledge_snippet | L442 |
| DELETE | /api/tenants/{tenant_id}/knowledge-snippets/{snippet_id} | delete_knowledge_snippet | L494 |

**DB Operations:** tenants (CRUD), users (delete_many), opportunities (delete_many), intelligence (delete_many), chat_messages (delete_many), knowledge_snippets (CRUD)

#### HAPPY Stratum (10 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| TEN-H-001 | List tenants (super) | super_admin token | 200, list | L48-91 |
| TEN-H-002 | Get tenant by ID | valid tenant_id | 200, tenant | L93-113 |
| TEN-H-003 | Create tenant | valid tenant data | 200, tenant | L20-46 |
| TEN-H-004 | Update tenant (PUT) | valid update | 200, updated | L262-338 |
| TEN-H-005 | Patch tenant | partial update | 200, merged | L194-259 |
| TEN-H-006 | Delete tenant | valid tenant_id | 204 | L340-363 |
| TEN-H-007 | List knowledge snippets | valid tenant_id | 200, list | L368-382 |
| TEN-H-008 | Create knowledge snippet | valid data | 200, snippet | L389-439 |
| TEN-H-009 | Update knowledge snippet | valid update | 200, updated | L442-491 |
| TEN-H-010 | Delete knowledge snippet | valid snippet_id | 204 | L494-507 |

#### BOUNDARY Stratum (7 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| TEN-B-001 | Name at max length (255) | 255 char name | 200 |
| TEN-B-002 | Slug at max length (63) | 63 char slug | 200 |
| TEN-B-003 | List 100 tenants | paginated | 200, pagination works |
| TEN-B-004 | All config fields set | max config | 200 |
| TEN-B-005 | Deep nested merge | nested branding | preserved |
| TEN-B-006 | 100 knowledge snippets | large list | 200 |
| TEN-B-007 | Unicode in snippet content | UTF-8 | 200 |

#### INVALID Stratum (10 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| TEN-I-001 | Duplicate slug | existing slug | 400 | L26-31 |
| TEN-I-002 | Unknown field in PUT | extra_field=true | 400 | L293-298 |
| TEN-I-003 | Unknown field in PATCH | extra_field=true | 400 | L224-229 |
| TEN-I-004 | Unknown field in snippet | extra_field=true | 400 | L412-417 |
| TEN-I-005 | Tenant admin creates tenant | tenant_admin token | 403 | L20 |
| TEN-I-006 | User reads other tenant | cross-tenant | 403 | L99-103 |
| TEN-I-007 | Create snippet for master | master tenant | 403 | L423-424 |
| TEN-I-008 | Update non-existent tenant | fake UUID | 404 | L232-237, L301-306 |
| TEN-I-009 | Delete non-existent tenant | fake UUID | 404 | L348-354 |
| TEN-I-010 | Delete non-existent snippet | fake snippet_id | 404 | L504-505 |

#### EMPTY Stratum (6 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| TEN-E-001 | Create tenant no name | name missing | 422 |
| TEN-E-002 | Create tenant no slug | slug missing | 422 |
| TEN-E-003 | Empty update body | {} | 400 (L217-221) |
| TEN-E-004 | List tenants (none exist) | empty DB | 200, [] |
| TEN-E-005 | List snippets (none exist) | empty | 200, [] |
| TEN-E-006 | Create snippet empty content | content: "" | handled |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| TEN-P-001 | List 100 tenants < 500ms | 100 tenants | 200 in <500ms |
| TEN-P-002 | Create tenant < 200ms | valid data | 200 in <200ms |
| TEN-P-003 | Delete cascades < 2s | tenant with data | 204 in <2s |
| TEN-P-004 | 10 concurrent updates | parallel | All succeed |

#### FAILURE Stratum (8 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| TEN-F-001 | DB down | any request | 503 |
| TEN-F-002 | Unique index collision | race condition | 400 |
| TEN-F-003 | Delete tenant cascades users | tenant has users | cascaded |
| TEN-F-004 | Delete tenant cascades opps | tenant has opps | cascaded |
| TEN-F-005 | Delete tenant cascades intel | tenant has intel | cascaded |
| TEN-F-006 | Delete tenant cascades chat | tenant has chat | cascaded |
| TEN-F-007 | Delete tenant cascades snippets | tenant has snippets | cascaded |
| TEN-F-008 | Partial update failure | DB fail mid-update | rollback |

---

### 6.3 CHAT (routes/chat.py) — 3 endpoints, ~35 tests

**Endpoints (verified line numbers):**
| Method | Path | Function | Line |
|--------|------|----------|------|
| POST | /api/chat/message | send_chat_message | L130 |
| GET | /api/chat/history/{conversation_id} | get_chat_history | L435 |
| GET | /api/chat/turns/{conversation_id} | get_chat_turns | L512 |

**External Service:** Mistral API (L8, L358-366)
**DB Operations:** tenants (find_one, update_one), chat_turns (find, insert_one), chat_messages (find), knowledge_snippets (find)

#### HAPPY Stratum (7 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| CHAT-H-001 | Send chat message | valid message | 200, response | L130-432 |
| CHAT-H-002 | Get chat history | valid conversation_id | 200, list | L435-509 |
| CHAT-H-003 | Get chat turns | valid conversation_id | 200, turns | L512-529 |
| CHAT-H-004 | Multi-turn conversation | 3 sequential messages | context preserved | L316-327 |
| CHAT-H-005 | Chat with knowledge injection | tenant has knowledge | knowledge used | L270-287 |
| CHAT-H-006 | Chat with RAG injection | RAG enabled | RAG context used | L289-302 |
| CHAT-H-007 | Quota decrements | send message | messages_used++ | L207-256 |

#### BOUNDARY Stratum (7 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| CHAT-B-001 | Message at max length | max_user_chars | 200 | L199-204 |
| CHAT-B-002 | Quota at 1 remaining | last allowed | 200, then 429 | L207-256 |
| CHAT-B-003 | Conversation ID at max length | 128 chars | 200 | L187-191 |
| CHAT-B-004 | History 100 turns | large history | 200, paginated | L316-320 |
| CHAT-B-005 | Month boundary quota reset | new UTC month | quota resets | L217-234 |
| CHAT-B-006 | Max turns history limit | max_turns_history | older trimmed | L261, L319 |
| CHAT-B-007 | Concurrent same user | 2 parallel chats | both succeed |

#### INVALID Stratum (8 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| CHAT-I-001 | Empty message | message: "" | 400 | L162-166 |
| CHAT-I-002 | Chat disabled | chat_policy.enabled=false | 403 | L180-184 |
| CHAT-I-003 | Quota exceeded | over limit | 429 | L253-256 |
| CHAT-I-004 | Invalid conversation_id format | special chars | 400 | L192-196 |
| CHAT-I-005 | Conversation_id too long | >128 chars | 400 | L187-191 |
| CHAT-I-006 | Message too long | >max_user_chars | 400 | L199-204 |
| CHAT-I-007 | Cross-tenant history | other tenant | isolated | L448-451 |
| CHAT-I-008 | Missing conversation_id | none | 400 | L162-166 |

#### EMPTY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| CHAT-E-001 | No message in body | {} | 400 |
| CHAT-E-002 | Empty chat history | new user | 200, [] |
| CHAT-E-003 | No turns for conversation | empty | 200, [] |
| CHAT-E-004 | Whitespace-only message | "   " | 400 |
| CHAT-E-005 | No knowledge context | disabled | 200, no injection |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| CHAT-P-001 | Response under 5000ms | simple message | 200 in <5s |
| CHAT-P-002 | History list under 500ms | 100 turns | 200 in <500ms |
| CHAT-P-003 | Turns list under 200ms | 50 turns | 200 in <200ms |
| CHAT-P-004 | 5 concurrent chats | parallel | All complete |

#### FAILURE Stratum (4 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| CHAT-F-001 | LLM service down | valid message | 503 | L349-355, L369-376 |
| CHAT-F-002 | LLM timeout | valid message | 503 | L369-376 |
| CHAT-F-003 | DB down during save | valid message | 500 | L399-407 |
| CHAT-F-004 | Quota release on LLM failure | LLM fails | quota restored | L338-347 |

---

### 6.4 OPPORTUNITIES (routes/opportunities.py) — 6 endpoints, ~35 tests

**Endpoints (verified line numbers):**
| Method | Path | Function | Line |
|--------|------|----------|------|
| POST | /api/opportunities | create_opportunity | L25 |
| GET | /api/opportunities | list_opportunities | L96 |
| GET | /api/opportunities/{opp_id} | get_opportunity | L150 |
| DELETE | /api/opportunities/{opp_id} | delete_opportunity | L180 |
| PATCH | /api/opportunities/{opp_id} | update_opportunity_status | L205 |
| GET | /api/opportunities/stats/{tenant_id} | get_opportunity_stats | L253 |

**DB Operations:** opportunities (CRUD, aggregate), tenants (find_one)

#### HAPPY Stratum (7 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| OPP-H-001 | List opportunities | valid token | 200, list | L96-148 |
| OPP-H-002 | Get opportunity by ID | valid opp_id | 200, opportunity | L150-178 |
| OPP-H-003 | Create opportunity | valid data | 200, opportunity | L25-77 |
| OPP-H-004 | Delete opportunity | valid opp_id | 204 | L180-203 |
| OPP-H-005 | Update opportunity status | client_status | 200, updated | L205-251 |
| OPP-H-006 | Get opportunity stats | valid tenant_id | 200, stats | L253-283 |
| OPP-H-007 | Filter by source_type | source_type param | 200, filtered | L117-118 |

#### BOUNDARY Stratum (6 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| OPP-B-001 | List 1000 opportunities | pagination | 200, paginated |
| OPP-B-002 | Filter by min_score | min_score=75 | 200, filtered |
| OPP-B-003 | Search text filter | search param | 200, matched |
| OPP-B-004 | Large description | 50KB | 200 |
| OPP-B-005 | All client fields | status+notes+tags | 200 |
| OPP-B-006 | Concurrent updates | parallel | All succeed |

#### INVALID Stratum (7 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| OPP-I-001 | Cross-tenant list | tenant_id mismatch | filtered | L111-115 |
| OPP-I-002 | Cross-tenant get | other tenant's opp | 403 | L167-171 |
| OPP-I-003 | Cross-tenant delete | other tenant's opp | 403 | L196-200 |
| OPP-I-004 | Cross-tenant update | other tenant's opp | 403 | L225-229 |
| OPP-I-005 | Cross-tenant stats | other tenant | 403 | L262-266 |
| OPP-I-006 | Update non-existent | fake opp_id | 404 | L217-222 |
| OPP-I-007 | Delete non-existent | fake opp_id | 404 | L189-194 |

#### EMPTY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| OPP-E-001 | List empty tenant | no opps | 200, [] |
| OPP-E-002 | Stats empty tenant | no opps | 200, zeros |
| OPP-E-003 | Update ignored fields | non-allowed fields | 200, ignored (L236-237) |
| OPP-E-004 | Create duplicate external_id | same external_id | 400 (L41-49) |
| OPP-E-005 | Get non-existent | fake opp_id | 404 |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| OPP-P-001 | List 100 opps < 500ms | 100 opps | 200 in <500ms |
| OPP-P-002 | Stats aggregation < 300ms | large dataset | 200 in <300ms |
| OPP-P-003 | Bulk create 50 | sequential | All <30s |
| OPP-P-004 | 10 concurrent reads | parallel | All succeed |

#### FAILURE Stratum (6 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| OPP-F-001 | DB down | any request | 503 |
| OPP-F-002 | Tenant not found (create) | fake tenant_id | 404 (L52-57) |
| OPP-F-003 | Opp not found (get) | fake opp_id | 404 |
| OPP-F-004 | Opp not found (delete) | fake opp_id | 404 |
| OPP-F-005 | Opp not found (update) | fake opp_id | 404 |
| OPP-F-006 | Opp not found (stats) | fake tenant_id | 200, zeros |

---

### 6.5 INTELLIGENCE (routes/intelligence.py) — 5 endpoints, ~33 tests

**Endpoints (verified line numbers):**
| Method | Path | Function | Line |
|--------|------|----------|------|
| POST | /api/intelligence | create_intelligence | L24 |
| GET | /api/intelligence | list_intelligence | L50 |
| GET | /api/intelligence/{intel_id} | get_intelligence | L100 |
| DELETE | /api/intelligence/{intel_id} | delete_intelligence | L126 |
| PATCH | /api/intelligence/{intel_id} | update_intelligence | L151 |

**DB Operations:** intelligence (CRUD)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| INT-H-001 | Create intelligence | valid data | 200, intel | L24-48 |
| INT-H-002 | List intelligence | valid token | 200, list | L50-98 |
| INT-H-003 | Get intelligence by ID | valid intel_id | 200, intel | L100-124 |
| INT-H-004 | Delete intelligence | valid intel_id | 204 | L126-149 |
| INT-H-005 | Update intelligence | valid update | 200, updated | L151-192 |
| INT-H-006 | Filter by type | type param | 200, filtered | L70-71 |

#### BOUNDARY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| INT-B-001 | Large content | 100KB text | 200 |
| INT-B-002 | List 500 records | pagination | 200 |
| INT-B-003 | Unicode content | UTF-8 special | 200 |
| INT-B-004 | Search filter | search param | 200, matched |
| INT-B-005 | Multiple per tenant | 10 records | all returned |

#### INVALID Stratum (7 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| INT-I-001 | Create for other tenant | cross-tenant | 403 | L33-37 |
| INT-I-002 | Get other tenant's intel | cross-tenant | 403 | L117-121 |
| INT-I-003 | Delete other tenant's intel | cross-tenant | 403 | L142-146 |
| INT-I-004 | Update other tenant's intel | cross-tenant | 403 | L167-171 |
| INT-I-005 | Get non-existent | fake intel_id | 404 | L110-114 |
| INT-I-006 | Delete non-existent | fake intel_id | 404 | L135-140 |
| INT-I-007 | Update non-existent | fake intel_id | 404 | L160-165 |

#### EMPTY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| INT-E-001 | List empty tenant | no intel | 200, [] |
| INT-E-002 | Empty update body | {} | 200 (no-op) |
| INT-E-003 | Update ignored fields | non-allowed fields | ignored (L178-179) |
| INT-E-004 | Null content | content: null | handled |
| INT-E-005 | Whitespace content | "   " | handled |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| INT-P-001 | Create under 200ms | valid data | 200 in <200ms |
| INT-P-002 | List 100 under 500ms | 100 records | 200 in <500ms |
| INT-P-003 | Get single under 100ms | valid id | 200 in <100ms |
| INT-P-004 | 5 concurrent creates | parallel | All succeed |

#### FAILURE Stratum (6 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| INT-F-001 | DB down | any request | 503 |
| INT-F-002 | Intel not found (get) | fake id | 404 |
| INT-F-003 | Intel not found (delete) | fake id | 404 |
| INT-F-004 | Intel not found (update) | fake id | 404 |
| INT-F-005 | Connection pool exhausted | high load | 503 |
| INT-F-006 | Partial update failure | DB fail | rollback |

---

### 6.6 EXPORTS (routes/exports.py) — 2 endpoints, ~28 tests

**Endpoints (verified line numbers):**
| Method | Path | Function | Line |
|--------|------|----------|------|
| POST | /api/exports/pdf | export_branded_pdf | L27 |
| POST | /api/exports/excel | export_branded_excel | L173 |

**DB Operations:** tenants (find_one), opportunities (find), intelligence (find)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| EXP-H-001 | Export opportunities PDF | opportunity_ids | 200, PDF | L27-171 |
| EXP-H-002 | Export opportunities Excel | opportunity_ids | 200, Excel | L173-248 |
| EXP-H-003 | Export intelligence PDF | intelligence_ids | 200, PDF | L27-171 |
| EXP-H-004 | Export mixed PDF | both ids | 200, PDF | L27-171 |
| EXP-H-005 | Export determinism | same input 2x | identical output |
| EXP-H-006 | Tenant branding applied | tenant logo/colors | branded output |

#### BOUNDARY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| EXP-B-001 | Export 100 records | large dataset | 200, complete |
| EXP-B-002 | Unicode in data | special chars | correct encoding |
| EXP-B-003 | Large text fields | 50KB descriptions | 200 |
| EXP-B-004 | Master branding | sub-client | master branding used (L59-60) |
| EXP-B-005 | Empty optional fields | nulls in data | handled |

#### INVALID Stratum (5 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| EXP-I-001 | Missing tenant_id | no tenant_id | 400 | L46-47 |
| EXP-I-002 | Cross-tenant export | other tenant | 403 | L50-51, L193-194 |
| EXP-I-003 | Non-existent tenant | fake UUID | 404 | L54-56, L196-198 |
| EXP-I-004 | Wrong tenant_id for opps | mismatched | filtered |
| EXP-I-005 | User exports other tenant | tenant_user | 403 |

#### EMPTY Stratum (4 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| EXP-E-001 | No matching data | empty ids | 404 | L74-75, L201-202 |
| EXP-E-002 | Empty opportunity_ids | [] | 404 |
| EXP-E-003 | Empty intelligence_ids | [] | 404 |
| EXP-E-004 | Both empty | [] and [] | 404 |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| EXP-P-001 | Export 100 records < 5s | 100 records | 200 in <5s |
| EXP-P-002 | Export 500 records < 15s | 500 records | 200 in <15s |
| EXP-P-003 | 3 concurrent exports | parallel | All succeed |
| EXP-P-004 | Memory stable large export | 1000 records | No OOM |

#### FAILURE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| EXP-F-001 | DB down | any export | 503 |
| EXP-F-002 | Partial read failure | DB fails mid-read | error |
| EXP-F-003 | PDF generation failure | reportlab error | 500 |
| EXP-F-004 | Excel generation failure | openpyxl error | 500 |

---

### 6.7 UPLOAD (routes/upload.py) — 2 endpoints, ~28 tests

**Endpoints (verified line numbers):**
| Method | Path | Function | Line |
|--------|------|----------|------|
| POST | /api/upload/opportunities/csv/{tenant_id} | upload_opportunities_csv | L44 |
| POST | /api/upload/logo/{tenant_id} | upload_tenant_logo | L136 |

**DB Operations:** tenants (find_one, update_one), opportunities (insert_one)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| UPL-H-001 | Upload valid CSV | test_clean.csv | 200, count | L44-134 |
| UPL-H-002 | Upload creates opportunities | new opps | created | L87-121 |
| UPL-H-003 | Upload tenant logo PNG | test_logo.png | 200, data_uri | L136-217 |
| UPL-H-004 | Upload tenant logo JPEG | test_logo.jpg | 200, data_uri | L136-217 |
| UPL-H-005 | Super admin uploads CSV | super token | 200 | L57-61 |
| UPL-H-006 | Logo resized if large | >500px | resized | L178-188 |

#### BOUNDARY Stratum (6 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| UPL-B-001 | 2MB CSV file | test_large.csv | 200 |
| UPL-B-002 | 10000 rows | test_10k_rows.csv | 200 |
| UPL-B-003 | Unicode content | test_unicode.csv | 200 |
| UPL-B-004 | 5MB logo | at limit | 200 | L167-171 |
| UPL-B-005 | Quoted commas in fields | CSV escaping | parsed |
| UPL-B-006 | CRLF line endings | Windows CSV | 200 |

#### INVALID Stratum (6 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| UPL-I-001 | Not a CSV file | .exe file | 400 | L64-68 |
| UPL-I-002 | Non-super admin CSV | tenant_user | 403 | L57-61 |
| UPL-I-003 | Cross-tenant logo | other tenant | 403 | L149-153 |
| UPL-I-004 | Invalid image type | .gif file | 400 | L156-161 |
| UPL-I-005 | Logo too large (>5MB) | 10MB file | 400 | L167-171 |
| UPL-I-006 | Tenant not found (CSV) | fake tenant_id | 404 | L76-81 |

#### EMPTY Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| UPL-E-001 | Empty file (0 bytes) | empty.csv | error |
| UPL-E-002 | Headers only, no data | headers_only.csv | 200, 0 created |
| UPL-E-003 | No file in request | missing file | 422 |
| UPL-E-004 | All empty cell values | blank rows | handled |

#### PERFORMANCE Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| UPL-P-001 | 1000 rows < 10s | 1000 rows | 200 in <10s |
| UPL-P-002 | Logo upload < 2s | 50KB PNG | 200 in <2s |
| UPL-P-003 | 3 concurrent uploads | parallel | All succeed |
| UPL-P-004 | Memory stable large file | 2MB file | No OOM |

#### FAILURE Stratum (4 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| UPL-F-001 | DB down mid-upload | valid file | 503 |
| UPL-F-002 | Tenant not found (logo) | fake tenant_id | 404 | L207-211 |
| UPL-F-003 | CSV parse error | malformed | error | L129-134 |
| UPL-F-004 | Image processing error | corrupt image | error | L189-191 |

---

### 6.8 SYNC (routes/sync.py) — 2 endpoints, ~26 tests

**Endpoints (verified line numbers):**
| Method | Path | Function | Line |
|--------|------|----------|------|
| POST | /api/sync/manual/{tenant_id} | manual_sync_tenant | L15 |
| POST | /api/sync/opportunity/{tenant_id} | fetch_opportunity_by_id | L88 |

**External Services:** HigherGov (L37,122), Perplexity (L38)
**DB Operations:** tenants (find_one, update_one), sync_logs (find_one)

#### HAPPY Stratum (5 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| SYN-H-001 | Manual sync tenant | valid tenant_id | 200, results | L15-86 |
| SYN-H-002 | Sync single opportunity | opportunity_id | 200, synced | L88-134 |
| SYN-H-003 | Sync creates new opps | new from API | created |
| SYN-H-004 | Sync type=opportunities | opportunities only | 200 | L51-59 |
| SYN-H-005 | Sync type=intelligence | intelligence only | 200 | L62-70 |

#### BOUNDARY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| SYN-B-001 | Sync 100 opportunities | large batch | 200 |
| SYN-B-002 | Unicode in synced data | special chars | preserved |
| SYN-B-003 | Concurrent syncs | 2 parallel | handled |
| SYN-B-004 | Empty sync response | no new opps | 200, 0 created |
| SYN-B-005 | Both services sync | sync_type=all | both synced |

#### INVALID Stratum (5 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| SYN-I-001 | Non-existent tenant | fake UUID | 404 | L29-34, L108-113 |
| SYN-I-002 | Cross-tenant fetch | other tenant | 403 | L102-106 |
| SYN-I-003 | Missing opportunity_id | no opp_id | 400 | L115-120 |
| SYN-I-004 | Non-super admin manual sync | tenant_user | 403 | L19 |
| SYN-I-005 | Invalid sync_type | sync_type=fake | ignored |

#### EMPTY Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| SYN-E-001 | Sync tenant no config | no HigherGov setup | handled |
| SYN-E-002 | Empty sync response | API returns [] | 200, 0 synced |
| SYN-E-003 | Null opportunity_id | opp_id: null | 400 |
| SYN-E-004 | New tenant first sync | no existing data | 200 |

#### PERFORMANCE Stratum (3 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| SYN-P-001 | Sync 50 opps < 30s | 50 opportunities | 200 in <30s |
| SYN-P-002 | Single opp sync < 5s | 1 opportunity | 200 in <5s |
| SYN-P-003 | 3 concurrent syncs | parallel tenants | All succeed |

#### FAILURE Stratum (4 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| SYN-F-001 | HigherGov down | sync request | error in results | L56-59, L68-70 |
| SYN-F-002 | Perplexity down | intelligence sync | error in results | L62-70 |
| SYN-F-003 | Partial sync failure | some opps fail | partial success | L78 |
| SYN-F-004 | DB down | any request | 503 |

---

### 6.9 CONFIG (routes/config.py) — 2 endpoints, ~24 tests

**Endpoints (verified line numbers):**
| Method | Path | Function | Line |
|--------|------|----------|------|
| PUT | /api/config/tenants/{tenant_id}/intelligence-config | update_intelligence_config | L33 |
| GET | /api/config/tenants/{tenant_id}/intelligence-config | get_intelligence_config | L135 |

**DB Operations:** tenants (find_one, update_one)

#### HAPPY Stratum (5 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| CFG-H-001 | Get intelligence config | valid tenant_id | 200, config | L135-161 |
| CFG-H-002 | Update intelligence config | valid config | 200, updated | L33-133 |
| CFG-H-003 | Update cron expression | valid cron | 200 | L94-100 |
| CFG-H-004 | Super admin updates | super token | 200 | L79-83 |
| CFG-H-005 | Tenant admin updates own | tenant_admin | 200 | L79-83 |

#### BOUNDARY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| CFG-B-001 | All config fields set | max config | 200 |
| CFG-B-002 | Complex cron expression | "0 0 * * MON-FRI" | 200 |
| CFG-B-003 | scoring_weights all set | all 6 weights | 200 |
| CFG-B-004 | Frequent cron (every minute) | "* * * * *" | 200 |
| CFG-B-005 | Large prompt template | 10KB | 200 |

#### INVALID Stratum (5 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| CFG-I-001 | Invalid JSON body | malformed | 400 | L48-54 |
| CFG-I-002 | Empty JSON body | {} | 400 | L56-60 |
| CFG-I-003 | Unknown fields | extra_field=true | 400 | L63-76 |
| CFG-I-004 | Cross-tenant update | other tenant | 403 | L79-83 |
| CFG-I-005 | Invalid cron expression | "not-a-cron" | 400 | L94-100 |

#### EMPTY Stratum (3 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| CFG-E-001 | Get config new tenant | no config yet | 200, empty | L157-160 |
| CFG-E-002 | Non-existent tenant | fake UUID | 404 | L86-91, L150-155 |
| CFG-E-003 | Null config values | field: null | handled |

#### PERFORMANCE Stratum (3 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| CFG-P-001 | Get config < 100ms | valid request | 200 in <100ms |
| CFG-P-002 | Update config < 200ms | valid update | 200 in <200ms |
| CFG-P-003 | 10 concurrent gets | parallel | All succeed |

#### FAILURE Stratum (3 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| CFG-F-001 | DB down | any request | 503 |
| CFG-F-002 | Tenant not found | fake UUID | 404 | L86-91 |
| CFG-F-003 | Scheduler reload failure | bad config | logged | L119-127 |

---

### 6.10 ADMIN (routes/admin.py) — 3 endpoints, ~27 tests

**Endpoints (verified line numbers):**
| Method | Path | Function | Line |
|--------|------|----------|------|
| GET | /api/admin/dashboard | get_admin_dashboard | L15 |
| POST | /api/admin/sync/{tenant_id} | trigger_manual_sync | L60 |
| GET | /api/admin/system/health | check_system_health | L133 |

**External Services:** HigherGov (L82), Perplexity (L83)
**DB Operations:** tenants (count_documents, find_one, aggregate, update_one), users (count_documents), opportunities (count_documents), intelligence (count_documents), sync_logs (find)

#### HAPPY Stratum (5 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| ADM-H-001 | Get admin dashboard | super_admin token | 200, dashboard | L15-58 |
| ADM-H-002 | Trigger manual sync | valid tenant_id | 200, results | L60-131 |
| ADM-H-003 | Get system health | super_admin token | 200, health | L133-156 |
| ADM-H-004 | Dashboard shows all stats | super_admin | summary object | L48-58 |
| ADM-H-005 | Health shows services | super_admin | services status | L143-147 |

#### BOUNDARY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| ADM-B-001 | Dashboard 100 tenants | large dataset | 200 |
| ADM-B-002 | Sync 100 opportunities | large batch | 200 |
| ADM-B-003 | High usage tenants | >400 rate_limit_used | shown | L34-45 |
| ADM-B-004 | Recent syncs list | 10 syncs | 200 | L30-31 |
| ADM-B-005 | Concurrent dashboard access | 5 parallel | All succeed |

#### INVALID Stratum (5 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| ADM-I-001 | Non-super admin dashboard | tenant_admin | 403 | L17 |
| ADM-I-002 | Non-super admin sync | tenant_admin | 403 | L64 |
| ADM-I-003 | Sync non-existent tenant | fake UUID | 404 | L74-79 |
| ADM-I-004 | Non-super admin health | tenant_user | 403 | L135 |
| ADM-I-005 | Invalid tenant_id format | "not-uuid" | handled |

#### EMPTY Stratum (4 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| ADM-E-001 | Dashboard no tenants | empty system | 200, zeros |
| ADM-E-002 | Sync empty response | no opps from API | 200, 0 synced |
| ADM-E-003 | No high usage tenants | all low | empty list |
| ADM-E-004 | No recent syncs | new system | empty list |

#### PERFORMANCE Stratum (3 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| ADM-P-001 | Dashboard < 1s | valid request | 200 in <1s |
| ADM-P-002 | Health check < 500ms | valid request | 200 in <500ms |
| ADM-P-003 | Sync 50 opps < 30s | 50 opps | 200 in <30s |

#### FAILURE Stratum (5 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| ADM-F-001 | DB down dashboard | dashboard request | 503 |
| ADM-F-002 | HigherGov down sync | sync request | error in results | L101-104 |
| ADM-F-003 | Perplexity down sync | sync request | error in results | L113-115 |
| ADM-F-004 | Health DB unreachable | health request | degraded | L150-154 |
| ADM-F-005 | Partial sync failure | some opps fail | partial results |

---

### 6.11 USERS (routes/users.py) — 5 endpoints, ~33 tests

**Endpoints (verified line numbers):**
| Method | Path | Function | Line |
|--------|------|----------|------|
| POST | /api/users | create_user | L17 |
| GET | /api/users | list_users | L72 |
| GET | /api/users/{user_id} | get_user | L123 |
| PUT | /api/users/{user_id} | update_user | L145 |
| DELETE | /api/users/{user_id} | delete_user | L187 |

**DB Operations:** users (CRUD), tenants (find_one)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| USR-H-001 | Create user | valid data | 200, user | L17-70 |
| USR-H-002 | List users | tenant_admin token | 200, list | L72-121 |
| USR-H-003 | Get user by ID | valid user_id | 200, user | L123-143 |
| USR-H-004 | Update user | valid update | 200, updated | L145-185 |
| USR-H-005 | Delete user | valid user_id | 204 | L187-218 |
| USR-H-006 | Super admin lists all | super_admin | all users |

#### BOUNDARY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| USR-B-001 | Email at max length (254) | 254 chars | 200 |
| USR-B-002 | Full name max length | 255 chars | 200 |
| USR-B-003 | List 100 users | pagination | 200 |
| USR-B-004 | Password at min (8) | 8 chars | 200 |
| USR-B-005 | Concurrent user creates | 5 parallel | All succeed |

#### INVALID Stratum (8 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| USR-I-001 | Duplicate email | existing email | 400 | L26-31 |
| USR-I-002 | Create for other tenant | cross-tenant | 403 | L34-39 |
| USR-I-003 | Create super_admin | role=super_admin | 403 | L40-44 |
| USR-I-004 | Get other tenant's user | cross-tenant | 403 | L137-141 |
| USR-I-005 | Update other tenant's user | cross-tenant | 403 | L163-167 |
| USR-I-006 | Delete other tenant's user | cross-tenant | 403 | L204-208 |
| USR-I-007 | Delete yourself | own user_id | 400 | L211-215 |
| USR-I-008 | Tenant not found | fake tenant_id | 404 | L47-53 |

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
| USR-P-001 | Create user < 300ms | valid data | 200 in <300ms |
| USR-P-002 | List 50 users < 500ms | 50 users | 200 in <500ms |
| USR-P-003 | 10 concurrent reads | parallel | All succeed |
| USR-P-004 | Bulk create 20 | sequential | All <30s |

#### FAILURE Stratum (5 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| USR-F-001 | DB down | any request | 503 |
| USR-F-002 | User not found (get) | fake user_id | 404 | L130-134 |
| USR-F-003 | User not found (update) | fake user_id | 404 | L155-160 |
| USR-F-004 | User not found (delete) | fake user_id | 404 | L196-201 |
| USR-F-005 | Email index conflict | race condition | 400 |

---

### 6.12 RAG (routes/rag.py) — 4 endpoints, ~38 tests

**Endpoints (verified line numbers):**
| Method | Path | Function | Line |
|--------|------|----------|------|
| GET | /api/tenants/{tenant_id}/rag/status | get_rag_status | L74 |
| POST | /api/tenants/{tenant_id}/rag/documents | ingest_document | L105 |
| DELETE | /api/tenants/{tenant_id}/rag/documents/{doc_id} | delete_document | L223 |
| GET | /api/tenants/{tenant_id}/rag/documents | list_documents | L245 |

**External Service:** Mistral API (L14, L48-61)
**DB Operations:** tenants (find_one), kb_documents (CRUD), kb_chunks (CRUD)

#### HAPPY Stratum (6 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| RAG-H-001 | Get RAG status | valid tenant | 200, status | L74-102 |
| RAG-H-002 | Ingest document | valid content | 200, doc_id | L105-220 |
| RAG-H-003 | Delete document | valid doc_id | 204 | L223-242 |
| RAG-H-004 | List documents | valid tenant | 200, list | L245-264 |
| RAG-H-005 | Document gets chunked | 10KB doc | chunks created | L149-157 |
| RAG-H-006 | Embeddings generated | valid doc | embeddings stored | L177-193 |

#### BOUNDARY Stratum (7 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| RAG-B-001 | Document at max size | 100KB | 200 |
| RAG-B-002 | Max documents reached | at limit | 200 | L140-147 |
| RAG-B-003 | Max chunks reached | at limit | 200 | L152-157 |
| RAG-B-004 | Unicode content | UTF-8 special | 200 |
| RAG-B-005 | List 100 documents | pagination | 200 |
| RAG-B-006 | Large chunk count | many chunks | handled |
| RAG-B-007 | Concurrent ingests | 3 parallel | All succeed |

#### INVALID Stratum (7 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| RAG-I-001 | Non-existent tenant | fake UUID | 404 | L82-84, L118-120 |
| RAG-I-002 | Master tenant RAG | master tenant | 403 | L122-123 |
| RAG-I-003 | RAG disabled tenant | rag_enabled=false | 403 | L126-127 |
| RAG-I-004 | Empty document content | content: "" | 400 | L132-133 |
| RAG-I-005 | Document limit exceeded | over max_documents | 409 | L143-147 |
| RAG-I-006 | Chunk limit exceeded | would exceed | 409 | L153-157 |
| RAG-I-007 | Non-existent document | fake doc_id | 404 | L234-235 |

#### EMPTY Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| RAG-E-001 | List empty documents | no docs | 200, [] |
| RAG-E-002 | Status no documents | 0 indexed | 200, count=0 |
| RAG-E-003 | Whitespace content | "   " | 400 |
| RAG-E-004 | New tenant RAG status | no prior use | 200, defaults |
| RAG-E-005 | Delete removes chunks | delete doc | chunks deleted | L238 |

#### PERFORMANCE Stratum (5 tests)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| RAG-P-001 | Ingest 10KB < 5s | 10KB doc | 200 in <5s |
| RAG-P-002 | Ingest 100KB < 30s | 100KB doc | 200 in <30s |
| RAG-P-003 | List 50 docs < 500ms | 50 docs | 200 in <500ms |
| RAG-P-004 | Status check < 200ms | valid tenant | 200 in <200ms |
| RAG-P-005 | 5 concurrent lists | parallel | All succeed |

#### FAILURE Stratum (8 tests)

| ID | Test | Input | Expected | Line |
|----|------|-------|----------|------|
| RAG-F-001 | Embedding service down | ingest request | 503 | L51-54 |
| RAG-F-002 | Embedding timeout | ingest request | handled |
| RAG-F-003 | DB down | any request | 503 |
| RAG-F-004 | Partial ingest failure | fails mid-chunk | cleanup | L212-220 |
| RAG-F-005 | Malformed embedding response | bad vector | handled |
| RAG-F-006 | Document not found (delete) | fake doc_id | 404 | L234-235 |
| RAG-F-007 | Concurrent delete race | 2 deletes same | handled |
| RAG-F-008 | Ingest cleanup on error | error mid-process | chunks deleted | L214-216 |

---

## 7. FAILURE RESPONSE MATRIX

| Status | Pass Rate | Runs | Criteria | Action | Blocks Deploy? |
|--------|-----------|------|----------|--------|----------------|
| **PASS** | 100% | 59/59 | Zero failures | None required | No |
| **FLAKY** | 97-99% | 57-58/59 | 1-2 failures | Investigate within 48h | No |
| **UNSTABLE** | 80-96% | 47-56/59 | 3-12 failures | Block, investigate immediately | **Yes** |
| **FAIL** | <80% | <47/59 | >12 failures | Block, incident created | **Yes** |

### Automatic Actions

```yaml
on_status:
  PASS:
    - log_success
    - update_dashboard
    - update_badge: "Monte Carlo: PASS"

  FLAKY:
    - create_investigation_ticket
    - notify_slack: "#test-alerts"
    - allow_deploy_with_warning
    - update_badge: "Monte Carlo: FLAKY"

  UNSTABLE:
    - block_deploy
    - page_on_call
    - create_incident_ticket: priority=P2
    - update_badge: "Monte Carlo: UNSTABLE"

  FAIL:
    - block_deploy
    - page_on_call: immediate
    - trigger_rollback_if_prod
    - create_incident: priority=P1
    - update_badge: "Monte Carlo: FAIL"
```

---

## 8. CI/CD GATES

### 8.1 Before Merge to Main

```yaml
name: PR Check
on: pull_request

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      mongodb:
        image: mongo:7.0
        ports: [27017:27017]

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r backend/requirements.txt

      - name: Seed test data
        env:
          MONGO_URL: mongodb://localhost:27017
          DB_NAME: outpace_intelligence
        run: |
          python scripts/seed_carfax_tenants.py
          python scripts/seed_carfax_users.py

      - name: Start API
        run: |
          cd backend
          uvicorn main:app --host 0.0.0.0 --port 8000 &
          sleep 5

      - name: CARFAX Smoke (HAPPY only)
        env:
          API_URL: http://localhost:8000
        run: ./carfax.sh all
```

### 8.2 Before Deploy to Staging

```yaml
name: Staging Gate
on:
  push:
    branches: [staging]

jobs:
  full-test:
    runs-on: ubuntu-latest

    steps:
      - name: Run All Strata
        run: |
          for stratum in happy boundary invalid empty performance failure; do
            ./carfax.sh all $stratum || exit 1
          done

      - name: Docker Build
        run: docker-compose -f docker-compose.test.yml build

      - name: Integration Health
        run: |
          docker-compose -f docker-compose.test.yml up -d
          sleep 30
          curl -f http://localhost:8001/health
          docker-compose -f docker-compose.test.yml down
```

### 8.3 Before Deploy to Production

```yaml
name: Production Gate
on:
  workflow_dispatch:
    inputs:
      commit_sha:
        description: 'Commit SHA to deploy'
        required: true

jobs:
  monte-carlo:
    runs-on: ubuntu-latest

    steps:
      - name: Monte Carlo Full (59 runs × 72 strata)
        run: |
          ./scripts/monte_carlo_full.sh

      - name: Verify 100% Pass Rate
        run: |
          PASS_RATE=$(jq '.pass_rate' carfax_reports/monte_carlo_*.json | tail -1)
          if [ "$PASS_RATE" != '"100.0%"' ]; then
            echo "Monte Carlo failed: $PASS_RATE"
            exit 1
          fi

      - name: Manual Sign-off Required
        uses: trstringer/manual-approval@v1
        with:
          approvers: tech_lead,qa_lead
          minimum-approvals: 2
```

---

## 9. ROLLBACK TRIGGERS

### Automatic Rollback Conditions

| Trigger | Threshold | Detection | Action |
|---------|-----------|-----------|--------|
| Health check fails | >5 minutes | /health endpoint 5xx | Rollback |
| Error rate spike | >5% of requests | APM monitoring | Rollback |
| P99 latency | >10 seconds | APM monitoring | Rollback |
| DB connection failures | >10 in 1 minute | Connection pool | Rollback |
| Auth failures | >20% of attempts | Auth middleware logs | Rollback |
| Monte Carlo regression | UNSTABLE or FAIL | CI job | Block deploy |

### Rollback Procedure

```bash
#!/bin/bash
# rollback.sh

# 1. Immediate rollback
kubectl rollout undo deployment/b2b-api

# 2. Verify rollback
kubectl rollout status deployment/b2b-api
curl -f https://api.example.com/health

# 3. Document incident
cat << EOF > incident.json
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "deployed_sha": "$DEPLOYED_SHA",
  "rolled_back_to": "$(kubectl get deployment b2b-api -o jsonpath='{.spec.template.spec.containers[0].image}')",
  "symptoms": "$SYMPTOMS",
  "monte_carlo_status": "$(cat carfax_reports/monte_carlo_*.json | jq -r '.status' | tail -1)"
}
EOF

# 4. Notify
curl -X POST $SLACK_WEBHOOK -d @incident.json
```

---

## 10. DOCKER COMPOSE TEST ENVIRONMENT

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  test-mongo:
    image: mongo:7.0
    ports:
      - "27018:27017"
    environment:
      MONGO_INITDB_DATABASE: outpace_intelligence
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s

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
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8082/health"]
      interval: 10s
      timeout: 5s
      retries: 3

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
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  mock-perplexity:
    build: ./mocks/perplexity
    ports:
      - "8083:8083"
    environment:
      CHAOS_ENABLED: "true"
      CHAOS_LATENCY_MIN_MS: 100
      CHAOS_LATENCY_MAX_MS: 500
      CHAOS_FAILURE_RATE: 0.02
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8083/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  seeder:
    build:
      context: .
      dockerfile: Dockerfile.seeder
    environment:
      MONGO_URL: mongodb://test-mongo:27017
      DB_NAME: outpace_intelligence
    depends_on:
      test-mongo:
        condition: service_healthy
    profiles: ["seed"]

  api:
    build: ./backend
    ports:
      - "8001:8000"
    environment:
      MONGO_URL: mongodb://test-mongo:27017
      DB_NAME: outpace_intelligence
      JWT_SECRET: test-secret-key-12345
      MISTRAL_API_KEY: mock-key
      MISTRAL_API_URL: http://mock-mistral:8082
      HIGHERGOV_API_URL: http://mock-highergov:8081
      PERPLEXITY_API_URL: http://mock-perplexity:8083
      ENVIRONMENT: test
    depends_on:
      test-mongo:
        condition: service_healthy
      mock-mistral:
        condition: service_healthy
      mock-highergov:
        condition: service_healthy
      mock-perplexity:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  test-runner:
    build:
      context: .
      dockerfile: Dockerfile.test
    environment:
      API_URL: http://api:8000
      MONGO_URL: mongodb://test-mongo:27017
      DB_NAME: outpace_intelligence
    depends_on:
      api:
        condition: service_healthy
    volumes:
      - ./carfax_reports:/app/carfax_reports
    profiles: ["test"]
```

### Two-Step Test Flow

```bash
# Step 1: Seed data
docker-compose -f docker-compose.test.yml --profile seed up seeder

# Step 2: Run tests
docker-compose -f docker-compose.test.yml --profile test up test-runner --abort-on-container-exit
```

---

## 11. SUMMARY

| Metric | Value | Source |
|--------|-------|--------|
| Route Files | 12 | `ls backend/routes/*.py` |
| Total Lines | 3,194 | `wc -l` |
| **Total Endpoints** | **47** | `grep @router` |
| Categories | 12 | 1 per route file |
| Strata per Category | 6 | Happy/Boundary/Invalid/Empty/Performance/Failure |
| Total Strata | 72 | 12 × 6 |
| **Total Tests** | **~420** | Sum across categories |
| Monte Carlo Runs/Stratum | 59 | 95% confidence |
| **Total Executions** | **~24,780** | 72 × 59 × ~5.8 |
| External Services | 3 | Mistral, HigherGov, Perplexity |
| MongoDB Collections | 10 | Code analysis |

### Invariants Verified

| ID | Invariant | Test Categories | Strata |
|----|-----------|-----------------|--------|
| INV-1 | Tenant Isolation | ALL | INVALID (cross-tenant tests) |
| INV-2 | Chat Atomicity | CHAT | FAILURE (LLM failures + quota release) |
| INV-3 | Paid Chat Enforcement | CHAT | BOUNDARY (quota tests) |
| INV-4 | Master Tenant Restriction | TENANTS, RAG | INVALID (master tenant tests) |
| INV-5 | Export Determinism | EXPORTS | HAPPY (same input = same output) |

### Endpoint Count Verification

```
grep -c "@router\." backend/routes/*.py | sort -t: -k2 -n -r
───────────────────────────────────────────────────────
tenants.py:10
opportunities.py:6
users.py:5
intelligence.py:5
rag.py:4
admin.py:3
auth.py:3
chat.py:3
config.py:2
exports.py:2
sync.py:2
upload.py:2
───────────────────────────────────────────────────────
TOTAL: 47 endpoints
```

---

END OF TEST PLAN V3
