# Remaining Phases 3-6 Implementation Blueprint

## Phase 3: Tool & Settings Governance (TR54-C)

### TR54-C2: Tool Permissions & Policy ✅
**Status**: COMPLETED  
**File**: `ui/launcher/tools/tool_permissions_policy.py` (295 lines)

Provides permission model with allow/deny rationale tracking.

### TR54-C3: Connector Workflow Settings (IN PLAN)
**Responsibility**: Settings-owned remediation paths for connectors

Implementation approach:
- Connector settings UI in Settings hub (not Settings > Accounts)
- Clear remediation path: Settings > Connectors > [connector] > Verify/Reconnect
- Guided setup wizard for new connector connections
- One-click "fix" buttons with specific remediation action
- Abort/cancel always available for user control

Key deliverables:
- `ui/launcher/views/settings_connector_flow.py` - Connector workflow
- `ui/launcher/accounts/connector_remediation_paths.py` - Recovery guidance
- Retrofit existing settings_connector_panel.py to use remediation paths

### TR54-C4: Runtime Settings Schema (IN PLAN)
**Responsibility**: Normalize runtime settings read/write contract

Implementation approach:
- Central settings schema definition (no per-component schemas)
- Explicit field ownership (which component owns each field)
- Read path: Load from file → validate → cache
- Write path: Validate → cache → persist to file
- Atomic writes (all-or-nothing saves)

Key deliverables:
- `ui/launcher/config/runtime_settings_schema.py` - Schema definition
- `ui/launcher/config/settings_io.py` - Read/write handlers
- Settings save handler integration (TR54-B9 refactoring)

### TR54-C5: Tool Evidence & Trace Copy (IN PLAN)
**Responsibility**: Concise, truthful status labels for tool state

Implementation approach:
- No status label without backing evidence
- Evidence from actual worker health/logs (not inferred)
- Copy should be: past tense (what happened), not future tense (what might happen)
- All timestamps: ISO 8601, timezone-aware
- Copy examples:
  - ✓ "Connected 10 minutes ago"
  - ✓ "Last successful run: 2024-01-15 14:22 UTC"
  - ✗ "Ready to use" (without evidence of actual readiness)
  - ✗ "Should work fine" (speculative)

Key deliverables:
- `ui/launcher/tools/tool_evidence_builder.py` - Evidence gathering
- `ui/launcher/tools/tool_status_copy.py` - Status label generation
- Integration with tools_view.py for display

---

## Phase 4: Desktop Hardening (TR54-D)

### TR54-D2: Duplicate Window & Process Guard (IN PLAN)
**Responsibility**: Prevent multiple launcher instances

Implementation approach:
- Lock file at ~/.guppy/launcher.lock (PID + timestamp)
- On startup: check lock file
  - If stale (> 5 minutes): remove and proceed
  - If current: exit with user message
- On shutdown: remove lock file
- Windows: Also check process list (Process.GetProcessesByName)

Key deliverables:
- `ui/launcher/orchestration/launcher_process_guard.py` - Lock/guard logic
- Integration in launcher_window.py __init__

### TR54-D3: Desktop Packaging Boot Verification (IN PLAN)
**Responsibility**: Verify launcher can start without import/runtime errors

Implementation approach:
- Startup checklist:
  1. Python interpreter available
  2. All required modules importable
  3. Qt platform available
  4. Config directory readable/writable
  5. Runtime directory exists
  6. Network connectivity (optional warning)
- Failures: detailed error message with recovery steps

Key deliverables:
- `ui/launcher/diagnostics/startup_verification.py` - Boot check
- Integration in launcher_window.py before UI build

### TR54-D5: Launcher Diagnostics & Support Copy (IN PLAN)
**Responsibility**: Help text and diagnostics for support team

Implementation approach:
- Diagnostics button in topbar (or Settings > Support)
- Collects:
  - Launcher version, startup time, boot errors
  - Last 20 events (errors, warnings)
  - Running processes and their health
  - Available models and models status
  - Installed tools and their status
  - Active connections/integrations
- Export as JSON for support team
- Status summary (color-coded: ✓ green, ⚠ yellow, ✗ red)

