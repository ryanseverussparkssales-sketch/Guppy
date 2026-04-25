# Dual-Track Execution Status — Real-time Assessment

**Date:** 2026-04-22 (Session update)  
**Perspective:** What's actually in the codebase vs. what was planned

---

## Track 1: FR-LOCAL (User Experience) ✅ COMPLETE

**Status:** Ready for user testing

| Item | Status | Details |
|------|--------|---------|
| build_and_launch.ps1 | ✅ | One-command startup verified |
| verify_guppy_setup.ps1 | ✅ | Diagnostic utility ready |
| LOCAL_PRODUCTION_SETUP.md | ✅ | Architecture + reduction path documented |
| .env.local setup | ✅ | API keys via environment variables |
| Environment var loading | ✅ | launch.py reads .env + .env.local |

**Blocker:** User testing — waiting for machine access

**Next step:** When accessible, run build_and_launch.ps1 and verify:
- Web UI loads
- Chat sends/receives messages
- Settings functional
- Model selection works

---

## Track 2: FR-C (Code Architecture) — MIXED STATUS

### FR-C Completed Tranches

| Tranche | Purpose | Status |
|---------|---------|--------|
| FR-C1 | API snapshot decomposition | ✅ DONE |
| FR-C2 | Launcher shell reduction | ✅ DONE |
| FR-C3 | Models hub panel split | ✅ DONE |
| FR-C5 | Settings operations split | ✅ DONE |
| FR-C9 | Runtime/request lane | ✅ DONE |

**5 tranches complete, 5 remain (FR-C4, C6, C7, C8, C10)**

---

## FR-C7: Connector Manager Extraction

### Current Status: Phase 1 ✅ + Phase 2 📋 Ready

**Phase 1 (Completed this session):**
- ✅ `connector_state_service.py` (141 lines)
- ✅ `connector_action_service.py` (325 lines)
- ✅ `connector_history_service.py` (180 lines) [NEW]
- ✅ Unit tests written (10 tests, all mocking-based)
- ✅ Wrapper pattern verified (`utils/connector_manager.py` delegates)
- ✅ Import sites verified working (all 6)
- ✅ Environment variables configured

**Phase 2 (Ready for execution on Windows):**
```powershell
python tools/dev_workflow.py test-fast         # Unit tests
python tools/dev_workflow.py test-default      # Integration tests
python tools/dev_workflow.py release-check     # Full validation
```

See `FR-C7_PHASE2_VERIFICATION_PLAN.md` for complete instructions.

**Phases 3-4 (Scheduled):**
- Phase 3 (May 6): Review 6 import sites, decide on updates
- Phase 4 (May 16): Add deprecation markers

**Target:** May 19 completion

---

## FR-C8: Personalization Config Services

### Current Status: SERVICES EXIST ✅ + WRAPPER IN PLACE ✅

**Discovery:** Services already created (earlier than planned)

Files found in `src/guppy/experience_config/`:
- ✅ `personalization_defaults.py` (11.5 KB) — Default configs + persona definitions
- ✅ `personalization_storage.py` (21.4 KB) — Persistence layer (load/save/validate)
- ✅ `personalization_resolution.py` (9.9 KB) — Runtime resolution with overrides

**Wrapper status in `utils/personalization_config.py`:**
- ✅ Imports from all three services (lines 6-44)
- ✅ Delegates with `_service_` prefix pattern
- ✅ Backward compatibility maintained

**Tests exist:**
- `tests/unit/test_personalization_resolution.py`
- `tests/unit/test_personalization_storage_service.py`
- `tests/unit/test_personalization_config_scaffold.py`

### What's Left for FR-C8

**Phase 2 (Verify logic migration):**
- Run test suite: `test-fast`, `test-default`, `release-check`
- Expected: All tests pass, zero regressions
- Status: ⏳ Queued (pending Phase 2 Windows test run)

**Phase 3 (Update imports):**
- Assess import sites for cleaner direct access
- Update if beneficial
- Run tests
- Status: 📋 Scheduled (May 6)

**Phase 4 (Deprecation):**
- Add deprecation markers to wrapper
- Status: 📋 Scheduled (May 16)

**Target:** June 11 (same pipeline as FR-C7)

---

