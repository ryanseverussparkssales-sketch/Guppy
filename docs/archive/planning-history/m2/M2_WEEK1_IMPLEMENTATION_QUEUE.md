# M2 Week 1 Implementation Queue

Window: Week of Apr 15, 2026  
Objective: complete Week 1 design-to-skeleton work with mergeable increments and daily validation.

## Gate Baseline Executed (Apr 13, 2026)

1. Architecture boundary check: pass
2. Wrapper integrity check: pass
3. Doc ownership check: pass
4. New module line-cap check: pass
5. Test gate: 45 passed

## Queue (File-by-File)

Current execution status:

1. W1-01 completed on Apr 13, 2026
2. W1-02 completed on Apr 13, 2026
3. W1-03 reopened on Apr 14, 2026 after doc-to-tree drift review
4. W1-04 completed on Apr 13, 2026
5. W1-05 completed on Apr 13, 2026
6. W1-06 next in queue

Session review (Apr 13, 2026):

1. Chat reliability fix shipped: route-aware API rate-limit buckets prevent status polling from consuming chat quota.
2. W1-01 shipped: robust instance config/state normalization and warnings for malformed data.
3. W1-02 shipped: topbar active-instance switcher with launcher wiring and per-instance transcript restore.
4. W1-03 shipped: Persona Builder mockup controls (tone/verbosity sliders, teaching style, scope toggle) with live prompt preview.
5. W1-04 shipped: models view route strategy panel for simple/complex/teaching with fallback-chain validation and read-only summary.
6. W1-05 shipped: voices view now surfaces engine readiness/default binding plus capability validation hooks and interruption-safe non-blocking preview handling.
7. Validation evidence: targeted launcher/model/voice tests passing for W1-04/W1-05 changes.

Drift correction (Apr 14, 2026):

1. W1-03 should remain open. The current `settings_view.py` in tree still exposes runtime profile, mode, surface, and toggle controls only.
2. The shipped-in-docs claim for tone/verbosity sliders, teaching style, scope toggle, and live preview overstated actual implementation.
3. Keep Persona Builder v1 in active work until the launcher Settings view contains the mockup controls and preview state.

### W1-01 Instance Manager Schema Hardening

Files:

- [config/instances.json](config/instances.json)
- [runtime/instance_state.json](runtime/instance_state.json)
- [guppy_api.py](guppy_api.py)

Tasks:

1. Tighten schema defaults and error messages for missing/invalid instance entries.
2. Ensure runtime state auto-heals when unknown instance names are present.
3. Add deterministic ordering for instance listing and status output.

Acceptance:

1. GET /instances remains stable when config contains malformed entries.
2. Unknown runtime instance keys are ignored without crash.

### W1-02 Home Header Quick-Switcher Skeleton

Files:

- [ui/launcher/components/topbar.py](ui/launcher/components/topbar.py)
- [ui/launcher/launcher_window.py](ui/launcher/launcher_window.py)
- [ui/launcher/views/assistant_view.py](ui/launcher/views/assistant_view.py)

Tasks:

1. Add active-instance selector control in top bar.
2. Wire selection signal into launcher state and session label refresh.
3. Keep current transcript restore behavior consistent per instance.

Acceptance:

1. Switching active instance updates session strip immediately.
2. No regression in send/cancel behavior while switching.

### W1-03 Persona Builder v1 Mockup (No Heavy Handlers)

Files:

- [ui/launcher/views/settings_view.py](ui/launcher/views/settings_view.py)
- [runtime/persona_config.json](runtime/persona_config.json)
- [M2_UI_QUICK_REFERENCE.md](M2_UI_QUICK_REFERENCE.md)

Tasks:

1. Add visible slider/select controls for tone, verbosity, and teaching style.
2. Add scope toggle scaffold for global vs per-model.
3. Render live preview panel from control state, without backend mutation yet.

Acceptance:

1. Control changes update preview without exceptions.
2. Existing settings save path remains unaffected.

