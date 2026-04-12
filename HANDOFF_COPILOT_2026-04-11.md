# Guppy AI Suite — Copilot Handoff Report
**Date:** 2026-04-11  
**From:** Claude Sonnet 4.6 session (context exhausted)  
**To:** GitHub Copilot / next AI session  
**Priority:** HIGH — model upgrade just completed, needs validation + 3 feature tracks

---

## 1. Current System State

### Hardware
```
CPU   Ryzen 9 9900X   12c/24t
GPU   RX 7900 XTX     24GB VRAM — ROCm ACTIVE, full GPU offload confirmed
RAM   96GB
DISK  4x Samsung 990 PRO 2TB NVMe
```

### Ollama Models (JUST REBUILT — needs testing)
```
guppy:latest     local persona model (active)
merlin:latest    local persona model (active)
guppy            fallback local persona (if tagged alias not present)
merlin           fallback local persona (if tagged alias not present)
```

### Python Environment
```
.venv/Scripts/python.exe  (always use this, not system python)
PySide6              6.11.0
anthropic            0.86.0
faster-whisper       1.2.1
openwakeword         0.6.0   ← installed this session, models downloaded
chromadb             1.5.2   ← installed, NOT yet wired in
```

### Tool Count
```
65 tools registered in guppy_core.py
```

---

## 2. What Was Done This Session

### A. New Tools Added (all in guppy_core.py + media_tools.py)
| Tool | File | Status |
|------|------|--------|
| `clipboard_read` | guppy_core.py | LIVE, tested |
| `clipboard_write` | guppy_core.py | LIVE, tested |
| `get_active_window` | guppy_core.py | LIVE, tested |
| `focus_window` | guppy_core.py | LIVE, tested |
| `read_screen_text` | guppy_core.py | LIVE, uses Claude Haiku vision |
| `calendar_events` | media_tools.py | LIVE, needs Google Calendar creds |
| `send_email` | media_tools.py | LIVE, uses existing Gmail OAuth |
| `gmail_scan_inbox` | media_tools.py | LIVE, AI classifies + auto-creates tasks |
| `search_web` | guppy_core.py | UPGRADED — Perplexity if key set, else browser |
| `get_weather` | guppy_core.py | LIVE, needs OWM key |

### B. Morning Brief Upgraded
`_morning_brief()` in guppy_core.py now pulls in order:
1. Weather (if OPENWEATHERMAP_API_KEY + WEATHER_LOCATION set)
2. Calendar today (if google_calendar_credentials.json exists)
3. Reminders
4. Tasks
5. Gmail unread counts
6. **Inbox action items** — runs gmail_scan_inbox, shows bills/interviews/client requests
7. Recent memory context

### C. Voice Upgrades
- `guppy_voice.py` VoiceConfig.stt_model default: `"base"` → `"large-v3"`
- Reads from env var `GUPPY_WHISPER_MODEL` (set in .env)
- openwakeword installed + 6 ONNX models downloaded (alexa, hey_mycroft, hey_jarvis, hey_rhasspy, timer, weather)
- Fast path (`_wake_word_listener_oww`) now active by default

### D. Infrastructure
- `.env` created at `C:/Users/Ryan/Guppy/.env` with ANTHROPIC_API_KEY pre-loaded
- `bin/cloudflared.exe` v2026.3.0 bundled
- `bin/start_tunnel.bat` + `bin/cloudflare_terminal.ps1` updated to use local binary
- `Modelfile.guppy` + `Modelfile.merlin` created/updated for local persona workflow
- `build_models.bat` — one-click persona rebuild script

---

## 3. TASK A — Test New Models (DO THIS FIRST)

Both `guppy` and `merlin` were rebuilt for local persona use. They need validation before Ryan uses them in production.

### 3A. Guppy Model Tests
Run from `.venv/Scripts/python.exe` in `C:/Users/Ryan/Guppy`:

