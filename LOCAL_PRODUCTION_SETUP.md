# Guppy Local Production Setup

## Overview

This document describes the **local, fully-powered version** of Guppy that runs on your machine, and how it can be reduced for actual production deployment.

---

## Quick Start (Local Version)

```powershell
# One command to build and launch everything
pwsh -ExecutionPolicy Bypass -File build_and_launch.ps1
```

That's it. This will:
1. ✅ Build the web UI to static files
2. ✅ Start the backend API (port 8081)
3. ✅ Serve the built web UI (port 3003)
4. ✅ Open your browser
5. ✅ Keep everything running

---

## Architecture: Local Version

```
┌─────────────────────────────────────────────────────┐
│           Your Browser (http://127.0.0.1:3003)      │
│                                                     │
│  Guppy Web UI (built React app)                    │
│  - Full-featured chat interface                    │
│  - Settings & workspaces                           │
│  - All features enabled                            │
└────────────────┬────────────────────────────────────┘
                 │ API Calls
                 ▼
┌─────────────────────────────────────────────────────┐
│        Guppy Backend API (port 8081)                │
│                                                     │
│  - Chat endpoints (/api/chat)                       │
│  - Settings (/api/settings)                         │
│  - Workspaces (/api/workspaces)                     │
│  - Model management (/api/models)                   │
│  - All local Ollama models (guppy-fast, etc.)       │
└────────────────┬────────────────────────────────────┘
                 │ Model Inference
                 ▼
         ┌───────────────┐
         │   Ollama      │
         │   Running:    │
         │   - qwen2.5   │
         │   - guppy-*   │
         │   - Others    │
         └───────────────┘
```

**Key Point:** Everything runs locally. No external APIs, no cloud calls, no latency.

---

## File Structure: Local Version

```
guppy/
├── src/guppy/api/              ← Backend API (Flask/FastAPI)
│   ├── server.py               ← Main server
│   ├── routes_chat.py          ← Chat endpoints
│   └── ...
│
├── web/                         ← Frontend React app
│   ├── src/                    ← React source code
│   │   ├── store/              ← State management
│   │   ├── components/         ← UI components
│   │   ├── views/              ← Pages
│   │   └── ...
│   │
│   ├── dist/                   ← BUILT web UI (static files)
│   │   ├── index.html          ← Single HTML entry point
│   │   ├── assets/             ← JS, CSS bundles
│   │   └── ...
│   │
│   ├── package.json            ← npm dependencies
│   └── vite.config.ts          ← Build configuration
│
├── build_and_launch.ps1        ← Run this ONE TIME to start everything
└── launch_guppy_complete.bat   ← Alternative Windows batch launcher
```

---

## How to Reduce for Production

When you're ready to deploy to production, here's what to reduce:

### Phase 1: Remove Dev Dependencies
```powershell
# Current (Local): Full React dev dependencies
# npm install   # 500+ MB

# Production: Minified, optimized build only
npm run build --prod   # Outputs ~500 KB in dist/
```

### Phase 2: Simplify Backend
```python
# Current (Local): Full Guppy features
# - All models available
# - All endpoints
# - Full logging
# - Development auth bypass (GUPPY_DEV_MODE)

# Production: Reduced to core
# - Select models only (e.g., just guppy-fast + guppy-code)
# - Core endpoints only (/chat, /status)
# - Minimal logging
# - Strict JWT auth
# - Rate limiting enforced
```

### Phase 3: Deployment Options

#### Option A: Docker (Recommended)
```dockerfile
# Single container with both frontend + backend
# - Backend serves built UI at /
# - API at /api/*
# - No need for separate Node/Python on prod machine
```

#### Option B: Cloud (AWS/GCP/Azure)
```
- Frontend: Static hosting (S3, Cloud Storage, etc.)
- Backend: Serverless (Lambda, Cloud Run, etc.)
- Database: Managed (RDS, Firestore, etc.)
```

#### Option C: Single Binary
```
- PyInstaller bundle that includes:
  - Python interpreter
  - Built web UI (in assets/)
  - All dependencies
- User runs one .exe on Windows
```

---

## Current Commands (Local)

