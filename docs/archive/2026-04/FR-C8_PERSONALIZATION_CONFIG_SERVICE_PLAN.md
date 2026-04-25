# FR-C8: Personalization Config Service Split Plan

**Objective:** Split `utils/personalization_config.py` into dedicated services  
**Target:** Create service-shaped seams under `src/guppy/experience_config/`  
**Dependency:** After FR-C7 (Connector extraction stable)  
**Impact:** Config persistence/normalization become services, not utility monolith  
**Deadline:** Before FR-C10 (by June 12, 2026)

---

## Current State Analysis

### File: `utils/personalization_config.py`
```
Current size: ~700 lines
Status: At base cap, mixed responsibilities
Issues:
- Config loading/saving logic mixed with resolution logic
- Persona defaults embedded with runtime resolution
- Voice bindings tangled with provider inventory
- Hard to test individual concerns
```

### Dependencies (Files that import it)
```
grep -r "from utils import personalization_config"
grep -r "from utils.personalization_config import"
grep -r "import utils.personalization_config"
```

### Responsibilities to Extract
1. **Personalization Defaults Service** - Default configs, templates, initial state
2. **Personalization Storage Service** - Persistence layer (load/save/migrate configs)
3. **Personalization Resolution Service** - Runtime resolution of config with overrides

---

## Extraction Strategy

### Phase 1: Create New Services (Week 1)

**Location:** `src/guppy/experience_config/`

#### 1.1 Create `personalization_defaults.py` (~150 lines)
```python
"""
Manages personalization default configurations and templates.

Responsibilities:
- Define default persona (name, voice, style)
- Provide initial config template
- Supply reset-to-defaults config
- Offer preset configurations (minimal, standard, full)
"""

class PersonalizationDefaults:
    @staticmethod
    def default_config() -> dict[str, Any]:
        """Return base default personalization config"""
        pass
    
    @staticmethod
    def default_persona() -> dict[str, Any]:
        """Return default persona (name, voice, preferences)"""
        pass
    
    @staticmethod
    def default_voice_binding() -> dict[str, Any]:
        """Return default voice bindings"""
        pass
    
    @staticmethod
    def preset_configs() -> dict[str, dict[str, Any]]:
        """Return available preset configurations"""
        pass
```

**Tests:** `tests/unit/test_personalization_defaults.py`

#### 1.2 Create `personalization_storage.py` (~200 lines)
```python
"""
Handles personalization configuration persistence.

Responsibilities:
- Load config from JSON file
- Save config to JSON file
- Migrate old config formats
- Validate config integrity
- Backup/restore configs
"""

class PersonalizationStorage:
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.config_path = config_dir / "personalization.json"
    
    def load_config(self) -> dict[str, Any]:
        """Load personalization config from file"""
        pass
    
    def save_config(self, config: dict[str, Any]) -> bool:
        """Save personalization config to file"""
        pass
    
    def migrate_config(self, old_version: int) -> dict[str, Any]:
        """Migrate config from old format to current"""
        pass
    
    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        """Validate config structure and values"""
        pass
    
    def backup_config(self) -> Path:
        """Create backup of current config"""
        pass
    
    def restore_config(self, backup_path: Path) -> bool:
        """Restore config from backup"""
        pass
```

**Tests:** `tests/unit/test_personalization_storage.py`

#### 1.3 Create `personalization_resolution.py` (~200 lines)
```python
"""
Runtime resolution of personalization config with overrides.

Responsibilities:
- Merge defaults with user config
- Apply environment variable overrides
- Resolve voice selections to available voices
- Handle missing/invalid values gracefully
"""

class PersonalizationResolver:
    def __init__(self, storage: PersonalizationStorage, defaults: PersonalizationDefaults):
        self.storage = storage
        self.defaults = defaults
    
    def resolve_config(self) -> dict[str, Any]:
        """Return fully-resolved config (defaults + user + env overrides)"""
        pass
    
    def resolve_persona(self) -> dict[str, Any]:
        """Get resolved persona with all values present"""
        pass
    
    def resolve_voice_binding(self, voice_id: str) -> dict[str, Any]:
        """Resolve voice binding to actual voice"""
        pass
    
    def apply_environment_overrides(self, config: dict[str, Any]) -> dict[str, Any]:
        """Apply environment variable overrides to config"""
        pass
    
    def get_effective_value(self, config: dict, key: str, default: Any) -> Any:
        """Get effective value for key, preferring user config then default"""
        pass
```

**Tests:** `tests/unit/test_personalization_resolution.py`

---

## Phase 2: Migrate Current Logic (Week 2)

**Move from `utils/personalization_config.py` to new services:**

| Current Code | Move To | Action |
|--------------|---------|--------|
| `_default_*()` functions | `PersonalizationDefaults` | Extract config templates |
| `load_config()` | `PersonalizationStorage.load_config()` | Extract persistence |
| `save_config()` | `PersonalizationStorage.save_config()` | Extract persistence |
| `_migrate_*()` functions | `PersonalizationStorage.migrate_config()` | Extract versioning |
| `resolve_persona()` | `PersonalizationResolver.resolve_persona()` | Extract resolution |
| `resolve_voice_binding()` | `PersonalizationResolver.resolve_voice_binding()` | Extract resolution |
| `get_default_*()` | `PersonalizationDefaults` | Extract defaults |

