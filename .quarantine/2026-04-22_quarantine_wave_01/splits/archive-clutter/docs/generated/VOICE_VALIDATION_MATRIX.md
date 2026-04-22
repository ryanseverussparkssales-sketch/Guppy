# Voice Validation Matrix

**Last updated: April 18, 2026**
**Purpose:** Real-device validation coverage for the Guppy voice system across engines, devices, and user flows.

---

## Validation Status

| Field | Value |
|---|---|
| **Overall Status** | PENDING |
| **Tester** | — |
| **Date Range** | — |
| **Blocking Issues** | *(none recorded — fill in after first run)* |

### Blocking Issues Placeholder

- [ ] *(No blocking issues recorded yet)*

---

## Risk Register (From PROJECT_BRIEF Current Gaps)

The following risks from `docs/PROJECT_BRIEF.md` Current Gaps apply directly to voice validation:

| Risk ID | Source | Risk Description |
|---|---|---|
| VR-1 | Current Gap 2 | Voice lifecycle still needs broader real-device validation across engines, especially preview behavior on more machines. |
| VR-2 | Current Gap 2 | Engine coverage is not uniform: kokoro path is the default `auto` path but SAPI fallback behavior under failure conditions has not been systematically validated. |
| VR-3 | Current Gap 5 | Workspace framing changes (P1 work) may have side-effects on voice assignment persistence if persona/workspace switching resets active voice selection. |
| VR-4 | VOICE.md | ElevenLabs path depends on `ELEVENLABS_API_KEY` at runtime; misconfigured environments could silently fall back to kokoro or SAPI without user awareness. |
| VR-5 | VOICE.md | SAPI fallback spawns a PowerShell subprocess; interruption via `stop_speaking()` terminates that process, but race conditions between spawn and stop have not been exercised on slow machines. |
| VR-6 | VOICE_SYSTEM_STATUS.md | 57 audio devices detected on the reference machine; non-default device selection and hot-plug device changes have not been validated. |

---

## Validation Matrix

For each scenario: complete **Pass/Fail**, **Notes**, **Tester**, and **Date** during real-device testing.

### Section A — Push-to-Talk (PTT) Core Flow

| ID | Description | Steps | Expected Result | Pass/Fail | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| PTT-01 | Basic PTT transcript → response | 1. Hold PTT button. 2. Speak a short phrase ("What time is it?"). 3. Release. | Transcript appears in chat; Guppy speaks a response via active TTS engine. | — | — | — | — |
| PTT-02 | PTT with silence (no speech) | 1. Hold PTT. 2. Stay silent for full `silence_cutoff` window. 3. Release. | No spurious transcript; no TTS playback triggered. | — | — | — | — |
| PTT-03 | PTT timeout (max duration) | 1. Hold PTT and speak continuously past 45s default. | Recording cuts at `VoiceConfig.max_duration`; partial transcript returned; no hang. | — | — | — | — |
| PTT-04 | PTT while TTS is playing | 1. Ask a long question. 2. While Guppy is speaking the response, trigger PTT. | `listen_once()` waits until active speech synthesis completes before recording begins (VOICE.md step 1). | — | — | — | — |
| PTT-05 | PTT fallback: Whisper unavailable | 1. Simulate Whisper unavailable (e.g., uninstall or rename model). 2. Attempt PTT transcript. | Falls back to Google SpeechRecognition; transcript still returned; no crash. | — | Risk: requires env manipulation. | — | — |

### Section B — Voice Assignment and Persistence

| ID | Description | Steps | Expected Result | Pass/Fail | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| VA-01 | Assign voice in Settings | 1. Open Settings → Persona/Voice section. 2. Select a non-default voice (e.g., switch from `bm_lewis` to a different kokoro voice). 3. Save. | Guppy's next spoken response uses the newly assigned voice. | — | — | — | — |
| VA-02 | Voice persists across restart | 1. Assign a voice per VA-01. 2. Quit the launcher entirely. 3. Relaunch. 4. Trigger a spoken response. | Previously assigned voice is still active after restart; no revert to default. | — | Persistence flows through `experience_config/services.py` per Handoff entry 9. | — | — |
| VA-03 | Voice persists across workspace switch | 1. Assign a voice in workspace A. 2. Switch to workspace B. 3. Switch back to workspace A. 4. Trigger a spoken response. | Voice assignment is still the one set in step 1; workspace switch did not reset it. | — | Related to Risk VR-3. | — | — |
| VA-04 | Default voice on first run | 1. Fresh profile or cleared voice config. 2. Trigger a spoken response without explicit assignment. | Default voice (`bm_lewis` per VOICE_SYSTEM_STATUS.md) is used; no error. | — | — | — | — |

### Section C — Voice Preview

| ID | Description | Steps | Expected Result | Pass/Fail | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| VP-01 | Preview correct voice before assigning | 1. Open Settings → Voice section. 2. Hover/click Preview on a listed voice without saving. | Preview plays the selected voice, not the currently active voice. | — | Related to Risk VR-1: preview behavior on more machines is a known gap. | — | — |
| VP-02 | Preview does not persist | 1. Preview a voice per VP-01. 2. Cancel or close without saving. 3. Trigger a spoken response. | Still uses the previously assigned voice, not the previewed one. | — | — | — | — |
| VP-03 | Preview under SAPI engine | 1. Force SAPI provider (`GUPPY_TTS_PROVIDER=sapi`). 2. Preview a voice. | Preview plays via SAPI PowerShell path without error. | — | Env var required. | — | — |

### Section D — Voice Interruption

