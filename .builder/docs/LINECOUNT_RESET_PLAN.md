# Line-Cap Reset Plan: Target 550 Lines per File
## TR54-A2: Systematic Decomposition Strategy

### Current State Analysis

**Total UI Lines**: 17,183
**Files Over 550 Lines**: 9 files (exceeds Stitch target)
**Target**: All files < 550 lines (stretch goal: < 450 lines)

### Files Requiring Decomposition

| File | Current | Target | Reduction | Priority | Lane |
|------|---------|--------|-----------|----------|------|
| launcher_window.py | 993 | 400 | 593 | P0 | A,D1,B4 |
| models_view.py | 668 | 450 | 218 | P0 | B5 |
| settings_device_accounts_panel.py | 620 | 450 | 170 | P0 | B10 |
| library_view.py | 620 | 450 | 170 | P0 | B8 |
| assistant_view.py | 618 | 450 | 168 | P0 | B4 |
| assistant_shell_sections.py | 594 | 450 | 144 | P1 | B4 |
| settings_operations_panel.py | 593 | 450 | 143 | P1 | B10 |
| settings_view.py | 575 | 450 | 125 | P1 | B9 |
| instance_manager_sections.py | 569 | 450 | 119 | P1 | B11 |

**Total Reduction Needed**: 1,660 lines

---

## Decomposition Strategy by File

### PRIORITY 0: Critical Path Files

#### 1. launcher_window.py (993 → 400 lines)

**Current Structure**: Monolithic main window with mixed concerns
**Target Structure**: Thin orchestration shell + extracted modules

**Extraction Plan** (by lane):

| Lane | Module | Lines | Details |
|------|--------|-------|---------|
| A | `launcher_shell_orchestrator.py` | 150 | Build UI, signal wiring, tab navigation |
| D1 | `launcher_poll_orchestration_impl.py` | 120 | Polling, startup phases, health sync |
| D4 | `launcher_polling_health_signal.py` | 80 | Health signal hardening, recovery sync |
| B1 | `launcher_shell_refresh_handlers.py` | 100 | Refresh coordination across modules |
| C4 | `launcher_runtime_settings_schema.py` | 60 | Normalized settings read/write |
| Util | `launcher_snapshot_builders.py` | 100 | Snapshot assembly utilities |
| Util | `launcher_telemetry_support.py` | 80 | Logging, telemetry, evidence gathering |

**Remaining in launcher_window.py** (~400 lines):
- `__init__()` — Window lifecycle setup
- `_build_ui()` stub — Delegates to orchestrator
- Main loop integration points
- Top-level error handling
- State coordination (request seq, session id)
- Component instantiation

**Extraction Order**:
1. First: Snapshot builders (no dependencies on window state)
2. Second: Poll orchestration + health signal (depends on snapshots)
3. Third: Shell orchestrator (depends on polling)
4. Fourth: Remaining utilities
5. Final: Clean up window.py

**Validation After Decomposition**:
- [ ] launcher_window.py < 400 lines
- [ ] No cyclic imports between modules
- [ ] First poll completes < 3000ms (startup budget)
- [ ] All signal connections functional
- [ ] Existing automation tests pass

---

#### 2. models_view.py (668 → 450 lines)

**Current Structure**: Hub view with library + runtime model rendering
**Target Structure**: Hub shell + library section + runtime section

**Extraction Plan**:

| Extract To | Lines | Content |
|------------|-------|---------|
| `models_hub_shell_view.py` | 200 | Tab switching, view mode toggle, status bar |
| `models_library_section.py` | 200 | Library model cards, metadata, selection |
| `models_runtime_section.py` | 150 | Runtime model evidence, health, workers |

**Remaining in models_view.py** (~450 lines):
- Hub layout container
- View mode state machine
- Model list aggregation
- Filter/search coordination

**Extraction Order**:
1. Library section (no runtime dependencies)
2. Runtime section (depends on health snapshots)
3. Hub shell (depends on both sections)

---

#### 3. settings_device_accounts_panel.py (620 → 450 lines)

**Current Structure**: Device account management with form, list, and operations
**Target Structure**: Account list view + account form view + operations panel

