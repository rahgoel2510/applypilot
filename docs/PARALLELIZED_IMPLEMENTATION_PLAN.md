# ApplyPilot — Parallelized Implementation Plan

**Created:** 2026-08-05  
**Goal:** Compress 20-week sequential roadmap into ~10 weeks via maximum concurrency  
**Approach:** 5 independent workstreams running in parallel, merging at key integration gates

---

## TL;DR — The Proposal

Instead of doing Phases 0→1→2→3→4 sequentially, I decompose the 37 items into **5 independent workstreams** that can execute in parallel. Most items across phases have NO dependency on each other — they touch different files, different layers, different concerns.

**Result:**
- Sequential: ~20 weeks (1 engineer)
- Parallelized: ~10 weeks (1 engineer doing context-switching) or ~4 weeks (5 engineers)
- With AI assistance (you + me): ~6-7 weeks realistic

---

## Dependency Graph (What ACTUALLY Blocks What)

```
                           ┌─────────────────────┐
                           │  WEEK 0 (Day 1)     │
                           │  Emergency Fixes     │
                           │  • Rotate secrets    │
                           │  • Fix CORS          │
                           │  • Remove /env       │
                           │  • Add API key auth  │
                           │  • SQLite WAL mode   │
                           └──────────┬──────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
            ▼                         ▼                         ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│  WORKSTREAM A     │   │  WORKSTREAM B     │   │  WORKSTREAM C     │
│  Security & Auth  │   │  Data Layer       │   │  Privacy &        │
│                   │   │                   │   │  Compliance       │
│  Wk 1-4          │   │  Wk 1-6           │   │  Wk 1-3           │
│  (independent)    │   │  (CRITICAL PATH)  │   │  (independent)    │
└───────────────────┘   └────────┬──────────┘   └───────────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                    │
            ▼                    ▼                    ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│  WORKSTREAM D     │   │  WORKSTREAM E     │   │  Integration      │
│  Observability &  │   │  Multi-Tenancy    │   │  Gate             │
│  Resilience       │   │                   │   │                   │
│  Wk 1-4           │   │  Wk 6-10          │   │  Wk 10            │
│  (independent     │   │  (BLOCKED by B)   │   │  (merge + test)   │
│   until Wk 6)     │   │                   │   │                   │
└───────────────────┘   └───────────────────┘   └───────────────────┘
```

---

## Critical Path Analysis

The **critical path** (longest chain of dependent items) is:

```
SQLite WAL → PostgreSQL Migration → tenant_id on all models → RLS policies → 
Agent isolation → Multi-tenant auth → Integration testing
```

**Total critical path duration: ~10 weeks**

Everything else can run in parallel alongside this chain. Here's why:

| Item | Why it's blocking |
|------|-------------------|
| PostgreSQL migration | Multi-tenancy needs real DB; can't do RLS on SQLite |
| `tenant_id` on models | RBAC, RLS, agent isolation all need tenant context |
| Agent process isolation | Can't run multiple agents without isolated state |

---

## The 5 Workstreams (Detailed)

### Workstream A: Security & Auth (Weeks 1-4, Independent)

No dependency on database migration. All items touch API middleware layer and config.

| Week | Item | Files Touched | Effort |
|------|------|---------------|--------|
| 1 | Rate limiting (`slowapi`) | `main.py` | 4h |
| 1 | WebSocket auth (token on upgrade) | `websocket_routes.py` | 4h |
| 1 | CSRF protection | `main.py` | 2h |
| 1 | Path traversal fix in upload | `settings_routes.py` | 1h |
| 2 | Credential encryption (OS keychain) | `config.py`, new `vault.py` | 2d |
| 2 | Pre-commit secret detection hooks | `.pre-commit-config.yaml` | 2h |
| 3 | Container hardening (non-root, caps) | `docker-compose.yml`, `Dockerfile` | 4h |
| 3 | Reverse proxy config (Caddy/Nginx) | New `infra/Caddyfile` | 4h |
| 3 | Telegram bot multi-factor auth | `bot.py` | 4h |
| 4 | Prompt injection sanitization | `answer_generator.py`, `inmail.py` | 1d |
| 4 | Input validation on all endpoints | `routes.py`, `settings_routes.py` | 1d |

**Output:** Fully hardened API layer, zero auth bypasses, encrypted secrets.

---

