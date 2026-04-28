# Guppy Platform Hardening Plan
## Audio-First Foundation → Backend Optimization → Repo Cleanup

**Date:** 2026-04-28  
**Timeline:** May 1 – June 12 (P6 final delivery)  
**Owner:** Ryan Sparks + Claude Agent  
**Priority Order:** Audio → Backends → Repo  

---

## Phase 1: Audio Pipeline Hardening (May 1–22, 3 weeks)

### Goal
**Flawless conversational audio.** If a user wants pure voice I/O, it works perfectly. No dropouts, no transcription fails, no TTS glitches. Every utterance in, clean response out, spoken back—reliable, every time.

### 1.1 Refactor TTS/STT Architecture

#### Current State (Problems)
```
src/guppy/voice/voice.py              → Monolithic, ~400 lines
├── Google STT (async, timeout issues)
├── Kokoro TTS (fallback SAPI, slow)
├── Wake-word detection (untested)
└── Push-to-talk (PTT) integration (fragile)
```

**Issues identified:**
- Google STT timeout handling inadequate
- Kokoro fallback chain is blocking (not async)
- Wake-word path is incomplete
- PTT state machine has race conditions
- Error recovery is silent (user doesn't know what failed)

#### Solution: Decompose into Layers

```
src/guppy/voice/                          (reorganized)
├── __init__.py
├── core.py                               (new: base types, event enums)
├── stt/                                  (new)
│   ├── __init__.py
│   ├── base.py                          (STTProvider abstract base)
│   ├── google_provider.py                (Google STT with timeout handling)
│   ├── fallback_provider.py              (whisper, assemblyai, local models)
│   └── detector.py                       (voice activity detection, silence detection)
├── tts/                                  (new)
│   ├── __init__.py
│   ├── base.py                          (TTSProvider abstract base)
│   ├── kokoro_provider.py                (async Kokoro pipeline)
│   ├── sapi_provider.py                  (Windows SAPI fallback, async wrapper)
│   ├── elevenlabs_provider.py            (if API key available)
│   └── cache.py                          (TTS output caching by text hash)
├── wake_word/                            (new)
│   ├── __init__.py
│   ├── detector.py                       (wake-word recognition, threshold tuning)
│   └── models/                           (wake-word model files, configurable)
├── ptt.py                                (push-to-talk state machine, rewritten)
├── voice.py                              (simplified facade, orchestrates the layers)
└── integration.py                        (test integration between all layers)
```

#### 1.2 Dedicated Audio-Only Workspace

New workspace type: `WorkspaceMode::AUDIO_ONLY`

**Workspace properties:**
```python
class AudioOnlyWorkspace(Workspace):
    mode: WorkspaceMode = WorkspaceMode.AUDIO_ONLY
    
    # Only voice input allowed
    accept_text_input: bool = False
    
    # Forced voice output
    force_tts_output: bool = True
    
    # Auto-play responses (no "Play" button)
    auto_play: bool = True
    
    # Conversation UI: audio waveform + transcript overlay
    ui_preset: str = "audio_conversation"
    
    # Strict audio pipeline (no fallback to text)
    strict_mode: bool = True
    
    # Feedback system: rate audio quality of each response
    audio_quality_feedback: bool = True
```

**UI/UX for Audio-Only Workspace:**
- **Input zone:** Large mic button, waveform visualizer, "Listening..." → "Processing..." → "Speaking..."
- **Transcript display:** Interim transcription in real-time (user sees what's being heard)
- **Output:** Waveform of TTS response + playback scrubber
- **Quality feedback:** Star rating (1–5) for audio clarity of each response
- **No text input field** (mobile-first UX, voice only)
- **Workspace switcher:** Easy toggle to audio-only from main chat

#### 1.3 TTS/STT Health Monitoring

**New telemetry per utterance:**

```python
class AudioEvent(TypedDict):
    timestamp: float
    utterance_id: str
    
    # STT metrics
    stt_provider: str
    stt_latency_ms: float
    stt_confidence: float  # 0.0–1.0
    stt_error: Optional[str]
    input_audio_duration_ms: float
    
    # TTS metrics
    tts_provider: str
    tts_latency_ms: float
    tts_output_duration_ms: float
    tts_error: Optional[str]
    
    # Quality
    user_rating: Optional[int]  # 1–5 stars (collected from audio-only workspace)
    
    # Context
    workspace_id: str
    conversation_id: str
```

**Dashboard view:** Real-time audio metrics
- STT latency (p50, p95, p99)
- TTS latency by provider
- Error rate by provider
- User ratings (quality feedback)
- Fallback chain triggers (when Google STT fails, how often does fallback work?)

#### 1.4 Error Recovery & User Feedback

**Rule: Never silently fail audio.**

```python
# Example: Google STT times out
if stt_response.error == "timeout":
    # Notify user immediately
    await notify_user(
        type="audio_failure",
        message="Transcription took too long. Trying fallback...",
        action="retry" | "use_text_input"
    )
    
    # Fallback chain (parallel, fastest-first)
    fallback_providers = [
        WhisperProvider(),      # Local model, ~2s
        AssemblyAIProvider(),   # Cloud, ~3s (if key available)
        SAPIProvider()          # Windows SAPI speech-to-text
    ]
    
    result = await race(fallback_providers)
    if result.success:
        await notify_user(type="audio_recovery", message="Got it!")
    else:
        await notify_user(
            type="audio_critical_fail",
            message="Audio transcription failed. Try text input?",
            action="open_text_input"
        )
```

#### 1.5 Testing Strategy (Week 3)

**1.5a Stress Tests**
```
✓ 100 consecutive utterances without pause (detect audio queue overflow)
✓ 2-minute monologue (test streaming, buffering)
✓ Rapid fire (user interrupts after 200ms) (test cancellation)
✓ Silence detection (user goes quiet mid-word)
✓ Background noise (simulate coffee shop) (test noise floor)
✓ Network failure (simulate Google STT timeout) (test fallback chain)
```

**1.5b Audio Quality Tests**
```
✓ Kokoro TTS: Validate speech naturalness (subjective but criteria: clear, not robotic, appropriate pace)
✓ SAPI fallback: Validate Windows voice quality
✓ Latency baseline: User speaks → response spoken back in <3 seconds (p95)
✓ Confidence scoring: STT confidence correlates with accuracy (< 0.7 confidence should be marked)
```

**1.5c Integration Tests**
```
✓ Audio-only workspace: Mic input → STT → inference → TTS → speaker (full loop, 10 iterations)
✓ Fallback chain: Google timeout → Whisper succeeds (4 test cases per fallback pair)
✓ Quality feedback: User rates audio; rating persists to AudioEvent telemetry
```

**Output:** Video demo (user voice in → Guppy response spoken back, no text at all)

---

## Phase 2: Backend Organization & Optimization (May 23–June 5, 2 weeks)

### Goal
**Unified backend interface.** All local/cloud backends speak the same language. Single routing decision. Clear fallback chains. Predictable latency.

### 2.1 Backend Registry Refactor

**Current state:**
```
src/guppy/local_llm/local_client.py       (llama.cpp discovery)
src/guppy/api/routes_backends.py          (backend management routes)
src/guppy/inference/router.py             (routing logic, scattered)
```

**Target state:**
```
src/guppy/backends/                       (new: unified backend abstraction)
├── __init__.py
├── registry.py                           (BackendRegistry: single source of truth)
├── types.py                              (Backend, BackendCapability, BackendStatus enums)
├── base.py                               (Backend abstract class)
├── local/                                (new)
│   ├── ollama.py                        (Ollama provider)
│   ├── llamacpp.py                      (llama.cpp provider, 8 backends)
│   ├── lm_studio.py                     (LM Studio provider)
│   └── local_discovery.py                (Port scanning, auto-discovery)
├── cloud/                                (new)
│   ├── anthropic.py                     (Claude provider)
│   ├── openai.py                        (GPT provider)
│   ├── google.py                        (Gemini provider)
│   ├── mistral.py                       (Mistral provider)
│   └── cohere.py                        (Cohere provider)
├── routing/                              (new)
│   ├── router.py                        (unified routing logic)
│   ├── fallback.py                      (FallbackChain orchestrator)
│   ├── latency_tracker.py                (per-backend latency SLOs)
│   └── cost_tracker.py                   (cloud usage tracking)
└── health.py                             (HealthCheck orchestrator for all backends)
```

### 2.2 Backend Abstraction Layer

```python
class Backend(ABC):
    """Base class for all backends (local + cloud)."""
    
    @property
    def id(self) -> str:
        """Unique backend ID (e.g., 'ollama', 'llamacpp-pepe', 'claude-opus')."""
        
    @property
    def type(self) -> BackendType:
        """LOCAL | CLOUD."""
        
    @property
    def capabilities(self) -> Set[BackendCapability]:
        """STREAM, TOOL_CALL, VISION, FUNCTION_CALLING, etc."""
        
    @property
    def latency_slo_ms(self) -> int:
        """Expected p95 latency in ms (local: ~500ms, cloud: ~2000ms)."""
    
    @property
    def cost_per_1k_tokens(self) -> Optional[float]:
        """Cost per 1K tokens (None for local)."""
    
    @property
    def vram_required_gb(self) -> Optional[float]:
        """VRAM needed (None for cloud)."""
    
    async def health_check(self) -> HealthStatus:
        """Is this backend ready? READY | DEGRADED | DOWN."""
        
    async def infer(self, request: InferenceRequest) -> AsyncIterator[InferenceChunk]:
        """Stream inference tokens."""
        
    async def infer_batch(self, requests: List[InferenceRequest]) -> List[InferenceResult]:
        """Parallel inference (where supported)."""
```

### 2.3 Unified Routing Decision

```python
class RoutingDecision:
    """What to run, where, and why."""
    
    primary_backend_id: str           # e.g., 'llamacpp-pepe'
    fallback_chain: List[str]         # [fallback-1, fallback-2, ...]
    reason: str                       # "user_selected" | "cost_optimized" | "latency_slo" | "feature_required"
    estimated_cost: Optional[float]
    estimated_latency_ms: int
```

**Routing criteria (in order):**
1. **User explicit selection** → use that backend (no fallback unless it fails)
2. **Cost budget exceeded for session** → switch to free/cheaper backend
3. **Latency SLO breach detected** → try faster backend
4. **Feature required** (vision, tool-call) → filter to capable backends only
5. **Default strategy** → latency-optimized (local > cloud)

### 2.4 Fallback Chain Intelligence

```python
class FallbackChain:
    """Orchestrate fallback when primary backend fails."""
    
    async def execute(
        self,
        request: InferenceRequest,
        chain: List[BackendID],
        on_failure_callback: Callable,
    ) -> InferenceResult:
        """
        Try backends in order until one succeeds.
        
        1. Try primary, measure latency
        2. If timeout at 2s, trigger fallback in parallel
        3. First successful response wins
        4. Losers are cancelled
        5. Log decision + latency + cost to RoutingEvent
        """
```

### 2.5 Backend Health Dashboard

**New endpoint:** `GET /api/backends/health`

```json
{
  "timestamp": "2026-05-23T14:30:00Z",
  "backends": {
    "ollama": {
      "status": "ready",
      "latency_p95_ms": 340,
      "models_loaded": ["guppy-fast", "guppy-code"],
      "last_check": "2026-05-23T14:29:55Z"
    },
    "llamacpp-pepe": {
      "status": "ready",
      "latency_p95_ms": 420,
      "vram_used_gb": 8.2,
      "last_check": "2026-05-23T14:29:50Z"
    },
    "claude-opus": {
      "status": "ready",
      "latency_p95_ms": 1800,
      "cost_this_month": "$2.34",
      "tokens_used_this_month": 18000,
      "last_check": "2026-05-23T14:29:00Z"
    },
    "google-gemini": {
      "status": "degraded",
      "latency_p95_ms": 3200,
      "error_rate": 0.15,
      "last_error": "rate_limit",
      "last_check": "2026-05-23T14:28:00Z"
    }
  },
  "routing_stats": {
    "primary_backend_success_rate": 0.98,
    "fallback_triggered_count": 3,
    "average_inference_latency_ms": 680
  }
}
```

### 2.6 Backend Optimization Matrix

| Backend | Role | Optimization | SLO |
|---------|------|-------------|-----|
| **ollama (guppy-fast)** | Default fast | Pin model in memory, reduce batch size | <300ms |
| **llamacpp-pepe** | Fast local chat | Prefetch context, reduce max_tokens | <500ms |
| **llamacpp-qwen3** | Reasoning (local) | Solo mode only (19GB), long context | <2000ms |
| **llamacpp-hermes4** | Tools (local, recommended) | Async tool-call accumulation | <800ms |
| **claude-opus** | High-quality fallback | Batch requests, cost tracking | <2000ms |
| **mistral-free** | Cost-optimized cloud | Try before Claude, stop if acceptable | <2500ms |

---

## Phase 3: Repo Cleanup & Organization (June 6–12, final week)

### Goal
**Clean, navigable codebase.** Every module has one responsibility. No dead code. Clear ownership.

### 3.1 Directory Structure Cleanup

**Remove/archive:**
```
compat_shims/legacy_surfaces/      → archive to docs/archive/legacy_surfaces_ref/
compat_shims/launcher_ui/          → gradual migration (keep 2 weeks, archive rest)
ui/launcher/ (Qt code)             → migrate to ui/web/ or archive
.quarantine/                       → documented, keep
```

**Organize:**
```
src/guppy/
├── api/                  (FastAPI routes, backend selection, inference)
├── backends/             (NEW: unified backend abstraction, replaces routes_backends.py)
├── voice/                (REFACTORED: TTS/STT layers)
├── inference/            (routing, tool execution, legacy code to trim)
├── memory/               (persistence, workspace state)
├── ui/                   (web UI React frontend)
├── cli/                  (launch.py entry, command handling)
└── tools/                (tool registry, tool runner, tool evidence)

docs/
├── PROJECT_BRIEF.md      (active roadmap)
├── LIVE_ARCHITECTURE.md  (runtime truth)
├── archive/              (historical docs, organized by date)
└── reference/            (technical deep-dives)
```

### 3.2 Code Cleanup

**Phase 3a: Dead code detection**
```
Run: python tools/check_architecture_boundaries.py --report
Remove: All detected unreachable code
Verify: All routes mounted, all imports resolved
```

**Phase 3b: Module slimming**
```
modules > 500 lines → split into smaller files
No god objects
Clear domain boundaries
```

**Phase 3c: Test alignment**
```
Rename: compat_shims/launcher_ui/tests/ → tests/legacy_ui_compat/
Rename: tests/smoke/ → tests/integration/smoke/
Create: tests/backends/ (new tests for backend registry)
Create: tests/voice/ (new tests for audio pipeline)
```

### 3.3 Documentation Cleanup

**Update:**
- README.md → reflect backend registry changes
- CLAUDE.md → update architecture, reference new backend layer
- PROJECT_BRIEF.md → final status update (everything complete)

**Create:**
- docs/BACKENDS.md (how to add a new backend)
- docs/AUDIO_PIPELINE.md (TTS/STT architecture and troubleshooting)
- docs/AUDIO_ONLY_WORKSPACE.md (user guide for audio-only mode)

### 3.4 Final Verification (End of Week)

```
✓ dev-check passes with no warnings
✓ test-default passes (100% pass rate)
✓ test-smoke passes (launcher, API, security)
✓ 10 backends healthy (ollama + 8 llamacpp + claude)
✓ Audio-only workspace demo (voice in → voice out)
✓ Backend health dashboard responsive
✓ Project brief up-to-date
✓ README reflects new structure
✓ No dead code, no stale docs
```

---

## Timeline Summary

| Phase | Dates | Owner | Deliverables |
|-------|-------|-------|--------------|
| **1: Audio** | May 1–22 | Ryan + Claude | Refactored TTS/STT, audio-only workspace, audio health telemetry, demo video |
| **2: Backends** | May 23–June 5 | Ryan + Claude | Backend registry, unified routing, fallback orchestration, health dashboard |
| **3: Cleanup** | June 6–12 | Ryan + Claude | Organized repo, updated docs, final verification, release-ready codebase |

---

## Success Criteria

### Audio Pipeline
- [ ] User can use audio-only workspace without touching text input
- [ ] STT confidence > 0.85 for clear speech
- [ ] TTS latency < 1.5s for typical response
- [ ] Fallback chain works: Google → Whisper → SAPI (no user-visible failures)
- [ ] Audio quality feedback integrated into telemetry

### Backends
- [ ] All 10 backends registered, health-checked
- [ ] Routing decision logs explain why backend was chosen
- [ ] Fallback triggered automatically on timeout/error
- [ ] Cost tracking works for cloud backends
- [ ] Health dashboard shows real-time status

### Repo
- [ ] No unreachable code detected
- [ ] All modules < 600 lines
- [ ] All imports resolve
- [ ] All tests pass
- [ ] Documentation current and linked

---

## Critical Path Dependencies

1. **Audio Phase must complete before Backends** — backend routing needs audio metrics
2. **Backends Phase must complete before Cleanup** — cleanup depends on new backend structure
3. **All three complete before June 12** — P6 final delivery

**Risk mitigation:** Start Backends Week 2 in parallel if Audio Phase on track; start Cleanup Week 3 if Backends on track.

---

## Resources Needed

- **Audio specialist:** Ryan (voice expertise) or Claude (coding + testing)
- **Backend specialist:** Ryan (model knowledge) or Claude (refactoring + routing)
- **Repo specialist:** Claude (cleanup, documentation)
- **Testing:** Both (integration, stress testing, demo validation)

---

## Metrics to Track

```
Audio Phase:
  - STT error rate (target < 5%)
  - TTS latency p95 (target < 1500ms)
  - Fallback chain success rate (target > 98%)
  - User rating (target > 4.2/5 on audio quality)

Backends Phase:
  - Backends healthy (target 10/10)
  - Routing decision accuracy (target > 95%)
  - Cost tracking coverage (target 100% of cloud requests)
  - Fallback success rate (target > 98%)

Cleanup Phase:
  - Test pass rate (target 100%)
  - Code coverage (maintain > 75%)
  - Dead code removed (target 0 unreachable)
  - Doc freshness (all docs < 7 days old)
```

---

**Next Step:** Kick off Phase 1 (May 1). Start with TTS/STT decomposition while audio-only workspace design is finalized.
