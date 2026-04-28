# Tasks

## Active

## Waiting On

## Someday

- PHASE_2: Backend Registry & Optimization (May 23-June 5)
- PHASE_3: Repo Cleanup & Freeze Readiness (June 6-12)
- Wake-word real model: wire pvporcupine + access key for production wake word; current EnergyThreshold is dev/test only
- TTS streaming: replace whole-then-yield with chunked streaming (Kokoro local supports it via KPipeline; ElevenLabs has streaming endpoint)
- Microphone capture backend: wire sounddevice/pyaudio into voice.py _capture_microphone_audio + _stream_microphone_audio (delegated to platform wrapper currently)

## Done

- [x] ~~**PHASE_1_Task_1.1: Voice Module Decomposition**~~ (2026-04-28)
- [x] ~~**PHASE_1_Task_1.2: STT Provider Implementations**~~ (2026-04-28)
  - Google + Whisper + SAPI providers, FallbackChainOrchestrator, facade transcribe() with full STT_*/utterance_id telemetry, 26 tests passing.

- [x] ~~**PHASE_1_Task_1.3: TTS Provider Implementations**~~ (2026-04-28)
  - KokoroTTSProvider (HTTP API + local KPipeline modes, async)
  - SAPITTSProvider (pyttsx3 preferred, PowerShell fallback, async)
  - ElevenLabsTTSProvider (streaming REST, model=eleven_turbo_v2_5)
  - TTSCache (LRU, content+voice+provider hash key, 256 entries default, hit-rate stats)
  - TTSFallbackOrchestrator (ElevenLabs → Kokoro → SAPI, per-provider 10s timeout, fallback_chain in metadata)
  - facade synthesize()/speak() with TTS_START/SUCCESS/ERROR/FALLBACK events, utterance_id linking, automatic cache check before orchestrator
  - 24 tests passing in tests/unit/test_tts_providers.py (cache LRU/eviction/voice-keying, all 3 providers, orchestrator winner/fallback/all-fail, facade events/cache-hit/exception)
  - **Limitations:** stream_synthesize yields one chunk (whole-then-yield) — true streaming is on Phase 1.5 stretch list

- [x] ~~**PHASE_1_Task_1.4: Wake-Word Detection Skeleton**~~ (2026-04-28)
  - WakeWordDetector with debounce + threshold filtering + WakeWordConfig
  - WakeWordEvent dataclass with confidence/keyword/provider/timestamp_ms/audio_excerpt
  - EnergyThresholdWakeWordProvider (RMS-based, dev/test stub) — always-available, deterministic on synthetic audio
  - PorcupineWakeWordProvider skeleton (requires pvporcupine + PORCUPINE_ACCESS_KEY env var; health_check fails gracefully without)
  - 17 tests passing in tests/unit/test_wake_word.py (energy provider tone/silence/quiet, Porcupine skeleton no-key path, detector debounce/threshold/disabled/exception paths)
  - **Limitations:** Porcupine needs access key + .ppn keyword files for production. EnergyThreshold is voice-activity gate, NOT a true wake-word.

- [x] ~~**P6 Hardening: 6 corrupted source files reconstructed**~~ (2026-04-28)
  - routes_backends.py, routes_chat_history.py, routes_realtime.py, routes_settings.py, _server_fragment_models.py, inference/local_client.py — all had truncated in-progress edits, all reconstructed and now compile clean.
  - Preserved intent: Hermes 4/3/Rocinante backend additions, db_utils migration, image_base64 multimodal field, model parameter persistence, _alive_names helper, etc.