**Keep in `utils/personalization_config.py`:**
- Only compatibility wrapper that delegates to new services
- Used by legacy code during transition
- Plan to remove in FR-C10

---

## Phase 3: Update Imports (Week 2-3)

**Find all files importing `personalization_config`:**
```bash
grep -r "from utils.personalization_config import" src/
grep -r "import utils.personalization_config" src/
```

**Update to use new services where beneficial:**
```python
# Before
from utils.personalization_config import load_config, resolve_persona

# After (cleaner)
from src.guppy.experience_config.personalization_storage import PersonalizationStorage
from src.guppy.experience_config.personalization_resolution import PersonalizationResolver

storage = PersonalizationStorage(config_dir)
resolver = PersonalizationResolver(storage, PersonalizationDefaults())
```

**Priority files to update:**
1. `src/guppy/experience_config/` - Config management (primary user)
2. `src/guppy/launcher_application/` - Launcher initialization
3. `src/guppy/api/` - API initialization

---

## Phase 4: Deprecate Old Code (Week 3)

**Add deprecation wrapper in `utils/personalization_config.py`:**
```python
"""
DEPRECATED: Use src.guppy.experience_config services instead.

This module is maintained for backward compatibility only.
All new code should use:
- PersonalizationDefaults for default configurations
- PersonalizationStorage for persistence
- PersonalizationResolver for runtime resolution
"""

import warnings
from src.guppy.experience_config.personalization_defaults import PersonalizationDefaults
from src.guppy.experience_config.personalization_storage import PersonalizationStorage
from src.guppy.experience_config.personalization_resolution import PersonalizationResolver

# Create singleton instances for compatibility
_defaults = PersonalizationDefaults()
_storage = PersonalizationStorage(...)
_resolver = PersonalizationResolver(_storage, _defaults)

def load_config():
    """DEPRECATED - Use PersonalizationStorage directly"""
    warnings.warn("Use PersonalizationStorage.load_config()", DeprecationWarning)
    return _storage.load_config()

# ... other compatibility wrappers
```

---

## Testing Strategy

### Unit Tests
```python
# tests/unit/test_personalization_defaults.py
def test_default_config_structure()
def test_default_persona_fields()
def test_preset_configs_available()

# tests/unit/test_personalization_storage.py
def test_load_missing_config()
def test_save_and_load_config()
def test_migrate_old_format()
def test_validate_config()
def test_backup_restore()

# tests/unit/test_personalization_resolution.py
def test_resolve_with_defaults_only()
def test_resolve_with_user_config()
def test_apply_environment_overrides()
def test_resolve_voice_binding()
```

### Integration Tests
```python
# tests/integration/test_personalization_services.py
def test_full_config_lifecycle()
def test_storage_resolver_integration()
def test_defaults_resolution_fallback()
def test_migration_and_resolution()
```

### Compatibility Tests
```python
# tests/integration/test_personalization_compat.py
def test_old_interface_still_works()
def test_deprecation_warnings_appear()
def test_compatibility_wrapper_correctness()
```

---

## Success Criteria

✅ **Code extracted:**
- [ ] `personalization_defaults.py` exists and works
- [ ] `personalization_storage.py` exists and works
- [ ] `personalization_resolution.py` exists and works

✅ **Tests passing:**
- [ ] All new service unit tests pass
- [ ] All integration tests pass
- [ ] No regression in existing tests
- [ ] Deprecation warnings appear when old API used

✅ **Migration complete:**
- [ ] All internal code uses new services
- [ ] Only compatibility wrapper remains in `utils/`
- [ ] `utils/personalization_config.py` size < 150 lines (wrapper only)

✅ **Quality gates:**
- [ ] `python tools/dev_workflow.py dev-check` passes
- [ ] `release-check` green
- [ ] No new linting errors

---

## Timeline

| Phase | Duration | Dates |
|-------|----------|-------|
| Phase 1: Create services | 1 week | May 19 - May 26 |
| Phase 2: Migrate logic | 1 week | May 26 - June 2 |
| Phase 3: Update imports | 1 week | June 2 - June 9 |
| Phase 4: Deprecate | 2 days | June 9 - June 11 |
| Testing & refinement | 1 day | June 11 |
| **Ready for FR-C10** | — | By June 11 |

---

## Blockers & Dependencies

**Depends on:**
- ✅ FR-C7 (Connector extraction stable)

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

- **File organization:** New services go under `src/guppy/experience_config/` (config layer)
- **Singleton pattern:** Use module-level singletons for compatibility during transition
- **Error handling:** Graceful fallback to defaults on load/migration errors
- **Performance:** Ensure service calls are as fast as old utility functions
- **Documentation:** Each service should have clear docstrings explaining contracts

---

## Integration with FR-C7 and FR-LOCAL

**FR-C8 builds on FR-C7's pattern:**
- Same service extraction strategy
- Same wrapper for backward compatibility
- Same testing approach (unit + integration + compatibility)

**Benefits for production (via FR-LOCAL reduction path):**
1. Config services are independently testable
2. Default configs can be simplified for minimal deployments
3. Storage layer can be swapped (file → embedded → cloud)
4. Resolution logic can be disabled/optimized for production

---

**Status:** Ready to begin (depends on FR-C7 Phase 2 completion)  
**Sequence:** After FR-C7, FR-C8, then FR-C10 (freeze audit)  
**Complexity:** Medium (similar to FR-C7 but config-specific)
