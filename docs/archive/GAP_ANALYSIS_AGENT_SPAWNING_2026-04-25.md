# Gap Analysis: Agent Spawning & Cloud-Local Integration
**Date:** 2026-04-25  
**Scope:** Current repo vs Phase 1-4 execution plan  
**Owner:** Full-stack + Backend engineers

---

## Executive Summary

Guppy has **strong foundational infrastructure for agent spawning and cloud-local routing** but is missing critical orchestration, persistence, and fallback chain logic. The router exists and task classification works, but:

1. ✅ **Already implemented:** Task classifier, provider detection, basic model catalog
2. ⚠️ **Partially built:** Inference router (local → cloud fallback), in-memory job tracking
3. ❌ **Missing:** Agent job persistence, queue + retry logic, cost attribution, metrics collection

**Phase 1 feasibility:** 80% of code exists; 20% wiring + testing needed  
**Critical blocker:** Web UI ↔ Desktop parity validation (not router-dependent)  
**Timeline:** Phase 1 achievable in 2 weeks with focused effort

---

## Part 1: Current State vs Planning Docs

### A. Provider Abstraction Layer

**Status:** ✅ Partially implemented  
**Location:** `src/guppy/api/routes_providers.py` + `src/guppy/inference/_router_fragment_core.py`

**What exists:**
- Five cloud providers hardcoded: Anthropic, OpenAI, Google, Cohere, Mistral
- Provider model catalogs (21+ models across 5 providers)
- Local model metadata with capability tags (7 Ollama custom models + base models)
- Active provider tracking in settings DB

**What's missing:**
- Provider abstraction interface (abstract base class)
- Unified provider client factory (currently Anthropic, OpenAI, Google hardcoded)
- Provider health checks / readiness probes
- Cost-per-token metadata per provider model
- Rate limit tracking per provider

**Gap size:** 2-3 days of work

**Code sample (current):**
```python
# routes_providers.py
_ANTHROPIC_MODELS = [
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "tier": "smart"},
    ...
]

_OPENAI_MODELS = [
    {"id": "gpt-4o", "name": "GPT-4o", "tier": "smart"},
    ...
]
```

**Required abstraction:**
```python
class ProviderClient(ABC):
    def get_models(self) -> List[ModelSpec]: ...
    def infer(self, prompt, model_id, max_tokens) -> str: ...
    def health_check(self) -> ProviderHealth: ...
    def get_cost_per_token(self, model_id) -> float: ...

class ProviderRegistry:
    def register(self, provider_id: str, client: ProviderClient): ...
    def get_client(self, provider_id: str) -> ProviderClient: ...
    def list_providers(self) -> List[ProviderMetadata]: ...
```

---

### B. Task Router & Complexity Detection

**Status:** ✅ Fully implemented  
**Location:** `src/guppy/inference/_router_fragment_core.py` (lines 189-250)

**What exists:**
- `_classify_task()` method returning "simple" / "complex" / "teaching"
- Semantic classification via Haiku (with cache)
- Fallback heuristic (keyword-based) when semantic classifier disabled
- Classification cache (256 entries)
- Environment variable overrides for low-compute mode

**Classification logic:**
```python
def _classify_task(self, user_text: str, system_prompt: str = "") -> str:
    # 1. Check cache
    # 2. If semantic classifier enabled + Haiku available:
    #    - Call Haiku to classify as simple/complex/teaching
    # 3. Fallback to keyword heuristics
    # 4. Cache result
```

**Local model selection (already wired):**
```python
LOCAL_TIER_MAP = {
    "simple": "guppy-fast",      # 7B, ~0.43s (with ROCm)
    "complex": "guppy",           # 32B, ~2-4s
    "teaching": "guppy-teach",    # 32B, specialized
}
```

**What's missing:**
- Task complexity signals: token budget, context window required, reasoning depth
- Specialized task types: "coding", "vision", "research"
- Fallback routing rules (which provider when Ollama times out)
- Cost-based routing (when budget exceeded)
- Latency-based routing (when latency budget critical)

**Gap size:** 1 day of work (extending classifier, adding signals)

---

### C. Fallback Chain & Retry Logic

**Status:** ⚠️ Partially implemented  
**Location:** `src/guppy/api/routes_realtime.py` (lines 177-186)

