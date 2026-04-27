# Guppy: Claude Code Reference

**Purpose:** Persistent notes on architecture, conventions, known issues, and integration points for Claude (and future agents).

**Last updated:** 2026-04-27

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

2. **Legacy code quarantined** — `compat_shims/legacy_surfaces/` is empty (candidate for removal). `src/guppy/merlin/` is deprecated: `__init__.py` emits a `DeprecationWarning` and `check_architecture_boundaries.py` blocks all external imports. No active code references it. `.quarantine/` contains a README only — confirmed intentional archival, not dead code.

3. **Catalog routes are all production** — `launcher_application/` catalogs (connector, workflow, instance, voice) are active production code. No experimental catalog routes exist.

4. **Single /repair endpoint** — `/repair` and `/repair-token/refresh` live only in `routes_ops.py`, mounted via `build_ops_router()` in `server_runtime.py`. The previously referenced `snapshot_misc_routes.py` and `_server_fragment_routes_core.py` no longer exist.

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
*(none open — all resolved below)*

### 🟡 Documentation
- [ ] Add architecture diagram to README.md

### 🟢 Verified / Resolved
- ✅ **`compat_shims/legacy_surfaces/`** — Not empty; contains an intentional `__init__.py` quarantine marker (`__all__ = ()`). Guardrail in `tools/check_architecture_boundaries.py` blocks imports. Protocol documented in `docs/LEGACY_QUARANTINE_PROTOCOL.md` and `docs/LEGACY_SURFACES.md`. No action needed.
- ✅ **`api/` root folder** — Active Vercel cloud backend (`app.py`, `auth.py`, `index.py`, `routes/`). Completely separate from the local runtime. See `docs/LIVE_ARCHITECTURE.md`. Not dead code.
- ✅ **`/repair` endpoints** — Single live implementation in `routes_ops.py` (mounted via `build_ops_router()`). `snapshot_misc_routes.py` and `_server_fragment_routes_core.py` no longer exist; stale references removed from CLAUDE.md and a clarifying comment added to `routes_ops.py`.
- ✅ **`ui/launcher/` shim clarification** — Documented in "Known Architecture Seams" §1 above and in `docs/LIVE_ARCHITECTURE.md`. OPERATIONS.md does not exist (reference was stale); `docs/LIVE_ARCHITECTURE.md` is the canonical architecture doc.
- ✅ **Launcher shortcut management** — `tools/ensure_desktop_launcher.ps1` updates `Desktop\Guppy Launcher.lnk` to point to dist exe or repo launcher. Documented in Tools & Utilities below.

