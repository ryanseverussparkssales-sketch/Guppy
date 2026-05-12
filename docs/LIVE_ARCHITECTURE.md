# Live Architecture Map

Last updated: 2026-05-03

> **Authority:** CLAUDE.md owns module/routing facts. This doc owns the dependency and domain model.

---

## Primary Surface: Web UI

The Web UI (React/Vite, `web/`) is the **authoritative user surface**, served at `http://localhost:<port>` by the FastAPI backend. The desktop launcher (`launcher_app.py`) is a Qt wrapper that spawns the server and opens the browser — it holds no UI logic.

**Nav structure:** Three primary surfaces → Companion | Workspace | Codespace. All secondary nav (Personas, Instructions, Tools, Settings, Admin) is accessible from within each surface.

---

## Three Primary Surfaces

### Companion (`/companion`)
Voice-first, personality-led. Animated avatar, push-to-talk, wake word, camera vision, escalate-to-Workspace.
Model cascade (2026-05-03 consolidation): hermes4 (8086) → hermes3 (8087, on-demand) → Haiku cloud.
Fast path: simple queries (≤12 words, no tool cues) → phi4-mini (8091) first (~0.3s TTFT), falls through to 36B if needed.

### Workspace (`/workspace`)
15-tab hub: Chat | Agents | CRM | Screen | Files | PC | Tasks | Calls | Calendar | Email | Media | Docs | Tools | Memory | Leads.
Model cascade: hermes4 (8086) → hermes3 (8087, on-demand) → Sonnet cloud.

### Codespace (`/codespace`)
3-tab: Chat | Sandbox | Triage.
Model cascade: hermes4 (8086) → hermes3 (8087) → Sonnet cloud.

---

## Backend Route Map (all active, all mounted)

| Prefix | Module | Notes |
|---|---|---|
| `/api/chat` | `routes_realtime.py` | SSE streaming + WebSocket inference |
| `/api/agents` | `routes_agents.py` | Agent registry CRUD |
| `/api/surface/*` | `routes_surface.py` | Surface state, spawn, SSE event bus |
| `/api/companion/*` | `routes_companion.py` | Personality, voice session, vision, tool whitelist |
| `/api/workspace/*` | `routes_workspace_data.py` | Contacts/tasks JSON API + pipeline proxy |
| `/api/codespace/*` | `routes_codespace.py` | Sandbox lifecycle + triage + self-improvement |
| `/api/screen/*` | `routes_screen_monitor.py` | AI activity summaries, 30-min background job |
| `/api/voip/*` | `routes_voip.py` | Call log CRUD, Twilio webhook |
| `/api/calendar/*` | `routes_calendar.py` | Local events + Google Calendar sync |
| `/api/email/*` | `routes_email.py` | Local cache + Gmail sync |
| `/api/media/*` | `routes_media.py` | qBittorrent proxy + media catalog + recordings |
| `/api/documents/*` | `routes_documents.py` | Upload + AI analysis + download |
| `/api/tasks/*` | `routes_tasks.py` | Task CRUD |
| `/api/mcp/*` | `routes_mcp.py` | MCP server add/remove/enable/test |
| `/api/desktop/*` | `routes_desktop.py` | pyautogui screenshot/click/type/scroll |
| `/api/inference/metrics` | `routes_inference_metrics.py` | Time-series metrics from guppy_main.db |
| `/api/screenpipe/*` | `routes_screenpipe.py` | External Screenpipe daemon bridge (port 3030) |
| `/api/voices` | `routes_voice.py` | TTS/STT management |
| `/api/backends/llamacpp` | `routes_backends.py` | llamacpp backend management |
| `/api/pipeline/*` | `routes_pipeline.py` | CRM pipeline |
| `/api/reminders/*` | `routes_reminders.py` | Reminders |
| `/api/files/*` + `/api/system/*` | `routes_files.py` | File browser, psutil metrics, clipboard |
| `/api/drop/*` | `routes_drop.py` | GuppyDrop watchdog + SSE push |
| `/api/library/*` | `routes_library.py` | Collections + items CRUD |
| `/api/booklet/*` | `routes_booklet.py` | Booklet sections |
| `/api/calibre/*` + `/api/kindle/*` | `routes_calibre.py` | Calibre/Kindle integration |
| `/api/acquisition/*` | `routes_acquisition.py` | LazyLibrarian/Prowlarr |
| `/api/tier3/*` | `routes_tier3.py` | Tier3 features |
| `/api/queue/*` | `routes_queue.py` | Inference job queue |
| `/api/providers/*` | `routes_providers.py` | Provider management |
| `/api/provider-management/*` | `routes_provider_management.py` | Provider lifecycle |
| `/api/settings/*` | `routes_settings.py` | Settings |
| `/api/models/*` | `routes_models.py` | Model management |
| `/api/model-roles/*` | `routes_model_roles.py` | Surface-to-model role assignment + operator config |
| `/api/workspaces/*` | `routes_workspaces.py` | Workspace management |
| `/api/workspace/*` | `routes_workspace.py` | Workspace-specific helpers |
| `/api/instances/*` | `routes_instances.py` | Instance management |
| `/api/chat-history/*` | `routes_chat_history.py` | Conversation history |
| `/api/conversations/*` | `routes_conversations.py` | Persistent sessions, SSE streaming, partner selection |
| `/api/memory/*` | `routes_memory.py` | Memory CRUD and semantic search (user-facing) |
| `/api/control/*` | `routes_control.py` | Service/model lifecycle, logs viewer, PC health |
| `/api/vpn/*` | `routes_vpn.py` | VPN connection management |
| `/api/launcher/*` | `routes_launcher.py` | Launcher control |
| `/api/tools/*` | `routes_tools.py` | Tool registry |
| (ops) | `routes_ops.py` | Repair token, ops endpoints |
| (core) | `routes_core.py` | Core infrastructure endpoints |

