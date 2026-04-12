# Inference Router Integration — COMPLETE

> Historical note: this file is retained as milestone archive context. Current living docs are `README.md` and `ROADMAP.md`.

## Summary

Successfully integrated the **Inference Router** into Guppy. All API requests now route through a priority-based inference system with automatic fallbacks.

## Priority Chain

```
REQUEST
   ↓
[LOCAL] Try guppy model via Ollama
   • Free (no API cost)
   • Fast (~100-150 tokens/sec)
   • Timeout: 30 seconds
   ↓ (on timeout/failure)
[HAIKU] Try Claude Haiku
   • Low cost (~$0.80 per million input tokens)
   • Fast (~1-3 seconds network latency)
   ↓ (on failure)
[SONNET] Try Claude Sonnet
   • Medium cost (~$3 per million input tokens)
   • Highest reasoning capability
   ↓ (on failure)
[ERROR] Return error to user
```

## Files Created

### 1. `inference_router.py` (Main Module)
- **Location**: `C:\Users\Ryan\guppy\inference_router.py`
- **Size**: ~450 lines
- **Exports**: `InferenceRouter` class, `get_router()` function, `route_inference()` convenience function
- **Features**:
  - Query local model via Ollama API
  - Query Claude Haiku as secondary fallback
  - Query Claude Sonnet as last resort
  - Automatic timeout and error handling
  - Metadata tracking (tokens, source, timestamp)

### 2. `apply_router_integration.py` (Integration Script)
- **Location**: `C:\Users\Ryan\guppy\apply_router_integration.py`
- **Purpose**: Applied patches to `guppy_api.py`
- **Already Executed**: Yes ✓

### 3. Documentation Files
- `INFERENCE_ROUTER_INTEGRATION_COMPLETE.md` (this file)
- `INFERENCE_STRATEGY.md` (strategy and configuration)
- `INTEGRATION_PATCH.py` (reference implementation)

## Changes to guppy_api.py

### Import Added
```python
try:
    from inference_router import get_router
    INFERENCE_ROUTER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Inference router not available: {e}")
    INFERENCE_ROUTER_AVAILABLE = False
```

### New Function Added
```python
def _call_unified_inference(user_text: str, system_prompt: str) -> str:
    """
    NEW: Unified inference using intelligent router.
    Priority: local (guppy) -> haiku -> sonnet
    Automatically falls back if local model is unavailable.
    """
    # Uses InferenceRouter to handle fallback logic
```

### /chat Endpoint Updated
The `/chat` endpoint now uses `_call_unified_inference()` when the router is available, falling back to the old method only if needed.

```python
# Use unified inference router (local -> haiku -> sonnet)
if INFERENCE_ROUTER_AVAILABLE:
    response = await _run_blocking(
        _call_unified_inference,
        request.message,
        system_prompt,
        timeout_seconds=CHAT_TIMEOUT_SECONDS,
    )
else:
    # Fallback to old method
    ...
```

## Backup

Original file backed up: `guppy_api.py.backup`

You can restore with:
```powershell
Copy-Item "C:\Users\Ryan\guppy\guppy_api.py.backup" "C:\Users\Ryan\guppy\guppy_api.py" -Force
```

## Testing the Integration

### 1. Start Ollama
```powershell
# Ollama is already running or start with:
& "C:\Users\Ryan\AppData\Local\Ollama\start_ollama.bat"
```

### 2. Query via API
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is 2+2?",
    "session_id": "test-123",
    "use_claude": false
  }'
