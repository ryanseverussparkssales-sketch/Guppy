# Phase 4: Health Check Optimization

**Status:** Planning  
**Focus:** Replace minimal inference health checks with real lightweight endpoints  
**Impact:** Reduce API quota usage, improve health accuracy, lower latency

---

## Current State (Phase 3)

### Problem
```python
# Current implementation in cloud clients
async def health_check(self) -> bool:
    """Check health by attempting minimal inference."""
    try:
        response, metadata = await self.infer(
            prompt="1+1=",  # Minimal prompt
            max_tokens=5,
        )
        return True
    except Exception:
        return False
```

**Issues:**
- Wastes API quota on every health check
- Each check counts as a billable inference
- High latency (API round-trip for inference)
- Inaccurate for connectivity-only checks

### Current Health Check Behavior
- Cached for 5 seconds (TTL)
- Triggered on: registry initialization, explicit checks, health_check_all()
- Part of fallback chain building (excludes unhealthy providers)
- Consecutive failure tracking (> 2 failures = excluded)

---

## Optimization Strategy

### Goal
Replace minimal inference with real but lightweight API endpoints:
- Models listing endpoints (fast, free/cheap)
- API connection checks (no inference)
- Reduce from ~500-2000ms to ~50-200ms
- Zero inference quota usage

### Per-Provider Health Endpoints

#### 1. **Local (Ollama)**
```
Current: POST /api/generate (minimal inference)
Optimized: GET /api/v1/models
- Lists available models
- No inference needed
- Latency: ~20-50ms
```

#### 2. **Anthropic**
```
Current: POST /v1/messages (minimal inference)
Optimized: GET /v1/models (if available) or OPTIONS /v1/messages
- List available Claude models
- Or check API authentication via OPTIONS
- Latency: ~50-100ms
```

#### 3. **OpenAI**
```
Current: POST /v1/chat/completions (minimal inference)
Optimized: GET /v1/models
- List all available GPT models
- No inference needed
- Latency: ~30-80ms
- Free/included in API key quota
```

#### 4. **Google**
```
Current: POST /v1beta/models/{model}:generateContent (minimal inference)
Optimized: GET /v1beta/models (list models endpoint)
- List available Gemini models
- No inference needed
- Latency: ~50-100ms
```

#### 5. **Cohere**
```
Current: POST /v2/chat (minimal inference)
Optimized: GET /v2/models (if available) or HEAD /v2/chat
- List available Command models
- Or check API via HEAD request
- Latency: ~40-90ms
```

#### 6. **Mistral**
```
Current: POST /v1/chat/completions (minimal inference)
Optimized: GET /v1/models
- List available Mistral models
- No inference needed
- Latency: ~30-80ms
```

---

## Implementation Plan

### Phase 4a: Add Lightweight Health Endpoints

#### Step 1: Update CloudProviderClient ABC
```python
class CloudProviderClient(ProviderClient):
    """Abstract base for cloud providers."""
    
    async def health_check(self) -> bool:
        """Check provider health via lightweight endpoint."""
        # Delegates to subclass implementation
        return await self._lightweight_health_check()
    
    async def _lightweight_health_check(self) -> bool:
        """Subclass must implement lightweight health check."""
        raise NotImplementedError
    
    async def list_models(self) -> List[str]:
        """List available models (already exists)."""
        raise NotImplementedError
```

#### Step 2: Implement per-provider lightweight health checks

**AnthropicClient:**
```python
async def _lightweight_health_check(self) -> bool:
    """Check health via models listing or OPTIONS request."""
    try:
        # Try models endpoint if available
        async with aiohttp.ClientSession() as session:
            headers = {"x-api-key": self.api_key}
            # Use OPTIONS to check connection without inference
            async with session.options(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=3.0),
            ) as resp:
                return resp.status in (200, 401, 405)  # 401/405 ok, means API reachable
    except Exception:
        return False
```

**OpenAIClient:**
```python
async def _lightweight_health_check(self) -> bool:
    """Check health via /models endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with session.get(
                "https://api.openai.com/v1/models",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=3.0),
            ) as resp:
                return resp.status == 200
    except Exception:
        return False
```

**GoogleClient:**
```python
async def _lightweight_health_check(self) -> bool:
    """Check health via /models endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": self.api_key},
                timeout=aiohttp.ClientTimeout(total=3.0),
            ) as resp:
                return resp.status == 200
    except Exception:
        return False
```

**CohereClient:**
```python
async def _lightweight_health_check(self) -> bool:
    """Check health via HEAD request."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with session.head(
                "https://api.cohere.ai/v2/chat",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=3.0),
            ) as resp:
                return resp.status in (200, 400)  # 400 ok, means API reachable
    except Exception:
        return False
```

**MistralClient:**
```python
async def _lightweight_health_check(self) -> bool:
    """Check health via /models endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with session.get(
                "https://api.mistral.ai/v1/models",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=3.0),
            ) as resp:
                return resp.status == 200
    except Exception:
        return False
```

