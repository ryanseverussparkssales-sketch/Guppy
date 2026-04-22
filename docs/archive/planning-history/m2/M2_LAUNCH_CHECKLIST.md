# M2 Launch Checklist

**Target Launch:** June 15, 2026  
**Prep Window:** April 15 â€” June 14 (8 weeks)  
**Status:** ðŸŸ¢ **READY TO ACTIVATE**

---

## Pre-Launch Verification (Due Jun 10)

### Code Quality Gate
- [ ] All M1 tests still passing (70/70)
- [ ] No new lint errors introduced
- [ ] No legacy window spawns possible from default flow
- [ ] INIT button wired on all agent cards
- [ ] Transcript clean (no transient "Processing..." bubbles)

### Documentation Gate
- [ ] ROADMAP.md updated with M2 active status
- [ ] M2_ENGINEERING_PLAN.md published + reviewed
- [ ] All 8 M2 workstreams finalized (instances, home, personas, routes, voices, agent tools, app management, offhours)
- [ ] Decision points documented (bounded multi-instance, sync query contract, ElevenLabs defer, approval-required default)
- [ ] Success metrics defined and baselined

### Infrastructure Gate
- [ ] `/status` API endpoint returns model health
- [ ] Provider/model routes schema in `runtime/provider_registry.json`
- [ ] Persona config schema in `runtime/persona_config.json`
- [ ] Voice bindings schema in `runtime/voice_bindings.json`
- [ ] Instance definition schema in `config/instances.json`
- [ ] Tool permission schema in `config/tool_permissions.json`
- [ ] Off-hours task queue empty (ready to accept M2 tasks)

### Security Gate
- [ ] Per-instance tool permissions enforced server-side
- [ ] Inter-instance query endpoint returns `ok|busy|timeout` status and respects 5s timeout
- [ ] Instance logs redact obvious secrets and enforce retention policy
- [ ] Raw log export displays warning and is operator-only

### Dependency Gate
- [ ] Kokoro inference stable at baseline
- [ ] Merlin-code model responding to code generation prompts
- [ ] Guppy-fast model responding to summarization prompts
- [ ] System TTS working on Windows (fallback verified)

### Stakeholder Gate
- [ ] Product brief reviewed and approved (docs/PROJECT_BRIEF.md)
- [ ] M2 scope locked (no feature creep without gate approval)
- [ ] Team agrees on priority order (1=Builder, 2=Routes, 3=Voice, etc.)
- [ ] Budget allocated ($40â€“60 for Claude via off-hours agents)

---

## Weekly Tracking (Apr 15 â€” Jun 14)

Use this template to track progress against 8-week ramp:

### Week of Apr 15 (Week 1/8)
- [ ] Instance Manager: config/runtime schema finalized
- [ ] Home Tab: quick-switcher layout sketched
- [ ] Persona Builder: form mockup in Qt (no handlers yet)
- [ ] Model Routes: provider registry binding finalized
- [ ] Voice: engine abstraction design (which engines supported)
- [ ] Agent Tools/App Mgmt: split existing controls into separate surfaces
- [ ] Off-Hours: write task templates outlined
- **Goal:** Designs approved, dev environment ready

### Week of Apr 22 (Week 2/8)
- [ ] Instance Manager: create/delete/switch flow working
- [ ] Home Tab: active instance indicator + restore history working
- [ ] Persona Builder: slider events wired to preview
- [ ] Model Routes: dropdown selectors working
- [ ] Voice: Kokoro API abstraction implemented
- [ ] Agent Tools: card template + permission schema ready
- [ ] Off-Hours: first template (test stub generator) coded
- **Goal:** All workstreams have working skeleton

### Week of Apr 29 (Week 3/8)
- [ ] Inter-instance query API: bounded sync contract implemented
- [ ] Persona Builder: save flow working, JSON persisted
- [ ] Model Routes: fallback chain editing working
- [ ] Voice: system TTS fallback integrated
- [ ] Agent Tools/App Mgmt: old mixed controls removed, new surfaces in place
- [ ] Off-Hours: dry-run staging working
- **Goal:** Feature completeness for Epic 1 & 4

### Week of May 6 (Week 4/8)
- [ ] Tool runner/API capability enforcement tested end-to-end
- [ ] Persona Builder: v0.1 complete + tested
- [ ] Model Routes: health badges working (polling `/status`)
- [ ] Voice: preview playback tested
- [ ] Agent Tools: all live tools have descriptions + dry-run
- [ ] App Mgmt: warmup/restart/audit cards working
- [ ] Off-Hours: approval workflow tested end-to-end
- **Goal:** Epics 1, 4, 6 done; Epics 2, 3 in progress

### Week of May 13 (Week 5/8)
- [ ] Model Routes: route visualizer (optional) or skipped to M2.2
- [ ] Voice: per-persona assignment working
- [ ] Recovery Actions: all 3 cards wired (warmup, restart, audit)
- [ ] Off-Hours: 5+ write task templates ready
- **Goal:** Epics 2, 3, 5 feature-complete

