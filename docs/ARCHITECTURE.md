# ApplyPilot — Modular Enterprise Architecture

## Status: DESIGN DOCUMENT (No code changes yet)
## Date: 2026-08-02

---

## 1. Design Principles

1. **Protocol-based DI** — Every service depends on a Protocol, never a concrete class
2. **Single Responsibility** — Each module does ONE thing well
3. **Pipeline-first** — The event bus is the primary execution path; orchestrator is a thin bootstrap layer
4. **Resilience built-in** — Circuit breakers, health checks, graceful degradation at every boundary
5. **Testable by default** — All dependencies injectable; no module-level singletons in business logic

---

## 2. Current Problems

| Problem | Location | Impact |
|---------|----------|--------|
| God-object orchestrator | `orchestrator.py` (50KB) | Untestable, all logic tangled |
| Concrete coupling | Every module imports concrete classes | Can't mock, can't swap |
| Singleton config | `config.py` global `_settings_instance` | Hard to test, can't override per-context |
| Duplicate logic | `orchestrator.py` duplicates `pipeline/linkedin_stages.py` | Two code paths to maintain |
| No resilience | Browser failures crash entire cycle | Lost progress, no partial recovery |
| Mixed concerns in browser.py | Navigation + scraping + form detection + login | 63KB monolith |

---

## 3. Target Module Structure

```
linkedin_agent/
├── __init__.py
├── __main__.py                    # CLI entry point (thin)
├── protocols.py                   # ALL Protocol definitions (the contract layer)
├── container.py                   # DI container — wires protocols to implementations
├── config.py                      # Settings loader (KEEP, but no singleton in business logic)
│
├── core/                          # Domain models & value objects
│   ├── __init__.py
│   ├── models.py                  # Job, ApplicationResult, CycleTally, etc.
│   ├── events.py                  # EventType, JobEvent, StageMarker (MOVE from pipeline/)
│   └── exceptions.py              # Domain exceptions
│
├── services/                      # Business logic services (Protocol implementations)
│   ├── __init__.py
│   ├── discovery.py               # Job discovery orchestration
│   ├── evaluation.py              # Scoring + qualification logic
│   ├── application.py             # Application submission logic (from applicant.py)
│   ├── notification.py            # Telegram notifications (from telegram_bot.py)
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── premium_scorer.py      # LinkedIn Premium match score
│   │   ├── fallback_scorer.py     # Keyword TF-IDF scorer (MOVE)
│   │   └── composite_scorer.py    # Tries premium, falls back to keyword
│   ├── inmail.py                  # InMail drafting (MOVE, slim down)
│   └── external_apply.py          # External ATS handler (MOVE)
│
├── infrastructure/                # I/O adapters (implement protocols)
│   ├── __init__.py
│   ├── browser/
│   │   ├── __init__.py
│   │   ├── session.py             # Launch, login, session management
│   │   ├── navigation.py          # Page navigation, URL construction
│   │   ├── scraper.py             # Job listing extraction, score reading
│   │   ├── form_filler.py         # Easy Apply form automation
│   │   └── stealth.py             # Anti-detection (MOVE)
│   ├── telegram/
│   │   ├── __init__.py
│   │   ├── client.py              # Low-level Telegram API calls
│   │   └── formatter.py           # Message formatting
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── dedup_db.py            # Turso dedup (MOVE)
│   │   ├── daily_cap.py           # Daily cap tracking (MOVE)
│   │   ├── retry_queue.py         # Retry queue (MOVE)
│   │   └── applied_store.py       # Local applied.json (extract from matcher)
│   ├── tracker_client.py          # HTTP client for tracker API (MOVE)
│   └── ai_client.py              # OpenRouter/OpenAI API wrapper (extract from answer_generator)
│
├── resilience/                    # Cross-cutting resilience patterns
│   ├── __init__.py
│   ├── circuit_breaker.py         # Circuit breaker for external calls
│   ├── health.py                  # Health check registry
│   ├── retry.py                   # Retry with backoff (generic)
│   └── graceful.py                # Graceful degradation helpers
│
├── pipeline/                      # Event-driven pipeline (KEEP as primary flow)
│   ├── __init__.py
│   ├── bus.py                     # EventBus (KEEP, enhance with health)
│   ├── stages.py                  # Base stage ABC (KEEP)
│   ├── runner.py                  # PipelineRunner (KEEP, make it THE orchestrator)
│   └── linkedin_stages.py         # LinkedIn stage implementations (REFACTOR to use services)
│
├── orchestrator.py                # GUTTED → thin bootstrap + CLI adapter only
├── scheduler.py                   # KEEP (uses container to get dependencies)
├── bot.py                         # Telegram bot command handler (KEEP, slim)
└── logger.py                      # KEEP
```

