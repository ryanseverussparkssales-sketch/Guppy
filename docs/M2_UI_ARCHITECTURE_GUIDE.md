# M2 UI Architecture Refinement

**Updated:** April 13, 2026  
**Status:** 🟢 **LOCKED** — Approved for M2 implementation

---

## Executive Summary

The M2 UI has been redesigned to position **conversation as the primary product** while enabling sophisticated background instance management and separation of concerns between user-facing tools and app-management operations.

**Three Major Changes:**
1. **Home Tab = Primary Surface** (70%+ screen focus) — active instance chat
2. **Multi-Instance Architecture** — one primary active instance plus one background collaborator in M2.0, with inter-agent communication
3. **Tool Separation** — Agent Tools (for instances) vs App Management (for app operations)

---

## M2.0 Operating Envelope

To preserve fast first response on local Windows hardware, M2.0 intentionally limits concurrency:

1. Up to 5 configured instances may exist.
2. Up to 2 instances may be active simultaneously.
3. Only 1 inter-instance query may be in flight at a time.
4. `POST /instances/{name}/query` is synchronous with a 5s timeout in M2.0.
5. Queue-based background orchestration is deferred to M2.2.

---

## New Tab Structure

### Tabs in Order (Left to Right in UI)

| Tab | Purpose | Visibility | Content |
|---|---|---|---|
| **Home** | Active instance chat | Always visible | Large chat transcript + input |
| **Instance Manager** | Background instance control | Always visible | List of instances, create/delete/logs, switch, drag-reorder |
| **Agent Tools** | Tools for active instance | Always visible | Run_python, read_file, write_file, query_instance (instance-aware permissions) |
| **App Management** | App-level operations | Always visible | Warmup, restart, audit, diagnostics, logs |
| **Settings** | Persona configuration | Always visible | Tone/verbosity sliders, teaching style, preview |
| **Models** | Model assignment | Always visible | Task type routes, fallback chains, health badges |
| **Voices** | Voice library | Always visible | Import, assignment, preview playback |

**Removed Tab:** Advanced (merged to App Management)

---

## UI Layout & Real Estate

### Home Tab (Primary)
```
[Instance: Guppy ▼] [Switch ▼]
────────────────────────────────────────────────────────  70% height
│                                                         │
│  [User Message]                                         │
│  > [Assistant Response]                                 │
│  > [Assistant Response]                                 │
│                                                         │
│  [Input: Ask anything...                         ]      │
│  [Send]                                                 │
────────────────────────────────────────────────────────
Status: Active (Guppy) | Model: Merlin | Voice: Kokoro
```

### Instance Manager Tab (Supporting)
```
Instances (List View)
┌─────────────────────────────────────┬─────────────────┐
│ Name      │ Status   │ Last Message │ Actions        │
├─────────────────────────────────────┼─────────────────┤
│ Guppy     │ Active   │ "Sure, I'll..." │ [Switch] ... │
│ Builder   │ Running  │ "Schema saved"  │ [Logs] ...   │
│ Merlin    │ Idle     │ "Ready"         │ [Delete] ... │
└─────────────────────────────────────┴─────────────────┘
[Create New Instance]
```

### Agent Tools Tab (Supporting)
```
Agent Tools for: [Guppy ▼]

[Search: find a tool...]  [All ▼] [Read-Only] [Write] [Query]

┌──────────────┬──────────────┬──────────────┐
│ run_python   │ read_file    │ write_file   │
│ ✓ Ready      │ ✓ Ready      │ ✓ Ready      │
│ Execute code │ Read text    │ Write text   │
│ [Run]        │ [Run]        │ [Run]        │
└──────────────┴──────────────┴──────────────┘

┌──────────────┬──────────────┬──────────────┐
│ query_instance│screenshot   │write_json    │
│ ✓ Ready      │ ✓ Ready      │ ✓ Ready      │
│ Query other  │ Screen cap   │ Write JSON   │
│ instances    │ [Run]        │ [Run]        │
└──────────────┴──────────────┴──────────────┘
```

### App Management Tab (Supporting)
```
Recovery Actions
┌──────────────────────────────┐
│ [Warmup]                     │
│ Refresh model cache          │
│ [Execute]                    │
└──────────────────────────────┘

System Health
├─ Status: Healthy
├─ Models Loaded: 5/5
├─ Instances Running: 2
└─ Uptime: 14:23

Recent Events (Last 5)
├─ 14:22 Model warmup complete
├─ 14:20 Instance 'Builder' created
├─ 14:18 Model 'merlin' loaded
├─ 14:15 Launcher started
└─ 14:10 API health check OK
```

---

## Key Architectural Decisions

