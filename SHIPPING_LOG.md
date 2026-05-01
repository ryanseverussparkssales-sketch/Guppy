# Guppy Shipping Log

**Purpose:** Detailed implementation notes for completed features and initiatives. Reference for understanding architectural decisions and implementation details.

**Last updated:** 2026-05-01

---

## Phase 6 Hardening — Shipped (2026-05-01)

### Security Hardening Round 1

**Stream timeout + client disconnect cleanup (`routes_realtime.py`)**
- `_generate_with_heartbeat()` now enforces a wall-clock cap via `GUPPY_STREAM_TIMEOUT_SECONDS` env var (default 300 s)
- `request.is_disconnected()` polled each iteration — async generator cleaned up immediately on client disconnect
- Prevents indefinitely hung HTTP connections when a model server stalls

**`shell_run` injection fix (`routes_realtime.py`)**
- Replaced `subprocess.run(command, shell=True)` with `shlex.split(command)` + `shell=False`
- The `_SHELL_SAFE_PREFIXES` allowlist only checked `startswith()`, meaning `git status; rm -rf /` would have passed. With `shell=False` the semicolon is treated as a literal character in the first argv element — no shell interpretation.

**`ensure_column` DDL allowlist (`memory_db.py`, `memory_store.py`)**
- Added `_ALLOWED_MEMORY_TABLES = frozenset({"facts", "conversations"})` to both files
- `ensure_column()` now raises `ValueError` for any table name not in the allowlist
- Prevents accidental DDL on arbitrary table names from a bad/patched caller

### Codebase Cleanup

**Archived deprecated modules**
- `src/guppy/merlin/` → `docs/archive/deprecated-modules/merlin/` (was emitting `DeprecationWarning`)
- `compat_shims/launcher_ui/` → `docs/archive/deprecated-modules/compat_launcher_ui/` (93 files, old Qt desktop UI)
- Removed `test_merlin_core_smoke_imports` from `tests/smoke/test_router_smoke.py`
- Removed `src/guppy/merlin/*` from `pytest.ini` coverage omit (module no longer exists)

---

## Usability Pass — Routing + Runtime (2026-05-01)

### Partner + On-Demand Backend Auto-Start
- Conversation partner selection now auto-starts the chosen backend (and fails fast if the launch target is missing).
- Tool-call routing attempts to auto-start xLAM when offline before falling back to Hermes 4.
- Local fallback routing attempts to auto-start the 70B CPU backend when selected.
- **Impact:** Fewer “offline model” surprises; partner/model switches are usable without manual boot steps.

### Phi Orchestrator Promotion
- Added a dedicated `llamacpp-phi4-mini` backend entry (port 8091) and made it the workspace controller role.
- Session summarization now targets phi-4-mini; dispatch remains a lightweight router fallback.
- Updated model routing docs + CLAUDE registry to match the new always-on orchestrator.
- **Impact:** Orchestrator role now matches the Phi-first architecture without breaking dispatch fallback.

### Semantic Memory Lexical Fallback
- SQLite semantic recall now falls back to lexical matching when embeddings are unavailable.
- Updated semantic memory docs header to reflect OpenAI-compat embedding servers instead of Hermes-only.
- **Impact:** Memory stays usable even when the embedding endpoint is offline or unsupported.

### Tool-Call Event Logging
- Added `tool_call_events` table with surface/session/task metadata.
- Logged tool calls from companion, workspace, conversations, and workspace-task executor flows.
- **Impact:** Tool usage is auditable and debuggable in `guppy_main.db`.

### Surface Defaults Alignment
- Companion surface default model now seeds as Hermes 3 (matching runtime routing).
- **Impact:** New surface configs align with the always-on stack without manual edits.

### Faster Status Probes
- Added TTL caches for backend probes and model listings in local runtime status.
- New env tuning: `GUPPY_BACKEND_PROBE_TTL_SECONDS`, `GUPPY_MODEL_LIST_TTL_SECONDS`.
- **Impact:** `/api/status` and related callers avoid repeated slow backend probes.