**LocalProviderClient:**
```python
async def _lightweight_health_check(self) -> bool:
    """Check health via /models endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://127.0.0.1:11434/api/v1/models",
                timeout=aiohttp.ClientTimeout(total=3.0),
            ) as resp:
                return resp.status == 200
    except Exception:
        return False
```

### Phase 4b: Performance Improvements

#### Caching Strategy
```python
class ProviderHealth:
    """Enhanced health tracking."""
    provider_id: str
    is_healthy: bool
    last_check: datetime
    check_duration_ms: float  # NEW: Track latency
    error_message: Optional[str] = None
    consecutive_failures: int = 0
    cache_ttl_seconds: int = 5  # Configurable per provider
```

#### Parallel Health Checks
```python
async def health_check_all(self) -> Dict[str, bool]:
    """Check all providers in parallel."""
    tasks = [
        self.health_check(provider_id)
        for provider_id in self._configs
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return dict(zip(self._configs.keys(), results))
```

### Phase 4c: Monitoring & Metrics

#### Health Check Metrics
```python
{
    "health_checks": {
        "anthropic": {
            "is_healthy": True,
            "check_duration_ms": 45.2,
            "consecutive_failures": 0,
            "last_check": "2026-04-25T10:35:00Z",
        },
        "openai": {
            "is_healthy": True,
            "check_duration_ms": 62.8,
            "consecutive_failures": 0,
            "last_check": "2026-04-25T10:35:01Z",
        },
        ...
    }
}
```

#### Logging
```python
[REGISTRY] Health check completed in 125ms
  ├─ local: HEALTHY (22ms)
  ├─ anthropic: HEALTHY (45ms)
  ├─ openai: HEALTHY (63ms)
  ├─ google: UNHEALTHY (timeout)
  ├─ cohere: HEALTHY (51ms)
  └─ mistral: HEALTHY (58ms)
```

---

## Benefits

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Health Check Latency** | 500-2000ms | 50-200ms | 5-10x faster |
| **API Quota Usage** | 1 inference per check | 0 | Free |
| **Cost per Check** | $0.001-0.015 | $0 | 100% savings |
| **Fallback Chain Speed** | 3-5 seconds | 500-1000ms | 3-10x faster |
| **Provider Availability** | Accurate via inference | Accurate via endpoint | Same accuracy |

---

## Testing Strategy

### Unit Tests
- Mock HTTP responses from health endpoints
- Test timeout handling
- Test authentication failures
- Test malformed responses

### Integration Tests
- Real health checks against real API endpoints
- Verify endpoint availability
- Measure actual latencies
- Test cache TTL behavior

### Performance Tests
- Benchmark health check latency
- Compare before/after health check times
- Measure fallback chain building time
- Verify API quota savings

---

## Rollout Plan

### Phase 4a-1: LocalProviderClient
- Update Ollama health check
- Test with running Ollama instance
- Measure latency improvement

### Phase 4a-2: Cloud Providers
- Update each cloud provider in sequence
- Test with real API keys
- Verify endpoint availability

### Phase 4a-3: Registry Integration
- Update registry health check caching
- Implement parallel health checks
- Add metrics collection

### Phase 4b: Performance Optimization
- Implement request batching for health checks
- Add health check scheduling (spread across time)
- Optimize cache TTL per provider

### Phase 4c: Monitoring
- Add health check metrics to queue status endpoint
- Create health dashboard view
- Add alerting for degraded providers

---

## Known Limitations

### Provider Endpoints
- Not all providers document their lightweight endpoints
- Some providers may not have model listing endpoints
- Authentication checks (OPTIONS/HEAD) may differ by API version

### Fallback Strategy
- Some providers might return 200 but API is actually down
- Network latency affects health accuracy
- DNS failures not detected by lightweight checks

### Future Enhancements
- Implement more sophisticated health checks (e.g., probe with cached model list)
- Add health check retry logic
- Implement health check pooling (run once, use for all checks)
- Add custom health check per provider

---

## Code Changes Summary

| File | Change | Lines |
|------|--------|-------|
| `provider_client.py` | Add `_lightweight_health_check()` to ABC | +10 |
| `local_client.py` | Implement lightweight health check | +15 |
| `provider_clients_cloud.py` | Implement 5 lightweight health checks | +100 |
| `test_health_checks.py` | New comprehensive health check tests | +200 |

---

## Success Criteria

- ✅ All 6 providers have lightweight health checks
- ✅ Health check latency < 200ms (avg)
- ✅ Zero inference quota usage for health checks
- ✅ 100% API endpoint availability
- ✅ Fallback chain building < 1 second (was 3-5s)
- ✅ All health check tests passing
- ✅ Metrics visible in queue status endpoint

---

**Phase 4a Status:** Ready for implementation  
**Estimated completion:** 2-3 hours  
**Next phase:** Request queuing & load balancing
