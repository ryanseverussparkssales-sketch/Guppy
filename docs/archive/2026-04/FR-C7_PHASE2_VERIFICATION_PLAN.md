# FR-C7 Phase 2: Logic Migration Verification

**Status:** Ready to execute (2026-04-22)  
**Target Completion:** Apr 29, 2026  
**Prerequisites:** All Phase 1 services created ✅, Unit tests written ✅

---

## What Phase 2 Does

Phase 2 verifies that the connector manager extraction is logically sound by running the full test suite. This ensures:
1. All new services work correctly in isolation (unit tests)
2. Connector logic works when integrated with the wrapper pattern (integration tests)
3. No regressions in existing connector functionality (regression tests)
4. Build system still passes validation (release-check)

---

## Execution Plan

### Step 1: Quick Unit Test Check (5 min)

Run the fast unit test suite to verify connector-related tests pass:

```powershell
cd C:\Users\Ryan\Guppy
python tools/dev_workflow.py test-fast
```

**Expected outcome:**
- All connector-related tests pass
- No import errors
- test_connector_history_service.py runs cleanly (10 tests)

**If it fails:**
- Check error message for import errors
- Common issues:
  - Missing `from __future__ import annotations` in test file
  - Test file not in `tests/unit/` directory
  - Missing function exports in service files
- Fix and re-run

---

### Step 2: Full Integration Test (10 min)

Run integration tests to verify connector logic works end-to-end:

```powershell
python tools/dev_workflow.py test-default
```

**Expected outcome:**
- All unit tests pass
- All integration tests pass
- No wrapper pattern breakage
- All 6 import sites work correctly

**If it fails:**
- Review error output for which integration test failed
- Likely causes:
  - Wrapper function signature mismatch
  - Missing service export
  - State management issue
- Update the failing service or integration test
- Re-run

---

### Step 3: Release Validation (10 min)

Run the full release-check to ensure nothing broke:

```powershell
python tools/dev_workflow.py release-check
```

**Expected outcome:**
- All tests pass (unit + integration)
- No warnings or deprecation issues yet (Phase 4 adds those)
- Build validation succeeds
- Zero regressions

**If it fails:**
- Check if it's a new warning or existing issue
- If new: Debug what Phase 1 changes caused it
- If existing: Document as pre-existing blocker
- Report in NEXT_STEPS_CHECKLIST.md §Risk Mitigation

---

## Phase 2 Success Criteria

✅ **All checks:**
- [ ] test-fast passes (all unit tests green)
- [ ] test-default passes (all integration tests green)
- [ ] release-check passes (full validation green)
- [ ] No new regressions detected
- [ ] All 6 import sites confirmed working

✅ **Connector history service:**
- [ ] get_usage_stats() returns correct stats format
- [ ] get_action_history() respects limit and ordering
- [ ] estimate_connector_performance() classifies correctly (healthy/degraded/failing)
- [ ] export_analytics() handles date ranges properly

✅ **Wrapper pattern:**
- [ ] connector_manager.py imports all services correctly
- [ ] All wrapper functions delegate to services
- [ ] Backward compatibility maintained

---

## What to Document

After Phase 2 completes, update these files:

### 1. NEXT_STEPS_CHECKLIST.md
- Mark Phase 2 as complete
- Note any issues that came up
- Update timeline if needed

### 2. FR-C7_STATUS_2026-04-22.md
- Record test results:
  - test-fast: PASS/FAIL
  - test-default: PASS/FAIL
  - release-check: PASS/FAIL
- Note any warnings or regressions
- Confirm wrapper pattern still works

### 3. execution_status_2026-04-22.md (memory)
- Update Phase 2 status
- Note any blockers
- Record timestamp of completion

### 4. CLAUDE.md
- If new warnings added: document them
- If new test patterns emerged: add notes
- If regressions found: add to "Known Issues & TODOs"

---

## Troubleshooting

### "ModuleNotFoundError: No module named connector_history_service"
**Cause:** Test file can't find the service
**Fix:**
1. Verify file exists: `src/guppy/launcher_application/connector_history_service.py`
2. Verify `__init__.py` exports the functions (or pytest autodiscovers)
3. Check test import path matches file location

### "AssertionError in test_get_usage_stats_with_history"
**Cause:** Service function returns unexpected format
**Fix:**
1. Review expected vs. actual output in test
2. Check function in connector_history_service.py
3. Verify calculation logic (e.g., success_rate = successful / total)
4. Update test if spec changed, or service if logic wrong

### "release-check fails but test-fast/test-default pass"
**Cause:** Build system or linting issue, not test logic
**Fix:**
1. Check full error output (typically formatting, import order, etc.)
2. Most common: import order or line length
3. Run `python tools/dev_workflow.py dev-check --guard-scope delta` for quick local fix
4. Fix and re-run

### "Wrapper pattern broken: import site X fails"
**Cause:** Wrapper function doesn't delegate correctly
**Fix:**
1. List the 6 import sites:
   - `src/guppy/api/server_runtime.py`
   - `src/guppy/launcher_application/services.py`
   - (4 others from Phase 2 grep)
2. Verify each import still works
3. Check wrapper function signatures match service signatures
4. Test one import site directly: `from utils.connector_manager import <func>; <func>(...)`

---

## Next Steps After Phase 2

Once Phase 2 verification completes:

1. **Phase 3 (May 6):** Review 6 import sites
   - Decide: Keep wrapper imports or update?
   - Document decision and rationale

2. **Phase 4 (May 16):** Add deprecation markers
   - Mark utils/connector_manager.py as deprecated
   - Add warnings to wrapper functions

3. **FR-C7 Completion (May 19):** Merge and document
   - All tests passing
   - No regressions
   - Wrapper pattern complete

---

## Quick Command Reference

```powershell
# Navigate to repo
cd C:\Users\Ryan\Guppy

# Run all three Phase 2 checks in sequence
python tools/dev_workflow.py test-fast
python tools/dev_workflow.py test-default
python tools/dev_workflow.py release-check

# Or run a quick sanity check before full tests
python tools/dev_workflow.py dev-check --guard-scope delta

# Verify wrapper pattern manually
python -c "from utils.connector_manager import load_state; print('Wrapper import OK')"
```

---

**Phase 2 is automated and deterministic.** All test results are either PASS or FAIL with clear error messages. No subjective judgment required — just execute the commands and document the results.

**Once Phase 2 passes,** proceed immediately to Phase 3 (import assessment) on 2026-05-06.