### Week of May 20 (Week 6/8)
- [ ] Full integration: all tabs working together
- [ ] Cross-tab signals: persona change triggers model rebuild
- [ ] Voice change triggers TTS reload
- [ ] Cross-tab consistency: no orphaned state
- **Goal:** Entire M2 feature set integrated

### Week of May 27 (Week 7/8)
- [ ] UAT prep: test plan completed
- [ ] Edge case testing: invalid JSON, timeout recovery, etc.
- [ ] Performance: form load <200ms, route select <100ms
- [ ] Documentation: user guide + troubleshooting for Builder
- **Goal:** Ready for stakeholder UAT

### Week of Jun 3 (Week 8/8)
- [ ] UAT sign-off: all acceptance criteria pass
- [ ] Bug fixes: <15 min P1 + P2 bugs fixed
- [ ] Performance tuning: <50ms added to startup time
- [ ] Release prep: tag git, build executable, test installer
- **Goal:** Production-ready build

### Week of Jun 10 (Launch Prep)
- [ ] Final verification gate run (see below)
- [ ] Team sign-off on all 8 workstreams
- [ ] Stakeholder approval to proceed
- [ ] Build tagged and archived

---

## Launch Day (Jun 15)

### Morning Checklist
- [ ] All tests pass: `pytest tests/ -q`
- [ ] Lint clean: `pylint` or equivalent
- [ ] No console errors on first launch
- [ ] All tabs render without errors
- [ ] Home/Instance Manager/Agent Tools/App Management/Settings/Models/Voices tabs all load

### Smoke Test
- [ ] INIT button live on all agent cards â†’ open embedded chat
- [ ] Switch active instance from Home header â†’ transcript swaps cleanly
- [ ] Query background instance â†’ `ok|busy|timeout` surfaced correctly
- [ ] Select model in Models tab â†’ route updates
- [ ] Adjust persona slider in Settings â†’ preview updates
- [ ] Play voice sample from Voices tab â†’ audio plays
- [ ] Click "Warmup" in App Management tab â†’ status appears in chat

### Operational Readiness
- [ ] Off-hours worker ready (queue empty, tasks runnable)
- [ ] Monitoring alerts set up (launcher crash, model failure)
- [ ] Rollback plan documented (revert to M1 build if needed)
- [ ] Team on-call for first week

### Go/No-Go Decision
- **GO:** All boxes checked; proceed to active development
- **HOLD:** Any gate failed; pause and debug

---

## Success Criteria (End of M2 â€” Sep 30)

### Feature Completion
- [ ] Epic 0: Instance Manager + multi-instance shipped with bounded limits
- [ ] Epic 0.1: Home tab primary interface shipped
- [ ] Epic 1: Persona Builder v1 live (non-technical UX confirmed)
- [ ] Epic 2: Model Assignment + Routes visible (100% coverage)
- [ ] Epic 3: Voice assignment working (per-persona override tested)
- [ ] Epic 4: Agent Tools tab clean and capability-aware
- [ ] Epic 5: App Management actions discoverable + guarded
- [ ] Epic 6: Off-hours at scale (5â€“10 write tasks/week)

### Code Quality
- [ ] 80+ test coverage (70 existing + new epics)
- [ ] 0 lint errors
- [ ] All code reviewed per architecture contract
- [ ] No deprecated APIs used

### Performance
- [ ] Startup time: <3 sec (no regression from M1)
- [ ] Form response: <200ms
- [ ] Voice playback: <500ms to first audio
- [ ] Model selection: <100ms to apply

### User Experience
- [ ] NPS â‰¥7/10 on Builder form
- [ ] 0 "not wired yet" visible in any tab
- [ ] Every action shows outcome (success/error)
- [ ] Voice interruption works reliably (>95% success)

### Documentation
- [ ] User guide published
- [ ] Video tutorials recorded (if timeline allows)
- [ ] Troubleshooting guide updated
- [ ] Architecture docs updated

### Operational
- [ ] Monitoring dashboards active
- [ ] Incident runbook documented
- [ ] Off-hours metrics tracked and healthy
- [ ] Deployment process automated

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| PySide6 threading issues (audio playback) | Medium | High | Test voice playback early (Week 2); spike thread safety |
| Form state complexity (edit mode race) | Medium | Medium | Use Qt state machine or unit test state transitions |
| Off-hours patch conflicts | Low | High | Lock key files; whitelist only safe dirs; dry-run only |
| Model health API timeout | Low | Medium | Cache health for 30s; show "unknown" if timeout |
| Kokoro latency > 2s | Low | Medium | Test inference time weekly; defer batch inference to M2.2 |

---

## Sign-Off

- [ ] Architecture review: _________________ Date: _____
- [ ] Product lead: _________________ Date: _____
- [ ] Platform lead: _________________ Date: _____
- [ ] Team consensus: APPROVED / HOLD

**Status:** ðŸŸ¢ **LAUNCH-READY** (Jun 15 target)

