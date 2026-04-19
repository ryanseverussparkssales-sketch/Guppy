# KPI Instrumentation Spec — Library Feature

Last updated: April 18, 2026

## Overview

This spec defines the 5 product KPIs for the Library feature, the instrumentation points for each, and the JSON event schemas. All events are appended to the existing `runtime/agent_performance.jsonl` log (append-only JSONL, no new dependencies).

---

## KPI 1 — Library Attach Rate

**Definition:** Percentage of chat send actions that include at least one active Library context item.

### Instrumentation Point

| Field | Value |
|---|---|
| File | `src/guppy/launcher_application/library_workflow.py` |
| Function | `compose_library_aware_message(cmd, active_items)` |
| Signal/condition | `items` list is non-empty after filtering |

Fire one event per chat send, regardless of whether items are attached — the `attached` field distinguishes the outcome.

### Event Schema

```json
{
  "event": "library.chat_send",
  "ts": "2026-04-18T14:23:01Z",
  "workspace_name": "my-workspace",
  "attached": true,
  "item_count": 2,
  "item_titles": ["Design Notes", "API Draft"],
  "item_kinds": ["note", "file"]
}
```

### Review Threshold

| Signal | Value |
|---|---|
| Healthy | `attached == true` in ≥ 30 % of `library.chat_send` events within 14 days of first use |
| Needs attention | < 10 % attach rate after 30 days — indicates Library is present but users are not connecting it to chat |

---

## KPI 2 — Default Source Pin Rate

**Definition:** Percentage of active workspaces that have a default Library source pinned.

### Instrumentation Point

| Field | Value |
|---|---|
| File | `src/guppy/launcher_application/library_workflow.py` |
| Function | `_save_workspace_defaults(defaults)` |
| Signal/condition | A new workspace key is written with a non-empty title value |

Fire one `library.default_pinned` event when a workspace default is set, and one `library.default_cleared` event when an entry is removed.

### Event Schema

```json
{
  "event": "library.default_pinned",
  "ts": "2026-04-18T14:25:00Z",
  "workspace_name": "my-workspace",
  "item_title": "Design Notes"
}
```

```json
{
  "event": "library.default_cleared",
  "ts": "2026-04-18T14:30:00Z",
  "workspace_name": "my-workspace"
}
```

### Review Threshold

| Signal | Value |
|---|---|
| Healthy | At least one workspace has a default pinned within 7 days of Library first use |
| Needs attention | Zero defaults set after 30 days — the pin affordance is not discoverable or not trusted |

---

## KPI 3 — Context Reuse in Chat

**Definition:** Number of chat messages per session where Library context was prepended into the outgoing message payload.

### Instrumentation Point

| Field | Value |
|---|---|
| File | `src/guppy/launcher_application/library_workflow.py` |
| Function | `compose_library_aware_message(cmd, active_items)` |
| Signal/condition | Return value differs from the raw `command_text` (i.e., `items` was non-empty) |

This event is a subset of `library.chat_send` with `attached == true`, but records the number of items included so reuse depth is visible.

### Event Schema

```json
{
  "event": "library.context_reused",
  "ts": "2026-04-18T14:23:01Z",
  "workspace_name": "my-workspace",
  "items_prepended": 2,
  "item_titles": ["Design Notes", "API Draft"]
}
```

### Review Threshold

| Signal | Value |
|---|---|
| Healthy | Average `items_prepended` ≥ 1.2 across `library.context_reused` events — users are regularly attaching at least one item |
| Needs attention | Average drops below 1.0 or total event count stagnates — users send attached messages once and do not repeat |

---

## KPI 4 — Root Approval Rate

**Definition:** Percentage of root-save attempts that complete successfully through the validation gate.

### Instrumentation Point

| Field | Value |
|---|---|
| File | `src/guppy/launcher_application/library_workflow.py` (validation gatekeeping), `src/guppy/launcher_application/library_storage.py` |
| Function | Call site of `upsert_approved_root(...)` after gate checks pass |
| Signal/condition | Fire `library.root_save_attempted` at submission; fire `library.root_save_approved` or `library.root_save_rejected` on resolution |

### Event Schema

```json
{
  "event": "library.root_save_approved",
  "ts": "2026-04-18T14:26:00Z",
  "workspace_name": "my-workspace",
  "root_path": "C:/Users/Ryan/Documents/ProjectDocs"
}
```

```json
{
  "event": "library.root_save_rejected",
  "ts": "2026-04-18T14:26:01Z",
  "workspace_name": "my-workspace",
  "rejection_reason": "path_not_found"
}
```

### Review Threshold

| Signal | Value |
|---|---|
| Healthy | ≥ 80 % of `library.root_save_attempted` events resolve to `library.root_save_approved` |
| Needs attention | > 25 % rejection rate — indicates UX friction in root selection or path validation errors that confuse users |

---

## KPI 5 — Workspace Default Persistence (Load Success)

**Definition:** Percentage of workspace switches where a previously pinned Library default was successfully loaded back into the active context.

### Instrumentation Point

| Field | Value |
|---|---|
| File | `src/guppy/launcher_application/library_workflow.py` |
| Function | `_load_workspace_defaults()` called from `apply_library_payload(...)` or workspace-switch handler |
| Signal/condition | Fire `library.default_loaded` when a workspace default key is present in the loaded defaults dict and successfully passed to `set_active_context_items` via `sync_assistant_library_context` |

### Event Schema

```json
{
  "event": "library.default_loaded",
  "ts": "2026-04-18T14:28:00Z",
  "workspace_name": "my-workspace",
  "item_title": "Design Notes",
  "load_source": "workspace_defaults_file"
}
```

```json
{
  "event": "library.default_load_miss",
  "ts": "2026-04-18T14:28:01Z",
  "workspace_name": "my-workspace",
  "reason": "no_default_configured"
}
```

### Review Threshold

| Signal | Value |
|---|---|
| Healthy | `library.default_loaded` fires on ≥ 90 % of workspace switches for workspaces that have a pinned default |
| Needs attention | < 80 % load success — indicates the `runtime/library_workspace_defaults.json` persistence path is unreliable |

---

## Instrumentation Implementation Notes

### Log Target

Append all events to `runtime/agent_performance.jsonl` (same pattern as existing runtime telemetry). Each line is a complete JSON object followed by a newline.

```python
import json, datetime
from pathlib import Path

_PERF_LOG = Path("runtime/agent_performance.jsonl")

def _emit_library_event(payload: dict) -> None:
    payload.setdefault("ts", datetime.datetime.utcnow().isoformat() + "Z")
    try:
        with _PERF_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        pass
```

### Call Sites Summary

| KPI | Module | Function | Event name(s) |
|---|---|---|---|
| Attach Rate | `library_workflow.py` | `compose_library_aware_message` | `library.chat_send` |
| Default Pin Rate | `library_workflow.py` | `_save_workspace_defaults` | `library.default_pinned`, `library.default_cleared` |
| Context Reuse | `library_workflow.py` | `compose_library_aware_message` | `library.context_reused` |
| Root Approval | `library_workflow.py` + `library_storage.py` | root-save gate + `upsert_approved_root` | `library.root_save_attempted`, `library.root_save_approved`, `library.root_save_rejected` |
| Default Persistence | `library_workflow.py` | `_load_workspace_defaults` + `sync_assistant_library_context` | `library.default_loaded`, `library.default_load_miss` |

### No New Dependencies

All instrumentation uses only `json`, `datetime`, and `pathlib` from the standard library. No analytics SDK, no network calls, no new packages.
