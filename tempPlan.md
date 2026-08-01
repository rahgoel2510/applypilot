# ApplyPilot — Cleanup & Quality Roadmap

**Date:** 2026-08-02  
**Scope:** Security fixes, dead code removal, quality tooling, architecture refactoring.

---

## Current State Assessment

| Metric | Value | Enterprise Target |
|--------|-------|------------------|
| Test Coverage | 28% (146 tests) | 80%+ critical paths |
| Linter/Formatter | None | ruff + pre-commit |
| Type Checking | None | mypy strict |
| CI/CD | None | GitHub Actions |
| API Auth | None | Token/session auth |
| Secrets in Code | 1 hardcoded JWT | Zero (all in .env) |
| Dependency Pinning | Unpinned | Exact versions |
| CORS | allow_origins=[*] | Scoped to localhost |

---

## Phase 0: Security Fixes (URGENT)

**Risk:** CRITICAL — JWT token committed to git history  
**Effort:** 30 minutes  
**Status:** ✅ COMPLETE

### 0A. Move Turso Token to .env

- [x] Replace hardcoded `TURSO_URL` and `TURSO_TOKEN` in `dedup_db.py` with `os.environ.get()`
- [x] Add `TURSO_URL` and `TURSO_TOKEN` to `.env.example`
- [x] Add to `.env` locally
- [x] Validate dedup_db still connects
- [x] Run full test suite

### 0B. Future: Rotate Token

- [ ] After push, rotate the Turso token (old one is in git history)
- [ ] Consider git-filter-branch or BFG to scrub history (optional)

---

## Phase 1: Dead Code Removal (LOW RISK)

**Risk:** Minimal — pure deletion of confirmed dead code  
**Effort:** 1-2 hours  
**Validation:** `pytest tests/ -x` + `npm run build`

### 1A. Python Backend

**Delete entirely:**
- `linkedin_agent/scheduler.py` (~350 lines — never instantiated, orchestrator has its own daemon loop)

**In `browser.py` — DO NOT DELETE form methods.** Instead, add a comment block:
```python
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LEGACY REFERENCE: Easy Apply form-handling methods below.
# These are NOT called at runtime — applicant.py has its own
# implementations (_click_easy_apply, _click_next, submit, etc).
# Kept as reference for LinkedIn selector patterns.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
Methods preserved as reference: `click_easy_apply()`, `get_current_modal_fields()`, `fill_field()`, `_get_field_label()`, `_select_radio()`, `click_autocomplete_option()`, `click_next()`, `click_submit()`, `confirm_submission()`, `save_and_close()`, `dismiss_upsell()`

**In `logger.py`** — remove:
- `ApplicationLogger` class
- `ResultStatus` enum  
- `ApplicationResult` dataclass
- `timed()` decorator
- `get_logger()` function
- Keep ONLY `setup_logging()`

**In `matcher.py`** — remove:
- `classify_fields()`
- `_match_autofill_key()`
- `compute_match_score()`
- `load_feedback()`

**In `orchestrator.py`** — remove:
- `main()` function at bottom
- `process_job()` method (never called; run_scan_cycle processes inline)

**In `search_modes.py`** — remove:
- `apply_mode_to_config()`
- `get_all_modes()`

**In `inmail.py`** — remove:
- `draft_connection_note()`

**In `applicant.py`** — remove:
- Dead scoring code path (~line 166) calling non-existent `self.matcher.score_job()`

**In `bot.py`** — remove:
- `import time` (unused)

### 1B. Frontend Cleanup

**Delete 15 dead component files:**
- `components/Dashboard.jsx` (superseded by `pages/Dashboard.jsx`)
- `components/Board.jsx` (superseded by `pages/Board.jsx`)
- `components/AgentControlPanel.jsx` (superseded by `pages/AgentControl.jsx`)
- `components/Agents.jsx` (superseded by `pages/Agents.jsx`)
- `components/Scheduler.jsx` (superseded by `pages/Scheduler.jsx`)
- `components/ServiceManager.jsx` (superseded by `pages/ServiceManager.jsx`)
- `components/SettingsPanel.jsx` (superseded by `pages/Settings.jsx`)
- `components/TechLogs.jsx` (no replacement — fully dead)
- `components/SearchBar.jsx` (only used by dead Board)
- `components/KanbanColumn.jsx` (only used by dead Board)
- `components/JobCard.jsx` (only used by dead Board)
- `components/AddJobModal.jsx` (only used by dead Board)
- `components/RunHistory.jsx` (only used by dead AgentControlPanel)
- `components/MissingSettingsModal.jsx` (only used by dead AgentControlPanel)
- `components/ActivityFeed.jsx` (only used by dead Dashboard)

**Delete dead CSS & assets:**
- `src/App.css`
- `src/assets/react.svg`
- `src/assets/vite.svg`  
- `src/assets/hero.png`

**In `api.js`** — remove 8 dead functions:
- `getFeedbackSummary()`, `getConfigYaml()`, `updateConfigYaml()`
- `getAgentRunDetail()`, `diagnoseRun()`, `autoRepair()`
- `updateAgentConfig()`, `fetchFreeModels()`

**Remove unused npm packages:**
```bash
npm uninstall @xyflow/react @mui/x-data-grid @mui/x-date-pickers
```

**Clean unused imports in active files:**
- `layout/AppLayout.jsx`: remove `AccountTreeIcon`, `TimelineIcon`
- `pages/Dashboard.jsx`: remove `RadialGauge`, `Sparkline`
- `components/Animated.jsx`: remove unused exports `FadeInUp`, `StaggerContainer`, `StaggerItem`

### 1C. Project Root Cleanup

**Remove from git tracking:**
```bash
git rm --cached .DS_Store
git rm -r --cached '*/__pycache__' 2>/dev/null
git rm -r --cached .pytest_cache 2>/dev/null
git rm -r --cached linkedin_job_agent.egg-info 2>/dev/null
```

**Delete:**
- `tmp/` directory
- `tracker/Dockerfile.tracker` (duplicate — update docker-compose.yml to use `tracker/Dockerfile`)
- SQLite auxiliary files: `*.db-shm`, `*.db-wal`, `*.db-info`

**Update `.gitignore`** — add:
```gitignore
*.db-shm
*.db-wal
*.db-info
tmp/
```

**Update `docker-compose.yml`** — change `dockerfile: tracker/Dockerfile.tracker` → `dockerfile: tracker/Dockerfile`

### 1D. Validation
```bash
python3 -c "from linkedin_agent.orchestrator import JobAgent"
python3 -c "from linkedin_agent.browser import LinkedInBrowser"
python3 -c "from linkedin_agent.matcher import JobMatcher"
python3 -m pytest tests/ -x
cd tracker/frontend && npm run build
```

---

## Phase 1.5: Quality Foundation

**Risk:** Low — adds tooling, doesn't change behavior  
**Effort:** 1-2 hours

### 1.5A. Add Ruff (Linter + Formatter)

Add to `pyproject.toml`:
```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]
ignore = ["E501"]  # line length handled by formatter

