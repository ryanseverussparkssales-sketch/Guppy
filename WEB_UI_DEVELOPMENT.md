# Web UI Development & Deployment Guide

**Last updated:** 2026-04-22

---

## Quick Start (Local Development)

### Prerequisites
- Node.js 18+ (for web UI)
- Python 3.12+ (for backend API)
- Ollama or other local LLM running on `http://127.0.0.1:11434`

### Step 1: Install Dependencies

```bash
# Install Python dependencies (if not already done)
pip install -r requirements.txt

# Install Node dependencies
cd web
npm install
cd ..
```

### Step 2: Set Environment Variables

Copy `.env.example` to `.env` and set required keys:

```bash
cp .env.example .env
```

**Critical for local dev:**
```env
VITE_API_URL=/api
GUPPY_DEV_MODE=1
ANTHROPIC_API_KEY=your-key-here  # or OPENAI_API_KEY
```

### Step 3: Run Backend API

In one terminal:

```bash
# Starts FastAPI server on http://localhost:8081
python src/guppy/cli/launch.py api
```

Or if you have the venv:

```bash
python -m src.guppy.cli.api
```

### Step 4: Run Web UI Dev Server

In another terminal:

```bash
cd web
npm run dev
```

This starts Vite on `http://localhost:3000` with automatic proxy to backend.

### Step 5: Open in Browser

Visit: `http://localhost:3000`

You should see:
- Chat interface
- Models dropdown populated
- Tools list populated
- Chat working and responding

---

## Architecture

### Frontend (React + TypeScript)

**Location:** `web/src/`

```
web/src/
├── api/
│   └── client.ts          # Axios instance, baseURL configuration
├── components/
│   ├── layout/            # AppShell, Sidebar, TopBar
│   ├── Chat.tsx           # Main chat interface
│   └── ui/                # Shadcn UI components
├── hooks/
│   ├── useApi.ts          # API call wrapper
│   ├── useChatHistory.ts  # Chat state management
│   └── useTheme.ts        # Dark/light mode
├── App.tsx                # Main app component
└── main.tsx               # Entry point
```

### Backend (FastAPI)

**Location:** `api/`

```
api/
├── index.py               # Vercel entrypoint
├── app.py                 # FastAPI app definition
├── auth.py                # Authentication & rate limiting
└── routes/
    ├── chat.py            # POST /chat (inference)
    ├── catalog.py         # GET /catalog (models + tools)
    ├── health.py          # GET /health (API status)
    ├── auth_token.py      # POST /auth/token
    └── auth_refresh.py    # GET /auth/refresh
```

### Development Server Setup

**Vite Config** (`web/vite.config.ts`):
```typescript
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8081',
      changeOrigin: true,
    },
  },
}
```

This means:
- Frontend runs on `http://localhost:3000`
- API calls to `/api/...` are proxied to `http://localhost:8081/...`
- CORS is handled automatically by proxy

---

## API Endpoints

### Chat

**Endpoint:** `POST /api/chat`

**Request:**
```json
{
  "message": "What is Guppy?",
  "history": [],
  "mode": "guppy"
}
```

**Response:**
```json
{
  "reply": "Guppy is a local AI assistant...",
  "model": "gpt-4o-mini",
  "latency_ms": 1234,
  "finish_reason": "stop"
}
```

### Catalog (Models + Tools)

**Endpoint:** `GET /api/catalog`

**Response:**
```json
{
  "schema_version": 1,
  "models": [
    {
      "id": "gpt-4o-mini",
      "name": "GPT-4o Mini",
      "provider": "openai"
    }
  ],
  "tools": [
    {
      "id": "web_search",
      "name": "Web Search",
      "description": "Search the web for information"
    }
  ]
}
```

### Health Check

**Endpoint:** `GET /api/health`

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

---

## Troubleshooting

### Chat Window is Blank

**Check 1: API running?**
```bash
curl http://localhost:8081/health
```

Should return 200 with JSON. If not:
```bash
# Start API server
python src/guppy/cli/launch.py api
```

**Check 2: API endpoint correct?**
Open browser DevTools → Network tab.
Try sending a message. Look for XHR request to `/api/chat`.

If it 404s or shows `localhost:8081 unreachable`, the proxy isn't working:
```bash
# Stop and restart Vite
cd web
npm run dev
```

**Check 3: Environment variable set?**
```bash
# In web/.env or root .env
VITE_API_URL=/api
```

### Models/Tools Not Showing

**Check:** API catalog endpoint returns data

```bash
curl http://localhost:8081/api/catalog
```

Should return a JSON object with `models` and `tools` arrays.