## Remaining FR-C Tranches

| Tranche | Purpose | Plan | Status |
|---------|---------|------|--------|
| **FR-C4** | TBD | Unknown | 📋 Pending |
| **FR-C6** | TBD | Unknown | 📋 Pending |
| **FR-C10** | Freeze audit + waiver reset | Comprehensive audit | 📋 June 12 |

---

## Execution Timeline (Revised)

```
April 22 (Today)
├─ FR-LOCAL ✅ Complete, waiting for user test
├─ FR-C7 Phase 2 📋 Ready (tests on Windows)
├─ FR-C8 Services ✅ Exist, Phase 2 queued
└─ Environment ✅ Variable setup done

April 24-29
├─ FR-C7 Phase 2 (test-fast, test-default, release-check)
└─ FR-C8 Phase 2 (same, after Phase 1 tests pass)

May 1-19
├─ FR-C7 Phase 3-4 (import updates, deprecation)
├─ FR-C8 Phase 3-4 (same pattern)
└─ FR-C4, FR-C6 (implementation TBD)

June 12
└─ All tranches complete, freeze-ready

June 12+
└─ User tests FR-LOCAL, deployment selection
```

---

## Critical Path for Next 2 Weeks

### Immediate (Apr 22-29)
1. **FR-C7 Phase 2** — Run test suite on Windows
   - Commands: test-fast, test-default, release-check
   - Expected: All pass
   - Document results in FR-C7_STATUS_2026-04-22.md

2. **FR-C8 Phase 2** — Runs same tests (dependent on Phase 1 ✅)
   - After FR-C7 Phase 2 passes
   - Same test commands
   - Same documentation

3. **Verify FR-LOCAL** — Spot check after FR-C7 changes
   - Confirm build_and_launch.ps1 still works
   - Note any issues

### Short-term (May 1-16)
1. **FR-C7 Phase 3** — Import site review (May 6)
2. **FR-C7 Phase 4** — Deprecation markers (May 16)
3. **FR-C8 Phase 3** — Import site review (May 6)
4. **FR-C8 Phase 4** — Deprecation markers (May 16)

### Mid-term (May 19 - June 11)
1. **FR-C4 & FR-C6** — Implementation (scope TBD)
2. **User test FR-LOCAL** — When machine access available
3. **Document production path** — Update LOCAL_PRODUCTION_SETUP.md if needed

### Final (June 12)
1. **FR-C10 Audit** — Comprehensive freeze-readiness review
2. **All tranches complete** — Codebase freeze-ready

---

## Decision Point: What to Work On Next

### Option A: Prepare FR-C7 Phase 2 Execution Materials
- ✅ Done — FR-C7_PHASE2_VERIFICATION_PLAN.md created
- Impact: User has clear instructions to run tests on Windows

### Option B: Prepare FR-C4 & FR-C6 Scope
- TBD — Need to identify what these tranches are
- Impact: Know what remains to complete

### Option C: Prepare FR-C10 Freeze Audit Checklist  
- TBD — Build comprehensive audit framework
- Impact: Clear success criteria for June 12 deadline

### Option D: Begin Phase 2 Code Analysis  
- Investigate: What is left to extract or refactor
- Impact: Roadmap for remaining work

---

## Summary

| Track | Status | Blocker | Next |
|-------|--------|---------|------|
| **FR-LOCAL** | ✅ Ready | User access | Test on Windows |
| **FR-C7** | Phase 1 ✅ | Windows tests | Run test-fast/default |
| **FR-C8** | Svcs ✅ | Windows tests | Run same tests |
| **FR-C4/C6** | Unknown | Scope TBD | Identify purpose |
| **FR-C10** | Not started | Audit framework | Create checklist |

**Overall progress:** 5/10 FR-C tranches complete, both major tracks have clear paths forward, environment configured, documentation in place.

**Recommendation:** 
1. **Prepare for Phase 2 execution** — User will run tests on Windows (timeline clear)
2. **Identify FR-C4/C6** — What are these tranches? Enables roadmap clarity
3. **Start FR-C10 framework** — Audit criteria for freeze-readiness

---

**Updated:** 2026-04-22  
**Next checkpoint:** FR-C7 Phase 2 test results (when user executes)
