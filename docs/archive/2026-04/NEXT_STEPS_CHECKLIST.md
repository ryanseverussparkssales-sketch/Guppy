# Next Steps Checklist — FR-C7 & Beyond

**Status:** FR-C7 Phase 1 ✅ Complete, ready for Phase 2-4  
**Timeline:** All items due by May 19 (FR-C7) and June 11 (FR-C8)

---

## Immediate (This Week)

### Phase 2: Verify Logic Migration
**Plan created:** See `FR-C7_PHASE2_VERIFICATION_PLAN.md` for complete instructions

When ready to execute (suggested Apr 24-29):
- [ ] Run `python tools/dev_workflow.py test-fast`
  - Expected: All connector-related tests pass (10 in test_connector_history_service.py)
  - If fails: Check import errors, see troubleshooting guide
- [ ] Run `python tools/dev_workflow.py test-default` 
  - Expected: Integration tests pass, wrapper pattern verified
  - If fails: Check wrapper function signatures match service exports
- [ ] Run `python tools/dev_workflow.py release-check`
  - Expected: Green across the board (full validation)
  - If fails: See troubleshooting guide in Phase 2 plan

### Verification Tasks
- [ ] Verify wrapper pattern still intact
  - File: `utils/connector_manager.py`
  - Imports from: connector_state_service, connector_action_service, connector_history_service
  - All 6 import sites should work without changes
- [ ] Confirm test file structure
  - File: `tests/unit/test_connector_history_service.py`
  - 10 unit tests, all using mocks
  - Tests: usage_stats, action_history, performance estimation, analytics export

### Documentation
- [ ] Update `NEXT_STEPS_CHECKLIST.md` 
  - Mark Phase 2 complete with test results
  - Update timeline if needed
- [ ] Update `FR-C7_STATUS_2026-04-22.md`
  - Record test results (PASS/FAIL)
  - Note any regressions or new issues
- [ ] Update memory: `execution_status_2026-04-22.md`
  - Record Phase 2 completion date
  - Note any blockers or surprises

---

## Phase 3: Import Updates (By May 6)

### Assessment
- [ ] Review 6 import sites (from Phase 2 grep)
  - Decide: Keep wrapper imports or update?
  - Pattern: If wrapper works, keep; if cleaner, update
- [ ] Document decision for each site
  - Rationale (maintainability, clarity)
  
### Updates (If Needed)
- [ ] Update `src/guppy/api/server_runtime.py`
  - [ ] Change imports if cleaner path exists
  - [ ] Run tests after change
- [ ] Update `src/guppy/launcher_application/services.py`
  - [ ] Same decision logic
- [ ] Update other import sites
  - [ ] Same process: assess → update → test

### Validation
- [ ] All 6 sites still work after updates
- [ ] Tests pass (`test-fast` + `test-default`)
- [ ] `release-check` still green

---

## Phase 4: Deprecation (By May 16)

### Wrapper Deprecation
- [ ] Open `utils/connector_manager.py`
- [ ] Add deprecation docstring at module top
  ```python
  """
  DEPRECATED: Use connector_state_service, connector_action_service, 
  or connector_history_service instead.
  
  This module is maintained for backward compatibility only.
  All new code should use the dedicated services in src.guppy.launcher_application/
  """
  ```
- [ ] Add deprecation imports (optional, but helps IDEs)
  ```python
  import warnings
  warnings.warn(
      "utils.connector_manager is deprecated",
      DeprecationWarning
  )
  ```
- [ ] Update internal comments for clarity

### Verification
- [ ] Run `release-check` — should still pass
- [ ] Verify no new warnings in tests (or only expected deprecation warnings)
- [ ] Confirm backward compatibility maintained

---

## Mid-Stage: FR-C7 Completion (By May 19)

### Final Validation
- [ ] All phases 1-4 complete
- [ ] All tests green
- [ ] Zero regressions
- [ ] Documentation updated

### Success Criteria
- [x] `connector_state_service.py` exists and works
- [x] `connector_action_service.py` exists and works
- [x] `connector_history_service.py` exists and works
- [ ] All new service unit tests pass
- [ ] All integration tests pass
- [ ] No regression in existing tests
- [ ] Only compatibility wrapper remains in `utils/`
- [ ] `utils/connector_manager.py` < 200 lines
- [ ] `release-check` green

### Readiness for FR-C8
- [ ] FR-C7 fully complete and merged
- [ ] All blockers resolved
- [ ] Documentation updated
- [ ] Proceed to FR-C8 planning

---

## FR-LOCAL Integration (Ongoing)

### After Each FR-C Phase
- [ ] Test `build_and_launch.ps1` still works
  - Run command: `pwsh -ExecutionPolicy Bypass -File build_and_launch.ps1`
  - Expected: Web UI loads, API responds, no errors
- [ ] Verify core features
  - [ ] Chat works
  - [ ] Settings load
  - [ ] Model selection works
  - [ ] Workspaces functional
- [ ] Document any issues
  - Report blockers to FR-C lead

### When User Can Access Machine
- [ ] Test FR-LOCAL user experience
- [ ] Verify produced artifacts work
- [ ] Collect feedback
- [ ] Update production reduction guide if needed

---

## FR-C8 Preparation (Start May 19)

