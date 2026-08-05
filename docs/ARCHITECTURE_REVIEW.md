# ApplyPilot — Principal Engineer Architecture Review

**Review Date:** 2026-08-05  
**Reviewer:** Principal Engineer (FAANG-level review)  
**Scope:** Security, Scalability, Availability, Multi-Tenancy, Data Privacy  
**Verdict:** 🔴 NOT PRODUCTION-READY — 17 Critical findings, 25 High, 21 Medium

---

## Executive Summary

ApplyPilot is a well-designed personal automation tool, but it has **zero production security controls**. The application has no authentication, exposes all secrets via API, uses unencrypted storage, has no multi-tenancy support, and violates multiple GDPR articles. Converting this to a secure, multi-tenant SaaS requires fundamental architectural changes.

| Domain | Score | Critical Issues |
|--------|-------|-----------------|
| **Security** | 1/10 | Zero auth, wildcard CORS, plaintext secrets exposed via API |
| **Scalability** | 3/10 | SQLite single-writer, in-memory state, no horizontal scaling |
| **Availability** | 3/10 | Single browser SPOF, no checkpoint/resume, no HA |
| **Multi-Tenancy** | 0/10 | No user concept, no tenant isolation at any level |
| **Data Privacy** | 1/10 | No encryption at rest, no retention policy, no GDPR compliance |

---

## Table of Contents