| ID | Description | Steps | Expected Result | Pass/Fail | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| VI-01 | Interrupt kokoro TTS mid-response | 1. Ask a long question so Guppy produces a multi-sentence TTS response. 2. While audio is playing, trigger PTT. | `stop_speaking()` halts kokoro playback via `sounddevice.stop()`; PTT recording begins cleanly. | — | — | — | — |
| VI-02 | Interrupt SAPI TTS mid-response | 1. Force SAPI provider. 2. Ask a long question. 3. Trigger PTT while SAPI is speaking. | SAPI PowerShell subprocess is terminated; recording begins without leftover audio. | — | Related to Risk VR-5. | — | — |
| VI-03 | Interrupt ElevenLabs TTS mid-response | 1. Configure ElevenLabs API key. 2. Force ElevenLabs provider. 3. Ask a long question and interrupt mid-playback. | Playback stops; PTT records cleanly; no dangling HTTP stream. | — | Requires valid API key. | — | — |
| VI-04 | Double-interrupt (rapid PTT) | 1. Trigger PTT while Guppy is speaking. 2. Before recording completes, trigger PTT again. | No crash or deadlock; second PTT either queues or cancels gracefully. | — | Edge case for stop event race. | — | — |

### Section E — Engine Coverage

| ID | Description | Steps | Expected Result | Pass/Fail | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| ENG-01 | kokoro engine (auto/default path) | 1. Ensure kokoro installed. 2. Leave `GUPPY_TTS_PROVIDER` at `auto`. 3. Trigger TTS. | kokoro is selected (resolution order step 3 in VOICE.md); clear speech output. | — | Default engine per VOICE_SYSTEM_STATUS.md. | — | — |
| ENG-02 | Windows SAPI engine | 1. Set `GUPPY_TTS_PROVIDER=sapi`. 2. Trigger TTS. | SAPI PowerShell path executes; audible speech; no crash. | — | Fallback engine. | — | — |
| ENG-03 | ElevenLabs engine (explicit) | 1. Set `GUPPY_TTS_PROVIDER=elevenlabs` and `ELEVENLABS_API_KEY`. 2. Trigger TTS. | ElevenLabs API is called; streamed speech plays back. | — | Requires external API key. | — | — |
| ENG-04 | Auto-fallback: kokoro missing | 1. Remove or break kokoro import. 2. Leave `GUPPY_TTS_PROVIDER=auto`. 3. Trigger TTS. | Fallback chain activates: ElevenLabs (if key present) or SAPI; no silent failure. | — | Resolution order steps 4–5 in VOICE.md. | — | — |
| ENG-05 | STT Whisper primary path | 1. Ensure `faster-whisper` installed. 2. Trigger PTT and speak. | `faster-whisper` CPU path used for transcription; accurate result returned. | — | `stt_model` default is `large-v3`; may be slow on CPU. | — | — |

### Section F — Device Coverage

| ID | Description | Steps | Expected Result | Pass/Fail | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| DEV-01 | Default system audio input/output | 1. Leave OS audio device set to system default. 2. Run full PTT cycle. | Capture and playback use default device without explicit configuration; round-trip succeeds. | — | Reference machine has 57 devices; default selection path must not require user intervention. | — | — |
| DEV-02 | Non-default input device | 1. Select a non-default microphone in OS sound settings (e.g., NexiGo N930AF FHD Webcam Audio). 2. Run PTT cycle. | `sounddevice` captures from the OS-selected non-default device; transcript is accurate. | — | Related to Risk VR-6. | — | — |
| DEV-03 | Non-default output device | 1. Set a non-default speaker/headphone output in OS sound settings. 2. Trigger TTS. | Audio plays on the non-default output device; no routing to default device. | — | — | — | — |
| DEV-04 | Hot-plug device change during session | 1. Start a session. 2. Unplug and replug the primary microphone mid-session. 3. Attempt PTT. | Capture recovers or surfaces a clear error; no silent failure or crash. | — | Exploratory/edge case. | — | — |

### Section G — First-Run Voice Setup

| ID | Description | Steps | Expected Result | Pass/Fail | Notes | Tester | Date |
|---|---|---|---|---|---|---|---|
| FRV-01 | New user completes voice setup without docs | 1. Start Guppy with a fresh or cleared voice config. 2. Using only the launcher UI, find where to enable and configure voice. 3. Assign a voice. 4. Run a PTT cycle. | User can locate voice settings, assign a voice, and complete a PTT round-trip without consulting external documentation. | — | Acceptance bar: no external docs needed. Related to P1 first-run clarity goal. | — | — |
| FRV-02 | Voice engine status is visible on first launch | 1. Launch with a fresh profile. 2. Open Settings → Voice (or equivalent). | Active TTS engine and STT model are clearly labeled; user understands what is running. | — | — | — | — |
| FRV-03 | Voice disabled by default is safe | 1. Launch with voice features unconfigured or disabled. 2. Send a chat message. | No TTS playback without explicit user intent; no error prompts or silent failures. | — | — | — | — |

---

## Sign-Off

| Scenario Group | Tester | Date | Status |
|---|---|---|---|
| PTT Core (PTT-01–05) | — | — | PENDING |
| Voice Assignment (VA-01–04) | — | — | PENDING |
| Voice Preview (VP-01–03) | — | — | PENDING |
| Voice Interruption (VI-01–04) | — | — | PENDING |
| Engine Coverage (ENG-01–05) | — | — | PENDING |
| Device Coverage (DEV-01–04) | — | — | PENDING |
| First-Run Setup (FRV-01–03) | — | — | PENDING |
