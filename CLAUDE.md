# Guppy: Claude Code Reference

**Purpose:** Persistent notes on architecture, conventions, known issues, and integration points for Claude (and future agents).

**Last updated:** 2026-04-22

---

## Architecture Overview

### Core Topology
```
Desktop UI (Qt)              Web UI (FastAPI)           API (REST)
    ↓                              ↓                        ↓
launcher_app.py              hub_app.py              server.py
    ↓                              ↓                        ↓
    └─────── launcher_application/ ────────────────────────┘
                     ↓
    launcher_application/ (intents, state contracts, services)
                     ↓
    experience_config/ (settings, persona, voice)
```

### Key Modules
- **`src/guppy/cli/launch.py`** — Single entrypoint for all launch modes (launcher, guppyprime, hub, api, agent)
- **`src/guppy/launcher_application/`** — Shared workflow catalog, launcher services, state contracts
- **`src/guppy/api/`** — REST API with JWT auth, repair token, dev mode
- **`src/guppy/experience_config/`** — Runtime persona, provider selection, voice settings
- **`src/guppy/apps/`** — UI surfaces (launcher_app.py, hub_app.py)

### Known Architecture Seams
1. **UI Launcher is a re-export shim** — `ui/launcher/__init__.py` delegates to `compat_shims/launcher_ui/ui/launcher/`. Real code lives in compat_shims. This is intentional (cleanup in progress).

2. **Legacy code quarantined** — `compat_shims/legacy_surfaces/` is empty (candidate for removal). `src/guppy/merlin/` holds old specialist material (not active launcher).

3. **Multiple /repair endpoints** — `/repair` and `/repair-token/refresh` declared in three files (`routes_ops.py`, `snapshot_misc_routes.py`, `_server_fragment_routes_core.py`). Verify if these are alternative mount points or dead code.

---

## Build & Test

### Local Development
```powershell
# Activate venv (if not already active)
.venv\Scripts\activate

# Run canonical dev workflow
python tools/dev_workflow.py dev-check --guard-scope delta
python tools/dev_workflow.py test-fast         # Unit tests only
python tools/dev_workflow.py test-default      # Unit + integration
python tools/dev_workflow.py test-smoke        # Smoke coverage
python tools/dev_workflow.py release-check     # Full validation
```

### Bootstrap
If virtual env not detected, run:
```powershell
powershell -ExecutionPolicy Bypass -File tools/bootstrap_venv.ps1 -Dev
```

### Environment
- **Python:** ≥ 3.12 (see `pyproject.toml`)
- **Ollama:** Must be running on `http://127.0.0.1:11434`
- **Key env vars:**
  - `GUPPY_DEV_MODE` — Enables dev endpoints, logging (see `src/guppy/api/auth.py:36`)
  - `GUPPY_JWT_SECRET` — JWT signing key (fallback if keyring unavailable)

### Test Structure
- **`tests/smoke/`** — Runtime smoke tests (launcher, API, security)
- **`tests/unit/`** — Fast unit tests
- **`tests/integration/`** — Slower integration tests
- Note: Some tests resolve via `compat_shims/launcher_ui/tests/` (pytest compiles them correctly, but literal path `tests/unit/test_...` may be imprecise)

---

## Security & Repair Token

### Auth
- **Endpoint:** `POST /repair` and `GET /repair-token/refresh`
- **Guard:** `X-Repair-Token` header (checked at `src/guppy/api/_server_fragment_routes_core.py:270`)
- **JWT:** Secret resolved from keyring or `GUPPY_JWT_SECRET` env var (see `src/guppy/api/auth.py:36–41`)

### Database (SQLite)
- **Pragmas applied** (see `utils/db_utils.py:89–93`):
  - `journal_mode=WAL` (write-ahead logging)
  - `synchronous=...` (durability)
  - `busy_timeout=...` (concurrency)
  - `foreign_keys=ON` (referential integrity)
  - `temp_store=MEMORY` (temp table performance)

---

## Known Issues & TODOs

