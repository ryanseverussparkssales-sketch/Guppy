# Phase 2: Backend Organization & Optimization - Implementation Tasks
**Duration:** May 23–June 5, 2026 (2 weeks)  
**Owner:** Backend Infrastructure Team  
**Depends on:** Phase 1 completion (audio infrastructure)  
**Status:** Ready for execution

---

## Phase 2 Summary

Unify scattered backend code into a centralized `BackendRegistry` with intelligent routing, cost tracking, and fallback chain orchestration. Replace fragmented backend management across multiple files with a single source of truth.

**Success Criteria:**
- All 10 backends (Ollama, 8 llama.cpp variants, Claude) managed via unified registry
- Routing decision time < 50ms
- Cost tracking enabled for all cloud providers
- Fallback chain success rate > 98%
- Health check latency < 2s per backend
- Backend health dashboard responsive

---

## Week 1: Backend Registry & Abstraction (May 23–29)

### Task 1.1: Backend Type System
**Description:** Define core types for backend abstraction.

**Subtasks:**
1. Create `src/guppy/backends/types.py`:
   ```python
   class BackendType(Enum):
       LOCAL = "local"      # Ollama, llama.cpp, LM Studio
       CLOUD = "cloud"      # Claude, GPT-4, Gemini, etc.
   
   class BackendCapability(Enum):
       STREAMING = "streaming"              # Supports token streaming
       TOOL_CALL = "tool_call"              # Can execute tools/functions
       VISION = "vision"                    # Can process images
       FUNCTION_CALLING = "function_calling"  # Structured output
   
   class BackendStatus(Enum):
       HEALTHY = "healthy"
       DEGRADED = "degraded"    # High latency but working
       UNAVAILABLE = "unavailable"
       UNKNOWN = "unknown"      # Not yet probed
   
   @dataclass
   class Backend:
       id: str                              # "claude", "llamacpp-hermes4", etc.
       type: BackendType
       display_name: str
       capabilities: Set[BackendCapability]
       latency_slo_ms: int                 # Target latency
       cost_per_1k_tokens: Optional[float] # None for local
       vram_required_gb: Optional[float]   # None for cloud
       is_local: bool = computed property
       
   @dataclass
   class HealthStatus:
       backend_id: str
       status: BackendStatus
       latency_ms: float
       models_loaded: List[str]
       vram_usage_gb: Optional[float]
       last_check: datetime
       error_message: Optional[str]
   
   @dataclass
   class RoutingDecision:
       primary_backend_id: str
       fallback_chain: List[str]
       reason: str  # "user_selected", "cost_optimized", "latency_slo", etc.
       estimated_cost_cents: Optional[float]
       estimated_latency_ms: float
       timestamp: datetime
   ```

2. Create `src/guppy/backends/base.py`:
   ```python
   class Backend(ABC):
       async def health_check() -> HealthStatus
       async def infer(prompt: str) -> AsyncIterator[str]
       async def infer_batch(prompts: List[str]) -> List[str]
       async def get_available_models() -> List[str]
   ```

**Acceptance Criteria:**
- [ ] All types defined with clear semantics
- [ ] Type hints complete and mypy passes
- [ ] Base class has stable async interface
- [ ] Docstrings complete

**Time Estimate:** 1.5 days  
**Owner:** Backend Lead

---

### Task 1.2: Backend Registry Implementation
**Description:** Implement centralized `BackendRegistry` as single source of truth.

**Subtasks:**
1. Create `src/guppy/backends/registry.py`:
   ```python
   class BackendRegistry:
       def __init__(self):
           self._backends: Dict[str, Backend] = {}
           self._health_cache: Dict[str, HealthStatus] = {}
       
       def register(self, backend: Backend) -> None
       def unregister(self, backend_id: str) -> None
       def get(self, backend_id: str) -> Backend
       def list_all() -> List[Backend]
       def list_by_capability(cap: BackendCapability) -> List[Backend]
       def list_local() -> List[Backend]
       def list_cloud() -> List[Backend]
       
       async def health_check_all() -> Dict[str, HealthStatus]
       async def health_check(backend_id: str) -> HealthStatus
       
       def get_cached_health(backend_id: str) -> Optional[HealthStatus]
   ```

