# Phase 1: Audio Pipeline Hardening - Implementation Tasks
**Duration:** May 1–22, 2026 (3 weeks)  
**Owner:** Audio Infrastructure Team  
**Status:** Ready for execution

---

## Phase 1 Summary

Transform the monolithic `src/guppy/voice/voice.py` into a decomposed, production-grade audio architecture with real-time telemetry, intelligent fallback chains, and dedicated audio-only workspace support.

**Success Criteria:**
- STT error rate < 5%
- TTS latency p95 < 1500ms
- Fallback chain success rate > 98%
- User quality rating > 4.2/5
- Audio-only workspace functional and tested
- Comprehensive video demo of pure voice interaction

---

## Week 1: Architecture Refactor (May 1–5)

### Task 1.1: Voice Module Decomposition
**Description:** Extract monolithic `src/guppy/voice/voice.py` into layered architecture.

**Subtasks:**
1. Create directory structure under `src/guppy/voice/`:
   - `core.py` (base types, event enums, AudioEvent schema)
   - `stt/` (STT provider implementations)
   - `tts/` (TTS provider implementations)
   - `wake_word/` (wake-word detection service)
   - `ptt.py` (push-to-talk state machine)
   - `voice.py` (simplified facade)
   - `integration.py` (test integration helpers)

2. Define `core.py` types:
   ```python
   class AudioEvent:
       # Telemetry per utterance
       utterance_id: str
       workspace_id: str
       conversation_id: str
       stt_provider: str
       stt_latency_ms: float
       stt_confidence: float
       tts_provider: str
       tts_latency_ms: float
       error_message: Optional[str]
       fallback_chain_triggered: bool
       user_quality_rating: Optional[int]  # 1-5 stars
       timestamp: datetime
   
   class STTResult:
       text: str
       confidence: float
       provider: str
       latency_ms: float
       language: str
   
   class TTSResult:
       audio_bytes: bytes
       provider: str
       latency_ms: float
   ```

3. Define provider base classes:
   ```python
   class STTProvider(ABC):
       async def transcribe(audio: bytes) -> STTResult
       async def health_check() -> HealthStatus
   
   class TTSProvider(ABC):
       async def synthesize(text: str) -> TTSResult
       async def health_check() -> HealthStatus
   ```

**Acceptance Criteria:**
- [ ] Directory structure created with clear module boundaries
- [ ] `core.py` defines AudioEvent, STTResult, TTSResult, provider base classes
- [ ] Type hints complete and mypy passes
- [ ] Old `voice.py` still functional (refactoring in progress)

**Time Estimate:** 2 days  
**Owner:** Audio Lead

---

### Task 1.2: STT Provider Implementations
**Description:** Extract Google STT, Whisper fallback, and SAPI into separate provider classes.

**Subtasks:**
1. `src/guppy/voice/stt/google_stt.py`:
   - Implement `GoogleSTTProvider` with proper timeout handling (3s initial, fallback after 5s)
   - Add confidence scoring
   - Implement health check (can reach API?)
   - Add error logging and user notification

2. `src/guppy/voice/stt/whisper_stt.py`:
   - Implement `WhisperSTTProvider` (local, offline fallback)
   - Use `openai-whisper` or equivalent
   - Add confidence scoring
   - Health check for model availability

3. `src/guppy/voice/stt/sapi_stt.py`:
   - Implement `SAPISTTProvider` (Windows built-in, last-resort fallback)
   - Minimal latency
   - Health check for Windows speech engine

4. `src/guppy/voice/stt/__init__.py`:
   - Export STT provider registry
   - Implement provider factory

**Acceptance Criteria:**
- [ ] Each provider passes unit tests
- [ ] Google STT has timeout guard at 5s
- [ ] Whisper fallback uses local model
- [ ] SAPI has <500ms latency baseline
- [ ] All providers implement health_check()
- [ ] Error messages user-friendly

**Time Estimate:** 2 days  
**Owner:** Audio Lead

---

### Task 1.3: TTS Provider Implementations
**Description:** Extract Kokoro TTS, Windows SAPI, and ElevenLabs into separate providers.