---

## 4. Protocols Layer (`linkedin_agent/protocols.py`)

This is the SINGLE source of truth for all interfaces. Every service and infrastructure
module implements one or more of these protocols. Tests mock against these.

### Protocols to define:

```
BrowserSession (Protocol)
├── launch() → None
├── login(email, password) → None
├── close() → None
├── is_healthy() → bool
└── page → Page

JobScraper (Protocol)
├── navigate_to_jobs(collection) → None
├── search_jobs(keyword, location, posted_within) → None
├── get_job_listings(max_count) → list[JobData]
├── open_job(job_id) → None
├── is_already_applied() → bool
├── is_external_apply() → bool
├── get_external_apply_url() → str | None
└── get_match_score() → tuple[int, int]

FormFiller (Protocol)
├── click_easy_apply() → None
├── fill_form_fields(answers: dict) → list[str]  # returns blocking fields
├── submit_application() → bool
├── discard_application() → None
└── upload_resume(path: Path) → None

Scorer (Protocol)
├── score(title, company, location, description) → float | None
└── method_name → str

Notifier (Protocol)
├── send_notification(message: str) → None
├── send_job_applied(title, company, location, score, url) → None
├── send_tally_report(tally: dict) → None
├── request_human_input(question, timeout) → str | None
└── send_inmail_draft(title, company, recruiter, draft) → None

DedupStore (Protocol)
├── is_seen(job_id: str) → bool
├── mark_seen(job_id, **metadata) → None
├── mark_applied(job_id) → None
├── total_seen() → int
└── sync() → None

DailyCap (Protocol)
├── can_apply() → bool
├── record_application() → None
├── today_count → int
├── remaining → int
├── is_at_limit → bool
└── is_near_limit → bool

RetryQueue (Protocol)
├── add(job: dict, error: str) → None
├── get_due() → list[dict]
├── mark_success(job_id: str) → None
├── pending_count → int
├── cleanup_old(max_age_hours: int) → None
└── get_stats() → dict

TrackerClient (Protocol)
├── push_event(event, title, company, **kwargs) → None
├── log(level, category, message, **kwargs) → None
├── log_cycle_start(max_postings, collection) → None
├── log_cycle_end(submitted, skipped, paused, errors, duration_sec) → None
└── push_inmail_draft(title, company, recruiter, draft_text, job_id) → None

AIClient (Protocol)
├── generate_answer(question, context) → str
├── generate_cover_letter(job, candidate) → str
└── is_available() → bool

HealthCheck (Protocol)
├── name → str
├── check() → HealthStatus
└── is_critical → bool

ConfigProvider (Protocol)
├── candidate → CandidateConfig
├── job_search → JobSearchConfig
├── scheduler → SchedulerConfig
├── telegram → TelegramConfig
├── inmail → InmailConfig
├── self_learning → SelfLearningConfig
└── secrets → SecretsConfig
```

### Why a single file?

- Importing any protocol is `from linkedin_agent.protocols import Scorer`
- No circular dependencies (protocols have zero implementation imports)
- Easy to audit the full contract surface area
- IDE autocomplete shows all available interfaces in one place

---

## 5. DI Container (`linkedin_agent/container.py`)

A lightweight, explicit DI container. No magic — just a class that builds the
dependency graph and provides typed accessors.

### Responsibilities:
- Reads `Settings` from `config.py`
- Instantiates all infrastructure implementations
- Wires services with their dependencies
- Provides factory methods for the pipeline stages
- Supports override for testing (`container.override(Scorer, mock_scorer)`)

