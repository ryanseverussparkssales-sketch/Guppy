# Database Inventory — Tranche I Audit

**Produced:** 2026-04-30  
**Status:** Consolidation complete via `src/guppy/db/` module

---

## Canonical Layout (post-Tranche I)

| DB File | Location | Owner | Tables |
|---|---|---|---|
| `guppy_main.db` | `USER_DATA_DIR/guppy_main.db` | Primary app DB | chat_sessions, messages, workspace_tasks, inference_metrics, inference_events, calendar_events, email_threads, email_messages, contacts, pipeline_runs, pipeline_steps, pipeline_tool_calls, library_items, library_metadata, voip_calls, documents, surface_config, operator_settings, agents, agent_runs, model_roles, media_catalog, call_recordings, screen_timeline, screen_ai_summaries, reminders, tool_executions |
| `guppy_memory.db` | `USER_DATA_DIR/guppy_memory.db` | Memory/facts DB | facts, memory_items, semantic_chunks |
| `triage.db` | `runtime/triage.db` | Codespace only | triage_runs, triage_failures, self_improve_proposals |
| `guppy_rate_limits.sqlite3` | `USER_DATA_DIR/guppy_rate_limits.sqlite3` | Auth only | rate_limits |

---

## Pre-Consolidation DB Files (all migrated or replaced)

| Old file | Old location | Migrated to |
|---|---|---|
| `guppy_main.db` | `USER_DATA_DIR/guppy_main.db` | Same — authoritative |
| `guppy_memory.db` | `USER_DATA_DIR/guppy_memory.db` | Same — authoritative |
| `chat_history.db` | `USER_DATA_DIR/chat_history.db` | → `guppy_main.db` (routes_conversations) |
| `agents.db` | `USER_DATA_DIR/agents.db` | → `guppy_main.db` (routes_agents) |
| `library.db` | `USER_DATA_DIR/library.db` | → `guppy_main.db` (launcher_application/library_storage) |
| `pipeline.db` | `USER_DATA_DIR/pipeline.db` | → `guppy_main.db` (routes_pipeline, routes_tools) |
| `tools.db` | `USER_DATA_DIR/tools.db` | → `guppy_main.db` (routes_realtime, _router_fragment_execution) |
| `mcp_servers.db` | `USER_DATA_DIR/mcp_servers.db` | → `guppy_main.db` (mcp/manager) |
| `calendar.db` | `runtime/calendar.db` | → `guppy_main.db` (routes_calendar) |
| `email.db` | `runtime/email.db` | → `guppy_main.db` (routes_email) |
| `documents.db` | `runtime/documents.db` | → `guppy_main.db` (routes_documents) |
| `reminders.db` | `runtime/reminders.db` | → `guppy_main.db` (routes_reminders) |
| `voip.db` | `runtime/voip.db` | → `guppy_main.db` (routes_voip) |
| `screen_monitor.db` | `runtime/screen_monitor.db` | → `guppy_main.db` (routes_screen_monitor) |
| `self_improve.db` | `runtime/self_improve.db` | → `triage.db` (codespace/self_improve) |
| `guppy.db` | `runtime/guppy.db` | Empty/abandoned — deleted |
| `model_roles.db` | `USER_DATA_DIR/model_roles.db` | → `guppy_main.db` (routes_model_roles) |

---

## DB Access Module

All consolidated access flows through `src/guppy/db/`:

- `get_main_db()` — thread-local connection to `guppy_main.db`
- `get_memory_db()` — thread-local connection to `guppy_memory.db`
- `get_triage_db()` — connection to `runtime/triage.db` (codespace only)
- All connections: WAL mode, `foreign_keys=ON`, `busy_timeout=5000`

---

## Open Issues

- Alembic migrations for Tranches A–H tables are tracked under Tranche I
- `library_storage.py` (launcher_application) still uses its own `LIBRARY_DB_PATH` (legacy path) — to be redirected in a follow-up