**Subtasks:**
1. `src/guppy/voice/tts/kokoro_tts.py`:
   - Implement `KokoroTTSProvider`
   - Local neural TTS (primary)
   - Latency baseline target: <800ms
   - Health check for model availability

2. `src/guppy/voice/tts/sapi_tts.py`:
   - Implement `SAPITTSProvider` (Windows fallback)
   - Fast, <300ms latency
   - Less natural but reliable

3. `src/guppy/voice/tts/elevenlabs_tts.py`:
   - Implement `ElevenLabsTTSProvider` (cloud fallback)
   - High quality, ~1200ms latency
   - Requires API key (optional)

4. `src/guppy/voice/tts/__init__.py`:
   - Export TTS provider registry
   - Implement provider factory

**Acceptance Criteria:**
- [ ] Each provider passes unit tests
- [ ] Kokoro <800ms p95 latency
- [ ] SAPI <300ms latency
- [ ] ElevenLabs gracefully handles no API key
- [ ] All providers implement health_check()
- [ ] TTS output quality tested

**Time Estimate:** 2 days  
**Owner:** Audio Lead

---

### Task 1.4: Wake-Word Detection Service
**Description:** Extract wake-word detection into standalone service.

**Subtasks:**
1. `src/guppy/voice/wake_word/detector.py`:
   - Implement `WakeWordDetector` class
   - Support "Hey Guppy" and fallback patterns
   - Non-blocking detection on audio stream
   - Configurable sensitivity

2. Add telemetry:
   - Track wake-word detection latency
   - Track false-positive rate
   - User enable/disable preference

**Acceptance Criteria:**
- [ ] Wake-word detection runs in background thread
- [ ] False-positive rate < 2%
- [ ] User can disable via settings
- [ ] Telemetry logged to AudioEvent

**Time Estimate:** 1 day  
**Owner:** Audio Lead

---

## Week 2: Audio-Only Workspace & Fallback Chains (May 6–12)

### Task 2.1: Audio-Only Workspace Type
**Description:** Implement dedicated workspace mode for voice-only interaction.

**Subtasks:**
1. Define `WorkspaceMode` enum:
   ```python
   class WorkspaceMode(Enum):
       TEXT_FIRST = "text_first"          # Default: text + voice
       AUDIO_ONLY = "audio_only"          # Voice-only, no text input
       VOICE_PRIORITY = "voice_priority"  # Voice encouraged, text available
   ```

2. Create `AudioOnlyWorkspace` class:
   ```python
   class AudioOnlyWorkspace:
       mode: WorkspaceMode = WorkspaceMode.AUDIO_ONLY
       accept_text_input: bool = False     # Force voice input only
       force_tts_output: bool = True       # Always speak responses
       auto_play: bool = True              # Auto-play TTS immediately
       ui_preset: str = "audio_conversation"
       strict_mode: bool = True            # Error recovery if audio fails
       audio_quality_feedback: bool = True # Ask for 1-5 star rating
   ```

3. Update workspace creation UI:
   - Add "Create Audio-Only Workspace" button
   - Pre-populate settings
   - Show UI preset: large mic button, waveform visualizer, no text input

4. Modify chat composer:
   - Disable text input field in audio-only mode
   - Force focus to mic button
   - Show real-time transcript overlay (read-only)
   - Show quality feedback UI (1-5 stars)

**Acceptance Criteria:**
- [ ] New workspace type can be created
- [ ] Text input disabled in audio-only mode
- [ ] TTS auto-plays on audio-only workspace
- [ ] UI shows large mic button + waveform
- [ ] Quality feedback UI functional
- [ ] Settings persist across sessions

**Time Estimate:** 2 days  
**Owner:** UI/Audio Team

---

### Task 2.2: Fallback Chain Orchestration
**Description:** Implement intelligent fallback chains with parallel execution.