[tool.ruff.lint.isort]
known-first-party = ["linkedin_agent"]
```

### 1.5B. Pin Dependencies

Replace `requirements.txt` with exact versions:
```
playwright==1.52.0
python-telegram-bot==22.1
pyyaml==6.0.2
python-dotenv==1.0.1
openai==1.86.0
apscheduler==3.10.4
platformdirs==4.3.6
rich==14.0.0
httpx==0.28.1
libsql-experimental==0.0.50
```

### 1.5C. Add Pre-commit Config

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.12
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

### 1.5D. Validation
```bash
ruff check linkedin_agent/ tests/
python3 -m pytest tests/ -x
```

---

## Phase 2: Decouple Orchestrator (MEDIUM RISK)

**Prerequisite:** Phase 1 complete + test coverage at 60%+ for orchestrator  
**Risk:** Medium — behavioral refactor  
**Effort:** 4-6 hours

### 2A. Extract `JobDiscoverer`
### 2B. Extract `JobEvaluator`  
### 2C. Slim `CycleCoordinator`
### 2D. Extract `DaemonRunner`
### 2E. Dependency Injection via Factory

(Details in git history — see previous version of this file)

---

## Phase 3: Wire Event-Driven Pipeline (OPTIONAL)

**Prerequisite:** Phase 2 complete  
**Risk:** Low-medium — pipeline code exists and is tested  
**Effort:** 6-8 hours

Replace procedural cycle loop with `pipeline/` event bus architecture.

---

## Enterprise Gaps (Future Backlog)

| Gap | Priority | Phase |
|-----|----------|-------|
| API authentication for tracker | High | After Phase 1.5 |
| Scope CORS to localhost only | High | After Phase 1.5 |
| Add GitHub Actions CI | High | Phase 1.5 |
| Frontend tests (Vitest) | Medium | Phase 2+ |
| Structured JSON logging | Medium | Phase 2 |
| TypeScript migration | Low | Phase 3+ |
| Monitoring/alerting | Low | Phase 3+ |
| Request tracing (correlation IDs) | Low | Phase 3+ |

---

## Reference: browser.py Method Verification

These methods in `LinkedInBrowser` are confirmed NOT called at runtime (verified 2026-08-02):

| Method | Why Dead | Reference Value |
|--------|----------|----------------|
| `click_easy_apply()` | `applicant.py` has `_click_easy_apply()` | LinkedIn Easy Apply button selectors |
| `get_current_modal_fields()` | Not called anywhere | Modal field parsing logic |
| `fill_field()` | Not called anywhere | Input/select/radio fill patterns |
| `_get_field_label()` | Only by dead `get_current_modal_fields()` | Label extraction from form elements |
| `_select_radio()` | Only by dead `fill_field()` | Radio button group handling |
| `click_autocomplete_option()` | Not called anywhere | Autocomplete dropdown interaction |
| `click_next()` | `applicant.py` has `_click_next()` | Next/Review button selectors |
| `click_submit()` | `applicant.py` has `submit()` | Submit button selector |
| `confirm_submission()` | Not called anywhere | Success detection patterns |
| `save_and_close()` | Not called anywhere | Draft save + modal close |
| `dismiss_upsell()` | Not called anywhere | Premium upsell dismissal |

**Decision:** Keep as-is with LEGACY REFERENCE comment block. These contain valuable LinkedIn selector patterns that took effort to develop and may be needed if applicant.py needs debugging or rewriting.
