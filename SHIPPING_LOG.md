# Guppy Shipping Log

**Purpose:** Detailed implementation notes for completed features and initiatives. Reference for understanding architectural decisions and implementation details.

**Last updated:** 2026-05-03

---

## Two-Model Core Stability Checkpoint — Shipped (2026-05-03, commit 8315900)

### Critical Fix: Tool Primer Always Injected

**Root cause:** `skip_tools=True` was passed to `stream_unified_inference` for pass-1 companion and workspace calls to suppress OpenAI-format tool schemas. `router_surface.py` line 54 gated `_inject_tool_primer()` on `not skip_tools` — so on every pass-1 call, the tool primer was silently stripped from the system prompt. Rocinante and Hermes4 generated pass-1 responses with no knowledge of available tools or their XML format.

**Fix:** `_inject_tool_primer(augmented_system, surface)` call moved to the `realtime_inference_support.py` injection chain, after all other injections, unconditional on `skip_tools`. The `skip_tools` flag now controls only the OpenAI API schema objects passed in the `tools=` parameter — not the system-prompt tool description block. `router_surface.py` still has the `if not skip_tools:` guard as an intentional no-op remnant (safe to leave; the real injection already happened upstream).

### Pass-2 Tool-Loop Guard

**Root cause:** Companion and workspace pass-2 synthesis calls did not pass `skip_tools=True`, so the tool primer was injected again on the synthesis turn. Models occasionally emitted another `<tool_call>` block during synthesis (loop condition).

**Fix:** Both companion pass-2 and workspace pass-2 in `routes_realtime.py` now call `stream_unified_inference(..., skip_tools=True)` and use a dedicated synthesis system prompt that ends with "Do NOT emit any `<tool_call>` blocks."

### Companion History Limit 15→20

`_SURFACE_HISTORY_LIMITS["companion"]` was set to 15 with a comment referencing "Hermes3 8K context". Rocinante has 16K context (`_BACKEND_CONTEXT_TOKENS["llamacpp-rocinante"] = 16384`). Raised to 20 to use Rocinante's available context budget.

### Windows File Lock Fix

`_inject_user_preferences()` used `with sqlite3.connect(str(DB_PATH)) as conn:`. Python's sqlite3 context manager handles transaction commit/rollback but does NOT close the connection on `__exit__`. On Windows, this held the file lock for the lifetime of the Python object. Replaced with explicit `conn.close()` in a `finally` block.

### New: 22-Test Integration Suite (`tests/integration/test_two_model_core.py`)

Tests the Rocinante+Hermes4 core without a live model server — validates prompt assembly and routing logic only:

| Class | Tests | What it covers |
| --- | --- | --- |
| `TestToolPrimerInjection` | 5 | Companion/workspace/codespace primers present; CONVERSATION HISTORY instruction; TOOL CALL FORMAT reminder |
| `TestToolCallNormalization` | 5 | JSON passthrough; XML→JSON conversion; bad args graceful degradation; multiple calls; no calls |
| `TestContextBudgetGuard` | 4 | Normal conversation under budget; pathological session triggers guard; Rocinante > Hermes3 context; companion limit ≥ 20 |
| `TestMultiTurnHistoryInjection` | 3 | `augment_system_with_history` is a no-op (by design — history goes via messages array); `sanitize_chat_history` preserves content; trimming to surface limit |
| `TestSemanticMemoryPipeline` | 5 | Empty/garbage/good recall results; exact-key SQL bypass skips `_embed_text`; user preferences SQL scan |

All 22 pass. Guards: `dev-check --guard-scope delta` all green.

---

## Routing Stability + Memory Quality — Shipped (2026-05-03)

### Stream Stability: asyncio Heartbeat Queue (commit 911c40f)

**Root cause:** `_generate_with_heartbeat()` used `asyncio.wait_for(asyncio.shield(gen.__anext__()), timeout=30)`. On timeout, it called `__anext__()` again while the shielded call was still running → `ValueError: async generator already running` → stream died after exactly one heartbeat with no error visible to the client.

**Fix:** Queue-drain pattern. Producer task drains the async generator into an `asyncio.Queue`; consumer pulls with `asyncio.wait_for(queue.get(), timeout=30)` and emits `": heartbeat\n\n"` SSE comments when empty. Producer and consumer never share the generator reference concurrently.

### Rocinante as Companion Default (commit 911c40f)

- `_SURFACE_LOCAL_DEFAULTS["companion"]` changed from `llamacpp-hermes3` to `llamacpp-rocinante`
- Cascade: Rocinante (8088) → Hermes3 (8087) → Haiku cloud
- Hermes3 remains watchdog-maintained always-on fallback; Rocinante is on-demand
- Model identity updated in `context_injection.py`: `_MODEL_IDENTITY["companion"]` now reflects Rocinante X 12B

### XML Tool Call Normalization (commit 911c40f)