**Subtasks:**
1. `src/guppy/voice/fallback.py`:
   ```python
   class FallbackChain:
       primary: STTProvider
       fallbacks: List[STTProvider]
       timeout_per_provider: int = 2000  # ms
       parallel_execution: bool = True
       
       async def transcribe(audio: bytes) -> STTResult:
           # Execute in parallel, return first success
           # Cancel losers on success
           # Log decision/latency/cost
   ```

2. Implement parallel execution with `asyncio.gather()`:
   - Start all providers in parallel
   - Set timeout per provider (2s)
   - Return first success
   - Cancel remaining tasks on success
   - Log which provider succeeded and why

3. Define default fallback chains:
   - **Text-first:** Google STT → Whisper → SAPI
   - **Offline-first:** Whisper → SAPI (no Google)
   - **Fastest:** SAPI → Whisper → Google (SAPI first for speed)

4. Add cost/latency tracking:
   - Track latency per provider per utterance
   - Track cost (cloud providers only)
   - Aggregate stats to RoutingEvent

**Acceptance Criteria:**
- [ ] Fallback chain executes in parallel
- [ ] Timeout per provider enforced (2s)
- [ ] First-success-wins strategy works
- [ ] Losers cancelled on success
- [ ] Decision/latency/cost logged
- [ ] Fallback success rate > 98% in tests

**Time Estimate:** 2 days  
**Owner:** Audio Lead

---

### Task 2.3: Error Recovery & User Notification
**Description:** Never silently fail audio. Implement intelligent recovery.

**Subtasks:**
1. Create `AudioErrorRecovery` class:
   - Detect failures (timeout, API error, confidence too low)
   - Execute fallback chain immediately
   - Show user-friendly recovery message
   - Never block conversation

2. User notification patterns:
   - "Transcription timed out, trying offline model..."
   - "Audio quality low (confidence: 42%), retrying with different engine..."
   - "Google STT unavailable, using local model instead"
   - "If this persists, try speaking more clearly"

3. Implement retry logic:
   - Automatic retry on confidence < 50%
   - Max 3 retries before asking user to try again
   - Log retry attempts to AudioEvent

4. Add recovery dashboard:
   - Show recent errors per conversation
   - Show which provider succeeded for each utterance
   - Show fallback chain triggers

**Acceptance Criteria:**
- [ ] No silent failures in audio
- [ ] User notified immediately of issues
- [ ] Intelligent fallback executed
- [ ] Retry logic capped at 3 attempts
- [ ] Recovery messages tested with real users
- [ ] Telemetry tracks every failure/recovery

**Time Estimate:** 2 days  
**Owner:** Audio/UI Team

---

## Week 3: Testing, Telemetry & Demo (May 13–22)

### Task 3.1: Audio Telemetry Dashboard
**Description:** Implement real-time monitoring of audio system health.

**Subtasks:**
1. Create new endpoint `GET /api/audio/telemetry`:
   ```python
   {
       "stt_metrics": {
           "latency_p50_ms": 523,
           "latency_p95_ms": 1200,
           "latency_p99_ms": 2100,
           "error_rate": 0.032,  # 3.2%
           "providers": {
               "google": {"success": 850, "timeout": 42, "error": 8},
               "whisper": {"success": 120, "fallback_triggers": 50},
               "sapi": {"success": 45, "latency_ms": 200}
           }
       },
       "tts_metrics": {
           "latency_p50_ms": 623,
           "latency_p95_ms": 1100,
           "latency_p99_ms": 1800,
           "error_rate": 0.008,
           "providers": {
               "kokoro": {"success": 920, "latency_ms": 750},
               "sapi": {"success": 95, "latency_ms": 280},
               "elevenlabs": {"success": 5}
           }
       },
       "fallback_stats": {
           "fallback_chain_triggers": 92,
           "fallback_success_rate": 0.989,
           "average_fallback_attempts_per_failure": 1.3
       },
       "quality_feedback": {
           "average_rating": 4.24,  # 1-5 stars
           "ratings_by_provider": {
               "google": 4.5,
               "whisper": 4.1,
               "kokoro_tts": 4.6,
               "sapi_tts": 3.2
           }
       }
   }
   ```

