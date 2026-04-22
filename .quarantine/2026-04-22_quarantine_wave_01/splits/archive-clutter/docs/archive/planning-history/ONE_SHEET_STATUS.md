# Guppy Honest One-Sheet

Date: April 12-13, 2026
Audience: product owner + engineering handoff

## Executive Readout

Guppy has strong infrastructure and operating tooling, but is not pilot-release ready at this moment.
Current gate status is NO_GO due to local model fleet ping timeout, not due to missing core scaffolding.

A full reliability pass was completed April 12-13, 2026 covering: launcher bootstrap, IPC atomicity,
/repair endpoint auth, guppy_core package split, and UI layout overhaul. These remove the primary
structural debt and are not reflected in the NO_GO — the gate failure is model-fleet only.

## How Far Are We (Honest Estimate)

1. Infrastructure and observability: 90% complete.
2. Day-to-day reliability hardening: 85% complete.
3. Product UX builder completeness (persona/model/voice): 55% complete.
4. AI context quality (shared memory, grounded recall consistency): 50% complete.
5. Pilot release readiness overall: 65% complete (blocked by current NO_GO gate instability).

## Timeline (Honest)

### Completed in current cycle (through 2026-04-13)

1. Unified launcher is the primary app surface and is functionally usable.
2. Runtime hardening is in place: schema audits, logging health checks, telemetry mirror, resource envelope checks.
3. Off-hours worker was hardened (stale-running recovery, cleaner output, autostart fallback path).
4. Triage stack improved: nightly summary, regression state, decision canary, and fault-injection canary.
5. Seed vault storage rollout is now concrete: USB snapshots now, NAS path ready next.
6. Launcher auto-bootstrap: guppy_api.py and guppy_hub.py now start automatically on launcher open.
7. IPC atomicity: all .cmd and .status file writes are now atomic (temp+rename) via utils/safe_io.py.
8. /repair endpoint secured: per-process token written to runtime/repair_token.txt, verified on every call.
9. guppy_core refactored: 2,511-line monolith split into guppy_core/ package with clean submodules.
10. PowerShell window flashing eliminated: CREATE_NO_WINDOW applied to all subprocess calls.
11. UI layout overhaul: chat input + integrated status strip, agent cards in status panel, dropdowns at bottom.
12. JSONL rotation implemented: session_events.jsonl and launcher_events.jsonl now cap at 20MB.

### Next 7 days (critical stabilization)

1. Fix local model fleet ping instability in `tools/verify_ollama_runtime.py` path (timeouts under load).
2. Reconcile triage artifact ordering so summaries and gate outputs never disagree by run window.
3. Lock the daily pilot gate to stable GO/LIMITED_GO over repeated runs.
4. Confirm unattended startup path on real sign-in/reboot scenarios.

### Next 30 days (roadmap window)

1. Track 1 completion: persona/model/voice builder UX in launcher (no JSON editing required).
2. Track 2 completion: full daily workflow productization + shared memory catalog v1.
3. Track 3 progress: Windows installer/update path and broader hardware fallback profile handling.

## Roadmap Summary (Condensed)

1. Track 1 (highest): full custom builder UX for persona, model assignment, and voice mapping.
2. Track 2: daily workflow execution and cross-agent shared memory catalog with citations and confidence metadata.
3. Track 3: Windows productization (installer/update lifecycle, risky-action policies, hardware fallback behavior, remote beta EXE with limited access).
4. Phase 15 extension: Digital Seed Vault + media/wiki librarian with staged storage rollout (USB -> NAS -> scheduled replication).

## Remote Beta Tester EXE Plan (Limited Access)

1. Distribution model: one-folder packaged EXE bundle with runtime config files, no full source checkout required for testers.
2. Access model: restricted tool allowlist; write-side actions require explicit confirmation and are fully logged.
3. API model: per-tester token scopes, revocable credentials, and request rate limits.
4. Data model: tester profile stores only minimal local runtime data and encrypted token material.
5. Validation model: dedicated beta gate with auth, tool policy, and telemetry checks before each beta drop.

Implementation status (now):