## P6 Platform Hardening — Shipped Features (2026-04-23 to 2026-04-28)

### Web UI Parity & Inference Controls (2026-04-26)
- Stop button (AbortController), Steer mode toggle (prepends steering directive), TTS toggle (voice.speak() after stream)
- AbortError propagated correctly through syncManager → streamChat so Stop never falls back to a blocking non-stream call
- **Impact:** Full inference control surface, production-ready streaming

### llamacpp Agentic Tool-Call Loop (2026-04-26)
- `_stream_llamacpp_tokens()` rewritten to accumulate OpenAI SSE tool_call deltas, execute tools via `owner.core.run_tool()`
- Loop up to `max_tool_rounds=6` with proper state management
- `_to_openai_tools()` converts Anthropic `input_schema` format to OpenAI `parameters`
- Steer mode normalised before routing checks in `stream_unified_inference`
- **Impact:** Local models can now execute tools autonomously

### MiniCPM-o 4.5 Omni Vision Model (2026-04-26)
- Port 8084, Mode A (can pair with Pepe)
- Routes: `minicpm-o-4.5`, `minicpm-o`, `minicpm`, `minicpm-omni`
- Launch script: `C:\llama-cpp\launch-minicpm.bat` (requires `--mmproj` flag)
- Files: Download from `openbmb/MiniCPM-o-4_5-gguf`
- **VRAM Reality:**
  - Pepe+MiniCPM: ~17 GB ✅
  - Pepe+Gemma+MiniCPM: ~26 GB (borderline 24 GB card)
  - Qwen3+anything: impossible (~36 GB)
- **Impact:** Vision capability on local GPU

### Dispatch Auto-Start, VRAM Bar, Cloud Routing (2026-04-27)
- `llamacpp-dispatch` auto-starts at Guppy boot (`_run_auto_starts()` daemon thread, 5 s delay)
- `VramBar` component in BackendsTab: stacked coloured segments per running backend, mode legend, free-GB readout
- Each backend carries `vram_gb` + `auto_start` in `_LLAMACPP_CONFIG`
- New endpoint: `GET /api/backends/llamacpp/vram`
- Env var: `GUPPY_GPU_VRAM_GB` (default 24)
- `query_instance` tool gains `mode` param (`"auto"`, `"local"`, `"claude"`, `"code"`) — dispatch agent can route subtasks to cloud/budgeting inference router
- Instance query timeout cap: 5 s → 120 s
- **Impact:** Intelligent local/cloud switching, GPU capacity awareness

### Web UI Nav + SPA Routing Fixes (2026-04-27)
- Web nav rebuilt: Chat / Launch Control / Personas / Instructions / Tools + Settings footer
- Old Dashboard/Library/Voices/Desktop routes redirect to new paths:
  - `/library→/personas`, `/voices→/tools`, `/desktop→/tools`, `/status→/settings`
- SPA catch-all changed from `@app.get("/{full_path:path}")` to `@app.exception_handler(404)` in `server_runtime.py`
- Fixes Starlette 1.0.0 routing conflict where wildcard route intercepted API routes added via `include_router()`
- llamacpp offline fallback: `realtime_inference_support.py` does port liveness check before forcing `local` mode
- If user's saved `active_local_model` points to offline llamacpp backend, falls back to Ollama instead of raising 500
- `llamacpp_failed` flag plumbed through streaming path so `can_stream_ollama` fires correctly
- **Impact:** Clean routing, graceful offline fallback

