# Master Roadmap to Freeze-Readiness

**Comprehensive plan:** FR-C1 through FR-C10 status + execution sequencing  
**Target:** June 12, 2026 (Freeze-ready state)  
**Date:** 2026-04-22

---

## Complete FR-C Tranche Status

### ✅ LANDED (5/10 Tranches)

| ID | Purpose | Lines Before → After | Status |
|----|---------|----------------------|--------|
| **C1** | API Runtime Snapshot | 2232 → 1990 | ✅ DONE |
| **C2** | Launcher Shell Reduction | 3354 → 3069 | ✅ DONE |
| **C3** | Models Hub Split | 1542 → 1298 | ✅ DONE |
| **C5** | Settings Operations Split | ~1032 → <900 | ✅ DONE |
| **C9** | Runtime/Request Lane | 586 → 403 | ✅ DONE |

**Plus:** Home/Library/Voices decomposition wave ✅ (assistant, library, voices views reduced)

---

## 📋 PENDING (5/10 Tranches)

### FR-C4: Home Chat Coordinator Split 
**Goal:** Reduce `assistant_view.py` to <1200 lines  
**What:** Separate transcript/composer/starter/detail behavior into sections  
**Current Size:** ~1300 lines  
**Target Reduction:** 100-150 lines  
**Timeline:**  
- Start: May 20 (after FR-C7/C8 Phase 2)
- Complete: June 2
- Tests: Unit tests for new section modules
**Deliverables:**
- `ui/launcher/views/assistant_transcript_section.py`
- `ui/launcher/views/assistant_composer_section.py`
- `ui/launcher/views/assistant_starters_section.py`
- Wrapper in `assistant_view.py` that orchestrates sections

---

### FR-C6: Library & Voice Surface Decomposition
**Goal:** Reduce `library_view.py` to <900 lines, `voices_view.py` to <866 lines  
**What:** Extract row/card/editor/section logic  
**Current Sizes:**
- library_view.py: ~950 lines
- voices_view.py: ~866 lines  
**Target Reduction:** 50-100 lines per view  
**Timeline:**
- Start: June 2 (after C4)
- Complete: June 8
- Tests: Unit tests for section modules
**Deliverables:**
- `ui/launcher/views/library_card_sections.py` (if not already done)
- `ui/launcher/views/voices_card_sections.py` (if not already done)
- Reduced parent views

---

### FR-C7: Connector Manager Extraction
**Current Status:** Phase 1 ✅ (Apr 22), Phases 2-4 pending

| Phase | Goal | Timeline | Status |
|-------|------|----------|--------|
| **Phase 1** | Create services + tests | Apr 22 ✅ | ✅ DONE |
| **Phase 2** | Verify tests pass | Apr 24-29 | 📋 Ready (win dows) |
| **Phase 3** | Update imports if cleaner | May 6 | 📋 Scheduled |
| **Phase 4** | Add deprecation | May 16 | 📋 Scheduled |
| **Complete** | All phases done | May 19 | 🎯 Target |

**Phase 2 Commands:**
```powershell
python tools/dev_workflow.py test-fast
python tools/dev_workflow.py test-default
python tools/dev_workflow.py release-check
```

See `FR-C7_PHASE2_VERIFICATION_PLAN.md` for details.

---

### FR-C8: Personalization Config Service Split
**Current Status:** Services exist ✅ (in `src/guppy/experience_config/`), Phases 2-4 pending

| Phase | Goal | Timeline | Status |
|-------|------|----------|--------|
| **Phase 1** | Create services + tests | Pre-Apr 22 ✅ | ✅ DONE |
| **Phase 2** | Verify tests pass | Apr 24-29 (after C7) | 📋 Ready |
| **Phase 3** | Update imports if cleaner | May 6 | 📋 Scheduled |
| **Phase 4** | Add deprecation | May 16 | 📋 Scheduled |
| **Complete** | All phases done | June 11 | 🎯 Target |

