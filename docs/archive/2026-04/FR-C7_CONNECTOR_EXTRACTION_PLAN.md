# FR-C7: Connector Manager Extraction Plan

**Objective:** Move connector state/history/action orchestration out of `utils/connector_manager.py` into proper services  
**Target:** Remove non-compat code; leave only wrapper if needed  
**Dependency:** After FR-C5 (Settings seams stable)  
**Impact:** `utils/` no longer acts like app layer  
**Deadline:** Before FR-C10 (by June 5, 2026)

---

## Current State Analysis

### File: `utils/connector_manager.py`
```
Current size: ~670 lines
Status: Below base cap but has mixed responsibilities
Issues:
- Acts as both service container AND compatibility wrapper
- Connector state logic mixed with action orchestration
- History management not clearly separated
- Tests scattered across multiple locations
```

### Dependencies (Files that import it)
```
grep -r "from utils import connector_manager"
grep -r "from utils.connector_manager import"
```

### Responsibilities to Extract
1. **Connector State Service** - Manages connector configuration, status, availability
2. **Connector Action Service** - Handles orchestration of connector operations
3. **Connector History Service** - Tracks connector usage/interactions

---

## Extraction Strategy

### Phase 1: Create New Services (Week 1)

**Location:** `src/guppy/launcher_application/`

#### 1.1 Create `connector_state_service.py` (~250 lines)
```python
"""
Manages connector state, configuration, and availability.

Responsibilities:
- Load connector configuration (from config/)
- Track connector availability (which are installed/working)
- Store connector preferences per workspace
- Validate connector prerequisites
"""

class ConnectorStateService:
    def __init__(self):
        self.config = load_connector_config()
        self.available = []
        self.disabled = []
    
    def get_available_connectors(self) -> List[Connector]:
        """Return connectors that are installed and working"""
        pass
    
    def get_connector_status(self, name: str) -> ConnectorStatus:
        """Check if a specific connector is available"""
        pass
    
    def validate_connector_prerequisites(self, name: str) -> ValidationResult:
        """Verify dependencies for a connector"""
        pass
    
    def register_connector(self, config: ConnectorConfig) -> bool:
        """Add new connector to registry"""
        pass
```

**Tests:** `tests/unit/test_connector_state_service.py`

#### 1.2 Create `connector_action_service.py` (~250 lines)
```python
"""
Orchestrates connector operations and interactions.

Responsibilities:
- Execute connector actions (search, retrieve, transform)
- Queue connector requests
- Handle connector errors and retries
- Track connector performance metrics
"""

class ConnectorActionService:
    def __init__(self, state_service: ConnectorStateService):
        self.state = state_service
        self.request_queue = RequestQueue()
    
    def execute_action(self, connector: str, action: str, params: dict) -> Result:
        """Execute a connector action with proper error handling"""
        pass
    
    def queue_connector_request(self, request: ConnectorRequest) -> str:
        """Queue a request for async execution"""
        pass
    
    def get_action_history(self, connector: str) -> List[ActionRecord]:
        """Retrieve recent actions for a connector"""
        pass
    
    def estimate_connector_performance(self, connector: str) -> PerformanceMetrics:
        """Calculate connector latency/reliability"""
        pass
```

**Tests:** `tests/unit/test_connector_action_service.py`

#### 1.3 Create `connector_history_service.py` (~150 lines)
```python
"""
Tracks connector usage history and interactions.

Responsibilities:
- Log connector usage (when, which, success/failure)
- Calculate connector statistics
- Export usage analytics
"""

class ConnectorHistoryService:
    def __init__(self):
        self.db = sqlite3.connect(HISTORY_DB)
    
    def record_action(self, action: ActionRecord) -> None:
        """Log connector action execution"""
        pass
    
    def get_usage_stats(self, connector: str) -> UsageStats:
        """Calculate success rate, latency, frequency"""
        pass
    
    def export_analytics(self, date_range: tuple) -> Dict:
        """Export connector analytics for reporting"""
        pass
```

**Tests:** `tests/unit/test_connector_history_service.py`

---

### Phase 2: Migrate Current Logic (Week 2)

**Move from `utils/connector_manager.py` to new services:**

| Current Code | Move To | Action |
|--------------|---------|--------|
| `get_available_connectors()` | `ConnectorStateService.get_available_connectors()` | Extract logic |
| `validate_connector()` | `ConnectorStateService.validate_connector_prerequisites()` | Extract logic |
| `execute_action()` | `ConnectorActionService.execute_action()` | Extract + enhance |
| `queue_request()` | `ConnectorActionService.queue_connector_request()` | Extract + enhance |
| `get_history()` | `ConnectorHistoryService.get_usage_stats()` | Extract + enhance |
| `_init_defaults()` | `ConnectorStateService.__init__()` | Extract config loading |
| `_load_config()` | `ConnectorStateService.__init__()` | Extract config loading |

**Keep in `utils/connector_manager.py`:**
- Only compatibility wrapper that delegates to new services
- Used by legacy code during transition
- Plan to remove in FR-C10