```python
# test_models.py — create and run this
import requests, json, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:11434/api/generate"

def ask(model, prompt, expect_keyword=None):
    r = requests.post(BASE, json={"model": model, "prompt": prompt, "stream": False}, timeout=60)
    resp = r.json().get("response", "ERROR")
    ok = expect_keyword.lower() in resp.lower() if expect_keyword else True
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {model}: {resp[:120]}")
    return ok

tests = [
    # Guppy persona
    ("guppy", "Who are you? One sentence.", "guppy"),
    ("guppy", "Address me correctly. What do you call me?", "ryan"),
    ("guppy", "What is 17 * 23?", "391"),
    ("guppy", "List 3 Python data structures.", "list"),
    # Merlin persona
    ("merlin", "Who are you?", "merlin"),
    ("merlin", "What is recursion?", None),   # Should answer with questions first
    ("merlin", "Sign off your message.", None),  # Should end with ✦
]

passed = sum(ask(m, p, k) for m, p, k in tests)
print(f"\n{passed}/{len(tests)} passed")
```

**Expected failures to watch for:**
- Model ignores persona (answers out of character) → needs Modelfile tuning
- `guppy` doesn't sign off with 🎩 → add explicit instruction to Modelfile.guppy
- `merlin` doesn't use Socratic method → check system prompt preserved correctly
- Either model is much slower than before → check `ollama ps` for GPU offload

### 3B. Tool Integration Test with New Model
```python
# Test that guppy model works via the actual Guppy tool pipeline
# Run guppy_agent.py in non-interactive mode:
from guppy_agent import ollama_turn
from guppy_core import get_startup_system

result = ollama_turn(
    [{"role": "user", "content": "What tools do you have available? Name 5."}],
    user="test",
    system=get_startup_system(),
    model="guppy"
)
print(result)
```

### 3C. Performance Benchmark
```bash
# Time a response to compare old vs new
powershell -Command "Measure-Command { ollama run guppy 'Explain binary search in 2 sentences.' }"
```
Old local baseline: ~3-5s first token  
Current local persona baseline: should be similar or faster with same VRAM

---

## 4. TASK B — Add These Programs/Tools

The following were discussed as high-value additions. Implement in `guppy_core.py` (definitions) and the relevant module.

### 4A. Semantic Memory with ChromaDB (HIGH PRIORITY)
ChromaDB is already installed (`chromadb 1.5.2`). Wire it in for semantic search.

**Create `guppy_semantic_memory.py`:**
```python
"""
Semantic memory layer using ChromaDB + nomic-embed-text (via Ollama).
Wraps the existing SQLite guppy_memory.py with vector search.

First: ollama pull nomic-embed-text
"""
import chromadb
from chromadb.utils import embedding_functions

COLLECTION = "guppy_memory"
_client = chromadb.PersistentClient(path="C:/Users/Ryan/Guppy/chroma_db")

def get_embedder():
    return embedding_functions.OllamaEmbeddingFunction(
        url="http://localhost:11434/api/embeddings",
        model_name="nomic-embed-text"
    )

def remember_semantic(key: str, value: str, category: str = "general") -> str:
    col = _client.get_or_create_collection(COLLECTION, embedding_function=get_embedder())
    col.upsert(ids=[key], documents=[value], metadatas=[{"category": category, "key": key}])
    return f"Stored in semantic memory: {key}"

def recall_semantic(query: str, n=5, category: str = "") -> str:
    col = _client.get_or_create_collection(COLLECTION, embedding_function=get_embedder())
    where = {"category": category} if category else None
    results = col.query(query_texts=[query], n_results=n, where=where)
    docs = results.get("documents", [[]])[0]
    if not docs:
        return "Nothing found in semantic memory."
    return "\n".join(f"  • {d}" for d in docs)
```

**Add tools to TOOLS list in guppy_core.py:**
- `semantic_remember` — store to vector DB
- `semantic_recall` — similarity search (much better than keyword `recall`)

**First run:** `ollama pull nomic-embed-text`

### 4B. GitHub Tool
```python
# Add to guppy_core.py TOOLS:
{
    "name": "github",
    "description": "Interact with GitHub — list repos, create/read issues, list PRs, get file contents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list_repos", "list_issues", "create_issue", "list_prs", "get_file"]},
            "repo":   {"type": "string", "description": "owner/repo format"},
            "title":  {"type": "string"},
            "body":   {"type": "string"},
            "path":   {"type": "string"},
        },
        "required": ["action"]
    }
}

# Implementation uses GITHUB_TOKEN env var + requests to api.github.com
# No extra pip install needed — requests already available
```