2. Replace scattered backend imports:
   - Old: Direct imports from `inference/router.py`, `api/services_realtime.py`, etc.
   - New: Single `BackendRegistry` instance created at app startup
   - Lazy initialization: backends probed on first access

3. Initialize at app startup:
   - Load all 10 backends into registry
   - Run async health_check_all() with timeout
   - Cache health results
   - Store in app context for route access

**Acceptance Criteria:**
- [ ] Registry implements all CRUD methods
- [ ] Health check caching works
- [ ] All 10 backends register successfully
- [ ] Access time < 10ms for all registry lookups
- [ ] Tests cover all CRUD operations

**Time Estimate:** 2 days  
**Owner:** Backend Lead

---

### Task 1.3: Local Backend Implementations
**Description:** Wrap Ollama, llama.cpp, and LM Studio as Backend implementations.

**Subtasks:**
1. Create `src/guppy/backends/local/ollama.py`:
   - Implement `OllamaBackend` class
   - Connect to `http://127.0.0.1:11434`
   - Support streaming inference
   - Health check: can reach API?
   - Track VRAM usage

2. Create `src/guppy/backends/local/llamacpp.py`:
   - Implement `LlamaCppBackend` base class
   - Create 8 subclasses: Gemma, Pepe, Qwen3, MiniCPM, Dispatch, Hermes4, Hermes3, Rocinante
   - One instance per port (8080-8088)
   - Support streaming with OpenAI API format
   - Health check: port reachable + model loaded?
   - Track VRAM per backend

3. Create `src/guppy/backends/local/lm_studio.py`:
   - Implement `LMStudioBackend` class
   - Discovery mode: find running LM Studio instances
   - Health check if available

4. Register all local backends in registry at startup

**Acceptance Criteria:**
- [ ] All 10 local backends can be instantiated
- [ ] Streaming inference works for each
- [ ] Health checks pass for available backends
- [ ] VRAM tracking accurate
- [ ] Tests verify streaming output quality

**Time Estimate:** 2 days  
**Owner:** Backend Lead

---

### Task 1.4: Cloud Backend Implementations
**Description:** Wrap Claude, GPT-4, Gemini, Mistral, Cohere as Backend implementations.

**Subtasks:**
1. Create `src/guppy/backends/cloud/anthropic.py`:
   - Implement `AnthropicBackend` (Claude)
   - Support streaming messages API
   - Track token counts for billing
   - Cost calculation: $0.003/$0.015 per 1k input/output tokens
   - Health check: API key valid?

2. Create `src/guppy/backends/cloud/openai.py`:
   - Implement `OpenAIBackend` (GPT-4)
   - Support streaming completions
   - Track token counts
   - Cost calculation for GPT-4/4o models
   - Health check: API key valid?

3. Create `src/guppy/backends/cloud/google.py`:
   - Implement `GoogleBackend` (Gemini)
   - Support streaming
   - Cost tracking
   - Health check: credentials valid?

4. Create `src/guppy/backends/cloud/mistral.py`:
   - Implement `MistralBackend`
   - Free tier: ministral-8b
   - Paid: mistral-medium-latest
   - Cost tracking (free vs. paid)

5. Create `src/guppy/backends/cloud/cohere.py`:
   - Implement `CohereBackend`
   - Free tier: command-r7b
   - Cost tracking

6. Register all cloud backends in registry

**Acceptance Criteria:**
- [ ] All 5 cloud backends can be instantiated
- [ ] Streaming inference works for each
- [ ] API key validation on health check
- [ ] Cost calculation accurate
- [ ] Token counting correct
- [ ] Tests verify cost tracking

**Time Estimate:** 2 days  
**Owner:** Backend Lead

