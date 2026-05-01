# Guppy — Master Tranche Codex
**Authored:** 2026-04-29  
**Authority:** This document is the single source of truth for the Guppy recovery and build-out plan. It supersedes any conflicting tranche lists in chat history.  
**Status:** Target contract, not a completion receipt. Tranches are ordered and have acceptance criteria, but current implementation state varies by item.

**Implementation status note (2026-04-30):**
- **Skeleton** means module/table/route shape exists, but the behavior may be stubbed or not end-to-end verified.
- **Wired** means the route is mounted or the schema is inventoried and guarded by import/path tests.
- **Working** means focused behavior tests or smoke evidence exercise the user-facing path.

Current sweep status: Tranches A-H are partially skeleton/wired, not uniformly working. Known gaps include conversation partner role/backend resolution in the dedicated conversations route, stubbed workspace task execution, Library API item persistence still using JSON while DB tables are now inventoried by migration, and Screenpipe/AI summary behavior remaining best-effort when local llama.cpp services are offline.

---

## Hardware Reality (locked)

| Resource | Value |
|---|---|
| GPU VRAM | 24 GB (AMD ROCm/HIP) |
| RAM | 98 GB |
| Local runtime | llama.cpp **only** — Ollama and LM Studio are eliminated |

**Hot VRAM budget (always-on core):**

| Model | Role | VRAM |
|---|---|---|
| Phi-4-mini (`llamacpp-dispatch`, port 8085) | Workspace controller | ~2.5 GB |
| Hermes 4 14B (`llamacpp-hermes4`, port 8086) | Workspace worker | ~11 GB |
| Hermes 3 8B (`llamacpp-hermes3`, port 8087) | Conversation default | ~9 GB |
| **Total always-on** | | ~22.5 GB |

**Conversation partner hot-swap (one at a time, shares remaining ~1.5 GB headroom):**  
- Rocinante 12B (port 8088, ~10 GB) — writing/roleplay — swap out Hermes3 when active  
- Pepe 8B (port 8082, ~8.5 GB) — study/funny chat — swap out Hermes3 when active  
- MiniCPM 4.5 (port 8084, ~9 GB) — private vision — swap out Hermes3 when active  

**On-demand / escalation:**  
- xLAM 8B (port 8089, ~5 GB) — tool-call specialist, only if Phi/Hermes4 fail tool JSON  
- Llama 3.3 70B (port 8090, CPU/RAM, ~42 GB RAM, 0 VRAM) — deep escalation, queued only  

---

## Model Role Registry (locked target)

This is the authoritative role map. Nothing in code should use raw model keys as UI-visible routing modes.

```
conversation.default              → llamacpp-hermes3   (port 8087)
conversation.partner.writing      → llamacpp-rocinante  (port 8088)
conversation.partner.study        → llamacpp-pepe        (port 8082)
conversation.partner.vision       → llamacpp-minicpm     (port 8084)
workspace.controller              → llamacpp-dispatch    (port 8085)  [Phi-4-mini]
workspace.worker.primary          → llamacpp-hermes4     (port 8086)  [Hermes 4 14B]
workspace.worker.escalation       → llamacpp-chat        (port 8090)  [Llama 3.3 70B — CPU]
workspace.tool_specialist         → llamacpp-xlam        (port 8089)  [on-demand only]
cloud.paid                        → anthropic/claude, openai (gate: cloud_paid_enabled)
cloud.free                        → mistral/cohere free tier (gate: cloud_free_enabled)
```

**Operator-visible controls (the only knobs users ever touch):**
1. Cloud paid on/off  
2. Cloud free on/off  
3. Conversation partner: Hermes 3 | Rocinante | Pepe | MiniCPM Vision  

Everything else is system policy, not user burden.

---

## Surfaces (locked target)

| Surface | Route | Primary job |
|---|---|---|
| **Conversations** | `/conversations` (was Companion) | Daily chat, voice, vision, personality |
| **Workspace** | `/workspace` | PC control, tasks, automation, CRM, screen, files |
| **Codespace** | `/codespace` | Code sandbox, self-triage, Docker |
| **Control** | `/control` | Admin, backends, cloud toggles, partner select |

`CompanionView.tsx` → rename/refactor to `ConversationsView.tsx`.  
`ControlView.tsx` → replace current AdminPanel with the clean operator control surface.

---

## Tranche Execution Order

```
Tranche 0 → Tranche A → Tranche B → Tranche C → Tranche D → Tranche E → Tranche F → Tranche G → Tranche H
```

---

## Tranche 0 — Kill Ollama and LM Studio Completely

**Goal:** llama.cpp is the only local inference runtime. Ollama and LM Studio are gone from every code path. Embeddings get a llamacpp-native fallback.

**Problem inventory (known locations):**

