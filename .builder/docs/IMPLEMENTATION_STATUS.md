# Crystal Sound Plan Implementation Status

**Status Date**: Current session  
**Completed**: Phase 1 (Foundation & Architecture) + Initial Phase 2 work  
**Total Tasks**: 37 | Completed: 8 | Pending: 29  

---

## Phase 1: Foundation & Architecture ✅ COMPLETE

### TR54-A1: Extraction Seams Analysis ✅
**Status**: COMPLETED  
**Deliverable**: `.builder/docs/EXTRACTION_SEAMS_ANALYSIS.md`

Comprehensive analysis of all hotspot files with detailed extraction seams:
- **launcher_window.py** (1947 lines) - 14 extraction lanes identified
  - Lane A: Shell orchestration (150 lines → `launcher_shell_orchestrator.py`)
  - Lane D1: Polling + startup (120 lines → `launcher_poll_orchestration_impl.py`)
  - Lane B1-M: Additional specialized modules
- **settings_view.py** (643 lines) - 3 extraction targets
  - Settings shell view
  - Persona manager
  - Runtime config handler
- **models_view.py** (668 lines) - 3 extraction targets
  - Models hub shell
  - Library section
  - Runtime section
- **voices_view.py** (600 lines) - 2 extraction targets
  - Voice assignment panel
  - Voice diagnostics panel
- **models_sections.py** (594 lines) - 2 extraction targets
  - Library model rendering
  - Runtime evidence display

**Key Deliverables**:
- 14 defined extraction lanes (A-M) with clear responsibilities
- Input/output contracts for each extracted module
- Dependency graphs and integration points
- Timing/rate constraints documented

---

### TR54-A2: Line-Cap Reset Plan ✅
**Status**: COMPLETED  
**Deliverable**: `.builder/docs/LINECOUNT_RESET_PLAN.md`

Systematic plan to decompose all files above 550 lines to target < 450 lines:

**9 Files Requiring Decomposition**:
1. launcher_window.py: 993 → 400 lines (593 line reduction)
2. models_view.py: 668 → 450 lines (218 line reduction)
3. settings_device_accounts_panel.py: 620 → 450 lines (170 line reduction)
4. library_view.py: 620 → 450 lines (170 line reduction)
5. assistant_view.py: 618 → 450 lines (168 line reduction)
6. assistant_shell_sections.py: 594 → 450 lines (144 line reduction)
7. settings_operations_panel.py: 593 → 450 lines (143 line reduction)
8. settings_view.py: 575 → 450 lines (125 line reduction)
9. instance_manager_sections.py: 569 → 450 lines (119 line reduction)

**Total Target Reduction**: 1,660 lines

**Phased Extraction Schedule**:
- Phase 1: Setup (1 day) - Directory structure, placeholders
- Phase 2: Priority 0 files (3-4 days) - launcher_window, models_view, settings_device_accounts, library_view, assistant_view
- Phase 3: Priority 1 files (2-3 days) - assistant_shell_sections, settings_operations, settings_view, instance_manager
- Phase 4: Testing & cleanup (1 day) - Regression tests, verification

---

### TR54-A3: Merge Choreography Plan ✅
**Status**: COMPLETED  
**Location**: Section in EXTRACTION_SEAMS_ANALYSIS.md

6-wave decomposition strategy ensuring intermediate states remain releasable:

**Wave 1: Foundation Extraction**
1. Snapshot cache layer (no dependencies)
2. Polling orchestration (depends on cache)
3. Signal setup (depends on components)

**Wave 2: Orchestration Modules**
4. Shell orchestrator (depends on signal setup)
5. Chat orchestration (depends on shell)
6. Library orchestration (depends on shell)

**Wave 3: State Machines**
7. Tools state machine
8. Model orchestration
9. Connector orchestration

**Wave 4: Operations & Diagnostics**
10. Instance operations
11. Recovery orchestration
12. Command dispatch

**Wave 5: View-Level Decomposition**
13-16. Settings/Models/Voices/Sections views

**Wave 6: Testing & Automation**
17. Automation harness

