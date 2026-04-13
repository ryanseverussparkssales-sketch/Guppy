# M2 Engineering Plan

**Milestone:** Functional Parity for Builder and Tooling  
**Target Date:** September 30, 2026  
**Prep Window:** April 15 — June 14, 2026 (2 months to ramp)  
**Active Development:** June 15 — September 30 (3.5 months)

---

## Product Positioning: Primary vs Supporting Surfaces

**Primary Surface (Home Tab):** Active instance chat interface — the main product offering where users chat with their selected models and personas

**Supporting Surfaces:** 
- Instance Manager: Background instances, logs, instance creation/switching, inter-agent communication
- Agent Tools: Tools available within active instance (read/write/execute for the running agent)
- App Management: App-level operations (warmup, restart, audit, process guards)
- Settings/Models/Voices: Configuration persistence

This separation allows users to:
1. Chat with one instance while others run in background
2. Monitor background instance logs and status
3. Enable agent-to-agent communication (instances can query each other)
4. Run Builder in background while chatting to primary instance

---

## M2.0 Operating Limits

To keep M2 feasible on a Windows local-first machine, multi-instance support is intentionally bounded:

1. Up to 5 configured instances may exist in `config/instances.json`.
2. Up to 2 instances may be active at once in M2.0: one foreground chat instance and one background worker/collaborator.
3. Only 1 inter-instance query may be in flight at a time.
4. `POST /instances/{name}/query` is a synchronous, bounded request in M2.0 with a 5s timeout.
5. If the target instance is busy, the API returns a busy/timeout response; implicit queueing is deferred to M2.2.

---

## EPIC 0: Instance Manager + Multi-Instance Architecture

**Scope:** Users can create, manage, switch between, and monitor multiple instances; instances can run in background and communicate with each other

### Deliverables

1. **Instance Manager Tab** (`ui/launcher/views/instance_manager_view.py`)
   - List of available instances: name | status (active | idle | running) | last message
   - Action buttons: Create New | Switch | View Logs | Delete | Duplicate
   - Drag-to-reorder (optional; defer if time tight)
   - Double-click to activate instance → switch home tab to that instance
   - **Lines of code est.:** ~500

2. **Instance Creation Modal** (`ui/launcher/components/instance_editor_modal.py`)
   - Form fields: instance name | model assignment (simple/complex/code/vault) | persona override | voice override
   - "Create with defaults" quick button
   - "Advanced" expandable section (timeout, max_tokens, temperature)
   - Save → writes to `config/instances.json`
   - **Lines of code est.:** ~300

3. **Instance State Tracker** (extend `runtime/instance_state.json`)
   - Track per-instance: name, model routes, persona, voice, status, last_message, created_at, message_count
   - Support up to 2 active runtime instances and 5 configured instances in memory
   - Save/load on startup
   - **Lines of code est.:** ~150

4. **Background Instance Logger** (`utils/instance_logger.py`)
   - Append-only log per instance: `runtime/logs/instance_{name}.jsonl`
   - Each entry: timestamp | user_msg | assistant_response | tokens_used | model_used | duration_ms
   - Accessible from Instance Manager "View Logs" button
   - **Lines of code est.:** ~200

5. **Inter-Agent Communication Bridge** (extend `guppy_api.py`)
   - New endpoint: `POST /instances/{name}/query` → send message to background instance
   - Synchronous bounded contract in M2.0: returns completed response or busy/timeout within 5s
   - Response schema: `{ "response": "...", "tokens_used": 42, "model": "merlin", "source_instance": "guppy", "status": "ok|busy|timeout" }`
   - Instances can invoke other instances via tool call (e.g., "ask Guppy to summarize")
   - **Lines of code est.:** ~300

6. **Active Instance Indicator** (launcher_window.py)
   - Status bar shows: "Active: [instance_name]"
   - Clicking switches to Instance Manager
   - Visual cue (icon or highlight) in tab bar
   - **Lines of code est.:** ~100

7. **Capability Enforcement Layer** (extend `guppy_core/tool_runner.py` and API dispatch)
   - Enforce per-instance tool permissions server-side, not only in the UI
   - Instance capability lookup sourced from `config/tool_permissions.json` + instance type
   - Denied tool calls return structured authorization errors for transcript/log visibility
   - **Lines of code est.:** ~220