### Structure:
```python
class Container:
    def __init__(self, config: Settings):
        self._config = config
        self._overrides: dict[type, Any] = {}
        self._singletons: dict[type, Any] = {}

    # Infrastructure
    def browser_session(self) -> BrowserSession: ...
    def job_scraper(self) -> JobScraper: ...
    def form_filler(self) -> FormFiller: ...
    def notifier(self) -> Notifier: ...
    def dedup_store(self) -> DedupStore: ...
    def daily_cap(self) -> DailyCap: ...
    def retry_queue(self) -> RetryQueue: ...
    def tracker(self) -> TrackerClient: ...
    def ai_client(self) -> AIClient: ...

    # Services (composed from infrastructure)
    def scorer(self) -> Scorer: ...          # CompositeScorer(premium, fallback)
    def discovery_service(self) -> DiscoveryService: ...
    def evaluation_service(self) -> EvaluationService: ...
    def application_service(self) -> ApplicationService: ...

    # Pipeline
    def pipeline_runner(self, dry_run: bool = False) -> PipelineRunner: ...

    # Testing support
    def override(self, protocol: type, instance: Any) -> None: ...
    def reset_overrides(self) -> None: ...
```

### Why explicit over a framework?
- Zero external dependencies (no `dependency-injector`, no `inject`)
- Fully type-checked by mypy/pyright
- Easy to understand: one file, read top-to-bottom
- Tests just call `container.override(Protocol, FakeImpl())`

---

## 6. File-by-File Plan

### NEW FILES

| File | Purpose | Exports |
|------|---------|---------|
| `linkedin_agent/protocols.py` | All Protocol definitions | Every protocol listed in §4 |
| `linkedin_agent/container.py` | DI container | `Container` class |
| `linkedin_agent/core/__init__.py` | Package | — |
| `linkedin_agent/core/models.py` | Domain models | `JobData`, `ApplicationResult`, `CycleTally`, `HealthStatus` |
| `linkedin_agent/core/events.py` | Event types (MOVED from pipeline/) | `EventType`, `JobEvent`, `StageMarker`, `Platform` |
| `linkedin_agent/core/exceptions.py` | Domain exceptions | `AgentError`, `BrowserError`, `SessionExpiredError`, `ChallengeDetectedError`, `CapReachedError` |
| `linkedin_agent/services/__init__.py` | Package | — |
| `linkedin_agent/services/discovery.py` | Discovery orchestration logic | `DiscoveryService` |
| `linkedin_agent/services/evaluation.py` | Scoring + qualification | `EvaluationService` |
| `linkedin_agent/services/application.py` | Application submission | `ApplicationService` |
| `linkedin_agent/services/notification.py` | Notification dispatch | `NotificationService` |
| `linkedin_agent/services/scoring/__init__.py` | Package | — |
| `linkedin_agent/services/scoring/premium_scorer.py` | LinkedIn Premium scorer | `PremiumScorer` (implements `Scorer`) |
| `linkedin_agent/services/scoring/fallback_scorer.py` | Keyword scorer | `FallbackScorer` (implements `Scorer`) |
| `linkedin_agent/services/scoring/composite_scorer.py` | Try premium then fallback | `CompositeScorer` (implements `Scorer`) |
| `linkedin_agent/infrastructure/__init__.py` | Package | — |
| `linkedin_agent/infrastructure/browser/__init__.py` | Package | — |
| `linkedin_agent/infrastructure/browser/session.py` | Browser launch/login/close | `PlaywrightSession` (implements `BrowserSession`) |
| `linkedin_agent/infrastructure/browser/navigation.py` | URL navigation | `LinkedInNavigator` (implements part of `JobScraper`) |
| `linkedin_agent/infrastructure/browser/scraper.py` | Job listing extraction | `LinkedInScraper` (implements `JobScraper`) |
| `linkedin_agent/infrastructure/browser/form_filler.py` | Easy Apply form logic | `EasyApplyFormFiller` (implements `FormFiller`) |
| `linkedin_agent/infrastructure/telegram/__init__.py` | Package | — |
| `linkedin_agent/infrastructure/telegram/client.py` | Telegram API wrapper | `TelegramClient` (implements `Notifier`) |
| `linkedin_agent/infrastructure/telegram/formatter.py` | Message templates | `MessageFormatter` |
| `linkedin_agent/infrastructure/persistence/__init__.py` | Package | — |
| `linkedin_agent/infrastructure/persistence/dedup_db.py` | Turso dedup | `TursoDedupStore` (implements `DedupStore`) |
| `linkedin_agent/infrastructure/persistence/daily_cap.py` | Daily cap | `FileDailyCap` (implements `DailyCap`) |
| `linkedin_agent/infrastructure/persistence/retry_queue.py` | Retry queue | `FileRetryQueue` (implements `RetryQueue`) |
| `linkedin_agent/infrastructure/persistence/applied_store.py` | Applied jobs file | `JsonAppliedStore` |
| `linkedin_agent/infrastructure/tracker_client.py` | Tracker HTTP client | `HttpTrackerClient` (implements `TrackerClient`) |
| `linkedin_agent/infrastructure/ai_client.py` | OpenRouter API | `OpenRouterAIClient` (implements `AIClient`) |
| `linkedin_agent/resilience/__init__.py` | Package | — |
| `linkedin_agent/resilience/circuit_breaker.py` | Circuit breaker pattern | `CircuitBreaker` |
| `linkedin_agent/resilience/health.py` | Health check registry | `HealthRegistry`, `HealthStatus` |
| `linkedin_agent/resilience/retry.py` | Generic async retry | `async_retry` decorator |
| `linkedin_agent/resilience/graceful.py` | Graceful degradation | `degrade_to`, `fallback_on_failure` |

