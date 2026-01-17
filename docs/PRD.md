# Product Requirements Document

**Product:** OutPace B2B Intelligence Dashboard
**Version:** 1.0 Draft
**Updated:** 2026-01-06

---

## 1. Product Summary

Multi-tenant SaaS platform for **Business Development and Strategic Intelligence** in government contracting. Clients track federal contract opportunities, receive AI-generated intelligence reports, and get actionable insights—all branded to their company.

**Core Value:** Actionable intelligence and professional presentation, delivered on the client's schedule.

---

## 2. Business Model

| Tier | Features | Pricing |
|------|----------|---------|
| Basic | Opportunities sync, manual exports | TBD |
| Pro | + Intelligence reports, scheduled delivery | TBD |
| Enterprise | + Chat, RAG, custom intervals | TBD |

**Future:** Stripe integration for subscription billing.

---

## 3. Users & Roles

| Role | Description | Access |
|------|-------------|--------|
| **super_admin** | OutPace staff | All tenants, all config, sync triggers, agent prompts |
| **tenant_user** | Client employee | Own tenant's opportunities, intelligence, chat, exports |
| **master_client** | Special tenant | Restricted from chat/RAG config modification |

---

## 4. URL Architecture (Phase 1)

**Single URL + Login Routing:**
- `app.outpace.ai` (or chosen domain)
- Everyone logs in at same URL
- After login, tenant_id determines:
  - Branding (colors, logo)
  - Data access
  - Feature availability

**Phase 2 (Future):**
- Subdomain per tenant: `acme.outpace.ai`
- Custom domains: `intel.acmecorp.com`

---

## 5. Customization Per Tenant

| Element | Location | Status |
|---------|----------|--------|
| Company logo | Upload via API | Working |
| Brand colors | tenant.branding | Working |
| Card images | tenant.branding | TBD |
| PDF/Excel exports | Uses tenant branding | Working |
| System prompts | agent_config per tenant | Working |

---

## 6. Core Features

### 6.1 Opportunity Sync (Working)
- Pull from HigherGov API based on saved search
- Store in `opportunities` collection per tenant
- Scheduled sync (APScheduler) + manual trigger

### 6.2 Intelligence Reports (Working)
- Generated via Perplexity API
- Configurable intervals per tenant/tier
- Stored in `intelligence` collection

### 6.3 Chat with RAG (Partially Working)
- Mistral AI for LLM
- Two agent types: `opportunities` | `intelligence`
- Quota enforcement per tenant

**CURRENT CAPABILITY:**
- Tenant knowledge injection (company profile, key facts)
- Knowledge snippets (keyword matching)
- RAG documents (embeddings)

**MISSING (Architecture Gap):**
- Chat does NOT query actual `opportunities` collection
- Chat does NOT query actual `intelligence` collection
- User asks "What opportunities do I have?" → Chat doesn't know

**REQUIRED:**
- When agent_type="opportunities": inject relevant opportunity data into context
- When agent_type="intelligence": inject relevant intelligence data into context

### 6.4 Exports (Working)
- Branded PDF with tenant logo/colors
- Branded Excel/CSV
- Deterministic: valid file OR loud failure

### 6.5 Super Admin Configuration (Partial)
- Manage tenants, users
- Trigger sync
- Upload logos, configure branding

**MISSING:**
- Edit agent system prompts via UI
- Configure Perplexity/HigherGov API keys per tenant (if needed)

---

## 7. Integrations

| Service | Purpose | Status |
|---------|---------|--------|
| HigherGov | Contract opportunity data | Working |
| Perplexity AI | Intelligence reports | Working |
| Mistral AI | Chat LLM + RAG embeddings | Working |
| APScheduler | Scheduled sync | Working |
| Stripe | Payment processing | Future |

---

## 8. Security Invariants (All Proven)

