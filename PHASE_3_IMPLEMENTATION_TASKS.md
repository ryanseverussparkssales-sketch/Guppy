# Phase 3: Repo Cleanup & Organization - Implementation Tasks
**Duration:** June 6–12, 2026 (1 week, final sprint)  
**Owner:** Repo Stewardship Team  
**Depends on:** Phase 2 completion (backend infrastructure)  
**Status:** Ready for execution

---

## Phase 3 Summary

Remove technical debt, archive dead code, reorganize directory structure, and finalize documentation. Transform Guppy from a working codebase into a clean, freezeable architecture ready for long-term maintenance and growth.

**Success Criteria:**
- All dead code removed/archived
- Directory structure clean and documented
- No modules > 500 lines (unless explicitly documented)
- Test alignment complete
- Documentation fully current
- dev-check and release-check passing
- Zero unresolved architecture debt markers

---

## Phase 3 Execution (June 6–12)

### Task 1: Dead Code Detection & Removal (June 6–7)

**Subtasks:**

1. **Run architecture audit:**
   ```bash
   python tools/check_architecture_boundaries.py --report
   python tools/check_wrapper_integrity.py --report
   python tools/check_doc_ownership.py --report
   ```
   - Generate comprehensive report of all issues
   - Categorize: dead code, stale imports, orphaned modules, doc drift
   - Priority: high-impact items first

2. **Identify removal candidates:**
   - `compat_shims/legacy_surfaces/` - Quarantine marker only, ready for archival
   - `compat_shims/launcher_ui/` - Qt UI code, replaced by web UI
   - `src/guppy/merlin/` - Already has deprecation warning, not used
   - `.quarantine/` - Intentional archive, clean up README
   - Any `_legacy.py`, `_deprecated.py`, `_compat.py` files still in use

3. **Verify no active references:**
   ```bash
   grep -r "from compat_shims.legacy_surfaces" src/
   grep -r "import.*launcher_ui" src/
   grep -r "from.*merlin" src/
   ```
   - Confirm zero imports from dead code
   - If imports exist, migrate before deletion

4. **Archive and remove:**
   - Move candidates to `.archive/YYYY-MM-DD_PHASE_3/`
   - Document what was archived and why
   - Remove from git tracking
   - Update `.gitignore` if needed
   - Create ARCHIVAL_LOG.md documenting removed items

**Acceptance Criteria:**
- [ ] Architecture audit report complete
- [ ] All dead code identified and categorized
- [ ] No active imports from dead code verified
- [ ] Dead code removed or archived
- [ ] ARCHIVAL_LOG.md created
- [ ] git status shows expected deletions

**Time Estimate:** 1.5 days  
**Owner:** Tech Lead

---

### Task 2: Module Slimming & Reorganization (June 6–8)

**Subtasks:**

1. **Identify large modules:**
   ```bash
   find src -name "*.py" -exec wc -l {} + | sort -rn | head -20
   ```
   - Modules > 500 lines need justification or splitting
   - Known exceptions (documented waivers): launcher_window.py, models_view.py, assistant_view.py
   - Others must be refactored

2. **Split oversized modules:**
   - If a module > 500 lines and no documented waiver:
     - Extract helper classes/functions into new modules
     - Create `_support.py` or `_helpers.py` files
     - Reexport from parent for backward compatibility
     - Document split in module docstring

3. **Example refactoring pattern:**
   ```python
   # OLD: src/guppy/example/large_module.py (600 lines)
   # Split into:
   src/guppy/example/
   ├── large_module.py (200 lines, main logic only)
   ├── large_module_helpers.py (200 lines, helpers)
   ├── large_module_validation.py (150 lines, validation)
   └── __init__.py (reexports main class)
   ```

4. **Domain boundary cleanup:**
   - Ensure each module in `src/guppy/` has clear ownership
   - No cross-domain imports without justification
   - Document domain boundaries in CLAUDE.md
   - Example domains:
     - `api/` - REST API routes only
     - `voice/` - Audio I/O only
     - `backends/` - LLM provider abstraction
     - `workspace_governance/` - Workspace contracts
     - `launcher_application/` - Launcher service layer
     - `experience_config/` - User settings/preferences

**Acceptance Criteria:**
- [ ] No module > 500 lines without documented waiver
- [ ] Each module has clear ownership and docstring
- [ ] Cross-domain imports properly justified
- [ ] Domain boundaries documented
- [ ] Backward compatibility maintained
- [ ] Tests still pass after refactoring

**Time Estimate:** 2 days  
**Owner:** Architecture Lead

---

### Task 3: Test Reorganization & Alignment (June 8–9)

**Subtasks:**

1. **Audit test structure:**
   - Verify `tests/unit/`, `tests/integration/`, `tests/smoke/` directories exist
   - Check for orphaned test files
   - Identify tests with no corresponding source module
   - Identify source modules with no tests