---

## Inference Stack

- **Task types:** simple, complex, teaching, agentic, tool_call
- **Modes:** auto, claude, ollama, local, code, teaching, vault, local_paired
- **Classifier:** Haiku semantic + heuristic fallback
- **llamacpp backends** (fixed ports): pepe (8082), qwen3 (8083), minicpm (8084), dispatch (8085), hermes4 (8086), hermes3 (8087), rocinante (8088), xlam (8089), chat-70b (8090), phi4-mini (8091), nomic-embed (8092)
- **Ollama removed from routing** — `can_stream_ollama=False`; all local routes go to llamacpp
- **Auto-routing:** `task_type=tool_call` → xlam; `task_type=agentic` → hermes4/qwen3
- **Metrics:** all registry-routed inferences persisted to `guppy_main.db` → `inference_metrics` table

---

## Voice System

- **STT chain:** faster-whisper → Google SpeechRecognition → SAPI
- **TTS chain:** kokoro → ElevenLabs → Windows SAPI PowerShell
- **Wake word:** openwakeword (`GUPPY_OWW_MODEL`) or transcription-loop fallback
- **Modes:** push-to-talk, hold-to-talk, wake-word continuous

---

## Background Services (started at boot)

- **Triage watchdog** — polls `src/guppy/` + `tools/` every 5s (60s debounce), auto-triggers dev-check on changes
- **Screen monitor** — 30-min snapshot cycle, AI summaries via dispatch/hermes3
- **llamacpp dispatch** — auto-starts at boot (5s delay), port 8085

---

## Memory System

- **SQLite:** facts, contacts, tasks, pipeline/CRM, session summaries, conversation history (`guppy_main.db`)
- **Semantic:** ChromaDB or SQLite + `nomic-embed-text` via dedicated llamacpp embed server (port 8092); graceful lexical fallback when offline
- **`promote_durable_chat_memory()`** — extracts preferences, identity, decisions, scope
- **`get_startup_context()`** — briefing injected at conversation start

---

## Live Dependency Flow

```
entrypoint wrappers
  → src/guppy/apps/ (composition roots)
  → launcher/application services
  → domain services (api/, inference/, codespace/, voice/, memory/)
  → persistence/adapters (SQLite, ChromaDB, external APIs)
```

**Guard:** `src/guppy/apps/launcher_app.py` is the only composition root allowed to import `ui.launcher`. All UI logic lives in `web/` (React). The `ui/` Qt layer is wrapper-only.

---

## Seam Modules (active)

Under `src/guppy/launcher_application/` and `src/guppy/workspace_governance/` — typed contracts for launcher state, connector inventory, workspace governance, and runtime readiness. These are the boundary between Qt launcher shell and the backend domain.

---

## Documentation Contract

1. `CLAUDE.md` — module locations, routes, patterns. Update after every architectural change.
2. `docs/MASTER_PHASE_PLAN.md` — surface roadmap, phase history.
3. `docs/PROJECT_BRIEF.md` — active status and handoff source.
4. `docs/GUPPY_PRODUCT_NORTH_STAR.md` — product vision and surface definitions.
5. `docs/archive/` — historical only. Do not treat as active architecture source.
