# Phase 3 Integration Guide: Cloud Provider Clients

**Status:** Implementation in progress (cloud clients + registry wired)  
**Created:** 2026-04-25  
**Files:** 5 cloud client classes + registry integration + tests

---

## What's Implemented

### Phase 3 Deliverables

#### 1. **src/guppy/inference/provider_clients_cloud.py** (750+ lines)
Five cloud provider client implementations extending CloudProviderClient.

**Supported Providers:**

- **AnthropicClient**
  - Models: claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5
  - API: https://api.anthropic.com/v1/messages
  - Auth: x-api-key header
  - Pricing: ~$0.003/1k input, $0.015/1k output (Opus 4.6)
  - Token counting: Exact via messages.count_tokens()

- **OpenAIClient**
  - Models: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo
  - API: https://api.openai.com/v1/chat/completions
  - Auth: Bearer token header
  - Pricing: ~$0.00015/1k input, $0.0006/1k output (GPT-4o-mini)
  - Token counting: Via tiktoken encoding

- **GoogleClient**
  - Models: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash
  - API: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
  - Auth: API key in query parameter
  - Pricing: ~$0.0000375/1k input, $0.00015/1k output (Gemini 2.0 Flash)
  - Token counting: Estimated from character count

- **CohereClient**
  - Models: command-r-plus-08-2024, command-r, command-light, aya
  - API: https://api.cohere.ai/v2/chat
  - Auth: Bearer token header
  - Pricing: ~$0.001/1k input, $0.002/1k output
  - Token counting: Exact via usage field

- **MistralClient**
  - Models: mistral-large-latest, mistral-small-latest, codestral, nemo, pixtral
  - API: https://api.mistral.ai/v1/chat/completions
  - Auth: Bearer token header
  - Pricing: ~$0.0002/1k input, $0.0006/1k output
  - Token counting: Exact via usage field

**Key Features (all providers):**
- Unified async interface: `infer(prompt, system_prompt, task_type, max_tokens)` → `(response_text, InferenceMetadata)`
- Proper error handling: Catches timeouts, API errors, authentication failures
- Health checks: `health_check()` → bool (via minimal inference request)
- Model listing: `list_models()` → List[str]
- Cost tracking: Token counts + per-1k-token pricing
- Timeout management: Configurable via aiohttp.ClientTimeout
- Comprehensive logging at info/error/debug levels

#### 2. **Provider Registry Integration** (provider_registry.py)
Updated registry to instantiate cloud provider clients.

**Changes:**
- Import cloud client classes: `AnthropicClient`, `OpenAIClient`, `GoogleClient`, `CohereClient`, `MistralClient`
- `get_client(provider_id)` now handles all cloud providers with if/elif chain
- Cloud clients accept `api_key` parameter (optional; falls back to environment)
- API keys loaded from environment or settings DB (via ProviderConfig)
- Client instances cached per provider
- All providers initialized with model ID and timeout from config

**Flow:**
```
ProviderRegistry.get_client(provider_id)
  ├─ Check cache (_clients dict)
  ├─ Load config (enabled, API key, model, timeout)
  ├─ Validate API key available
  ├─ Instantiate cloud client:
  │   ├─ AnthropicClient(api_key=..., model=..., timeout=...)
  │   ├─ OpenAIClient(api_key=..., model=..., timeout=...)
  │   ├─ GoogleClient(api_key=..., model=..., timeout=...)
  │   ├─ CohereClient(api_key=..., model=..., timeout=...)
  │   └─ MistralClient(api_key=..., model=..., timeout=...)
  └─ Cache & return client
```

#### 3. **Cloud Client Constructor Updates**
All cloud providers updated to accept `api_key` as optional parameter.

**Pattern:**
```python
class AnthropicClient(CloudProviderClient):
    def __init__(self, model: str = "claude-opus-4-6", timeout: float = 30.0, api_key: Optional[str] = None):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        super().__init__(provider_id="anthropic", model=model, api_key=api_key, timeout=timeout)
```

- Accepts explicit api_key (from registry)
- Falls back to environment variable if not provided
- Passes to parent CloudProviderClient

#### 4. **Integration Tests** (tests/integration/test_provider_registry_phase3.py)
Comprehensive test suite validating registry + cloud clients.

**Test Coverage:**
- Cloud client instantiation with explicit api_key
- Registry client creation for each provider
- Provider caching (same instance returned)
- Fallback chain building with priority ordering
- Disabled provider exclusion
- Registry status/diagnostics structure

---

## How Phase 2 + Phase 3 Work Together