**What exists:**
- Single inference call: `ctx.call_unified_inference(message, system_prompt, mode, history)`
- Timeout handling: `owner.CHAT_TIMEOUT_SECONDS` (default ~60s)
- Idempotency key tracking (prevents duplicate requests)
- Response caching for "simple" tasks

**What's missing (critical):**
- Queue + retry infrastructure (in-memory or Redis)
- Token refresh hooks (when cloud provider auth expires)
- Circuit breaker pattern (stop retrying after N failures)
- Error recovery UI (chat banner + "retry" button)
- Fallback chain execution: local (5s) → cloud-tier1 (30s) → cloud-tier2 (60s)
- Partial response streaming on retry

**Current code (simple fallback only):**
```python
response = await ctx.run_blocking(
    ctx.call_unified_inference,
    request.message,
    system_prompt,
    request.mode,
    request.history,
    instance_name=active_instance_name,
    instance_type=active_instance_type,
    timeout_seconds=owner.CHAT_TIMEOUT_SECONDS,
)
```

**Required queue structure:**
```python
class ChatQueueEntry:
    id: str                          # UUID
    request: ChatRequest             # Original request
    status: str                      # queued, running, failed, completed
    attempts: int                    # Retry count
    last_provider: str               # Local, Haiku, Sonnet
    error: Optional[str]
    response: Optional[str]
    created_at: datetime
    updated_at: datetime
    metadata: Dict                   # Latency, tokens, cost, etc.
```

**Gap size:** 1-2 weeks of work

---

### D. Agent Job Spawning & Management

**Status:** ❌ Not implemented  
**Location:** Would be `src/guppy/api/routes_agents.py` + `src/guppy/jobs/agent_executor.py`

**Current related code:**
- Model pull job tracker in `routes_models.py` (simple threading + in-memory dict)
- Agent CLI in `src/guppy/cli/agent.py` (terminal interface, not job-based)

**What's missing (entire system):**

1. **Job database schema:**
   ```sql
   CREATE TABLE agent_jobs (
       id TEXT PRIMARY KEY,           -- UUID
       conversation_id TEXT NOT NULL,
       user_id TEXT NOT NULL,
       task_type TEXT,                -- complex, specialized, research
       status TEXT,                   -- spawned, running, streaming, completed, failed
       classification TEXT,           -- Task complexity from router
       selected_provider TEXT,        -- "local" / "anthropic" / "openai" / etc
       selected_model TEXT,           -- "guppy" / "claude-opus-4-7" / etc
       original_message TEXT,
       system_prompt TEXT,
       max_tokens INT,
       latency_budget_ms INT,
       created_at TIMESTAMP,
       started_at TIMESTAMP,
       completed_at TIMESTAMP,
       duration_ms INT,
       error_message TEXT,
       cost_usd DECIMAL(10, 4),
       tokens_used INT,
       result TEXT,                   -- Agent response
       metadata JSONB                 -- Extra tracking
   );
   ```

2. **Agent executor (orchestrator):**
   ```python
   class AgentExecutor:
       async def spawn(
           self,
           conversation_id: str,
           message: str,
           system_prompt: str,
           task_type: str,  # "complex", "research", "specialized"
           provider_hint: str = "auto",  # User preference
           max_tokens: int = 16384,
           latency_budget_ms: int = 60000,
       ) -> AgentJob:
           """
           1. Create job record in DB
           2. Select provider based on task_type + latency_budget
           3. Start agent in background
           4. Return job_id for polling
           """
   
       async def stream_results(self, job_id: str) -> AsyncIterator[str]:
           """Stream agent output back to chat"""
   
       async def get_status(self, job_id: str) -> AgentJobStatus:
           """Poll job status"""
   
       async def cancel(self, job_id: str) -> None:
           """Cancel running agent"""
   ```

3. **API endpoints:**
   ```
   POST   /api/agents/spawn          → spawn agent job
   GET    /api/agents/{job_id}       → poll status
   GET    /api/agents/{job_id}/stream → stream results (EventSource/SSE)
   DELETE /api/agents/{job_id}       → cancel job
   ```

4. **Chat integration:**
   - Detect when task complexity == "complex"
   - Show user: "Complex task detected. Spawning agent..."
   - Return job_id immediately (non-blocking)
   - Stream results as agent runs
   - Show provider badge: "Running on Claude Opus"