### 🟢 Verified Working
- ✅ CLI launcher paths (launcher, guppyprime, hub, api, agent)
- ✅ JWT and repair token auth flows
- ✅ Database pragmas and hardening
- ✅ All documented tool scripts and test files
- ✅ `GUPPY_DEV_MODE` env var and logging
- ✅ **Web UI parity (P6)** — Web UI fetches model inventory and workspace state entirely from the same API endpoints as the desktop. No duplicate inventories. Parity validated 2026-04-23. One known gap: `models_view.py` has a local `CLOUD_MODELS` list for the desktop library panel — must stay in sync with `src/guppy/api/routes_providers.py`. (Fixed `claude-opus-4` → `claude-opus-4-7` 2026-04-23.)
- ✅ **Phase 3 complete (TR54-C)** — `ui/launcher/accounts/connector_remediation_paths.py`, `ui/launcher/views/settings_connector_flow.py`, `ui/launcher/config/runtime_settings_schema.py`, `ui/launcher/config/settings_io.py`, `ui/launcher/tools/tool_evidence_builder.py`, `ui/launcher/tools/tool_status_copy.py`
- ✅ **TR54-D (Desktop Hardening) D1–D5 complete** — D1 startup orchestration, D2 process guard, D3 boot verification (`ui/launcher/diagnostics/startup_verification.py`), D4 snapshot cache, D5 diagnostics (`ui/launcher/diagnostics/launcher_diagnostics.py` + `ui/launcher/views/diagnostics_panel.py`). D3 wired into `compat_shims/launcher_ui/launcher_app.py` main(). `datetime.utcnow()` deprecation fixed across 4 API route files.
- ✅ **Move-to-Strong roadmap S1–S6 complete (2026-04-23)** — S1: continuity spine (workspace cards + home entry hints surface continuity_summary); S2: library metadata hierarchy (timestamps, date labels, longer note previews); S3: tool clarity (availability_status on ToolActionEntry, PLANNED badge on cards, planned tools excluded from bucket counts); S4: model/voice/local runtime confidence (planned adapters clearly labeled, voice engines probed at startup); S5: web API parity (GET /api/tools endpoint backed by TOOL_ACTION_REGISTRY, ToolsView no longer falls back to mock data); S6: freeze polish (verify_voice_runtime.py validation tool, CONNECTOR/PLANNED filter fix in tools_view, CLAUDE.md updated).
- ✅ **Web UI inference controls (2026-04-26)** — Stop button (AbortController), Steer mode toggle (prepends steering directive, normalised before routing so streaming fires), TTS toggle (voice.speak() after stream). AbortError propagated correctly through syncManager → streamChat so Stop never falls back to a blocking non-stream call.
- ✅ **llamacpp agentic tool-call loop (2026-04-26)** — `_stream_llamacpp_tokens()` rewritten to accumulate OpenAI SSE tool_call deltas, execute tools via `owner.core.run_tool()`, and loop up to `max_tool_rounds=6`. `_to_openai_tools()` converts Anthropic `input_schema` format to OpenAI `parameters`. Steer mode normalised before routing checks in `stream_unified_inference`.
- ✅ **MiniCPM-o 4.5 Omni wired in (2026-04-26)** — Port 8084, Mode A (can pair with Pepe). Routes: `minicpm-o-4.5`, `minicpm-o`, `minicpm`, `minicpm-omni`. Launch script at `C:\llama-cpp\launch-minicpm.bat` — requires `--mmproj` flag. Files must be downloaded from `openbmb/MiniCPM-o-4_5-gguf`. **VRAM reality:** Pepe+MiniCPM ~17 GB ✅; Pepe+Gemma+MiniCPM ~26 GB (borderline 24 GB card); Qwen3+anything impossible (~36 GB).
- ✅ **Dispatch auto-start + VRAM bar + cloud routing (2026-04-27)** — Three features: (1) `llamacpp-dispatch` auto-starts at Guppy boot (`_run_auto_starts()` daemon thread, 5 s delay); (2) `VramBar` component in BackendsTab — stacked coloured segments per running backend, mode legend, free-GB readout; each backend now carries `vram_gb` + `auto_start` in `_LLAMACPP_CONFIG`; new `GET /api/backends/llamacpp/vram` endpoint; `GUPPY_GPU_VRAM_GB` env var (default 24); (3) `query_instance` tool gains `mode` param (`"auto"`, `"local"`, `"claude"`, `"code"`) propagated through `tool_runner.py` → `InstanceQueryRequest.mode` → `routes_instances.py` mode override — dispatch agent can now route subtasks to cloud/budgeting inference router. Instance query timeout cap raised 5 s → 120 s.
- ✅ **Web UI nav + SPA routing fixes (2026-04-27)** — (1) Web nav rebuilt: Chat / Launch Control / Personas / Instructions / Tools + Settings footer; old Dashboard/Library/Voices/Desktop routes redirect to new paths; `/library→/personas`, `/voices→/tools`, `/desktop→/tools`, `/status→/settings`. (2) SPA catch-all changed from `@app.get("/{full_path:path}")` to `@app.exception_handler(404)` in `server_runtime.py` — fixes Starlette 1.0.0 routing conflict where the wildcard route intercepted API routes added via `include_router()`. (3) llamacpp offline fallback: `realtime_inference_support.py` now does port liveness check before forcing `local` mode — if the user's saved `active_local_model` points to an offline llamacpp backend, inference falls back to Ollama instead of raising 500. `llamacpp_failed` flag plumbed through streaming path so `can_stream_ollama` fires correctly.
- ✅ **Mistral + Cohere inference wiring (2026-04-27)** — Added streaming inference paths for Mistral and Cohere to `realtime_inference_support.py`. Uses `_stream_openai_compat_tokens()` via `https://api.mistral.ai/v1` and `https://api.cohere.com/compatibility/v1`. Free-tier auto-routing: in auto mode, Mistral (`ministral-8b-latest`) is tried before Cohere (`command-r7b-12-2024`) before escalating to paid Anthropic Claude. Explicit model selection (user picks a Mistral/Cohere model from the picker) routes directly to that provider. `routes_realtime.py` `_get_active_cloud_model()` now reads the active provider from settings DB so non-Anthropic selections propagate correctly. Model catalogs updated: Mistral adds `ministral-8b-latest`/`ministral-3b-latest` (free), `mistral-medium-latest`, `pixtral-large-latest`; Cohere adds `command-r7b-12-2024` (free); Google adds `gemini-2.0-flash-lite`, `gemini-1.5-flash`, `gemini-1.5-flash-8b` (all free). Free models carry `"free": True` badge shown in TopBar model picker. TopBar now shows Cohere + Mistral provider sections alongside Anthropic/OpenAI/Google.

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
- **`tools/verify_voice_runtime.py`** — Voice engine availability check (edge_tts, kokoro, pyttsx3, ElevenLabs)
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
2. Check `docs/LIVE_ARCHITECTURE.md` (canonical architecture reference)
3. Run `python tools/dev_workflow.py dev-check --guard-scope delta` (verify your changes don't break guardrails)

**When adding features:**
1. Update `CLAUDE.md` (this file) with new architecture, modules, or conventions
2. Add tests to `tests/` (unit or integration, depending on scope)
3. Document in `.builder/docs/` if it's a significant design decision

**When debugging:**
1. Check `GUPPY_DEV_MODE` is enabled
2. Verify Ollama is running (`verify_ollama_runtime.py`)
3. Review log output from `src/guppy/api/auth.py:464` (dev mode logging)
