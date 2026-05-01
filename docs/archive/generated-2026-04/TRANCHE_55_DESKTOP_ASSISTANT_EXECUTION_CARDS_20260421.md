# Tranche 55 Desktop Assistant Execution Cards

Date: April 21, 2026

Status: planned

## Program intent

This tranche converts the active `P6` hardening lane into an end-state execution deck for the actual Guppy product contract.

The goal is not to add new surface sprawl. The goal is to close the remaining gap between the current five-hub shell and the intended Windows desktop assistant:

1. One five-pane desktop launcher.
2. One tray/background companion.
3. One chat-first daily workflow.
4. Honest local-model execution on the user's hardware.
5. Persistent memory, files, media, and tools that stay coherent across desktop and backup web surfaces.

## Source-of-truth inputs consulted

1. `docs/PROJECT_BRIEF.md` - single active roadmap, status, and tranche source.
2. `ROADMAP.md` - pointer-only compatibility stub confirming the brief is canonical.
3. `docs/GUPPY_PRODUCT_NORTH_STAR.md` - chat-first, personal, persistent, calm product contract.
4. `docs/PRODUCT_FEATURE_FILTER.md` - keep/cut/demote/defer filter for scope discipline.
5. `docs/generated/PRE_LAUNCH_READINESS_20260420.md` - current release posture is `LIMITED GO`.
6. `docs/generated/TRANCHE_54_MODULE_BREAKUP_AND_STITCH_EXECUTION_CARDS_20260420.md` - current decomposition and hardening card style baseline.

## End-state product contract

1. Guppy remains exactly a five-hub desktop application: `HOME`, `MODELS`, `TOOLS`, `LIBRARY`, `SETTINGS`.
2. `HOME` stays the daily chat surface and absorbs workspace continuity without turning Workspaces into a sixth primary nav destination.
3. A tray/background companion stays alive outside the main launcher and reflects current runtime, workspace, and health truth without inventing a second product.
4. Local execution remains first-class: Ollama stable by default, LM Studio discovery/readiness-visible, Lemonade challenger-visible, `local_harness` development/evidence-visible, and any future lanes such as AnythingLLM or Hugging Face local must land behind explicit adapter contracts and truthful readiness labels.
5. `SETTINGS` owns API keys, credentials, diagnostics, recovery, admin controls, machine/runtime posture, and provider/plugin lifecycle.
6. `MODELS` owns model/persona/voice routing decisions, local runtime readiness, loadouts, and voice-backend evidence.
7. `TOOLS` owns tool inventory, permissions, traces, web-search-capable tools, and future plugin/tool addition flows, while credentials still route back to `SETTINGS`.
8. `LIBRARY` owns files, notes, saved artifacts, media playback, and handoff back into chat, while persistent memory stays chat-facing and workspace-aware.
9. The backup web UI is a secondary surface only. It must speak the same backend truth as desktop rather than reviving a separate scaffold contract.

## End-state execution checklist

- [ ] Launcher bootstrap truth is restored across CLI, root shims, compat wrappers, and packaged entrypoints.
- [ ] The tray/background app and the main launcher share one bounded runtime/status contract.
- [ ] Home chat, workspace context, and library handoff remain calm and primary.
- [ ] Local provider lanes are honest and testable for Ollama, LM Studio, Lemonade, and `local_harness`.
- [ ] Planned adapter lanes such as AnythingLLM and Hugging Face local have registry-backed onboarding and honest non-ready states until implemented.
- [ ] Voice interruption, TTS, STT, preview, and binding flows are validated on real devices and surfaced clearly in Models plus Settings.
- [ ] Persistent memory survives restart, stays workspace-aware, and improves chat continuity without noisy operator UI.
- [ ] Library notes, artifacts, and media playback flow cleanly into Home chat.
- [ ] Tool addition, permissioning, traces, web-search-capable tooling, and plugin-style onboarding all route through one canonical registry pattern.
- [ ] API key storage and provider/plugin lifecycle remain Settings-owned, keyring-first, and explicit about degraded storage modes.
- [ ] The backup web UI stays wired to `/status`, `/instances`, and `/chat` instead of a parallel legacy API shape.
- [ ] Packaging, diagnostics, release-check, runtime matrix, and voice matrix all converge on one honest launch readiness posture.