**Extraction Plan**:

| Extract To | Lines | Content |
|------------|-------|---------|
| `settings_accounts_list_view.py` | 200 | Account list rendering, selection, filtering |
| `settings_account_form_view.py` | 180 | Account form, field validation, save/cancel |
| `settings_account_operations_view.py` | 150 | Verify, reconnect, disable, remove actions |

**Remaining in settings_device_accounts_panel.py** (~450 lines):
- Panel coordinator
- Account lifecycle state machine
- Event routing between sub-views

---

#### 4. library_view.py (620 → 450 lines)

**Current Structure**: Library hub with card grid, editor, media panel, layout
**Target Structure**: Library shell + editor shell + media panel (already extracted)

**Extraction Plan**:

| Extract To | Lines | Content |
|------------|-------|---------|
| `library_editor_shell.py` | 200 | Editor state, form submission, validation |
| `library_card_grid_view.py` | 180 | Card layout, selection, filtering, root management |

**Remaining in library_view.py** (~450 lines):
- Hub container
- Section coordination
- State machine (browse/edit/use-in-chat)
- Media panel integration

---

#### 5. assistant_view.py (618 → 450 lines)

**Current Structure**: Home/chat view with composer, transcript, context, starters
**Target Structure**: Chat shell + transcript panel + context panel + starters

**Extraction Plan**:

| Extract To | Lines | Content |
|------------|-------|---------|
| `assistant_transcript_panel.py` | 200 | Message rendering, scrolling, user interactions |
| `assistant_context_ribbon.py` | 120 | Context display, context actions (copy, clear) |
| `assistant_starters_panel.py` | 100 | Starter grid, quick prompt selection |

**Remaining in assistant_view.py** (~450 lines):
- Chat shell container
- Composer integration
- Message submission orchestration
- View state machine

---

### PRIORITY 1: Secondary Decomposition Files

#### 6. assistant_shell_sections.py (594 → 450 lines)

**Current Structure**: Sections for first-run, context summary, active context
**Target Structure**: Split by content type

**Extraction Plan**:

| Extract To | Lines | Content |
|------------|-------|---------|
| `assistant_first_run_flow.py` | 150 | First-run cards, setup steps, wizard integration |
| `assistant_context_summary_section.py` | 120 | Context header summary, status badges |

**Remaining** (~450 lines): Keep remaining sections and parent shell

---

#### 7. settings_operations_panel.py (593 → 450 lines)

**Current Structure**: Operations management with task cards, status, history
**Target Structure**: Operations list + operation detail + event drain

**Extraction Plan**:

| Extract To | Lines | Content |
|------------|-------|---------|
| `settings_operations_list_view.py` | 180 | Operation cards, filtering, status summaries |
| `settings_operation_detail_view.py` | 130 | Operation logs, timeline, evidence display |

**Remaining** (~450 lines): Panel shell, state coordination

---

#### 8. settings_view.py (575 → 450 lines)

**Current Structure**: Settings hub with tabs, sections, persona management
**Target Structure**: Settings shell + persona manager (target 450)

**Extraction Plan**:

| Extract To | Lines | Content |
|------------|-------|---------|
| `settings_persona_manager.py` | 180 | Persona list, form, create/edit/delete |

**Remaining in settings_view.py** (~450 lines):
- Tab shell
- Section routing
- Runtime settings loader
- Save/load orchestration

---

#### 9. instance_manager_sections.py (569 → 450 lines)

**Current Structure**: Instance list and detail sections
**Target Structure**: Instance list grid + detail shell

**Extraction Plan**:

| Extract To | Lines | Content |
|------------|-------|---------|
| `instance_list_grid_view.py` | 180 | Instance cards, filtering, selection |

**Remaining** (~450 lines): Detail shell, operations

---

### Additional Files Approaching Limit (≥ 500 lines)

These files are close to the 550 line threshold and should be monitored:

| File | Current | Status | Action |
|------|---------|--------|--------|
| tools_view_cards.py | 547 | At limit | Mark for Q2 review |
| voices_view.py | 546 | At limit | Mark for Q2 review |
| models_hub_view.py | 516 | Healthy | Monitor |
| models_sections.py | 506 | Healthy | Monitor (already below 550) |