| File | Issue |
|---|---|
| `src/guppy/inference/local_client.py` | `_BACKENDS` dict includes `ollama`, `lmstudio`, `lemonade` entries; docstring references all three |
| `src/guppy/memory/semantic.py` | Line 31: `_EMBED_BASE_URL` defaults to `http://localhost:11434`; lines 86/101/168/172/194/324/346/362 all call Ollama embedding API |
| `src/guppy/memory/mempalace_adapter.py` | Lines 30/45: hardcoded `http://localhost:11434/api/embed` and `/api/embeddings` |
| `src/guppy/api/realtime_inference_support.py` | Lines 586, 611, 620, 669: references `_OLLAMA_CHAT_URL`, fallback messaging says "Start Ollama or LM Studio" |
| `src/guppy/api/routes_realtime.py` | Imports `_OLLAMA_CHAT_URL` from `realtime_inference_support` |
| `src/guppy/cli/launch.py` | Lines 91–95: `OLLAMA_MODEL`, `OLLAMA_FAST_MODEL`, etc. env defaults; line 193: `GUPPY_LOCAL_RUNTIME_BACKEND=ollama` |
| `src/guppy/cli/agent.py` | `ollama_turn()` function, imports `to_ollama_tools` |
| `src/guppy/api/error_codes.py` | `OLLAMA_*` error codes (lines 78–83, 160–165, 215–227) |
| `src/guppy/debug/_tabs.py` | `_check_ollama()`, references `_mode = "ollama"` |
| `guppy_core/network_utils.py` | `check_ollama()` function |
| `guppy_core/system_prompt.py` | `to_ollama_tools()` function |
| `guppy_core/__init__.py` | Exports `check_ollama`, `to_ollama_tools` |
| `guppy_core/tool_runner.py` | Line 1202: `GUPPY_OLLAMA_BASE_URL` env var, line 1216: Ollama chat call |
| `guppy_webui.py` | Lines 51–59: `OLLAMA_MODEL`, `OLLAMA_FAST_MODEL`, etc. env defaults |
| `docs/MASTER_PHASE_PLAN.md` | Phase 5 self-improvement calls "guppy-fast via Ollama"; Concurrent Silo model table references Ollama |
| `CLAUDE.md` | Multiple Ollama model roster entries, "Ollama removed from routing" note is partial |

**Deliverables:**

- [ ] `src/guppy/inference/local_client.py` — Remove `ollama`, `lmstudio`, `lemonade` entries from `_BACKENDS`. Remove all related env var lookups. Remove docstring references. Keep only `llamacpp-*` backends and `local_harness`.
- [ ] `src/guppy/memory/semantic.py` — Replace Ollama embedding HTTP calls with a llamacpp-native embedding path. Default `_EMBED_BASE_URL` to `http://localhost:8087` (Hermes 3, which supports `/v1/embeddings` via llama.cpp). Add `GUPPY_EMBED_BACKEND` env var (default: `llamacpp`). Stub: if `GUPPY_EMBED_BACKEND=none`, disable semantic memory entirely and log a warning rather than crash.
- [ ] `src/guppy/memory/mempalace_adapter.py` — Same: replace hardcoded Ollama URLs with the llamacpp embed URL.
- [ ] `src/guppy/api/realtime_inference_support.py` — Remove `_OLLAMA_CHAT_URL`. Remove Ollama/LM Studio fallback path and messaging. Remove `ollama` from the mode list in line 669.
- [ ] `src/guppy/api/routes_realtime.py` — Remove import of `_OLLAMA_CHAT_URL`.
- [ ] `src/guppy/cli/launch.py` — Remove all `OLLAMA_*` env defaults. Change default `GUPPY_LOCAL_RUNTIME_BACKEND` to `llamacpp-hermes3`.
- [ ] `src/guppy/cli/agent.py` — Remove `ollama_turn()`. Remove import of `to_ollama_tools`. Replace with llamacpp client call.
- [ ] `src/guppy/api/error_codes.py` — Replace `OLLAMA_*` error codes with `LOCAL_MODEL_*` equivalents. Update all references.
- [ ] `src/guppy/debug/_tabs.py` — Remove `_check_ollama()`. Remove `_mode = "ollama"` toggle logic.
- [ ] `guppy_core/network_utils.py` — Remove `check_ollama()`. Add `check_llamacpp(port: int) -> tuple[bool, str]`.
- [ ] `guppy_core/system_prompt.py` — Remove `to_ollama_tools()`. Local tool format is now OpenAI-compat (llama.cpp uses OpenAI tool schema natively).
- [ ] `guppy_core/__init__.py` — Remove exports of `check_ollama`, `to_ollama_tools`.
- [ ] `guppy_core/tool_runner.py` — Remove Ollama-specific HTTP call. Replace with llamacpp OpenAI-compat call.
- [ ] `guppy_webui.py` — Remove all `OLLAMA_*` env defaults.
- [ ] Update `CLAUDE.md` model roster — remove all Ollama model rows.

**Acceptance:**
- `grep -r "ollama\|lmstudio\|lemonade" src/ guppy_core/ guppy_webui.py` returns zero live code hits (comments/docstrings that say "removed" are fine).
- App starts without Ollama running.
- `GET /api/backends/llamacpp` returns all registered llamacpp backends.
- Semantic memory either embeds via llamacpp or degrades gracefully with a logged warning.

---

## Tranche A — Model Role Registry

**Goal:** One authoritative, code-level model role registry. No surface, route, or UI ever passes a raw model key as a routing mode string again.

**Problem inventory:**
- `realtime_inference_support.py` uses string modes: `"local"`, `"claude"`, `"ollama"`, `"code"`, `"teaching"`, `"vault"`, `"local_paired"` — these are ad hoc and not grounded in role semantics.
- `routes_backends.py` labels `llamacpp-dispatch` as "Phi-4-mini Orchestrator" but the underlying model file is still Qwen2.5-3B (ambiguity noted in CLAUDE.md).
- `routes_companion.py` personality presets hard-code model backend keys.
- `surface_config` table has per-surface model defaults but they are not validated against a role registry.
- Frontend sends arbitrary `mode` strings in `ChatRequest`.

**Deliverables:**