**Services Exist:**
- `personalization_defaults.py` (11.5 KB) — Default configs
- `personalization_storage.py` (21.4 KB) — Persistence layer
- `personalization_resolution.py` (9.9 KB) — Runtime resolution

**Wrapper Status:** `utils/personalization_config.py` already delegates to services ✅

---

### FR-C10: Freeze Audit & Waiver Reset
**Goal:** Re-audit every waiver; document what's transitional; prepare clean freeze snapshot  
**Timeline:**
- Start: June 12 (after C7, C8, C4, C6)
- Duration: 1-2 days (parallel with final validation)
- Complete: June 12
**Scope:**
- ✅ All hotspots below cap or have justified waivers
- ✅ `release-check` green across board
- ✅ All tests passing
- ✅ No stale metadata or docs
- ✅ Services properly seamed
**Deliverables:**
- Updated module caps in `pyproject.toml`
- Waiver audit report
- Architecture documentation current
- README updated with new structure

---

## Execution Timeline: Critical Path

```
April 22 (NOW)
├─ FR-C7 Phase 1 ✅ DONE
├─ FR-C8 Phase 1 ✅ DONE (services exist)
├─ FR-LOCAL ✅ DONE (ready for user test)
└─ Environment ✅ (API keys via .env.local)

April 24-29 (Phase 2 Verification)
├─ FR-C7 Phase 2: Run tests (test-fast, test-default, release-check)
│  └─ Expected: All pass, zero regressions
└─ FR-C8 Phase 2: Run same tests (after C7 Phase 2 ✅)
   └─ Expected: All pass, zero regressions

May 6 (Phase 3: Import Updates)
├─ FR-C7 Phase 3: Review 6 import sites, update if cleaner
├─ FR-C8 Phase 3: Review import sites, update if cleaner
└─ Both: Verify tests still pass after updates

May 16 (Phase 4: Deprecation)
├─ FR-C7 Phase 4: Add deprecation marker to connector_manager.py
├─ FR-C8 Phase 4: Add deprecation marker to personalization_config.py
└─ Both: `release-check` green

May 19 (C7 COMPLETE + C4 Starts)
├─ FR-C7 ✅ COMPLETE (Phase 1-4 done)
└─ FR-C4 START: Home chat coordinator split (reduce assistant_view.py)

June 2 (C4 COMPLETE + C6 Starts)
├─ FR-C4 ✅ COMPLETE (assistant_view.py reduced)
└─ FR-C6 START: Library & voice surface decomposition

June 8 (C6 COMPLETE)
├─ FR-C6 ✅ COMPLETE (library_view.py, voices_view.py reduced)
└─ All 9 architecture tranches done (C1,C2,C3,C4,C5,C6,C7,C8,C9)

June 12 (FREEZE-READY)
├─ FR-C10 ✅ Audit complete
├─ All tests passing
├─ All documentation current
└─ FREEZE: Codebase ready for stabilization
```

---

## Work Distribution

### Week 1 (Apr 22-28)
- **FR-C7 Phase 2:** Run test suite on Windows (tests prepared, waiting execution)
- **FR-C8 Phase 2:** Run test suite on Windows (after C7 Phase 2)
- **FR-LOCAL:** User test (when accessible)
- **Status:** Both major extraction tranches verified

### Week 2 (May 1-7)
- **FR-C7 Phase 3-4:** Import updates + deprecation (5-7 days)
- **FR-C8 Phase 3-4:** Import updates + deprecation (5-7 days, parallel)
- **Status:** Both extraction tranches stabilized

### Week 3 (May 8-19)
- **FR-C4 Start:** Home coordinator split (May 20)
- **Timeline overlap:** C7/C8 finishing, C4 starting
- **Status:** Transition from extraction to decomposition tranches

### Week 4 (May 20-31)
- **FR-C4:** Home chat coordinator (5-7 days)
- **Status:** Home view streamlined

