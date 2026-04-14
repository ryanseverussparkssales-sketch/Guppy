# Voice and Audio System

Canonical implementation lives in `src/guppy/voice/voice.py`; `guppy_voice.py` is the compatibility shim.

## Runtime Components

- Capture: `sounddevice` input stream (`float32`, mono)
- WAV serialization: `soundfile`
- STT primary: `faster-whisper` (CPU, `compute_type="int8"`)
- STT fallback: `speech_recognition` Google recognizer
- TTS providers:
  - `kokoro` when import/init succeeds
  - ElevenLabs when explicitly selected and configured
  - Windows SAPI PowerShell fallback

## Push-to-Talk Flow

1. `listen_once()` waits until active speech synthesis completes.
2. It records microphone audio with timeout (`VoiceConfig.max_duration`, default 45s).
3. RMS VAD marks speech when RMS exceeds `speech_threshold`, then cuts off after `silence_cutoff` seconds of silence.
4. Captured audio is written to a temp WAV file.
5. `_transcribe_file()` uses Whisper when available, otherwise Google SpeechRecognition when available.
6. It returns `{"text": <str>, "error": <str>}`.

`hold_to_talk()` is a convenience wrapper around `listen_once(timeout=10)`.

## Wake Word Modes

Wake mode is started with `start_wake_word_detection()`.

- Default mode: transcription loop (`_wake_word_listener`)
  - repeated 2-second listens
  - checks configured phrases in recognized text
  - higher CPU than model-based wake detection
- Optional mode: openwakeword (`_wake_word_listener_oww`)
  - used only when `GUPPY_OWW_MODEL` is set and openwakeword imports successfully
  - falls back to transcription mode on init/stream failure

Configured wake phrases include `guppy`, `hey guppy`, `butler`, and common misrecognitions.

## TTS Selection Logic

Provider preference comes from `GUPPY_TTS_PROVIDER` (`auto` by default).

Resolution order in `speak()`:

1. `elevenlabs` if explicitly requested
2. `sapi` if explicitly requested
3. `kokoro` when available and provider is `auto`
4. ElevenLabs in `auto` mode when API key exists and `requests` is available
5. SAPI fallback

`quiet_mode` disables playback without changing routing state.

## Interruption Behavior

- `stop_speaking()` sets a stop event and stops audio output (`sounddevice.stop()` when available)
- if SAPI is active, the spawned PowerShell process is terminated
- `stop_tts()` delegates to `stop_speaking()`
- `stop_listening()` sets the listen stop event

This supports immediate user interruption while speech is active.

## Key Settings

`VoiceConfig` defaults:

- `stt_model`: `GUPPY_WHISPER_MODEL` or `large-v3`
- `samplerate`: `22050`
- `max_duration`: `45.0`
- `silence_cutoff`: `GUPPY_SILENCE_CUTOFF` or `0.7`
- `speech_threshold`: `GUPPY_SPEECH_THRESHOLD` or `0.01`

TTS-related env vars used by the implementation:

- `GUPPY_TTS_PROVIDER` (`auto`, `kokoro`, `sapi`, `elevenlabs`)
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_MODEL_ID`
- `ELEVENLABS_DEFAULT_VOICE_ID`
- `GUPPY_SAPI_VOICE`
- `GUPPY_OWW_MODEL`

## Diagnostics

Use `backend_status()` to inspect active backend decisions at runtime. It reports:

- selected TTS backend
- selected STT backend
- wake backend state
- quiet mode
- configured Whisper model
- fallback activation flags
- last backend errors (`tts_error`, `stt_error`)

## Known Constraints

- Without `faster-whisper` and `speech_recognition`, transcription is unavailable
- Without `kokoro` and ElevenLabs configuration, TTS falls back to SAPI
- openwakeword mode requires a configured model path; otherwise transcription wake mode is used
- wake callbacks depend on microphone capture quality and current backend availability