- [ ] New module: `src/guppy/model_roles.py`
  ```python
  # Authoritative model role registry
  MODEL_ROLES: dict[str, str] = {
      "conversation.default":           "llamacpp-hermes3",
      "conversation.partner.writing":   "llamacpp-rocinante",
      "conversation.partner.study":     "llamacpp-pepe",
      "conversation.partner.vision":    "llamacpp-minicpm",
      "workspace.controller":           "llamacpp-dispatch",
      "workspace.worker.primary":       "llamacpp-hermes4",
      "workspace.worker.escalation":    "llamacpp-chat",
      "workspace.tool_specialist":      "llamacpp-xlam",
  }

  ALWAYS_ON_ROLES = {
      "workspace.controller",
      "workspace.worker.primary",
      "conversation.default",  # or active partner
  }

  CONVERSATION_PARTNER_ROLES = [
      "conversation.default",
      "conversation.partner.writing",
      "conversation.partner.study",
      "conversation.partner.vision",
  ]
  ```
- [ ] `resolve_role(role: str) -> str` — returns the backend key for a role, raises `ValueError` for unknown roles.
- [ ] `get_active_conversation_partner() -> str` — reads `surface_config` DB for current partner role, returns backend key.
- [ ] Wire `routes_companion.py` and `routes_surface.py` to use `model_roles.resolve_role()` instead of hard-coded backend keys.
- [ ] Wire `realtime_inference_support.py` — replace ad hoc mode strings with role-based resolution. Mode `"local"` maps to `conversation.default`. Mode `"workspace"` maps to `workspace.worker.primary`. Remove `"ollama"`, `"vault"`, `"teaching"` modes entirely.
- [ ] `GET /api/model-roles` — returns the full registry + current assignments (for Control surface display).
- [ ] `PUT /api/model-roles/conversation-partner` — body `{"role": "conversation.partner.writing"}` — operator changes partner. Validates against `CONVERSATION_PARTNER_ROLES`.
- [ ] Update `surface_config` DB seeding to use role keys, not raw backend strings.

**Acceptance:**
- `grep -r '"local"\|"ollama"\|"vault"\|"teaching"\|"code"' src/guppy/api/realtime_inference_support.py` returns no routing-decision sites.
- `GET /api/model-roles` returns a valid JSON map.
- `PUT /api/model-roles/conversation-partner` with `{"role": "conversation.partner.writing"}` switches Conversations to Rocinante.
- Invalid role returns 422.

---

## Tranche B — Operator Control Surface

**Goal:** Replace the current sprawling settings UI with a clean, minimal control surface that exposes exactly the three operator controls: paid cloud on/off, free cloud on/off, conversation partner selection.

**Current problem:**
- `ControlView.tsx` exists but is under-defined.
- `SettingsView.tsx` exposes too much internal routing.
- Frontend `BackendSelector.tsx` lets users pick arbitrary model keys — this must die.
- `ModelsView.tsx` and `ProvidersView.tsx` are operator-facing and confuse model selection with routing.

**Deliverables:**

- [ ] Backend: `GET/PUT /api/control/operator-settings`  
  Schema:
  ```json
  {
    "cloud_paid_enabled": true,
    "cloud_free_enabled": false,
    "conversation_partner": "conversation.default"
  }
  ```
  Stored in a new `operator_settings` table in `guppy_main.db`. NOT in `settings.db` or `surface_config`.
- [ ] Backend validates `conversation_partner` against `CONVERSATION_PARTNER_ROLES`.
- [ ] `ControlView.tsx` rewrite — three sections:
  1. **Cloud Access** — two toggles: Paid Cloud (Claude/GPT), Free Cloud (Mistral/Cohere).
  2. **Conversation Partner** — four radio cards: Hermes 3 (default), Rocinante (writing/roleplay), Pepe (study/funny), MiniCPM (vision/private).
  3. **Model Health** — read-only status grid: each core model's port, warm status, last ping. No start/stop from here (that is backend auto-management).
- [ ] Remove `BackendSelector.tsx` from Companion/Workspace/Codespace headers. It should not be visible on any surface.
- [ ] `SettingsView.tsx` — remove model/backend selection panels. Keep only: appearance, voice settings, notifications, API keys.
- [ ] `ModelsView.tsx` — archive to `web/src/views/archive/`. Replace nav link in Control with Model Health section.

**Acceptance:**
- User cannot select a model key directly anywhere in the UI.
- `GET /api/control/operator-settings` returns current state.
- Toggling paid cloud off prevents any cloud routing (backend enforces, not just UI).
- Conversation partner change takes effect on the next Conversations chat turn.

---

## Tranche C — Auto Warm Manager

**Goal:** Core models start automatically. No manual "start model" required in normal operation. Persona models hot-swap when the partner changes.

**Current state:**
- `routes_backends.py` has `auto_start: True` on dispatch, hermes4, hermes3 — but the start logic is only partially wired in the watchdog.
- `services_runtime_warmup.py` exists — review its coverage.
- The 70B CPU model is never auto-started/warmed.

**Deliverables:**

- [ ] `src/guppy/api/services_model_manager.py` (new) — Model lifecycle manager:
  - `_REQUIRED_ROLES` = `["workspace.controller", "workspace.worker.primary", "conversation.default"]`
  - `_OPTIONAL_ROLES` = `["conversation.partner.writing", "conversation.partner.study", "conversation.partner.vision", "workspace.tool_specialist"]`
  - On startup: iterate `_REQUIRED_ROLES`, resolve to backend keys, launch `.bat` files for any that aren't responding on their port.
  - Watchdog thread: every 60 s, ping each required role's port. If dead, restart. Log ERROR. Broadcast SSE `model_restart` event.
  - On partner change (from Tranche B): unload current partner model (stop process), start new partner model, warm KV cache.
  - 70B registration: added to `_LLAMACPP_CONFIG` with `cpu_only: True`, no `auto_start` (it starts on first escalation request, not at boot).
