# Guppy — Database Architecture

**Last updated:** 2026-04-30 (Tranche I — DB consolidation complete)

---

## Canonical Database Layout

| Database | Path | Owner | Contents |
|----------|------|-------|----------|
| `guppy_main.db` | `%LOCALAPPDATA%\Guppy\guppy_main.db` | App data | All primary app tables (see below) |
| `guppy_memory.db` | `%LOCALAPPDATA%\Guppy\guppy_memory.db` | Memory subsystem | Facts, embeddings, recall index |
| `triage.db` | `runtime/triage.db` | Codespace only | Dev-check run history, fix proposals, self-improvement logs |

---

## guppy_main.db — Table Inventory

| Table | Owner Route/Module | Notes |
|-------|--------------------|-------|
| `surface_config` | routes_surface, routes_realtime, routes_companion | Per-surface model + personality settings |
| `conversations` | routes_conversations | Chat session metadata |
| `messages` | routes_conversations | Chat message history |
| `agents` | routes_agents | Spawned agent task records |
| `contacts` | routes_workspace_data | CRM contacts |
| `tasks` | routes_tasks, routes_workspace_data | Task CRUD |
| `reminders` | routes_reminders | Reminder schedule |
| `calendar_events` | routes_calendar | Local events + Google sync cache |
| `email_threads` | routes_email | Gmail thread cache |
| `voip_calls` | routes_voip | Call log + recordings |
| `screen_events` | routes_screen_monitor | Screenpipe activity timeline |
| `documents` | routes_documents | Uploaded doc metadata |
| `media_items` | routes_media | qBittorrent catalog + recordings |
| `inference_metrics` | routes_inference_metrics | Per-request token/latency stats |
| `tools` | routes_tools, realtime_inference_support | Tool schema registry |
| `pipeline_runs` | routes_pipeline | Workflow run history |
| `mcp_servers` | mcp/manager.py | MCP plugin config |
| `library_metadata` | library/enricher.py | OpenLibrary cache (TTL 30 days) |
| `operator_settings` | routes_model_roles | Cloud gate + partner config |
| `model_roles` | routes_model_roles | Role → model key mappings |

---

## guppy_memory.db — Table Inventory

| Table | Owner | Notes |
|-------|-------|-------|
| `facts` | memory/memory.py | Key-value semantic memory |
| `embeddings` | memory/semantic.py | Vector embeddings for recall |

---

## triage.db — Table Inventory

| Table | Owner | Notes |
|-------|-------|-------|
| `triage_runs` | codespace/codespace_triage.py | Dev-check run results |
| `triage_failures` | codespace/codespace_triage.py | Per-check failure records |
| `fix_proposals` | codespace/self_improve.py | AI fix proposals + apply status |

---

## Access Patterns

All database access goes through `src/guppy/db/`:

```python
from src.guppy.db import get_main_db, get_memory_db, get_triage_db

with get_main_db() as conn:
    conn.execute("SELECT ...")
```

Each connection has standard pragmas applied:
- `PRAGMA journal_mode=WAL`
- `PRAGMA foreign_keys=ON`
- `PRAGMA busy_timeout=5000`

---

## Path Constants

All path constants are in `src/guppy/paths.py`:

```python
MAIN_DB_PATH   = USER_DATA_DIR / "guppy_main.db"
MEMORY_DB_PATH = USER_DATA_DIR / "guppy_memory.db"
TRIAGE_DB_PATH = RUNTIME_DIR / "triage.db"
```

Override via environment variables:
- `GUPPY_MAIN_DB_PATH`
- `GUPPY_MEMORY_DB_PATH`

---

## Rate Limits DB (Separate)

`guppy_rate_limits.sqlite3` is managed by `src/guppy/api/auth.py` for JWT rate limiting. This is intentionally separate — it's transient/operational, not app data.

---

## Migration Status

- **Tranche I (2026-04-30):** All route files migrated from scattered per-feature DBs (`tasks.db`, `surface.db`, `media.db`, etc.) to `guppy_main.db` via `MAIN_DB_PATH` constant.
- **Alembic:** Schema migrations live in `migrations/`. Run `alembic upgrade head` to apply.
