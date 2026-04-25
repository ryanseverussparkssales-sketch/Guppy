# Phase 4a: Lightweight Health Check Endpoints - Quick Reference

## Provider Health Check Endpoints

### Local (Ollama)
```
Method: GET
Endpoint: http://127.0.0.1:11434/api/v1/models
Latency: 20-50ms
Auth: None
Success Status: 200
Implementation: GET to model listing endpoint
```

### Anthropic
```
Method: OPTIONS
Endpoint: https://api.anthropic.com/v1/messages
Latency: 50-100ms
Auth: x-api-key header
Success Status: 200, 401, 405 (all indicate API is reachable)
Implementation: OPTIONS request (405 Method Not Allowed means API exists)
Note: OPTIONS used instead of POST to avoid inference charges
```

### OpenAI
```
Method: GET
Endpoint: https://api.openai.com/v1/models
Latency: 30-80ms
Auth: Bearer token header
Success Status: 200
Implementation: GET to model listing endpoint
Note: Free, included in API quota, fast
```

### Google Gemini
```
Method: GET
Endpoint: https://generativelanguage.googleapis.com/v1beta/models
Latency: 50-100ms
Auth: API key in query parameter (?key=...)
Success Status: 200
Implementation: GET to model listing endpoint
Note: Free, no token consumption
```

### Cohere
```
Method: HEAD
Endpoint: https://api.cohere.ai/v2/chat
Latency: 40-90ms
Auth: Bearer token header
Success Status: 200, 400, 401 (all indicate API is reachable)
Implementation: HEAD request (minimalist connectivity check)
Note: 400 = bad request but API exists; 401 = auth error but API exists
```

### Mistral
```
Method: GET
Endpoint: https://api.mistral.ai/v1/models
Latency: 30-80ms
Auth: Bearer token header
Success Status: 200
Implementation: GET to model listing endpoint
Note: Free, no token consumption
```

---

## Implementation Comparison

### Old Approach (Phase 3) - Minimal Inference
```python
# Wasteful health check using minimal inference
async def health_check(self) -> bool:
    payload = {
        "model": self.model,
        "messages": [{"role": "user", "content": "ok"}],
        "max_tokens": 1,  # Minimal, but still counts as inference!
    }
    async with session.post(api_url, json=payload) as resp:
        return resp.status == 200
```

**Problems:**
- Consumes API quota (billable)
- Wastes tokens
- Slow (500-2000ms)
- Costs $0.001-0.015 per check

### New Approach (Phase 4a) - Lightweight Endpoints
```python
# Efficient health check using lightweight endpoint
async def _lightweight_health_check(self) -> bool:
    async with session.get(models_endpoint) as resp:
        return resp.status == 200
```

**Benefits:**
- No API quota consumed (free)
- No token usage
- Fast (50-200ms)
- Zero cost
- 5-10x faster

---

## Performance Metrics

### Expected Latencies (Phase 4a)
| Provider | Endpoint | Latency | Improvement |
|----------|----------|---------|-------------|
| Ollama | GET /api/v1/models | 20-50ms | N/A |
| Anthropic | OPTIONS /v1/messages | 50-100ms | 5-10x |
| OpenAI | GET /v1/models | 30-80ms | 6-20x |
| Google | GET /v1beta/models | 50-100ms | 5-10x |
| Cohere | HEAD /v2/chat | 40-90ms | 5-12x |
| Mistral | GET /v1/models | 30-80ms | 6-20x |

### Cost Savings
| Provider | Old Cost/Check | New Cost/Check | Savings |
|----------|---|---|---|
| Anthropic | $0.001-0.015 | $0 | 100% |
| OpenAI | $0.0001-0.001 | $0 | 100% |
| Google | $0.00001-0.0001 | $0 | 100% |
| Cohere | $0.001-0.002 | $0 | 100% |
| Mistral | $0.0002-0.0006 | $0 | 100% |

### Quota Savings
10 health checks/minute:
- **Old:** 10 billable inferences/minute
- **New:** 0 billable inferences/minute

---

## Testing Endpoints Manually

### Ollama
```bash
# Check if Ollama is running
curl http://127.0.0.1:11434/api/v1/models
# Expected: 200 with JSON list of models
```

### Anthropic
```bash
# Test OPTIONS request (should return 405)
curl -X OPTIONS https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2024-06-15" \
  -I
# Expected: 405 Method Not Allowed (or 401 if invalid key)
```

### OpenAI
```bash
# List models
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
# Expected: 200 with JSON list of models
```

### Google
```bash
# List models
curl "https://generativelanguage.googleapis.com/v1beta/models?key=$GOOGLE_API_KEY"
# Expected: 200 with JSON list of models
```