---

## Week 2: Routing, Fallback & Dashboard (May 30–June 5)

### Task 2.1: Unified Routing Decision Logic
**Description:** Implement intelligent backend selection based on criteria.

**Subtasks:**
1. Create `src/guppy/backends/routing/router.py`:
   ```python
   class UnifiedRouter:
       def __init__(self, registry: BackendRegistry):
           self.registry = registry
       
       async def route(
           self,
           prompt: str,
           workspace: Workspace,
           user_preference: Optional[str] = None,
           cost_budget_cents: Optional[float] = None,
           latency_slo_ms: int = 2000,
           required_capabilities: Set[BackendCapability] = None
       ) -> RoutingDecision:
           # Criteria priority:
           # 1. User explicit selection (if provided & available)
           # 2. Cost budget (if specified)
           # 3. Latency SLO
           # 4. Required capabilities
           # 5. Default strategy (latency-optimized)
   ```

2. Implement routing criteria evaluation:
   - **User Selection:** If user chose a specific backend, use it
   - **Cost Budget:** Calculate cost for each cloud provider, filter those exceeding budget
   - **Latency SLO:** Use cached health data, prefer backends under SLO
   - **Capabilities:** Filter for required capabilities (vision, tool_call, etc.)
   - **Default:** Prefer local if available, else fastest cloud provider

3. Define default routing strategy:
   - **Latency-optimized (DEFAULT):**
     1. Ollama if available and under SLO
     2. llamacpp-dispatch if available
     3. Mistral free tier if available
     4. Claude if available
   - **Cost-optimized:**
     1. Mistral free tier
     2. Cohere free tier
     3. Claude if budget allows
   - **Quality-optimized:**
     1. Claude Opus
     2. Claude Sonnet
     3. Mistral medium

**Acceptance Criteria:**
- [ ] Routing decision made in < 50ms
- [ ] All criteria properly weighted
- [ ] Default strategy works for all scenarios
- [ ] Tests cover edge cases (all backends down, no budget, etc.)

**Time Estimate:** 2 days  
**Owner:** Backend Lead

---

### Task 2.2: Fallback Chain Orchestration
**Description:** Implement intelligent fallback when primary fails.

**Subtasks:**
1. Create `src/guppy/backends/routing/fallback.py`:
   ```python
   class FallbackChainOrchestrator:
       async def execute_with_fallback(
           self,
           decision: RoutingDecision,
           prompt: str,
           timeout_per_backend: int = 2000
       ) -> InferenceResult:
           # Execute primary + fallback chain
           # Parallel execution, first-success-wins
           # Cancel losers on success
           # Log routing event
   ```

2. Implement parallel execution:
   - Start primary + first fallback in parallel (0ms, 500ms offset)
   - If primary fails within timeout, start next fallback
   - Cap at 3 concurrent backends (cost control)
   - Return first success, cancel others

3. Define default fallback chains:
   - **Local-first chain:**
     1. Ollama (guppy-fast)
     2. llamacpp-dispatch
     3. Claude fallback
   - **Cloud-first chain:**
     1. Claude Sonnet
     2. Claude Haiku (fast)
     3. Mistral free tier

4. Log routing decisions:
   - Which backend was primary
   - Which fallbacks were triggered
   - Why each failed (timeout, error, cost)
   - Final success latency
   - Total cost if cloud

**Acceptance Criteria:**
- [ ] Fallback chain executes correctly
- [ ] Parallel execution works
- [ ] First-success-wins strategy proven
- [ ] Losers cancelled on success
- [ ] Fallback success rate > 98%
- [ ] Tests verify all chain scenarios

**Time Estimate:** 2 days  
**Owner:** Backend Lead

---

### Task 2.3: Backend Health Monitoring
**Description:** Implement real-time health telemetry for all 10 backends.

**Subtasks:**
1. Create `src/guppy/backends/health.py`:
   - Implement health check orchestrator
   - Run checks every 30 seconds in background
   - Store results in cache with TTL
   - Track latency history (rolling 60-min window)

