# View Decomposition Guide
## TR54-B4 through TR54-B11: Systematic View Component Extraction

This guide provides the exact extraction plan for decomposing all major view files to < 450 lines each.

---

## TR54-B4: Assistant View (Home/Chat) Decomposition

**File**: `ui/launcher/views/assistant_view.py` (618 lines → 450 lines)

### Extracted Components

#### 1. Assistant Transcript Panel
**File**: `ui/launcher/views/assistant_transcript_panel.py` (~200 lines)

**Content**:
- `_add_message()` - Add message to transcript
- `_scroll_to_bottom()` - Auto-scroll logic
- `_clear_transcript_widgets()` - Clear display
- `add_user_message()`, `add_assistant_message()`, `add_system_message()`
- `ensure_welcome_message()`
- `_MessageWidget` inner class (if extracted)

**Contract**:
- Input: Message text, role, formatting
- Output: Rendered message widget
- Signals: message_added, clear_requested
- No dependency on: composer, context, starters

#### 2. Assistant Context Ribbon
**File**: `ui/launcher/views/assistant_context_ribbon.py` (~120 lines)

**Content**:
- `_toggle_context_details()`
- `_sync_context_bar_visibility()`
- `_update_workspace_details_visibility()`
- Context display widgets
- Active context management

**Contract**:
- Input: Context list, visibility state
- Output: Context ribbon display
- Signals: context_cleared, context_changed
- Depends on: assistant_view parent for state

#### 3. Assistant Starters Panel
**File**: `ui/launcher/views/assistant_starters_panel.py` (~100 lines)

**Content**:
- `_refresh_starter_buttons()`
- `_toggle_starters()` 
- `_load_starter()`
- Starter button grid rendering
- `_starter_templates()` helper

**Contract**:
- Input: Starter templates list
- Output: Starter button grid
- Signals: starter_selected, context_applied
- Depends on: launcher_application.launcher_shell_support

#### 4. Assistant Empty State
**File**: `ui/launcher/views/assistant_empty_state_panel.py` (~100 lines)

**Content**:
- `_build_empty_state()`
- `_refresh_empty_state()`
- `_refresh_empty_state_copy()`
- `_refresh_empty_state_guidance()`
- Empty state UI assembly

**Contract**:
- Input: Workspace type, hero subtitle
- Output: Welcome/empty state display
- No signals (display only)

**Remaining in assistant_view.py** (~450 lines):
- Shell container
- Composer integration
- Message submission flow (`_submit()`)
- Mode/persona management
- Settings application
- Route preview sync

---

## TR54-B5: Models Hub View Decomposition

**File**: `ui/launcher/views/models_view.py` (668 lines → 450 lines)

### Extracted Components

#### 1. Models Hub Shell
**File**: `ui/launcher/views/models_hub_shell_view.py` (~200 lines)

**Content**:
- View mode toggle (Runtime/Library)
- Mode change handling
- Model loading state
- View stacking logic

**Contract**:
- Input: Mode (runtime/library), filters
- Output: Active view display
- Signals: view_mode_changed, model_selected

#### 2. Models Library Section
**File**: `ui/launcher/views/models_library_section.py` (~200 lines)

**Content**:
- Library model card rendering
- Model metadata display
- Selection callbacks
- Install/uninstall actions

**Contract**:
- Input: Model list from backend
- Output: Selected model ID
- Signals: model_selected, install_requested

#### 3. Models Runtime Section
**File**: `ui/launcher/views/models_runtime_section.py` (~150 lines)

**Content**:
- Runtime model status
- Health/evidence display
- Operation tracking
- Worker process display

**Contract**:
- Input: Runtime health snapshot
- Output: Model readiness status
- Signals: health_changed

**Remaining in models_view.py** (~450 lines):
- Hub container
- Mode state machine
- Model aggregation logic
- View coordination

---

## TR54-B6: Voices View Decomposition

**File**: `ui/launcher/views/voices_view.py` (546 lines → 450 lines)

### Extracted Components

#### 1. Voices Assignment Panel
**File**: `ui/launcher/views/voices_assignment_panel.py` (~200 lines)

**Content**:
- Voice binding form
- Available voices list
- Assignment controls
- Save/cancel buttons
- Validation logic

**Contract**:
- Input: Current bindings, available voices
- Output: Updated bindings dict
- Signals: bindings_changed, save_requested

#### 2. Voices Diagnostics Panel
**File**: `ui/launcher/views/voices_diagnostics_panel.py` (~100 lines)

**Content**:
- Voice capture testing UI
- Microphone test button
- Test results display
- Diagnostic status