8. **Instance Log Safety Policy**
   - Redact obvious secrets/tokens before writing instance logs
   - Retain full logs for 14 days, summaries/metadata for 30 days
   - Add export warning banner before raw log download
   - **Lines of code est.:** ~120

**Acceptance Criteria:**
- [ ] User can create new instance with form (no JSON editing)
- [ ] Switching instances swaps home tab chat history
- [ ] Background instances can receive messages via API
- [ ] Background instance logs are readable from UI
- [ ] Instances can send message to other instances (Q&A use case)
- [ ] Instance list persists across restart
- [ ] Supports at least 5 configured instances, 2 active runtime instances, and 1 inter-instance query in flight
- [ ] Tool permissions are enforced below the UI (API/tool runner), not only by tab filtering
- [ ] Instance logs apply redaction and retention policy before export

### Dependencies
- [ ] Instance state schema defined (`config/instances.json`)
- [ ] API routing supports multiple instance contexts
- [ ] Chat history stored per-instance

### Risk: High
- Complex state management (active vs background, switching context)
- Cross-instance permission enforcement and sync timeout behavior
- Mitigation: Start with 2-instance MVP, 1 in-flight query limit, and explicit busy/timeout semantics

---

## EPIC 0.1: Home Tab (Main Product Interface)

**Scope:** Primary chat interface for active instance; position as the main product offering

### Deliverables

1. **Assistant Home Tab** (enhance existing `ui/launcher/views/assistant_view.py`)
   - Large chat transcript (primary focus)
   - Action prompt at bottom: "Select tools below, then ask..."
   - Status strip: Active instance name | model being used | voice status
   - Instance indicator in top-left (clickable → switch instance)
   - **Lines of code est.:** ~200

2. **Quick Model Selection** (in home tab header)
   - Dropdown: "Model: [Merlin ▼]"
   - Shows quick-pick favorite models
   - Falls back to selected instance model if none chosen
   - **Lines of code est.:** ~100

3. **Auto-Switch UI Elements for Instance**
   - Agent Tools tab becomes dependent on active instance's permissions
   - Status strip updates when instance switches
   - Persona preview updated for active instance persona (if overridden)
   - Voice indicator shows active instance voice (if overridden)
   - **Lines of code est.:** ~150

**Acceptance Criteria:**
- [ ] Home tab is visually prominent (takes 70%+ of window)
- [ ] Chat history is large and readable
- [ ] Instance indicator visible and clickable
- [ ] Model selector works; falls back gracefully
- [ ] Persona/voice display matches active instance
- [ ] No visual clutter from background instances

### Dependencies
- [ ] Instance state tracking (Epic 0)
- [ ] Single instance chat flow working (current state)

### Risk: Low
- Mostly layout/UX refinement
- Mitigation: Use existing assistant_view.py; add components incrementally

---

## EPIC 1: Persona Builder v1

**Scope:** Non-technical users can define persona behavior without JSON editing

### Deliverables

1. **Persona Form Widget** (`ui/launcher/components/persona_form.py`)
   - Tone slider (0–10): formal → conversational
   - Verbosity slider (0–10): terse → verbose
   - Teaching style dropdown: Socratic | Direct | Example-Driven | Coaching
   - Scope radio buttons: Global | Per-Model Override
   - Save button → writes to `runtime/persona_config.json`
   - Reset to Default button
   - **Lines of code est.:** ~400

2. **System Prompt Preview** (modal from form)
   - Live rendering of system message as user adjusts sliders
   - Shows impact on Merlin/Guppy instructions
   - Modal title: "SYSTEM PROMPT PREVIEW"
   - **Lines of code est.:** ~200

3. **Persona Config Loader** (extend `utils/personalization_config.py`)
   - Load personas from file
   - Merge global + per-model overrides
   - Validate against schema
   - Hot-reload on file change (optional for M2)
   - **Lines of code est.:** ~150

4. **Form Integration** (launcher_window.py)
   - Settings tab embeds persona form
   - Save flow: validate → write JSON → reload system prompt
   - Error handling (invalid slider pos, bad JSON write)
   - **Lines of code est.:** ~100

**Acceptance Criteria:**
- [ ] Non-technical user can open persona form
- [ ] Adjusting sliders updates preview in real-time
- [ ] Save persists to disk and reloads on restart
- [ ] Reset button returns to factory defaults
- [ ] Merlin teaching mode respects "Teaching Style" setting
- [ ] 0 "not wired yet" tooltips on persona form