---

### Phase 3: Update Imports (Week 2-3)

**Find all files importing `connector_manager`:**
```bash
grep -r "from utils.connector_manager import" src/
grep -r "import utils.connector_manager" src/
```

**Update to use new services:**
```python
# Before
from utils.connector_manager import get_available_connectors

# After
from src.guppy.launcher_application.connector_state_service import ConnectorStateService

state_service = ConnectorStateService()
connectors = state_service.get_available_connectors()
```

**Priority files to update:**
1. `src/guppy/launcher_application/` - Core app logic
2. `ui/launcher/views/` - UI components
3. `src/guppy/experience_config/` - Config management

---

### Phase 4: Deprecate Old Code (Week 3)

**Add deprecation wrapper in `utils/connector_manager.py`:**
```python
"""
DEPRECATED: Use src.guppy.launcher_application services instead.

This module is maintained for backward compatibility only.
All new code should use:
- ConnectorStateService for state management
- ConnectorActionService for actions
- ConnectorHistoryService for history
"""

import warnings
from src.guppy.launcher_application.connector_state_service import ConnectorStateService
from src.guppy.launcher_application.connector_action_service import ConnectorActionService
from src.guppy.launcher_application.connector_history_service import ConnectorHistoryService

# Create singleton instances for compatibility
_state_service = ConnectorStateService()
_action_service = ConnectorActionService(_state_service)
_history_service = ConnectorHistoryService()

def get_available_connectors():
    """DEPRECATED - Use ConnectorStateService directly"""
    warnings.warn("Use ConnectorStateService.get_available_connectors()", DeprecationWarning)
    return _state_service.get_available_connectors()

# ... other compatibility wrappers
```

---

## Testing Strategy

### Unit Tests
```python
# tests/unit/test_connector_state_service.py
def test_load_available_connectors()
def test_validate_prerequisites()
def test_connector_status_tracking()
def test_register_new_connector()

# tests/unit/test_connector_action_service.py
def test_execute_action_success()
def test_execute_action_with_retry()
def test_queue_connector_request()
def test_error_handling_and_recovery()

# tests/unit/test_connector_history_service.py
def test_record_action()
def test_calculate_usage_stats()
def test_export_analytics()
```

### Integration Tests
```python
# tests/integration/test_connector_services_integration.py
def test_full_connector_workflow()
def test_state_action_history_coordination()
def test_error_propagation_across_services()
```

### Compatibility Tests
```python
# tests/integration/test_connector_manager_compatibility.py
def test_old_interface_still_works()
def test_deprecation_warnings_appear()
def test_compatibility_wrapper_correctness()
```

---

## Success Criteria

✅ **Code extracted:**
- [x] `connector_state_service.py` exists and works
- [x] `connector_action_service.py` exists and works
- [x] `connector_history_service.py` exists and works (CREATED 2026-04-22)

✅ **Tests passing:**
- [ ] All new service unit tests pass
- [ ] All integration tests pass
- [ ] No regression in existing tests
- [ ] Deprecation warnings appear when old API used

✅ **Migration complete:**
- [ ] All internal code uses new services
- [ ] Only compatibility wrapper remains in `utils/`
- [ ] `utils/connector_manager.py` size < 200 lines

✅ **Quality gates:**
- [ ] `python tools/dev_workflow.py dev-check` passes
- [ ] `release-check` green
- [ ] No new linting errors

---

## Timeline

| Phase | Duration | Dates | Status |
|-------|----------|-------|--------|
| Phase 1: Create services | 1 week | Apr 22 - Apr 29 | ✅ COMPLETE (Apr 22) |
| Phase 2: Verify logic migration | 1 week | Apr 29 - May 6 | 🔄 IN PROGRESS |
| Phase 3: Update imports (if needed) | 1 week | May 6 - May 13 | ⏳ PENDING |
| Phase 4: Deprecate wrapper | 3 days | May 13 - May 16 | ⏳ PENDING |
| Testing & refinement | 3 days | May 16 - May 19 | ⏳ PENDING |
| **Ready for FR-C8** | — | By May 19 | 🎯 TARGET |

---

## Blockers & Dependencies

**Depends on:**
- ✅ FR-C5 (Settings seams stable)

**Blocks:**
- ⏸️ FR-C10 (Freeze audit can't fully pass until old code removed)

**No impact to:**
- ✅ FR-LOCAL (user experience track)
- ✅ Other FR-C tranches

---

## Rollback Plan

If extraction fails:
1. Keep compatibility wrapper as permanent solution
2. Document remaining debt in FR-C10 waiver
3. Proceed to other tranches
4. Plan full removal in next release cycle

---

## Notes

- **File organization:** New services go under `src/guppy/launcher_application/` (app layer, not utility)
- **Singleton pattern:** Use module-level singletons for compatibility during transition
- **Error handling:** Propagate errors from services to callers (no silent failures)
- **Performance:** Ensure service calls are as fast as old utility functions
- **Documentation:** Each service should have clear docstrings explaining contracts