2. Create web UI dashboard:
   - Real-time latency graphs (p50, p95, p99)
   - Error rate trends
   - Provider success rate comparison
   - Quality rating distribution
   - Fallback chain trigger heatmap

3. Add telemetry persistence:
   - Store `AudioEvent` to `audio_telemetry.jsonl`
   - Keep rolling 7-day window
   - Compute aggregations on query

**Acceptance Criteria:**
- [ ] Telemetry endpoint returns accurate metrics
- [ ] Dashboard shows real-time data
- [ ] Historical data retained for 7 days
- [ ] Quality feedback integrated into metrics
- [ ] Performance: queries < 200ms

**Time Estimate:** 2 days  
**Owner:** Backend/Dashboard Team

---

### Task 3.2: Comprehensive Test Suite
**Description:** Stress test audio pipeline under various conditions.

**Subtasks:**
1. **Stress tests:**
   ```python
   # tests/integration/test_audio_stress.py
   - Test 100 consecutive utterances
   - Test 2-minute continuous monologue
   - Test rapid interrupts (user talking while TTS playing)
   - Test silence detection (user goes silent, system timeout)
   - Test background noise (50dB SPL, typing, AC)
   - Test network failure (Google STT unavailable)
   ```

2. **Audio quality tests:**
   ```python
   # tests/integration/test_audio_quality.py
   - TTS naturalness (MOS score > 4.0)
   - SAPI quality baseline
   - Latency baseline: STT < 1500ms p95, TTS < 1000ms p95
   - Confidence scoring accuracy
   - Wake-word detection accuracy (false-positive < 2%)
   ```

3. **Integration tests:**
   ```python
   # tests/integration/test_audio_only_workspace.py
   - Full audio-only loop: hear prompt → speak response → hear TTS
   - Fallback chain execution
   - Quality feedback persistence
   - Error recovery workflows
   - Audio-only workspace creation/deletion
   ```

4. **Test fixtures:**
   - Pre-recorded audio samples (various speakers, accents, noise levels)
   - Mock STT/TTS providers for deterministic testing
   - Latency injection fixtures (simulate slow providers)

**Acceptance Criteria:**
- [ ] 100 consecutive utterances complete without failure
- [ ] 2-minute monologue handled correctly
- [ ] Rapid interrupts don't break state machine
- [ ] Silence detection timeout < 3s
- [ ] Background noise doesn't degrade accuracy > 10%
- [ ] Network failure triggers fallback successfully
- [ ] All tests pass, coverage > 85%

**Time Estimate:** 3 days  
**Owner:** QA/Test Team

---

### Task 3.3: Video Demo Production
**Description:** Record and edit comprehensive demo of pure voice interaction.

**Subtasks:**
1. Script the demo:
   - Cold start → wake-word → conversation
   - Model switching via voice
   - Tool execution via voice
   - Interruption & recovery
   - Error scenario & fallback
   - Quality feedback rating

2. Record multiple takes:
   - Clear audio quality
   - Show both speaker and screen
   - Capture waveform visualization
   - Show telemetry updates live

3. Edit and post-produce:
   - Add captions
   - Add on-screen annotations
   - Show latency metrics (overlay)
   - Show fallback chain triggers
   - Highlight recovery moments
   - ~5-7 minute final length

4. Publish:
   - Upload to Guppy docs
   - Include transcript
   - Link from PROJECT_BRIEF.md
   - Share on internal comms channel

**Acceptance Criteria:**
- [ ] Demo video created (5-7 min)
- [ ] Clear audio quality throughout
- [ ] Captions and annotations complete
- [ ] Covers all major workflows
- [ ] Shows error recovery
- [ ] Published to docs with transcript

**Time Estimate:** 2 days  
**Owner:** Demo/Communications Team

---

### Task 3.4: Documentation & Integration
**Description:** Document audio architecture and integrate into main docs.

**Subtasks:**
1. Create `docs/AUDIO_PIPELINE.md`:
   - Architecture overview
   - Provider implementations
   - Fallback chain logic
   - Telemetry schema
   - Configuration options
   - Troubleshooting guide