### Architecture
```
FastAPI REST API
    ↓
QueueExecutor.process_next_job()
    ├─ Dequeue next InferenceQueue record
    ├─ Call ProviderRegistry.infer_with_fallback()
    │   ├─ Build fallback chain (enabled providers by priority)
    │   ├─ For each provider in chain:
    │   │   ├─ Get client via ProviderRegistry.get_client()
    │   │   │   └─ Instantiate CloudProviderClient subclass
    │   │   ├─ Execute: client.infer(prompt, system_prompt, ...)
    │   │   ├─ Return (response, InferenceMetadata) on success
    │   │   └─ On timeout/error: try next provider
    │   └─ All providers exhausted: raise RuntimeError
    ├─ Update job: status='success', response=..., provider_used=...
    └─ Record attempt in inference_queue_attempts table
```

### Execution Example
1. **Client submits:** `POST /api/queue/enqueue { prompt: "...", preferred_provider: "anthropic" }`
2. **Queue stores:** InferenceQueue(status='queued', prompt=..., preferred_provider='anthropic', ...)
3. **Scheduler processes:** QueueScheduler.start() polls queue every 5s
4. **Executor dequeues:** QueueExecutor.process_next_job()
   - Fetches job from queue (status='queued')
   - Updates to status='executing'
5. **Fallback chain builds:** `["anthropic", "openai", "google", "cohere", "mistral", "local"]`
   - Prefers "anthropic" (moved to front)
6. **Attempt 1 (Anthropic):**
   - `ProviderRegistry.get_client("anthropic")` → instantiate AnthropicClient
   - `client.infer(prompt, system_prompt)` → call Anthropic API
   - **Timeout after 30s**
   - Record attempt: `InferenceQueueAttempt(attempt_number=1, provider='anthropic', success=0, error='timeout')`
7. **Attempt 2 (OpenAI):**
   - Fallback to next provider
   - `client.infer()` → call OpenAI API
   - **Success:** response received
   - Record: `InferenceQueueAttempt(attempt_number=2, provider='openai', success=1, latency_ms=245.5, cost_usd=0.0015)`
8. **Job completion:**
   - Update job: status='success', response=..., provider_used='openai', retry_count=1
   - Client polls: `GET /api/queue/job/{job_id}` → returns success + response

---

## Integration Checklist

### Step 1: Verify Environment Variables
```bash
# Set cloud provider API keys (or they'll be auto-disabled)
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GOOGLE_API_KEY="AIza..."
export COHERE_API_KEY="..."
export MISTRAL_API_KEY="..."
```

### Step 2: Run Registry Integration Tests
```bash
# Test cloud client instantiation + registry wiring
pytest tests/integration/test_provider_registry_phase3.py -v
```

**Expected output:**
```
test_anthropic_client_with_api_key PASSED
test_openai_client_with_api_key PASSED
test_google_client_with_api_key PASSED
test_cohere_client_with_api_key PASSED
test_mistral_client_with_api_key PASSED
test_registry_creates_anthropic_client PASSED
test_registry_creates_openai_client PASSED
test_registry_client_caching PASSED
test_fallback_chain_respects_priority PASSED
test_registry_status_structure PASSED
```

### Step 3: Test Fallback Chain Integration
```python
# In Python REPL or test
import asyncio
from src.guppy.inference.provider_registry import get_provider_registry

registry = get_provider_registry()

# Check which providers are enabled
status = registry.get_status()
print(status["providers"])
# Output: {'local': {...}, 'anthropic': {...enabled: true}, 'openai': {...enabled: true}, ...}

# Build fallback chain
chain = registry.build_fallback_chain(task_type="complex")
print(chain)
# Output: ['local', 'anthropic', 'openai', 'google', 'cohere', 'mistral']
```

### Step 4: Test Inference with Fallback
```python
import asyncio
from src.guppy.inference.provider_registry import get_provider_registry

registry = get_provider_registry()

# This will try providers in order until one succeeds
response, metadata = await registry.infer_with_fallback(
    prompt="What is 2+2?",
    system_prompt="You are a helpful assistant.",
    task_type="simple",
    preferred_model="anthropic",  # Try Anthropic first
)

print(f"Response: {response}")
print(f"Used provider: {metadata.provider}")
print(f"Latency: {metadata.latency_ms}ms")
print(f"Cost: ${metadata.cost:.6f}")
```

### Step 5: Verify Queue Executor Uses Cloud Providers
```python
# The queue executor already uses infer_with_fallback()
# So Phase 2 queue + Phase 3 cloud clients are integrated
from src.guppy.inference.queue_executor import QueueExecutor
from src.guppy.inference.provider_registry import get_provider_registry

executor = QueueExecutor(db_session, get_provider_registry())

# Enqueue will use cloud providers via fallback chain
job_id = await executor.enqueue(
    prompt="Analyze this code",
    task_type="code",
    preferred_provider="openai",
)

# Scheduler will process via cloud providers
await executor.process_next_job()
```