---

## Implementation Workflow

### Phase 1: Setup (1 day)
- [ ] Create directory structure for extracted modules
- [ ] Set up placeholder files with proper imports
- [ ] Create test scaffolding for each module

### Phase 2: Extract Priority 0 Files (3-4 days)

**Day 1: launcher_window.py**
- Extract snapshot builders + telemetry
- Extract poll orchestration + health signal
- Extract shell orchestrator
- Validation: startup < 3000ms, tests pass

**Day 2: models_view.py**
- Extract library section
- Extract runtime section
- Validate: no view rendering regression

**Day 3: settings_device_accounts_panel.py**
- Extract account list view
- Extract account form view
- Extract operations view
- Validate: account operations functional

**Day 4: library_view.py + assistant_view.py**
- library_view.py: Extract editor shell, card grid
- assistant_view.py: Extract transcript, context, starters
- Validate: chat flow intact, library nav works

### Phase 3: Extract Priority 1 Files (2-3 days)

**Day 5: assistant_shell_sections.py + settings_operations_panel.py**
- Extract first-run flow
- Extract context summary
- Extract operations list + detail

**Day 6: settings_view.py + instance_manager_sections.py**
- Extract persona manager
- Extract instance list grid
- Validate: all settings operations work

### Phase 4: Testing & Cleanup (1 day)
- [ ] Full regression test suite
- [ ] Line count verification (all < 550)
- [ ] Import cycle detection
- [ ] Documentation updates

---

## Extraction Template

Each extracted module follows this pattern:

```python
"""
Module: [extracted_name]
Purpose: [single responsibility]
Lane: [TR54-Bx/Cx/Dx/Ex]

Extracted from: [original_file.py]
Lines: [count]
Dependencies:
  - [module1]
  - [module2]
"""

# Imports organized by:
# 1. Standard library
# 2. Third-party (PySide6, etc.)
# 3. Internal (guppy modules)
# 4. Sibling (other UI modules)
# 5. Parent module (original file if needed)

# Class/function definitions follow

class ModuleClass:
    """Extracted responsibility."""
    pass
```

---

## Line Reduction Checklist

### For Each File:
- [ ] Identify clear extraction boundaries
- [ ] Create placeholder files
- [ ] Move code with minimal refactoring
- [ ] Update imports in original file
- [ ] Update imports in all dependents
- [ ] Run type checking (if applicable)
- [ ] Test module in isolation
- [ ] Test integration with original file
- [ ] Verify line counts reduced
- [ ] Document extraction seams
- [ ] Update EXTRACTION_SEAMS_ANALYSIS.md if changed

### Validation Criteria:
- [ ] All files < 550 lines
- [ ] Target files < 450 lines
- [ ] Zero import cycles
- [ ] All signal connections functional
- [ ] No regression in automation test support
- [ ] Startup time within budget
- [ ] View rendering performance maintained

---

## Risk Mitigation

**Risk 1: Import Cycles**
- Mitigation: Use dependency injection for circular references
- Validation: Run `python -m py_compile` on all modules

**Risk 2: Signal Connection Breakage**
- Mitigation: Extract signal wiring last, test extensively
- Validation: Run full UI smoke tests

**Risk 3: View Rendering Regression**
- Mitigation: Keep layout logic in parent view during extraction
- Validation: Screenshot comparison tests

**Risk 4: Startup Time Regression**
- Mitigation: Monitor phase timing throughout extraction
- Validation: Startup < 3000ms budget maintained

---

## Success Metrics

- [x] All seam contracts defined (from TR54-A1)
- [ ] All files < 550 lines by completion of Phase 3
- [ ] Target files < 450 lines by completion of Phase 3
- [ ] Total reduction: 1,660 lines accomplished
- [ ] Zero import cycles
- [ ] All automated tests passing
- [ ] Startup timing budget maintained (< 3000ms)
- [ ] Zero regression in UI responsiveness
- [ ] All signal connections tested and validated
