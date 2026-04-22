# BE-TR01 — Backend Execution Tranche

**Date:** 2026-04-21  
**Branch:** master  
**Owner:** Backend (non-UI)  
**UI Surface:** Qt.io (separate, out of scope for this tranche)

---

## Objective

Extract all AI inference, chat, and API surface concerns into a cloud-deployable
backend that can be iterated independently on Vercel, with no dependency on the
local desktop runtime, voice hardware, or Qt UI.

---

## Ownership Boundary

| Layer | Owner | Location |
|---|---|---|
| AI Inference / Chat | **This tranche** | `api/` (Vercel cloud) |
| Inference Router | **This tranche** | `src/guppy/inference/` (shared) |
| Auth (JWT + Turnstile) | **This tranche** | `src/guppy/api/auth.py` |
| FastAPI server (local) | Local runtime | `src/guppy/api/server_runtime.py` |
| Desktop shell / connectors | Local runtime | `src/guppy/launcher_application/` |
| Voice / Audio | Local runtime | `src/guppy/voice/` |
| Qt UI | **Qt.io tranche** | `ui/` |

---

## Deliverables

### 1. `api/app.py` — Vercel-native FastAPI shell
- Minimal FastAPI app, no local runtime imports
- CORS for Qt client origin
- Lifespan: probe AI provider availability at startup

### 2. `api/routes/chat.py` — `/chat` endpoint
- `POST /chat` — stateless text chat completion
- `POST /chat/stream` — SSE streaming response
- Request: `{ message, history?, mode?, persona? }`
- Response: `{ reply, model, latency_ms, schema_version }`

Status: implemented (contract-safe baseline route + SSE event stream).

### 3. `api/routes/health.py` — `/health` endpoint
- `GET /health` — liveness probe
- Returns AI provider availability flags

### 4. `api/index.py` — Vercel ASGI entry
- Points to `api/app.py`'s exported `app`

Status: implemented.

### 5. `pyproject.toml` — `[project]` table
- Required for `uv lock` on Vercel
- Declares runtime deps: fastapi, uvicorn, python-jose, httpx

Status: implemented.

### 6. `vercel.json` — Routing
- Already in place; catch-all rewrite to `/api/index.py`

---

## Environment Variables (Vercel Project Settings)

| Var | Purpose |
|---|---|
| `OPENAI_API_KEY` | Primary AI backend |
| `ANTHROPIC_API_KEY` | Claude fallback |
| `GUPPY_AI_BACKEND` | `openai` \| `anthropic` \| `auto` |
| `GUPPY_TURNSTILE_SECRET` | Cloudflare Turnstile validation |
| `GUPPY_JWT_SECRET` | JWT signing key |

Local machine keys (connectors, daemon auth) are **never** set in Vercel.

---

## API Contract (schema_version: 1)

### POST /chat

**Request**
```json
{
  "schema_version": 1,
  "message": "string",
  "history": [{"role": "user|assistant", "content": "string"}],
  "mode": "auto|creative|precise",
  "persona": "guppy|merlin|null"
}
```

**Response**
```json
{
  "schema_version": 1,
  "reply": "string",
  "model": "string",
  "latency_ms": 0,
  "finish_reason": "stop|length|error"
}
```

### GET /health

**Response**
```json
{
  "status": "ok",
  "providers": {
    "openai": true,
    "anthropic": false
  },
  "schema_version": 1
}
```

---

## Security Rules

- No local secrets, no connector credentials in Vercel
- All write endpoints require Turnstile + JWT
- JWT expiry: 24 h
- Rate limit: 60 req/min per user

---

## Success Criteria

- [x] `vercel deploy` completes without runtime-version errors — `vercel.json` specifies `python3.12`; `tools/vercel_preflight.py --skip-env` validates runtime config pre-deploy
- [x] `GET /health` returns 200 with provider flags, `version`, and `uptime_seconds` (Wave 4)
- [x] `POST /chat` returns a streamed reply from AI provider (OpenAI `gpt-4o-mini` / Anthropic `claude-3-5-haiku-20241022`)
- [x] Qt UI can call `/chat` with CORS headers intact — CORS middleware configured with `X-Request-ID` in `allow_headers`
- [x] No `guppy_core`, `voice`, or `daemon` imports in Vercel app path — enforced by `tools/check_architecture_boundaries.py` + `test_architecture_boundary_guard.py`

### Additional gates completed beyond original criteria

- [x] `POST /auth/token` — API-key → signed JWT exchange (Wave 3)
- [x] `POST /auth/refresh` — JWT sliding-window renewal (Wave 4)
- [x] Persona + mode system-prompt injection (`guppy`, `merlin`; `precise`, `creative`) (Wave 3)
- [x] Input validation — `message` 1–4000 chars, `history` ≤ 50 items, `content` ≤ 8000 chars (Wave 4)
- [x] `X-Request-ID` middleware — echoes or generates per-request trace ID (Wave 4)
- [x] `tools/vercel_preflight.py` — pre-deploy configuration validator wired into `backend-gate` (Wave 5)
- [x] 37 unit tests passing (Waves 1–4 + contracts + boundary guard)

**Tranche status: COMPLETE**

---

## Excluded from This Tranche

- Qt UI implementation
- Local runtime feature work
- Voice transcription cloud path (future tranche)
- Connector / workspace API cloud path (future tranche)