Add `GITHUB_TOKEN=` to `.env` (generate at github.com/settings/tokens, repo scope).

### 4C. Run Python Snippet Tool
```python
{
    "name": "run_python",
    "description": "Execute a Python snippet and return stdout/result. Use for calculations, data transforms, quick scripts.",
    "input_schema": {
        "type": "object", 
        "properties": {
            "code": {"type": "string", "description": "Python code to execute."},
            "timeout": {"type": "integer", "description": "Max seconds. Default 10."}
        },
        "required": ["code"]
    }
}

# Implementation: subprocess with .venv python, capture stdout, enforce timeout
# Security: runs in subprocess so it can't corrupt guppy state
```

### 4D. Windows Notification Push Tool
```python
{
    "name": "notify",
    "description": "Send a Windows 11 toast notification to Ryan. Use for async alerts, reminders that fire mid-task, or completing background work.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title":   {"type": "string"},
            "message": {"type": "string"},
            "duration": {"type": "string", "enum": ["short", "long"], "description": "Default short"}
        },
        "required": ["title", "message"]
    }
}

# Uses win11toast (already in requirements.txt)
from win11toast import notify as _win_notify
_win_notify(title, message, duration=duration)
```

### 4E. Web Summarize (Firecrawl / requests fallback)
```python
{
    "name": "web_summarize",
    "description": "Fetch a URL and return a summary of its content. Handles JS-heavy pages if FIRECRAWL_API_KEY is set.",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "instruction": {"type": "string", "description": "What to extract. Default: summarize the page."}
        },
        "required": ["url"]
    }
}
# If FIRECRAWL_API_KEY set: POST to api.firecrawl.dev/v1/scrape
# Else: requests + BeautifulSoup (already installed), strip tags, send to Claude for summary
```

---

## 5. TASK C — Interface Upgrades

Three independent UI improvements. Read the relevant files first before editing.

### 5A. Streaming Responses in guppy_ui.py (HIGHEST VALUE)
**Problem:** Responses appear all at once after the full generation. Feels slow.  
**Fix:** Guppy already has streaming in `guppy_api.py` via WebSocket. Wire it into the Ollama path in `guppy_ui.py`.

**Location:** `guppy_ui.py` — find `_WorkerThread` (around line 60-130). It calls `ollama_turn()` from `guppy_agent.py`.

**What to do:**
1. In `guppy_agent.py` → `ollama_turn()`, add a `stream=True` variant that yields tokens
2. In `guppy_ui.py` → `_WorkerThread`, emit partial tokens via a new `token` signal
3. In the chat bubble widget, append tokens as they arrive instead of replacing

**Ollama streaming endpoint:**
```python
# POST to http://localhost:11434/api/chat with stream=True
# Response is newline-delimited JSON, each line has {"message": {"content": "token"}}
import requests, json
resp = requests.post("http://localhost:11434/api/chat",
    json={"model": "guppy", "messages": msgs, "stream": True},
    stream=True, timeout=120
)
for line in resp.iter_lines():
    if line:
        chunk = json.loads(line)
        token = chunk.get("message", {}).get("content", "")
        if token:
            yield token  # or emit signal
```

### 5B. Chat History Panel
**Problem:** No way to scroll back through prior conversations.  
**File:** `guppy_ui.py`

Add a collapsible left sidebar (QSplitter + QListWidget) that shows:
- Session titles (auto-named from first message)
- Click to load prior session from `guppy_memory.py`
- "New Chat" button clears current session

`guppy_memory.py` already stores messages with `session_id`. Query with:
```python
_mem.get_session_messages(session_id)  # check if this method exists, add if not
```

### 5C. Hub Dashboard Real-Time Charts
**Problem:** Hub shows static text badges for API/CF/Auth status.  
**File:** `guppy_hub.py` — `StatusSettingsCard`

Add a live sparkline chart (use `PySide6.QtCharts` — already available via PySide6) showing:
- API response time (ms) over last 60 seconds
- GPU VRAM usage (from `psutil` or `subprocess("powershell Get-CimInstance Win32_VideoController")`)
- Active model + context length