### Dependencies
- None — standalone feature

### Risk: Medium
- PySide6 slider complexity, real-time preview rendering
- Mitigation: Use existing StatusPanel card patterns

---

## EPIC 2: Model Assignment + Route Visualizer

**Scope:** Users can see and edit model assignments for task types

### Deliverables

1. **Model Assignment Card** (`ui/launcher/components/model_assignment_card.py`)
   - List of task types (Simple | Complex | Teaching | Code | Vault)
   - For each: dropdown to select primary model
   - Secondary dropdown (fallback options)
   - Tertiary field (fallback override if provided)
   - Edit button → inline edit mode
   - Save → writes to `runtime/provider_registry.json`
   - **Lines of code est.:** ~500

2. **Health Status Badges** (extend existing badge renderer)
   - ✓ Ready (model responding <2s)
   - ⚠ Slow (model responding 2–10s)
   - ✗ Offline (model not responding)
   - Fetch from `/status` API endpoint
   - cache for 30s to avoid hammering
   - **Lines of code est.:** ~150

3. **Route Visualizer** (optional diagram)
   - Flow chart: task → router → model1 → model2 → model3
   - Show fallback chain visually
   - Clickable nodes → show system prompt for that model
   - **Lines of code est.:** ~300 (optional; defer if time tight)

4. **"Test Run" Button**
   - Send mock query to test route
   - Show latency, response preview
   - Reveal which model handled it
   - **Lines of code est.:** ~200

5. **Models Tab Integration** (`launcher_window.py`)
   - Embed card in Models tab
   - Load model routes on startup
   - Save/reload flow

**Acceptance Criteria:**
- [ ] User can see which model is assigned to each task type
- [ ] Fallback chains are visible and editable
- [ ] Health badges update periodically
- [ ] Test run works and shows response + latency
- [ ] Settings persist across restart
- [ ] All model assignments have an explicit strategy (no ambiguous routes)

### Dependencies
- [ ] `/status` API endpoint must return model health (EXISTING — check guppy_api.py)
- [ ] Provider/model routes schema defined (EXISTING — check runtime/provider_registry.json)

### Risk: Medium
- Complex widget state (edit mode vs view mode, unsaved changes)
- Mitigation: Use simple click-to-assign, no drag-drop for MVP

---

## EPIC 3: Voice Library + Assignment

**Scope:** Users can import voices and assign per-persona/per-model

### Deliverables

1. **Voice Import Flow** (`ui/launcher/components/voice_importer.py`)
   - Button: "Import Voice"
   - Modal: select engine (Kokoro | System TTS | ElevenLabs-optional)
   - For Kokoro: URL input to download model
   - For System: language/gender selection
   - For ElevenLabs: API key input, list available voices
   - Validate + save to `runtime/voice_bindings.json`
   - **Lines of code est.:** ~400

2. **Voice Assignment Form**
   - Global voice selector (default to Kokoro EN male)
   - Per-persona override (Merlin → ElevenLabs, etc.)
   - Per-model override (guppy-fast → system EN, guppy → Kokoro)
   - Preview button → speaker icon, play 3-second sample
   - **Lines of code est.:** ~300

3. **Voice Preview Widget**
   - Play sample text ("The AI assistant Guppy is ready to assist.")
   - Use Kokoro API by default, fallback to system TTS
   - Stop on new user input (interruption-safe)
   - Show playback state (playing | stopped | error)
   - **Lines of code est.:** ~250

4. **Voice Playback Integration** (extend `guppy_voice.py`)
   - Respect per-persona, per-model voice binding
   - Load voice config at startup
   - Route TTS calls to correct engine
   - **Lines of code est.:** ~100

5. **Voices Tab** (`launcher_window.py`)
   - Manage imports, assignment, preview
   - List currently available voices + their engine + status
   - Delete voice button (with confirmation)

**Acceptance Criteria:**
- [ ] User can import a voice from any supported engine
- [ ] Voice bindings persist across restart
- [ ] Preview works without blocking UI
- [ ] Merlin respects persona voice (can hear difference)
- [ ] Fallback voice plays if preferred voice unavailable
- [ ] Interruption stops playback cleanly

### Dependencies
- [ ] `guppy_voice.py` must support voice selection per-call
- [ ] `runtime/voice_bindings.json` schema defined
- [ ] Kokoro inference working at baseline