### Workstream B: Data Layer (Weeks 1-6, CRITICAL PATH)

This is the bottleneck because PostgreSQL unlocks everything else.

| Week | Item | Files Touched | Effort |
|------|------|---------------|--------|
| 1 | SQLite WAL + busy_timeout + indexes | `database.py`, `models.py` | 4h |
| 1-2 | Design PostgreSQL schema (from SQLite models) | New `migrations/` | 2d |
| 2-3 | PostgreSQL migration + Alembic setup | `database.py`, `models.py`, all routes | 1w |
| 3 | Connection pooling (SQLAlchemy config) | `database.py` | 4h |
| 3 | Replace file-based retry queue → Redis Streams | `retry_queue.py`, new `redis_queue.py` | 2d |
| 4 | Replace file-based daily cap → Redis atomic | `daily_cap.py` | 1d |
| 4 | Externalize pipeline state to Redis | `orchestrator.py` | 2d |
| 5 | Cycle checkpoint/resume mechanism | `orchestrator.py` | 2d |
| 5 | Async dedup (wrap libsql in asyncio.to_thread) | `dedup_db.py` | 4h |
| 6 | Redis Pub/Sub for WebSocket fan-out | `websocket_routes.py` | 1d |
| 6 | Data retention + cleanup scheduler | New `cleanup_scheduler.py` | 1d |

**Output:** PostgreSQL + Redis foundation. Pipeline state externalized. Ready for multi-tenancy.

---

### Workstream C: Privacy & Compliance (Weeks 1-3, Independent)

No dependency on DB migration — these are policy/code changes on current schema.

| Week | Item | Files Touched | Effort |
|------|------|---------------|--------|
| 1 | Create PRIVACY.md (Art. 30 records) | New `docs/PRIVACY.md` | 1d |
| 1 | PII redaction in AI prompts | `answer_generator.py`, `inmail.py` | 1d |
| 1 | Screenshot auto-deletion (24h TTL) | `external_apply.py`, new cron | 4h |
| 2 | Right to erasure endpoint | New `privacy_routes.py` | 2d |
| 2 | Data portability export endpoint | New `privacy_routes.py` | 1d |
| 2 | Consent management for special categories | `settings_routes.py`, frontend | 1d |
| 3 | PII scrubbing in log formatters | `logger.py` | 4h |
| 3 | File permissions hardening (0600/0700) | `browser.py`, `dedup_db.py`, startup | 4h |
| 3 | Graph DB prompt TTL + PII exclusion | `graph/store.py` | 4h |
| 3 | TLS for inter-service communication | `tracker_client.py`, `agent_control.py` | 1d |

**Output:** GDPR-compliant. Right to erasure + export working. PII minimized across all layers.

---

### Workstream D: Observability & Resilience (Weeks 1-4, Independent until Week 6)

Can start immediately. Final integration with Redis/PostgreSQL metrics happens at Week 6.

| Week | Item | Files Touched | Effort |
|------|------|---------------|--------|
| 1 | Structured JSON logging (`structlog`) | `logger.py`, all modules | 2d |
| 1 | Correlation IDs (cycle_id, job_id) | `orchestrator.py`, all modules | 1d |
| 2 | Prometheus metrics endpoint | New `metrics.py`, `main.py` | 2d |
| 2 | Browser watchdog + crash recovery | `browser.py` | 1d |
| 3 | Health check endpoint (comprehensive) | `resilience/health.py`, `main.py` | 1d |
| 3 | Circuit breaker persistence (Redis) | `circuit_breaker.py` | 4h |
| 3 | Graceful degradation wiring | `orchestrator.py` | 1d |
| 4 | Async pipeline with bounded queues | `orchestrator.py` | 2d |
| 4 | Backpressure between discovery/eval | `orchestrator.py` | 1d |
| 4 | Browser memory management | `browser.py` | 4h |

**Output:** Observable system. Prometheus metrics. Structured logs. Self-healing browser. Proper backpressure.

---

### Workstream E: Multi-Tenancy (Weeks 6-10, BLOCKED BY Workstream B)

Cannot start until PostgreSQL migration is complete (needs real RLS, real connection pooling, real schemas).

