# Voice + Runtime Matrix Prefill Report

Generated (UTC): 2026-04-22T04:02:10.093090+00:00

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
| Git Branch | master |

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

## Voice Runtime Snapshot

| Field | Value |
|---|---|
| Voice Enabled | True |
| Runtime Backend | local_harness |
| Default Voice Binding | EDGE TTS / en-GB-RyanNeural |
| Default Persona | main_guppy |
| Global Persona Assignment | main_guppy |
| Persona Bindings | 1 |
| Model Bindings | 0 |

## Voice Capability Snapshot

| Capability | Value |
|---|---|
| edge_tts importable | True |
| kokoro importable | True |
| faster_whisper importable | True |
| sounddevice importable | True |
| ELEVENLABS_API_KEY present | False |
| GUPPY_TTS_PROVIDER | auto |

## Package Evidence Snapshot

| Field | Value |
|---|---|
| Receipt Timestamp | 2026-04-20T15:26:19.130067+00:00 |
| Packaging Result | True |
| Stage | package |
| Summary | WINDOWS PACKAGE completed 1/1 packaging step(s). |
| Artifact | C:\Users\Ryan\Guppy\dist\Guppy\Guppy.exe |
| Artifact Size | 105005975 |

## Matrix Coverage Summary

| Matrix | Exists | Scenario Rows | Pass | Prefilled | Waived | Pending | Other |
|---|---|---|---|---|---|---|---|
| Voice | True | 28 | 0 | 5 | 23 | 0 | 0 |
| Runtime | True | 6 | 2 | 2 | 2 | 0 | 0 |

## Suggested Matrix Header Prefill

Use these values when filling non-pass/fail metadata fields in matrix headers.

- Tester: Automation prefill on DESKTOP-QARUGE1
- Date Range: 2026-04-21 (local)
- Blocking Issues: Keep manual unless an automation step failed above.

## Manual Follow-Up Still Required

- Execute real-device voice playback, interruption, preview, and hot-plug scenarios before any GO claim.
- Re-run first-run voice setup on a fresh profile; current-machine evidence comes from an already-configured profile.
- Execute Lemonade and packaged-runtime spot checks on machines that actually host those environments.