### Risk: Medium-High
- Audio playback threading (QAudio vs PyAudio vs platform APIs)
- Engine integration complexity (ElevenLabs requires API key)
- Mitigation: Defer ElevenLabs to M2.2; lock Kokoro + system for M2.0

---

## EPIC 4: Agent Tools Tab

**Scope:** Tools available for use within the active instance; separated from app management tools

### Deliverables

1. **Tool Card Template** (`ui/launcher/components/agent_tool_card.py`)
   - Icon + name + description
   - Status badge: ✓ Ready | 🔧 Wired | ⏱ Coming M3 | 🔒 Instance-Restricted
   - If restricted: show which instances/models can use it
   - "Run" or "Configure" button (or disabled + tooltip)
   - Quick preview of input schema (if available)
   - **Lines of code est.:** ~250

2. **Agent Tools Tab Layout** (`ui/launcher/views/agent_tools_view.py`)
   - Grid of tool cards (3 columns, scrollable)
   - Category filter buttons: All | Read-Only | Write | Code | Query
   - Search: "find a tool"
   - Tools shown only if available for active instance
   - Disabled/grayed out tools show reason (e.g., "Not available for guppy-fast")
   - **Lines of code est.:** ~300

3. **Per-Instance Tool Permissions** (extend `config/instances.json`)
   - Define which tools are available per instance type
   - Default: read-only tools for all; write tools for admin instances
   - Custom override per instance (optional)
   - Schema stored in `config/tool_permissions.json`
   - Enforced in API/tool runner as well as launcher UI
   - **Lines of code est.:** ~150

4. **Tool Invocation Flow**
   - User clicks "Run" on tool card
   - If requires input: inline modal appears (QLineEdit, QTextEdit, etc. based on schema)
   - Execution happens in context of active instance
   - Outcome appears in Home tab chat (success/error/result)
   - **Lines of code est.:** ~200

5. **Dry-Run Pattern for Write Tools**
   - `write_file`, `execute_command`, `run_python`: add dry-run checkbox
   - Preview what would happen
   - User confirms before actual execution
   - **Lines of code est.:** ~150

**Acceptance Criteria:**
- [ ] Only tools available for active instance are shown
- [ ] Each tool has clear description
- [ ] Write tools have dry-run option
- [ ] Tool invocation outcome visible in chat
- [ ] Instance context is respected (admin vs restricted instances)
- [ ] Search finds tools by name or description
- [ ] No "not wired yet" tooltips
- [ ] Direct API/tool invocations are denied when the active instance lacks capability

### Dependencies
- [ ] Instance model/type system defined (Epic 0)
- [ ] Tool schema includes per-instance permissions
- [ ] Home tab chat can receive tool outcomes

### Risk: Low
- Mostly configuration + filtering logic
- Mitigation: Reuse tool descriptions from tool_registry.py

---

## EPIC 5: App Management Tab

**Scope:** App-level recovery and diagnostics operations; separate from Agent Tools

### Deliverables

1. **Recovery Action Cards** (`ui/launcher/components/recovery_action_card.py`)
   - Card 1: "Warmup — Refresh model cache, reload voice engine"
   - Card 2: "Restart Daemon — Hard reset background processes"
   - Card 3: "Audit Runtime — Check logs, schema validation, health"
   - Each card: description + button (maybe confirm dialog)
   - Show outcome in Home tab chat or in Status area
   - **Lines of code est.:** ~250

2. **Diagnostics Panel**
   - Read-only status snapshot: "System Health"
   - Display: models loaded | instances running | voice status | API health
   - Refresh button (manual or auto every 30s)
   - Show last 5 warning/error events
   - **Lines of code est.:** ~200

3. **Operator Logs Viewer**
   - Tail of `launcher_events.jsonl` (last 50 entries)
   - Filterable by level: ERROR | WARN | INFO | DEBUG
   - Clickable to show full entry
   - Export button (download as zip)
   - **Lines of code est.:** ~200

4. **App-Level Guardrails** (no instance-specific guards)
   - Guard: Can't run Warmup if inference in-flight (show "try again in 5s")
   - Guard: Restart shows warning if instances are active
   - Override button: "Force Restart Anyway" (for emergencies)
   - **Lines of code est.:** ~100

5. **App Management Tab Layout**
   - 3 sections: Recovery (top) | Diagnostics (middle) | Logs (bottom)
   - Responsive: stack vertical on small windows
   - **Lines of code est.:** ~100

