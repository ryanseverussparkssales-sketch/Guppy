# M2 Engineering Plan

**Milestone:** Functional Parity for Builder and Tooling  
**Target Date:** September 30, 2026  
**Prep Window:** April 15 — June 14, 2026 (2 months to ramp)  
**Active Development:** June 15 — September 30 (3.5 months)

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
   - Save → writes to `config/model_routes.json`
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
- [ ] Model routes schema defined (EXISTING — check config/model_routes.json)

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

## EPIC 4: Tools Tab Cleanup

**Scope:** Every visible tool has a documented action or explicit "Coming Soon" badge

### Deliverables

1. **Placeholder Removal**
   - Audit all current tools in launcher Tools tab
   - Mark "not wired" placeholders as: HIDDEN (if <20% wired) or DISABLED+BADGE (if 20–80%)
   - Remove: notification bell placeholder, PTT placeholder
   - Keep: run_python, read_file, write_file, screenshot (if working)
   - **Lines of code est.:** ~100

2. **Tool Card Template** (`ui/launcher/components/tool_card.py`)
   - Icon + name + description
   - Status badge: ✓ Ready | 🔧 Wired | ⏱ Coming M3 | 🔒 Beta Only
   - If beta: show `GUPPY_BETA_RESTRICTED_MODE` lock status
   - "Run" or "Configure" button (or disabled + tooltip)
   - **Lines of code est.:** ~200

3. **Dry-Run Pattern** (for risky tools)
   - `run_python` → add dry-run checkbox: "Show what I'd run, don't execute"
   - `write_file` → add dry-run checkbox: "Stage file for review"
   - `execute_command` → add dry-run checkbox: "Show command"
   - Visualize what would happen
   - **Lines of code est.:** ~150

4. **Tools Tab Integration**
   - Replace old button grid with new card grid
   - Category filters: All | Read-Only | Write | Code | CRM/VoIP
   - Search: "find a tool"
   - **Lines of code est.:** ~200

5. **Schema Audit** (docs)
   - Document which tools are live, which are deferred
   - Create explicit rows in ROADMAP.md for each tool
   - Add comments to tool_registry.py indicating M2 vs M3 status

**Acceptance Criteria:**
- [ ] No "not wired yet" tooltips visible (all hidden or have real action)
- [ ] Every tool has a description
- [ ] Beta tools show their restriction level
- [ ] Dry-run pattern works for write operations
- [ ] CRM/VoIP tools explicitly say "Coming M3"
- [ ] Search finds tools by name or description
- [ ] Test: run all live tools; all succeed or fail gracefully

### Dependencies
- [ ] `guppy_core/beta_policy.py` must be current (check `BETA_ONLY_TOOLS`)

### Risk: Low
- Mostly UI organization, no new functionality
- Mitigation: Reuse existing tool descriptions from tool_registry.py

---

## EPIC 5: Advanced Tab + Recovery Actions

**Scope:** Recovery flows are discoverable; process guards prevent accidents

### Deliverables

1. **Recovery Action Cards** (`ui/launcher/components/recovery_card.py`)
   - Card 1: "Warmup — Refresh model cache"
   - Card 2: "Restart Daemon — Hard reset background processes"
   - Card 3: "Audit Runtime — Check logs and config"
   - Each card: description + button (maybe confirm dialog)
   - Show outcome in Assistant transcript
   - **Lines of code est.:** ~250

2. **Process Guards** (extend `launcher_window.py`)
   - Guard 1: Can't launch second Guppy if one is running
   - Guard 2: Can't restart daemon if API is in flight
   - Guard 3: Can't hotswap models during inference
   - Show clear message if guard blocks action
   - **Lines of code est.:** ~150

3. **Outcome Visibility**
   - Recovery action outcome (success | failure | partial) appears in chat
   - Show relevant log tail or error message
   - E.g.: "Warmup: refreshed 5 models. Merlin unavailable (rebuild pending)."
   - **Lines of code est.:** ~200

4. **Advanced Tab Layout**
   - 3 columns: Recovery | Diagnostics | Operator Logs
   - Recovery: action cards above
   - Diagnostics: read-only status snapshot
   - Operator Logs: tail of launcher_events.jsonl
   - **Lines of code est.:** ~200

**Acceptance Criteria:**
- [ ] User can trigger all recovery actions from UI
- [ ] Outcomes are visible in chat (not silently logged)
- [ ] Guards prevent accidental double-launches
- [ ] Warmup resets local model cache
- [ ] Restart kills + relaunches daemon cleanly
- [ ] Audit writes diagnostic report to file

### Dependencies
- [ ] `/repair` endpoint working (EXISTING — check guppy_api.py)
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

### **Week of Apr 15 (Ramp Phase)**
- [ ] All epic PRDs reviewed + approved
- [ ] Builder form v0 prototype (Qt mockup, no handlers)
- [ ] Model assignment data structure finalized
- [ ] Voice engine abstraction design (which engines to support)

### **May 1–31 (Core Implementation)**
- [ ] Epic 1: Persona Builder v1 complete + tested
- [ ] Epic 2: Model Assignment MVP (click-to-assign only, no visualizer)
- [ ] Epic 4: Tools Tab cleanup (cards, badges, descriptions)

### **June 1–14 (Polish + Testing)**
- [ ] Epic 3: Voice Library basics (Kokoro + system TTS only)
- [ ] Epic 5: Advanced Tab + Recovery Cards
- [ ] Epic 6: Off-hours write tasks (5 templates, dry-run working)
- [ ] Full integration test + UAT prep

### **June 15 – Sep 30 (Refinement & Scale)**
- [ ] Collect early UAT feedback
- [ ] Epic 2.1: Add route visualizer if demand signals
- [ ] Epic 3.2: Add ElevenLabs optional support
- [ ] Epic 6.2: Auto-apply safe write tasks
- [ ] Documentation & video tutorials
- [ ] M2 Exit Testing (Sep 15 – 30)

---

## SUCCESS METRICS

| Metric | Target | Why Matters |
|---|---|---|
| Builder form completion time | <2 min for non-technical user | UX quality |
| Model assignment clarity | 100% of users understand fallback chain | Feature clarity |
| Off-hours task success rate | >85% (after approval) | Agent reliability |
| Tools tab NPS | 7+/10 | UI satisfaction |
| Recovery action success | 100% (guards work) | Safety |
| Voice assignment latency | <500ms config load | Performance |

---

## BLOCKERS & DEPENDENCIES

| Blocker | Status | Mitigation |
|---|---|---|
| Audio playback latency (PySide6 + Kokoro) | Medium | Test early; defer ElevenLabs |
| Form state management complexity (edit mode) | Low | Use Qt state machine or simple flags |
| Off-hours patch conflicts | Medium | Lock key files (guppy_core, ui/launcher); use dry-run only |
| Voice engine API keys | Low | Document setup; defer optional engines |

---

## DECISION POINTS

1. **Drag-drop vs Click-to-Assign for Model Selection**
   - DECIDED: Click-to-assign (MVP, simpler)
   - May revisit in M2.2 if UX feedback

2. **All voices or just Kokoro + System TTS?**
   - DECIDED: Kokoro + System (Lock ElevenLabs to M2.2)
   - Needs less maintenance, fewer API keys

3. **Auto-apply off-hours tasks or always require approval?**
   - DECIDED: Approval required in M2.0 (safe default)
   - Auto-apply for <5-line changes in M2.2 (pending approval)

---

## EOF — M2 SCOPE LOCKED

**Approved by:** Architecture Review  
**Date:** April 13, 2026  
**Next Gate:** M2 Kickoff Readiness (Jun 15, 2026)
