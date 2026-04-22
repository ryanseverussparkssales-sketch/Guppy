from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from utils.db_utils import open_db as _open_db

from .memory_pipeline_support import (
    add_pipeline_item_record as _add_pipeline_item_record,
    ensure_pipeline_schema,
    get_pipeline_items_text as _get_pipeline_items_text,
    get_revenue_dashboard_data_map as _get_revenue_dashboard_data_map,
    log_pipeline_activity_record as _log_pipeline_activity_record,
    update_pipeline_item_record as _update_pipeline_item_record,
)
from .memory_support import normalize_text


def _normalize_workspace_name(workspace_name: str | None) -> str:
    return str(workspace_name or "").strip()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def journal_event(conn: sqlite3.Connection, event_type: str, payload: dict) -> None:
    conn.execute(
        "INSERT INTO memory_events (event_type,payload,timestamp) VALUES (?,?,?)",
        (event_type, json.dumps(payload, ensure_ascii=True), datetime.now().isoformat()),
    )


def open_memory_connection(db_path: Path) -> sqlite3.Connection:
    conn = _open_db(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT DEFAULT 'general',
        key TEXT,
        value TEXT,
        normalized_key TEXT,
        normalized_value TEXT,
        created TEXT,
        updated TEXT
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        normalized_content TEXT,
        timestamp TEXT
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        company TEXT,
        email TEXT,
        phone TEXT,
        notes TEXT,
        last_contact TEXT
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT,
        status TEXT DEFAULT 'pending',
        due_date TEXT,
        created TEXT
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS memory_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT,
        payload TEXT,
        timestamp TEXT
    )"""
    )
    ensure_pipeline_schema(conn)

    ensure_column(conn, "facts", "normalized_key", "TEXT")
    ensure_column(conn, "facts", "normalized_value", "TEXT")
    ensure_column(conn, "conversations", "normalized_content", "TEXT")
    ensure_column(conn, "conversations", "workspace_name", "TEXT")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_updated ON facts(updated DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_norm_key ON facts(normalized_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_norm_value ON facts(normalized_value)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_session_id ON conversations(session_id, id DESC)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conv_workspace_session ON conversations(workspace_name, session_id, id DESC)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON memory_events(timestamp DESC)")
    conn.commit()
    return conn


def remember_fact(db_path: Path, key: str, value: str, category: str = "general") -> str:
    conn = open_memory_connection(db_path)
    try:
        now = datetime.now().isoformat()
        normalized_key = normalize_text(key)
        normalized_value = normalize_text(value)
        existing = conn.execute("SELECT id FROM facts WHERE key=?", (key,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE facts SET value=?, category=?, normalized_key=?, normalized_value=?, updated=? WHERE key=?",
                (value, category, normalized_key, normalized_value, now, key),
            )
            journal_event(conn, "remember.update", {"key": key, "category": category})
            conn.commit()
            return f"Updated memory: [{category}] {key} = {value}"

        conn.execute(
            "INSERT INTO facts (category,key,value,normalized_key,normalized_value,created,updated) VALUES (?,?,?,?,?,?,?)",
            (category, key, value, normalized_key, normalized_value, now, now),
        )
        journal_event(conn, "remember.insert", {"key": key, "category": category})
        conn.commit()
        return f"Remembered: [{category}] {key} = {value}"
    finally:
        conn.close()


def recall_facts(db_path: Path, query: str = "", category: str = "") -> str:
    conn = open_memory_connection(db_path)
    try:
        if category:
            rows = conn.execute(
                "SELECT category,key,value,updated,COALESCE(normalized_key,''),COALESCE(normalized_value,'') "
                "FROM facts WHERE category=?",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT category,key,value,updated,COALESCE(normalized_key,''),COALESCE(normalized_value,'') "
                "FROM facts"
            ).fetchall()

        if query:
            query_norm = normalize_text(query)
            scored = []
            for cat, key, value, updated, nkey, nvalue in rows:
                score = 0
                if query_norm == nkey:
                    score += 100
                if query_norm and query_norm in nkey:
                    score += 60
                if query_norm and query_norm in nvalue:
                    score += 40
                tokens = [t for t in query_norm.split(" ") if len(t) > 2]
                if tokens:
                    token_hits = sum(1 for token in tokens if token in nkey or token in nvalue)
                    score += token_hits * 5
                if score > 0:
                    scored.append((score, updated, cat, key, value))
            scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
            rows_out = [(cat, key, value, updated) for _score, updated, cat, key, value in scored[:20]]
        else:
            rows_sorted = sorted(rows, key=lambda row: row[3], reverse=True)
            rows_out = [(row[0], row[1], row[2], row[3]) for row in rows_sorted[:30]]

        if not rows_out:
            return "Nothing found in memory."
        return "\n".join(f"[{row[0]}] {row[1]}: {row[2]} (updated {row[3][:10]})" for row in rows_out)
    finally:
        conn.close()


def forget_fact(db_path: Path, key: str) -> str:
    conn = open_memory_connection(db_path)
    try:
        conn.execute("DELETE FROM facts WHERE key=?", (key,))
        journal_event(conn, "forget", {"key": key})
        conn.commit()
        return f"Forgotten: {key}"
    finally:
        conn.close()


def save_conversation_message(
    db_path: Path,
    session_id: str,
    role: str,
    content: str,
    workspace_name: str | None = None,
) -> None:
    conn = open_memory_connection(db_path)
    try:
        normalized_workspace = _normalize_workspace_name(workspace_name)
        conn.execute(
            "INSERT INTO conversations (session_id,workspace_name,role,content,normalized_content,timestamp) VALUES (?,?,?,?,?,?)",
            (
                session_id,
                normalized_workspace or None,
                role,
                content,
                normalize_text(content),
                datetime.now().isoformat(),
            ),
        )
        journal_event(
            conn,
            "conversation.save",
            {
                "session_id": session_id,
                "role": role,
                "workspace_name": normalized_workspace,
            },
        )
        conn.commit()
    finally:
        conn.close()


def load_recent_history_records(
    db_path: Path,
    session_id: str | None = None,
    limit: int = 20,
    workspace_name: str | None = None,
) -> list[dict[str, str]]:
    conn = open_memory_connection(db_path)
    try:
        normalized_workspace = _normalize_workspace_name(workspace_name)
        if session_id:
            if normalized_workspace:
                rows = conn.execute(
                    "SELECT role,content FROM conversations WHERE session_id=? AND COALESCE(workspace_name, '')=? ORDER BY id DESC LIMIT ?",
                    (session_id, normalized_workspace, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT role,content FROM conversations WHERE session_id=? ORDER BY id DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
        else:
            if normalized_workspace:
                rows = conn.execute(
                    "SELECT role,content FROM conversations WHERE COALESCE(workspace_name, '')=? ORDER BY id DESC LIMIT ?",
                    (normalized_workspace, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT role,content FROM conversations ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]
    finally:
        conn.close()


def get_session_summary_text(
    db_path: Path,
    limit: int = 5,
    workspace_name: str | None = None,
) -> str:
    conn = open_memory_connection(db_path)
    try:
        normalized_workspace = _normalize_workspace_name(workspace_name)
        if normalized_workspace:
            rows = conn.execute(
                "SELECT DISTINCT session_id, MIN(timestamp), COUNT(*) FROM conversations WHERE COALESCE(workspace_name, '')=? GROUP BY session_id ORDER BY MIN(timestamp) DESC LIMIT ?",
                (normalized_workspace, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT session_id, MIN(timestamp), COUNT(*) FROM conversations GROUP BY session_id ORDER BY MIN(timestamp) DESC LIMIT ?",
                (limit,),
            ).fetchall()
        if not rows:
            return "No previous sessions found."
        return "\n".join(f"Session {row[0][:8]}... - {row[1][:10]} - {row[2]} messages" for row in rows)
    finally:
        conn.close()


def save_contact_record(
    db_path: Path,
    name: str,
    company: str = "",
    email: str = "",
    phone: str = "",
    notes: str = "",
) -> str:
    conn = open_memory_connection(db_path)
    try:
        now = datetime.now().isoformat()
        existing = conn.execute("SELECT id FROM contacts WHERE name=?", (name,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE contacts SET company=?,email=?,phone=?,notes=?,last_contact=? WHERE name=?",
                (company, email, phone, notes, now, name),
            )
            journal_event(conn, "contact.update", {"name": name})
            conn.commit()
            return f"Contact updated: {name}"

        conn.execute(
            "INSERT INTO contacts (name,company,email,phone,notes,last_contact) VALUES (?,?,?,?,?,?)",
            (name, company, email, phone, notes, now),
        )
        journal_event(conn, "contact.insert", {"name": name})
        conn.commit()
        return f"Contact saved: {name}"
    finally:
        conn.close()


def get_contacts_text(db_path: Path, search: str = "") -> str:
    conn = open_memory_connection(db_path)
    try:
        if search:
            rows = conn.execute(
                "SELECT name,company,email,phone,notes,last_contact FROM contacts WHERE name LIKE ? OR company LIKE ?",
                (f"%{search}%", f"%{search}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT name,company,email,phone,notes,last_contact FROM contacts ORDER BY last_contact DESC"
            ).fetchall()
        if not rows:
            return "No contacts found."
        return "\n".join(
            f"{row[0]} | {row[1]} | {row[2]} | Last: {row[5][:10] if row[5] else 'Never'}" for row in rows
        )
    finally:
        conn.close()


def add_task_record(db_path: Path, task: str, due_date: str = "") -> str:
    conn = open_memory_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO tasks (task,due_date,created) VALUES (?,?,?)",
            (task, due_date, datetime.now().isoformat()),
        )
        journal_event(conn, "task.add", {"task": task, "due_date": due_date})
        conn.commit()
        return f"Task added: {task}"
    finally:
        conn.close()


def get_tasks_text(db_path: Path, status: str = "pending") -> str:
    conn = open_memory_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT id,task,due_date,created FROM tasks WHERE status=? ORDER BY created DESC",
            (status,),
        ).fetchall()
        if not rows:
            return f"No {status} tasks."
        return "\n".join(f"[{row[0]}] {row[1]}{f' - due {row[2]}' if row[2] else ''}" for row in rows)
    finally:
        conn.close()


def complete_task_record(db_path: Path, task_id: int) -> str:
    conn = open_memory_connection(db_path)
    try:
        conn.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
        journal_event(conn, "task.complete", {"task_id": task_id})
        conn.commit()
        return f"Task {task_id} marked complete."
    finally:
        conn.close()


def add_pipeline_item_record(
    db_path: Path,
    title: str,
    company: str = "",
    contact_name: str = "",
    stage: str = "new_lead",
    value: float = 0.0,
    confidence: int = 30,
    next_action: str = "",
    due_date: str = "",
    source: str = "",
    notes: str = "",
) -> str:
    conn = open_memory_connection(db_path)
    try:
        result = _add_pipeline_item_record(
            conn,
            journal_event,
            title,
            company,
            contact_name,
            stage,
            value,
            confidence,
            next_action,
            due_date,
            source,
            notes,
        )
        conn.commit()
        return result
    finally:
        conn.close()


def update_pipeline_item_record(
    db_path: Path,
    item_id: int,
    stage: str = "",
    value: float | None = None,
    confidence: int | None = None,
    next_action: str | None = None,
    due_date: str | None = None,
    status: str | None = None,
    notes: str | None = None,
) -> str:
    conn = open_memory_connection(db_path)
    try:
        result = _update_pipeline_item_record(
            conn,
            journal_event,
            item_id,
            stage,
            value,
            confidence,
            next_action,
            due_date,
            status,
            notes,
        )
        conn.commit()
        return result
    finally:
        conn.close()


def log_pipeline_activity_record(db_path: Path, item_id: int, note: str, activity_type: str = "note") -> str:
    conn = open_memory_connection(db_path)
    try:
        result = _log_pipeline_activity_record(conn, journal_event, item_id, note, activity_type)
        conn.commit()
        return result
    finally:
        conn.close()


def get_pipeline_items_text(db_path: Path, stage: str = "", status: str = "open", limit: int = 30) -> str:
    conn = open_memory_connection(db_path)
    try:
        return _get_pipeline_items_text(conn, stage, status, limit)
    finally:
        conn.close()


def get_revenue_dashboard_data_map(db_path: Path) -> dict:
    conn = open_memory_connection(db_path)
    try:
        return _get_revenue_dashboard_data_map(conn)
    finally:
        conn.close()


def get_session_summaries_text(db_path: Path, limit: int = 3) -> str:
    conn = open_memory_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT key, value, updated FROM facts WHERE category='session_summary' ORDER BY updated DESC LIMIT ?",
            (limit,),
        ).fetchall()
        if not rows:
            return ""
        lines = ["PREVIOUS SESSION SUMMARIES:"]
        for _key, value, updated in rows:
            lines.append(f"\n[{updated[:10]}]")
            lines.append(value)
        return "\n".join(lines)
    finally:
        conn.close()


def get_recent_messages_text(
    db_path: Path,
    exclude_session: str | None = None,
    limit: int = 10,
    workspace_name: str | None = None,
) -> str:
    conn = open_memory_connection(db_path)
    try:
        normalized_workspace = _normalize_workspace_name(workspace_name)
        prior_session = ""
        scoped_workspace = ""

        if normalized_workspace:
            if exclude_session:
                row = conn.execute(
                    "SELECT session_id FROM conversations WHERE session_id != ? AND COALESCE(workspace_name, '')=? ORDER BY id DESC LIMIT 1",
                    (exclude_session, normalized_workspace),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT session_id FROM conversations WHERE COALESCE(workspace_name, '')=? ORDER BY id DESC LIMIT 1",
                    (normalized_workspace,),
                ).fetchone()
            if row:
                prior_session = str(row[0] or "")
                scoped_workspace = normalized_workspace
            else:
                if exclude_session:
                    row = conn.execute(
                        "SELECT session_id FROM conversations WHERE session_id != ? AND COALESCE(workspace_name, '')='' ORDER BY id DESC LIMIT 1",
                        (exclude_session,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT session_id FROM conversations WHERE COALESCE(workspace_name, '')='' ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                if row:
                    prior_session = str(row[0] or "")
        else:
            if exclude_session:
                row = conn.execute(
                    "SELECT session_id FROM conversations WHERE session_id != ? ORDER BY id DESC LIMIT 1",
                    (exclude_session,),
                ).fetchone()
            else:
                row = conn.execute("SELECT session_id FROM conversations ORDER BY id DESC LIMIT 1").fetchone()
            if row:
                prior_session = str(row[0] or "")

        if not prior_session:
            return ""

        if scoped_workspace:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM conversations WHERE session_id = ? AND COALESCE(workspace_name, '')=? ORDER BY id DESC LIMIT ?",
                (prior_session, scoped_workspace, limit),
            ).fetchall()
        elif normalized_workspace:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM conversations WHERE session_id = ? AND COALESCE(workspace_name, '')='' ORDER BY id DESC LIMIT ?",
                (prior_session, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (prior_session, limit),
            ).fetchall()

        if not rows:
            return ""

        rows = list(reversed(rows))
        date_str = rows[0][2][:10]
        lines = [f"LAST SESSION ({date_str}):"]
        for role, content, _timestamp in rows:
            label = "Ryan" if role == "user" else "Guppy"
            snippet = content[:250] + "..." if len(content) > 250 else content
            lines.append(f"  {label}: {snippet}")
        return "\n".join(lines)
    finally:
        conn.close()


def get_workspace_memory_snapshot(db_path: Path, workspace_name: str | None = None) -> dict[str, object]:
    conn = open_memory_connection(db_path)
    try:
        normalized_workspace = _normalize_workspace_name(workspace_name)

        def _snapshot_for_scope(scope: str) -> dict[str, object]:
            row = conn.execute(
                "SELECT COUNT(*), COUNT(DISTINCT session_id), MAX(timestamp) "
                "FROM conversations WHERE COALESCE(workspace_name, '')=?",
                (scope,),
            ).fetchone()
            message_count = int((row[0] if row else 0) or 0)
            session_count = int((row[1] if row else 0) or 0)
            latest_timestamp = str((row[2] if row else "") or "")
            latest_row = conn.execute(
                "SELECT session_id, role, content, timestamp "
                "FROM conversations WHERE COALESCE(workspace_name, '')=? "
                "ORDER BY id DESC LIMIT 1",
                (scope,),
            ).fetchone()
            if latest_row:
                latest_session_id = str(latest_row[0] or "")
                latest_role = str(latest_row[1] or "")
                latest_message = str(latest_row[2] or "")
                latest_timestamp = str(latest_row[3] or latest_timestamp or "")
            else:
                latest_session_id = ""
                latest_role = ""
                latest_message = ""
            return {
                "workspace_name": normalized_workspace,
                "message_count": message_count,
                "session_count": session_count,
                "latest_timestamp": latest_timestamp,
                "latest_session_id": latest_session_id,
                "latest_role": latest_role,
                "latest_message": latest_message,
                "used_legacy_fallback": False,
            }

        if normalized_workspace:
            scoped = _snapshot_for_scope(normalized_workspace)
            if int(scoped.get("message_count", 0) or 0) > 0:
                return scoped
            legacy = _snapshot_for_scope("")
            legacy["workspace_name"] = normalized_workspace
            legacy["used_legacy_fallback"] = bool(int(legacy.get("message_count", 0) or 0) > 0)
            return legacy
        return _snapshot_for_scope("")
    finally:
        conn.close()