**Gap size:** 2-3 weeks of work

---

### E. Cost Attribution & Metrics

**Status:** ❌ Not implemented  
**Location:** Would be `src/guppy/metrics/cost_tracker.py`

**What's needed:**

1. **Cost metadata per model:**
   ```python
   COST_PER_TOKEN_1M = {
       # Local (zero cost)
       "guppy": 0.0,
       "guppy-fast": 0.0,
       
       # Anthropic (April 2026 pricing)
       "claude-haiku": {"input": 0.80, "output": 4.0},
       "claude-sonnet": {"input": 3.0, "output": 15.0},
       "claude-opus": {"input": 15.0, "output": 75.0},
       
       # OpenAI
       "gpt-4o": {"input": 2.50, "output": 10.0},
       "gpt-4o-mini": {"input": 0.15, "output": 0.60},
       
       # Google
       "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
       "gemini-2.5-pro": {"input": 1.25, "output": 5.0},
   }
   ```

2. **Cost calculator:**
   ```python
   class CostTracker:
       def estimate_cost(
           self,
           provider: str,
           model: str,
           input_tokens: int,
           output_tokens: int,
       ) -> float:
           """Estimate cost in USD"""
   
       def record_inference(
           self,
           job_id: str,
           provider: str,
           model: str,
           input_tokens: int,
           output_tokens: int,
           latency_ms: int,
       ) -> None:
           """Record actual inference metrics"""
   ```

3. **Metrics database:**
   ```sql
   CREATE TABLE inference_metrics (
       id TEXT PRIMARY KEY,
       conversation_id TEXT,
       provider TEXT,
       model TEXT,
       input_tokens INT,
       output_tokens INT,
       total_tokens INT,
       latency_ms INT,
       cost_usd DECIMAL(10, 6),
       success BOOLEAN,
       error_code TEXT,
       timestamp TIMESTAMP,
       INDEX (conversation_id, timestamp),
       INDEX (provider, timestamp),
   );
   ```

4. **Daily cost report:**
   ```python
   class DailyCostSummary:
       total_cost: float
       inference_count: int
       by_provider: Dict[str, float]
       by_model: Dict[str, float]
       by_status: Dict[str, int]  # "success", "failed", "fallback"
       top_expensive_conversations: List[Tuple[str, float]]
   ```

**Gap size:** 3-4 days of work

---

## Part 2: Implementation Roadmap (Phase 1-4)

### Phase 1: Provider Abstraction + Task Router (Weeks 1-2)

**Effort:** 80 hours (2 FTE weeks)

**Deliverables:**
1. ✅ Provider abstraction interface + registry (18 hours)
2. ✅ Extend task classifier with complexity signals (12 hours)
3. ✅ Local → Cloud fallback routing rules (16 hours)
4. ✅ Provider health checks (10 hours)
5. ✅ Unit tests (20 hours)
6. ✅ Integration tests with all 5 cloud providers (4 hours)

**Critical path tasks:**
- Define `ProviderClient` abstract base class
- Build `ProviderRegistry` with lazy client initialization
- Add signals to task classifier (token budget, context window, reasoning depth)
- Implement 3-tier routing: Local (5s) → Haiku (30s) → Sonnet (60s)
- Test fallback on Ollama timeout

**Success criteria:**
- `pytest tests/unit/test_provider_registry.py` ✅
- `pytest tests/integration/test_router_fallback.py` ✅
- All cloud providers return expected model lists
- Task classifier returns "simple"/"complex"/"teaching" with >90% accuracy

**Key files to create:**
```
src/guppy/inference/providers/__init__.py
src/guppy/inference/providers/base.py              # ProviderClient ABC
src/guppy/inference/providers/registry.py          # ProviderRegistry
src/guppy/inference/providers/anthropic_client.py
src/guppy/inference/providers/openai_client.py
src/guppy/inference/providers/google_client.py
src/guppy/inference/providers/cohere_client.py
src/guppy/inference/providers/mistral_client.py
src/guppy/inference/providers/ollama_client.py     # Wrap local_client.py

src/guppy/inference/task_classification.py         # Extend _classify_task
src/guppy/inference/routing_rules.py               # Fallback chains
```