## Tranche map

1. `TR55-A` Launcher, tray, and entrypoint truth.
2. `TR55-B` Local runtime and provider parity.
3. `TR55-C` Voice, TTS, STT, and multimodal controls.
4. `TR55-D` Memory, library, media, and continuity.
5. `TR55-E` Tools, plugins, web fallback, and admin/control surfaces.
6. `TR55-F` Packaging, diagnostics, validation, and launch closeout.

## TR55-A cards (launcher, tray, and entrypoints)

### `TR55-A1` Launcher bootstrap reconciliation card
- Scope: restore one truthful launcher path across CLI, compat wrappers, desktop shortcuts, and packaged output.
- Files: `src/guppy/cli/launch.py`, `src/guppy/apps/launcher_app.py`, `compat_shims/launcher_ui/launcher_app.py`, `compat_shims/launcher_ui/guppy_launcher.py`, root `guppy_launcher.py` shim if retained.
- Acceptance:
1. Every supported launcher surface resolves to a real module.
2. Launcher bootstrap/import smoke passes without compatibility guesswork.
3. `docs/PROJECT_BRIEF.md` launcher-path wording matches the live tree.

### `TR55-A2` Tray/background handshake card
- Scope: keep the tray companion alive, quiet, and synchronized with launcher/runtime truth.
- Files: `src/guppy/apps/hub_app.py`, `guppy_hub.py`, `src/guppy/launcher_application/shell_status.py`, `src/guppy/launcher_application/status_poll.py`, `src/guppy/launcher_application/launcher_api_runtime_control.py`.
- Acceptance:
1. Tray and launcher do not diverge on current workspace, runtime health, or readiness language.
2. Background/offline degradation is visible but calm.
3. No second ownership island appears outside the five-hub shell.

### `TR55-A3` Home and workspace continuity card
- Scope: preserve chat-first Home while making workspace context reliable and obvious.
- Files: `compat_shims/launcher_ui/ui/launcher/views/assistant_view.py`, `assistant_context.py`, `assistant_active_context.py`, `src/guppy/launcher_application/home_presenter.py`, `workspace_activation.py`, `workspace_refresh.py`.
- Acceptance:
1. A returning user can resume the right workspace and context without hunting.
2. Workspace controls stay subordinate to the daily chat path.
3. Home does not re-accumulate diagnostics or model-operator clutter.

## TR55-B cards (local runtime and provider parity)

### `TR55-B1` Provider tier and readiness truth card
- Scope: lock clear runtime/provider truth across stable, optional, and experimental lanes.
- Files: `src/guppy/launcher_application/provider_registry.py`, `src/guppy/launcher_application/local_model_readiness.py`, `src/guppy/workspace_governance/provider_status.py`, `compat_shims/launcher_ui/ui/launcher/views/models_hub_view.py`.
- Acceptance:
1. Every provider has a visible tier and a truthful readiness state.
2. No UI copy implies a provider is runnable when it is only planned or discovered.
3. Models and Settings use the same provider lifecycle language.

### `TR55-B2` Local runtime adapter parity card
- Scope: keep local execution first-class on the user's hardware.
- Files: `src/guppy/local_llm/runtime_challengers.py`, `src/guppy/api/server_runtime.py`, `src/guppy/launcher_application/models_route_support.py`, `compat_shims/launcher_ui/ui/launcher/views/models_view.py`, `local_llm_view.py`.
- Acceptance:
1. Ollama, LM Studio, Lemonade, and `local_harness` each have an honest path for readiness, invocation, and failure messaging.
2. Models Hub can show why a lane is ready, missing, or experimental.
3. Runtime fallback behavior is explicit instead of silent.