2. Create `GET /api/backends/health` endpoint:
   ```json
   {
       "timestamp": "2026-06-01T10:00:00Z",
       "backends": [
           {
               "id": "ollama",
               "status": "healthy",
               "latency_ms": 345,
               "latency_p95_ms": 520,
               "models_loaded": ["guppy-fast"],
               "vram_usage_gb": 5.2,
               "vram_total_gb": 24,
               "last_check": "2026-06-01T10:00:00Z"
           },
           {
               "id": "claude-opus",
               "status": "healthy",
               "latency_ms": 1200,
               "latency_p95_ms": 1800,
               "models_loaded": ["claude-opus"],
               "cost_per_1k_tokens": 0.015,
               "tokens_used_today": 45000,
               "cost_today_cents": 67.5,
               "last_check": "2026-06-01T09:59:45Z"
           }
       ],
       "summary": {
           "backends_healthy": 8,
           "backends_degraded": 1,
           "backends_unavailable": 1,
           "total_vram_available_gb": 24,
           "total_cost_today_cents": 125.3
       }
   }
   ```

3. Add cost tracking:
   - Track tokens per cloud backend per day
   - Calculate cost using provider rates
   - Aggregate to workspace/conversation level
   - Show cost breakdown in dashboard

4. Add telemetry persistence:
   - Store RoutingEvent (decision, backend, latency, cost) to `backend_routing.jsonl`
   - Rolling 7-day window
   - Aggregate stats on query

**Acceptance Criteria:**
- [ ] Health checks run reliably every 30s
- [ ] Cache TTL prevents stale data
- [ ] Endpoint response < 100ms
- [ ] Cost calculation accurate
- [ ] Latency percentiles computed correctly
- [ ] Tests verify health check accuracy

**Time Estimate:** 2 days  
**Owner:** Backend Lead

---

### Task 2.4: Backend Health Dashboard
**Description:** Build web UI dashboard for backend status monitoring.

**Subtasks:**
1. Create React component `src/guppy/web/pages/BackendsDashboard.tsx`:
   - Real-time backend status cards (green/yellow/red)
   - Latency sparklines per backend
   - VRAM stacked bar chart
   - Cost tracker showing today's spend
   - Fallback chain trigger heatmap
   - Provider success rate comparison

2. Add metrics to dashboard:
   - Average inference latency by provider
   - Error rate trends
   - Cost vs. tokens graph
   - Uptime % over last 7 days
   - Cache hit rate (repeated queries)

3. Add settings per backend:
   - Enable/disable backend
   - Set SLO target latency
   - Set cost budget limit
   - Set max VRAM usage

4. Auto-refresh every 5 seconds
   - Don't hammer API with requests
   - Batch multiple metrics in single call
   - Show last-update timestamp

**Acceptance Criteria:**
- [ ] Dashboard loads in < 2s
- [ ] Metrics refresh smoothly
- [ ] All 10 backends visible
- [ ] Cost tracking visible
- [ ] SLO violations highlighted
- [ ] Settings persist across refresh

**Time Estimate:** 2 days  
**Owner:** Frontend Lead

---

### Task 2.5: Backend-Specific Optimizations
**Description:** Tune each backend for target SLO.

**Subtasks:**
1. **Ollama (guppy-fast)**
   - Pin model in memory: don't unload
   - Target SLO: < 300ms
   - Prefetch common prompts
   - Measure: run 50 inference calls, log latency

2. **llamacpp-dispatch**
   - 2.5GB VRAM, fast routing model
   - Target SLO: < 500ms
   - Keep loaded at all times
   - Pre-warm with empty chat context

3. **llamacpp-pepe**
   - Target SLO: < 500ms
   - Prefetch context for current conversation
   - Monitor: token throughput and latency stability