- [ ] KV cache warming: after process start, send a 1-token prefill to each required model (already exists for hermes3/hermes4 — extend to dispatch/phi).
- [ ] `GET /api/model-health` — returns `{role: {backend, port, status: warm|starting|offline, latency_ms}}` for all roles.
- [ ] Wire model manager startup into server `lifespan` in `server_runtime.py`.
- [ ] `services_runtime_warmup.py` — audit and merge or deprecate into the new manager.

**Acceptance:**
- Server boots and all three required models (dispatch, hermes4, hermes3) are warm within 90 s without manual action.
- Killing one required model process causes auto-restart within 60 s.
- `GET /api/model-health` shows `warm` for required roles.
- 70B starts on first escalation request, not at boot.

---

## Tranche D — Conversations Surface (Dedicated Chat Path)

**Goal:** Conversations is a first-class daily chat surface with persistent sessions, voice, vision, and a clean delegation path to Workspace. It does not share a route or model with Workspace.

**Current state:**
- `CompanionView.tsx` is the current conversation surface but named/framed as "Companion."
- Chat goes through the generic `/api/chat/stream` route in `routes_realtime.py` — same route used by Workspace.
- Session model is not per-surface; history bleeds.

**Deliverables:**

**Backend:**
- [ ] `routes_conversations.py` — new dedicated router:
  - `POST /api/conversations/chat` — non-streaming
  - `POST /api/conversations/chat/stream` — SSE streaming (primary)
  - `GET /api/conversations/sessions` — list conversation sessions
  - `POST /api/conversations/sessions` — create session
  - `GET /api/conversations/sessions/{id}/messages` — history
  - `DELETE /api/conversations/sessions/{id}` — clear session
- [ ] Conversation model always uses `model_roles.get_active_conversation_partner()` — never a mode string.
- [ ] Tool envelope for conversations: `web_fetch`, `create_reminder`, `download_media`, `memory_write`, `memory_recall`, `workspace_task`. No file writes, no shell, no code execution.
- [ ] `workspace_task` tool creates a record via `POST /api/workspace/tasks` (internal call, not user-visible) and returns a task ID + status to the conversation.
- [ ] Sessions stored in `conversations` and `conversation_messages` tables in `guppy_main.db`.
- [ ] Pepe personality system prompt — retune for study/funny-chat. Remove "internet humor / shitpost energy." Replace with: curious study partner, explains things clearly, occasionally dry/irreverent humor. Still uses full tool schema.
- [ ] Mount `routes_conversations.py` in `server_runtime.py`.

**Frontend:**
- [ ] Rename `CompanionView.tsx` → `ConversationsView.tsx`. Update route from `/companion` to `/conversations`. Keep `/companion` as redirect for compatibility.
- [ ] Nav sidebar: change label "Companion" → "Conversations."
- [ ] `ConversationsView.tsx` reads from `/api/conversations/*` — not from generic chat route.
- [ ] Session picker in sidebar panel (collapsible) — list of recent sessions, create new.
- [ ] Partner selector — four cards rendered from `GET /api/control/operator-settings` + `GET /api/model-roles`. Shows only partner models, not worker models.
- [ ] Remove `BackendSelector.tsx` from this view entirely.
- [ ] Voice, vision, avatar presence stay as-is.
- [ ] "Hand to Workspace" button on any message → calls `workspace_task` tool → shows task ID chip.

**Acceptance:**
- Conversations chat uses the active conversation partner, not a generic local backend.
- A fresh session starts clean; history is session-scoped.
- Pepe is the study partner, not the shitposter.
- "Hand to Workspace" creates a visible task in Workspace's task panel.
- Switching partner mid-conversation starts using the new model on the next turn.

---

## Tranche E — Workspace Orchestrator Boundary

**Goal:** Workspace is the durable automation backbone. Phi is the controller. Hermes 4 is the worker. Long-running tasks, PC control, scheduling, tool chains, and 70B escalation all live here — not in `routes_realtime.py`.

**Current state:**
- Workspace chat currently goes through the same generic `/api/chat/stream`.
- `routes_surface.py` has `spawn_task` but it's lightweight.
- No dedicated task state machine.
- PC control exists in `routes_desktop.py` as raw pyautogui calls — no grounding layer.
- Screenpipe is wired in `routes_screenpipe.py` but not deeply integrated into the task loop.

**Deliverables:**

**Backend:**
- [ ] `src/guppy/workspace/orchestrator.py` — Workspace orchestrator module:
  - Task state machine: `queued → planning → running → blocked → complete | failed`
  - Phi controller loop: receives task, emits plan, dispatches to Hermes4 for execution steps
  - Escalation: if Hermes4 returns `needs_escalation=true`, re-route step to 70B (queued, async)
  - Tool executor: `web_search`, `file_read`, `file_list`, `shell_run`, `contacts_search`, `calendar_read`, `email_read`, `screenpipe_search`, `pc_screenshot`, `pc_click`, `pc_type`, `pc_scroll`
  - Safety gate: destructive actions (`file_delete`, `shell_run` with mutation, `pc_click` on new app) require `requires_confirmation=true` returned to SSE — user must confirm before execution continues
  - Trace log: every action step written to `workspace_task_steps` table
