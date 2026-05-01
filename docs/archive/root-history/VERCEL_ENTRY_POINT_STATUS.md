# Vercel Entry Point Status — 2026-04-23

## Configuration Analysis

### ✅ Build Configuration
**vercel.json:**
```json
{
  "buildCommand": "cd web && npm install && npm run build",
  "outputDirectory": "static",
  "framework": "vite"
}
```

**web/vite.config.ts:**
```typescript
build: {
  outDir: '../static',    // ✅ Matches vercel.json
  emptyOutDir: true,
  rollupOptions: {
    input: 'index.html',
  },
}
```

**Status:** ✅ Web build configured correctly

---

### ✅ API Entry Point Configuration
**vercel.json:**
```json
{
  "builds": [
    {
      "src": "api/index.py",           // ✅ Entry point exists
      "use": "@vercel/python",
      "config": {
        "runtime": "python3.12"
      }
    }
  ]
}
```

**api/index.py:**
```python
from api.app import app  # ✅ Exports FastAPI app
```

**api/app.py:**
```python
app = FastAPI(...)       # ✅ Creates and exports app
```

**Status:** ✅ Python entry point structure correct

---

### ✅ Route Configuration
**vercel.json:**
```json
{
  "routes": [
    {
      "src": "/api/(.*)",              // API requests → Python handler
      "dest": "/api/index.py"
    },
    {
      "src": "/(.*)",                  // Everything else → static files
      "dest": "/$1"
    }
  ]
}
```

**Status:** ✅ Routing configured correctly

---

### ✅ Dependencies
**api/requirements.txt:**
- fastapi ✅
- httpx ✅
- python-jose[cryptography] ✅
- openai ✅
- anthropic ✅

**Root requirements.txt:**
- All dependencies present ✅

**Status:** ✅ All FastAPI dependencies available

---

## What Could Be Broken

### Hypothesis 1: Deployment Not Running
- Check Vercel project logs for build failures
- Verify `npm run build` completes successfully in web/
- Check if `static/` directory is generated post-build

### Hypothesis 2: Import Path Issue
- `api/index.py` imports `from api.app import app`
- This assumes `/api` is in PYTHONPATH
- Vercel's Python runtime should handle this automatically

### Hypothesis 3: Environment Variables
- API requires environment variables for providers:
  - `OPENAI_API_KEY` (if using OpenAI)
  - `ANTHROPIC_API_KEY` (if using Anthropic)
  - `GUPPY_CORS_ORIGINS` (for CORS)
- These need to be set in Vercel project settings

### Hypothesis 4: Module Not Found at Runtime
- If Vercel build succeeds but runtime fails:
  - API routes may not be finding imports
  - Check api/routes imports (auth_token, chat, etc.)

---

## What's Actually Needed

To validate the entry point is correct, run:

```bash
# 1. Activate venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# 2. Install API dependencies
pip install -r api/requirements.txt

# 3. Test import
python -c "from api.index import app; print(f'App loaded: {app}')"

# 4. Test locally with Vercel CLI
npm install -g vercel
vercel dev

# 5. Or run directly with uvicorn
cd api
uvicorn index:app --reload --port 8000
```

---

## Next Steps

**Tell me what error you're seeing:**
1. Is the Vercel build failing? (share build log)
2. Is the deployment failing at runtime? (share runtime error)
3. Are the API endpoints unreachable? (test with `curl http://localhost:3000/api/health`)
4. Is there a specific 404 or 500 error?

Once you clarify what's broken, I can fix it.