### 🔴 Code Cleanup
- [ ] Empty directory: `compat_shims/legacy_surfaces/` — Remove or restore content
- [ ] Abandoned surface: `api/` folder at root has `requirements.txt` but no Python sources. Verify if dead code.
- [ ] Multiple `/repair` implementations — Consolidate or document alternative mount points

### 🟡 Documentation
- [ ] Add one-line clarification to `OPERATIONS.md` §2 explaining that `ui/launcher/` is a re-export shim
- [ ] Document launcher shortcut management (`tools/ensure_desktop_launcher.ps1`)
- [ ] Add architecture diagram to README.md

### 🟢 Verified Working
- ✅ CLI launcher paths (launcher, guppyprime, hub, api, agent)
- ✅ JWT and repair token auth flows
- ✅ Database pragmas and hardening
- ✅ All documented tool scripts and test files
- ✅ `GUPPY_DEV_MODE` env var and logging

---

## Tools & Utilities

### Build & Dev Workflow
- **`tools/dev_workflow.py`** — Canonical build system. Use this for all CI/local validation.
- **`tools/check_architecture_boundaries.py`** — Verify module import rules
- **`tools/check_wrapper_integrity.py`** — Validate wrapper shims
- **`tools/check_doc_ownership.py`** — Audit doc source of truth
- **`tools/check_new_module_line_cap.py`** — Enforce module size limits
- **`tools/pilot_exit_check.py`** — Graceful shutdown verification
- **`tools/verify_logging_health.py`** — Log system audit
- **`tools/verify_ollama_runtime.py`** — Ollama availability check
- **`tools/run_overnight_low_compute.py`** — Off-hours testing

### Desktop Launcher
- **`tools/ensure_desktop_launcher.ps1`** — Updates `Desktop\Guppy Launcher.lnk` to point to dist exe (if built) or repo launcher

---

## Launcher Patterns

### One-Click Launchers
- `Guppy_WebUI_Launcher.bat` → `bin/launch_web_ui.bat` (local Web UI)
- `OpenAI_WebUI_Launcher.bat` → `launch_openai_webui.ps1` (Docker OpenAI surface)

### Supervisor-Friendly
- `bin/launch_api_supervised.bat` — For external monitoring/restart on crash
- `bin/launch_automation_test.bat` — Guided automation test entrypoint

### Model Roster (Ollama)
| Model | Base | VRAM | Role |
|-------|------|------|------|
| `guppy-fast` | qwen2.5:7b | ~5 GB | Fast butler, simple queries |
| `vault-scraper` | qwen2.5:7b | shared | Digital Seed Vault extraction |
| `guppy-code` | qwen2.5-coder:14b | ~9 GB | Code review, debug |
| `guppy` | qwen2.5:32b | ~20 GB | Complex butler tasks |
| `guppy-teach` | qwen2.5:32b | shared | Socratic teaching |

---

## Config

### instances.json
Located at `config/instances.json`. Defines available runtime instances:
- `guppy-primary` (enabled) — Default instance
- `builder-collab` (enabled: false) — Optional builder collaboration instance

---

## When to File Issues

- Architecture questions → Check `.builder/docs/`
- Build/test failures → Run `python tools/dev_workflow.py dev-check`
- Missing paths → Verify against canonical brief in `docs/PROJECT_BRIEF.md`
- Security concerns → Review `src/guppy/api/auth.py` and repair token flow
- Performance → Profile with `tools/verify_ollama_runtime.py`

---

## For Claude Agents

**Before making changes:**
1. Read `docs/PROJECT_BRIEF.md` (active status & roadmap)
2. Check `OPERATIONS.md` / `DEVELOPMENT.md` (stable reference)
3. Run `python tools/dev_workflow.py dev-check --guard-scope delta` (verify your changes don't break guardrails)

**When adding features:**
1. Update `CLAUDE.md` (this file) with new architecture, modules, or conventions
2. Add tests to `tests/` (unit or integration, depending on scope)
3. Document in `.builder/docs/` if it's a significant design decision

**When debugging:**
1. Check `GUPPY_DEV_MODE` is enabled
2. Verify Ollama is running (`verify_ollama_runtime.py`)
3. Review log output from `src/guppy/api/auth.py:464` (dev mode logging)
