# Feature Flag Strategy: Dark-Launch Consolidations

**Decision:** Approved for immediate Phase 0 rollout with all developers  
**Authorization:** Go-all-in on Settings + Models + Home Chat consolidations  
**Risk Posture:** Full mitigation; prefer safety over speed

---

## Why Feature Flags Matter

### Problem We're Solving

When consolidating three major UI surfaces, there are two dangers:

1. **The "Cutover Crisis"** — Ship new code, operators immediately break because we didn't catch every edge case
   - Example: Settings consolidation moves connector logic → if validation is slightly different, connectors fail silently
   - Example: Models consolidation moves voice logic → if device enumeration breaks, users can't use voice input

2. **The "Rollback Nightmare"** — Operator encounters issue; need to roll back, but old code is already deleted
   - If we remove `my_pc_view.py` immediately, we can't restore it without reverting entire commit

### The Feature Flag Solution

**Core Pattern:** Old and new surfaces run in parallel, controlled by a flag.

```
SETTING_HUB_DARK_LAUNCH = False  (default, old surfaces live)
    ↓
Operators: Still see my_pc_view.py, advanced_view.py, etc.
Code: Both old and new code paths active, new path untested

SETTING_HUB_DARK_LAUNCH = True   (rollout phase 1)
    ↓
Operators: Still see OLD surfaces by default, but can opt-in to new Settings Hub
Code: New path gets real traffic, edge cases revealed

SETTING_HUB_DARK_LAUNCH = True + OLD_VIEWS_DEPRECATED = True  (rollout phase 2)
    ↓
Operators: See ONLY new Settings Hub, old code is dead
Code: Old surfaces deleted, old code path removed

```

**Benefit:** If something breaks at phase 1, we just set flag back to False. No rollback needed. Old code still exists.

---

## Feature Flag Implementation (Three Options)

### Option A: Centralized in `utils/personalization_config.py` ⭐ RECOMMENDED

**Why:** This is where all operator preferences live (model selection, voice device, connector bindings, etc.)

```python
# utils/personalization_config.py

@dataclass
class FeatureFlags:
    """Dark-launch feature flags for hub consolidations."""
    settings_hub_enabled: bool = False           # Default: off (old surfaces live)
    models_hub_enabled: bool = False             # Default: off (old surfaces live)
    home_chat_cleanup_enabled: bool = False      # Default: off (old surfaces live)

class PersonalizationConfig:
    def __init__(self):
        self.features = FeatureFlags()  # Load from persona persistence
    
    def load(self):
        """Load from persona file; fall back to defaults."""
        try:
            config = json.load(open(self.config_path))
            self.features = FeatureFlags(**config.get("features", {}))
        except:
            self.features = FeatureFlags()  # Use defaults if load fails
    
    def save(self):
        """Persist flags to persona file."""
        config = {
            "features": {
                "settings_hub_enabled": self.features.settings_hub_enabled,
                "models_hub_enabled": self.features.models_hub_enabled,
                "home_chat_cleanup_enabled": self.features.home_chat_cleanup_enabled,
            }
        }
        json.dump(config, open(self.config_path, 'w'))
```

**Usage in UI code:**

```python
# ui/launcher/launcher_window.py

class LauncherWindow(QMainWindow):
    def __init__(self, config: PersonalizationConfig):
        self.config = config
        
        # Settings Hub routing
        if self.config.features.settings_hub_enabled:
            self.settings_view = SettingsHubNewConsolidated()  # New hub
        else:
            self.settings_view = SettingsHubLegacy()  # Old scattered surfaces
        
        # Models Hub routing
        if self.config.features.models_hub_enabled:
            self.models_view = ModelsHubNewConsolidated()  # New hub
        else:
            self.models_view = ModelsHubLegacy()  # Old scattered surfaces
```

**Advantages:**
- ✅ Colocated with all other operator preferences
- ✅ Persisted to disk automatically (survives app restart)
- ✅ No new configuration file needed
- ✅ Already has pattern for graceful default fallback