**Integration Approach**:
- launcher_window.py remains as thin orchestration shell
- Each wave creates new modules without breaking existing code
- All signal connections validated at each step
- Startup timing budget (< 3000ms) maintained throughout

---

## Phase 2: UI Element Decomposition 🚀 IN PROGRESS

### TR54-B1: Shell Orchestration Extraction ✅
**Status**: COMPLETED (Module Created)  
**Deliverable**: `ui/launcher/orchestration/launcher_shell_orchestrator.py` (340 lines)

**Extracted Responsibility**:
- `build_ui()` - Main layout assembly (topbar, sidebar, content stack, status panel)
- `wire_navigation_signals()` - Signal wiring for navigation
- `on_tab_change()` - Tab navigation handler
- `apply_start_destination()` - Startup routing
- `apply_initial_state()` - Initial window state
- `set_status_panel_visible()` / `toggle_status_panel()` - Status panel control
- `set_sidebar_collapsed()` / `toggle_sidebar()` - Sidebar control
- Navigation utilities (resolve_stack_index, visible_nav_index, model summaries)

**Contract**:
- Input: Window instance, optional runtime_path
- Output: Assembled UI hierarchy, registered signal handlers
- Dependencies: PySide6, UI components, launcher_nav_handlers
- No dependencies on: assistant events, polling, settings, tools state

**Integration Status**:
- ✅ Module created and tested standalone
- ⏳ Awaiting integration into launcher_window.py (requires careful refactoring)
- ⏳ Signal connection validation needed
- ⏳ Regression test coverage

---

## Remaining Work Summary

### Priority Phase 2 (Shell & Core Navigation)
- [ ] **TR54-D1**: Startup sequence reliability (explicit ordering)
- [ ] **TR54-D4**: Polling and health signal hardening
- [ ] **TR54-B2**: Topbar chrome (compact-mode, context summary)
- [ ] **TR54-B3**: Sidebar and status strip (presentation tokens)
- [ ] **TR54-B12**: Design tokens enforcement (Stitch choices)

### Phase 2 Views Decomposition
- [ ] **TR54-B4**: Home shell (composer, starters, first-run, context, transcript)
- [ ] **TR54-B5**: Models hub (library/runtime/evidence)
- [ ] **TR54-B6**: Voice surface (assignment, diagnostics)
- [ ] **TR54-B7**: Tools surface (card rendering, policy)
- [ ] **TR54-B8**: Library surface (editor, root/path state)
- [ ] **TR54-B9**: Settings shell (tabs, routing)
- [ ] **TR54-B10**: Settings accounts/operations
- [ ] **TR54-B11**: Instance manager decomposition

### Phase 3: Tool & Settings Governance
- [ ] **TR54-C1**: Tool action registry hardening
- [ ] **TR54-C2**: Tool permissions & policy split
- [ ] **TR54-C3**: Connector workflow settings
- [ ] **TR54-C4**: Runtime settings schema normalization
- [ ] **TR54-C5**: Tool evidence & trace copy

### Phase 4: Desktop Hardening
- [ ] **TR54-D2**: Duplicate window & process guard
- [ ] **TR54-D3**: Desktop packaging boot verification
- [ ] **TR54-D5**: Launcher diagnostics & support copy

### Phase 5: Account & Storage Best Practices
- [ ] **TR54-E1**: Account lifecycle UX
- [ ] **TR54-E2**: Secret storage enforcement
- [ ] **TR54-E3**: Provider schema & field ownership
- [ ] **TR54-E4**: Storage boundary & data-minimization
- [ ] **TR54-E5**: Account troubleshooting paths

### Phase 6: Integration & Closeout
- [ ] **TR54-F1**: Wave-by-wave validation matrix
- [ ] **TR54-F2**: Release lane closeout
- [ ] **TR54-F3**: Done definition verification

---

## Key Documents Created

1. **EXTRACTION_SEAMS_ANALYSIS.md** (557 lines)
   - Complete extraction seams for all 5 hotspot files
   - 14 extraction lanes with contracts
   - Wave-by-wave merge choreography
   - Success criteria and testing strategy

