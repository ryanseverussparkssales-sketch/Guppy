# Runtime Validation Matrix

**Last updated: April 19, 2026**  
**Purpose:** Track the runtime validation work that still needs real-machine execution beyond the repo's structural guardrails and smoke tests.

---

## Scope

This matrix exists because the automated repo checks now cover:
- local/runtime structural readiness
- provider library and key readiness
- packaging/distribution contracts
- launcher/runtime smoke behavior

Those checks do **not** fully replace real-machine validation for voice playback, local model execution, provider connectivity on configured environments, or machine-specific device behavior.

---

## Structural Checks Already In Repo

| Area | Current Structural Check |
|---|---|
| Local runtime | `python tools/verify_ollama_runtime.py --prompt ok` |
| Provider runtime | `python tools/verify_provider_runtime.py` |
| Provider lightweight smoke | `python tools/verify_provider_runtime.py --smoke` |
| Packaging/build assumptions | `python tools/validate_build_checks.py` |
| Product smoke | `python tools/dev_workflow.py test-smoke` |
| Full guarded release lane | `python tools/dev_workflow.py release-check` |

---

## Real-Machine Follow-Up Matrix

| ID | Area | Machine / Environment | Steps | Expected Result | Pass/Fail | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|---|
| RT-01 | Ollama local runtime | Primary Windows dev box | Run `python tools/verify_ollama_runtime.py --prompt ok` with Ollama loaded and confirm the returned snapshot matches the live loaded model. | Runtime snapshot agrees with the actually loaded local model and prompt succeeds without timeout drift. | — | — | — | — |
| RT-02 | Lemonade local runtime | Lemonade-configured machine | Run the local runtime checks on a machine with Lemonade configured and a mapped model present. | Lemonade model discovery and request path behave the same way the launcher readiness surface reports. | — | — | — | — |
| RT-03 | Provider smoke lane | Machine with live provider keys | Run `python tools/verify_provider_runtime.py --smoke`. | Live provider model-list checks succeed for the intentionally configured providers. | — | — | — | — |
| RT-04 | Voice engine playback | Real audio output device | Complete the scenarios in `docs/generated/VOICE_VALIDATION_MATRIX.md`. | Real playback, interruption, fallback, and assignment behavior match the documented launcher state. | — | — | — | — |
| RT-05 | Hot device changes | Machine with removable audio devices | Change microphone and/or speaker devices during a live session, then retry voice flows. | Runtime recovers cleanly or reports a clear operator-visible failure. | — | — | — | — |
| RT-06 | Post-package runtime spot check | Fresh package or dist output | Launch the packaged or dist surface and run a minimal runtime smoke walk. | Launcher/API/runtime status agrees with the packaged environment and no packaging-only regressions appear. | — | — | — | — |

---

## Sign-Off

| Group | Status | Notes |
|---|---|---|
| Local runtime parity | PENDING | Needs at least one Ollama-confirmed and one Lemonade-confirmed machine pass. |
| Provider connectivity | PENDING | Structural readiness exists; live provider smoke remains environment-specific. |
| Voice/device behavior | PENDING | Use `VOICE_VALIDATION_MATRIX.md` as the detailed test sheet. |
| Post-package runtime spot check | PENDING | Run only when a fresh package/dist handoff is being validated. |