- [ ] `routes_workspace.py` (replace/extend `routes_workspace_data.py`):
  - `POST /api/workspace/tasks` — create task (from Conversations delegation or direct)
  - `GET /api/workspace/tasks` — list with state filter
  - `GET /api/workspace/tasks/{id}` — task detail + step trace
  - `POST /api/workspace/tasks/{id}/run` — trigger orchestrator
  - `POST /api/workspace/tasks/{id}/confirm` — user confirms blocked action
  - `POST /api/workspace/tasks/{id}/cancel`
  - `GET /api/workspace/tasks/{id}/stream` — SSE: live step output
  - `POST /api/workspace/events` — internal event bus for surface comms
- [ ] Task DB tables: `workspace_tasks`, `workspace_task_steps` in `guppy_main.db`.
- [ ] Remove workspace tool execution from `routes_realtime.py` — it should not be in the generic chat route.

**Frontend:**
- [ ] `WorkspaceView.tsx` — "Chat" tab uses `/api/workspace/tasks` model, not `/api/chat/stream`. Chat in Workspace submits a task, not a free-form message stream.
- [ ] Task panel (Agents tab) — real-time task list with state badges, step trace accordion, confirm/cancel buttons.
- [ ] "Workspace Chat" input → creates a task → immediately shows in task panel with `planning` state.
- [ ] Safety confirmation modal — shown when task hits `blocked` on a destructive action.

**Acceptance:**
- Creating a task from Conversations (via `workspace_task` tool) appears in Workspace task panel with correct state.
- Phi plans, Hermes4 executes, 70B escalates — each visibly labeled in the step trace.
- A `shell_run` task that mutates files pauses at `blocked` state, waits for user confirm.
- Screenpipe search is available as a workspace tool and appears in step traces.

---

## Tranche F — OmniParser / UI-TARS Screen Parsing Layer

**Goal:** Upgrade PC control from raw coordinate clicks to grounded, vision-understood UI actions. The pattern: observe → parse → decide → ground action → safety gate → execute → trace.

**Current state:**
- `routes_desktop.py` has raw `pyautogui` screenshot/click/type/drag/scroll.
- No semantic understanding of what's on screen.
- No element grounding.

**Architecture to implement (copy pattern from OmniParser + UFO/UI-TARS):**

```
Screenshot → OmniParser parse → element map → action grounding → pyautogui execute
```

**Deliverables:**

- [ ] `src/guppy/workspace/screen_parser.py`:
  - `capture_screen() -> PIL.Image` — wraps `pyautogui.screenshot()`
  - `parse_screen(image) -> list[UIElement]` — calls OmniParser or falls back to MiniCPM vision for element detection
  - `UIElement` datatype: `{label, bbox, element_type, confidence}`
  - `find_element(elements, description: str) -> UIElement | None` — fuzzy match by label/description
  - `ground_click(description: str) -> tuple[int, int]` — returns pixel coordinates for a described element
- [ ] OmniParser integration — use Microsoft OmniParser v2 ONNX model locally (no API call):
  - Check for model at `C:\guppy-models\omniparser\` — if missing, fall back to MiniCPM vision query
  - `GUPPY_OMNIPARSER_MODEL_PATH` env var override
  - OmniParser runs fast (CPU ONNX) — suitable for per-action grounding
- [ ] MiniCPM fallback vision path — when OmniParser model not present, send screenshot to `llamacpp-minicpm` with "describe all visible UI elements and their locations" prompt, parse JSON response into `UIElement` list
- [ ] Updated `routes_desktop.py`:
  - `POST /api/desktop/click-element` — body `{"description": "Submit button"}` → grounded click
  - `POST /api/desktop/type-in` — body `{"description": "search bar", "text": "..."}` → grounded focus + type
  - `POST /api/desktop/screenshot-parsed` — returns screenshot + parsed element map
  - Keep raw `POST /api/desktop/click` (by coords) for backward compat + explicit use
- [ ] Action safety gate:
  - `SAFE` actions (screenshots, reads): execute immediately
  - `MODERATE` actions (clicks on known app): execute, log
  - `DESTRUCTIVE` actions (clicks in system UI, type in admin field): require `requires_confirmation=true` — surface to Workspace confirm flow
- [ ] Action trace: every grounded action logged to `workspace_task_steps` with element label + bbox + screenshot hash

**Frontend:**
- [ ] Workspace `ScreenPanel.tsx` (new tab in PC section) — shows live parsed element map overlaid on screenshot. Highlighted elements clickable (for manual grounding preview).
- [ ] "What's on screen?" button → captures + parses → shows element list in panel.

**Acceptance:**
- `POST /api/desktop/click-element {"description": "Chrome address bar"}` clicks the correct element on screen.
- OmniParser model absent → MiniCPM vision fallback → still returns a valid element map.
- A destructive action (clicking "Uninstall" button) hits the safety gate and blocks.
- Screenpipe timeline and the parsed element map are both available in Workspace PC tab.

---

## Tranche G — Screenpipe Deep Integration

**Goal:** Screenpipe is not just a status widget. It is the memory layer for everything that has happened on screen. Workspace tasks can search it. The conversation partner can reference it. It feeds the context for PC control decisions.

**Current state:**
- `routes_screenpipe.py` provides status/search/recent — good foundation.
- `ScreenPanel.tsx` shows recent + search tabs — good foundation.
- AI summaries exist in `routes_screen_monitor.py` but call "guppy-fast via Ollama" (Tranche 0 must fix this first).
- Workspace orchestrator does not search Screenpipe as part of task planning.
- Conversation partner cannot reference screen history.

**Deliverables:**

**Backend:**
- [ ] Fix `routes_screen_monitor.py` — replace Ollama AI summary call with `llamacpp-hermes3` (fast, always-on). Use `POST http://localhost:8087/v1/chat/completions` for summary generation.
- [ ] `GET /api/screenpipe/context` — new endpoint: given a `task_description`, searches Screenpipe for relevant recent activity, returns summarized context (up to 3 relevant clips). Used by orchestrator before task planning.
- [ ] `GET /api/screenpipe/app-focus` — returns the currently focused application (via most recent Screenpipe OCR frame).
- [ ] Wire `screenpipe_search` as a workspace orchestrator tool (see Tranche E).
- [ ] Wire `screenpipe_context` into Phi's planning prompt: before planning a task, Phi sees "Recent screen context: [summary]".
- [ ] Companion `memory_recall` tool can optionally include Screenpipe context when query matches time-based or app-based patterns (e.g., "what was I working on this morning").