### Build Only
```powershell
pwsh -ExecutionPolicy Bypass -File build_and_launch.ps1 -BuildOnly
```
Output: `web/dist/` folder with production-ready HTML/JS/CSS

### API Only (Manual Mode)
```powershell
python -m guppy.cli.launch api
```
Then separately: `cd web && npm run dev`

### Verify Everything Works
```powershell
pwsh -ExecutionPolicy Bypass -File verify_guppy_setup.ps1
```

---

## Key Design Decisions: Local Version

| Aspect | Local Version | Why |
|--------|---------------|-----|
| **Models** | All available (qwen2.5, guppy-*, etc.) | Maximum capability |
| **Frontend** | Full React dev tools | Easy to iterate |
| **Auth** | Dev mode allowed (`GUPPY_DEV_MODE=1`) | No authentication overhead |
| **Logging** | Verbose, detailed | Debugging support |
| **Features** | All enabled | Nothing hidden |
| **Ports** | 3003 (UI), 8081 (API) | Standard local ports |
| **Database** | SQLite (built-in) | Zero setup |

---

## Reducing Scope for Production

When ready to reduce for production, make these changes:

### Backend (src/guppy/api/)
1. **Remove dev endpoints** - Delete routes marked `@app.get("/dev/*")`
2. **Reduce models** - Edit `config/instances.json` to include only production models
3. **Enable strict auth** - Set `GUPPY_DEV_MODE=0`, enforce JWT validation
4. **Optimize logging** - Change log level from DEBUG to WARNING
5. **Add rate limiting** - Global and per-user limits

### Frontend (web/)
1. **Remove dev features** - Disable "Test" buttons, debug panels
2. **Simplify settings** - Hide advanced options, remove development toggles
3. **Optimize bundle** - Already done by `npm run build`
4. **Add analytics** - Track usage for production insights

### Deployment
1. **Serve built UI from backend** - Backend serves `web/dist/` at `/`
2. **Add HTTPS** - All production APIs require SSL
3. **Scale horizontally** - Run multiple backend instances
4. **Add monitoring** - Health checks, error tracking, performance monitoring

---

## Testing Locally

### Manual Testing Checklist
```
✅ Web UI loads without errors
✅ Can create new conversation
✅ Can send message and get response
✅ Error handling works (try offline mode)
✅ Settings page loads
✅ Model selection works
✅ Workspace switching works
```

### Automated Tests
```powershell
# Run test suite
python -m pytest tests/

# Smoke tests only
python -m pytest tests/smoke/

# Integration tests
python -m pytest tests/integration/
```

---

## Environment Variables

### Local Version (Development)
```powershell
set GUPPY_DEV_MODE=1
set GUPPY_JWT_SECRET=dev-secret-key
set VITE_API_URL=http://127.0.0.1:8081
set OLLAMA_BASE_URL=http://127.0.0.1:11434
```

### Production Version
```powershell
set GUPPY_DEV_MODE=0
set GUPPY_JWT_SECRET=<strong-random-key>
set VITE_API_URL=https://api.yourdomain.com
set OLLAMA_BASE_URL=http://local-ollama:11434
set LOG_LEVEL=WARNING
```

---

## Troubleshooting

### Port Already in Use
```powershell
# Find what's using port 3003
netstat -ano | findstr :3003

# Find what's using port 8081
netstat -ano | findstr :8081

# Kill the process (replace PID with actual number)
taskkill /PID <PID> /F
```

### API Not Responding
```powershell
# Check if Ollama is running
curl http://127.0.0.1:11434/api/tags

# Check if API started correctly
curl http://127.0.0.1:8081/

# View API logs
# Terminal where API was started should show error messages
```

### Build Fails
```powershell
# Clear Node cache
rm -r web/node_modules web/dist

# Reinstall
cd web
npm install
npm run build
```

---

## Next Steps

1. **Run it locally** - `build_and_launch.ps1`
2. **Use it** - Full-powered version on your machine
3. **When ready for production** - Follow "Reducing Scope" section
4. **Deploy** - Choose Docker, Cloud, or Single Binary option

---

**Status:** ✅ Ready for local use  
**Production Ready:** When you follow the reduction guide above  
**Questions:** Check CLAUDE.md in the repo root for architecture details