### W1-04 Model Route Binding Finalization

Files:

- [ui/launcher/views/models_view.py](ui/launcher/views/models_view.py)
- [runtime/provider_registry.json](runtime/provider_registry.json)
- [src/guppy/inference/router.py](/c:/Users/Ryan/Guppy/src/guppy/inference/router.py)

Tasks:

1. Align model category labels with task types used by router.
2. Validate fallback chain UI values against provider registry entries.
3. Expose read-only route summary block in models view.

Acceptance:

1. Invalid fallback models are rejected in UI with clear error text.
2. Route summary matches registry and router task types.

### W1-05 Voice Engine Abstraction Design Stub

Files:

- [ui/launcher/views/voices_view.py](ui/launcher/views/voices_view.py)
- [runtime/voice_bindings.json](runtime/voice_bindings.json)
- [src/guppy/voice/voice.py](/c:/Users/Ryan/Guppy/src/guppy/voice/voice.py)

Tasks:

1. Surface supported engines and selected default in voices view.
2. Add validation hook points for engine capability checks.
3. Keep preview path interruption-safe and non-blocking.

Acceptance:

1. Engine list displays from runtime data without freezing UI.
2. Preview stop on user interruption remains reliable.

### W1-06 Agent Tools and App Management Split Skeleton

Files:

- [ui/launcher/views/tools_view.py](ui/launcher/views/tools_view.py)
- [ui/launcher/views/advanced_view.py](ui/launcher/views/advanced_view.py)
- [ui/launcher/launcher_window.py](ui/launcher/launcher_window.py)

Tasks:

1. Separate instance-level actions from operator-level recovery actions.
2. Keep existing recovery actions functional in the operator surface.
3. Add explicit labels clarifying instance scope vs app scope.

Acceptance:

1. Recovery actions still execute and report outcome.
2. Tool controls no longer appear mixed with operator controls.

### W1-07 Capability Enforcement First Slice

Files:

- [config/tool_permissions.json](config/tool_permissions.json)
- [guppy_api.py](guppy_api.py)
- [guppy_core/tool_runner.py](guppy_core/tool_runner.py)
- [guppy_core/beta_policy.py](guppy_core/beta_policy.py)

Tasks:

1. Enforce deny-by-default behavior server-side for restricted instance tools.
2. Return explicit blocked status with human-readable reason.
3. Log blocked attempts to existing telemetry channels.

Acceptance:

1. Unauthorized tool calls are blocked even if UI allows invocation.
2. Block events are visible in runtime telemetry.

## Test Queue for Week 1

Files:

- [tests/smoke/test_launcher_interactions_smoke.py](tests/smoke/test_launcher_interactions_smoke.py)
- [tests/smoke/test_runtime_smoke.py](tests/smoke/test_runtime_smoke.py)
- [tests/unit/test_security_hardening.py](tests/unit/test_security_hardening.py)
- [tests](tests)

Tasks:

1. Expand smoke tests for active-instance switching and session-strip updates.
2. Add security tests for capability enforcement deny paths.
3. Add API tests for instance listing resiliency and query busy timeout contract.

## Daily Execution Cadence (Week 1)

1. Start day: run gate checks before first code change.
2. During day: complete one queue item at a time, with tests after each item.
3. End day: rerun full gate and update this file with pass/fail and carry-forward notes.

## Command Block

Use this command set at start and end of each day:

1. .\\.venv\\Scripts\\python.exe tools/check_architecture_boundaries.py
2. .\\.venv\\Scripts\\python.exe tools/check_wrapper_integrity.py
3. .\\.venv\\Scripts\\python.exe tools/check_doc_ownership.py
4. .\\.venv\\Scripts\\python.exe tools/check_new_module_line_cap.py
5. .\\.venv\\Scripts\\python.exe -m pytest tests/smoke/test_runtime_smoke.py tests/smoke/test_launcher_interactions_smoke.py tests/unit/test_security_hardening.py -v