`PySide6.QtCharts.QSplineSeries` + `QChartView` — minimal code, high visual impact.

---

## 6. Keys Needed (Ryan to supply)

```
.env file: C:/Users/Ryan/Guppy/.env

PERPLEXITY_API_KEY=      # pplx.ai/settings/api — free, enables AI search answers
OPENWEATHERMAP_API_KEY=  # openweathermap.org/api — free, enables weather
WEATHER_LOCATION=Dallas,TX,US
GITHUB_TOKEN=            # github.com/settings/tokens — enables GitHub tool
FIRECRAWL_API_KEY=       # firecrawl.dev — paid, improves web scraping (optional)
GUPPY_JWT_SECRET=        # any long random string — enables remote API auth
```

---

## 7. File Map (Key Files Only)

```
C:/Users/Ryan/Guppy/
├── guppy_ui.py          Main GUI — PySide6, orb state machine, chat
├── guppy_core.py        Tool definitions (65 tools) + dispatcher + system prompt
├── guppy_voice.py       TTS (Kokoro) + STT (Whisper large-v3) + wake word (OWW)
├── guppy_memory.py      SQLite memory — facts, tasks, pipeline, contacts
├── guppy_daemon.py      APScheduler background services + window watcher
├── guppy_hub.py         Hub UI — health badges, model switcher, settings
├── guppy_api.py         FastAPI server — JWT auth, /chat, /ws, /status
├── guppy_agent.py       Terminal REPL + ollama_turn() helper
├── media_tools.py       Spotify, YouTube, Gmail (purge + scan + send), Calendar
├── merlin_ui.py         Merlin UI (separate window)
├── merlin_core.py       Merlin worker thread
├── council_ui.py        Council mode — Guppy + Merlin debate panel
├── .env                 API keys (ANTHROPIC pre-loaded, others need filling)
├── Modelfile.guppy      Guppy local persona model
├── Modelfile.merlin     Merlin local persona model
└── build_models.bat     Rebuild both models: run after any Modelfile change
```

---

## 8. Quick Start Commands

```bash
# Activate venv (always required)
cd C:/Users/Ryan/Guppy
.venv/Scripts/activate

# Launch Guppy GUI
bin/launch_guppy.bat

# Run model tests (Task A)
.venv/Scripts/python.exe test_models.py

# Pull nomic-embed-text for semantic memory (Task B)
ollama pull nomic-embed-text

# Rebuild models after Modelfile changes
build_models.bat

# Syntax check
.venv/Scripts/python.exe -c "import guppy_core; print(len(guppy_core.TOOLS), 'tools OK')"

# Systems check
.venv/Scripts/python.exe tests/smoke_api.py   # requires API server running
```

---

## 9. Known Issues / Watch Out For

1. **Whisper large-v3 first load** — takes ~30s on first voice session. Normal. Singleton caches it after.
2. **gmail_scan_inbox in morning_brief** — will trigger Gmail OAuth browser pop if not yet authenticated. Wrap in try/except or skip on first run.
3. **Local persona drift** — if model breaks character in testing, strengthen persona constraints in Modelfile and rebuild.
4. **chromadb installed but not wired** — `guppy_semantic_memory.py` doesn't exist yet. Task B item.
5. **merlin_ui.py / merlin_core.py have UTF-8 BOM** — known, not breaking, left intentionally.
6. **No .env when launching via Guppy.bat** (root bat) — only `bin/launch_guppy.bat` loads `.env`. Update `Guppy.bat` to also load it.

---

## 10. Priority Order

```
1. [ ] Run model tests (Task A) — validate local persona models are working in character
2. [ ] Add run_python tool (Task B-C) — high value, low risk
3. [ ] Add notify tool (Task B-D) — trivial, win11toast already installed  
4. [ ] Wire streaming tokens in guppy_ui.py (Task C-A) — biggest UX win
5. [ ] Semantic memory with ChromaDB (Task B-A) — after nomic-embed-text pull
6. [ ] GitHub tool (Task B-B) — needs GITHUB_TOKEN from Ryan
7. [ ] Chat history panel (Task C-B)
8. [ ] Hub sparkline charts (Task C-C)
9. [ ] web_summarize tool (Task B-E)
```