### Setup
- [ ] Create `personalization_defaults.py`
  - [ ] Copy template from `FR-C8_PERSONALIZATION_CONFIG_SERVICE_PLAN.md`
  - [ ] Implement all functions
  - [ ] Add docstrings
- [ ] Create `personalization_storage.py`
  - [ ] Same process as defaults
- [ ] Create `personalization_resolution.py`
  - [ ] Same process as storage
- [ ] Create unit tests
  - [ ] Copy test templates from plan
  - [ ] Run and verify all pass

### Integration
- [ ] Phase 2-4 (same as FR-C7)
  - Verify → Import Updates → Deprecate
- [ ] Target completion: June 11

---

## Production Path (After June 12)

### Validation
- [ ] Both tracks complete (FR-LOCAL ✅, FR-C ✅)
- [ ] All tests passing
- [ ] Documentation current
- [ ] User has tested FR-LOCAL

### Deployment Selection
- [ ] Choose deployment model
  - [ ] Docker (recommended, simplest)
  - [ ] Cloud (AWS/GCP/Azure for scale)
  - [ ] Single Binary (for end users)
- [ ] Follow reduction guide in `LOCAL_PRODUCTION_SETUP.md`
  - [ ] Remove dev endpoints
  - [ ] Select production models
  - [ ] Simplify UI
  - [ ] Enable strict auth
- [ ] Deploy and validate

---

## Testing Strategy (Ongoing)

### Before Each Commit
```bash
# Quick check
python tools/dev_workflow.py dev-check --guard-scope delta

# Full validation
python tools/dev_workflow.py test-fast
python tools/dev_workflow.py test-default
python tools/dev_workflow.py release-check
```

### After Each Phase
- [ ] Run full test suite
- [ ] Verify FR-LOCAL still works
- [ ] Check for new warnings/errors
- [ ] Update status documents

### Before Merging to Main
- [ ] `release-check` green
- [ ] All new tests passing
- [ ] No regressions detected
- [ ] Documentation updated
- [ ] Memory files updated

---

## Documentation Maintenance

### After Each Session
- [ ] Update `EXECUTION_STATUS_2026-04-22.md`
- [ ] Update `FR-C7_STATUS_2026-04-22.md`
- [ ] Update memory: `execution_status_2026-04-22.md`
- [ ] Add notes to `MEMORY.md` if new discoveries

### Before Phase Completion
- [ ] Verify plan files match actual work
- [ ] Update timeline with actual dates
- [ ] Document blockers/resolutions
- [ ] Create new phase plan (FR-C8 → FR-C10)

---

## Success Tracking

| Checkpoint | Target Date | Status | Notes |
|------------|-------------|--------|-------|
| FR-C7 Phase 1 | Apr 22 | ✅ Complete | Services created + tests |
| FR-C7 Phase 2 | Apr 29 | ⏳ Pending | Run test suite |
| FR-C7 Phase 3 | May 6 | ⏳ Pending | Update imports if needed |
| FR-C7 Phase 4 | May 16 | ⏳ Pending | Deprecation markers |
| FR-C7 Complete | May 19 | 🎯 Target | All phases done |
| FR-C8 Complete | Jun 11 | 🎯 Target | Services created + tests |
| Freeze Ready | Jun 12 | 🎯 Target | All tranches + audit |

---

## Risk Mitigation

### If Test Suite Fails
1. Check error message carefully
2. Likely causes:
   - [ ] Missing import in test file
   - [ ] Service function signature mismatch
   - [ ] State/mock setup issue
3. Fix approach:
   - Debug specific failure
   - Update service or test
   - Re-run test suite
   - If still broken: Document blocker, escalate

### If Wrapper Pattern Breaks
1. Verify all exports present in connector_manager.py
2. Check import sites still work
3. Re-read wrapper pattern
4. Fix any broken delegations
5. Re-test all 6 import sites

### If Production Reduction Path Unclear
1. Re-read `LOCAL_PRODUCTION_SETUP.md`
2. Reference specific section for your chosen deployment
3. Document any ambiguities
4. Create issue if guidance is wrong

---

## Handoff Checklist (If Task Transferred)

If someone else takes over:
- [ ] Read `FR-C7_CONNECTOR_EXTRACTION_PLAN.md` (strategy)
- [ ] Read `FR-C7_STATUS_2026-04-22.md` (current progress)
- [ ] Review `EXECUTION_STATUS_2026-04-22.md` (big picture)
- [ ] Check `CLAUDE.md` for architecture context
- [ ] Run `python tools/dev_workflow.py test-fast` to verify baseline
- [ ] Ask questions about blockers or unclear items

---

## Current Status Summary

✅ **Completed:**
- FR-C7 Phase 1: Services created, tests written
- FR-LOCAL: One-command setup ready

🔄 **In Progress:**
- FR-C7 Phase 2-4: Verification, import updates, deprecation

⏳ **Pending:**
- FR-C8: Personalization config extraction
- FR-C10: Freeze audit

🎯 **June 12 Target:**
- All tranches landed and verified
- Codebase freeze-ready
- User has usable local + production path

---

**Last Updated:** 2026-04-22  
**Next Checkpoint:** Phase 2 test results  
**Escalation Contact:** Review CLAUDE.md for architecture questions