If empty:
- Check your API keys (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`)
- Restart API server
- Check `/api/health` to see which providers are available

### Dependencies Keep Breaking

**Problem:** You reinstalled venv but web UI stopped working

**Solution:** Reinstall both Python AND Node dependencies

```bash
# Full clean install
pip install -r requirements.txt          # Python deps
cd web && npm install && cd ..           # Node deps
npm run build                            # Build web UI for production
```

---

## Building for Production

### Build Web UI

```bash
cd web
npm run build
```

Output: `web/dist/` (static HTML/JS/CSS)

### Build Both

```bash
npm run build-all  # If you've added this script
```

Or manually:
```bash
cd web && npm run build && cd ..
# Python API is ready to go (no build needed)
```

---

## Deploying to Vercel

### Prerequisites

1. **Vercel Account:** https://vercel.com
2. **GitHub Repo:** Connected to Vercel
3. **Environment Variables:** Set in Vercel dashboard

### Environment Variables in Vercel

1. Go to Vercel project settings
2. Add these environment variables:

```
VITE_API_URL: https://YOUR-VERCEL-DOMAIN.vercel.app/api
ANTHROPIC_API_KEY: sk-ant-...
OPENAI_API_KEY: (if using OpenAI)
GUPPY_CORS_ORIGINS: https://YOUR-VERCEL-DOMAIN.vercel.app,https://www.YOUR-VERCEL-DOMAIN.vercel.app
```

### vercel.json Configuration

The root `vercel.json` now includes:
- Build command for web UI: `cd web && npm install && npm run build`
- Output directory: `web/dist/`
- Python runtime for API
- Routes configuration (static files + API)

When you push to Vercel:
1. Vercel reads `vercel.json`
2. Runs the build command (compiles React → `web/dist/`)
3. Deploys Python API at `/api/`
4. Routes `/api/*` to Python, everything else to static files
5. Frontend loads from `web/dist/index.html`
6. Frontend calls `/api/chat` (same domain, no CORS needed)

### Deployment Checklist

- [ ] Environment variables set in Vercel dashboard
- [ ] `vercel.json` updated with build command and routes
- [ ] `VITE_API_URL` set to your Vercel domain
- [ ] Push to main/master branch
- [ ] Wait for Vercel build to complete
- [ ] Visit your domain
- [ ] Chat input appears
- [ ] Models/tools show up
- [ ] Send a message and get a response
- [ ] Check browser DevTools for any errors

---

## Common Issues & Fixes

### Issue: "Cannot GET /"

**Cause:** Web UI not being served (not built, or routes misconfigured)

**Fix:**
```bash
# Rebuild web UI
cd web && npm run build && cd ..
# Check web/dist/ exists
ls web/dist/
# Should show: index.html, assets/, etc.
```

### Issue: API 401 Unauthorized

**Cause:** Missing or invalid authentication token

**Fix:**
- Get token: `POST /auth/token` with credentials
- Send in requests: `Authorization: Bearer TOKEN`
- Or: Check that TURNSTILE_SECRET and JWT_SECRET are set

### Issue: "Cannot reach localhost:8081"

**Cause:** API not running or not on port 8081

**Fix:**
```bash
# Check if API is running
lsof -i :8081  # macOS/Linux
netstat -ano | findstr :8081  # Windows

# Start API if not running
python src/guppy/cli/launch.py api
```

### Issue: CORS errors

**Cause:** Frontend domain not in `GUPPY_CORS_ORIGINS`

**Fix:**
In `.env`:
```
GUPPY_CORS_ORIGINS=http://localhost:3000,http://localhost:8081,https://your-domain.com
```

---

## Development Tips

### Hot Reload

Changes to `.tsx` files automatically reload in browser (Vite feature).

Changes to Python API require manual restart:
```bash
# Stop the API server (Ctrl+C)
# Restart it
python src/guppy/cli/launch.py api
```

### Debugging

**Browser DevTools:**
- Network tab: Check API requests/responses
- Console: Check for JavaScript errors
- Application tab: Check localStorage (access token, etc.)

**API Logs:**
```bash
# If running with GUPPY_DEV_MODE=1, logs are verbose
GUPPY_DEV_MODE=1 python src/guppy/cli/launch.py api
```

### Testing

```bash
# Run unit tests
python -m pytest tests/unit/ -q

# Run API smoke tests
python tests/smoke/smoke_api.py

# Run web build check
cd web && npm run build && cd ..
```

---

## Next Steps

- [ ] Local development working (chat responds, models show)
- [ ] Commit changes to Git
- [ ] Deploy to Vercel (check deployment logs for errors)
- [ ] Validate on Vercel (chat, models, tools working)
- [ ] Add to your workflow (commit → auto-deploy)