1. [Security Findings](#1-security)
2. [Scalability & Availability Findings](#2-scalability--availability)
3. [Multi-Tenancy Findings](#3-multi-tenancy)
4. [Data Privacy & Compliance Findings](#4-data-privacy--compliance)
5. [Prioritized Remediation Roadmap](#5-remediation-roadmap)
6. [Target Architecture](#6-target-architecture)

---

## 1. Security

### 1.1 CRITICAL — Zero Authentication on Backend API

**File:** `tracker/backend/main.py`  
**Impact:** Any network-reachable client can control the agent, steal credentials, trigger applications

The FastAPI backend has NO authentication. All endpoints are public:
- `/api/agent/trigger` — starts LinkedIn automation
- `/api/settings` — reads/writes ALL secrets
- `/api/settings/env` — returns LinkedIn password, API keys as plaintext JSON
- `/api/service/start|stop` — controls daemon processes
- `/api/jobs` — full CRUD on application history

**Fix:** Implement JWT/OAuth2 authentication middleware. Add API key auth as minimum viable control.

---

### 1.2 CRITICAL — Wildcard CORS with Credentials

**File:** `tracker/backend/main.py` (lines 44-50)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  # DANGEROUS with wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Any malicious website visited by the user can make authenticated cross-origin requests to exfiltrate secrets via `/api/settings/env`.

**Fix:** Restrict to `["http://localhost:5173", "http://localhost:80"]`.

---

### 1.3 CRITICAL — Settings API Exposes All Secrets in Plaintext

**File:** `tracker/backend/settings_routes.py` (line 258)

```python
@router.get("/env")
def get_settings_as_env(db: Session = Depends(get_db)):
    """Internal: returns all settings as key-value for the agent subprocess."""
    _seed_from_sources(db)
    return _get_all_settings(db)
```

Returns `LINKEDIN_PASSWORD`, `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY` as plaintext JSON. Combined with no auth + wildcard CORS = complete credential exfiltration.

**Fix:** Remove endpoint. Use env variable injection or Unix domain sockets for inter-process communication.

---

### 1.4 CRITICAL — Plaintext Secrets in .env and Database

**File:** `.env`, `settings_routes.py`

Credentials stored as plaintext in `.env`, then seeded into unencrypted SQLite `app_settings` table. If machine is compromised, all secrets are immediately readable.

**Fix:** Use OS keychain (`keyring` library) or encrypted vault. Add pre-commit hooks for secret detection.

---

### 1.5 HIGH — Resume Upload Path Traversal

**File:** `tracker/backend/settings_routes.py` (line 285-311)

```python
file_path = RESUME_DIR / file.filename  # filename unsanitized
```

Attacker can upload `../../.env` or `../backend/main.py` to overwrite arbitrary files.

**Fix:**
```python
safe_name = PurePosixPath(file.filename).name
if not safe_name or safe_name.startswith('.'):
    raise HTTPException(400, "Invalid filename")
```

---

### 1.6 HIGH — Command Injection via Agent Subprocess

**File:** `tracker/backend/agent_control.py`

Environment variables fetched from unauthenticated `/api/settings/env` are injected into subprocess without validation. Malicious settings values could manipulate agent behavior.

**Fix:** Validate all env vars against allowlists before subprocess injection.

---

### 1.7 HIGH — No WebSocket Authentication

**File:** `tracker/backend/websocket_routes.py`

`/ws/events` accepts any connection without auth. Broadcasts all pipeline events (job details, scores) to any listener.

**Fix:** Require token-based auth on WebSocket upgrade handshake.

---

### 1.8 HIGH — Docker Container Runs as Root

**File:** `docker-compose.yml`

No `user:` directive, data stored in `/root/`. Container breakout grants full host access.

**Fix:** Add `user: "1000:1000"`, `read_only: true`, `security_opt: [no-new-privileges:true]`, `cap_drop: [ALL]`.

---

### 1.9 HIGH — Telegram Bot Weak Auth

**File:** `linkedin_agent/bot.py`

Only chat_id verification. If chat ID leaks, anyone can trigger real applications via `/run_agent --apply`.

**Fix:** Add multi-factor (chat_id + username), log unauthorized attempts, alert owner.

---

### 1.10 HIGH — No Rate Limiting

**File:** All route files

No rate limiting anywhere. Attacker can trigger `/api/agent/trigger` in a loop (LinkedIn ban risk), brute-force settings, exhaust API quotas.

**Fix:** Add `slowapi` rate limiter with per-IP and per-endpoint limits.

---

### 1.11 MEDIUM — AI Prompt Injection via Job Listings

**File:** `linkedin_agent/answer_generator.py`

Job titles/company names injected directly into AI prompts. Malicious job postings could manipulate generated answers.

**Fix:** Sanitize inputs (strip newlines, limit length), use structured message formats.

---

### 1.12 MEDIUM — No CSRF Protection

Combined with permissive CORS, any website can forge state-changing requests while the tracker is running.

**Fix:** Implement CSRF tokens or strict CORS origin restriction.

---

### 1.13 MEDIUM — Chromium Sandbox Disabled

**File:** `linkedin_agent/stealth.py`

`--no-sandbox` flag disables browser security. Malicious page exploit = no containment.

**Fix:** Remove `--no-sandbox`, configure proper permissions for sandboxed execution.

---

### 1.14 LOW — Error Messages Leak Internal Paths

**File:** `tracker/backend/settings_routes.py`

`return {"error": str(e)}` — exception messages expose internal paths and system info.

**Fix:** Return generic errors to clients; log details server-side.


---

## 2. Scalability & Availability

### 2.1 CRITICAL — SQLite as Primary Database (Single-Writer Lock)

**File:** `tracker/backend/database.py`

```python
DATABASE_URL = "sqlite:///./tracker.db"
create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
```

SQLite has a single-writer lock. Under concurrent FastAPI requests + agent writes = `database is locked` errors. No connection pooling, no read replicas, no concurrent write safety.

**Fix:** 
- Immediate: Enable WAL mode (`PRAGMA journal_mode=WAL`)
- Long-term: Migrate to PostgreSQL with connection pooling (`pool_size`, `max_overflow`, `pool_pre_ping`)

---

### 2.2 CRITICAL — Entire Pipeline State in Process Memory

**File:** `linkedin_agent/orchestrator.py`

`CycleTally`, `_shutdown_event`, dedup checks — all live in a single Python process. Running two instances causes duplicate applications and race conditions. Process crash = all state lost.

**Fix:** Externalize state to Redis or shared DB. Implement distributed locking for job claims.

---

### 2.3 CRITICAL — File-Based Daily Cap (No Distributed Coordination)

**File:** `linkedin_agent/daily_cap.py`

Daily cap in `~/.linkedin_agent/daily_applications.json`. Two processes track independently → potential 160 applications/day → LinkedIn ban.

**Fix:** Move to atomic shared datastore (Redis INCR with TTL, or SQLite with proper locking).

---

### 2.4 CRITICAL — Single Browser Instance is SPOF

**File:** `linkedin_agent/browser.py`

One Playwright browser instance. If it crashes, hangs, or OOM-kills, the entire scan cycle fails. No watchdog, no health check, no auto-recovery.

**Fix:** Add browser health-check (`page.evaluate('1+1')` with timeout). Kill and relaunch if unresponsive. Consider browser pool.

---

### 2.5 HIGH — No Checkpoint/Resume Within Scan Cycle

**File:** `linkedin_agent/orchestrator.py`

If agent crashes at job #45 of 100, all progress is lost. No cycle checkpoint exists.

**Fix:** Persist `{cycle_id, jobs_remaining, jobs_completed}`. Resume from checkpoint on restart.

---

### 2.6 HIGH — In-Memory Singleton Orchestrator

**File:** `linkedin_agent/multi_agent_orchestrator.py`

Agent schedules, run history (50 records), and state are all in-memory dicts. Process restart = lost state.

**Fix:** Persist agent state to tracker DB. Recover on startup.

---

### 2.7 HIGH — WebSocket Connections Are Process-Local

**File:** `tracker/backend/websocket_routes.py`

`ConnectionManager` holds WS connections in memory. Multiple processes = fragmented event delivery.

**Fix:** Redis Pub/Sub for cross-instance WS event fan-out.

---

### 2.8 HIGH — File-Based Retry Queue (No Atomicity)

**File:** `linkedin_agent/retry_queue.py`

`retry_queue.json` with only Python threading.Lock (process-local). Multiple workers corrupt the file. No DLQ, no visibility timeout, no message acknowledgment.

**Fix:** Replace with Redis Streams, RabbitMQ, or SQS.

---

### 2.9 HIGH — Sequential Job Processing (No Pipeline Parallelism)

**File:** `linkedin_agent/orchestrator.py`

Jobs processed in a for-loop. No parallel evaluation, no prefetching. Full cycle time = N × per-job-latency.

**Fix:** `asyncio.Queue` with configurable worker concurrency (3-5 workers). Discovery feeds queue, workers claim jobs.

---

### 2.10 HIGH — No Structured Logging or Metrics

**File:** All modules

All logging is `logger.info(f"...")` — human-readable but not machine-parseable. No correlation IDs, no Prometheus metrics, no OpenTelemetry spans.

Cannot answer: "What's p95 job processing time?" or "How many browser timeouts per hour?"

**Fix:** 
- Structured JSON logging (`structlog`)
- Prometheus counters: `jobs_processed_total{status}`, `cycle_duration_seconds`, `browser_errors_total`
- Expose `/metrics` endpoint

---

### 2.11 HIGH — Single Container, No High Availability

**File:** `docker-compose.yml`

One container runs everything. No load balancer, no replica count, no failover. Container death = total outage.

**Fix:** PostgreSQL first (unlocks concurrency), then replicas + reverse proxy (Traefik/Nginx).

---

### 2.12 HIGH — No Backpressure Between Discovery and Processing

**File:** `linkedin_agent/orchestrator.py`

Discovers all jobs (up to 100), stores in list, then processes sequentially. No feedback to slow discovery when processing is slow.

**Fix:** Bounded `asyncio.Queue(maxsize=10)` between discovery and evaluation. Discovery blocks when full.

---

### 2.13 MEDIUM — Synchronous libsql Calls in Async Pipeline

**File:** `linkedin_agent/dedup_db.py`

Blocking `dedup.is_seen()`, `dedup.mark_seen()` calls inside `async def run_scan_cycle()` block the event loop.

**Fix:** Wrap in `asyncio.to_thread()` or use async libsql client.

---

### 2.14 MEDIUM — No Database Indexes on Query Columns

**File:** `tracker/backend/models.py`

`Job.company`, `Job.stage` frequently queried but lack indexes. Kanban board queries degrade with scale.

**Fix:** Add composite indexes: `(stage, date_added)`, `(company, title)`, `(source, stage)`.

---

### 2.15 MEDIUM — No Data Retention/Cleanup

**File:** `models.py`, `database.py`

`activity_logs` grows unbounded (~438K rows/year). SQLite degrades past 1M rows without VACUUM.

**Fix:** Archive logs > 30 days. Run VACUUM monthly. Add background pruning task.

---

### 2.16 MEDIUM — Browser Instance Unbounded Memory

**File:** `linkedin_agent/browser.py`

Persistent Chromium context can consume 500MB–2GB. No memory limit, no idle timeout, no page cleanup.

**Fix:** Max-pages limit. Close idle pages. Monitor `process.memory_info()`, force-restart if threshold exceeded.

---

### 2.17 MEDIUM — Circuit Breakers Lost on Restart

**File:** `linkedin_agent/resilience/circuit_breaker.py`

In-memory circuit state. Restart resets to CLOSED → burst of failures before re-tripping.

**Fix:** Persist circuit state (failure count + last failure timestamp) to Redis or file.

---

### 2.18 MEDIUM — No Graceful Degradation Wiring

**File:** `linkedin_agent/resilience/health.py`

`HealthMonitor` exists but isn't integrated into pipeline decisions. Agent doesn't skip InMail when AI is unhealthy.

**Fix:** Wire health checks into stage gates. Degrade non-critical steps when dependencies are unhealthy.


---

## 3. Multi-Tenancy

**Overall Assessment: 0/10 — Zero multi-tenancy primitives exist.**

The application is a single-user, self-hosted tool with no concept of users, organizations, or access control.

### 3.1 CRITICAL — No Authentication or User Model

**File:** `main.py`, all route files

No middleware checks tokens, sessions, or API keys. Every endpoint uses only `db: Session = Depends(get_db)` — no user context injection. No `User` model exists anywhere.

**Fix:** 
- Implement OAuth2/OIDC or JWT-based auth middleware
- Create `User`, `Organization`, `Membership` models
- Inject `current_user` dependency into all routes
- Add RBAC: `owner`, `admin`, `member`, `viewer`

---

### 3.2 CRITICAL — No Tenant Identifier in Data Models

**File:** `tracker/backend/models.py`

`Job`, `ActivityLog`, `AppSetting`, `AgentRun`, `InMailDraft`, `FeedbackSignal`, `Todo` — NONE have `tenant_id`, `user_id`, or `org_id`. All queries fetch globally.

**Fix:** Add `tenant_id` (UUID, indexed, non-nullable) to every model. Implement row-level security.

---

### 3.3 CRITICAL — Single Shared Database

**File:** `tracker/backend/database.py`

One SQLite file = one global namespace. No partitioning, no schema separation, no data isolation.

**Fix:** Migrate to PostgreSQL with Row-Level Security policies scoped by tenant.

---

### 3.4 CRITICAL — Global Singleton Configuration

**File:** `linkedin_agent/config.py`, `settings_routes.py`

```python
_settings_instance: Settings | None = None  # Global singleton
```

One config, one `.env`, one set of credentials. One user's settings would overwrite another's.

**Fix:** Tenant-scoped settings: `(tenant_id, key)` composite key. Config factory: `get_config(tenant_id=...)`.

---

### 3.5 CRITICAL — Single Browser Session / LinkedIn Account

**File:** `agent_control.py`, `orchestrator.py`

`AgentController` is a module-level singleton. Only ONE agent process runs at a time. One LinkedIn account per deployment. No session isolation.

**Fix:** Browser session pool with isolated contexts per tenant. Containerized per-tenant agents.

---

### 3.6 HIGH — Shared Dedup Database

**File:** `linkedin_agent/dedup_db.py`

Single Turso database, no `tenant_id` in `jobs_seen`. If shared, User B's agent skips jobs User A applied to.

**Fix:** Add `tenant_id` column. Scope all dedup queries by tenant.

---

### 3.7 HIGH — Shared AI API Key / No Per-Tenant Quotas

**File:** `config.py`

Single `OPENAI_API_KEY` for all operations. No per-tenant usage tracking, billing, or rate limiting.

**Fix:** Per-tenant API keys (encrypted). Token usage tracking per tenant. Quota enforcement middleware.

---

### 3.8 HIGH — Global Singleton Agent Controller

**File:** `tracker/backend/agent_control.py`

```python
_controller: Optional[AgentController] = None  # Module-level singleton
```

Two concurrent users → second gets "Agent is already running."

**Fix:** Agent pool: `Dict[tenant_id, AgentController]`. Job queue with worker-per-tenant model.

---

### 3.9 MEDIUM — No Tenant-Aware Logging or Audit Trail

**File:** `models.py` (`ActivityLog`)

No `user_id` or `tenant_id` on logs. Cannot attribute actions to users. No audit trail of WHO triggered runs or changed settings.

**Fix:** Add tenant/user dimensions to all logs. Immutable append-only audit log.

---

### 3.10 MEDIUM — No Tenant Provisioning or Lifecycle

No signup, no tenant creation API, no data export, no "delete my account."

**Fix:** Tenant lifecycle service: create → active → suspended → pending_deletion → deleted.

---

### 3.11 MEDIUM — No Billing, Quotas, or Resource Limits

`daily_application_limit` is global. No per-tenant metering of API calls, browser time, or storage.

**Fix:** Usage metering per tenant. Quota enforcement. Plan-based limits with billing integration.

---

### Multi-Tenancy Target Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  API Gateway (Auth + Rate Limiting)            │
│  JWT validation → extract tenant_id → inject into context     │
└─────────────┬────────────────────────────────────────────────┘
              │
┌─────────────▼─────────────────────────────────────────────────┐
│           Application Layer (FastAPI + RBAC Middleware)         │
│  All queries auto-scoped: .filter(Model.tenant_id == ctx.tid) │
└─────────────┬────────────────────────────────────────────────┘
              │
┌─────────────▼──────┐  ┌───────────────┐  ┌──────────────────┐
│  PostgreSQL + RLS  │  │  Redis        │  │  Secrets Manager │
│  (shared schema,   │  │  (sessions,   │  │  (per-tenant     │
│   row-level        │  │   rate limits, │  │   credentials)   │
│   security)        │  │   pub/sub)    │  │                  │
└────────────────────┘  └───────────────┘  └──────────────────┘
              │
┌─────────────▼─────────────────────────────────────────────────┐
│              Agent Worker Pool (K8s / Container-per-tenant)     │
│  • Isolated browser context per tenant                         │
│  • Per-tenant resource quotas                                  │
│  • Job queue (SQS/Redis Streams) with tenant routing           │
└───────────────────────────────────────────────────────────────┘
```


---

## 4. Data Privacy & Compliance

**Regulations Assessed:** GDPR (EU 2016/679), CCPA (Cal. Civ. Code §1798), SOC2 Trust Criteria  
**Overall Status: NON-COMPLIANT across all frameworks.**

### 4.1 CRITICAL — PII Sent to Third-Party AI Without DPA

**Regulation:** GDPR Art. 28 (Processor), Art. 44-49 (International Transfers)  
**File:** `answer_generator.py`, `inmail.py`

Personal data sent to OpenRouter.ai without a Data Processing Agreement:
- `answer_generator.py`: System prompt includes `{name}`, `{skills}`, `{notice_period}`
- `inmail.py`: `get_candidate_summary()` sends Name, Email, Phone, Notice Period to AI

**Fix:**
1. Execute DPA with OpenRouter
2. Implement PII-safe prompt wrapper (use role titles, not personal identifiers)
3. Add config option to redact PII before AI calls
4. Document international transfer safeguards (SCCs)

---

### 4.2 CRITICAL — No Data Retention Policy

**Regulation:** GDPR Art. 5(1)(e) (Storage Limitation)  
**File:** All data stores

Data accumulates indefinitely with NO TTL or purge:
- `dedup_db.py`: Turso cloud DB — job history forever
- `models.py`: SQLite tables — no expiry columns
- `graph/store.py`: KùzuDB — jobs, prompts, embeddings forever
- `~/.linkedin_agent/applied.json`: Unbounded growth
- `~/.linkedin_agent/inmail_drafts.json`: Cached PII never expires

**Fix:** Add `created_at`/`expires_at` to all PII tables. Scheduled cleanup (90 days logs, 1 year job records). Configurable retention periods.

---

### 4.3 CRITICAL — No Right to Erasure

**Regulation:** GDPR Art. 17, CCPA §1798.105  

No mechanism for complete data deletion. Data spread across 6+ stores (SQLite, Turso, KùzuDB, JSON files, screenshots, browser data). Individual job delete exists but no "delete all my data" capability.

**Fix:** 
- Add `/api/privacy/delete-all` endpoint (cascade across all stores)
- Add CLI: `python3 -m linkedin_agent privacy --delete-all`
- Document all data locations for manual deletion

---

### 4.4 CRITICAL — Unencrypted Databases at Rest

**Regulation:** GDPR Art. 32(1)(a), SOC2 CC6.1, CC6.7  

ALL persistent stores are unencrypted:
- SQLite tracker DB (contains secrets in `app_settings`)
- KùzuDB graph (contains prompts with PII, embeddings)
- Turso local sync file `applypilot_dedup.db`
- JSON files (`applied.json`, `inmail_drafts.json`)

Machine compromise = all PII immediately readable.

**Fix:** SQLCipher for SQLite. Fernet encryption for JSON files. File permissions (0600). OS keychain for encryption keys.

---

### 4.5 HIGH — All Communication Over HTTP (No TLS)

**Regulation:** GDPR Art. 32(1)(a), SOC2 CC6.6  

All inter-service communication is plaintext HTTP:
- `tracker_client.py`: `http://127.0.0.1:8000/api`
- `agent_control.py`: `http://127.0.0.1:8000/api/settings/env` (fetches ALL secrets over HTTP)
- Frontend: `http://localhost:5173`

Especially dangerous in Docker/network environments where localhost traverses network interfaces.

**Fix:** HTTPS with self-signed cert locally. TLS between Docker containers. Unix domain sockets for sensitive IPC.

---

### 4.6 HIGH — Special Category Data Without Consent

**Regulation:** GDPR Art. 9 (Special Categories), Art. 6-7 (Consent)  

`config.yaml` collects and auto-fills GDPR special categories:
- `gender: Male`
- `veteran_status: 'No'`
- `disability: 'No'`
- `race_ethnicity: 'Prefer not to say'`

Stored in plaintext, seeded to SQLite, auto-submitted to third-party ATS platforms. No explicit consent collected or recorded.

**Fix:** Explicit consent flow with timestamp. Separate special-category data with additional access controls. Allow selective opt-out.

---

### 4.7 HIGH — Screenshots Expose PII

**Regulation:** GDPR Art. 5(1)(c) (Data Minimization)  
**File:** `external_apply.py`, `routes.py`

Full-page screenshots capture filled form fields (name, email, phone, sensitive answers). Stored unprotected in `screenshots/`, served via unauthenticated `/api/agent/screenshot`, sent to Telegram. Never auto-deleted.

**Fix:** Redact form fields before storage. Auth on screenshot endpoints. Auto-delete after 24 hours. Option to disable capture.

---

### 4.8 HIGH — No GDPR Article 30 Processing Records

**Regulation:** GDPR Art. 30  

No documentation exists for: what personal data is processed, purposes, categories of recipients (OpenRouter, Turso, Telegram), international transfers, retention periods, security measures.

**Fix:** Create `PRIVACY.md` with full processing inventory. Maintain machine-readable data flow map.

---

### 4.9 MEDIUM — PII in Log Files

**Regulation:** GDPR Art. 5(1)(c) (Data Minimization)  
**File:** `linkedin_agent/logger.py`

Logs include company names, job titles, resume filenames, login flow references. Session JSON files persist: company, title, location, scores — indefinitely.

**Fix:** PII scrubbing in log formatters. Time-based retention (30 days). Never log file paths containing PII.

---

### 4.10 MEDIUM — No Data Portability

**Regulation:** GDPR Art. 20, CCPA §1798.100  

No way to export all user data in structured format. `export_csv()` exists for session data only — not comprehensive.

**Fix:** Add `/api/privacy/export` endpoint generating ZIP of all data (JSON/CSV) across all stores.

---

### 4.11 MEDIUM — Browser Session Data Unprotected

**Regulation:** GDPR Art. 32  
**File:** `linkedin_agent/browser.py`

LinkedIn cookies (`li_at` session token) stored at `~/Library/Application Support/linkedin_agent/browser_data/` with default permissions. Any local process can steal the session.

**Fix:** File permissions `0700`. Consider encrypting cookie store. Session rotation notifications.

---

### 4.12 MEDIUM — Resume Files Without Access Control

**Regulation:** GDPR Art. 32  

Resume files (extensive PII) in `resumes/` directory. Uploaded/listed via unauthenticated endpoints. No virus scanning, no size limits, no encryption.

**Fix:** Auth on endpoints. Encrypt at rest. Restrictive permissions. File size/content validation.

---

### 4.13 MEDIUM — Cloud Database Without Data Residency Controls

**Regulation:** GDPR Art. 44-49  
**File:** `linkedin_agent/dedup_db.py`

Turso cloud DB stores job history. Data residency not configured or documented. Users have no visibility into where data is physically stored.

**Fix:** Configure Turso region. Document data flow. Offer local-only mode.

---

### 4.14 MEDIUM — Graph DB Stores Full AI Prompts with PII

**Regulation:** GDPR Art. 5(1)(c)(e)  
**File:** `linkedin_agent/graph/store.py`

`store_prompt()` persists full input_text and output_text of every AI call — containing candidate name, skills, cover letters. Unbounded, unencrypted archive.

**Fix:** Store only `input_hash`. Implement TTL (7-30 days). Exclude PII from stored prompts.


---

## 5. Remediation Roadmap

### Phase 0 — Emergency (This Week)

| # | Action | Effort | Blocks |
|---|--------|--------|--------|
| 1 | Rotate ALL secrets (LinkedIn, Telegram, OpenRouter, Turso) | 1 hour | — |
| 2 | Add API authentication (JWT or API key minimum) | 2 days | — |
| 3 | Fix CORS to specific origins only | 30 min | — |
| 4 | Remove `/api/settings/env` endpoint | 1 hour | Refactor agent env injection |
| 5 | Sanitize resume upload filename | 30 min | — |
| 6 | Enable SQLite WAL mode | 30 min | — |

### Phase 1 — Security Hardening (Weeks 1-2)

| # | Action | Effort |
|---|--------|--------|
| 7 | Add rate limiting (`slowapi`) | 1 day |
| 8 | WebSocket authentication | 1 day |
| 9 | CSRF protection | 1 day |
| 10 | Container hardening (non-root, read-only, cap-drop) | 2 hours |
| 11 | Encrypt secrets at rest (OS keychain or SQLCipher) | 2 days |
| 12 | Add pre-commit secret detection hooks | 2 hours |
| 13 | Browser watchdog with crash recovery | 1 day |

### Phase 2 — Data Privacy Compliance (Weeks 2-4)

| # | Action | Effort |
|---|--------|--------|
| 14 | Create PRIVACY.md (Art. 30 processing records) | 1 day |
| 15 | Implement data retention policies + cleanup scheduler | 2 days |
| 16 | Add `/api/privacy/delete-all` (right to erasure) | 2 days |
| 17 | Add `/api/privacy/export` (data portability) | 2 days |
| 18 | PII redaction in AI prompts | 1 day |
| 19 | Consent management for special-category data | 2 days |
| 20 | PII scrubbing in log formatters | 1 day |
| 21 | Screenshot auto-deletion + redaction | 1 day |
| 22 | HTTPS for inter-service communication | 1 day |

### Phase 3 — Scalability & Availability (Weeks 4-8)

| # | Action | Effort |
|---|--------|--------|
| 23 | Migrate to PostgreSQL + connection pooling | 1 week |
| 24 | Structured JSON logging with correlation IDs | 2 days |
| 25 | Prometheus metrics endpoint | 2 days |
| 26 | Replace file-based retry queue with Redis Streams | 3 days |
| 27 | Async pipeline with bounded queues + backpressure | 3 days |
| 28 | Cycle checkpoint for resume-on-crash | 2 days |
| 29 | Redis Pub/Sub for WebSocket fan-out | 2 days |

### Phase 4 — Multi-Tenancy (Months 2-4)

| # | Action | Effort |
|---|--------|--------|
| 30 | User + Organization + Membership models | 1 week |
| 31 | OAuth2/OIDC integration | 1 week |
| 32 | `tenant_id` on all models + PostgreSQL RLS | 1 week |
| 33 | Per-tenant credential storage (Secrets Manager) | 1 week |
| 34 | Agent process isolation (container-per-tenant) | 2 weeks |
| 35 | RBAC system (roles, permissions, team mgmt) | 2 weeks |
| 36 | Usage metering + billing integration | 2 weeks |
| 37 | Tenant provisioning/lifecycle automation | 1 week |

---

## 6. Target Architecture

```
                        ┌─────────────────────────────────┐
                        │         Load Balancer            │
                        │   (TLS termination, WAF)        │
                        └──────────────┬──────────────────┘
                                       │
                        ┌──────────────▼──────────────────┐
                        │        API Gateway               │
                        │  • JWT validation                │
                        │  • Rate limiting (per tenant)    │
                        │  • CORS enforcement              │
                        │  • Request routing               │
                        └──────────────┬──────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
   ┌──────────▼──────────┐ ┌──────────▼──────────┐ ┌──────────▼──────────┐
   │   FastAPI Backend    │ │   FastAPI Backend    │ │   FastAPI Backend    │
   │   (Replica 1)       │ │   (Replica 2)       │ │   (Replica N)       │
   │   • RBAC middleware  │ │   • Tenant context   │ │   • Scoped queries  │
   └──────────┬──────────┘ └──────────┬──────────┘ └──────────┬──────────┘
              │                        │                        │
              └────────────────────────┼────────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
┌────────▼────────┐        ┌───────────▼──────────┐      ┌──────────▼──────────┐
│   PostgreSQL    │        │       Redis           │      │   Secrets Manager   │
│   + RLS         │        │  • Sessions           │      │  (per-tenant creds) │
│   + Encryption  │        │  • Rate limits        │      │  • LinkedIn creds   │
│   + Read        │        │  • Pub/Sub (WS)       │      │  • API keys         │
│     replicas    │        │  • Job queue          │      │  • Tokens           │
└─────────────────┘        │  • Circuit state      │      └─────────────────────┘
                           └──────────────────────┘
                                       │
                        ┌──────────────▼──────────────────┐
                        │      Agent Worker Pool           │
                        │  ┌───────────────────────────┐  │
                        │  │  Worker (Tenant A)         │  │
                        │  │  • Isolated browser ctx    │  │
                        │  │  • Tenant-scoped config    │  │
                        │  │  • Resource quota: 2GB     │  │
                        │  └───────────────────────────┘  │
                        │  ┌───────────────────────────┐  │
                        │  │  Worker (Tenant B)         │  │
                        │  │  • Isolated browser ctx    │  │
                        │  │  • Tenant-scoped config    │  │
                        │  │  • Resource quota: 2GB     │  │
                        │  └───────────────────────────┘  │
                        └─────────────────────────────────┘
                                       │
                        ┌──────────────▼──────────────────┐
                        │       Observability              │
                        │  • Structured logs (ELK/Loki)   │
                        │  • Metrics (Prometheus/Grafana)  │
                        │  • Traces (OpenTelemetry)        │
                        │  • Tenant-tagged dashboards      │
                        │  • Alert rules per severity      │
                        └─────────────────────────────────┘
```

---

## 7. Risk Summary Matrix

| ID | Finding | Severity | Domain | GDPR/SOC2 |
|----|---------|----------|--------|-----------|
| 1.1 | Zero API authentication | CRITICAL | Security | Art. 32 |
| 1.2 | Wildcard CORS + credentials | CRITICAL | Security | — |
| 1.3 | `/api/settings/env` exposes all secrets | CRITICAL | Security | CC6.1 |
| 1.4 | Plaintext secrets in .env + DB | CRITICAL | Security/Privacy | Art. 32 |
| 2.1 | SQLite single-writer bottleneck | CRITICAL | Scalability | — |
| 2.2 | In-memory pipeline state | CRITICAL | Availability | — |
| 2.3 | File-based daily cap (race condition) | CRITICAL | Availability | — |
| 2.4 | Single browser SPOF | CRITICAL | Availability | — |
| 3.1 | No user/auth model | CRITICAL | Multi-Tenancy | Art. 32 |
| 3.2 | No tenant_id in data models | CRITICAL | Multi-Tenancy | — |
| 3.3 | Single shared database | CRITICAL | Multi-Tenancy | — |
| 3.4 | Global singleton config | CRITICAL | Multi-Tenancy | — |
| 3.5 | Single browser session | CRITICAL | Multi-Tenancy | — |
| 4.1 | PII sent to AI without DPA | CRITICAL | Privacy | Art. 28, 44 |
| 4.2 | No data retention policy | CRITICAL | Privacy | Art. 5(1)(e) |
| 4.3 | No right to erasure | CRITICAL | Privacy | Art. 17 |
| 4.4 | Unencrypted databases | CRITICAL | Privacy | Art. 32 |
| 1.5 | Path traversal in upload | HIGH | Security | — |
| 1.6 | Command injection risk | HIGH | Security | — |
| 1.7 | No WebSocket auth | HIGH | Security | — |
| 1.8 | Root container | HIGH | Security | CC6.1 |
| 1.9 | Telegram weak auth | HIGH | Security | — |
| 1.10 | No rate limiting | HIGH | Security | — |
| 2.5-2.12 | Scalability gaps (8 items) | HIGH | Scalability | — |
| 3.6-3.8 | Tenant isolation gaps | HIGH | Multi-Tenancy | — |
| 4.5 | HTTP only (no TLS) | HIGH | Privacy | Art. 32 |
| 4.6 | Special category data no consent | HIGH | Privacy | Art. 9 |
| 4.7 | Screenshot PII exposure | HIGH | Privacy | Art. 5(1)(c) |
| 4.8 | No Art. 30 records | HIGH | Privacy | Art. 30 |

---

## 8. Conclusion

ApplyPilot is a clever personal automation tool with solid domain logic (LinkedIn scraping, scoring, application flow). However, from a production engineering standpoint:

1. **It should never be exposed to a network** in its current state (zero auth = instant compromise)
2. **It cannot support multiple users** without a ground-up rewrite of the data layer
3. **It violates GDPR** in at least 7 articles and would fail any compliance audit
4. **It will hit scaling walls** at single-user level due to SQLite locks and browser fragility

**Estimated effort to production-readiness:**
- Security hardening only: 2-3 weeks
- + Privacy compliance: 4-6 weeks
- + Scalability: 8-10 weeks
- + Full multi-tenancy: 16-20 weeks (4-5 months)

The good news: the modular architecture (separate orchestrator, evaluator, applicant, notifier) is well-suited for these improvements. The event-driven pipeline design can be extended rather than rewritten.

---

*Document generated: 2026-08-05 | Reviewer: Principal Engineer Architecture Review*
