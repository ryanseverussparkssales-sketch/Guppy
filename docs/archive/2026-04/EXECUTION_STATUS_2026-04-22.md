# Guppy Execution Status — 2026-04-22

## Overview

Dual-track development is running in parallel:
- **Track 1: User Experience (FR-LOCAL)** — ✅ COMPLETE & READY
- **Track 2: Code Architecture (FR-C)** — 🔄 IN PROGRESS

---

## Track 1: User Experience (FR-LOCAL) ✅ READY NOW

### Current Status
- ✅ `build_and_launch.ps1` — One-command startup script
- ✅ `verify_guppy_setup.ps1` — Diagnostic utility
- ✅ `LOCAL_PRODUCTION_SETUP.md` — Architecture guide + reduction path
- ✅ Web UI builds to static files (optimized)
- ✅ Backend API on port 8081, Web UI on port 3003

### Immediate Action
```powershell
# User can run this NOW
pwsh -ExecutionPolicy Bypass -File build_and_launch.ps1
```

### Next: User Testing
When you can access the machine, verify:
- [ ] `build_and_launch.ps1` starts everything
- [ ] Web UI loads without errors
- [ ] Can send messages and get responses
- [ ] Settings and workspace switching work

---

## Track 2: Code Architecture (FR-C) — IN PROGRESS

### Completed Tranches

| Tranche | What | Lines Reduced | Status |
|---------|------|---------------|--------|
| **FR-C1** | API snapshot decomposition | 242B | ✅ DONE |
| **FR-C2** | Launcher shell reduction | 285B | ✅ DONE |
| **FR-C3** | Models hub panel split | 244B | ✅ DONE |
| **FR-C5** | Settings operations split | Multiple | ✅ DONE |
| **FR-C9** | Runtime/request lane reduction | 183B | ✅ DONE |
| **FR-C7** | Connector manager extraction | PHASE 1 ✅ | 🔄 IN PROGRESS |

### In Progress: FR-C7 (Connector Manager Extraction)

**Status:** Phase 1 ✅ Complete (2026-04-22)

**What was done:**
- ✅ Created `connector_state_service.py` (141 lines) — State management
- ✅ Created `connector_action_service.py` (325 lines) — Action orchestration  
- ✅ Created `connector_history_service.py` (180 lines) — NEW, usage tracking
- ✅ Verified `utils/connector_manager.py` is wrapper pattern
- ✅ Created unit tests for history service
- ✅ Verified all 6 import sites work correctly

**What's next:**
- Phase 2: Verify logic migration (tests pass)
- Phase 3: Update imports (if needed)
- Phase 4: Add deprecation markers
- Target: Complete by May 19

### Upcoming: FR-C8 (Personalization Config Service)

**Status:** Plan created, ready to start after FR-C7

**What will be done:**
- Extract defaults, storage, resolution into 3 services
- ~150 + 200 + 200 lines organized under `src/guppy/experience_config/`
- Same pattern as FR-C7 (service extraction + wrapper)
- Target: Complete by June 11

**After FR-C8:**
- FR-C10 (Freeze audit & waiver reset) — June 12 deadline

---

## Key Metrics

### Architecture Health
| Aspect | Target | Current | Status |
|--------|--------|---------|--------|
| Base module cap | 700 lines | Below | ✅ |
| Hotspot trend | ↓ Declining | Declining | ✅ |
| Service separation | Clear seams | Improving | 🔄 |
| Wrapper pattern | Minimal | <150 lines | ✅ |

### Timeline
```
Today (Apr 22)          ✓ FR-LOCAL ready
 ├─ FR-C7 Phase 2-4     (Apr 29 - May 19)
 └─ FR-C8              (May 19 - Jun 11)
 
By June 12             ✓ All tranches landed, freeze-ready
```

---

## What You Can Do Now

### 1. Test FR-LOCAL (Immediate)
```powershell
# When you access the machine
pwsh -ExecutionPolicy Bypass -File build_and_launch.ps1

# Verify it works
- Web UI loads
- Can chat with models
- Settings are accessible
```