**Frontend:**
- [ ] `ScreenPanel.tsx` — add "Context Search" tab: text input → calls `/api/screenpipe/context` → returns relevant clips with app name, timestamp, OCR text snippet, AI summary.
- [ ] Timeline tab — replace Ollama summary chip with llamacpp-generated summary (no code change if backend fix is done, chip just shows the stored summary).
- [ ] Workspace task detail — show "Screen context used" accordion if task planning pulled Screenpipe data.

**Acceptance:**
- `GET /api/screenpipe/context?task_description=write+email` returns relevant recent Screenpipe clips.
- AI summaries in timeline are generated by Hermes 3, not Ollama.
- Workspace task planning prompt includes recent screen context when Screenpipe is running.
- Screenpipe offline → graceful degradation, orchestrator continues without context, logs warning.

---

## Tranche H — BookDrop / Library Surface

**Goal:** Guppy is a personal media library, not just a chat assistant. The library surface should handle book/document intake, metadata enrichment, reader access, and device sync. Copy BookLore's UX patterns.

**Current state:**
- `routes_library.py` — collections + items CRUD exists.
- `routes_calibre.py` — Calibre integration exists.
- `routes_drop.py` — GuppyDrop watchdog + SSE push exists.
- `routes_acquisition.py` — acquisition tracking exists.
- `routes_media.py` — qBittorrent proxy, media catalog, Whisper transcription exists.
- `LibraryView.tsx` — full CRUD wired to API.
- Missing: metadata enrichment pipeline, built-in reader, OPDS sync, BookDrop-style intake UI.

**Deliverables:**

**Backend:**
- [ ] `routes_library.py` — add:
  - `POST /api/library/items/{id}/enrich` — trigger metadata enrichment: hit Open Library / Google Books API for cover, description, ISBN, tags. Store enriched metadata in `library_items` table.
  - `POST /api/library/drop` — file upload endpoint (PDF, EPUB, MOBI) — saves to configured `GUPPY_LIBRARY_PATH`, triggers enrichment, adds to collection.
  - `GET /api/library/items/{id}/read` — returns raw file bytes with correct Content-Type for in-browser reading.
  - `GET /api/library/opds` — OPDS 2.0 catalog feed for e-reader device sync (Koreader, Moon+ Reader, etc.).
  - `GET /api/library/opds/item/{id}` — OPDS item entry with download link.
- [ ] `src/guppy/library/enricher.py` — metadata enrichment service:
  - `enrich(title: str, author: str) -> dict` — queries Open Library API (free, no key), returns `{cover_url, description, subjects, publish_year, isbn}`.
  - Stores result in `library_metadata` table. Cached — re-use within 30 days.
- [ ] `routes_drop.py` — auto-enrich newly dropped files: after watchdog picks up a new file, trigger enrichment if it's a book format.
- [ ] Torrent/download policy gate: `POST /api/library/acquire` — accepts URL or search query, validates `LIBRARY_ACQUISITION_POLICY` env var (`open_content_only` | `user_approved` | `unrestricted`). Default: `user_approved` (requires explicit user confirmation per download).
- [ ] AI document analysis (existing `routes_documents.py`) — surface to library items: "Analyze this book" → Hermes 4 summarizes content, extracts themes, stores as `library_item_notes`.

**Frontend:**
- [ ] `LibraryView.tsx` — add panels:
  - **Drop zone** — drag-and-drop file intake area (BookDrop pattern). Shows import progress + enrichment status.
  - **Reader** — inline EPUB/PDF reader pane. Opens from item card. Full-screen mode.
  - **Enrichment status** — per-item metadata badge: "Enriched" | "Pending" | "No metadata found."
  - **OPDS chip** — shows OPDS feed URL for copying to e-reader. QR code option.
  - **Acquisition panel** — form for search/URL-based acquisition, policy gate warning, confirmation step.
- [ ] Remove any default torrent behavior from Companion tool schema — `download_media` tool should only be available if `LIBRARY_ACQUISITION_POLICY != open_content_only`.

**Acceptance:**
- Dropping a PDF into the drop zone adds it to the library, enriches metadata from Open Library, and shows cover/description within 30 s.
- `GET /api/library/opds` returns a valid OPDS 2.0 feed parseable by Koreader.
- In-browser reader opens an EPUB without external service calls.
- Acquisition form shows a confirmation step before any download is queued.
- AI analysis of a library item uses Hermes 4 via llamacpp — not Ollama.

---

## Tranche I — Database Source of Truth + Cleanup

**Goal:** One authoritative runtime settings store. No split-brain between `settings.db`, `surface.db`, `guppy_memory.db`, and inline SQLite fragments.

**Current problem inventory:**

