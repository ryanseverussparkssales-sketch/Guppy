# M2 Scope Lock & Decision Framework

**Locked:** April 13, 2026  
**Valid Through:** June 15, 2026 (M2 Launch)  
**Amendment Process:** Steering committee approval required; no feature creep without gate

---

## 8 M2 Workstreams (LOCKED)

| Epic | Owner | Priority | Start | End | Acceptance |
|---|---|---|---|---|---|
| 0. Instance Manager + Multi-Instance | UI/Platform | Highest | Apr 15 | May 13 | Users create instances, switch between them, background instances receive queries |
| 0.1. Home Tab (Primary Interface) | UI | Highest | Apr 15 | May 13 | Home tab is primary focus; instance switching works; all chat in one place |
| 1. Persona Builder v1 | UI | High | Apr 22 | May 6 | Non-technical user defines persona without file editing |
| 2. Model Assignment + Routes | ModelOps | High | Apr 22 | May 13 | Every task type has visible route + fallback chain |
| 3. Voice Library + Assignment | Voice | High | Apr 29 | May 13 | User can assign voice globally, override per-agent |
| 4. Agent Tools Tab | Tools | High | May 6 | May 20 | Tools scoped to active instance; permissions-aware; no system-level tool confusion |
| 5. App Management Tab | Platform | Medium | May 13 | May 27 | Recovery flows, diagnostics, logs separate from agent operations |
| 6. Off-Hours Write Scaling | Runtime | Medium | May 13 | May 27 | 5â€“10 safe write tasks/week; <3 writes/run budget |

**All must complete by Sep 30, 2026 exit gate.**

(Note: Workstreams 0 and 0.1 are foundation layers that enable the others. See M2_ENGINEERING_PLAN.md for detailed breakdown.)

---

## MUST DELIVER (Non-Negotiable)

1. **Home Tab is the primary product interface**
   - Takes 70%+ of window real estate
   - Active instance chat history immediately visible
   - Instance switcher in header for quick navigation
   - If user doesn't see chat first, UI architecture failed

2. **Multi-instance support works reliably**
   - Create instance â†’ switch â†’ activate â†’ receive messages â†’ all chat persisted per instance
  - Background instances can receive bounded synchronous queries via API
   - If switching drops chat history or breaks background instance, architecture failed

3. **Agent Tools vs App Management clearly separated**
   - Agent Tools tab: only tools that the active instance can USE
   - App Management tab: only tools for managing the app itself (warmup, restart, audit)
   - If user can accidentally run a "restart app" from within agent tools, separation failed

4. **Every action shows outcome; no silent operations**
   - Create instance â†’ confirmation + list updates
   - Send query to background instance â†’ result appears in log
   - Run recovery action â†’ status appears in chat or diagnostics
   - If silent or "pending...", UX failed

5. **Instance-Aware Tool Permissions Are Enforced Server-Side**
  - Instance can be marked "write-prohibited" â†’ write tools disabled in Agent Tools tab and denied by API/tool runner
  - Instances can be marked "read-only" â†’ tool list reflects this and denied operations return authorization errors
  - If a direct tool/API call can bypass restrictions, permissions failed

6. **Instance Logs Have Redaction and Retention Controls**
  - Raw per-instance logs redact obvious secrets before persistence/export
  - Retention: 14-day raw log window, 30-day summary/metadata window
  - Export warns operators that logs may still contain sensitive business context

7. **Off-hours writes are safe by default**
   - Dry-run staging to `runtime/offhours_results/dry_run/`
   - Human approval required before writing
   - Path validation against whitelist (src/, tests/, docs/, config/ only)
   - If task writes to root or outside workspace, REJECT

---

## OPTIONAL (May defer to M2.2 if time pressure)

| Feature | If Skipping | Mitigation |
|---|---|---|
| Instance Drag-to-Reorder | Omit visual reordering; keep list-based only | Add TODO; plan for M2.2 |
| Instance Queuing/Scheduling | Omit auto-queue feature; manual instance creation only | Document manual workflow; plan for M2.2 |
| Route Visualizer (flowchart) | Omit 2-week spike; keep click-to-assign only | Add TODO comment; plan for M2.2 |
| ElevenLabs Voice Support | Lock to Kokoro + system TTS only | Document optional support for future |
| Auto-Apply Write Tasks | Require approval for all; no auto-apply | Document auto-apply for M2.2 |

---

## STRICTLY OUT OF SCOPE (M3 or Later)

| Item | Why Deferred | Target Milestone |
|---|---|---|
| iOS client | Platform complexity; test on Windows first | M3 or post-launch |
| Live CRM writes (Salesforce, HubSpot) | Integration testing nightmare; skip MVP | M3 or post-launch |
| Shared Memory v1 (Qdrant RAG) | Storage scaling unknown; skip for pilot | M3 or post-launch |
| CI/CD deploy gates (GitHub Actions) | Adds test infrastructure burden | M3 or post-launch |