Some models emit `<tool_call><name>foo</name><arguments>{...}</arguments></tool_call>` instead of `<tool_call>{"name": "foo", "arguments": {...}}</tool_call>`. The existing `_TOOL_CALL_RE` only matched JSON-in-tags. Added `_normalize_tool_calls()` pre-parser that converts XML format to JSON format before regex extraction.

### Pass-2 Context Overflow Fix (commit 911c40f)

Workspace tool synthesis (pass-2) reused the full system prompt including `_WORKSPACE_TOOL_SCHEMA` (~3K tokens). Combined with tool results and history this exceeded the 32K context window on all cascade models, returning 0 tokens → "No backend available". Fix: strip `_WORKSPACE_TOOL_SCHEMA` from pass-2 prompt and append a short synthesis instruction.

### Companion `/action` Catch-All (commit 911c40f)

The companion `/action` endpoint had explicit `if name == "..."` handlers for only 5 of 9 allowed tools. Tools like `get_time`, `list_workspace_tasks`, `cancel_workspace_task` fell through to `raise HTTPException(400, "Unhandled action")`. Fixed with `_execute_companion_tool()` fallback covering all tools.

---

### Memory Noise Reduction (commit d1fb886)

**Exact-key recall short-circuit:** `_recall_sqlite` now checks `LOWER(memory_key) = LOWER(query)` and `LOWER(memory_key) LIKE LOWER(query%)` before any embedding I/O. When the user or a tool queries a key by exact name, results come back immediately without vector search noise.

**Recall depth n=8 → n=4:** Halves the number of recalled memories injected per prompt. Reduces token spend and cross-topic contamination.

**User preferences direct scan:** `_inject_user_preferences()` was calling `recall_semantic("", n=10, category="user_preference")` — the embedding of an empty string is undefined, producing random/near-random similarity results. Replaced with `SELECT memory_key, value FROM semantic_memory WHERE category='user_preference' ORDER BY created DESC LIMIT 10`.

**Garbage filter:** `build_semantic_prompt_context()` drops result blocks where all content lines (`-` prefixed) are shorter than 10 characters — this pattern indicates spurious lexical-fallback matches.

**Structured session summarizer:** Replaced the vague "3-4 sentence" prompt with a bullet-list fact-extraction prompt targeting: explicit preferences/decisions, completed tasks/outcomes, topics worth remembering, named entities (people, projects, tools).

### Surface-Aware Injection (commit d1fb886)

**File tree opt-in:** `_inject_workspace_context_async` skipped for companion surface entirely. For workspace/codespace, only injected when the query contains file-related keywords (`file`, `folder`, `code`, `script`, `path`, etc.).

**Surface state gate:** `_inject_surface_state_async` (cross-surface status block) skipped for companion unless query references `task`, `workspace`, `agent`, `status`, `running`, `progress`, or `complete`.

**Context budget guard:** After all injections, if `len(system_prompt) + sum(len(turn) for turn in history) > 85% of model context window` (from `_BACKEND_CONTEXT_TOKENS`), trims history to most-recent half and rebuilds without expensive workspace/surface injections.

---

## Phase 6 Hardening Round 2 — Shipped (2026-05-02)

### Security: `/repair-token/refresh` JWT Auth Gap Fixed
- The `/repair-token/refresh` endpoint previously only checked `client_ip not in ("127.0.0.1", ...)` — unauthenticated localhost requests were allowed through
- Fix: `routes_ops.py` now `Depends(verify_token)` on the endpoint — requires JWT Bearer in non-dev mode
- `GUPPY_DEV_MODE=True` keeps the dev bypass; production requires a valid JWT

### New: Semantic Memory Offline Unit Tests (`tests/unit/test_semantic_fallback.py`)
- 4 unit tests verifying `_recall_sqlite()` gracefully falls back to lexical matching when `_embed_text` returns `[]`
- Tests: lexical content returned, no exception raised, empty DB handled, `_lexical_recall` scores by word overlap
- Patching target: `_sem.DB_PATH` (the public module-level var bound from `src.guppy.paths.MEMORY_DB_PATH`)

### New: Docker App Container (`Dockerfile` + `docker-compose.yml`)
- `Dockerfile`: Python 3.12-slim, non-root `guppy` user, health check via `/health`, volumes for `runtime/` and `data/`
- `docker-compose.yml`: App stack; `GUPPY_JWT_SECRET` required (compose fails if unset); all provider keys optional; logging limits + restart policy
- Separate from `docker/docker-compose.vllm.yml` (inference-only stack)

### Test Suite State After Round 2
- `tests/test_security_hardening.py` — 29 pass, 10 skip (archived Qt launcher classes) ✅
- `tests/unit/test_semantic_fallback.py` — 4/4 pass ✅
- `tests/unit/test_tool_call_log.py` — 5/5 pass ✅
- `tests/unit/test_merlin_core.py` — 1/1 pass ✅

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
