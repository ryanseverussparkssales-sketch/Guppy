# Guppy Product North Star

Last updated: 2026-04-29

## One-Sentence Thesis

Guppy is a local-first personal operations platform — voice-first, ambient, and persistent across every surface.

## Core Product Definition

Guppy is a three-surface personal AI platform for one person doing real work:

1. **Companion** — voice-first, personality-led, always present. Fast personal assistant with vision, wake word, and avatar presence.
2. **Workspace** — operational command center. Agents, CRM, calendar, email, screen history, files, VoIP, and tasks in one hub.
3. **Codespace** — the workshop. Docker sandboxes, self-triage, AI fix proposals, and self-improvement pipeline.

The core promise is:

`I can talk to Guppy, kick tasks to my Workspace, and everything stays in sync — locally, persistently, without fighting the interface.`

## What Guppy Must Feel Like

1. Always ready — voice wakes it, text reaches it, tasks queue to the right surface.
2. Ambient — Companion can announce Workspace activity without being opened.
3. Calm daily use — no dashboard clutter on the surfaces you use most.
4. Persistent — memory, task state, and chat history survive restarts.
5. Trustworthy — local inference by default, cloud when you want it, credentials stay on-machine.

## Primary Surfaces

These are the three primary surfaces, each with its own model affinity and tool access:

1. **Companion** (`/companion`) — chat, voice, vision, personality, avatar. Escalates tasks to Workspace.
2. **Workspace** (`/workspace`) — 11-tab hub: Chat | Agents | CRM | Screen | Files | PC | Tasks | Calls | Calendar | Email | Media.
3. **Codespace** (`/codespace`) — 3-tab: Chat | Sandbox (Docker) | Triage (self-improve + AI fix proposals).

Secondary surfaces (accessible from within any primary surface):
- `/personas` — personality presets and instructions
- `/tools` — tool registry, enable/disable
- `/instructions` — system prompt editor
- `/settings` — credentials, models, providers, appearance (themes)
- `/admin` — inference metrics dashboard, ops panel

## What Is Now In Scope (Updated 2026-04-29)

All of the following shipped in Phases 1–5 and are active production features:

- ✅ Ambient wake mode — Companion speaks Workspace alerts with TTS when idle
- ✅ Self-improvement pipeline — AI proposes diffs, user applies or rejects, dev-check validates
- ✅ Docker sandbox execution — per-project containers, SSE terminal, lifecycle management
- ✅ Self-triage watchdog — monitors src/guppy/, auto-triggers dev-check on changes
- ✅ VoIP call log — SQLite-backed, Twilio webhook stub, live call placement via REST API
- ✅ Gmail sync — live via google-api-python-client
- ✅ Google Calendar sync — live, local CRUD + 90-day Google sync
- ✅ CRM live writes — HubSpot, Salesforce, GoHighLevel, Zoho via REST API
- ✅ Inference metrics — persisted to guppy_main.db, visible in AdminPanel dashboard
- ✅ Themes — Atoll Editorial (default), Dark, Liber Designatum (occult), Fear & Loathing (gonzo), Creem × Rolling Stone (rock mag)
- ✅ MCP plugin manager — add/remove MCP servers, enable/disable, test connections
- ✅ Desktop control API — pyautogui-backed screenshot, click, type, drag, scroll

## Decision Rule

When there is tension between power and clarity:

1. Keep the daily path smooth (Companion first, Workspace for operations, Codespace for code).
2. Hide diagnostics and power controls behind secondary nav.
3. Add surface capability only when it doesn't clutter the primary view of that surface.
4. Local inference is the default — cloud is opt-in per surface.

## V1 Is Real When

1. Companion responds in under 2 seconds on local hardware.
2. A task escalated from Companion appears in Workspace agents panel with live output.
3. Calendar, email, and CRM show real data after one-time credential setup.
4. Codespace proposes and applies its own fixes, validated by dev-check.
5. The user can theme, voice-configure, and credential everything from within the app.
6. Inference metrics show accurate per-provider cost and latency in AdminPanel.
