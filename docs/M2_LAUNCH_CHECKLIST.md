# M2 Launch Checklist

**Target Launch:** June 15, 2026  
**Prep Window:** April 15 — June 14 (8 weeks)  
**Status:** 🟢 **READY TO ACTIVATE**

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
- [ ] All 6 epic PRDs finalized (personas, routes, voices, tools, recovery, offhours)
- [ ] Decision points documented (drag-drop vs click, ElevenLabs defer, approval-required default)
- [ ] Success metrics defined and baselined

### Infrastructure Gate
- [ ] `/status` API endpoint returns model health
- [ ] Model routes schema in `config/model_routes.json`
- [ ] Persona config schema in `config/personas.json`
- [ ] Voice bindings schema in `runtime/voice_bindings.json`
- [ ] Off-hours task queue empty (ready to accept M2 tasks)

### Dependency Gate
- [ ] Kokoro inference stable at baseline
- [ ] Merlin-code model responding to code generation prompts
- [ ] Guppy-fast model responding to summarization prompts
- [ ] System TTS working on Windows (fallback verified)

### Stakeholder Gate
- [ ] Product brief reviewed and approved (docs/PROJECT_BRIEF.md)
- [ ] M2 scope locked (no feature creep without gate approval)
- [ ] Team agrees on priority order (1=Builder, 2=Routes, 3=Voice, etc.)
- [ ] Budget allocated ($40–60 for Claude via off-hours agents)

---

## Weekly Tracking (Apr 15 — Jun 14)

Use this template to track progress against 8-week ramp:

### Week of Apr 15 (Week 1/8)
- [ ] Persona Builder: form mockup in Qt (no handlers yet)
- [ ] Model Routes: data structure finalized
- [ ] Voice: engine abstraction design (which engines supported)
- [ ] Tools: placeholder audit completed (list of dead controls)
- [ ] Off-Hours: write task templates outlined
- **Goal:** Designs approved, dev environment ready

### Week of Apr 22 (Week 2/8)
- [ ] Persona Builder: slider events wired to preview
- [ ] Model Routes: dropdown selectors working
- [ ] Voice: Kokoro API abstraction implemented
- [ ] Tools: card template design ready
- [ ] Off-Hours: first template (test stub generator) coded
- **Goal:** All epics have working skeleton

### Week of Apr 29 (Week 3/8)
- [ ] Persona Builder: save flow working, JSON persisted
- [ ] Model Routes: fallback chain editing working
- [ ] Voice: system TTS fallback integrated
- [ ] Tools: old buttons removed, new cards in place
- [ ] Off-Hours: dry-run staging working
- **Goal:** Feature completeness for Epic 1 & 4

### Week of May 6 (Week 4/8)
- [ ] Persona Builder: v0.1 complete + tested
- [ ] Model Routes: health badges working (polling `/status`)
- [ ] Voice: preview playback tested
- [ ] Tools: all live tools have descriptions + dry-run
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
- [ ] Team sign-off on all 6 epics
- [ ] Stakeholder approval to proceed
- [ ] Build tagged and archived

---

## Launch Day (Jun 15)

### Morning Checklist
- [ ] All tests pass: `pytest tests/ -q`
- [ ] Lint clean: `pylint` or equivalent
- [ ] No console errors on first launch
- [ ] All tabs render without errors
- [ ] Settings/Models/Voices/Advanced tabs all load

### Smoke Test
- [ ] INIT button live on all agent cards → open embedded chat
- [ ] Select model in Models tab → route updates
- [ ] Adjust persona slider in Settings → preview updates
- [ ] Play voice sample from Voices tab → audio plays
- [ ] Click "Warmup" in Advanced tab → status appears in chat

### Operational Readiness
- [ ] Off-hours worker ready (queue empty, tasks runnable)
- [ ] Monitoring alerts set up (launcher crash, model failure)
- [ ] Rollback plan documented (revert to M1 build if needed)
- [ ] Team on-call for first week

### Go/No-Go Decision
- **GO:** All boxes checked; proceed to active development
- **HOLD:** Any gate failed; pause and debug

---

## Success Criteria (End of M2 — Sep 30)

### Feature Completion
- [ ] Epic 1: Persona Builder v1 live (non-technical UX confirmed)
- [ ] Epic 2: Model Assignment + Routes visible (100% coverage)
- [ ] Epic 3: Voice assignment working (per-persona override tested)
- [ ] Epic 4: Tools tab clean (no placeholders visible)
- [ ] Epic 5: Recovery actions discoverable + guarded
- [ ] Epic 6: Off-hours at scale (5–10 write tasks/week)

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
- [ ] NPS ≥7/10 on Builder form
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

**Status:** 🟢 **LAUNCH-READY** (Jun 15 target)
