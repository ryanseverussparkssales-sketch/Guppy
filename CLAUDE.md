# Guppy: Claude Code Reference

**Purpose:** Persistent notes on architecture, conventions, known issues, and integration points for Claude (and future agents).

**Last updated:** 2026-04-25 (session 2)

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
- **`src/guppy/cli/launch.py`** — Single entrypoint for all launch modes (launcher, guppyprime, hub, api, agent, **fishbowl**)
- **`src/guppy/config.py`** — Centralised pydantic-settings `GuppySettings`; import `settings` instead of `os.environ.get()`
- **`src/guppy/logging_setup.py`** — Loguru configuration + stdlib intercept; call `configure_logging()` at API startup
- **`src/guppy/launcher_application/`** — Shared workflow catalog, launcher services, state contracts
- **`src/guppy/api/`** — REST API with JWT auth, repair token, dev mode
- **`src/guppy/api/routes_tools.py`** — SQLite-backed tools registry (`GET /tools`, `POST /tools/:id/enable|disable`)
- **`src/guppy/api/routes_mcp.py`** — MCP server registry (`/api/mcp/servers`, test, tools listing)
- **`src/guppy/api/routes_providers.py`** — Provider/model management; checks env + settings DB; `POST /providers/{p}/active-model`. Supports 5 cloud providers: anthropic, openai, google, **cohere**, **mistral**
- **`src/guppy/mcp/manager.py`** — MCPPluginManager: SQLite registry, 11 preset servers, lazy client pool
- **`src/guppy/experience_config/`** — Runtime persona, provider selection, voice settings
- **`src/guppy/apps/`** — UI surfaces (launcher_app.py, hub_app.py, **fishbowl_app.py**)

### Web UI Key Files (`web/src/`)
- **`api/schemas.ts`** — Zod v4 schemas for all API responses; use `z.record(z.string(), ...)` (two-arg form required in v4)
- **`api/queries.ts`** — All TanStack Query hooks (`useQuery`/`useMutation`); query key registry `QK`
- **`api/client.ts`** — Axios client, baseURL `http://127.0.0.1:8081`
- **`themes/index.ts`** — Theme registry + `applyTheme(id)` / `initTheme()`; V0 adds `[data-theme="id"]` CSS block
- **`themes/dark.css`** — Dark theme override block (imported in index.css)
- **`components/CommandPalette.tsx`** — `Ctrl+K` / `Cmd+K` command palette (cmdk); navigate, switch provider, toggle tools
- **`views/MCPView.tsx`** — MCP server management UI

### Known Architecture Seams
1. **UI Launcher is a re-export shim** — `ui/launcher/__init__.py` delegates to `compat_shims/launcher_ui/ui/launcher/`. Real code lives in compat_shims. This is intentional (cleanup in progress).

2. **Legacy code quarantined** — `compat_shims/legacy_surfaces/` is empty (candidate for removal). `src/guppy/merlin/` holds old specialist material (not active launcher).

3. **Multiple /repair endpoints** — Consolidated. Only `routes_ops.py` / `ServerContext` path is active.

4. **os.environ.get() migration in progress** — `src/guppy/config.py` (GuppySettings) is the target; `server_runtime.py` and `auth.py` still use direct env reads for some values not yet in the schema.

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
- **`web/src/__tests__/`** — Vitest component tests (`npm test`); Playwright E2E (`npm run playwright`)
- Note: `asyncio_mode = auto` set in pytest.ini — async tests need no `@pytest.mark.asyncio` decorator

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
- [x] `compat_shims/legacy_surfaces/` — Intentionally empty quarantine marker (enforced by `tools/check_wrapper_integrity.py`); not a cleanup target
- [x] Multiple `/repair` implementations — Consolidated. Only `routes_ops.py` / `ServerContext` path is active.
- [x] `routes_settings.py:168` — Extra arg passed to `set_active_provider()` (only accepts 1). Fixed 2026-04-24.
- [x] `store/index.ts` — `Provider` type not re-exported, causing TS error in SettingsView. Fixed 2026-04-24.
- [x] `api/schemas.ts` — Zod v4 `z.record()` required two-arg form; all calls fixed 2026-04-25.
- [x] `web/src/types/api.ts` `SystemStatus` — interface used `health` field but API returns `status`; caused permanent "Offline" badge. Fixed 2026-04-25 (session 2). Also fixed `useApi.ts` hooks + `DashboardView.tsx`.
- [x] LM Studio `/api/status` returning MISSING/401 — fixed `local_client.py` (correct endpoint `/api/v1/models`, auth headers), `services_runtime_local.py` (lmstudio branch, model listing, warmup trigger). Fixed 2026-04-25.
- [ ] `os.environ.get()` migration — `server_runtime.py` and `auth.py` still use direct env reads; migrate to `settings` from `config.py`
- [ ] Migrate remaining views to TanStack Query hooks — `ModelsView`, `SettingsView`, `MCPView`, `ToolsView` still use manual `useState`/`useEffect` fetch patterns