2. **Reorganize test files:**
   ```
   tests/
   ├── unit/
   │   ├── test_backends.py
   │   ├── test_routing.py
   │   ├── test_voice.py
   │   └── ...
   ├── integration/
   │   ├── test_audio_pipeline.py
   │   ├── test_inference_end_to_end.py
   │   └── ...
   ├── smoke/
   │   ├── smoke_api.py
   │   ├── smoke_launcher.py
   │   └── smoke_voice.py
   └── fixtures/ (shared test data)
   ```

3. **Add missing tests:**
   - Modules with < 50% coverage need test additions
   - Focus on happy path + error cases
   - Use fixtures for common setup
   - Document why gaps exist if intentional

4. **Remove stale tests:**
   - Tests that reference deleted modules
   - Tests for deprecated functionality
   - Duplicate tests (if two test same thing)
   - Archive removed tests in `.archive/`

5. **Test documentation:**
   - Create `tests/README.md` explaining structure
   - Document how to run each test suite
   - List known test gaps and reasons
   - List slow tests and workarounds

**Acceptance Criteria:**
- [ ] Test directory structure clean
- [ ] No orphaned test files
- [ ] Coverage baseline established (target > 75%)
- [ ] All tests passing
- [ ] tests/README.md complete
- [ ] Test gaps documented

**Time Estimate:** 1.5 days  
**Owner:** QA Lead

---

### Task 4: Documentation Finalization (June 9–10)

**Subtasks:**

1. **Update core documentation:**
   - `README.md` - Ensure accurate, reflects Phase 1+2 changes
   - `CLAUDE.md` - Update architecture section with final state
   - `docs/PROJECT_BRIEF.md` - Timestamp to June 12, mark P6 complete
   - `docs/LIVE_ARCHITECTURE.md` - Ensure reflects final architecture
   - `docs/BUILD_TRUTH_PATH.md` - Update with final build process

2. **Create new documentation:**
   - `docs/AUDIO_PIPELINE.md` - Link from Phase 1
   - `docs/AUDIO_ONLY_WORKSPACE.md` - User guide, from Phase 1
   - `docs/BACKENDS.md` - Registry, routing, fallback chains (Phase 2)
   - `docs/BACKEND_OPTIMIZATION.md` - SLO tuning per backend (Phase 2)
   - `docs/DIRECTORY_STRUCTURE.md` - Explain src/ organization
   - `docs/MODULE_OWNERSHIP.md` - Domain boundaries, ownership assignments
   - `docs/TESTING_GUIDE.md` - How to run tests, coverage targets
   - `docs/ARCHITECTURE_DECISIONS.md` - Log of major decisions (web UI primary, backend registry, etc.)

3. **Update existing documentation:**
   - `docs/TROUBLESHOOTING.md` - Add audio/backend troubleshooting
   - `docs/PACKAGING.md` - Update with final build process
   - All docstrings in source code - ensure current
   - CONTRIBUTING.md - Add domain ownership rules, test guidelines

4. **Cross-link documentation:**
   - Create docs/INDEX.md with navigation map
   - Ensure no broken links
   - Add "See also" references between docs
   - Add breadcrumbs to each doc (where you are in the hierarchy)

5. **Archive old documentation:**
   - Move outdated docs to `docs/archive/`
   - Create `docs/archive/README.md` explaining what's there
   - Update CLAUDE.md to reference current docs only

**Acceptance Criteria:**
- [ ] All core docs updated and accurate
- [ ] New docs created for Phase 1 & 2 work
- [ ] Domain ownership documented
- [ ] No broken links
- [ ] Old docs archived
- [ ] docs/INDEX.md complete
- [ ] Docs reviewed for clarity and accuracy

**Time Estimate:** 1.5 days  
**Owner:** Technical Writer

---

### Task 5: CLAUDE.md Final Update (June 10)

**Subtasks:**

1. **Update Architecture Overview:**
   ```markdown
   # Guppy: Claude Code Reference
   
   ## Architecture Overview
   
   ### Core Topology (FINAL)
   ```
   Web UI (FastAPI + React) ◄─────────── PRIMARY SURFACE
       ↓
   Desktop Launcher (Qt Wrapper) ◄─────── Optional wrapper
       ↓ (spawns server + opens browser)
       localhost:8080 (FastAPI + React)
               ↓
       Backend Services:
       ├── AudioPipeline (STT/TTS/wake-word)
       ├── BackendRegistry (unified model routing)
       ├── Inference Router (intelligent fallback)
       ├── Workspace Governance (persistence)
       └── Experience Config (settings/persona)
   ```
   ```

