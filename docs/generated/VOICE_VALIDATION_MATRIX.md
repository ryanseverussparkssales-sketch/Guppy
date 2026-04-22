# Voice Validation Matrix

**Last updated: April 21, 2026**  
**Purpose:** Real-device validation coverage for the Guppy voice system across engines, devices, and user flows.

---

## Validation Status

| Field | Value |
|---|---|
| **Overall Status** | EVIDENCE ONLY - no new real-device playback/capture was executed in this closeout pass |
| **Tester** | Automation prefill on DESKTOP-QARUGE1 |
| **Date Range** | 2026-04-21 (local) with refreshed UTC runtime snapshots on 2026-04-22 |
| **Blocking Issues** | Current machine is already voice-configured; first-run and audible playback claims still need a real-device operator pass |

### Blocking Issues Recorded On April 21, 2026

- No new microphone capture, TTS playback, interruption, preview, or hot-plug scenario was executed in this closeout pass.
- `runtime/voice_bindings.json` and `src/guppy/experience_config/services.py` currently resolve to `EDGE TTS / en-GB-RyanNeural`, so the older `bm_lewis` and kokoro-default assumptions in this matrix cannot be claimed as current-machine defaults.
- The current machine is not a fresh profile, so first-run setup rows cannot be truthfully closed as passes from local evidence alone.

---

## Disposition Key

| Value | Meaning |
|---|---|
| `PASS` | Executed with real-device evidence in this closeout pass. |
| `PREFILLED` | Current-machine config or dependency evidence was captured, but the full end-to-end/manual scenario was not executed here. |
| `WAIVED` | Not executed in this pass; dated rationale explains why no truthful claim was made. |

---

## Risk Register (From PROJECT_BRIEF Current Gaps)

The following risks from `docs/PROJECT_BRIEF.md` Current Gaps apply directly to voice validation:

| Risk ID | Source | Risk Description |
|---|---|---|
| VR-1 | Current Gap 2 | Voice lifecycle still needs broader real-device validation across engines, especially preview behavior on more machines. |
| VR-2 | Current Gap 2 | Engine coverage is not uniform: older docs describe kokoro as the default `auto` path, but current persisted experience-config defaults on this machine are `EDGE TTS / en-GB-RyanNeural`. |
| VR-3 | Current Gap 5 | Workspace framing changes (P1 work) may have side-effects on voice assignment persistence if persona/workspace switching resets active voice selection. |
| VR-4 | VOICE.md | ElevenLabs path depends on `ELEVENLABS_API_KEY` at runtime; environments without that key must not silently imply live ElevenLabs coverage. |
| VR-5 | VOICE.md | SAPI fallback spawns a PowerShell subprocess; interruption via `stop_speaking()` terminates that process, but race conditions between spawn and stop have not been exercised on slow machines. |
| VR-6 | VOICE_SYSTEM_STATUS.md | The reference machine exposes many audio devices, but non-default device selection and hot-plug changes still need direct execution. |
| VR-7 | `runtime/voice_bindings.json`, `src/guppy/experience_config/services.py` | First-run/default-voice claims are currently drift-prone because persisted runtime bindings and fallback defaults do not match older `bm_lewis` wording. |

---

## Validation Matrix

For each scenario, the `Disposition` column records whether the row was executed, prefilled from current-machine evidence, or waived with dated rationale.

### Section A - Push-to-Talk (PTT) Core Flow

| ID | Description | Steps | Expected Result | Disposition | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| PTT-01 | Basic PTT transcript -> response | 1. Hold PTT button. 2. Speak a short phrase ("What time is it?"). 3. Release. | Transcript appears in chat; Guppy speaks a response via active TTS engine. | WAIVED | Requires live microphone capture plus audible TTS playback. Current-machine evidence on April 21, 2026 only confirmed dependency availability (`faster_whisper`, `sounddevice`, `edge_tts`, `kokoro`), not a spoken round-trip. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| PTT-02 | PTT with silence (no speech) | 1. Hold PTT. 2. Stay silent for full `silence_cutoff` window. 3. Release. | No spurious transcript; no TTS playback triggered. | WAIVED | Silence-cutoff behavior depends on real microphone capture. No live silence test was executed on April 21, 2026. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| PTT-03 | PTT timeout (max duration) | 1. Hold PTT and speak continuously past 45s default. | Recording cuts at `VoiceConfig.max_duration`; partial transcript returned; no hang. | WAIVED | The timeout path requires a >45s live recording session. That device exercise was not run in this closeout pass. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| PTT-04 | PTT while TTS is playing | 1. Ask a long question. 2. While Guppy is speaking the response, trigger PTT. | `listen_once()` waits until active speech synthesis completes before recording begins (VOICE.md step 1). | WAIVED | This interlock requires both live playback and live capture. No audio-session execution was performed on April 21, 2026. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| PTT-05 | PTT fallback: Whisper unavailable | 1. Simulate Whisper unavailable (e.g., uninstall or rename model). 2. Attempt PTT transcript. | Falls back to Google SpeechRecognition; transcript still returned; no crash. | WAIVED | This row requires mutating the STT environment or uninstalling dependencies. That disruption was intentionally not performed during closeout. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |

