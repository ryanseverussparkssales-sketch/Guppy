# API Endpoint Fix: Web UI Authentication Issue (2026-04-22)

## Problem Identified

**Symptom:** Web UI (React on localhost:3000) unable to call API endpoints, returning 401 Unauthorized errors.

**Root Cause:** API authentication (`require_rate_limit` dependency) was rejecting all requests that didn't include a Bearer token. The Web UI wasn't sending authentication headers because it's running locally in dev mode.

**Error Flow:**
```
Web UI calls: GET /api/workspaces (no Authorization header)
      ↓
FastAPI calls: require_rate_limit() dependency
      ↓
Dependency calls: _verify_token_credentials(credentials=None)
      ↓
Function checks: if not credentials → raise HTTPException(401)
      ↓
Result: 401 Unauthorized
```

## Files Affected

- **`src/guppy/api/auth.py`** — Authentication middleware

## Changes Made

### Modified: `src/guppy/api/auth.py` (lines 97-106)

**Before:**
```python
if not credentials:
    raise HTTPException(
        status_code=401,
        detail={"code": "auth_missing_bearer", "message": "Authentication required"},
        headers={"WWW-Authenticate": "Bearer"}
    )
```

**After:**
```python
if not credentials:
    # In dev mode, allow unauthenticated access for local testing
    if DEV_MODE:
        logger.info("Dev mode: allowing unauthenticated API request")
        return "dev-user"
    raise HTTPException(
        status_code=401,
        detail={"code": "auth_missing_bearer", "message": "Authentication required"},
        headers={"WWW-Authenticate": "Bearer"}
    )
```

**Why:** When `GUPPY_DEV_MODE=1` is set (which the launcher scripts do), the auth system now allows unauthenticated requests for local testing. This enables:
- Web UI to call API without bearer tokens
- Local development testing without credentials
- Normal production mode still requires authentication

## Verification Steps

### Step 1: Ensure API Is Running with Dev Mode

The launcher scripts (`launch_api_dev.bat`, `launch_web_ui.bat`) should automatically set `GUPPY_DEV_MODE=1`. Verify in the API startup logs:

```
INFO:src.guppy.api.auth:Dev mode: allowing unauthenticated API request
```

Or check PowerShell:
```powershell
$env:GUPPY_DEV_MODE=1
python -m src.guppy.cli.launch api
```

### Step 2: Test Endpoints with curl

Once API is running on `http://127.0.0.1:8081`:

```powershell
# Test without authentication (should now work in dev mode)
curl http://127.0.0.1:8081/api/workspaces

# Test model listing
curl http://127.0.0.1:8081/api/models

# Test settings
curl http://127.0.0.1:8081/api/settings
```

**Expected Results (Dev Mode):**
- `200 OK` with JSON response (not 401)
- Log shows: `Dev mode: allowing unauthenticated API request`

### Step 3: Test from Web UI

1. Start API: `launch_api_dev.bat`
2. Start Web UI: `npm run dev` (in `web/` directory)
3. Open http://localhost:3000
4. Check browser console (F12 → Console tab)
5. Check Network tab for API calls:
   - Should see `GET /api/workspaces` with status `200` (not 401)
   - Should see `GET /api/models` with status `200`
   - Should see `GET /api/settings` with status `200`

## Architecture Notes

### Dev Mode Bypass

The `GUPPY_DEV_MODE=1` environment variable controls several dev-friendly behaviors:
- **Turnstile auth:** Skipped (Cloudflare token validation)
- **Rate limiting:** Applied per-IP, but localhost requests bypass limits
- **Bearer token requirement:** Skipped (allows unauthenticated local requests)
- **Logging:** Verbose logging enabled

### Route Registration Verification (Already Done ✅)

Routes are properly registered in `server_runtime.py`:
```python
# Lines 277-279: Imports
from src.guppy.api.routes_workspaces import build_workspaces_router
from src.guppy.api.routes_chat_history import build_chat_history_router
from src.guppy.api.routes_settings import build_settings_router

# Lines 455-457: Registration
app.include_router(build_workspaces_router(_server_context))
app.include_router(build_chat_history_router(_server_context))
app.include_router(build_settings_router(_server_context))
```

Each router defines its own `/api/` prefix:
- `routes_models.py`: `APIRouter(prefix="/api/models")`
- `routes_workspaces.py`: `APIRouter(prefix="/api/workspaces")`
- `routes_chat_history.py`: `APIRouter(prefix="/api/chat/...")`
- `routes_settings.py`: `APIRouter(prefix="/api/settings")`

### Web UI vs Desktop UI Architectures

| Aspect | Desktop UI (Qt) | Web UI (React) |
|--------|-----------------|----------------|
| **Location** | `src/guppy/apps/launcher_app.py` | `web/src/` (npm project) |
| **Communication** | Direct Python calls to services | REST API calls to `/api/*` endpoints |
| **Auth** | N/A (same process) | Requires Bearer token OR dev mode bypass |
| **Port** | N/A (no HTTP) | localhost:3000 (React dev server) |
| **API Dependency** | Not required | Required for all data |

## What's Now Fixed

✅ API allows unauthenticated requests in dev mode  
✅ Web UI can call `/api/workspaces`, `/api/models`, `/api/settings` without auth headers  
✅ Both UI systems can function independently  
✅ Production mode still enforces authentication  

## What Still Needs Testing

- [ ] Web UI successfully loads model dropdown (was previously blank)
- [ ] Web UI successfully loads workspace list (was previously blank)
- [ ] Web UI successfully loads chat history
- [ ] Web UI successfully loads settings
- [ ] Model selection/switching works via dropdown
- [ ] Workspace creation/switching works
- [ ] Chat persistence works (messages saved/restored)
- [ ] Settings save/load works (credentials stored)

## Next Steps

1. **Restart API server** with the fix in place (GUPPY_DEV_MODE=1)
2. **Open Web UI** (localhost:3000)
3. **Check browser console** for any remaining errors
4. **Test each P0 feature:**
   - Model selection → should see list from `/api/models`
   - Workspace management → should see list from `/api/workspaces`
   - Chat persistence → verify messages save/restore
   - Settings → verify credentials can be stored

5. **Document any remaining issues** for further investigation

---

**Status:** ✅ Critical fix applied. Ready for testing.