**Any request for these items must include: business justification, timeline impact, risk analysis, and steering committee sign-off.**

---

## Key Architecture Constraints

### UI Layer
- **Home Tab is primary (70%+ visual focus)**
  - Instance chat history immediately visible
  - Instance switcher in header
  - Tool invocation targeted to active instance only
  - Standing document: [ui/launcher/DESIGN.md](../ui/launcher/DESIGN.md)
  - Test: Home tab takes >70% window height on 1920x1080 resolution

- **Instance Manager is supporting surface**
  - Create, list, switch, delete, view logs
  - Not cluttered with frequent operations
  - Power users navigate here for management
  - Casual users stay in Home tab

- **Transient state lives in status strip, not chat bubbles**
  - "Processing..." â†’ `assistant_view.set_status()`
  - Not â†’ `add_system_message()`
  - Standing document: [memory/repo/ui-streaming-convention.md](/memories/repo/ui-streaming-convention.md)

### Multi-Instance Architecture
- **Chat history stored per-instance**
  - Switching instances must restore full chat history
  - No chat pollution between instances
  - Instance definitions live in `config/instances.json`; runtime state lives in `runtime/instance_state.json`
  - Query per instance in API: `GET /instances` â†’ list all

- **Background instances remain responsive**
  - Endpoint: `POST /instances/{name}/query` â†’ bounded synchronous request in M2.0
  - At most 1 inter-instance query may be in flight at a time
  - Response includes token_count, model_used, duration_ms, source_instance, and status (`ok|busy|timeout`)

- **Inter-agent communication is explicit**
  - Instances can call other instances via tool (e.g., `query_instance(name, message)`)
  - Prevents accidental API loops (rate-limit querying)
  - Response includes source instance name (audit trail)

### Tools & API
- **Agent Tools vs App Management Tools (Strict Boundary)**
  - Agent Tools: run_python, read_file, write_file, query_instance, etc.
  - App Management: warmup, restart-daemon, audit-runtime
  - Tool list filtered per-instance type and enforced by API/tool runner below the UI
  - Permission schema: `config/tool_permissions.json`

- **Restricted capabilities are enforced server-side**
  - UI hiding/disablement is convenience only
  - API and tool runner must validate active instance capability before execution
  - Authorization failures are logged with reason and surfaced to the transcript/status area

- **Off-hours write budget: max 3 files/run**
  - Hard cap in `tools/idle_agent_worker.py`
  - Exceeding budget auto-downgrades to dry-run
  - No override flag

- **Path validation mandatory for all writes**
  - Whitelist: `src/`, `tests/`, `docs/`, `config/` only
  - Blacklist: root, `guppy_core/`, `ui/launcher/`
  - Function: `_safe_write_path()` in idle_agent_worker.py

### guppy_core Package
- **No breaking changes to tool_registry exports**
  - All 77 tools must remain importable
  - Standing document: [guppy_core/__init__.py](../guppy_core/__init__.py) line 1â€“25

