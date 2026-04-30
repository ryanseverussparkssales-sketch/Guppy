# Guppy — PC Control

**Last updated:** 2026-04-30

The PC control surface allows Guppy to observe and interact with the local desktop.

---

## Architecture

```
WorkspaceView (PC tab)
    ↓
SystemMetricsPanel — CPU/RAM/disk/net gauges
AutomationPanel    — screenshot, click, type, reminders
    ↓
GET /api/desktop/screenshot
POST /api/desktop/click
POST /api/desktop/type
POST /api/desktop/scroll
POST /api/desktop/drag
GET /api/system/metrics
    ↓
src/guppy/api/routes_desktop.py  — pyautogui wrapper
src/guppy/api/routes_screen_monitor.py — Screenpipe integration
```

---

## Desktop Control API (`/api/desktop/*`)

Backed by `pyautogui`. Graceful fallback if pyautogui is absent (returns 503).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/desktop/screenshot` | GET | Returns base64 PNG of current screen |
| `/api/desktop/click` | POST | `{x, y, button?}` — mouse click |
| `/api/desktop/type` | POST | `{text}` — keyboard type |
| `/api/desktop/scroll` | POST | `{x, y, clicks}` — scroll wheel |
| `/api/desktop/drag` | POST | `{x1, y1, x2, y2}` — click-drag |

---

## Screen Monitoring (`/api/screen/*`)

Backed by `Screenpipe` local service. Aggregates app focus, keystrokes (redacted), and window titles into a timeline.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/screen/timeline` | GET | Aggregated activity timeline |
| `/api/screenpipe/recent` | GET | Recent activity frames |
| `/api/screenpipe/search` | GET | Full-text search over screen history |
| `/api/screenpipe/context` | GET | Current app focus + recent context |

**AI summaries:** 30-minute background job generates per-window activity summaries using Hermes3.  
Summaries cached in `guppy_main.db.screen_events`.

---

## Safety Gate

- All desktop control actions are logged to `guppy_main.db.screen_events`
- No autonomous action execution without explicit user trigger or confirmed tool_call from LLM
- `POST /api/desktop/*` requires valid JWT (same auth as all API routes)

---

## OmniParser Integration (Future)

`docs/TRANCHE_CODEX.md` Tranche D+ references OmniParser for structured UI element detection from screenshots. Not yet implemented — current screenshot endpoint returns raw PNG.