### 🟡 Pending Features (installed, not yet wired)
- [ ] **Recharts** — installed; AdminPanel metrics dashboard charts not built yet (requests over time, latency sparklines)
- [ ] **react-resizable-panels** — installed; chat sidebar + desktop split not built yet
- [ ] **Theme customization packs** — system is ready (see 🎨 Theme System below); co-worker handover in progress (2026-04-25)

### 🟡 Documentation
- [x] Add one-line clarification to `instructions/OPERATIONS.md` §2 explaining that `ui/launcher/` is a re-export shim — done
- [ ] Document launcher shortcut management (`tools/ensure_desktop_launcher.ps1`)
- [ ] Add architecture diagram to README.md

### 🟢 Verified Working
- ✅ CLI launcher paths (launcher, guppyprime, hub, api, agent, fishbowl)
- ✅ JWT and repair token auth flows
- ✅ Database pragmas and hardening — also Alembic migrations at `migrations/` (head = 0001)
- ✅ All documented tool scripts and test files
- ✅ `GUPPY_DEV_MODE` env var and logging (loguru via `logging_setup.py`)
- ✅ Tools API (`GET /tools`, toggle enable/disable) — SQLite-backed, seeded with 8 tools
- ✅ MCP server registry — 11 presets, custom server CRUD, tool listing, test endpoint
- ✅ Fishbowl companion widget — always-on-top PySide6 app, Ctrl+Space hotkey, chat panel
- ✅ Web UI: markdown rendering (shiki + DOMPurify), Sonner toasts, framer-motion animations
- ✅ Web UI: TanStack Query wired — `QueryClientProvider` in main.tsx; AdminPanel fully migrated
- ✅ Web UI: Zod v4 schemas for all API responses (`web/src/api/schemas.ts`)
- ✅ Web UI: Theme system — `data-theme` attribute, `initTheme()` FOUC prevention, dark.css override
- ✅ Web UI: Command palette — `Ctrl+K` / `Cmd+K`, navigate + switch provider + toggle tools
- ✅ Web UI: Security hardening — CSP meta tag, Vite security headers, FastAPI security middleware
- ✅ Web UI: Provider model switching — `POST /providers/{p}/active-model`, active model persisted in settings DB
- ✅ Web UI: "Connected" badge — fixed `SystemStatus` type mismatch (`health` vs `status` field); badge now reflects real API state
- ✅ Vitest running — 5 MarkdownMessage tests pass; `npm test` works; TypeScript clean (`npx tsc --noEmit`)
- ✅ Cohere provider — 6 models (Command A, R+, R, Light, Aya 23 35B/8B); env `COHERE_API_KEY` / settings DB
- ✅ Mistral provider — 6 models (Large, Small, Codestral, Nemo, Pixtral 12B, Mixtral 8x22B); env `MISTRAL_API_KEY` / settings DB
- ✅ LM Studio local runtime — state READY with 7 models; auth via `GUPPY_LMSTUDIO_API_KEY`; `/api/v1/models` endpoint

### 🎨 Theme System for V0 — Handover Brief (2026-04-25)

**Status:** System fully wired and working. Ready for theme pack additions.

**How it works:**
- `web/src/themes/index.ts` — theme registry (`THEMES` array) + `applyTheme(id)` + `initTheme()` (FOUC prevention via `<script>` in `index.html`)
- `web/src/themes/dark.css` — example theme override block
- `web/src/index.css` — contains the `@theme` baseline block. **Never touch this.** Themes override via `[data-theme="id"]` attribute on `<html>`.
- `SettingsView.tsx` → Appearance card → `useTheme()` hook → `applyTheme()` → saves to localStorage + sets `document.documentElement.dataset.theme`

**To add a theme pack:**
1. Create `web/src/themes/my-theme.css` with a single `[data-theme="my-theme"] { --color-primary: ...; }` block
2. Add to `THEMES` array in `web/src/themes/index.ts`: `{ id: 'my-theme', label: 'My Theme', preview: ['#hex1', '#hex2'] }`
3. Import the CSS file in `web/src/themes/index.ts` or `web/src/index.css`
4. Run `npm run build` — theme appears in Settings → Appearance grid automatically

**CSS variables to override** (check `index.css` `@theme` block for full list):
- `--color-primary`, `--color-secondary`, `--color-background`, `--color-surface`
- `--color-on-surface`, `--color-on-surface-variant`
- `--font-headline`, `--font-body`

**Testing:** Open Settings → Appearance, click the new theme swatch. No restart needed.

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
2. Check `instructions/OPERATIONS.md` / `instructions/DEVELOPMENT.md` (stable reference)
3. Run `python tools/dev_workflow.py dev-check --guard-scope delta` (verify your changes don't break guardrails)

**When adding features:**
1. Update `CLAUDE.md` (this file) with new architecture, modules, or conventions
2. Add tests to `tests/` (unit or integration, depending on scope)
3. Document in `.builder/docs/` if it's a significant design decision

**When debugging:**
1. Check `GUPPY_DEV_MODE` is enabled
2. Verify Ollama is running (`verify_ollama_runtime.py`)
3. Review log output from `src/guppy/api/auth.py:464` (dev mode logging)