---

## Health Check & Monitoring

### Provider Health Status
```python
# Check individual provider health
health = await registry.health_check("anthropic")
print(health)  # True or False

# Check all providers
all_health = await registry.health_check_all()
print(all_health)
# Output: {'local': True, 'anthropic': True, 'openai': False, ...}

# View cached health status
health_info = registry._health
print(health_info["anthropic"])
# ProviderHealth(provider_id='anthropic', is_healthy=True, consecutive_failures=0, ...)
```

### Queue Health Metrics
```python
# Via scheduler (from Phase 2)
scheduler = QueueScheduler(db_session, registry)
metrics = await scheduler.get_queue_metrics()
print(metrics)
# {
#   "queued_count": 5,
#   "executing_count": 1,
#   "success_count": 42,
#   "failed_count": 2,
#   "avg_latency_ms": 245.5,
#   "total_cost_usd": 1.23,
# }
```

---

## Troubleshooting

### Cloud Provider Returns None
**Symptom:** `get_client("anthropic")` returns `None`

**Causes:**
1. API key not set: `ANTHROPIC_API_KEY` environment variable missing
2. Provider disabled in config
3. Configuration in settings DB (if loaded)

**Solution:**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
# Restart API/scheduler
```

### Timeout Errors in Fallback Chain
**Symptom:** Provider timeout, but fallback doesn't try next provider

**Causes:**
1. Timeout value too low (default 30s)
2. Network connectivity issue
3. API endpoint down

**Solution:**
```python
# Increase timeout in DEFAULT_CONFIGS (provider_registry.py)
"anthropic": ProviderConfig(
    ...
    timeout_seconds=60.0,  # Increased from 30.0
    ...
)
```

### Health Check Always Returns False
**Symptom:** All providers show `is_healthy=False`

**Causes:**
1. Network issue (can't reach APIs)
2. Invalid API keys
3. API rate limiting

**Solution:**
- Verify network connectivity: `curl https://api.anthropic.com/v1/models`
- Check API key validity in web dashboard
- Review rate limits and quota

---

## Known Limitations & Future Work

**Phase 3 Limitations:**
- Token counting varies by provider (some estimated, some exact)
- Pricing is approximate; use provider billing dashboards for accuracy
- Health checks via minimal inference (wastes API quota) — could use lightweight endpoints
- No distributed caching across multiple inference servers
- No provider load balancing (uses simple priority ordering)

**Phase 4 Work:**
- Implement actual health check endpoints (e.g., `/models` instead of minimal inference)
- Add per-provider request queuing to prevent thundering herd
- Load balancing by health + latency + cost
- Distributed caching for model lists + pricing
- Provider failover strategies (e.g., circuit breaker pattern)
- Cost optimization (route by cost per task type)

---

## Architecture Overview: Full Stack

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI REST API                         │
├─────────────────────────────────────────────────────────────┤
│  routes_queue.py                                            │
│  POST /api/queue/enqueue → job_id                           │
│  GET  /api/queue/job/{id} → status + response              │
│  GET  /api/queue/metrics → queue health                     │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│         Queue Executor & Scheduler (Phase 2)                 │
├─────────────────────────────────────────────────────────────┤
│  QueueExecutor                    QueueScheduler            │
│  ├─ enqueue()                     ├─ start() [daemon]        │
│  └─ process_next_job()            └─ process_ready_jobs()    │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│    Provider Registry + Cloud Clients (Phase 3)              │
├─────────────────────────────────────────────────────────────┤
│  ProviderRegistry.infer_with_fallback()                     │
│  ├─ Build fallback chain:                                    │
│  │  ["local", "anthropic", "openai", "google", ...]         │
│  ├─ For each provider:                                       │
│  │  ├─ get_client() → CloudProviderClient instance          │
│  │  ├─ client.infer() → call API                            │
│  │  └─ Return on success or try next                        │
│  │                                                            │
│  CloudProviderClient subclasses:                            │
│  ├─ AnthropicClient                                          │
│  ├─ OpenAIClient                                             │
│  ├─ GoogleClient                                             │
│  ├─ CohereClient                                             │
│  └─ MistralClient                                            │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│              SQLite Database (persistent)                   │
├─────────────────────────────────────────────────────────────┤
│  inference_queue                 inference_queue_attempts   │
│  inference_metrics               provider_configs            │
└─────────────────────────────────────────────────────────────┘
```

---

**Phase 3 Status:** ✅ Implemented (cloud clients + registry wired)  
**Phase 3 Testing:** 🟡 Basic integration tests added, e2e testing pending  
**Phase 4 Targets:** Health endpoints, load balancing, cost optimization