### Section B - Voice Assignment and Persistence

| ID | Description | Steps | Expected Result | Disposition | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| VA-01 | Assign voice in Settings | 1. Open Settings -> Persona/Voice section. 2. Select a non-default voice. 3. Save. | Guppy's next spoken response uses the newly assigned voice. | PREFILLED | `runtime/voice_bindings.json` on April 21, 2026 records a persisted binding for `main_guppy` using `EDGE TTS / en-GB-RyanNeural`, so a saved assignment exists on this machine. The Settings UI reassignment flow was not executed today. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| VA-02 | Voice persists across restart | 1. Assign a voice per VA-01. 2. Quit the launcher entirely. 3. Relaunch. 4. Trigger a spoken response. | Previously assigned voice is still active after restart; no revert to default. | PREFILLED | The persisted binding file and persona config are present in-repo on April 21, 2026, which is evidence that voice selection is stored across runs. No launcher restart plus audible playback check was executed in this pass. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| VA-03 | Voice persists across workspace switch | 1. Assign a voice in workspace A. 2. Switch to workspace B. 3. Switch back to workspace A. 4. Trigger a spoken response. | Voice assignment is still the one set in step 1; workspace switch did not reset it. | PREFILLED | `runtime/persona_config.json` shows a single global persona assignment (`main_guppy`), and `runtime/voice_bindings.json` contains no workspace-specific voice bindings. That config evidence is relevant, but the workspace-switch flow itself was not executed on April 21, 2026. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| VA-04 | Default voice on first run | 1. Fresh profile or cleared voice config. 2. Trigger a spoken response without explicit assignment. | Default voice is used with no error. | WAIVED | This machine is not a fresh profile, and the old `bm_lewis` expectation conflicts with current persisted/fallback defaults (`EDGE TTS / en-GB-RyanNeural` in `runtime/voice_bindings.json` and `src/guppy/experience_config/services.py`). No truthful first-run result can be claimed from local evidence alone. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |

### Section C - Voice Preview

| ID | Description | Steps | Expected Result | Disposition | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| VP-01 | Preview correct voice before assigning | 1. Open Settings -> Voice section. 2. Preview a listed voice without saving. | Preview plays the selected voice, not the currently active voice. | WAIVED | `edge_tts` is importable on this machine and the voice catalog includes Edge voices, but no preview playback was executed on April 21, 2026. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| VP-02 | Preview does not persist | 1. Preview a voice per VP-01. 2. Cancel or close without saving. 3. Trigger a spoken response. | Still uses the previously assigned voice, not the previewed one. | WAIVED | No preview-open/cancel flow was exercised in this closeout pass. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| VP-03 | Preview under SAPI engine | 1. Force SAPI provider (`GUPPY_TTS_PROVIDER=sapi`). 2. Preview a voice. | Preview plays via SAPI PowerShell path without error. | WAIVED | No explicit SAPI preview run was executed on April 21, 2026. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |

### Section D - Voice Interruption

| ID | Description | Steps | Expected Result | Disposition | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| VI-01 | Interrupt kokoro TTS mid-response | 1. Ask a long question so Guppy produces a multi-sentence TTS response. 2. While audio is playing, trigger PTT. | `stop_speaking()` halts kokoro playback via `sounddevice.stop()`; PTT recording begins cleanly. | WAIVED | No live kokoro playback interrupt was exercised on April 21, 2026. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| VI-02 | Interrupt SAPI TTS mid-response | 1. Force SAPI provider. 2. Ask a long question. 3. Trigger PTT while SAPI is speaking. | SAPI PowerShell subprocess is terminated; recording begins without leftover audio. | WAIVED | No explicit SAPI interruption run was executed in this closeout pass. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| VI-03 | Interrupt ElevenLabs TTS mid-response | 1. Configure ElevenLabs API key. 2. Force ElevenLabs provider. 3. Ask a long question and interrupt mid-playback. | Playback stops; PTT records cleanly; no dangling HTTP stream. | WAIVED | `ELEVENLABS_API_KEY` is absent on this machine, so an explicit ElevenLabs interruption scenario was not executable here on April 21, 2026. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| VI-04 | Double-interrupt (rapid PTT) | 1. Trigger PTT while Guppy is speaking. 2. Before recording completes, trigger PTT again. | No crash or deadlock; second PTT either queues or cancels gracefully. | WAIVED | The rapid double-interrupt race was not exercised on a live device in this pass. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |

### Section E - Engine Coverage