| ID | Name | Status |
|----|------|--------|
| INV-1 | Tenant Isolation | Enforced |
| INV-2 | Chat Atomicity | Enforced |
| INV-3 | Paid Chat Enforcement | Enforced |
| INV-4 | Master Tenant Restriction | Enforced |
| INV-5 | Export Determinism | Enforced |

---

## 9. Frontend Requirements

**Framework:** React (or alternative TBD)

### 9.1 Tenant User Pages
| Page | Purpose |
|------|---------|
| Login | Authentication |
| Dashboard | Overview of opportunities, recent intel |
| Opportunities | List + filter + search |
| Opportunity Detail | Full view + chat integration |
| Intelligence Feed | AI-generated reports |
| Chat | Conversational interface |
| Exports | Download PDFs/CSVs |

### 9.2 Super Admin Pages
| Page | Purpose |
|------|---------|
| Admin Dashboard | System overview |
| Tenants | CRUD, branding config |
| Users | Per-tenant user management |
| Sync Control | Manual triggers, schedules |
| Agent Config | Edit system prompts per tenant |

### 9.3 Branding Requirements
- Tenant logo displayed in header
- Brand colors applied to UI
- Card images on dashboard (tailored per tenant)
- Exports reflect tenant branding

---

## 10. Deployment

**Target:** Google Cloud Platform

**Components:**
- Backend: Cloud Run or Compute Engine
- Database: MongoDB Atlas or self-hosted
- Frontend: Cloud Storage + Cloud CDN (static hosting)
- Domain: Custom domain with SSL

**First deployment assistance needed.**

---

## 11. Definition of Done

### 11.1 MVP - Backend Complete
- [x] All 46 endpoints working
- [x] All 5 invariants enforced
- [x] Preflight validation
- [x] Test harness passes
- [x] Rate limiting (slowapi)
- [x] Chat queries opportunities/intelligence (verified in chat.py)

### 11.2 MVP - With Frontend
- [x] All tenant user pages functional
- [x] All super admin pages functional
- [x] Branding applied correctly
- [x] Password Reset pages
- [x] User Profile page
- [x] Playwright E2E tests (14 tests)
- [ ] End-to-end user flows verified manually

### 11.3 Production Ready
- [x] Docker Compose deployment ready
- [x] MongoDB authentication configured
- [x] Nginx reverse proxy with TLS support
- [x] Rate limiting enabled
- [ ] Deployed to GCP
- [ ] Real API keys configured
- [ ] SSL certificate installed
- [ ] At least one paying tenant

---

## 12. Architecture Gaps (Action Required)

| Gap | Description | Priority | Status |
|-----|-------------|----------|--------|
| ~~Chat-Opportunities Integration~~ | ~~Chat queries opportunities collection~~ | ~~HIGH~~ | DONE (chat.py:130-209) |
| ~~Chat-Intelligence Integration~~ | ~~Chat queries intelligence collection~~ | ~~HIGH~~ | DONE (chat.py:212-276) |
| **Screen Context Awareness** | Chat should know which item user is viewing | LOW | OPEN |
| **Agent Prompt Admin UI** | Super admin can't edit system prompts via UI | MEDIUM | OPEN |
| ~~Frontend~~ | ~~Not built~~ | ~~HIGH~~ | DONE (Vite+React) |
| **Stripe Integration** | Payment processing | LOW (Phase 2) | OPEN |
| **Subdomain Routing** | Per-tenant subdomains | LOW (Phase 2) | OPEN |

---

## 13. Out of Scope (Explicit)

- Mobile apps
- Public API for third parties
- White-label reseller capability
- Multi-language support

---

## 14. Revision History

| Date | Change | Author |
|------|--------|--------|
| 2026-01-12 | Production hardening complete: Docker Compose, rate limiting, MongoDB auth, TLS | Agent |
| 2026-01-12 | Frontend complete: Vite migration, Password Reset, User Profile, E2E tests | Agent |
| 2026-01-06 | Initial draft with user context | Agent |