### MODIFIED FILES (Major refactoring)

| File | Change | What remains |
|------|--------|--------------|
| `linkedin_agent/orchestrator.py` | **GUTTED from 50KB → ~3KB** | Thin CLI adapter: parses args, builds `Container`, calls `pipeline_runner.run_cycle()` or `run_daemon()`. Keeps `JobAgent` class name for backwards compat but delegates everything. |
| `linkedin_agent/pipeline/events.py` | **Becomes re-export** | `from linkedin_agent.core.events import *` (backwards compat) |
| `linkedin_agent/pipeline/bus.py` | **Add resilience** | Add circuit breaker on handler failures, health reporting, metrics export |
| `linkedin_agent/pipeline/stages.py` | **Minor** | Add `dependencies: list[type]` for self-documenting DI requirements |
| `linkedin_agent/pipeline/linkedin_stages.py` | **REFACTOR** | Stages become thin wrappers that delegate to services. `LinkedInDiscoveryStage.discover_jobs()` calls `self.discovery_service.discover()`. No direct browser/matcher access. |
| `linkedin_agent/pipeline/runner.py` | **Enhance** | Accept `Container` instead of building deps internally. Add health checks before cycle. Add graceful shutdown with in-progress job completion. |
| `linkedin_agent/config.py` | **Minor** | Keep `get_config()` for CLI compat. Add `Settings` implementing `ConfigProvider` protocol. Remove the global singleton pattern from business logic (inject instead). |
| `linkedin_agent/matcher.py` | **SPLIT** | Pure scoring logic → `services/scoring/`. Dedup logic → `infrastructure/persistence/applied_store.py`. Self-learning adjustments → `services/evaluation.py`. |
| `linkedin_agent/applicant.py` | **RENAME + REFACTOR** | Core form-filling logic moves to `infrastructure/browser/form_filler.py`. Orchestration logic (retry, notification, resume selection) moves to `services/application.py`. |
| `linkedin_agent/browser.py` | **SPLIT into 4 files** | See `infrastructure/browser/` above. Each file ≤ 15KB. |
| `linkedin_agent/telegram_bot.py` | **SPLIT** | API calls → `infrastructure/telegram/client.py`. Formatting → `infrastructure/telegram/formatter.py`. |
| `linkedin_agent/bot.py` | **Minor** | Keep as Telegram command handler. Inject `Container` for service access. |
| `linkedin_agent/scheduler.py` | **Minor** | Accept `Container`, use `pipeline_runner` from container. |
| `linkedin_agent/__main__.py` | **Minor** | Build `Container`, dispatch to run modes. |

### DELETED FILES (merged elsewhere)