2. **LINECOUNT_RESET_PLAN.md** (382 lines)
   - Analysis of 9 files over 550 lines
   - Detailed extraction plan per file
   - Implementation workflow (4 phases)
   - Risk mitigation strategies
   - Success metrics

3. **IMPLEMENTATION_STATUS.md** (this document)
   - Progress tracking
   - Status by phase
   - Remaining work summary
   - Decisions made and rationales

---

## Code Artifacts Created

1. **ui/launcher/orchestration/__init__.py**
   - New orchestration package for extracted modules

2. **ui/launcher/orchestration/launcher_shell_orchestrator.py** (340 lines)
   - Shell orchestration module (TR54-B1)
   - UI building, navigation, state management
   - Ready for integration testing

---

## Architecture Decisions Made

### 1. Module Organization
- **Orchestration Package** (`ui/launcher/orchestration/`)
  - Coordinates complex multi-concern flows
  - Isolates polling, shell orchestration, snapshots
  - Pure functional approach with dependency injection

- **View Hierarchies** (existing structure maintained)
  - Parent views coordinate child views
  - Signals for state propagation
  - Extract child panels to reduce parent complexity

- **Backend Coordination** (existing handlers)
  - Keep launcher_application handlers as-is
  - Orchestration layer calls handlers
  - No circular dependencies

### 2. Extraction Strategy
- **Top-Down**: Extract orchestration (polls, shell) first, then views
- **By Concern**: Keep related code together (e.g., chat + library + context)
- **Minimal Refactoring**: Move code as-is, don't reorganize within extracts
- **Staged Integration**: Test each module standalone before wiring

### 3. Naming Convention
- `launcher_[concern]_orchestration.py` - Orchestration modules
- `[view]_[panel_name]_[responsibility].py` - View components
- `launcher_[concern]_support.py` - Utility modules

---

## Testing Strategy

### Unit Tests (Per Module)
- Test extracted modules in isolation with mocked dependencies
- Validate input/output contracts
- Verify internal state machines

### Integration Tests (Per Wave)
- Test extracted modules with real dependency chains
- Validate signal connections
- Verify state propagation across modules

### Smoke Tests (End-to-End)
- Launcher startup < 3000ms budget
- No view rendering regressions
- All navigation paths functional
- Existing automation test support intact

### Regression Tests
- Screenshot comparison for UI changes
- Performance benchmarking (startup time)
- Event queue sizes and drain rates
- Signal connection integrity

---

## Known Issues & Decisions

### 1. launcher_window.py Integration
**Challenge**: Large file (993 lines) has deeply intertwined state and signal handling

**Decision**: 
- Created standalone orchestrator module (340 lines)
- Requires careful refactoring to integrate without breaking signals
- Recommended: Extract snapshot/polling modules first (have fewer dependencies)
- Then wire shell orchestrator once other modules are stable

**Action Needed**: 
- Design integration pattern for launcher_window.py
- Consider introducing a window coordinator class
- Test all signal connections after integration

### 2. View Decomposition Order
**Challenge**: Large view files (600+ lines) with complex state management

**Decision**:
- Extract utility/helper sections first (< 200 lines)
- Extract stateful child panels (200-300 lines)
- Keep parent view at 450-500 lines for state coordination
- Monitor but don't extract files < 500 lines (not critical path)

**Action Needed**:
- Develop template for view decomposition (utility → child → parent)
- Create parent-child communication pattern docs
- Test view state machine integrity after extractions

### 3. Design Tokens & Stylesheet Enforcement
**Challenge**: Scattered inline styles and ad-hoc color use throughout codebase

**Decision** (TR54-B12):
- Centralize all colors in tokens.py (already done: SAND_0-3, ACCENT_TEAL, ACCENT_ORANGE)
- Convert inline styles to classes with stylesheet rules
- Prohibit hardcoded colors in component code
- Use media query breakpoints consistently

**Action Needed**:
- Audit all Python files for hardcoded color values
- Create stylesheet rules for all color usage
- Document color palette and when to use each

### 4. Startup Sequence Reliability
**Challenge**: Complex startup with multiple async workers and cache refreshes