1. Runtime enforcement added in `guppy_core.run_tool()` behind `GUPPY_BETA_RESTRICTED_MODE=1`.
2. Default allowlist file added at `config/beta_tool_allowlist.txt`.
3. Policy verifier added: `python tools/verify_beta_package_policy.py`.

## Current Code State by Subsystem

### Product Surface

1. Strong: modular launcher architecture under `ui/launcher/` with core tabs and status rail.
2. Partial: some tool-surface parity items still planned (rich cards and button-action audit completion).
3. Debt: `guppy_ui.py` remains a large legacy surface with overlap risk against launcher path.

### Inference and Routing

1. Strong: smart routing, fallback chains, semantic classifier path, and routing telemetry.
2. Partial: AI quality still trails ops quality (intent precision and memory-grounded behavior need stronger consistency).
3. Risk: runtime gating can fail on local model ping timeout even when install/runtime snapshots look healthy.

### Voice and Interaction

1. Strong: wake/PTT, interruption handling, TTS fallback path.
2. Partial: real-world latency tuning still needed (wake model and cooldown tuning).

### Runtime Ops and Reliability

1. Strong: pilot gate scripts, logging verifier, provider verifier, overnight orchestration, triage summaries.
2. Strong: off-hours queue processor now hardened with stale recovery and cleaner result logs.
3. Risk: report coherence can drift if artifacts from adjacent runs are compared without strict run IDs.

### Memory, Vault, and Knowledge Layer

1. Strong: persistent + semantic memory backends exist; vault extraction mode exists.
2. New: backup workflow now implemented for USB and NAS targets in `tools/backup_seed_vault.py`.
3. Gap: shared memory catalog behavior is roadmap-defined but not yet fully productized in launcher workflows.

### API, Security, and Supervision

1. Strong: strict-mode auth and supervisor ownership model are in place.
2. Strong: /repair endpoint now requires per-process token auth (runtime/repair_token.txt).
3. Partial: broader provider ecosystem keys are optional and mostly unconfigured by design.

### Quality and Testing

1. Strong: smoke tests, schema audit tests, stress harness, and canary checks are present.
2. Gap: API concurrency behavior needs dedicated test coverage expansion beyond baseline smoke.

## Challenges and Why They Matter

1. Local model ping timeout causes NO_GO.
Impact: blocks pilot readiness despite broader stack health.
Needed: improve ping strategy/timeouts and isolate model-specific startup latency.

2. Legacy surface duplication (`guppy_ui.py` vs launcher).
Impact: feature drift, double-maintenance risk, inconsistent behavior.
Needed: explicit retirement or migration decision with timeline.

3. Memory quality gap vs memory plumbing.
Impact: assistant can store data but still underuses context in critical responses.
Needed: shared catalog retrieval contract and consistent prompt injection paths across surfaces.

4. Triage artifact consistency.
Impact: trust erosion when reports disagree between adjacent timestamps.
Needed: run-id correlation and summary generation against one exact gate snapshot.

5. Write-side tool safety boundary.
Impact: potential wrong-action risk if classifier confidence is weak.
Needed: confidence thresholds, explicit confirmation policy, and action ledger.

## Release Readiness Snapshot (Today)

1. Operational maturity: high.
2. Product polish: medium.
3. AI/context maturity: medium-low.
4. Pilot gate: NO_GO currently (mandatory local model fleet gate failed in latest report).

## Immediate Priority Stack

1. Stabilize gate_2 local fleet readiness first.
2. Freeze-or-migrate decision for legacy `guppy_ui.py`.
3. Implement shared memory catalog v1 retrieval contract and citation flow.
4. Complete launcher action-parity audit for all visible controls.
5. Add automated nightly backup + restore verification drill for seed/media vault data.

## Source Artifacts Used for This Readout

1. `runtime/pilot_exit_report.json`
2. `runtime/nightly_triage_summary.md`
3. `runtime/triage_regression_state.json`
4. `ROADMAP.md`
5. `docs/REMOTE_BETA_EXE_POLICY.md`
6. `config/beta_tool_allowlist.txt`
7. `tools/verify_beta_package_policy.py`