**Acceptance Criteria:**
- [ ] User can trigger all recovery actions from UI
- [ ] Outcomes visible in status area (not silently logged)
- [ ] Diagnostics show current app health
- [ ] Logs are searchable and exportable
- [ ] Guards prevent accidental actions (but can override)
- [ ] Recovery actions work cleanly (warmup resets cache, restart kills+relaunches daemon, audit generates report)

### Dependencies
- [ ] `/repair` endpoint working (existing — check guppy_api.py)
- [ ] Launcher-daemon IPC working
- [ ] Diagnostic snapshot function available

### Risk: Medium
- IPC timing (might race if daemon is busy)
- Mitigation: Add 2-second timeout, show "try again" if timeout

---

## EPIC 6: Off-Hours Agent Scaling

**Scope:** Write tasks are safe, reviewed, and common

### Deliverables

1. **Write Task Templates** (`tools/offhours_write_tasks.py`)
   - Template: "Generate test stubs for module X"
   - Template: "Update schema for config Y"
   - Template: "Docstring cleanup for function Z"
   - Each template includes: target model, prompt, output path, constraints
   - **Lines of code est.:** ~200

2. **Dry-Run Review Workflow**
   - Task runs → output staged to `runtime/offhours_results/dry_run/`
   - Human reviews staged file
   - Approves via CLI: `python tools/offhours_worker.py --approve-task task_id_123`
   - Applies patch or writes file
   - Logs approver + timestamp
   - **Lines of code est.:** ~150

3. **Per-Model Task Tuning**
   - Merlin-code prompts optimized (examples + constraints)
   - Guppy-fast prompts for summarization
   - Haiku prompts for triage
   - Store in `config/offhours_prompts/`
   - **Lines of code est.:** ~100

4. **Safety Guardrails**
   - Max 3 file writes per run (budget cap)
   - Paths must be within `src/`, `tests/`, `docs/`, `config/` only
   - Never write to root, `guppy_core/`, `ui/launcher/`
   - Checksum validation (generated file hash must match expected range)
   - **Lines of code est.:** ~150

5. **Metrics Collection**
   - Track: tasks run, success rate, dry-run % approved, files written
   - Store in `runtime/offhours_metrics.jsonl`
   - Report via CLI: `python tools/offhours_worker.py --report`
   - **Lines of code est.:** ~100

**Acceptance Criteria:**
- [ ] At least 5 write task templates working
- [ ] Dry-run produces valid Python/YAML/Markdown
- [ ] Approval workflow tested end-to-end
- [ ] Safety guards block unsafe paths
- [ ] Metrics show >85% success rate on approved tasks
- [ ] No human approval required for <5-line changes (optional)

### Dependencies
- [ ] `apply_patch` tool working (EXISTING — done in off-hours extension)
- [ ] Merlin-code responding consistently

### Risk: Medium
- Patch application edge cases (merge conflicts, formatting)
- Mitigation: Require human approval for all writes in M2.0; auto-apply in M2.2

---

## SCHEDULE & MILESTONES

### **Week of Apr 15 (Ramp Phase + Epic 0 Foundation)**
- [ ] All epic PRDs reviewed + approved
- [ ] Instance state schema finalized (`config/instances.json`)
- [ ] Tool permission schema finalized (`config/tool_permissions.json`)
- [ ] Instance Manager UI mockup
- [ ] Home Tab primary interface layout sketched
- [ ] Multi-instance chat history storage designed

### **May 1–31 (Core Implementation: Foundation + Configuration)**
- [ ] Epic 0: Instance Manager + Multi-Instance working (2 instances tested)
- [ ] Epic 0.1: Home Tab layout and instance switching working
- [ ] Epic 1: Persona Builder v1 complete + tested
- [ ] Epic 2: Model Assignment MVP (click-to-assign only)
- [ ] Epic 4 foundations: Agent Tools tab structure + capability enforcement layer

### **June 1–14 (Integration + Polish)**
- [ ] Epic 0: Inter-agent communication bridge working (sync bounded query with busy/timeout states)
- [ ] Epic 0.1: Home Tab fully integrated with instance switching
- [ ] Epic 3: Voice Library basics (Kokoro + system TTS) 
- [ ] Epic 4: Agent Tools cards + permissions filtering working
- [ ] Epic 5: App Management Tab (recovery actions, diagnostics, logs)
- [ ] Epic 6: Off-hours write tasks (5 templates, dry-run working)
- [ ] Instance log redaction + retention policy working
- [ ] Full integration test + UAT prep

