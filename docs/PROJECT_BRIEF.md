# Guppy Project Brief

Last updated: 2026-05-04

## What Guppy Is

Guppy is a **local-first personal AI platform** — voice-first, ambient, and persistent. It runs on a single Windows machine with a large GPU, serving one user who needs real work done: operations, code, research, communication, and media.

**Product vision:** `docs/GUPPY_PRODUCT_NORTH_STAR.md`

---

## Current Architecture (Web-First, Three-Surface)

The desktop launcher (`launcher_app.py`) spawns a FastAPI server and opens a browser. All UI lives in the React web app served at `localhost:8081`. There is no Qt desktop UI.

### Three Primary Surfaces

| Surface | Route | Model | Purpose |
|---|---|---|---|
| **Companion** | `/companion` | Hermes 4.3 36B Heretic (port 8086) / Phi-4-mini fast path | Voice/chat/vision, personality, avatar |
| **Workspace** | `/workspace` | Hermes 4.3 36B Heretic (port 8086) | 11-tab operations hub |
| **Codespace** | `/codespace` | Hermes 4.3 36B Heretic (port 8086) | Docker sandbox, self-triage, AI fix proposals |

**Single-model consolidation (2026-05-03):** All three surfaces share one primary — Hermes 4.3 36B Heretic Q4_K_M at port 8086. Companion has a fast path: simple queries (≤12 words, no tool cues) route to Phi-4-mini first (~0.3s TTFT), falling through to the 36B if needed.

Secondary nav: `/settings`, `/tools`, `/voices`, `/personas`, `/library`, `/control`, `/admin`

### Backend

FastAPI (`src/guppy/api/server_runtime.py`) with 40+ route modules. All routes mount at `/api/*`. Key modules:

| Routes | Prefix | Purpose |
|---|---|---|
| `routes_conversations.py` | `/api/conversations/*` | Persistent sessions, SSE streaming, partner selection |
| `routes_realtime.py` | `/api/chat/*` | Legacy/direct chat + WebSocket |
| `routes_model_roles.py` | `/api/model-roles/*`, `/api/control/operator-settings` | Partner roles + operator config |
| `routes_control.py` | `/api/control/*` | Service/model lifecycle, logs, PC health |
| `routes_companion.py` | `/api/companion/*` | Personality, voice session, vision |
| `routes_workspace_data.py` | `/api/workspace/*` | CRM, contacts, pipeline proxy |
| `routes_surface.py` | `/api/surface/*` | SSE event bus, task spawn, surface config |
| `routes_codespace.py` | `/api/codespace/*` | Docker lifecycle, triage, self-improve |
| `routes_backends.py` | `/api/backends/*` | llamacpp backend management + watchdog |
| `routes_settings.py` | `/api/settings/*` | All settings |
| `routes_chat_history.py` | `/api/chat-history/*` | Conversation history |

### Always-On Model Stack (~25.3 GB VRAM)

| Role | Model | Port | VRAM |
|---|---|---|---|
| **Primary — all surfaces** | Hermes 4.3 36B Heretic Q4_K_M | 8086 | ~21.8 GB |
| Companion fast path / orchestrator | Phi-4-mini-instruct Q4_K_M | 8091 | ~2.5 GB |
| Semantic embedding | nomic-embed-text-v1.5 | 8092 | ~1 GB |
| On-demand fallback | Hermes 3 8B Lorablated Q8_0 | 8087 | ~9 GB (if 36B offline) |
| Vision (on-demand) | MiniCPM-o 4.5 Omni | 8084 | ~9 GB |

Launch: `C:\llama-cpp\warmup.bat` starts always-on stack (ports 8086, 8091, 8092).
Context: 49,152 tokens (`--ctx-size 49152`), `--parallel 2`, `--flash-attn on`.

Full model roster: `docs/MODEL_ROUTING.md`

### Database

Single SQLite at `guppy_main.db` (path via `src/guppy/paths.MAIN_DB_PATH`). All 40+ route modules converge on this file. WAL mode + busy_timeout + foreign_keys. Details: `docs/DATABASES.md`

---

## Active Status (2026-05-04)

### Shipped (Phases 1–6 + 8-improvement batch complete)
- ✅ Three-surface architecture — Companion / Workspace / Codespace
- ✅ Persistent sessions with auto-titling via dispatch model
- ✅ Conversation partner selection (Hermes4 / Phi-4-mini / Hermes3 / Pepe / MiniCPM)
- ✅ Operator settings (cloud paid/free toggle, partner selection)
- ✅ Surface-locked model routing + per-surface cloud fallback
- ✅ Two-pass tool-call execution (companion + workspace)
- ✅ Grammar-constrained tool calls (GBNF) + JSON repair
- ✅ Backend watchdog — auto-restart crashed always-on models
- ✅ KV cache warming on startup
- ✅ Chunked TTS streaming + SSE exponential backoff
- ✅ Workspace 11-tab hub — Calendar, Email, Media, Tasks, VoIP, CRM, Screen, Files, PC, Agents, Chat
- ✅ Screenpipe integration — screen timeline, AI activity summaries
- ✅ Library surface — OPDS 1.2, OpenLibrary enricher, Calibre/Kindle
- ✅ DB consolidation — all routes on guppy_main.db
- ✅ Docker sandbox + SSE terminal + self-triage watchdog
- ✅ AI fix proposals — diff viewer, apply/reject, dev-check validation
- ✅ MCP plugin manager
- ✅ Desktop control API (pyautogui)
- ✅ PWA manifest + streaming + security hardening
- ✅ Control panel — service/model lifecycle, logs viewer, PC health
- ✅ **Single-model consolidation** — Hermes 4.3 36B Heretic replaces Rocinante + Hermes4 14B; 49K context
- ✅ **Companion fast path** — simple queries route to Phi-4-mini (~0.3s TTFT) with fallthrough to 36B
- ✅ **Kokoro ONNX TTS** — three-tier: HTTP API → local ONNX (HF cache auto-discovery) → KPipeline
- ✅ **Anthropic prompt caching** — `cache_control: ephemeral` on system blocks; ~80% cost reduction
- ✅ **System prompt TTL cache** — 60s in-memory LRU; bypasses full injection pipeline on cache hit
- ✅ **Structured memory categories** — `MEMORY_CATEGORIES` frozenset + `normalize_category()` + typed fact slots
- ✅ **Proactive companion nudge** — calendar-event SSE alerts voiced by TTS in ambient mode
- ✅ **MiniCPM-o vision endpoint** — `/api/companion/vision` auto-starts model, streams multimodal response

### In Progress / Next
- Wake word production (pvporcupine needs access key + .ppn files)
- True microphone streaming (sounddevice/pyaudio wiring)
- Local LLM benchmark harness (spec: `docs/LOCAL_LLM_BENCHMARK_SPEC.md`)
- TASKS.md for full queue

---

## Dev Commands

```powershell
python tools/dev_workflow.py dev-check --guard-scope delta   # pre-commit check
python tools/dev_workflow.py test-fast                        # unit tests
python tools/dev_workflow.py test-default                     # unit + integration
```

Full dev guide: `docs/DAILY_WORKFLOW.md`
Getting started: `docs/GETTING_STARTED.md`