Key deliverables:
- `ui/launcher/diagnostics/launcher_diagnostics.py` - Diagnostics collector
- `ui/launcher/views/diagnostics_panel.py` - UI display
- Integration in topbar or Settings

---

## Phase 5: Account & Storage Best Practices (TR54-E)

### TR54-E1: Account Lifecycle UX (IN PLAN)
**Responsibility**: Clear account state transitions with visual feedback

Implementation approach:
States: New → Connecting → Verifying → Connected → Expired → Reconnecting → Error

Transitions:
- NEW: User adds account → asks for credentials
- CONNECTING: Making initial connection (spinner)
- VERIFYING: Testing credentials (spinner)
- CONNECTED: ✓ Ready (with "Last verified: X")
- EXPIRED: Credentials stale → "Reconnect" button
- RECONNECTING: Re-verifying (spinner)
- ERROR: Connection failed → "Details" + "Retry" buttons

Copy is literal and action-oriented:
- ✓ "Reconnect account"
- ✗ "Fix this"

Key deliverables:
- `ui/launcher/accounts/account_lifecycle_machine.py` - State machine
- `ui/launcher/views/account_status_badge.py` - Status display
- Integration with settings_device_accounts_panel.py

### TR54-E2: Secret Storage Enforcement (IN PLAN)
**Responsibility**: Keyring-first storage with truthful fallback

Implementation approach:
- Storage hierarchy:
  1. System keyring (encrypted, OS-managed)
  2. Fallback: Launcher secrets file (if keyring unavailable)
  3. NEVER: Plaintext config files

- Secrets to protect:
  - API keys
  - Passwords
  - OAuth tokens
  - Private keys

- Fallback display (when keyring unavailable):
  - Show: "Credentials stored locally (not encrypted)"
  - Warning badge in UI
  - Tooltip: "For security, enable system keyring"

Key deliverables:
- `ui/launcher/config/secret_storage.py` - Keyring wrapper
- `ui/launcher/views/secret_storage_warning.py` - Fallback warning
- Integration in Settings > Accounts

### TR54-E3: Provider Schema & Field Ownership (IN PLAN)
**Responsibility**: Registry-first schema definition

Implementation approach:
- Central registry (not per-connector custom fields)
- Field schema:
  ```python
  {
    "field_key": "api_key",
    "field_type": "secret",  # secret, string, int, bool, select
    "label": "API Key",
    "required": True,
    "help_text": "Get from account settings at example.com",
    "validation_pattern": "^key_.*$",
    "owner": "connector:github",
  }
  ```
- Owner = which component is responsible for maintaining
- Schema enforced at field set/get time

Key deliverables:
- `ui/launcher/accounts/provider_schema_registry.py` - Schema registry
- `ui/launcher/config/field_validation.py` - Validation logic

### TR54-E4: Storage Boundary & Data Minimization (IN PLAN)
**Responsibility**: Keep secrets out of logs/snapshots

Implementation approach:
- Audit: Find all log calls
- Replace all `{secret}` with `{secret[:4]}...`
- Exclude secrets from snapshots (for testing/export)
- Never log full credentials, API keys, tokens
- Sanitize error messages (remove secrets)

Key deliverables:
- `ui/launcher/config/secret_sanitizer.py` - Sanitization utilities
- Integration with logging + snapshot builders

### TR54-E5: Account Troubleshooting Paths (IN PLAN)
**Responsibility**: Deterministic recovery for account failures

Implementation approach:
- Troubleshooting flows per connector type
- GitHub example:
  1. "Reconnect" → re-auth flow
  2. "Verify" → test token (actual API call)
  3. "Remove" → clear credentials
  4. If fails: "View details" → show actual error message from API

- Copy should point to one owner and one next step:
  - ✗ "Something went wrong" (unclear)
  - ✓ "Connection test failed. Try Reconnecting to re-authenticate."

Key deliverables:
- `ui/launcher/accounts/account_troubleshooting.py` - Troubleshooting flows
- `ui/launcher/views/account_error_dialog.py` - Error display

---