### **June 15 – Sep 30 (Refinement, Scale, and Advanced Features)**
- [ ] Collect early UAT feedback on instance model
- [ ] Epic 0.2: Background instance queuing/scheduling (optional)
- [ ] Epic 3.2: Add ElevenLabs optional support
- [ ] Epic 5.1: App-level monitoring dashboard
- [ ] Epic 6.2: Auto-apply safe write tasks
- [ ] Documentation & video tutorials
- [ ] M2 Exit Testing (Sep 15 – 30)

---

## SUCCESS METRICS

| Metric | Target | Why Matters |
|---|---|---|
| Instance creation time | <30s (form-based, no JSON) | UX quality |
| Instance switching latency | <500ms to display new chat | UX responsiveness |
| Home Tab as primary | 100% of new user flows start here | Product positioning |
| Inter-agent queries | 95% success rate for 1 in-flight bounded query | Feature reliability |
| Builder form completion time | <2 min for non-technical user | UX quality |
| Agent authorization | 100% of restricted tool calls blocked server-side | Safety |
| Off-hours task success rate | >85% (after approval) | Agent reliability |
| Voice assignment latency | <500ms config load | Performance |

---

## BLOCKERS & DEPENDENCIES

| Blocker | Status | Mitigation |
|---|---|---|
| Multi-instance state management (switching context) | High | Start with 2-instance MVP; build out |
| Audio playback latency (PySide6 + Kokoro) | Medium | Test early; defer ElevenLabs |
| Server-side capability enforcement for tools | High | Add capability checks in tool runner and API before UI rollout |
| Sensitive data in per-instance logs | High | Redaction, retention window, export warning, and operator-only access |
| Off-hours patch conflicts | Medium | Lock key files (guppy_core, ui/launcher); use dry-run only |
| Voice engine API keys | Low | Document setup; defer optional engines |

---

## DECISION POINTS

1. **Home Tab as Primary vs Tabs Coequal**
   - DECIDED: Home Tab = primary product surface (70%+ visual focus)
   - Instance Manager, Agent Tools, App Management = supporting surfaces
   - Rationale: Users need to chat first; everything else is configuration/management

2. **Agent Tools vs App Management Tabs (Separation of Concerns)**
   - DECIDED: Two separate tabs
     - Agent Tools: tools FOR instances to USE (run_python, read_file, query other instances)
     - App Management: tools FOR app management (warmup, restart, audit, diagnostics)
   - Rationale: Reduces cognitive load; clearer affordance; prevents misuse of system tools by agents
   
3. **Single Instance vs Multi-Instance MVP**
   - DECIDED: Bounded multi-instance from M2.0
   - Rationale: Required for builder/background collaboration, but limited to 2 active instances and 1 in-flight cross-instance query for feasibility

4. **Instance Context Switching (Add to Home Tab or Require Manager Tab)**
   - DECIDED: Quick switcher in Home Tab header (e.g., dropdown or small icon)
   - Instance Manager tab for full-featured creation/logs/deletion
   - Rationale: Faster workflow for power users; keeps primary surface uncluttered

5. **Inter-Agent Query Contract (Queued vs Bounded Sync)**
   - DECIDED: Bounded synchronous request in M2.0
   - Returns completed response or busy/timeout within 5s
   - Queue-based orchestration deferred to M2.2 after resource behavior is measured

6. **Drag-drop vs Click-to-Assign for Model Selection**
   - DECIDED: Click-to-assign (MVP, simpler)
   - May revisit in M2.2 if UX feedback

7. **All voices or just Kokoro + System TTS?**
   - DECIDED: Kokoro + System (Lock ElevenLabs to M2.2)
   - Needs less maintenance, fewer API keys

8. **Auto-apply off-hours tasks or always require approval?**
   - DECIDED: Approval required in M2.0 (safe default)
   - Auto-apply for <5-line changes in M2.2 (pending approval)

---

## EOF — M2 SCOPE LOCKED

**Approved by:** Architecture Review  
**Date:** April 13, 2026 (Updated for Instance Manager architecture)  
**Next Gate:** M2 Kickoff Readiness (Jun 15, 2026)

