# Guppy — Surface Architecture

**Last updated:** 2026-05-03

Three primary surfaces replace the legacy single `AssistantView`:

---

## 1. Companion (`/companion`)

**Purpose:** Personality-first voice/chat/vision interface. Always-on ambient presence.

**Backend routes:** `/api/companion/*`, `/api/chat/stream`, `/api/voices/*`

**Model:** Rocinante X 12B (port 8088) — personality-first, creative, tool-capable. Hermes 3 (port 8087) is the always-on watchdog fallback.

**Key features:**
- PersonalityPicker — 4 preset personalities; stored in `guppy_main.db.surface_config`
- Wake-word toggle — ambient always-listening mode
- Camera vision — frame capture → `/api/companion/vision`
- Ambient fullscreen mode — SSE alerts → TTS via sentence-boundary chunking
- `<tool_call>` two-pass parser — web_fetch / create_reminder / download_media / memory_write / memory_recall / workspace_task / get_time / list_workspace_tasks
- `workspace_task` tool — hands off long-running tasks to Workspace surface
- XML tool call normalization — handles `<name>/<arguments>` XML format from some models

**Chat delegation path:**
```
User voice/text → CompanionView → POST /api/chat/stream (surface=companion)
  → router_surface → Rocinante (8088) → Hermes3 fallback (8087)
  → tool_call parser → action executor or workspace_task spawn
```

---

## 2. Workspace (`/workspace`)

**Purpose:** 11-tab operations hub for power-user workflows.

**Backend routes:** `/api/workspace/*`, `/api/tasks/*`, `/api/calendar/*`, `/api/email/*`, `/api/media/*`, `/api/voip/*`, `/api/screen/*`, `/api/files/*`, `/api/system/*`

**Model:** Hermes 4 14B (port 8086) — deep reasoning, multi-step tool execution.

**Tabs:**
| Tab | Component | Backend |
|-----|-----------|---------|
| Chat | WorkspaceChatPanel | `/api/chat/stream` (surface=workspace) |
| Agents | AgentsPanel | `/api/workspace/tasks` SSE |
| CRM | CRMPanel | `/api/workspace/contacts`, `/api/workspace/tasks` |
| Screen | ScreenPanel | `/api/screenpipe/*`, `/api/screen/timeline` |
| Files | FilesPanel | `/api/files/*` |
| PC | SystemMetricsPanel + AutomationPanel | `/api/system/*` |
| Tasks | TaskManagerPanel | `/api/tasks/*` |
| Calls | VoIPPanel | `/api/voip/*` |
| Calendar | CalendarPanel | `/api/calendar/*` |
| Email | EmailPanel | `/api/email/*` |
| Media | MediaLibraryPanel | `/api/media/*` |

---

## 3. Codespace (`/codespace`)

**Purpose:** Developer surface — Docker sandbox, triage, self-improvement pipeline.

**Backend routes:** `/api/codespace/*`

**Model:** Hermes 4 14B (port 8086) — code analysis, fix proposals.

**Tabs:**
| Tab | Component | Backend |
|-----|-----------|---------|
| Chat | CodespaceChatPanel | `/api/chat/stream` (surface=codespace) |
| Sandbox | SandboxPanel | `/api/codespace/sandbox/*` — Docker lifecycle + SSE terminal |
| Triage | TriagePanel | `/api/codespace/triage/*` — dev-check history, AI fix proposals, diff viewer |

---

## Navigation

- Sidebar: Companion | Workspace | Codespace (primary tabs)
- Legacy routes (`/assistant`, `/launch-control`, `/agents`, `/instances`, `/models`) redirect to new surfaces
- Sidebar auto-collapses on all three primary surfaces

---

## Cross-Surface Communication

- **SSE event bus:** `GET /api/surface/events` — delivers surface state changes, task progress, background alerts
- **Task delegation:** Companion → `workspace_task` tool → `_spawn_task_direct()` in routes_surface → Workspace task queue
- **Background task loop:** asyncio 30-second tick delivers due reminders as SSE events; marks stale tasks after 6 hours
- **Watchdog:** daemon thread monitors ports 8085/8086/8087/8091/8092 every 60 s; auto-restarts crashed always-on models; re-warms KV cache after restart