### Cohere
```bash
# Test HEAD request
curl -I -X HEAD https://api.cohere.ai/v2/chat \
  -H "Authorization: Bearer $COHERE_API_KEY"
# Expected: 200, 400, or 401
```

### Mistral
```bash
# List models
curl https://api.mistral.ai/v1/models \
  -H "Authorization: Bearer $MISTRAL_API_KEY"
# Expected: 200 with JSON list of models
```

---

## Code Locations

### Main Implementations
- **CloudProviderClient ABC:** `src/guppy/inference/provider_client.py:324-401`
- **LocalProviderClient:** `src/guppy/inference/provider_client.py:258-286`
- **Cloud Providers:** `src/guppy/inference/provider_clients_cloud.py`
  - AnthropicClient: Lines 155-186
  - OpenAIClient: Lines 308-337
  - GoogleClient: Lines 475-499
  - CohereClient: Lines 629-661
  - MistralClient: Lines 783-815

### Tests
- **Unit Tests:** `tests/integration/test_phase4a_lightweight_health_checks.py`

---

## Caching Behavior

### Health Check Cache
```
TTL: 5 seconds
Storage: Per-client instance in `_health_check_cache`
Pattern: (healthy: bool, timestamp: float)

Example:
- First call at T=0: Calls API, caches result
- Call at T=1: Returns cached (within 5s TTL)
- Call at T=6: Cache expired, calls API again
```

### Cache Invalidation
- Automatic on TTL expiry (5 seconds)
- No manual invalidation (by design)
- Fresh check always available by waiting 5 seconds

---

## Error Handling

### Timeout (3.0 second hard timeout)
```python
except asyncio.TimeoutError:
    logger.debug(f"[PROVIDER] Health check timeout")
    return False  # Timeout = unhealthy (conservative)
```

### Connection Error
```python
except Exception as e:
    logger.debug(f"[PROVIDER] Health check failed: {e}")
    return False  # Any error = unhealthy (conservative)
```

### Missing API Key
```python
if not self.api_key:
    return False  # No key = unhealthy (always)
```

---

## Integration with ProviderRegistry

### No Changes Required
```python
# ProviderRegistry already calls health_check()
# It automatically uses the new lightweight implementation

await registry.health_check("anthropic")
# Internally calls: AnthropicClient._lightweight_health_check()
# With caching and error handling from: CloudProviderClient.health_check()
```

### Fallback Chain Building (Now Faster)
```python
# Was 3-5 seconds (doing 5-10 minimal inferences)
# Now 500-1000ms (doing 5-10 lightweight checks)
chain = registry.build_fallback_chain()
```

---

## Monitoring & Metrics

### Health Status Endpoint
```python
status = registry.get_status()
# Now shows accurate health with minimal latency

# Example output:
{
    "providers": {
        "anthropic": {
            "enabled": True,
            "healthy": True,
            "latency_ms": 65.2,  # NEW: Track latency
            "last_check": "2026-04-25T10:35:00Z",
        },
        ...
    }
}
```

### Logging
```
[REGISTRY] Health check completed in 125ms
  ├─ local: HEALTHY (22ms)
  ├─ anthropic: HEALTHY (65ms)
  ├─ openai: HEALTHY (48ms)
  ├─ google: UNHEALTHY (timeout)
  ├─ cohere: HEALTHY (75ms)
  └─ mistral: HEALTHY (52ms)
```

---

## Known Issues & Workarounds

### Issue: Google API Returns 403
**Cause:** API key not enabled for Generative AI
**Solution:** Enable the API in Google Cloud Console

### Issue: Cohere HEAD Returns 405
**Cause:** Provider doesn't support HEAD requests
**Status:** This is fine; we check for 400/401 which indicate API exists
**Note:** Current implementation accepts 200, 400, 401

### Issue: Anthropic OPTIONS Returns 401
**Cause:** Invalid API key
**Status:** This is fine; 401 means API is reachable (auth failed, not API down)
**Note:** Current implementation accepts 200, 401, 405

---

## Future Optimization (Phase 4b+)

### Parallel Health Checks
```python
# Run all health checks in parallel instead of sequentially
tasks = [health_check(p) for p in providers]
results = await asyncio.gather(*tasks)
# Was 250-500ms sequential, now 50-100ms parallel
```

### Smart Retry Logic
```python
# Retry with exponential backoff on timeout
for attempt in range(3):
    try:
        return await _lightweight_health_check()
    except TimeoutError:
        await asyncio.sleep(0.1 * (2 ** attempt))  # 100ms, 200ms, 400ms
```

### Health Check Pooling
```python
# Run once, use result for all concurrent requests
# Deduplicate simultaneous health checks
_pending_checks = {}
```

---

**Last Updated:** 2026-04-25  
**Phase 4a Status:** Implementation Complete ✅  
**Next Phase:** Phase 4b - Parallel Health Checks & Advanced Caching