| Week | Item | Files Touched | Effort |
|------|------|---------------|--------|
| 6 | User + Organization + Membership models | `models.py`, new `auth_models.py` | 2d |
| 6-7 | OAuth2/OIDC integration (auth middleware) | New `auth/`, `main.py` | 1w |
| 7 | `tenant_id` on all existing models + RLS | `models.py`, all routes, migrations | 1w |
| 8 | Per-tenant credential storage | New `secrets_service.py` | 2d |
| 8 | Agent pool (container-per-tenant) | `agent_control.py`, Docker config | 3d |
| 9 | RBAC system (roles + permissions) | New `rbac/`, middleware | 1w |
| 9 | Usage metering + quota enforcement | New `billing/` | 3d |
| 10 | Tenant provisioning + lifecycle | New `tenants/` | 3d |
| 10 | Integration testing + load testing | `tests/` | 3d |

**Output:** Full multi-tenant SaaS. Isolated users, RBAC, billing, provisioned lifecycle.


---

## Week-by-Week Gantt (Visual)

```
         Wk1    Wk2    Wk3    Wk4    Wk5    Wk6    Wk7    Wk8    Wk9    Wk10
         ────── ────── ────── ────── ────── ────── ────── ────── ────── ──────
[A] Sec  ██████ ██████ ██████ ██████ ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░
[B] Data ██████ ██████ ██████ ██████ ██████ ██████ ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░  ← CRITICAL PATH
[C] Priv ██████ ██████ ██████ ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░
[D] Obs  ██████ ██████ ██████ ██████ ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░
[E] MT   ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░ ░░░░░░ ██████ ██████ ██████ ██████ ██████
                                              ▲
                                              │ GATE: PostgreSQL ready
                                              │ (Workstream B delivers)

█ = Active work    ░ = Not yet started / completed
```

**Context-switching schedule for 1 engineer:**

```
Morning block (4h):    Workstream B (Data Layer — critical path, needs deep focus)
Afternoon block (4h):  Rotate between A, C, D (independent items, can context-switch)
```

This keeps the critical path always moving while making progress on other streams.

---

## Integration Gates (Merge Points)

| Gate | Week | What Must Be True | Who Merges |
|------|------|-------------------|------------|
| **G0** | End of Day 1 | Emergency fixes live, API key auth working | You |
| **G1** | End of Wk 3 | Security (A) + Privacy (C) merged to main. All current tests pass. | CI |
| **G2** | End of Wk 6 | PostgreSQL live. Redis live. All data migrated. Observability (D) merged. | You |
| **G3** | End of Wk 10 | Multi-tenancy merged. Full integration tests green. Load test passed. | You |

---

## What Can Run LITERALLY In Parallel (Same Day)

These items have ZERO file overlap and can be coded simultaneously:

```
DAY 1 (Emergency — all touch different files):
├── Fix CORS                      → main.py (1 line change)
├── Add API key auth              → new auth_middleware.py
├── Remove /api/settings/env      → settings_routes.py  
├── Sanitize upload filename      → settings_routes.py (different function)
└── Enable WAL mode               → database.py

WEEK 1 (All independent):
├── [A] Rate limiting             → main.py (middleware)
├── [B] PostgreSQL schema design  → new migrations/ directory
├── [C] PRIVACY.md document       → docs/ (just writing)
├── [C] PII redaction in prompts  → answer_generator.py, inmail.py
├── [D] Structured logging        → logger.py
└── [D] Correlation IDs           → orchestrator.py

WEEK 2 (All independent):
├── [A] Credential encryption     → new vault.py, config.py
├── [B] PostgreSQL migration      → database.py, models.py (big change)
├── [C] Right to erasure endpoint → new privacy_routes.py
├── [C] Data portability export   → new privacy_routes.py
├── [D] Prometheus metrics        → new metrics.py
└── [D] Browser watchdog          → browser.py
```

---

## Effort Comparison

| Approach | Calendar Time | Engineer-Hours | Risk |
|----------|-------------|----------------|------|
| **Sequential** (Phase 0→1→2→3→4) | 20 weeks | ~480h | Low (simple) |
| **Parallelized** (5 workstreams, 1 eng) | 10 weeks | ~480h | Medium (context-switching) |
| **Parallelized** (5 workstreams, 3 eng) | 6 weeks | ~480h | Medium (coordination) |
| **Parallelized** (5 workstreams, 5 eng) | 4 weeks | ~480h | High (merge conflicts) |
| **You + AI pair** (realistic) | 6-7 weeks | ~300h | Low-Medium |