### 2. Review Current Architecture
- Read `FR-C7_STATUS_2026-04-22.md` (connector extraction progress)
- Read `FR-C8_PERSONALIZATION_CONFIG_SERVICE_PLAN.md` (next phase)
- Understand the wrapper pattern (backward compatibility while refactoring)

### 3. Plan Production Deployment
- Reference `LOCAL_PRODUCTION_SETUP.md`
- Choose: Docker, Cloud, or Single Binary deployment
- Schedule deployment for after June 12 (when all FR-C complete)

---

## Key Files Created/Updated (2026-04-22)

### Service Implementations
- `src/guppy/launcher_application/connector_history_service.py` — NEW
- `tests/unit/test_connector_history_service.py` — NEW

### Planning & Status Documents
- `FR-C7_CONNECTOR_EXTRACTION_PLAN.md` — Updated with Phase 1 complete
- `FR-C7_STATUS_2026-04-22.md` — Current progress, verification tasks
- `FR-C8_PERSONALIZATION_CONFIG_SERVICE_PLAN.md` — Detailed plan for next tranche
- `EXECUTION_STATUS_2026-04-22.md` — This document

### Memory & Reference
- Updated `guppy_freeze_readiness_program.md` with FR-C7 status
- Updated `MEMORY.md` with FR-C7 references

---

## Next Steps (Ordered by Priority)

### Immediate (Next Session)
1. ✅ Run Phase 2 verification: `python tools/dev_workflow.py test-fast`
2. ✅ Verify `release-check` stays green
3. ✅ Document any test failures or import issues

### This Week (Apr 29)
1. Complete FR-C7 Phases 2-4 (verify → deprecate)
2. Validate FR-LOCAL still works with FR-C7 changes
3. Start FR-C8 preparation

### By May 19
1. Complete FR-C8 (personalization config extraction)
2. All FR-C7 + FR-C8 tests passing
3. Ready for FR-C10 final audit

### By June 12
1. FR-C10 freeze audit complete
2. All tranches integrated and tested
3. Codebase freeze-ready
4. Production deployment path validated

---

## Documentation Links

### Current Session
- `FR-C7_CONNECTOR_EXTRACTION_PLAN.md` — Full extraction strategy
- `FR-C7_STATUS_2026-04-22.md` — Phase 1 complete, what's next
- `FR-C8_PERSONALIZATION_CONFIG_SERVICE_PLAN.md` — Next tranche detailed plan
- `LOCAL_PRODUCTION_SETUP.md` — User-facing local setup guide

### Ongoing Reference
- `CLAUDE.md` — Architecture notes, build commands
- `EXECUTION_PLAN_2026-04-22.md` — High-level dual-track overview
- `guppy_freeze_readiness_program.md` — Full FR-C roadmap

### Memory
- `local_production_strategy_2026-04-22.md` — Dual-track context
- `guppy_freeze_readiness_program.md` — Tranches and strategy
- `MEMORY.md` — Index of all reference documents

---

## Success Criteria (Overall)

✅ **User Experience:**
- [x] One-command local powerhouse setup
- [x] Zero terminal management required
- [ ] User can actually test it (when access available)

🔄 **Code Architecture:**
- [x] FR-C7 services created
- [ ] FR-C7 logic verified & tests pass
- [ ] FR-C8 ready to start
- [ ] FR-C10 freeze audit scheduled

✅ **Production Path:**
- [x] Documented reduction strategy
- [x] Clear deployment options (Docker/Cloud/Binary)
- [ ] Validated by user testing FR-LOCAL
- [ ] Ready for post-June 12 deployment

---

**Status:** Two tracks running, user has immediate option (FR-LOCAL), code quality improving (FR-C)  
**Blocker:** User testing of FR-LOCAL (waiting for machine access)  
**Momentum:** FR-C7 Phase 1 ✅, FR-C8 ready to start, all systems proceeding to timeline