| ID | Description | Steps | Expected Result | Disposition | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| ENG-01 | kokoro engine (auto/default path) | 1. Ensure kokoro installed. 2. Leave `GUPPY_TTS_PROVIDER` at `auto`. 3. Trigger TTS. | kokoro is selected and speech output is clear. | WAIVED | `kokoro` is importable on this machine, but no auto-path playback was executed on April 21, 2026, and current persisted experience-config defaults are `EDGE TTS / en-GB-RyanNeural` rather than the older kokoro-default assumption in the matrix. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| ENG-02 | Windows SAPI engine | 1. Set `GUPPY_TTS_PROVIDER=sapi`. 2. Trigger TTS. | SAPI PowerShell path executes; audible speech; no crash. | WAIVED | No explicit `GUPPY_TTS_PROVIDER=sapi` execution was performed on April 21, 2026. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| ENG-03 | ElevenLabs engine (explicit) | 1. Set `GUPPY_TTS_PROVIDER=elevenlabs` and `ELEVENLABS_API_KEY`. 2. Trigger TTS. | ElevenLabs API is called; streamed speech plays back. | WAIVED | `ELEVENLABS_API_KEY` is absent on this machine, so explicit ElevenLabs playback could not be truthfully claimed. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| ENG-04 | Auto-fallback: kokoro missing | 1. Remove or break kokoro import. 2. Leave `GUPPY_TTS_PROVIDER=auto`. 3. Trigger TTS. | Fallback chain activates without silent failure. | WAIVED | This row requires intentionally breaking the kokoro path. That environment mutation was not performed during closeout. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| ENG-05 | STT Whisper primary path | 1. Ensure `faster-whisper` installed. 2. Trigger PTT and speak. | `faster-whisper` path is used for transcription and returns an accurate result. | PREFILLED | `faster_whisper` is importable on this machine, and `docs/VOICE.md` still documents it as the primary STT path. No spoken PTT transcription was executed on April 21, 2026, so this row is dependency evidence only. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |

### Section F - Device Coverage

| ID | Description | Steps | Expected Result | Disposition | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| DEV-01 | Default system audio input/output | 1. Leave OS audio device set to system default. 2. Run full PTT cycle. | Capture and playback use the default device and round-trip succeeds. | PREFILLED | The refreshed prefill helper snapshot on April 21, 2026 confirmed `sounddevice=True` with 57 detected audio devices, but default input/output remained unresolved (`index=None`) and no round-trip capture/playback was executed. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| DEV-02 | Non-default input device | 1. Select a non-default microphone in OS sound settings. 2. Run PTT cycle. | Capture uses the selected non-default device and transcript is accurate. | WAIVED | No non-default microphone selection or PTT run was executed in this closeout pass. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| DEV-03 | Non-default output device | 1. Set a non-default speaker/headphone output in OS sound settings. 2. Trigger TTS. | Audio plays on the selected non-default output device. | WAIVED | No non-default speaker/output routing check was executed on April 21, 2026. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| DEV-04 | Hot-plug device change during session | 1. Start a session. 2. Unplug and replug the primary microphone mid-session. 3. Attempt PTT. | Capture recovers or surfaces a clear error; no silent failure or crash. | WAIVED | No unplug/replug hot-plug exercise was performed in this closeout pass. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |

### Section G - First-Run Voice Setup

| ID | Description | Steps | Expected Result | Disposition | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| FRV-01 | New user completes voice setup without docs | 1. Start Guppy with a fresh or cleared voice config. 2. Using only the launcher UI, find where to enable and configure voice. 3. Assign a voice. 4. Run a PTT cycle. | User can locate voice settings, assign a voice, and complete a PTT round-trip without consulting external documentation. | WAIVED | This machine was not reset to a fresh profile on April 21, 2026, so no truthful first-run walkthrough could be claimed. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| FRV-02 | Voice engine status is visible on first launch | 1. Launch with a fresh profile. 2. Open Settings -> Voice (or equivalent). | Active TTS engine and STT model are clearly labeled. | WAIVED | No fresh-profile launcher walkthrough was executed in this closeout pass. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |
| FRV-03 | Voice disabled by default is safe | 1. Launch with voice features unconfigured or disabled. 2. Send a chat message. | No TTS playback without explicit user intent; no error prompts or silent failures. | WAIVED | `runtime/app_settings.json` already has `enable_voice=true` on this machine, so a disabled-by-default first-run state was not available for truthfully claiming this row. | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 |

---

## Sign-Off

| Scenario Group | Tester | Date | Status |
|---|---|---|---|
| PTT Core (PTT-01-05) | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 | WAIVED |
| Voice Assignment (VA-01-04) | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 | PREFILLED |
| Voice Preview (VP-01-03) | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 | WAIVED |
| Voice Interruption (VI-01-04) | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 | WAIVED |
| Engine Coverage (ENG-01-05) | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 | MIXED (`PREFILLED` + `WAIVED`) |
| Device Coverage (DEV-01-04) | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 | MIXED (`PREFILLED` + `WAIVED`) |
| First-Run Setup (FRV-01-03) | Automation prefill on DESKTOP-QARUGE1 | 2026-04-21 | WAIVED |