**Disadvantages:**
- ⚠️ Requires operator to manually edit config file to enable flag (no UI toggle yet)

---

### Option B: Environment Variables (Quick Testing)

```bash
# launch_guppy.bat
set GUPPY_SETTINGS_HUB_ENABLED=true
set GUPPY_MODELS_HUB_ENABLED=true
set GUPPY_HOME_CHAT_CLEANUP_ENABLED=false
call python guppy_ui.py
```

```python
# utils/personalization_config.py

class FeatureFlags:
    @staticmethod
    def load_from_env():
        return FeatureFlags(
            settings_hub_enabled=os.getenv("GUPPY_SETTINGS_HUB_ENABLED", "false").lower() == "true",
            models_hub_enabled=os.getenv("GUPPY_MODELS_HUB_ENABLED", "false").lower() == "true",
            home_chat_cleanup_enabled=os.getenv("GUPPY_HOME_CHAT_CLEANUP_ENABLED", "false").lower() == "true",
        )
```

**Advantages:**
- ✅ Fast for local testing (no restart needed if using environment reloading)
- ✅ Easy to enable for specific test runs

**Disadvantages:**
- ⚠️ Not persisted (resets on restart)
- ⚠️ Hard for operators to use (requires batch file editing)

---

### Option C: UI Toggle in Settings Hub

Once Settings Hub exists, add a "Developer" tab:

```python
# ui/launcher/views/settings_view.py

class SettingsHub(QWidget):
    def __init__(self, config: PersonalizationConfig):
        # ... existing sections ...
        
        # NEW: Developer section (only visible if operator.role == "developer")
        if self.config.current_operator_role == "developer":
            self.add_developer_section([
                ("Enable Models Hub (dark launch)", 
                 self.config.features.models_hub_enabled,
                 self.on_models_hub_toggle),
                ("Enable Home Chat Cleanup (dark launch)",
                 self.config.features.home_chat_cleanup_enabled,
                 self.on_home_chat_toggle),
            ])
    
    def on_models_hub_toggle(self, enabled: bool):
        self.config.features.models_hub_enabled = enabled
        self.config.save()
        QMessageBox.information(self, "Restart Required", 
                                "Close and reopen Guppy to apply feature flag change.")
```

**Advantages:**
- ✅ Operator-friendly (UI toggle, no config file editing)
- ✅ Immediate feedback (no batch file editing)

**Disadvantages:**
- ⚠️ Requires Settings Hub to exist first (only viable in phase 3-4 of rollout)

---

## Recommended Rollout (Feature Flag Progression)

### Phase 0-2: Use Option A (Centralized in PersonalizationConfig)
- Default flags: all False (old surfaces live)
- Developers modify config JSON manually to test new hubs
- Flag is persisted, survives restart
- When issue found, flip flag back to False

### Phase 3: Add Option B (Environment Variables)
- For CI testing, use env vars to enable specific hubs
- Allows headless testing of new hubs without UI
- `test-default` can run with flags enabled to catch regressions

### Phase 4+: Add Option C (UI Toggle)
- Once Settings Hub stable, add Developer tab with toggle
- Operators can self-serve enabling/disabling new hubs
- Clean telemetry: track which flags operators enabled

---

## Concrete Implementation for Phase 0

### Step 1: Add FeatureFlags to PersonalizationConfig

Edit `utils/personalization_config.py`:

```python
from dataclasses import dataclass, field
from typing import Optional
import json

@dataclass
class FeatureFlags:
    """Dark-launch feature flags for 5-hub consolidations."""
    settings_hub_enabled: bool = False           # Settings → unified hub
    models_hub_enabled: bool = False             # Models → unified hub  
    home_chat_cleanup_enabled: bool = False      # Home Chat → conversation-only
    
    def to_dict(self):
        return {
            "settings_hub_enabled": self.settings_hub_enabled,
            "models_hub_enabled": self.models_hub_enabled,
            "home_chat_cleanup_enabled": self.home_chat_cleanup_enabled,
        }

class PersonalizationConfig:
    def __init__(self):
        # ... existing fields ...
        self.features = FeatureFlags()
    
    def load(self):
        """Load operator config from disk; initialize feature flags."""
        try:
            data = json.load(open(self.config_path))
            # ... existing load logic ...
            
            # Load feature flags if present, else use defaults
            if "features" in data:
                self.features = FeatureFlags(**data["features"])
            else:
                self.features = FeatureFlags()  # Use defaults
        except Exception as e:
            logger.warning(f"Failed to load PersonalizationConfig: {e}, using defaults")
            self.features = FeatureFlags()
    
    def save(self):
        """Persist config to disk including feature flags."""
        config_dict = {
            # ... existing fields ...
            "features": self.features.to_dict(),
        }
        json.dump(config_dict, open(self.config_path, 'w'), indent=2)
```

### Step 2: Update launcher_window.py to Route on Flags

```python
# ui/launcher/launcher_window.py

class LauncherWindow(QMainWindow):
    def __init__(self, config: PersonalizationConfig):
        self.config = config
        self._initialize_hubs()
    
    def _initialize_hubs(self):
        """Initialize hub surfaces, routing on feature flags."""
        
        # Settings Hub: Old surfaces vs. consolidated hub
        if self.config.features.settings_hub_enabled:
            logger.info("🚀 DARK LAUNCH: Settings Hub (consolidated) enabled")
            self.settings_view = SettingsHubConsolidated(self.config)
        else:
            logger.info("Settings Hub (consolidated) disabled; using legacy surfaces")
            self.settings_view = SettingsHubLegacy(self.config)
        
        # Models Hub: Old surfaces vs. consolidated hub
        if self.config.features.models_hub_enabled:
            logger.info("🚀 DARK LAUNCH: Models Hub (consolidated) enabled")
            self.models_view = ModelsHubConsolidated(self.config)
        else:
            logger.info("Models Hub (consolidated) disabled; using legacy surfaces")
            self.models_view = ModelsHubLegacy(self.config)
        
        # Home Chat: Operator UI fragments vs. clean conversation surface
        if self.config.features.home_chat_cleanup_enabled:
            logger.info("🚀 DARK LAUNCH: Home Chat cleanup enabled")
            self.home_chat = HomeChatCleanup(self.config)
        else:
            logger.info("Home Chat cleanup disabled; using legacy surface with operator UI")
            self.home_chat = HomeChatLegacy(self.config)
```

### Step 3: Create Test Utilities to Toggle Flags

```python
# tests/conftest.py

@pytest.fixture
def config_with_all_hubs_enabled(config: PersonalizationConfig):
    """Fixture for testing with all dark-launch hubs enabled."""
    config.features.settings_hub_enabled = True
    config.features.models_hub_enabled = True
    config.features.home_chat_cleanup_enabled = True
    return config

@pytest.fixture
def config_with_settings_hub_only(config: PersonalizationConfig):
    """Fixture for testing Settings Hub consolidation in isolation."""
    config.features.settings_hub_enabled = True
    config.features.models_hub_enabled = False
    config.features.home_chat_cleanup_enabled = False
    return config
```

### Step 4: Update dev_workflow.py to Test Both Paths

```python
# tools/dev_workflow.py

def run_test_dark_launch(args):
    """Run tests with all dark-launch hubs enabled."""
    os.environ["PYTEST_GUPPY_DARK_LAUNCH"] = "true"
    subprocess.run(["python", "-m", "pytest", "tests/", "-v", ...])

# In CLI subcommands:
subparsers.add_parser("test-dark-launch", 
                      help="Run test suite with all hub consolidations enabled")
```

---

## Phase 0 Developer Kickoff Checklist