**Contract**:
- Input: Voice capture enable flag, voice model list
- Output: Test results
- Signals: test_started, test_completed

**Remaining in voices_view.py** (~450 lines):
- View shell
- Panel coordination
- Settings integration

---

## TR54-B7: Tools View Decomposition

**File**: `ui/launcher/views/tools_view.py` (463 lines → 400 lines)

### Extracted Components

#### 1. Tool Cards Panel
**File**: `ui/launcher/views/tools_cards_section.py` (~180 lines)

**Content**:
- Tool card rendering
- Tool icon display
- Tool status badges
- Card selection logic
- Tool grid layout

**Contract**:
- Input: Tool list with state/status
- Output: Selected tool ID
- Signals: tool_selected, tool_action_requested

#### 2. Tool Policy Panel
**File**: `ui/launcher/views/tools_policy_section.py` (~120 lines)

**Content**:
- Tool permissions display
- Allow/block status
- Policy reasoning text
- Policy override controls

**Contract**:
- Input: Tool policy dict, allow/deny reason
- Output: Policy change events
- Signals: policy_changed

**Remaining in tools_view.py** (~400 lines):
- View coordination
- Tool state synchronization
- Debug surface integration

---

## TR54-B8: Library View Decomposition

**File**: `ui/launcher/views/library_view.py` (620 lines → 450 lines)

### Extracted Components

#### 1. Library Editor Shell
**File**: `ui/launcher/views/library_editor_view.py` (~200 lines)

**Content**:
- Item editor form
- Title/description fields
- Path selection
- Save/cancel buttons
- Form validation

**Contract**:
- Input: Item data (note/artifact), item kind
- Output: Updated item dict
- Signals: item_saved, item_deleted

#### 2. Library Card Grid
**File**: `ui/launcher/views/library_card_grid_view.py` (~180 lines)

**Content**:
- Card grid layout
- Card selection
- Filtering/search
- Root path management
- Card rendering

**Contract**:
- Input: Card list, selected card ID
- Output: Selected card ID, action (edit/delete/use)
- Signals: card_selected, action_requested

**Remaining in library_view.py** (~450 lines):
- Hub container
- State machine (browse/edit/use-in-chat)
- Media panel integration
- View coordination

---

## TR54-B9: Settings View Decomposition

**File**: `ui/launcher/views/settings_view.py` (575 lines → 450 lines)

### Extracted Components

#### 1. Settings Persona Manager
**File**: `ui/launcher/views/settings_persona_manager_view.py` (~180 lines)

**Content**:
- Persona list rendering
- Persona form (create/edit/delete)
- Persona selection
- Scope management
- Config building

**Contract**:
- Input: Persona list, selected persona ID
- Output: Updated persona config
- Signals: persona_changed, persona_created, persona_deleted

**Remaining in settings_view.py** (~450 lines):
- Settings shell (tabs/sections)
- Runtime settings loader
- Save/load orchestration
- Section routing

---

## TR54-B10: Settings Accounts/Operations Decomposition

**File**: `ui/launcher/views/settings_device_accounts_panel.py` (620 lines → 450 lines)
**File**: `ui/launcher/views/settings_operations_panel.py` (593 lines → 450 lines)

### Device Accounts Panel Extractions

#### 1. Accounts List View
**File**: `ui/launcher/views/settings_accounts_list_view.py` (~200 lines)

**Content**:
- Account list rendering
- Account selection
- Account status badges
- Filter/search logic

**Contract**:
- Input: Account list with status
- Output: Selected account ID
- Signals: account_selected, account_action_requested

#### 2. Account Form View
**File**: `ui/launcher/views/settings_account_form_view.py` (~180 lines)

**Content**:
- Account form fields
- Field validation
- Save/cancel buttons
- Credential input widgets

**Contract**:
- Input: Account data, field schema
- Output: Updated account data
- Signals: form_valid_changed, save_requested

#### 3. Account Operations View
**File**: `ui/launcher/views/settings_account_operations_view.py` (~150 lines)

**Content**:
- Verify account button
- Reconnect button
- Disable/enable toggle
- Remove account button
- Operation status display

**Contract**:
- Input: Account ID, operation status
- Output: Operation result
- Signals: verify_requested, reconnect_requested, remove_requested

### Settings Operations Panel Extractions

#### 1. Operations List View
**File**: `ui/launcher/views/settings_operations_list_view.py` (~200 lines)

**Content**:
- Operation card rendering
- Status display
- Progress indicators
- Filtering/sorting

**Contract**:
- Input: Operation list
- Output: Selected operation ID
- Signals: operation_selected