- **No new top-level modules in guppy_core/**
  - Only add to existing 7: tool_metrics, system_prompt, tool_registry, tool_runner, debug_flags, beta_policy, network_utils
  - Amendment requires architecture review

---

## Decision Points with Recommendations

### Decision 1: Home Tab Priority (Primary vs Coequal)
**DECIDED:** Home Tab = primary product surface  
**Reasoning:** Users need to chat first; all other UX should support that  
**Constraint:** Must take 70%+ of window; all other tabs are secondary surfaces

### Decision 2: Multi-Instance MVP vs Single Instance
**DECIDED:** Bounded multi-instance from M2.0  
**Reasoning:** Needed for builder/background collaboration, but limited to 2 active instances and 1 in-flight inter-instance query for feasibility  
**Revisit in:** M2.2 if telemetry shows headroom for broader concurrency

### Decision 3: Instance Context Switching Location
**DECIDED:** Quick switcher in Home Tab header + Full manager in Instance Manager tab  
**Reasoning:** Power users get fast switcher; casual creation/management stays in separate tab  
**UX Impact:** Home tab stays uncluttered; Instance Manager is the "control center"

### Decision 4: Agent Tools vs App Management Tabs (Strict Boundary)
**DECIDED:** Two separate tabs with distinct purposes
- Agent Tools: tools that instances USE  
- App Management: tools for MANAGING the app itself
**Reasoning:** Reduces cognitive load; prevents accidental system operations; clearer permission model  
**Permission Model:** Write-prohibited instances see read-only tools only, and server-side execution checks enforce the same boundary

### Decision 5: Inter-Agent Query Contract
**DECIDED:** `POST /instances/{name}/query` is bounded synchronous in M2.0  
**Reasoning:** Clearer UI and lower operational complexity than queue orchestration in the first release  
**Constraint:** 5s timeout, 1 in-flight cross-instance query max, explicit `busy|timeout` status

### Decision 6: Drag-drop vs Click-to-Assign for Model Selection
**DECIDED:** Click-to-assign (MVP, simpler)  
**May revisit in:** M2.2 if UX feedback signals demand

### Decision 7: All voices or just Kokoro + System TTS?
**DECIDED:** Kokoro + System (Lock ElevenLabs to M2.2)  
**Reasoning:** Fewer API keys, less maintenance  
**Revisit in:** M2.2 after M2.0 stability + user demand signal

### Decision 8: Auto-apply off-hours tasks or always require approval?
**DECIDED:** Always require human approval in M2.0 (safe default)  
**Reasoning:** Safety-first; human review builds confidence  
**Revisit in:** M2.2 after 20+ successful approved tasks demonstrate reliability

---

## Blocking Dependencies (Must Exist by Jun 15)

| Dependency | Current Status | Owner | Due |
|---|---|---|---|
| `/status` API endpoint (model health) | âœ“ Exists in guppy_api.py | Platform | âœ“ Ready |
| Provider/model routes schema (`runtime/provider_registry.json`) | âœ“ Exists + validated | ModelOps | âœ“ Ready |
| Persona config schema (`runtime/persona_config.json`) | âœ“ Exists + validated | UI | âœ“ Ready |
| Voice bindings schema (`runtime/voice_bindings.json`) | âœ“ Exists | Voice | âœ“ Ready |
| Instance definition schema (`config/instances.json`) | Planned for M2.0 foundation | UI/Platform | May 1 |
| Tool permission schema (`config/tool_permissions.json`) | Planned for M2.0 foundation | Tools | May 1 |
| Server-side capability enforcement | Planned for M2.0 foundation | Platform | May 15 |
| Instance log retention/redaction policy | Planned for M2.0 foundation | Platform/Security | May 15 |
| Kokoro inference working | âœ“ Tested at baseline | Runtime | âœ“ Ready |
| Merlin-code model responsive | âœ“ Tested | Runtime | âœ“ Ready |
| System TTS fallback working | âœ“ Tested on Windows | Voice | âœ“ Ready |
| `apply_patch` tool ready | âœ“ In tool_registry + handler | Platform | âœ“ Ready |
| Off-hours worker task queue | âœ“ Exists; accepts write tasks | Runtime | âœ“ Ready |

**Not all dependencies are green yet. Instance schema, capability enforcement, and log safety controls are required before M2 launch.**

---

## Weekly Gate Reviews (Every Mon 10am)

Each week, review:
1. **Are we on schedule?** (Burndown vs plan)
2. **Have we discovered new risks?** (If yes, update Risk table)
3. **Do we need to defer any optional features?** (If yes, document + rescope)
4. **Are we violating any constraints?** (If yes, escalate immediately)

If > 2 gates fail, pause feature work and re-plan.

---

## Commit Protocol

Every M2 commit must include:
1. **Related epic** (e.g., `[Epic 1: Persona Builder]`)
2. **Acceptance criteria verified** (if applicable)
3. **Tests passing** (e.g., `70 tests passing`)
4. **No new lint errors** (linter clean)

Example:
```
[Epic 1: Persona Builder] Add tone slider + preview modal

- Slider events wired to live system prompt preview
- Preview modal shows how tone affects Merlin prompts
- Save button persists to runtime/persona_config.json
- Tests: form instantiation + slider responsive (2 new tests)
- Status: All 70 tests passing, no lint errors
```

---

## Escalation Path

**If you find a scope violation, blocker, or constraint conflict:**

1. **Email:** Attach evidence (test output, code snippet, decision doc reference)
2. **Cc:** Architecture + Product leads
3. **Subject:** `[M2 SCOPE ALERT] <title>`
4. **Include:**
   - What constraint was violated (reference this doc)
   - Why it happened
   - Proposed resolution (keep, defer, amend, exception)
   - Impact estimate (lines of code affected, days of delay)

**Expected response:** < 4 hours (working hours)

---

## Handoff to Next Phase (Oct 1)

On Sep 30, document:
1. **What shipped:** All 8 M2 workstreams summary
2. **What deferred:** Any M2.2 features + justification
3. **What broke:** Any technical debt or regressions
4. **What next:** Immediate M3 priorities

Store in: `M2_EXIT_REPORT.md`

---

## EOF â€” M2 SCOPE LOCKED

**Approved:** Architecture Review + Product Lead  
**Lock Date:** April 13, 2026  
**Breakpoints:** Weekly (every Mon); gate reviews (every Wed)  
**Escalation:** Email arch + product leads with `[M2 SCOPE ALERT]` tag