### Week 5 (June 1-8)
- **FR-C6:** Library & voice surface (5-7 days)
- **Status:** All view decompositions complete

### Week 6 (June 9-12)
- **FR-C10:** Freeze audit (2-3 days)
- **Final validation:** All tests, all docs
- **Status:** FREEZE-READY

---

## Success Criteria (June 12)

### Code Quality ✅
- [ ] All 10 FR-C tranches complete or in valid state
- [ ] All hotspot modules at/below cap or have current waiver
- [ ] Zero waivers for code marked "transitional"
- [ ] `release-check` green (0 failures)

### Testing ✅
- [ ] All unit tests pass (test-fast)
- [ ] All integration tests pass (test-default)
- [ ] Smoke tests pass (test-smoke)
- [ ] Zero new regressions vs. baseline

### Documentation ✅
- [ ] CLAUDE.md updated with new architecture seams
- [ ] README reflects current structure
- [ ] Service extraction pattern documented
- [ ] Waiver audit documented and current

### User Experience ✅
- [ ] FR-LOCAL tested and working (if machine accessible)
- [ ] Web UI still functional after all FR-C changes
- [ ] build_and_launch.ps1 still works (final check)
- [ ] Production reduction path validated

### Architecture Seams ✅
- [ ] Launcher → Application layer clear
- [ ] Configuration → Experience config layer clear
- [ ] Connector → Manager + Services clear
- [ ] Personalization → Config services clear
- [ ] Utils → Compatibility wrappers only

---

## Decision Framework: What's Ready Now?

### ✅ Ready to Execute Immediately
1. **FR-C7 Phase 2** — Test suite prepared, waiting Windows execution
2. **FR-C8 Phase 2** — Same tests, same command set
3. **FR-LOCAL test** — User can test when they access machine

### ✅ Ready to Start (May 1+)
1. **FR-C4** — Home chat coordinator split (specs clear, goal <1200 lines)
2. **FR-C6** — Library/voice decomposition (specs clear, goal <900 lines)

### 📋 Ready for Planning (June 1+)
1. **FR-C10** — Freeze audit (framework exists, execution June 12)

---

## Risk Mitigation

### If Phase 2 Tests Fail
1. Check error specifics (missing import, function mismatch, logic error)
2. Review service implementation vs. test expectations
3. Fix service or test (not the wrapper)
4. Re-run and document fix

### If Import Updates Break Code
1. Revert to wrapper imports
2. Document why wrapper is needed
3. Note as FR-C10 item (defer to next cycle)
4. Keep tests passing

### If timeline slips
- C4 and C6 can run in parallel if needed
- C10 audit can compress to 1 day for essential items
- Freeze can proceed with stale docs (not ideal, but acceptable)

---

## Next Immediate Actions

1. **Run FR-C7 Phase 2 tests** on Windows (Apr 24-29)
   ```powershell
   cd C:\Users\Ryan\Guppy
   python tools/dev_workflow.py test-fast
   python tools/dev_workflow.py test-default
   python tools/dev_workflow.py release-check
   ```

2. **Document results** in FR-C7_STATUS_2026-04-22.md
   - Which tests passed/failed
   - Any new warnings
   - Regressions (if any)

3. **Run FR-C8 Phase 2 tests** same commands, document results

4. **Test FR-LOCAL** when machine accessible
   ```powershell
   cd C:\Users\Ryan\Guppy
   pwsh -ExecutionPolicy Bypass -File build_and_launch.ps1
   ```

5. **May 1:** Start Phase 3 (import updates) for both C7 and C8

---

## Summary

**Total FR-C tranches:** 10  
**Complete:** 5 (C1, C2, C3, C5, C9)  
**Phase 1 done:** 2 (C7, C8)  
**Pending Phase 2:** 2 (C7, C8)  
**Pending full:** 3 (C4, C6, C10)  

**Timeline:** All complete by June 12 (on track)  
**Blocker:** Windows test execution (human action, not technical)  
**Next:** Run Phase 2 tests when ready  