| Store | Location | Problem |
|---|---|---|
| `settings.db` (root) | `runtime/settings.db` | Ad hoc settings writes from multiple routes |
| `settings.db` (user-data) | OS user-data dir | Duplicate? Unclear authority |
| `surface.db` | `runtime/surface.db` | Surface config — may not be used by all surfaces |
| `guppy_memory.db` | `runtime/guppy_memory.db` | Facts/contacts/tasks — correct owner |
| `guppy_main.db` | `runtime/guppy_main.db` | Chat history, inference metrics — correct owner |
| `triage.db` | `runtime/triage.db` | Codespace triage history — correct |
| Provider config DB | unclear | Referenced in conversation, not found in repo scan |

**Deliverables:**

- [ ] Audit all SQLite open calls in `src/guppy/` — catalog every distinct DB file and table.
- [ ] Produce `docs/audit/database-inventory.md` (Tranche 1 deliverable, produce here as part of fix).
- [ ] Consolidation decision:
  - `guppy_main.db` — canonical app DB: chat sessions, messages, workspace tasks, operator settings, model health log, inference metrics, calendar, email cache, contacts, pipeline, library items, VOIP log.
  - `guppy_memory.db` — canonical memory DB: facts, memory_items, semantic embeddings index.
  - `triage.db` — codespace only (fine as separate).
  - `settings.db` (root and user-data) → migrate live rows to `guppy_main.db.operator_settings`, then delete files.
  - `surface.db` → migrate to `guppy_main.db.surface_config`, then delete file.
- [ ] Add Alembic migration for any new tables created in Tranches A–H.
- [ ] `src/guppy/db/` — new db access module:
  - `get_main_db()` — returns connection to `guppy_main.db`
  - `get_memory_db()` — returns connection to `guppy_memory.db`
  - All WAL mode, foreign keys ON, busy timeout 5000 ms.
  - Replace scattered `sqlite3.connect(...)` calls in route files.

**Acceptance:**
- `find . -name "*.db" | grep -v ".venv"` lists only: `guppy_main.db`, `guppy_memory.db`, `triage.db` (and test fixtures).
- No route file opens a SQLite connection directly — all go through `src/guppy/db/`.
- `GET /api/control/operator-settings` reads from `guppy_main.db`.
- Surface config reads from `guppy_main.db.surface_config`.

---

## Tranche J — Docs Reconciliation

**Goal:** Docs describe the actual system. Stale archaeology is archived.

**Files to archive to `docs/archive/`:**

| File | Reason |
|---|---|
| `PHASE_1_IMPLEMENTATION_TASKS.md` | Superseded by MASTER_PHASE_PLAN |
| `PHASE_2_IMPLEMENTATION_TASKS.md` | Same |
| `PHASE_3_IMPLEMENTATION_TASKS.md` | Same |
| `PHASE2_INTEGRATION_GUIDE.md` | Same |
| `PHASE3_IMPLEMENTATION_SUMMARY.md` | Same |
| `PHASE3_INTEGRATION_GUIDE.md` | Same |
| `PHASE4_HEALTH_OPTIMIZATION_PLAN.md` | Same |
| `PHASE4A_ENDPOINTS_REFERENCE.md` | Same |
| `PHASE4A_IMPLEMENTATION_SUMMARY.md` | Same |
| `P0_PARITY_TESTING_PLAN_2026-04-23.md` | Old |
| `GAP_ANALYSIS_AGENT_SPAWNING_2026-04-25.md` | Old |
| `STRATEGIC_ASSESSMENT_2026-04-25.md` | Old |
| `AUDIT_FINDINGS_2026_04_26.md` | Superseded |
| `AUDIT_REPORT_2026_04_26.md` | Superseded |
| `REPO_REVIEW_SUMMARY_2026-04-27.md` | Old |
| `GIT_STATUS_2026-04-23.md` | Old |
| `ROADMAP_UPDATE_2026-04-27.md` | Old |
| `READINESS_REVIEW_2026-04-28.md` | Old |
| `PLATFORM_HARDENING_PLAN_2026-04-28.md` | Old |
| `EXECUTION_PRIORITY_MATRIX.md` | Old |

**Docs to rewrite/create:**

- [ ] `docs/LIVE_ARCHITECTURE.md` — current route map, model roles, DB layout, surface map. (Already exists — update to reflect Tranches 0–I.)
- [ ] `docs/SURFACES.md` — Conversations vs Workspace vs Codespace vs Control. Chat flow, delegation, model per surface.
- [ ] `docs/MODEL_ROUTING.md` — role registry, VRAM budget, warm policy, partner hot-swap logic.
- [ ] `docs/DATABASES.md` — which DB, which tables, who owns them, migration status.
- [ ] `docs/PC_CONTROL.md` — screen parsing architecture, safety gate levels, OmniParser integration.
- [ ] `docs/LIBRARY.md` — intake, enrichment, OPDS, acquisition policy.
- [ ] Update `CLAUDE.md` — remove Ollama model roster, add role registry table, update verified working list.
- [ ] Update `docs/MASTER_PHASE_PLAN.md` — mark Phases 1–5 as historical. Add this codex reference.

---

## Tranche K — Tests and Guardrails

**Goal:** No regression on the boundaries we just built.

**Deliverables:**

- [ ] `tests/unit/test_model_roles.py` — role resolution, partner selection, invalid role rejection.
- [ ] `tests/unit/test_operator_settings.py` — cloud gate enforcement, partner validation.
- [ ] `tests/integration/test_conversations_route.py` — conversation stream, session persistence, tool whitelist enforcement.
- [ ] `tests/integration/test_workspace_tasks.py` — task creation, state machine transitions, delegation from conversations.
- [ ] `tests/integration/test_model_routing.py` — conversation partner → correct backend port, workspace worker → hermes4 port, no Ollama port hit.
- [ ] `tests/integration/test_screenpipe_integration.py` — context search, app focus, graceful offline fallback.
- [ ] `tests/smoke/test_no_ollama.py` — asserts no HTTP call is made to port 11434 during a full chat round-trip.
- [ ] `tests/smoke/test_llamacpp_only.py` — asserts `_BACKENDS` in `local_client.py` contains no `ollama`/`lmstudio`/`lemonade` keys.
- [ ] Frontend typecheck: `pnpm tsc --noEmit` passes clean.
- [ ] Add to `dev_workflow.py dev-check`: run `test_no_ollama` and `test_llamacpp_only` as part of default guard.