### 1. Home Tab as Primary Surface (70%+ Real Estate)
**Why:** Users need to chat first. Everything else is configuration/management.  
**Constraint:** Home tab MUST occupy ≥70% of window height on 1920x1080 resolution.  
**Impact:** Other tabs anchored below or to the right; never compete for space with chat.

### 2. Multi-Instance Architecture (Not Single)
**Why:** Killer feature enables:
- Run Builder in background while chatting to Guppy
- Agents speaking to each other (inter-agent queries)
- Multiple personas/models available without leaving the main conversation surface
- Controlled background collaboration without overcommitting local resources

**API Support:**
```
POST /instances/{name}/query
{
  "message": "Summarize the main points",
  "system_prompt": "You are a summarizer"
}
→ { "response": "...", "tokens_used": 42, "model": "merlin", "source_instance": "builder", "status": "ok|busy|timeout" }
```

**Instance Context:** Each instance has:
- Model assignment (simple/complex/teaching/code)
- Persona override (tone, verbosity, teaching style)
- Voice override (Kokoro/system TTS/custom)
- Chat history (JSONL append-only log per instance)
- Status (active/idle/running)

### 3. Tool Separation: Agent Tools vs App Management
**Why:** Reduces cognitive load and prevents misuse.

**Agent Tools Tab (For Instances):**
- run_python, read_file, write_file
- query_instance (speak to other instances)
- screenshot, debug_console
- State: Instance-aware permissions in the UI, enforced again in API/tool runner

**App Management Tab (For App):**
- Warmup (refresh all model caches)
- Restart Daemon (hard reset background processes)
- Audit Runtime (check logs, validate schemas, health snapshot)
- Diagnostics (system health, events, uptime)

**Clear Boundary:** User cannot accidentally run "restart" from within Agent Tools; it's in a different tab with a different visual context.

### 4. Instance Quick-Switcher in Home Header
**Why:** Power users need fast access; casual users don't.

**UI Pattern:**
```
[Instance: Guppy ▼] [Switch to Instance Manager ▼]
```

Dropdown on left shows favorites/recent instances; Switch button opens full Instance Manager tab.

### 5. Instance Permissions System
**Why:** Safety & clarity. Some instances should be read-only.

**Instance Types:**
- `user_instance`: Full read/write access (default)
- `admin_instance`: Full access + system tools (if any)
- `read_only_instance`: Read_file only, no writes
- `builder_instance`: Write access to config/, tests/, docs/ only

**Tool Filtering:** Agent Tools tab reflects active instance type.  
Example: If instance type is `read_only_instance`, write_file is hidden or disabled in the UI and denied server-side if invoked directly.

---

## Data Model: Instance State

### `config/instances.json` (Persistent)
```json
{
  "default_instance": "Guppy",
  "instances": [
    {
      "name": "Guppy",
      "model_routes": {
        "simple": "guppy",
        "complex": "merlin",
        "teaching": "merlin",
        "code": "merlin-code"
      },
      "persona": {
        "tone": 5,
        "verbosity": 7,
        "teaching_style": "Socratic"
      },
      "voice": "Kokoro",
      "type": "user_instance",
      "created_at": "2026-04-13T00:00:00Z"
    },
    {
      "name": "Builder",
      "model_routes": { "simple": "merlin-code", ... },
      "persona": { ... },
      "voice": "System TTS",
      "type": "builder_instance",
      "created_at": "2026-04-13T12:00:00Z"
    }
  ]
}
```

### `runtime/instance_state.json` (Runtime State)
```json
{
  "active_instance": "Guppy",
  "instances": {
    "Guppy": {
      "status": "active",
      "message_count": 47,
      "last_message": "2026-04-13T14:22:15Z",
      "model_currently_using": "merlin"
    },
    "Builder": {
      "status": "running",
      "message_count": 12,
      "last_message": "2026-04-13T14:20:33Z",
      "model_currently_using": "merlin-code"
    }
  }
}
```

### `runtime/logs/instance_{name}.jsonl` (Chat History Per Instance)
```jsonl
{"timestamp": "2026-04-13T14:22:00Z", "role": "user", "message": "Summarize the code"}
{"timestamp": "2026-04-13T14:22:05Z", "role": "assistant", "message": "This function...", "tokens": 42, "model": "merlin", "duration_ms": 1200}
{"timestamp": "2026-04-13T14:22:15Z", "role": "user", "message": "Any potential bugs?"}
```

**Log safety policy:** redact obvious secrets before persistence/export, retain raw logs for 14 days, retain summary metadata for 30 days.

---

## Inter-Agent Communication Pattern

