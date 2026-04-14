# M2 UI Quick Reference Card

**One-Pager Guide to New Tab Structure & Architecture**

---

## 🏠 Tab Structure (Left to Right)

```
┌─────────────────────────────────────────────────────────────┐
│ Home │ Instance Manager │ Agent Tools │ App Mgmt │ Settings │ Models │ Voices │
└─────────────────────────────────────────────────────────────┘
   ▲
   Primary Product Interface (70%+ screen focus)
```

---

## 📋 Tab Purposes

| Tab | Purpose | Key Feature | Who Uses |
|---|---|---|---|
| **Home** | Active instance chat | Large transcript + quick instance switcher in header | Everyone on every session |
| **Inst. Manager** | Create/switch/delete instances + view logs | Live today: list, inline create or update form, switch, delete, log viewer | Power users, setup |
| **Agent Tools** | Tools the instance can use | Capability-aware tool catalog for the active instance, with blocked tools called out explicitly | Active user (via Home tab) |
| **App Mgmt** | Manage the app itself | Recovery cards, diagnostics snapshot, and operator logs live in one app-scoped surface | Operators, troubleshooters |
| **Settings** | Persona configuration | Tone/verbosity sliders, teaching style, preview | Casual + power users |
| **Models** | Model assignment + routes | Task type → model mapping, fallback chains | Power users, setup |
| **Voices** | Voice library | Import, assign, preview playback | Voice enthusiasts |

---

## 🎯 Product Positioning

```
Home Tab (Primary, current repo state)
└─ Instance → Guppy (active)
   ├─ Chat transcript
   ├─ Active instance chip
   ├─ Background activity + recovery summary
   └─ Runtime facts: profile, model, voice, latency, last query

Background Instances (Managed from Instance Manager)
├─ Builder (running): merlin-code, Schema writing
├─ Merlin (idle): Available as collaborator
└─ Additional instances (configured): idle until activated
```

**User Workflow:**
1. Open app → Home tab, Guppy active, chat ready
2. Need specialized work → Switch instance (instance switcher in Home header) OR
   Open Instance Manager tab for full control
3. Use tools → Agent Tools tab (tools for YOUR instance)
4. Troubleshoot app → App Mgmt tab (app-level operations)

**M2.0 Limit:** one foreground instance + one background collaborator, with one inter-instance query in flight.

---

## 🔄 Instance Switching (Two Methods)

### Fast Method (In Home Tab)
```
┌────────────────────────────────────────┐
│ [Instance: Guppy ▼]                    │
│ Favorites: │ Guppy □ Builder □ Merlin│
└────────────────────────────────────────┘
```

### Full Control (Instance Manager Tab)
```
Instance Manager
┌──────────────────────┬──────────────────┐
│ Name      │ Status   │ Actions          │
├──────────────────────┼──────────────────┤
│ Guppy     │ Active   │ [Logs] [Delete]  │
│ Builder   │ Running  │ [Logs] [Pause]   │
│ Merlin    │ Idle     │ [Logs] [Delete]  │
└──────────────────────┴──────────────────┘
[Inline Create or Update Form]
```

---

## 🛠️ Tools: Agent vs App Management

### Agent Tools Tab
**Tools the active INSTANCE can use:**
- `run_python` — Execute Python code
- `read_file` — Read files on disk
- `write_file` — Write to approved directories
- `query_instance` — Ask another instance (inter-agent query)
- `screenshot` — Capture screen
- (Tools filtered by instance permissions and enforced server-side)

### App Management Tab
**Tools to MANAGE the app:**
- Warmup — Refresh all model caches
- Restart Daemon — Hard reset processes
- Audit Runtime — Check logs & schemas
- Diagnostics — System health snapshot

**Current State:** the content split is now live at a first useful pass. Agent Tools is instance-scoped and capability-aware; App Mgmt owns warmup, restart, audit, diagnostics, and operator logs. Remaining work is deeper tool invocation flow plus server-side capability enforcement.

---

## 📱 Instance Quick-Switcher Placement

```
Home Tab Header
─────────────────────────────────────────────────────
│ [Instance: Guppy ▼]  [→ Manager Tab]  [≡ Menu]   │
│                                                   │
│  [Chat Transcript Area — 70% of window height]   │
│                                                   │
│  [Input: Ask anything...           ] [Send]      │
─────────────────────────────────────────────────────
Status: Active | Model: Merlin | Voice: Kokoro
```