2. Create `docs/AUDIO_ONLY_WORKSPACE.md`:
   - How to create audio-only workspace
   - User guide
   - Quality feedback system
   - Known limitations
   - FAQ

3. Update `CLAUDE.md`:
   - Add Audio Pipeline section
   - Update architecture diagram
   - Document new AudioEvent telemetry
   - List known issues

4. Update `README.md`:
   - Mention audio-only workspace
   - Link to audio docs
   - Quick start for voice users

5. Create migration guide for existing workspaces

**Acceptance Criteria:**
- [ ] All audio docs complete and cross-linked
- [ ] CLAUDE.md updated with architecture
- [ ] README mentions audio features
- [ ] Migration guide clear
- [ ] Zero broken links
- [ ] Docs reviewed for accuracy

**Time Estimate:** 1 day  
**Owner:** Documentation Team

---

### Task 3.5: Phase 1 Integration & Validation
**Description:** Integrate all components and validate against success criteria.

**Subtasks:**
1. Integration checklist:
   - [ ] All STT providers load at startup
   - [ ] All TTS providers load at startup
   - [ ] Fallback chain orchestration working
   - [ ] AudioEvent telemetry flowing to storage
   - [ ] Audio-only workspace mode functional
   - [ ] Quality feedback UI working
   - [ ] Telemetry dashboard responsive
   - [ ] Tests passing (integration + smoke)
   - [ ] No regressions in existing audio code

2. Success criteria validation:
   - [ ] STT error rate < 5% (measure over 100+ utterances)
   - [ ] TTS latency p95 < 1500ms (measure over 50+ utterances)
   - [ ] Fallback chain success rate > 98% (measure over network failures)
   - [ ] User quality rating > 4.2/5 (collect from testers)
   - [ ] Audio-only workspace fully functional
   - [ ] Video demo complete and reviewed

3. Final walkthrough:
   - [ ] Code review of all new modules
   - [ ] Architecture guardrails pass (dev-check)
   - [ ] Release-check passes
   - [ ] Handoff notes prepared for Phase 2

**Acceptance Criteria:**
- [ ] All success criteria met
- [ ] Integration complete
- [ ] Phase 1 ready for handoff to Phase 2
- [ ] Video demo approved

**Time Estimate:** 2 days  
**Owner:** Audio Lead + Tech Lead

---

## Timeline Summary

| Week | Dates | Focus | Deliverable |
|------|-------|-------|-------------|
| 1 | May 1–5 | Architecture decomposition | Refactored voice module with layered architecture |
| 2 | May 6–12 | Workspace + Fallback chains | Audio-only workspace type + intelligent fallbacks + error recovery |
| 3 | May 13–22 | Testing + Documentation + Demo | Video demo + telemetry dashboard + comprehensive test suite |

---

## Dependencies & Blockers

- **Ollama must be running** during all testing (needed for Whisper fallback model)
- **Google API key** required for full STT testing (can mock in some tests)
- **Network availability** required for ElevenLabs/cloud provider testing
- **Audio hardware** required for real PTT/STT/TTS testing (microphone + speakers)

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| STT Error Rate | < 5% | Failed transcriptions / total utterances over 100+ sample |
| TTS Latency p95 | < 1500ms | Measure generation latency for 50+ utterances |
| Fallback Success Rate | > 98% | Successful recovery / total fallback triggers |
| User Quality Rating | > 4.2/5 | Average rating from quality feedback UI (1-5 stars) |
| Audio-Only Workspace | Fully functional | All workflows testable, no known bugs |
| Test Coverage | > 85% | Coverage report from pytest-cov |
| Demo Approval | Signed off | Tech lead + product approval |

---

## Handoff Notes for Phase 2

- Audio-only workspace is now functional but can be further optimized
- Fallback chain metrics will inform Phase 2 backend optimization decisions
- Telemetry dashboard can be extended with cost tracking in Phase 2
- Consider adding more regional STT providers if Google latency remains an issue
- Wake-word detection ready for expanded model support in future phases

**Phase 1 Completion Target:** May 22, 2026  
**Phase 2 Kickoff:** May 23, 2026