| File | Merged Into |
|------|-------------|
| `linkedin_agent/daily_cap.py` | `infrastructure/persistence/daily_cap.py` |
| `linkedin_agent/retry_queue.py` | `infrastructure/persistence/retry_queue.py` |
| `linkedin_agent/dedup_db.py` | `infrastructure/persistence/dedup_db.py` |
| `linkedin_agent/fallback_scorer.py` | `services/scoring/fallback_scorer.py` |
| `linkedin_agent/stealth.py` | `infrastructure/browser/stealth.py` (just a move) |
| `linkedin_agent/tracker_client.py` | `infrastructure/tracker_client.py` |
| `linkedin_agent/answer_generator.py` | `infrastructure/ai_client.py` |
| `linkedin_agent/smart_parser.py` | `infrastructure/browser/form_filler.py` (merged) |
| `linkedin_agent/search_modes.py` | `config.py` (inline, it's just preset dicts) |

### UNCHANGED FILES

| File | Reason |
|------|--------|
| `linkedin_agent/logger.py` | Already self-contained |
| `tracker/backend/*` | Separate concern (API server) — Phase 2 refactor |
| `tracker/frontend/*` | Separate concern (React SPA) — no changes needed |
| `tests/*` | Will need updates but that's implementation, not architecture |

---

## 7. Dependency Graph

```
                         ┌─────────────────────┐
                         │   __main__.py        │
                         │   (CLI entry)        │
                         └──────────┬───────────┘
                                    │ builds
                         ┌──────────▼───────────┐
                         │   Container          │
                         │   (wires everything) │
                         └──────────┬───────────┘
                                    │ provides
               ┌────────────────────┼────────────────────┐
               │                    │                    │
    ┌──────────▼──────┐  ┌─────────▼─────────┐  ┌──────▼──────────┐
    │ PipelineRunner  │  │ Scheduler         │  │ Bot (Telegram)  │
    │ (THE primary    │  │ (cron trigger)    │  │ (commands)      │
    │  execution)     │  └─────────┬─────────┘  └─────────────────┘
    └────────┬────────┘            │ calls
             │                     │ runner.run_cycle()
             │ orchestrates        │
    ┌────────▼────────────────────────────────────────────────────┐
    │                    EventBus                                  │
    │  CYCLE_STARTED → DISCOVERED → EVALUATED → QUALIFIED → ...   │
    └────┬──────────────┬──────────────┬──────────────┬───────────┘
         │              │              │              │
    ┌────▼────┐   ┌─────▼─────┐  ┌────▼─────┐  ┌────▼──────────┐
    │Discovery│   │Evaluation │  │Application│  │Notification   │
    │ Stage   │   │ Stage     │  │ Stage     │  │ Stage         │
    └────┬────┘   └─────┬─────┘  └────┬─────┘  └────┬──────────┘
         │              │              │              │
    ┌────▼────┐   ┌─────▼─────┐  ┌────▼─────┐  ┌────▼──────────┐
    │Discovery│   │Evaluation │  │Application│  │Notification   │
    │ Service │   │ Service   │  │ Service   │  │ Service       │
    └────┬────┘   └─────┬─────┘  └────┬─────┘  └────┬──────────┘
         │              │              │              │
    ═════╪══════════════╪══════════════╪══════════════╪════════════
    PROTOCOL BOUNDARY (everything below is infrastructure)
         │              │              │              │
    ┌────▼────┐   ┌─────▼─────┐  ┌────▼─────┐  ┌────▼──────────┐
    │JobScraper│  │Scorer     │  │FormFiller │  │Notifier       │
    │(browser) │  │DedupStore │  │DailyCap   │  │(Telegram)     │
    └──────────┘  │AppliedStor│  │RetryQueue │  └───────────────┘
                  └───────────┘  │AIClient   │
                                 └───────────┘
```

### Key Rules:
- Services ONLY depend on Protocols (never on infrastructure directly)
- Infrastructure implements Protocols
- Pipeline stages delegate to Services
- Container wires implementations to protocols
- No module imports another module's internal implementation

---

## 8. Data Flow (Single Job Lifecycle)

```
1. PipelineRunner fires CYCLE_STARTED event
   │
2. EventBus routes to LinkedInDiscoveryStage
   │  └─ calls DiscoveryService.discover(keywords, locations, max)
   │     └─ uses JobScraper protocol (PlaywrightSession + LinkedInScraper)
   │     └─ returns list[JobEvent] with type=JOB_DISCOVERED
   │
3. EventBus routes each JOB_DISCOVERED to LinkedInEvaluationStage
   │  └─ calls EvaluationService.evaluate(job_event)
   │     ├─ DedupStore.is_seen(job_id) → skip if true
   │     ├─ JobScraper.open_job(job_id)
   │     ├─ JobScraper.is_already_applied() → skip if true
   │     ├─ JobScraper.is_external_apply() → route to EXTERNAL
   │     ├─ Scorer.score(title, company, location, desc) → float
   │     ├─ self_learning_adjust(score, company) → adjusted_score
   │     └─ threshold check → JOB_QUALIFIED or JOB_DISQUALIFIED
   │
4. EventBus routes JOB_QUALIFIED to LinkedInApplicationStage
   │  └─ calls ApplicationService.apply(job_event)
   │     ├─ DailyCap.can_apply() → CAP_REACHED if false
   │     ├─ FormFiller.click_easy_apply()
   │     ├─ FormFiller.fill_form_fields(answers)
   │     │   └─ AIClient.generate_answer() for unknown fields
   │     │   └─ Notifier.request_human_input() for sensitive fields
   │     ├─ FormFiller.submit_application()
   │     ├─ DailyCap.record_application()
   │     ├─ DedupStore.mark_applied(job_id)
   │     └─ returns JOB_APPLIED or JOB_FAILED or JOB_PAUSED
   │
5. EventBus routes terminal events to TelegramNotificationStage
   └─ calls NotificationService.notify(event)
      ├─ JOB_APPLIED → rich notification + InMail draft
      ├─ JOB_EXTERNAL → link + score to user
      ├─ JOB_PAUSED → blocking fields info
      ├─ JOB_FAILED → error summary
      └─ CAP_REACHED → daily cap warning
```

---

## 9. Resilience Patterns

### 9.1 Circuit Breaker (`resilience/circuit_breaker.py`)

Applied to:
- **Browser operations** — If Playwright crashes 3 times in 5 minutes, open circuit → skip remaining jobs, report to Telegram, save progress
- **Telegram API** — If sends fail 5 times, open circuit → log locally, batch-send when recovered
- **Tracker API** — If pushes fail, open circuit → buffer events, flush on recovery
- **AI Client** — If model unavailable, open circuit → use fallback scorer only

States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (probing recovery)

```python
class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3,
                 recovery_timeout_sec: int = 300, half_open_max: int = 1): ...
    async def call(self, fn: Callable, *args, **kwargs) -> Any: ...
    @property
    def state(self) -> Literal["closed", "open", "half_open"]: ...
    def reset(self) -> None: ...
```

### 9.2 Health Checks (`resilience/health.py`)

Each infrastructure component registers a health check. The PipelineRunner
checks health before starting a cycle and degrades gracefully.

```python
@dataclass
class HealthStatus:
    name: str
    healthy: bool
    message: str = ""
    last_check: datetime

class HealthRegistry:
    def register(self, check: HealthCheck) -> None: ...
    async def check_all(self) -> list[HealthStatus]: ...
    async def check_critical(self) -> bool: ...  # All critical services healthy?
```

**Health checks registered:**
| Component | Critical? | Degraded Behavior |
|-----------|-----------|-------------------|
| Browser session | YES | Cannot proceed — retry launch |
| LinkedIn login | YES | Cannot proceed — alert user |
| Telegram API | NO | Buffer notifications, log locally |
| Tracker API | NO | Skip dashboard updates, log locally |
| Dedup DB (Turso) | NO | Use local dedup only |
| AI Client | NO | Use fallback scorer, skip cover letters |
| Daily Cap file | NO | Use in-memory counter |

### 9.3 Graceful Degradation (`resilience/graceful.py`)

```python
# Decorator that catches failures and falls back
@degrade_to(fallback_value=None, log_level="warning")
async def get_ai_answer(question: str) -> str | None: ...

# Context manager for optional features
async with optional_feature("inmail_drafting", notifier):
    await inmail_service.draft_and_send(job)
    # If this fails, logs warning + notifies user, doesn't crash cycle
```

### 9.4 Retry (`resilience/retry.py`)

Generic async retry with exponential backoff, distinct from the job-level RetryQueue:

```python
@async_retry(max_attempts=3, backoff_base=2.0, exceptions=(TimeoutError, NetworkError))
async def navigate_to_page(url: str) -> None: ...
```

---

## 10. Pipeline Runner as Primary Orchestrator

The refactored `PipelineRunner` becomes the ONLY execution path. The old
`orchestrator.py` is reduced to a CLI adapter that builds the container and
calls the runner.

### New PipelineRunner responsibilities:
1. Accept `Container` (all deps pre-wired)
2. Run pre-flight health checks
3. Fire `CYCLE_STARTED` → let event bus drive everything
4. Handle shutdown signals (complete in-progress job, then stop)
5. Report cycle metrics
6. Process retry queue after main cycle
7. Persist state for crash recovery

### Old orchestrator.py becomes:
```python
class JobAgent:
    """Backwards-compatible CLI adapter. Delegates to PipelineRunner."""

    def __init__(self, config=None, dry_run=False):
        self.config = config or get_config(validate=True)
        self.container = Container(self.config)
        self.runner = self.container.pipeline_runner(dry_run=dry_run)

    async def run_scan_cycle(self):
        await self.runner.setup()
        result = await self.runner.run_cycle()
        await self.runner.shutdown()
        return result

    async def run_once(self):
        await self.run_scan_cycle()

    async def run_daemon(self):
        scheduler = self.container.scheduler()
        await scheduler.run()

    def request_shutdown(self):
        self.runner.request_shutdown()
```

That's it. ~30 lines. The 50KB god-object is gone.

---

## 11. Browser.py Decomposition (63KB → 4 files)

The current `browser.py` does too much. Split by concern:

### `infrastructure/browser/session.py` (~10KB)
- `PlaywrightSession` class
- `launch()` — headless Chromium with stealth args
- `login(email, password)` — credential entry + challenge detection
- `close()` — graceful browser shutdown
- `is_healthy()` — page responsive check
- Session persistence (cookies, storage state)
- Implements: `BrowserSession` protocol

### `infrastructure/browser/navigation.py` (~8KB)
- `LinkedInNavigator` class
- `navigate_to_jobs(collection)` — job feed URLs
- `search_jobs(keyword, location, posted_within)` — search URL construction + navigation
- `navigate_to_url(url)` — custom URL navigation
- `open_job(job_id)` — job detail page
- Human-like delays between navigations
- Implements: navigation subset of `JobScraper` protocol

### `infrastructure/browser/scraper.py` (~15KB)
- `LinkedInScraper` class
- `get_job_listings(max_count)` — parse job cards from list view
- `is_already_applied()` — detect "Applied" badge
- `is_external_apply()` — detect external apply button
- `get_external_apply_url()` — extract external URL
- `get_match_score()` — read Premium match percentage
- `check_application_statuses(max_check)` — read response updates
- Selector constants (grouped by page type)
- Implements: `JobScraper` protocol (composed with Navigator)

### `infrastructure/browser/form_filler.py` (~20KB)
- `EasyApplyFormFiller` class
- `click_easy_apply()` — open the modal
- `fill_form_fields(answers)` — iterate form pages, fill known fields
- `submit_application()` — final submit + success detection
- `discard_application()` — close modal cleanly
- `upload_resume(path)` — file upload handling
- Field detection (radio, select, text, textarea)
- City autocomplete handling
- Implements: `FormFiller` protocol

### `infrastructure/browser/stealth.py` (MOVE, ~10KB unchanged)
- `STEALTH_ARGS`, `get_random_ua()`, `get_stealth_scripts()`
- Anti-detection measures

---

## 12. Service Layer Detail

### `services/discovery.py`
```
class DiscoveryService:
    def __init__(self, scraper: JobScraper, config: ConfigProvider): ...
    async def discover(self, keywords, locations, max_postings, posted_within) → list[JobEvent]:
        # Source 1: Recommended
        # Source 2: OR queries per location
        # Source 3: Individual keyword × location (if < 80% found)
        # Source 4: Custom URLs
        # Returns deduplicated list of JobEvent
```

### `services/evaluation.py`
```
class EvaluationService:
    def __init__(self, scraper: JobScraper, scorer: Scorer,
                 dedup: DedupStore, config: ConfigProvider): ...
    async def evaluate(self, event: JobEvent) → JobEvent:
        # Dedup check → open job → already applied → external → score → threshold
    def adjust_score(self, score: float, company: str) → float:
        # Self-learning target/blocklist adjustments
```

### `services/application.py`
```
class ApplicationService:
    def __init__(self, form_filler: FormFiller, daily_cap: DailyCap,
                 notifier: Notifier, ai_client: AIClient,
                 dedup: DedupStore, config: ConfigProvider): ...
    async def apply(self, event: JobEvent) → JobEvent:
        # Cap check → open modal → fill → submit → record
    async def _resolve_unknown_field(self, question: str) → str:
        # Try AI → fallback to human input via Telegram
```

### `services/notification.py`
```
class NotificationService:
    def __init__(self, notifier: Notifier, tracker: TrackerClient,
                 inmail_drafter: InMailDrafter | None = None): ...
    async def notify(self, event: JobEvent) → None:
        # Route by event type → format → send
    async def send_cycle_report(self, metrics: dict) → None:
        # Enhanced tally report
```

---

## 13. Testing Strategy

### Unit Tests (fast, no I/O)
- Test each Service with mocked Protocol implementations
- Example: `TestEvaluationService` with `FakeJobScraper`, `FakeScorer`, `FakeDedupStore`
- Container override makes this trivial:
  ```python
  container = Container(test_config)
  container.override(JobScraper, FakeJobScraper(jobs=[...]))
  container.override(Scorer, FakeScorer(always_returns=0.85))
  service = container.evaluation_service()
  result = await service.evaluate(job_event)
  assert result.event_type == EventType.JOB_QUALIFIED
  ```

### Integration Tests (test real wiring)
- Use container with real implementations but against test fixtures
- Browser tests: use Playwright's route mocking (intercept LinkedIn responses)
- Telegram tests: mock HTTP endpoint

### Pipeline Tests (end-to-end flow)
- Fire `CYCLE_STARTED` through the bus with all fake services
- Assert correct event sequence: DISCOVERED → QUALIFIED → APPLIED
- Assert dead-letter handling for failures
- Already exists in `tests/test_pipeline.py` — enhance with DI

---

## 14. Migration Strategy (Phased)

### Phase 1: Foundation (No behavior changes)
1. Create `protocols.py` with all Protocol definitions
2. Create `container.py` with the DI container
3. Create `core/models.py` and `core/events.py` (move existing dataclasses)
4. Create `core/exceptions.py`
5. Create `resilience/` package with circuit breaker, health, retry
6. **All existing code continues to work unchanged**

### Phase 2: Extract Infrastructure
1. Split `browser.py` → `infrastructure/browser/` (4 files)
2. Move `daily_cap.py`, `retry_queue.py`, `dedup_db.py` → `infrastructure/persistence/`
3. Move `telegram_bot.py` → `infrastructure/telegram/`
4. Move `tracker_client.py` → `infrastructure/tracker_client.py`
5. Create `infrastructure/ai_client.py` from `answer_generator.py`
6. Add Protocol implementations to each infrastructure class
7. **Old import paths still work via re-exports in original locations**

### Phase 3: Extract Services
1. Create `services/discovery.py` (extract from orchestrator + linkedin_stages)
2. Create `services/evaluation.py` (extract from orchestrator + matcher)
3. Create `services/application.py` (extract from applicant.py)
4. Create `services/notification.py` (extract from telegram_bot.py)
5. Create `services/scoring/` (split matcher.py)
6. **Pipeline stages delegate to services instead of doing work directly**

### Phase 4: Gut Orchestrator
1. Refactor `pipeline/runner.py` to accept Container
2. Refactor `pipeline/linkedin_stages.py` to use services via protocols
3. Reduce `orchestrator.py` to thin CLI adapter (~30 lines)
4. Delete duplicate logic that lived in orchestrator
5. Update `__main__.py` to use Container
6. **Remove all old re-export shims from Phase 2**

### Phase 5: Harden
1. Wire circuit breakers into infrastructure layer
2. Add health checks to all infrastructure components
3. Add graceful degradation to pipeline runner
4. Update all tests to use container overrides
5. Add pipeline integration tests with fault injection

---

## 15. Backwards Compatibility

During migration, maintain these guarantees:
- `python3 -m linkedin_agent run` continues to work at every phase
- `from linkedin_agent.orchestrator import JobAgent` still works
- `from linkedin_agent.config import get_config` still works
- Dashboard/tracker integration unchanged
- `.env` and `config.yaml` format unchanged
- No database migrations required

Re-export shims in old file locations:
```python
# linkedin_agent/daily_cap.py (after Phase 2)
from linkedin_agent.infrastructure.persistence.daily_cap import (
    DailyApplicationCap,
    get_daily_cap,
)
```

These shims are removed in Phase 4 after all internal imports are updated.

---

## 16. Size Budget

Target file sizes after refactoring:

| File | Current | Target | Reduction |
|------|---------|--------|-----------|
| `orchestrator.py` | 50KB | 3KB | 94% |
| `browser.py` | 63KB | DELETED (split) | 100% |
| `infrastructure/browser/session.py` | — | 10KB | — |
| `infrastructure/browser/navigation.py` | — | 8KB | — |
| `infrastructure/browser/scraper.py` | — | 15KB | — |
| `infrastructure/browser/form_filler.py` | — | 20KB | — |
| `applicant.py` | 47KB | DELETED (split) | 100% |
| `services/application.py` | — | 12KB | — |
| `matcher.py` | 13KB | DELETED (split) | 100% |
| `pipeline/linkedin_stages.py` | 18KB | 8KB | 56% |
| `pipeline/runner.py` | 9KB | 12KB | (grows slightly, takes on more responsibility) |

No file should exceed 20KB. If it does, it needs further decomposition.