#### 2. Operation Detail View
**File**: `ui/launcher/views/settings_operation_detail_view.py` (~130 lines)

**Content**:
- Operation logs display
- Timeline visualization
- Evidence/trace display
- Detail panel

**Contract**:
- Input: Operation ID, logs, timeline
- Output: (display only)
- Signals: (none - read-only)

---

## TR54-B11: Instance Manager Decomposition

**File**: `ui/launcher/views/instance_manager_sections.py` (569 lines → 450 lines)

### Extracted Components

#### 1. Instance List Grid
**File**: `ui/launcher/views/instance_list_grid_view.py` (~200 lines)

**Content**:
- Instance card rendering
- Instance selection
- Filtering/search
- Status badges
- Card grid layout

**Contract**:
- Input: Instance list
- Output: Selected instance name
- Signals: instance_selected, instance_action_requested

**Remaining in instance_manager_sections.py** (~450 lines):
- Detail shell
- Operations (delete, logs)
- Instance state management

---

## Implementation Pattern

All view decompositions follow this pattern:

### 1. Extract Helper Functions
```python
# Move these first (no class state)
def _helper_function(...) -> ...:
    """Extracted helper."""
    pass
```

### 2. Create Child Panel Class
```python
class ChildPanel(QWidget):
    """Extracted child component."""
    signal_name = Signal(...)
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build child UI."""
        pass
    
    def update_from_parent(self, data: dict) -> None:
        """Receive state updates from parent."""
        pass
```

### 3. Update Parent View
```python
class ParentView(QWidget):
    """Parent coordinating child panels."""
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._child1 = ChildPanel1(self)
        self._child2 = ChildPanel2(self)
        self._wire_signals()
    
    def _wire_signals(self) -> None:
        """Connect child signals to handlers."""
        self._child1.signal_name.connect(self._on_child1_action)
```

---

## Testing Strategy Per View

For each decomposed view:

1. **Unit Test Child Panels** (in isolation)
   - Render without parent
   - Verify signal emissions
   - Test state updates

2. **Integration Test Parent** (with children)
   - Verify all children render
   - Test signal routing
   - Verify state synchronization

3. **Smoke Test Launcher** (full stack)
   - Navigate to view
   - Verify layout
   - Test all interactions

4. **Regression Test** (visual)
   - Screenshot comparison
   - Layout responsiveness at 1120px, 800px, 600px

---

## Checklist Per Extracted Module

- [ ] Module file created in correct location
- [ ] Docstring documents extracted content and contract
- [ ] All extracted methods work without modification
- [ ] All imports updated (parent and module)
- [ ] Signals properly defined and connected
- [ ] No circular dependencies between parent/child
- [ ] Parent view < 450 lines after extraction
- [ ] Child module < 300 lines
- [ ] Unit tests pass
- [ ] Integration test with parent passes
- [ ] Screenshot comparison shows no visual regression
- [ ] Launcher smoke test passes

---

## Execution Order

Follow this extraction order to maintain working intermediate states:

1. **Assistant View (B4)**
   - Extract helpers first
   - Then empty state panel (no dependencies)
   - Then transcript panel (depends on helpers)
   - Then context ribbon
   - Then starters panel
   - Finally: test, integrate

2. **Models View (B5)**
   - Extract library section first (independent)
   - Extract runtime section (depends on health snapshot)
   - Then hub shell (depends on both)

3. **Voices View (B6)**
   - Extract diagnostics first (minimal state)
   - Then assignment panel
   - Finally: integrate

4. **Tools View (B7)**
   - Extract cards panel first (rendering only)
   - Then policy panel
   - Finally: integrate

5. **Library View (B8)**
   - Extract card grid (data display)
   - Extract editor (form)
   - Finally: integrate

6. **Settings View (B9)**
   - Extract persona manager (isolated concern)
   - Finally: integrate

7. **Settings Device Accounts (B10 part 1)**
   - Extract list view first
   - Extract form view
   - Extract operations view
   - Finally: integrate

8. **Settings Operations (B10 part 2)**
   - Extract list view
   - Extract detail view
   - Finally: integrate

9. **Instance Manager (B11)**
   - Extract grid view
   - Keep detail shell
   - Finally: integrate

---

## Post-Decomposition Verification

After all decompositions complete:

- [ ] All views < 450 lines
- [ ] Total file count increased (many new modules)
- [ ] Total line count reduced by 1,660+ lines
- [ ] Zero import cycles (run python -m py_compile)
- [ ] All signal connections verified
- [ ] All view renders without error
- [ ] Navigation between views works
- [ ] All state propagation works
- [ ] Startup time maintained < 3000ms
- [ ] Screenshot regression test passes