### Mistral + Cohere Free Tier Wiring (2026-04-27)
- Added streaming inference paths for Mistral and Cohere to `realtime_inference_support.py`
- Uses `_stream_openai_compat_tokens()` via `https://api.mistral.ai/v1` and `https://api.cohere.com/compatibility/v1`
- Free-tier auto-routing: Mistral (`ministral-8b-latest`) → Cohere (`command-r7b-12-2024`) → paid Claude
- Explicit model selection routes directly to chosen provider
- `routes_realtime.py` `_get_active_cloud_model()` reads active provider from settings DB
- **Model Catalogs Updated:**
  - Mistral: `ministral-8b-latest`, `ministral-3b-latest` (free), `mistral-medium-latest`, `pixtral-large-latest`
  - Cohere: `command-r7b-12-2024` (free)
  - Google: `gemini-2.0-flash-lite`, `gemini-1.5-flash`, `gemini-1.5-flash-8b` (all free)
- Free models carry `"free": True` badge in TopBar model picker
- **Impact:** Cost-optimized inference stack, free tier prioritized

### Hermes 4/3 + Rocinante Tool-Capable Backends (2026-04-28)
- Three new llama.cpp backends:
  - `llamacpp-hermes4` (port 8086, Hermes 4 14B Q5_K_M, ~11 GB)
  - `llamacpp-hermes3` (port 8087, Hermes 3 8B Lorablated Q8_0, ~9 GB)
  - `llamacpp-rocinante` (port 8088, Rocinante X 12B Q5_K_M, ~10 GB)
- Launch scripts: `C:\llama-cpp\launch-hermes-4-14b.bat`, `launch-hermes-3-8b.bat`, `launch-rocinante-12b.bat`
- Wired into `local_client.py`, `routes_backends.py`, `routes_providers.py`
- Hermes models include `--jinja` flag for structured tool calls
- Added as primary fallbacks in `_MODE_A_FALLBACK_ORDER`
- **Gemma 4 E4B PLE Warning:** llama.cpp #22243 — PLE architecture not fully implemented; output quality is silently degraded
  - Affects `gemma-4-heretic-ara` fine-tune
  - Use Hermes or Rocinante for tool-capable or quality-sensitive tasks
  - Gemma 4 26B-A4B or 31B work correctly
- **Impact:** Uncensored, tool-capable local models, superior to Gemma 4 E4B for production

### Additional Session Work (2026-04-28)
- Workspace context injection (`_inject_workspace_context_async`)
- API key Fernet encryption
- Model params persistence
- Auto-conversation titles
- Conversation search UI
- Image attachment support for MiniCPM-o

---

## Desktop Hardening (TR54-D) — Shipped (2026-04-24 to 2026-04-25)

### D1–D5 Complete
- **D1:** Startup orchestration
- **D2:** Process guard
- **D3:** Boot verification (`ui/launcher/diagnostics/startup_verification.py`) — wired into `compat_shims/launcher_ui/launcher_app.py` main()
- **D4:** Snapshot cache
- **D5:** Diagnostics (`ui/launcher/diagnostics/launcher_diagnostics.py` + `ui/launcher/views/diagnostics_panel.py`)

### Fixes
- `datetime.utcnow()` deprecation fixed across 4 API route files

---

## Move-to-Strong Roadmap (S1–S6) — Shipped (2026-04-23)

### S1: Continuity Spine
- Workspace cards + home entry hints surface continuity_summary

### S2: Library Metadata Hierarchy
- Timestamps, date labels, longer note previews

### S3: Tool Clarity
- `availability_status` on ToolActionEntry
- PLANNED badge on cards
- Planned tools excluded from bucket counts

### S4: Model/Voice/Local Runtime Confidence
- Planned adapters clearly labeled
- Voice engines probed at startup

### S5: Web API Parity
- `GET /api/tools` endpoint backed by TOOL_ACTION_REGISTRY
- ToolsView no longer falls back to mock data

### S6: Freeze Polish
- `verify_voice_runtime.py` validation tool
- CONNECTOR/PLANNED filter fix in tools_view
- CLAUDE.md updated

---

## Historical Notes

- **Phase 3 (TR54-C) Complete:** Connector extraction, remediation paths, settings flow wiring
- **P0 Implementation:** Model Management, Workspaces, Chat Persistence, Settings — all shipped
- **Production-Readiness Checkpoint (2026-04-22):** P0 ✅, tools ✅, desktop integration ✅