### `TR55-B3` Planned adapter contract card
- Scope: define how non-core lanes join without becoming fake-ready features.
- Files: `src/guppy/launcher_application/provider_registry.py`, `src/guppy/workspace_governance/connector_metadata.py`, `src/guppy/workspace_governance/connector_service.py`, Settings and Models onboarding surfaces.
- Acceptance:
1. Planned adapters such as AnythingLLM and Hugging Face local have registry slots and explicit `planned` or `not installed` states.
2. Future additions do not require bespoke per-provider UI branches.
3. The product stays honest about what is available today versus later.

## TR55-C cards (voice, TTS, and STT)

### `TR55-C1` Voice interruption and preview reliability card
- Scope: finish the real-device validation path for voice behavior.
- Files: `src/guppy/voice/voice.py`, `src/guppy/voice/voice_runtime.py`, `src/guppy/voice/voice_support.py`, `compat_shims/launcher_ui/ui/launcher/views/voices_view.py`, `docs/generated/VOICE_VALIDATION_MATRIX.md`.
- Acceptance:
1. Push-to-talk, interruption on typing, preview playback, and fallback behavior match the documented launcher state.
2. Voice failures are diagnosable without leaking noise into Home.
3. Matrix rows are closed with real-device evidence instead of assumptions.

### `TR55-C2` TTS/STT backend ownership card
- Scope: keep backend choice visible in Models while credential and provider lifecycle stays in Settings.
- Files: `compat_shims/launcher_ui/ui/launcher/views/models_hub_view.py`, `voices_view.py`, `settings_device_accounts_panel.py`, `src/guppy/launcher_application/settings_device_accounts_presenter.py`, `src/guppy/launcher_application/connector_workflow.py`.
- Acceptance:
1. A user can tell which TTS and STT backends are active and what is required to change them.
2. Verification, reconnect, disable, and remove flows stay registry-backed.
3. Models never becomes a hidden credential editor.

## TR55-D cards (memory, library, media, continuity)

### `TR55-D1` Persistent memory continuity card
- Scope: make memory visibly useful to returning chat sessions without dashboarding it.
- Files: `src/guppy/memory/memory.py`, `memory_store.py`, `semantic.py`, `backend_adapter.py`, `compat_shims/launcher_ui/ui/launcher/views/assistant_view.py`.
- Acceptance:
1. Durable memory survives restart and improves context carry-through.
2. Workspace-aware recall is bounded and explainable.
3. Missing or degraded memory backends fail honestly without breaking chat.

### `TR55-D2` Library and media handoff card
- Scope: tighten the file, notes, artifact, and playback loop back into Home.
- Files: `src/guppy/launcher_application/library_workflow.py`, `library_presenter.py`, `library_media.py`, `compat_shims/launcher_ui/ui/launcher/views/library_view.py`, `library_media_panel.py`, `library_editor_support.py`.
- Acceptance:
1. Notes, saved artifacts, and approved-root files can be reused in chat with clear origin/context.
2. Local audio/video playback remains stable in the Library hub.
3. Library does not become a duplicate workspace manager or settings surface.

## TR55-E cards (tools, plugins, web fallback, admin)

### `TR55-E1` Tool and plugin registry card
- Scope: converge new tools, connectors, and plugin-style additions on one lifecycle model.
- Files: `src/guppy/launcher_application/tool_action_registry.py`, `tool_readiness.py`, `connector_workflow.py`, `src/guppy/workspace_governance/connector_service.py`, `compat_shims/launcher_ui/ui/launcher/views/tools_view.py`, `tools_view_cards.py`.
- Acceptance:
1. Tool add, remove, verify, reconnect, disable, and permission flows share canonical language.
2. Web-search-capable tools, document helpers, and future plugins do not invent separate onboarding systems.
3. Tools owns capability posture; Settings still owns secrets and recovery.