```

### 3. Watch Logs
The router logs will show:
```
[LOCAL] Querying guppy model via Ollama...
[LOCAL] ✓ Success
```

Or on fallback:
```
[LOCAL] Timeout (30s). Falling back.
[HAIKU] Querying Claude Haiku...
[HAIKU] ✓ Success. Tokens: 245
```

## Configuration

### Timeout
**File**: `C:\Users\Ryan\guppy\inference_router.py`
**Line**: `OLLAMA_TIMEOUT = 30`

Change to adjust how long to wait for local model before falling back.

### Model Names
**File**: `C:\Users\Ryan\guppy\inference_router.py`
**Lines**: 23-27

```python
OLLAMA_API = "http://127.0.0.1:11434/api/chat"
OLLAMA_TIMEOUT = 30
LOCAL_MODEL = "guppy"
HAIKU_MODEL = "claude-3-5-haiku-20241022"
SONNET_MODEL = "claude-3-5-sonnet-20241022"
```

## Behavior Changes

### Before Integration
- `/chat?use_claude=true` → Always use Claude (cloud)
- `/chat?use_claude=false` → Always use Ollama (local, fail if down)

### After Integration
- `/chat` → Try local guppy → Try Haiku → Try Sonnet (always succeeds unless all fail)
- `use_claude` flag is now ignored (router handles it automatically)
- No user-facing downtime if local model is unavailable

## Cost Impact

### Scenario Analysis

**100% Local** (perfect Ollama uptime)
- Monthly cost: $0
- Inference speed: ~100-150 tokens/sec
- Availability: Depends on hardware

**Local + Haiku fallback** (typical)
- ~80% local, ~20% Haiku
- Monthly cost: ~$30-50 (for 20% fallback usage)
- Inference speed: ~80-150 tokens/sec
- Availability: 99%+ (Haiku is very reliable)

**Local + Sonnet fallback** (conservative)
- ~80% local, ~20% Sonnet
- Monthly cost: ~$100-150 (for 20% fallback usage)
- Inference speed: ~50-150 tokens/sec (mixed)
- Availability: 99.9%+

**Default (Local + Haiku)**: Best cost/reliability balance

## Monitoring

### Log File
All router activity logs to the same logger as guppy_api.py. Check logs for:
- Which model was used
- Why fallbacks occurred
- Response times and token counts

### Example Log Output
```
======================================================================
INFERENCE ROUTER | Primary: local
======================================================================
[LOCAL] Querying guppy model via Ollama...
[LOCAL] ✓ Success
Inference completed via local. Metadata: {...}
```

### Status Endpoint
The `/status` endpoint will report router availability:
```json
{
  "status": "ok",
  "inference_router": "ready (current primary: local)",
  "guppy_core": "available"
}
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  guppy_ui.py (GUI) / guppy_api.py (API)            │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────▼──────────────┐
        │ _call_unified_inference() │ (new function)
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────────┐
        │    InferenceRouter            │ (new module)
        │  (inference_router.py)        │
        └────┬───────────────┬─────┬────┘
             │               │     │
      ┌──────▼──┐  ┌────────▼──┐ ┌▼──────────┐
      │ Ollama  │  │   Haiku   │ │  Sonnet   │
      │ (local) │  │  (cloud)  │ │  (cloud)  │
      └─────────┘  └───────────┘ └───────────┘
```

## Next Steps

### 1. Test in Production
- Deploy updated `guppy_api.py`
- Monitor fallback frequency (logs will show)
- Verify no user-facing errors

### 2. Monitor Fallback Rate
- If local model rarely times out, cost is minimal
- If frequent timeouts, consider increasing `OLLAMA_TIMEOUT`
- If cost is high, adjust model preferences (prefer Haiku over Sonnet)

### 3. Optional: Integrate into guppy_ui.py
The GUI (guppy_ui.py) can also use the router:
```python
from inference_router import get_router
router = get_router()
response, source, metadata = router.query(system_prompt, user_text, tools)
```

## Status

✅ **IMPLEMENTATION COMPLETE**

- [x] Created `inference_router.py` with priority chain
- [x] Updated `guppy_api.py` with router integration
- [x] Added `_call_unified_inference()` function
- [x] Fallback chain: local → haiku → sonnet
- [x] Automatic timeout handling (30 seconds)
- [x] Metadata tracking (source, tokens, timing)
- [x] Backup created (`guppy_api.py.backup`)
- [x] Documentation complete

**Ready for deployment.**

## Rollback

If needed, restore the original:
```powershell
Copy-Item "C:\Users\Ryan\guppy\guppy_api.py.backup" "C:\Users\Ryan\guppy\guppy_api.py" -Force
```

Then delete or rename `inference_router.py` to disable it.

---

**Created**: 2026-04-12 02:55 AM  
**Integrated by**: Guppy Integration Assistant  
**Status**: ACTIVE
