# Runtime Validation Matrix

**Last updated: April 21, 2026**  
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

## Disposition Key

| Value | Meaning |
|---|---|
| `PASS` | Executed in this closeout pass on the current machine and supported by refreshed evidence. |
| `PREFILLED` | Current-machine or repo-owned evidence exists, but the full end-to-end/manual scenario was not executed here. |
| `WAIVED` | Not executed in this pass; dated rationale explains why no truthful claim was made. |

---

## Structural Checks Already In Repo

| Area | Current Structural Check |
|---|---|
| Local runtime | `python tools/verify_local_model_runtime.py --prompt ok` |
| Provider runtime | `python tools/verify_provider_runtime.py` |
| Provider lightweight smoke | `python tools/verify_provider_runtime.py --smoke` |
| Packaging/build assumptions | `python tools/validate_build_checks.py` |
| Product smoke | `python tools/dev_workflow.py test-smoke` |
| Full guarded release lane | `python tools/dev_workflow.py release-check` |

---

## Real-Machine Follow-Up Matrix

| ID | Area | Machine / Environment | Steps | Expected Result | Disposition | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|---|
| RT-01 | Ollama local runtime | Primary Windows dev box | Run `python tools/verify_local_model_runtime.py --prompt ok` with Ollama loaded and confirm the returned snapshot matches the live loaded model. | Runtime snapshot agrees with the actually loaded local model and prompt succeeds without timeout drift. | PASS | Executed on April 21, 2026 (local) with `.venv\Scripts\python.exe tools/verify_local_model_runtime.py --prompt ok`. `runtime/model_runtime_snapshot.json` refreshed at `2026-04-22T03:53:27.324959+00:00`; all requested manifest models were present, every ping result was `ok`, and `ollama ps` returned active residency. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| RT-02 | Lemonade local runtime | Lemonade-configured machine | Run the local runtime checks on a machine with Lemonade configured and a mapped model present. | Lemonade model discovery and request path behave the same way the launcher readiness surface reports. | WAIVED | `runtime/app_settings.json` includes Lemonade URL/model placeholders, but this repo-owned evidence set does not include a machine with a live Lemonade runtime plus mapped models on April 21, 2026. No truthful discovery/request result could be claimed from this machine. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| RT-03 | Provider smoke lane | Machine with live provider keys | Run `python tools/verify_provider_runtime.py --smoke`. | Live provider model-list checks succeed for the intentionally configured providers. | PASS | Executed on April 21, 2026 (local) with `.venv\Scripts\python.exe tools/verify_provider_runtime.py --smoke`. `runtime/provider_runtime_snapshot.json` refreshed at `2026-04-22T03:55:29.884624+00:00` with `overall_state=READY`; Anthropic smoke passed (`models listed: 5`). OpenRouter, Groq, Gemini, and Mistral were not configured on this machine, so they remained out of scope for this pass. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| RT-04 | Voice engine playback | Real audio output device | Complete the scenarios in `docs/generated/VOICE_VALIDATION_MATRIX.md`. | Real playback, interruption, fallback, and assignment behavior match the documented launcher state. | PREFILLED | Closed by reference to the April 21, 2026 refresh of `docs/generated/VOICE_VALIDATION_MATRIX.md`. No new audible playback was executed in this pass; the linked matrix now marks each voice row as `PREFILLED` or `WAIVED` where real-device evidence is still missing. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| RT-05 | Hot device changes | Machine with removable audio devices | Change microphone and/or speaker devices during a live session, then retry voice flows. | Runtime recovers cleanly or reports a clear operator-visible failure. | WAIVED | Current-machine evidence was refreshed only to the level of device inventory (`sounddevice=True`, 57 devices detected, default input/output unresolved in the prefill snapshot). No removable-device hot-swap exercise was run on April 21, 2026, so recovery behavior remains unverified. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| RT-06 | Post-package runtime spot check | Fresh package or dist output | Launch the packaged or dist surface and run a minimal runtime smoke walk. | Launcher/API/runtime status agrees with the packaged environment and no packaging-only regressions appear. | PREFILLED | Packaging evidence exists from `runtime/windows_release_receipt.json` and `runtime/windows_release_summary.md` dated April 20, 2026, including `dist/Guppy/Guppy.exe`. This closeout pass did not launch the packaged build for a same-machine runtime walk, so the row is evidence-only rather than a pass. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |

---

## Sign-Off

| Group | Status | Notes |
|---|---|---|
| Local runtime parity | PARTIAL PASS | Ollama local runtime was executed on April 21, 2026; Lemonade still lacks a live-machine evidence source. |
| Provider connectivity | PARTIAL PASS | Anthropic smoke passed on this machine; other providers remain unconfigured here. |
| Voice/device behavior | EVIDENCE ONLY | Use `VOICE_VALIDATION_MATRIX.md` for the row-by-row closeout state. |
| Post-package runtime spot check | EVIDENCE ONLY | Packaging receipt exists, but no packaged-launch runtime walk was executed in this pass. |
