# Web UI Diagnostic & Stabilization Plan

**Date:** 2026-04-22  
**Status:** CRITICAL ISSUES IDENTIFIED  
**Priority:** HIGH (blocks P6 web/desktop parity requirement)

---

## Issues Found

### 1. 🔴 CRITICAL: Vercel Deployment Missing Web UI Build

**Problem:** `vercel.json` only configures the Python API; web UI is not being built or served.

**Current config:**
```json
{
  "builds": [{ "src": "api/index.py", "use": "@vercel/python" }],
  "rewrites": [{ "source": "/(.*)", "destination": "/api/index.py" }]
}
```

**Issue:**
- Web UI TypeScript/React code is NOT being compiled during Vercel build
- All requests (including static files) are rewritten to `/api/index.py`
- When user loads the app, they get a 404 or API response (not HTML)
- Chat window is blank because the UI never loads

**Impact:** Web UI completely non-functional on Vercel

**Root cause:** Vercel config was never updated after web UI was added

---

### 2. 🔴 CRITICAL: API Client Hard-coded to localhost:8081

**Location:** `web/src/api/client.ts` line 4

```typescript
baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8081'
```

**Problem:**
- When deployed to Vercel, frontend tries to call `localhost:8081` (doesn't exist)
- Local dev works because vite proxy routes `/api` to `localhost:8081`
- Vercel production has no proxy, so requests fail silently
- No API connection = no models, tools, or chat responses

**Impact:** Chat is blank because API calls fail

**Root cause:** Environment variable `VITE_API_URL` not set during Vercel build

---

### 3. 🟡 HIGH: Environment Variable Not Set in Vercel Build

**Problem:** Build-time environment variables need to be configured in Vercel.

**What needs to happen:**
- Vercel project settings must have `VITE_API_URL` env var
- Should point to: `https://guppy.sparkscuriositystudio.com/api` (or your Vercel domain)
- Without this, build-time substitution fails; frontend defaults to localhost

**Impact:** Production API URL unknown to deployed frontend

---

### 4. 🟡 HIGH: Duplicate package.json Files

**Locations:**
- Root: `/package.json` (uses caret ^versioning)
- Web: `/web/package.json` (uses locked versions)

**Problem:**
- Both have same dependencies but different version constraints
- When installing root, some versions may differ from web
- Causes "works locally but breaks after venv reinstall"
- When you do `pip install -r requirements.txt` in root, web dependencies never get installed

**Impact:** Dependencies are inconsistent; reinstalling sometimes picks wrong versions

---

### 5. 🟡 HIGH: Venv Reinstall Doesn't Include Web Dependencies

**Problem:** When you run `pip install -r requirements.txt`, only Python packages are installed.

Web UI dependencies (node_modules/) are separate and require npm install.

**Symptoms:**
- You reinstall venv: web UI breaks
- You install Python requirements: web UI still broken (needs npm install too)
- Missing coordination between Python and Node dependency install

**Impact:** Users have to manually remember to run both `pip install` AND `npm install`

---

### 6. 🟡 MEDIUM: Build Output Directory Ambiguity

**Problem:** `vite.config.ts` specifies `outDir: '../static'`

But:
- No `static/` directory exists at root
- Unclear if this should be `/static/` or `/web/dist/`
- Vercel doesn't know where to find built UI files

**Impact:** Even if web UI builds, Vercel can't serve it

---

### 7. 🟡 MEDIUM: No Development Server Documentation

**Problem:** Users don't know:
- How to run web UI locally (`npm run dev`)
- How to run backend API (`python src/guppy/cli/launch.py api`)
- How to connect them (proxy config)
- What environment variables to set

**Impact:** Onboarding friction; users guess and break setup

---

### 8. 🟠 LOW: Missing POST Install Script

**Problem:** `package.json` scripts don't include postinstall step to set up web dependencies.

Current scripts only have:
- `dev`: vite (web UI dev server)
- `build`: vite build (web UI build)
- `preview`: vite preview

Missing:
- Full build orchestration (build both API docs and web UI)
- Dependency coordination between root and web

**Impact:** No single command to "build everything"

---

## Why Chat Is Blank After Vercel Push

**Sequence of events:**

1. You push code to Vercel
2. Vercel runs build (only Python API, no web UI)
3. Web UI source files are not compiled to HTML/JS
4. User loads `https://your-domain.vercel.app/`
5. Vercel rewrites to `/api/index.py` (FastAPI)
6. FastAPI returns JSON (not HTML), browser shows blank or error
7. Even if HTML loaded, frontend's `VITE_API_URL` defaults to `localhost:8081`
8. Frontend XHR calls to `localhost:8081` fail (doesn't exist on Vercel)
9. Chat window has no data, models/tools don't load
10. User sees blank page

---

## Why Reinstalling Venv Breaks Things

**Sequence:**

1. You run `pip install -r requirements.txt`
2. This installs Python dependencies only
3. Web UI dependencies (in `web/package.json`) are NOT installed
4. You try to run web UI: `npm run dev` fails (dependencies missing)
5. Or you rebuild: `npm run build` fails (dependencies missing)
6. You manually run `npm install` (tedious, error-prone)
7. Next time, you forget and have to reinstall again

---

## Solution Summary

### Fix 1: Update vercel.json (CRITICAL)

Add web UI build and static file serving:

```json
{
  "buildCommand": "cd web && npm install && npm run build",
  "outputDirectory": "web/dist",
  "env": {
    "VITE_API_URL": "@guppy_api_url"
  },
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python",
      "config": { "runtime": "python3.12" }
    }
  ],
  "routes": [
    { "src": "/api/(.*)", "dest": "/api/index.py" },
    { "src": "/(.*)", "dest": "/web/dist/$1" }
  ]
}
```

### Fix 2: Set Environment Variable in Vercel

Vercel project settings:
- Add `VITE_API_URL = https://your-vercel-domain.com/api`

### Fix 3: Update API Client for Dynamic URL

Make API client work with relative paths (no hardcoded localhost):

```typescript
// web/src/api/client.ts
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  // ...
})
```

### Fix 4: Consolidate Dependencies

- Delete root `package.json`
- Keep only `web/package.json` with pinned versions
- Update bootstrap script to handle both Python + Node

### Fix 5: Add Postinstall Script

Root `package.json`:
```json
{
  "scripts": {
    "postinstall": "cd web && npm install"
  }
}
```

### Fix 6: Document Development Setup

Create `WEB_UI_SETUP.md` with:
- How to run web UI locally
- How to run backend API
- Environment variables needed
- Troubleshooting for blank chat, missing models

### Fix 7: Create Unified Build Command

```json
{
  "scripts": {
    "build": "cd web && npm run build && npm run build:api",
    "dev": "concurrently 'cd web && npm run dev' 'python src/guppy/cli/launch.py api'"
  }
}
```

---

## Recommended Fix Order

1. **TODAY:** Fix vercel.json (enables web UI to build/deploy)
2. **TODAY:** Set VITE_API_URL env var in Vercel dashboard
3. **TODAY:** Update API client to use `/api` relative path
4. **TODAY:** Test locally: `npm run dev` + `python api` = chat works
5. **Tomorrow:** Consolidate dependencies, add postinstall
6. **Tomorrow:** Add development documentation
7. **Tomorrow:** Create unified build/dev commands
8. **Test:** Redeploy to Vercel; verify chat, models, tools work

---

## Verification Checklist

After fixes:
- [ ] Local: `npm run dev` shows UI and chat works
- [ ] Local: `python src/guppy/cli/launch.py api` serves /api endpoints
- [ ] Vercel: Loads at custom domain (not blank)
- [ ] Vercel: Chat input works
- [ ] Vercel: Models show up
- [ ] Vercel: Tools show up
- [ ] Vercel: No console errors about API unreachable
- [ ] venv reinstall: No manual npm/pip steps needed

---

## Files to Modify

1. `/vercel.json` (major rewrite)
2. `/web/src/api/client.ts` (1-line change)
3. `/package.json` (consolidation or deletion)
4. Create `/WEB_UI_SETUP.md` (new)
5. Update `.env.example` (add VITE_API_URL)
6. Create `/Makefile` or unified build scripts (optional but helpful)