## Phase 6: Integration & Closeout (TR54-F)

### TR54-F1: Wave-by-Wave Validation Matrix (IN PLAN)
**Responsibility**: Test coverage per extraction wave

Test matrix:
```
Wave 1 (Snapshots):
  - [ ] Unit: Cache TTL, refresh semantics
  - [ ] Integration: Snapshot propagates to views
  - [ ] Smoke: Launcher starts < 3000ms

Wave 2 (Polling):
  - [ ] Unit: Poll tick rate, startup phase timing
  - [ ] Integration: Health signal updates views
  - [ ] Smoke: Topbar status updates on poll

Wave 3 (Orchestration):
  - [ ] Unit: Shell orchestrator, tab navigation
  - [ ] Integration: Chat flow works end-to-end
  - [ ] Smoke: All views accessible

...and so on for each wave
```

Key deliverables:
- `tests/integration/wave_validation_matrix.py` - Test matrix
- `tests/integration/test_extraction_waves.py` - Wave-by-wave tests

### TR54-F2: Release Lane Closeout (IN PLAN)
**Responsibility**: Prepare for release

Checklist:
- [ ] All files < 550 lines (verified)
- [ ] No cyclic imports (py_compile check)
- [ ] All tests passing (unit + integration + smoke)
- [ ] Performance budget maintained (startup < 3000ms)
- [ ] Zero regressions (screenshot comparison)
- [ ] Documentation updated (README, architecture docs)
- [ ] Release notes drafted (what changed, why)
- [ ] Branch cleaned (no debug code, commented code removed)

Key deliverables:
- Release checklist document
- Updated architecture documentation
- Release notes

### TR54-F3: Done Definition Verification (IN PLAN)
**Responsibility**: Verify all acceptance criteria met

Done criteria:
- [x] All extraction seams documented (TR54-A1)
- [x] Line-cap reset plan created (TR54-A2)
- [x] Merge choreography defined (TR54-A3)
- [x] Orchestration modules created (TR54-B1, D1, D4)
- [x] Design tokens enforced (TR54-B12)
- [x] View decomposition guide created (B4-B11)
- [x] Tool action registry hardened (TR54-C1)
- [x] Tool permissions split (TR54-C2)
- [ ] All remaining modules implemented (C3-C5, D2-D5, E1-E5)
- [ ] All tests green (F1)
- [ ] Release ready (F2)
- [ ] Zero regressions (F3)

---

## Integration Roadmap

### Month 1: Foundation
- ✅ Phase 1: Planning and seams (COMPLETE)
- ✅ Phase 2: Initial orchestration (partial - in progress)

### Month 2: Views & Governance
- Phase 2: Complete view guide
- Phase 3: Tool governance + settings
- Phase 4: Desktop hardening (parallel)

### Month 3: Accounts & Release
- Phase 5: Account lifecycle and storage
- Phase 6: Testing and release preparation

---

## Key Decision Points

1. **Extraction Pace**: Implement all modules first, then integrate? Or integrated staged rollout?
   - **Recommendation**: All modules first, then systematic integration per wave
   - **Reason**: Reduces risk of breaking something during integration

2. **Testing Coverage**: What's the minimum coverage for "done"?
   - **Recommendation**: Unit tests for all modules, integration tests for waves, smoke tests for launcher
   - **Pass threshold**: 100% of happy-path flows working, < 5% regression

3. **Rollout Strategy**: Ship all changes at once, or staged rollout?
   - **Recommendation**: Ship Wave 1-2 together (foundation), then Wave 3-6 in separate releases
   - **Reason**: Allows gathering feedback on foundation before larger changes

---

## Success Criteria (Final)

- [x] All files < 550 lines
- [ ] All modules functional (unit tested)
- [ ] All waves integrated (integration tested)
- [ ] Startup performance maintained (< 3000ms)
- [ ] Zero visual regressions
- [ ] All signal connections verified
- [ ] Security posture improved (secrets protected, policies audited)
- [ ] Account management improved (clear state, deterministic recovery)
- [ ] Documentation complete (architecture, troubleshooting, contributors)
- [ ] Ready to ship to production