---

## Button and Connector Audit (Companion / Workspace / Codespace)

This is a reference for Tranche D–F frontend work. Every button and wired connector is listed with its current state and target state.

### Conversations (was Companion)

| UI Element | Current State | Target State |
|---|---|---|
| Chat input → send | Routes to `/api/chat/stream` with `mode` string | Routes to `POST /api/conversations/chat/stream` |
| Voice PTT button | Wired to `/api/voices/listen_once` | Keep — no change |
| Wake word toggle | Wired to `/api/companion/voice/session` | Update URL to `/api/conversations/voice/session` |
| Camera / vision button | Wired to `/api/companion/vision` | Update URL to `/api/conversations/vision` |
| "Escalate to Workspace" button | POSTs to `/api/surface/spawn` | Becomes "Hand to Workspace" → calls `workspace_task` tool → `POST /api/workspace/tasks` |
| BackendSelector dropdown | Selects arbitrary model key | **Remove entirely** |
| PersonalityPicker dropdown | Selects personality preset | Becomes PartnerPicker: 4 cards, reads from `/api/control/operator-settings` |
| Avatar presence | Wired to voice state | Keep — no change |
| SurfaceStatusBar chip | Live SSE, shows other surface states | Keep — no change |
| Session list | Not present | Add — collapsible sidebar, reads `/api/conversations/sessions` |

### Workspace

| UI Element | Current State | Target State |
|---|---|---|
| Chat tab input | Routes to `/api/chat/stream` | Routes to `POST /api/workspace/tasks` (task creation) |
| Agents tab | Shows spawned tasks via SSE | Keep + extend with step trace accordion |
| CRM tab | Wired to `/api/workspace/contacts` + `/api/workspace/tasks` | Keep |
| Screen tab — Recent | Wired to `/api/screenpipe/recent` | Keep |
| Screen tab — Search | Wired to `/api/screenpipe/search` | Keep + add Context Search sub-tab |
| Screen tab — Timeline | Wired to `/api/screen/timeline` | Keep — AI summaries now from Hermes3 |
| Files tab | Wired to `/api/files/*` | Keep |
| PC tab | Wired to `/api/system/*` | Keep + add Screenshot+Parse button |
| Tasks tab | Wired to `/api/tasks/*` | Migrate to `/api/workspace/tasks` |
| Calendar tab | Wired to `/api/calendar/*` | Keep |
| Email tab | Wired to `/api/email/*` | Keep |
| Media tab | Wired to `/api/media/*` | Keep |
| VoIP tab | Wired to `/api/voip/*` | Keep |
| BackendSelector | In header | **Remove** |
| Task confirm modal | Not present | Add — shown when task hits `blocked` state |
| Safety gate confirm | Not present | Add — shown for destructive PC actions |

### Codespace

| UI Element | Current State | Target State |
|---|---|---|
| Chat tab | Routes to `/api/chat/stream` | OK — Codespace chat can use generic stream with codespace surface context |
| Sandbox tab | Wired to `/api/codespace/sandbox/*` | Keep |
| Triage tab | Wired to `/api/codespace/triage/*` | Keep |
| Self-improve proposals | Wired to `/api/codespace/proposals/*` | Keep — fix: proposals currently call guppy-fast→Ollama (see Tranche 0) |
| BackendSelector | Not present | Keep absent |

### Control (was ControlView)

| UI Element | Current State | Target State |
|---|---|---|
| Current content | Sparse / placeholder | Rewrite: Cloud toggles + Partner picker + Model health grid |
| Model health grid | Not present | Add — reads `/api/model-health` |
| Cloud paid toggle | Not present | Add — writes `/api/control/operator-settings` |
| Cloud free toggle | Not present | Add — same |
| Partner picker | Not present | Add — 4 radio cards |
| Admin / diagnostics | Mixed into settings | Move to `/admin` (existing AdminPanel) |

---

## Summary: What Changes, What Stays

| Component | Fate |
|---|---|
| Ollama, LM Studio, Lemonade | **Eliminated** (Tranche 0) |
| llama.cpp backends | **First-class, only runtime** |
| Semantic embeddings | **Migrated to llamacpp** (Hermes 3 `/v1/embeddings`) |
| CompanionView | **Renamed → ConversationsView**, dedicated route |
| Generic `/api/chat/stream` | **Narrowed** — only Codespace uses it directly; Conversations and Workspace get dedicated routes |
| Model role registry | **New** (Tranche A) — single truth |
| BackendSelector UI | **Removed from all surfaces** |
| Operator settings | **New clean table**, 3 controls only |
| Auto warm manager | **New** — Phi + Hermes4 + active partner always warm |
| OmniParser screen parsing | **New** (Tranche F) — grounded PC control |
| Screenpipe | **Deepened** (Tranche G) — feeds orchestrator planning |
| Library / BookDrop | **Extended** (Tranche H) — OPDS, enrichment, reader |
| DB consolidation | `guppy_main.db` + `guppy_memory.db` only |
| Stale docs | **Archived** to `docs/archive/` |
