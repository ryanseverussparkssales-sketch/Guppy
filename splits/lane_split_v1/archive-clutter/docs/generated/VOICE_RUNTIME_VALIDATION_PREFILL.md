# Voice + Runtime Matrix Prefill Report

Generated (UTC): 2026-04-20T07:28:42.683706+00:00

## Automation Scope

- This report only pre-fills machine/runtime context and does not mark manual pass/fail rows as complete.
- Real-device execution and operator judgment are still required for matrix sign-off.

## Machine Metadata

| Field | Value |
|---|---|
| Hostname | DESKTOP-QARUGE1 |
| OS | Windows 11 |
| Platform | Windows-11-10.0.26200-SP0 |
| Python | 3.12.10 |
| Python Executable | C:\Users\Ryan\Guppy\.venv\Scripts\python.exe |
| Git Branch | chore/worktree-simplify-pass-2026-04-18 |

## Audio Device Snapshot

| Field | Value |
|---|---|
| sounddevice Available | True |
| Device Count | 57 |
| Default Input | unknown (index=None) |
| Default Output | unknown (index=None) |
| Error | none |

## Runtime Snapshot Status

| Source | Status | Path |
|---|---|---|
| Provider Runtime Snapshot | READY | runtime/provider_runtime_snapshot.json |
| Ollama Runtime Snapshot | READY | runtime/model_runtime_snapshot.json |

## Matrix Coverage Summary

| Matrix | Exists | Scenario Rows | Pending Rows |
|---|---|---|---|
| Voice | True | 28 | 11 |
| Runtime | True | 6 | 6 |

## Suggested Matrix Header Prefill

Use these values when filling non-pass/fail metadata fields in matrix headers.

- Tester: Automation prefill on DESKTOP-QARUGE1
- Date Range: 2026-04-20
- Blocking Issues: Keep manual unless an automation step failed above.

## Manual Follow-Up Still Required

- Execute all real-device voice playback, interruption, and hot-plug scenarios in the voice matrix.
- Execute machine-specific runtime/provider checks on environments that actually hold provider keys and target models.