**Interaction:**
- Click `[Instance: Guppy ▼]` → Quick-switch to recent instances
- Click `[→ Manager Tab]` → Open Instance Manager for full control
- Home tab chat ALWAYS shows active instance

---

## 🔗 Inter-Agent Communication Pattern

User (in Guppy instance) asks:
> "Ask Merlin to write the test file"

What happens:
1. Guppy calls: `query_instance("Merlin", "Write a test file for parser.py")`
2. Background Merlin instance processes the request
3. Response appears in Guppy chat: "[From Merlin]: Here's the test file..."
4. Both instances append to their own logs (audit trail)

**Result:** Instances can collaborate without user context-switching.

---

## 💾 Instance Data Persistence

Each instance has:
- **Name** (Guppy, Builder, Merlin, etc.)
- **Model Assignment** (simple/complex/teaching/code tasks → which model)
- **Persona** (tone=0-10, verbosity=0-10, teaching_style)
- **Voice** (Kokoro, System TTS, custom)
- **Chat History** (JSONL log, append-only)
- **Status** (active/idle/running)
- **Type** (user_instance/builder_instance/read_only_instance)

Stored in:
- `config/instances.json` → Instance definitions (persisted)
- `runtime/instance_state.json` → Active instance + current states
- `runtime/logs/instance_{name}.jsonl` → Chat history per instance

Log policy:
- Raw logs retained 14 days
- Summary metadata retained 30 days
- Obvious secrets redacted before persistence/export

---

## ✅ Implementation Checklist (M2 Epics 0–6)

### Epic 0: Instance Manager + Multi-Instance
- [ ] Instance creation/deletion/switching UI
- [ ] Background instance logging (JSONL per instance)
- [ ] Instance state persistence (across restart)
- [ ] Inter-agent API endpoint: `/instances/{name}/query`
- [ ] Server-side capability enforcement for instance tools

### Epic 0.1: Home Tab Primary Interface
- [ ] Home tab takes ≥70% of window
- [ ] Quick-switcher in header
- [ ] Instance name indicator in status bar
- [ ] Chat history loads per-instance

### Epic 1: Persona Builder v1
- [ ] Tone/verbosity sliders
- [ ] Teaching style dropdown
- [ ] Live system prompt preview

### Epic 2: Model Assignment + Routes
- [ ] Task type → model dropdown
- [ ] Fallback chain editor
- [ ] Health badges

### Epic 3: Voice Library + Assignment
- [ ] Voice import (Kokoro + system TTS)
- [ ] Per-instance voice override
- [ ] Preview playback

### Epic 4: Agent Tools Tab
- [x] Tools list scoped to active instance
- [x] Permission-aware filtering (read-only instances, etc.)
- [ ] Tool card layout with Run buttons

### Epic 5: App Management Tab
- [x] Recovery action cards (warmup, restart, audit)
- [x] Diagnostics panel (system health)
- [x] Operator logs viewer (tail, filter)

### Epic 6: Off-Hours Scaling
- [ ] 5+ write task templates
- [ ] Dry-run staging works
- [ ] Approval workflow tested

---

## 🚀 Key Success Metrics (by Sep 30)

✅ Home tab is visually primary (≥70% screen on standard res)  
✅ Instance switching works (≥3 instances tested)  
✅ Background instances receive bounded synchronous queries reliably (95%+ success)  
✅ Tool separation clear (no "restart app" in Agent Tools tab)  
✅ Instance chat history persists across restart  
✅ Restricted tools are denied below the UI, not only hidden  
✅ No "not wired yet" tooltips anywhere  
✅ Every action shows outcome (no silent operations)  

---

## 📖 Related Documents

- **Deep dive:** [M2_ENGINEERING_PLAN.md](M2_ENGINEERING_PLAN.md) — 8 workstreams with acceptance criteria
- **Design spec:** [M2_UI_ARCHITECTURE_GUIDE.md](M2_UI_ARCHITECTURE_GUIDE.md) — Complete UI/UX reference
- **Scope lock:** [M2_SCOPE_LOCK.md](M2_SCOPE_LOCK.md) — Decisions, constraints, blockers
- **Launch plan:** [M2_LAUNCH_CHECKLIST.md](M2_LAUNCH_CHECKLIST.md) — 8-week ramp + go/no-go

---

**Print this page for quick reference during implementation.**