---

## My Recommendation: The Optimal Solo Engineer Plan

If you're doing this yourself (with me helping), here's what I'd do:

### Sprint 1 (Weeks 1-2): Foundation

**Focus:** Get secure + observable + privacy-compliant on CURRENT architecture.  
**Why:** Immediately deployable to VM with confidence.

```
Mon-Tue:  [A] Auth middleware + rate limiting + CORS (already coded above)
Wed:      [C] PRIVACY.md + PII redaction in AI prompts
Thu:      [D] Structured logging + correlation IDs  
Fri:      [C] Screenshot TTL + file permissions

Mon:      [A] Credential encryption (vault.py + OS keychain)
Tue:      [B] PostgreSQL schema design + Alembic setup
Wed-Thu:  [C] Right to erasure + data export endpoints
Fri:      [D] Prometheus metrics + browser watchdog
```

**End of Sprint 1:** App is secure, private, observable. Deploy to VM NOW.

### Sprint 2 (Weeks 3-4): Data Layer Migration

**Focus:** PostgreSQL + Redis. This is the hardest, most impactful work.

```
Mon-Wed:  [B] PostgreSQL migration (schema + all queries)
Thu:      [B] Connection pooling + read/write split
Fri:      [B] Redis setup + retry queue migration

Mon:      [B] Daily cap → Redis atomic
Tue:      [B] Pipeline state → Redis
Wed:      [D] Async pipeline + bounded queues + backpressure
Thu:      [B] Cycle checkpoint/resume
Fri:      [B] WebSocket fan-out (Redis Pub/Sub)
```

**End of Sprint 2:** Scalable data layer. Self-healing pipeline. Can handle concurrent load.

### Sprint 3 (Weeks 5-6): Multi-Tenancy Foundation

**Focus:** User model, auth, tenant isolation.

```
Mon-Tue:  [E] User + Org models + OAuth2 integration
Wed-Fri:  [E] tenant_id on all models + RLS policies

Mon-Tue:  [E] Per-tenant credentials (secrets service)
Wed-Thu:  [E] Agent pool architecture (container-per-tenant)
Fri:      [E] RBAC system
```

### Sprint 4 (Weeks 7-8): Polish & Ship

```
Mon-Tue:  [E] Usage metering + quotas
Wed:      [E] Tenant provisioning/lifecycle
Thu-Fri:  Integration testing + load testing + bug fixes
```

---

## What You Can Ship at Each Checkpoint

| Checkpoint | What's Live | Users Supported |
|-----------|-------------|-----------------|
| **End of Day 1** | Secured API (auth + CORS) | You, safely on public VM |
| **End of Week 2** | Full security + privacy + observability | You, GDPR-compliant |
| **End of Week 4** | PostgreSQL + Redis + resilient pipeline | You, with high availability |
| **End of Week 6** | Multi-tenant auth + isolation | You + 5-10 beta users |
| **End of Week 8** | Full SaaS with RBAC + billing | Unlimited users |

---

## Files That CANNOT Be Worked On Concurrently

These are merge-conflict hotspots — only one workstream should touch them at a time:

| File | Touched By | Resolution |
|------|-----------|------------|
| `main.py` | A (middleware), D (metrics) | A goes first (Week 1), D adds after (Week 2) |
| `orchestrator.py` | B (state), D (backpressure) | B goes first (Week 4), D adds after (Week 4 late) |
| `models.py` | B (PostgreSQL), E (tenant_id) | B completes first (Week 3), E adds columns (Week 6) |
| `database.py` | B (PostgreSQL), E (RLS) | B completes first (Week 3), E adds RLS (Week 7) |

Everything else has clean separation — different files entirely.

---

## How to Start Right Now

I can begin implementing **Sprint 1** immediately. The highest-impact, zero-dependency items I can code today:

1. ✅ Auth middleware (new file, no conflicts)
2. ✅ CORS fix (1-line change in `main.py`)
3. ✅ Rate limiting setup (add to `main.py`)
4. ✅ PRIVACY.md (documentation only)
5. ✅ PII redaction wrapper for AI prompts (touches only `answer_generator.py`)
6. ✅ Structured logging migration (touches only `logger.py`)

Want me to start implementing these? I can knock out the Day 1 emergency fixes and Week 1 items right now.