### `TR55-E2` Backup web parity card
- Scope: keep the fallback web shell useful without letting it drift into a second product.
- Files: `web/src/hooks/useAPI.ts`, `web/src/hooks/useAppState.ts`, `web/src/pages/Assistant.tsx`, `Workspace.tsx`, `Models.tsx`, `src/guppy/api/service.py`.
- Acceptance:
1. Web uses the same backend truth as desktop: `/status`, `/instances`, `/chat`.
2. Runtime, workspace, and model state labels mean the same thing in both surfaces.
3. Web-only placeholder routes and fake scaffold contracts do not return.

### `TR55-E3` Diagnostics, admin, and machine-control card
- Scope: keep power and recovery visible, but demoted to the correct surfaces.
- Files: `compat_shims/launcher_ui/ui/launcher/views/settings_hub_view.py`, `settings_operations_panel.py`, `settings_terminal_panel.py`, `src/guppy/launcher_application/windows_ops_runtime.py`, `windows_ops_presenter.py`, `packaging_audit.py`, `security_gate.py`.
- Acceptance:
1. Diagnostics, admin controls, and machine actions stay inside Settings-owned recovery surfaces.
2. Output paths and next steps are explicit.
3. Home remains calm even when the machine/runtime is degraded.

## TR55-F cards (packaging, validation, closeout)

### `TR55-F1` Secret storage and machine-auth posture card
- Scope: keep key storage and repair/admin trust explicit.
- Files: `utils/secret_store.py`, `src/guppy/workspace_governance/machine_auth.py`, `src/guppy/launcher_application/settings_device_accounts_presenter.py`, `src/guppy/api/server_runtime_auth_request_support.py`.
- Acceptance:
1. Keyring-first posture is visible and degraded fallback modes are honest.
2. Desktop, tray, and backup web auth bootstrap assumptions are compatible.
3. Secrets do not leak into diagnostics, snapshots, or support bundles.

### `TR55-F2` Runtime and voice matrix closeout card
- Scope: close remaining real-machine validation rows before final launch claims.
- Files: `docs/generated/RUNTIME_VALIDATION_MATRIX.md`, `docs/generated/VOICE_VALIDATION_MATRIX.md`, `docs/generated/VOICE_RUNTIME_VALIDATION_PREFILL.md`, runtime verification tools.
- Acceptance:
1. Remaining runtime and voice rows are executed or explicitly waived with dated rationale.
2. Packaging/device truth is based on current-machine evidence.
3. `LIMITED GO` can only advance when matrix evidence supports it.

### `TR55-F3` Honest launch readiness card
- Scope: unify packaging, diagnostics, release-check, and product-surface claims.
- Files: `tools/dev_workflow.py`, `tools/validate_build_checks.py`, `docs/generated/PRE_LAUNCH_READINESS_20260420.md`, `docs/PACKAGING.md`, launcher smoke and runtime smoke suites.
- Acceptance:
1. Release-check, smoke, packaging truth, and launcher entrypoint truth all agree.
2. No doc or UI copy claims a capability that the current build cannot prove.
3. Final launch posture reads `GO` only when desktop shell, tray, runtime, voice, and backup web parity all have supporting evidence.

## Recommended execution order

1. `TR55-A1`, `TR55-A2`, and `TR55-E2` first so launcher, tray, and web all target one real backend contract.
2. `TR55-B1`, `TR55-B2`, and `TR55-C2` next so provider/voice ownership language stops drifting.
3. `TR55-C1`, `TR55-D1`, and `TR55-D2` after that so daily continuity feels real on an actual machine.
4. `TR55-E1`, `TR55-E3`, and `TR55-F1` next so extensibility, secrets, and admin surfaces stay coherent.
5. `TR55-F2` and `TR55-F3` last as the honest launch gate.

## Done means

1. The product behaves like one calm desktop assistant instead of a launcher shell plus side projects.
2. Desktop launcher, tray app, and fallback web UI all agree on runtime/workspace/chat truth.
3. The local-first promise is real on a user machine, not just in docs or mocks.
4. The remaining power surfaces are strong but demoted, and the daily chat path stays primary.