### Use Case: Query Another Instance
```
User: "Ask Guppy to summarize the API docs"

→ active instance (Merlin) invokes tool: query_instance("Guppy", "Summarize the API docs")

guppy_api.py endpoint: POST /instances/Guppy/query
Payload: { "message": "Summarize the API docs" }

→ Background Guppy instance processes message immediately if idle

← Response: { "response": "The API...", "tokens_used": 78, "model": "guppy", "duration_ms": 2100, "source_instance": "Guppy", "status": "ok" }

→ Result appears in active instance chat: "[From Guppy]: The API..."
```

**Audit Trail:** Each response includes source instance name so user knows which instance answered. If the target is already busy, the caller receives `status=busy` instead of an implicit queue.

---

## Implementation Roadmap (M2)

### Week 1: Instance Manager Foundation (Apr 15–19)
- [ ] Implement instance state tracker (config/instances.json + runtime/instance_state.json)
- [ ] Build Instance Manager UI mockup
- [ ] Wire instance creation/deletion
- [ ] Test with 2 instances

### Week 2: Home Tab Primary + Switching (Apr 22–26)
- [ ] Refresh Home tab layout (70% height)
- [ ] Implement instance quick-switcher in header
- [ ] Wire chat history loading per instance
- [ ] Test switching between 3 instances

### Week 3: Agent Tools Separation (Apr 29–May 3)
- [ ] Extract tool list from existing Tools tab
- [ ] Implement permissions system (instance type → tool visibility)
- [ ] Create Agent Tools tab layout
- [ ] Create App Management tab layout

### Week 4: API & Multi-Instance Support (May 6–10)
- [ ] Add `/instances/{name}/query` endpoint
- [ ] Implement bounded synchronous cross-instance execution with busy/timeout handling
- [ ] Add instance logging (JSONL per instance)
- [ ] Test inter-agent query (Merlin → Guppy → Merlin)

### Week 5: Integration & Polish (May 13–17)
- [ ] Instance-aware persona/model/voice config
- [ ] Drag-to-reorder instances (optional)
- [ ] Instance deletion with confirmation
- [ ] View instance logs from UI

### Week 6–8: Refinement + Other Epics (May 20–Jun 14)
- [ ] Builder background support (Epic 1)
- [ ] Model assignment (Epic 2)
- [ ] Voice assignment (Epic 3)
- [ ] Full UAT + edge cases

---

## Success Criteria (Sep 30)

- [ ] Home tab takes ≥70% of window on standard resolution
- [ ] User can create, switch, delete instances without JSON editing
- [ ] Background instances receive and process bounded synchronous messages reliably
- [ ] Inter-agent queries work end-to-end (5+ successful test cases)
- [ ] Tool permissions work end-to-end (read-only instance cannot execute restricted tools via UI or direct invocation)
- [ ] Instance chat history persists across restart
- [ ] Instance logs viewable from UI (last 50 messages)
- [ ] No "not wired yet" tooltips in any tab
- [ ] Every action shows outcome (no silent operations)

---

## File Structure (New/Modified)

**New Files:**
- `ui/launcher/views/instance_manager_view.py` — Instance Manager UI
- `ui/launcher/components/instance_editor_modal.py` — Create instance form
- `ui/launcher/views/agent_tools_view.py` — Agent Tools tab
- `ui/launcher/views/app_management_view.py` — App Management tab (formerly Advanced)
- `utils/instance_logger.py` — Per-instance chat logging
- `config/instances.json` — Instance definitions
- `config/tool_permissions.json` — Tool permission matrix

**Modified Files:**
- `ui/launcher/launcher_window.py` — Tab reorganization, instance switching
- `ui/launcher/views/assistant_view.py` — Home tab layout (70% focus)
- `guppy_api.py` — Add `/instances/{name}/query` endpoint
- `guppy_core/tool_registry.py` — Add `query_instance` tool
- `guppy_core/tool_runner.py` — Add per-instance capability enforcement for tool execution

**Removed:** (none, Advanced tab code→App Management, not deleted)

---

## Backward Compatibility

✅ **All existing single-instance chat flows work unchanged.**  
✅ **Existing tool invocations can be migrated incrementally by mapping default capability sets to the current single-instance flow.**  
✅ **API endpoints remain the same; new endpoints additive only.**

**Migration:** On first launch post-M2, launcher creates default instance `"Guppy"` with current model/persona/voice config. Existing chat history can be imported to that instance (optional).

---

## EOF — M2 UI ARCHITECTURE REFINED

**Decision Gate:** Locked Apr 13, 2026  
**Implementation Start:** Apr 15, 2026  
**Launch:** Jun 15, 2026