---

### Phase 2: Wire into Chat + Queue Logic (Week 3)

**Effort:** 80 hours (2 FTE weeks)

**Deliverables:**
1. ✅ Chat queue + retry system (24 hours)
2. ✅ Token refresh hooks (12 hours)
3. ✅ Error recovery UI (chat banner + retry button) (16 hours)
4. ✅ Idempotency + deduplication (10 hours)
5. ✅ Fallback chain integration with routes_realtime.py (12 hours)
6. ✅ Tests + E2E verification (6 hours)

**Critical path:**
- Build in-memory queue with SQLite persistence option
- Hook `call_unified_inference()` → queue executor
- Implement circuit breaker (3 consecutive failures = stop retrying)
- Add error recovery UI to chat (banner: "Request failed on Haiku. Retrying on Sonnet...")
- Test fallback under simulated network failures

**Success criteria:**
- Chat survives provider timeout
- Fallback chain executes automatically
- User sees provider switch notification
- Manual retry button works

**Key files:**
```
src/guppy/api/queue/__init__.py
src/guppy/api/queue/chat_queue.py               # In-memory queue
src/guppy/api/queue/persistence.py              # Optional SQLite backing
src/guppy/api/queue/retry_policy.py             # Circuit breaker

web/src/components/ChatErrorRecovery.tsx         # Error banner + retry UI
```

---

### Phase 3: Metrics Dashboard (Week 4)

**Effort:** 40 hours (1 FTE week)

**Deliverables:**
1. ✅ Cost tracker database schema (6 hours)
2. ✅ Cost recorder in inference path (8 hours)
3. ✅ Daily metrics report + email (8 hours)
4. ✅ Web UI metrics dashboard (12 hours)
5. ✅ Real-time charts: latency, cost, success rate by provider (6 hours)

**Dashboard shows:**
- Total cost this month (USD)
- Cost by provider (pie chart)
- Latency distribution (histogram)
- Success rate by provider (%)
- Top 10 expensive conversations
- Inference count trend (line chart)

**Key files:**
```
src/guppy/metrics/__init__.py
src/guppy/metrics/cost_tracker.py               # Cost recording
src/guppy/metrics/models.py                     # SQLAlchemy schema
src/guppy/metrics/daily_report.py               # Report generation

web/src/views/MetricsView.tsx                   # Dashboard UI
web/src/hooks/useMetrics.ts                     # TanStack Query hooks
```

---

### Phase 4: Agent Spawning for Complex Tasks (Weeks 5-6)

**Effort:** 120 hours (3 FTE weeks)

**Deliverables:**
1. ✅ Agent job schema + database (10 hours)
2. ✅ Agent executor (spawn, stream, status, cancel) (30 hours)
3. ✅ API endpoints + handlers (20 hours)
4. ✅ Chat integration (detect complex → spawn) (16 hours)
5. ✅ Agent status UI in chat (job card, streaming output) (20 hours)
6. ✅ End-to-end tests (cost tracking, fallback, cancellation) (24 hours)

**Agent spawning logic:**
```
User message: "Give me a comprehensive analysis of our Q1 sales pipeline"
    ↓
Router.classify_task() → "complex"
    ↓
Chat returns immediately:
{
  "job_id": "ag_abc123",
  "status": "spawned",
  "provider": "anthropic",
  "model": "claude-opus-4-7",
  "message": "Complex task detected. Spawning agent on Claude Opus..."
}
    ↓
Web UI shows: [Agent Running] "Analyzing sales pipeline..." (streaming)
    ↓
Agent streams chunks as it reasons
    ↓
User can click "Show Full Reasoning" to expand
    ↓
Agent completes, cost tracked: $0.23

Latency: 45 seconds (acceptable for complex task)
```

**Success criteria:**
- Complex tasks automatically spawn agents
- Local model attempted first (if under latency budget)
- Fallback to cloud-tier1 (Haiku) if local times out
- Fallback to cloud-tier2 (Opus) if Haiku insufficient
- Cost tracked and reported
- User can cancel mid-run
- Streaming output visible in chat