4. **llamacpp-qwen3**
   - 19GB VRAM, reasoning-heavy model
   - Target SLO: < 2000ms
   - Solo use only (don't pair with other models)
   - Cache recent contexts

5. **llamacpp-hermes4**
   - Target SLO: < 800ms
   - Primary tool-execution backend
   - Ensure jinja template support enabled
   - Monitor: tool-call success rate

6. **Claude Opus (Primary Cloud)**
   - Target SLO: < 2000ms
   - Batching for cost optimization
   - Token counting for accurate cost tracking
   - Cache system prompt

7. **Mistral/Cohere (Cost-optimized)**
   - Use as fallback when Claude cost exceeds budget
   - Target SLO: < 2500ms
   - Monitor: feature parity with Claude

**Acceptance Criteria:**
- [ ] Each backend meets or exceeds target SLO
- [ ] SLO measured over 50+ inference calls
- [ ] p95 latency tracked and logged
- [ ] Optimization baseline documented
- [ ] No regression from current performance

**Time Estimate:** 2 days  
**Owner:** Backend Lead

---

### Task 2.6: Phase 2 Integration & Validation
**Description:** Integrate all components and validate.

**Subtasks:**
1. Integration checklist:
   - [ ] BackendRegistry loads all 10 backends
   - [ ] Unified router makes decisions < 50ms
   - [ ] Fallback chain executes correctly
   - [ ] Health dashboard responsive
   - [ ] Cost tracking accurate
   - [ ] Tests passing (routing + health + backends)
   - [ ] No performance regressions

2. Success criteria validation:
   - [ ] All 10 backends managed via registry
   - [ ] Routing decision time < 50ms
   - [ ] Cost tracking enabled for all cloud
   - [ ] Fallback chain success > 98%
   - [ ] Health check latency < 2s
   - [ ] Dashboard loads < 2s

3. Load testing:
   - Simulate 100 concurrent inference requests
   - Mix local and cloud backends
   - Verify fallback chain under load
   - Measure latency percentiles (p50, p95, p99)

4. Cost analysis:
   - Run sample workload (1000 inference calls)
   - Calculate cost vs. performance
   - Verify budget controls work
   - Document cost-performance trade-offs

**Acceptance Criteria:**
- [ ] All success criteria met
- [ ] Integration complete
- [ ] Load test results documented
- [ ] Phase 2 ready for handoff to Phase 3

**Time Estimate:** 2 days  
**Owner:** Backend Lead + Tech Lead

---

## Timeline Summary

| Week | Dates | Focus | Deliverable |
|------|-------|-------|-------------|
| 1 | May 23–29 | Registry + Type System | Unified BackendRegistry with all 10 backends |
| 2 | May 30–June 5 | Routing + Health + Dashboard | Routing engine + fallback orchestration + monitoring dashboard |

---

## Dependencies

- **Phase 1 completion:** Audio infrastructure must be stable before starting Phase 2
- **All API keys:** Claude, OpenAI, Google, Mistral, Cohere needed for cloud backend testing
- **Ollama running:** Required for Ollama + llama.cpp testing
- **GPU availability:** llama.cpp backends need GPU for performance targets
- **Network connectivity:** Cloud provider API access

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Routing Decision Time | < 50ms | Measure from request to decision made |
| Fallback Success Rate | > 98% | Successful recovery / total fallback triggers |
| Health Check Latency | < 2s | Time to check all 10 backends |
| Dashboard Load Time | < 2s | First paint to interactive |
| Cost Tracking Accuracy | 100% | Compare calculated cost to API billing |
| Backend SLO Achievement | > 95% | Requests meeting target latency / total requests |

---

## Handoff Notes for Phase 3

- Backend registry is now centralized and stable
- Routing decisions can be further optimized with ML-based decision making in future
- Health dashboard ready for expansion with cost prediction and budget alerts
- Fallback chain success metrics inform future redundancy decisions
- Consider adding more local backends (LM Studio, Ollama fine-tunes) in future phases

**Phase 2 Completion Target:** June 5, 2026  
**Phase 3 Kickoff:** June 6, 2026