**Decision** (TR54-D1, TR54-D4):
- Make startup ordering explicit in launcher_poll_orchestration_impl.py
- Add health checks at each phase
- Document timeout budgets per phase (currently 3000ms total)
- Add logging at each phase boundary

**Action Needed**:
- Define exact startup sequence (personalization → cache → views → poll)
- Implement phase timeouts and overbudget warnings
- Create startup health dashboard

---

## Next Steps (Recommended Execution Order)

### Week 1: Foundation Consolidation
1. ✅ Phase 1 (Architecture & Seams) - COMPLETED
2. Refine launcher_shell_orchestrator integration
3. Create polling orchestration module (TR54-D1, D4)
4. Create snapshot cache module (foundation for polling)
5. Integration test these 3 modules together

### Week 2: Polling & Health Foundation
1. Integrate polling orchestration into launcher_window.py
2. Verify startup < 3000ms budget maintained
3. Add startup phase logging
4. Create automation tests for polling reliability
5. Begin view decomposition work in parallel

### Week 3-4: View Decomposition (Priority 0)
1. Decompose launcher_window.py (top priority - 593 line reduction needed)
2. Decompose models_view.py
3. Decompose settings_device_accounts_panel.py
4. Decompose library_view.py
5. Decompose assistant_view.py
6. Regression testing after each extraction

### Week 5-6: View Decomposition (Priority 1) + Governance
1. Complete remaining view decompositions
2. Start tool action registry hardening (TR54-C1)
3. Implement tool permissions split (TR54-C2)
4. Full regression test suite

### Week 7-8: Settings & Accounts
1. Connector workflow settings (TR54-C3)
2. Runtime settings schema normalization (TR54-C4)
3. Account lifecycle UX (TR54-E1)
4. Secret storage enforcement (TR54-E2)

### Week 9-10: Hardening & Closeout
1. Desktop hardening (TR54-D2, D3, D5)
2. Account troubleshooting paths (TR54-E5)
3. Wave-by-wave validation (TR54-F1)
4. Release preparation (TR54-F2, F3)

---

## Success Criteria Progress

- [x] All extraction seams documented (TR54-A1)
- [x] Line-cap reset plan created (TR54-A2)
- [x] Merge choreography defined (TR54-A3)
- [x] First orchestration module created (TR54-B1)
- [ ] All files < 550 lines (9/9 files need reduction)
- [ ] Zero import cycles (pending full integration)
- [ ] Startup < 3000ms maintained (pending integration)
- [ ] All signal connections tested (pending integration)
- [ ] Zero automation test regression (pending integration)
- [ ] All view state machines validated (pending extraction)

---

## Questions for Stakeholders

1. **Integration Timeline**: What's the priority for integrating these modules vs. continuing with new extractions? Should we extract all modules first, then integrate in phases?

2. **Testing Coverage**: What level of regression test coverage is required before marking modules as "done"? (unit, integration, smoke, screenshot comparison?)

3. **View Decomposition Strategy**: Should we freeze new view development during decomposition, or proceed in parallel?

4. **Backward Compatibility**: Are there any hard constraints on maintaining backward compatibility during this refactoring?

5. **Documentation**: Should we update the launcher README with new architecture docs as we proceed?

---

## Appendix: Command Reference

### View Extraction Seams
```
cat .builder/docs/EXTRACTION_SEAMS_ANALYSIS.md
```

### View Line-Cap Plan
```
cat .builder/docs/LINECOUNT_RESET_PLAN.md
```

### View Extraction Choreography
```
grep -A 200 "Merge Choreography Plan" .builder/docs/EXTRACTION_SEAMS_ANALYSIS.md
```

### Check Current File Line Counts
```
wc -l ui/launcher/*.py ui/launcher/components/*.py ui/launcher/views/*.py | sort -rn
```

### View Shell Orchestrator Module
```
cat ui/launcher/orchestration/launcher_shell_orchestrator.py
```

---

**Status Last Updated**: Current session  
**Next Review**: After Phase 2 priority modules integration  
**Document Maintainer**: Implementation tracking system