**Key files:**
```
src/guppy/jobs/__init__.py
src/guppy/jobs/models.py                        # AgentJob SQLAlchemy model
src/guppy/jobs/executor.py                      # AgentExecutor class
src/guppy/jobs/persistence.py                   # Job DB access layer

src/guppy/api/routes_agents.py                  # API: /agents/{id}

web/src/components/AgentStatus.tsx              # Agent status card
web/src/components/StreamingOutput.tsx          # Real-time output
web/src/hooks/useAgentJob.ts                    # Polling + streaming
```

---

## Part 3: Critical Gaps & Blockers

### Blocker 1: Web UI ↔ Desktop Parity (P6 Critical)

**Impact:** High - Blocks entire Phase 2-4 without this  
**Timeline:** 3-4 weeks (separate from router work)  
**Dependency:** None (parallel track)

**What's blocking:**
- Web UI model list ≠ Desktop launcher model list (inventory sync)
- Workspace state doesn't persist across launcher ↔ web (selected model, settings, chat history)
- Route switching (local → cloud) not synced between surfaces

**Solution:** See STRATEGIC_ASSESSMENT.md Critical Path #1

---

### Blocker 2: Chat Stability (P6 Critical)

**Impact:** High - Requires Phase 2 completion  
**Timeline:** 2-3 weeks  
**Dependency:** Phase 1 (provider abstraction)

**What's blocking:**
- Token refresh fails during inference
- No retry mechanism if provider times out
- No fallback chain execution

**Solution:** See EXECUTION_PRIORITY_MATRIX.md Critical Path #2

---

### Blocker 3: Cost Attribution Data Model

**Impact:** Medium - Phase 5 (ML optimizer) depends on accurate metrics  
**Timeline:** 3-4 days (Phase 3)  
**Dependency:** Phase 1 (provider abstraction)

**What's blocking:**
- Can't optimize provider selection without cost data
- Can't build ROI report without latency + cost tracking

**Solution:** Implement metrics schema in Phase 3

---

## Part 4: Dependency Map

```
┌─────────────────────────────────────────────────────────┐
│          START: Environment + Providers Ready            │
│          (ANTHROPIC_API_KEY, OPENAI_API_KEY set)         │
└────────────────────────────┬────────────────────────────┘
                             ↓
        ┌────────────────────────────────────┐
        │ Phase 1: Provider Abstraction       │ (Weeks 1-2)
        │ ✓ ProviderRegistry                 │
        │ ✓ Task classification signals      │
        │ ✓ Routing rules                    │
        │ ✓ Tests passing                    │
        └────────────┬───────────────────────┘
                     ↓
        ┌────────────────────────────────────┐
        │ Phase 2: Chat Queue + Fallback      │ (Week 3)
        │ ✓ routes_realtime.py integration   │
        │ ✓ Fallback chain execution         │
        │ ✓ Error recovery UI                │
        │ ✓ E2E tests                        │
        └────────────┬───────────────────────┘
                     ↓
        ┌────────────────────────────────────┐
        │ Phase 3: Metrics + Cost Tracking    │ (Week 4)
        │ ✓ CostTracker in inference path    │
        │ ✓ Daily report                     │
        │ ✓ Web dashboard                    │
        │ ✓ Real-time charts                 │
        └────────────┬───────────────────────┘
                     ↓
        ┌────────────────────────────────────┐
        │ Phase 4: Agent Spawning             │ (Weeks 5-6)
        │ ✓ Agent job schema                 │
        │ ✓ AgentExecutor class              │
        │ ✓ Chat integration                 │
        │ ✓ Streaming UI                     │
        │ ✓ Cost + latency tracking          │
        └────────────┬───────────────────────┘
                     ↓
        ┌────────────────────────────────────┐
        │ Phase 5: ML Cost Optimizer (Future) │ (Ongoing)
        │ • Retrain on Phase 3 metrics       │
        │ • Optimize provider selection      │
        │ • A/B test routing strategies      │
        └────────────────────────────────────┘

PARALLEL CRITICAL PATHS (not blocked by router):
┌─────────────────────────────────────────┐
│ Parity Validation (Web ↔ Launcher)      │ (Weeks 1-4)
│ Chat Stability (Queue + Retry)          │ (Weeks 2-3)
│ Freeze-Readiness Program (FR-C4–C10)    │ (Ongoing)
└─────────────────────────────────────────┘
```

---

## Part 5: Code Quality Standards

### Testing Requirements