### For Settings Hub Team
- [ ] Read [docs/HUB_CONSOLIDATION_MASTER_PLAN.md](docs/HUB_CONSOLIDATION_MASTER_PLAN.md#plan-1-settings-hub-consolidation)
- [ ] Complete Phase 0: Document current settings ownership (my_pc_view, advanced_view, connector_panel, advanced_terminal_panel)
- [ ] Implement feature flag routing in launcher_window.py (settings_hub_enabled)
- [ ] Create SettingsHubConsolidated stub (dark-launched, disabled by default)
- [ ] Verify: Feature flag off → old surfaces live; feature flag on → new consolidated hub

### For Models Hub Team
- [ ] Read [docs/HUB_CONSOLIDATION_MASTER_PLAN.md](docs/HUB_CONSOLIDATION_MASTER_PLAN.md#plan-2-models-hub-consolidation)
- [ ] Complete Phase 0: Verify provider registry (utils/personalization_config.py#L671) and voice bindings (L723) stable
- [ ] Implement feature flag routing in launcher_window.py (models_hub_enabled)
- [ ] Create ModelsHubConsolidated stub (dark-launched, disabled by default)
- [ ] Verify: Feature flag off → old surfaces live; feature flag on → new consolidated hub

### For Home Chat Team
- [ ] Read [docs/HUB_CONSOLIDATION_MASTER_PLAN.md](docs/HUB_CONSOLIDATION_MASTER_PLAN.md#plan-3-home-chat-cleanup)
- [ ] Complete Phase 0: Inventory operator UI fragments in assistant_view.py (model controls, route status, diagnostics)
- [ ] Implement feature flag routing in launcher_window.py (home_chat_cleanup_enabled)
- [ ] Create HomeChatCleanup stub (dark-launched, disabled by default)
- [ ] Verify: Feature flag off → old surfaces live with operator UI; feature flag on → conversation-only

### For All Teams
- [ ] Implement FeatureFlags in utils/personalization_config.py (Step 1 above)
- [ ] Create test fixtures for flag toggling (Step 3 above)
- [ ] Verify guardrails still pass: `python tools/dev_workflow.py dev-check delta`
- [ ] Create git branch: `git checkout -b feat/settings-hub-phase-0` (or models, home-chat)
- [ ] Commit Phase 0 work with descriptive message
- [ ] Open PR with link to [HUB_CONSOLIDATION_MASTER_PLAN](docs/HUB_CONSOLIDATION_MASTER_PLAN.md) for context

---

## Flag Enabling Procedure (Operators)

Once Phase 0 complete and stubs merged, operators can test new hubs by editing config file:

```json
// ~/.config/guppy/personalization.json
{
  "current_model": "guppy-main",
  "voice_enabled": true,
  "features": {
    "settings_hub_enabled": true,
    "models_hub_enabled": false,
    "home_chat_cleanup_enabled": false
  }
}
```

Then restart Guppy. New Settings Hub loads instead of scattered surfaces.

If anything breaks:

```json
{
  "features": {
    "settings_hub_enabled": false  // ← Back to old surfaces
  }
}
```

Restart Guppy. Back to normal. No rollback commit needed.

---

## Success Criteria: Feature Flags

- ✅ All three flags default to False (old surfaces live)
- ✅ Feature flag logic centralizes in PersonalizationConfig
- ✅ launcher_window.py routes on flag state (no hardcoded hub selection)
- ✅ Config persists to disk (survives restart)
- ✅ Test fixtures allow headless testing with flags enabled
- ✅ Guardrails pass with flags on and off
- ✅ Developer can toggle flag in config file and restart app

---

## TL;DR: Why This Approach?

**The feature flag pattern enables "zero-downtime consolidation":**

1. **Phase 0-2:** Developers build new hubs with flags disabled (old surfaces untouched)
2. **Phase 3:** Team tests new hubs by enabling flags (old code still runs in parallel, ready to fallback)
3. **Phase 4:** If new hub works perfectly, disable flag permanently and remove old code
4. **If bug found:** Flip flag back to False, operators back to old surfaces immediately (no rollback commit)

This is how Netflix, Uber, and large platforms do UI rewrites—reduce blast radius by running old + new in parallel until new is proven solid.