2. **Update Key Modules:**
   - Add new modules (audio/*, backends/*, etc.)
   - Remove deprecated modules
   - Update module descriptions with final state
   - Link to new documentation

3. **Update Known Issues:**
   - Remove issues resolved in Phase 1-3
   - Document remaining known issues
   - Explain workarounds if any
   - Link to GitHub issues if applicable

4. **Add Verified Working:**
   - ✅ Audio pipeline with TTS/STT fallback chains
   - ✅ BackendRegistry with 10 backends managed
   - ✅ Unified routing with intelligent fallback
   - ✅ Backend health monitoring dashboard
   - ✅ Audio-only workspace type
   - ✅ Web UI as primary surface
   - ✅ Desktop launcher as wrapper

5. **Update Architecture Seams:**
   - Document final boundaries
   - Explain why each seam exists
   - Link to owned modules
   - Provide integration examples

6. **Add Final Statistics:**
   - Module count: X
   - Test coverage: Y%
   - Doc coverage: Z%
   - Known tech debt: N items (all < 500 lines)

**Acceptance Criteria:**
- [ ] Architecture section completely updated
- [ ] All new modules documented
- [ ] Known issues section current
- [ ] Verified Working section reflects final state
- [ ] Statistics accurate
- [ ] No stale references
- [ ] Document reviewed and approved

**Time Estimate:** 1 day  
**Owner:** Tech Lead

---

### Task 6: Final Verification & Validation (June 11–12)

**Subtasks:**

1. **Run all guardrails:**
   ```bash
   python tools/dev_workflow.py dev-check --guard-scope full
   python tools/dev_workflow.py test-default
   python tools/dev_workflow.py test-smoke
   python tools/dev_workflow.py release-check
   ```
   - All checks must pass
   - Zero warnings (unless documented)
   - Receipt generated

2. **Verify no regressions:**
   - All audio features working (Phase 1)
   - All backends accessible via registry (Phase 2)
   - No dead code imported anywhere
   - All tests passing
   - Documentation builds without errors

3. **Freeze readiness checklist:**
   - [ ] dev-check passes
   - [ ] release-check passes
   - [ ] test-smoke passes
   - [ ] Zero architecture debt markers
   - [ ] All modules < 500 lines (with waivers)
   - [ ] Documentation current and complete
   - [ ] No stale branches or uncommitted changes
   - [ ] CLAUDE.md reflects final state
   - [ ] PROJECT_BRIEF.md marked complete
   - [ ] Video demos present and linked

4. **Create final summary document:**
   - Title: `PHASE_3_COMPLETION_SUMMARY.md`
   - List all items completed
   - List metrics achieved
   - Document lessons learned
   - Provide handoff notes for future work

5. **Create release notes:**
   - Title: `RELEASE_NOTES_2026_06_12.md`
   - Summarize Phase 1-3 work
   - New features (audio pipeline, backend registry, etc.)
   - Breaking changes (none expected)
   - Known limitations
   - Future roadmap

6. **Verify git state:**
   ```bash
   git status  # Should be clean
   git log --oneline -10  # Recent commits healthy
   ```
   - All work committed
   - Branch clean
   - Ready for merge

**Acceptance Criteria:**
- [ ] All guardrails pass
- [ ] No regressions detected
- [ ] Freeze readiness checklist complete
- [ ] Final summary document created
- [ ] Release notes complete
- [ ] git state clean and ready for merge

**Time Estimate:** 1.5 days  
**Owner:** Tech Lead + QA Lead

---

## Cleanup Deliverables by Date

| Date | Deliverable | Owner |
|------|-------------|-------|
| June 6-7 | Dead code removed, ARCHIVAL_LOG created | Tech Lead |
| June 6-8 | All modules < 500 lines (with waivers), domain boundaries documented | Architecture Lead |
| June 8-9 | Test structure reorganized, coverage baseline established | QA Lead |
| June 9-10 | Documentation finalized, new docs created, old docs archived | Technical Writer |
| June 10 | CLAUDE.md fully updated with final state | Tech Lead |
| June 11-12 | All guardrails passing, freeze readiness confirmed | Tech Lead + QA Lead |
| June 12 | Final summary + release notes completed | Tech Lead |

---

## Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Dead code removed | 100% | Pending |
| Modules > 500 lines | 0 (except waivers) | Pending |
| Test coverage | > 75% | Pending |
| Documentation coverage | 100% | Pending |
| dev-check passing | Yes | Pending |
| release-check passing | Yes | Pending |
| Architecture debt items | 0 | Pending |
| Broken doc links | 0 | Pending |

---

## Post-Phase-3 Roadmap

After June 12, Guppy is in a **freezeable state**. Future work can focus on:

1. **Q3 2026:** Performance optimization
   - Batch inference for cost reduction
   - Caching layer for repeated queries
   - Model fine-tuning for specific tasks

2. **Q4 2026:** Feature expansion
   - More backend providers (Llama 2 fine-tunes, etc.)
   - Advanced tool chaining and automation
   - Multi-user workspace support

3. **Beyond:** Long-term stability
   - Regular dependency updates
   - Security audits
   - User feedback integration

---

## Final Notes

**Phase 3 Completion Target:** June 12, 2026  
**Guppy Status After Phase 3:** ✅ PRODUCTION-READY, FREEZEABLE ARCHITECTURE

The codebase will be clean, well-documented, and ready for long-term maintenance and growth.