**Phase 1:**
- Unit tests: 100% coverage for ProviderRegistry
- Integration tests: All 5 cloud providers + Ollama
- Mock external APIs (don't hit real endpoints)

**Phase 2:**
- Queue tests: Enqueue, dequeue, retry, circuit breaker
- Fallback tests: Timeout + switch providers
- Error recovery UI tests (Vitest + React Testing Library)

**Phase 3:**
- Cost calculation tests: Verify pricing per provider
- Metrics aggregation tests: Verify grouping by provider/model

**Phase 4:**
- Agent spawning tests: Verify job lifecycle
- Streaming tests: Verify output delivery
- Cancellation tests: Verify cleanup

### Code Organization

**Current mess:** Mixed router logic across:
- `_router_fragment_core.py`
- `_router_fragment_api.py`
- `_router_fragment_execution.py`
- `routes_realtime.py`

**Refactored structure:**
```
src/guppy/inference/
├── router.py                   # Main orchestrator
├── providers/
│   ├── base.py                 # ProviderClient ABC
│   ├── registry.py             # ProviderRegistry
│   ├── anthropic.py
│   ├── openai.py
│   └── ollama.py
├── classification.py           # Task classification
├── routing_rules.py            # Fallback chains
└── cache.py                    # Response cache

src/guppy/api/
├── queue/
│   ├── chat_queue.py           # Queue manager
│   └── retry_policy.py         # Circuit breaker
└── routes_realtime.py          # Cleaned up, delegate to queue

src/guppy/jobs/
├── models.py                   # SQLAlchemy schemas
├── executor.py                 # AgentExecutor
└── persistence.py              # DB access layer

src/guppy/metrics/
├── cost_tracker.py             # Cost recording
├── models.py                   # SQLAlchemy schemas
└── daily_report.py             # Report generation
```

---

## Part 6: Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Cloud provider API changes | Medium | High | Version pin, test all 5 |
| Token limits during complex tasks | Medium | Medium | Set max_tokens conservatively |
| Fallback chain deadlock | Low | High | Circuit breaker + timeout |
| Cost calculation errors | Low | Medium | Unit tests + reconciliation |
| Agent job loss on crash | Medium | High | SQLite persistence |
| Parity blocker delays router | High | High | Run parallel (parity team independent) |

---

## Part 7: Recommended Next Steps

### Week 1 (Apr 25 – May 1)

1. **Day 1-2:** Create ProviderClient ABC + registry (code review with full-stack engineer)
2. **Day 3-4:** Wrap all 5 cloud providers + Ollama in new interface
3. **Day 5:** Extend task classifier with complexity signals
4. **Day 6-7:** Implement fallback routing rules + tests

**Success metric:** Phase 1 code skeleton + tests running locally

### Week 2 (May 2-8)

1. **Integrate Phase 1 with routes_realtime.py**
2. **Implement queue + retry system**
3. **Add error recovery UI**
4. **Full integration tests**

**Success metric:** Chat survives Ollama timeout, falls back to Haiku

### Week 3 (May 9-15)

1. **Cost tracker schema + recording**
2. **Daily report generation**
3. **Web UI metrics dashboard**

**Success metric:** Dashboard shows real cost data

### Weeks 4-6 (May 16 – June 12)

1. **Agent job schema + executor**
2. **Chat integration (detect complex → spawn)**
3. **Streaming UI**
4. **End-to-end tests**

**Success metric:** Complex tasks spawn agents automatically

---

## Part 8: Known Unknowns

1. **Should agent spawning be sync or async?**
   - Current: Routes are async
   - Recommendation: Async with background task queue (celery or APScheduler)

2. **How to stream agent output in real-time?**
   - Option A: Polling (simple, 1-2s latency)
   - Option B: SSE (streaming, <100ms latency)
   - Recommendation: SSE with polling fallback

3. **How to handle user cancellation mid-stream?**
   - Challenge: Can't interrupt in-flight API call
   - Recommendation: Mark job as "cancelled" in DB, stop displaying output

4. **Should cost tracking be per-request or per-token?**
   - Current plan: Per-token (more accurate)
   - Fallback: Per-request (simpler)

---

**Status: Ready for Phase 1 kickoff**  
**Estimated completion: June 12, 2026 (P6 deadline)**
