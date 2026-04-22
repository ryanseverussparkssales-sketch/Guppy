from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from utils.db_utils import open_db as _open_db

from .memory_support import PIPELINE_STAGES, normalize_stage, normalize_text, safe_float, safe_int


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
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pipeline_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        company TEXT,
        contact_name TEXT,
        stage TEXT DEFAULT 'new_lead',
        value REAL DEFAULT 0,
        confidence INTEGER DEFAULT 30,
        next_action TEXT,
        due_date TEXT,
        status TEXT DEFAULT 'open',
        source TEXT,
        notes TEXT,
        created TEXT,
        updated TEXT
    )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pipeline_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        activity_type TEXT,
        note TEXT,
        timestamp TEXT
    )"""
    )

    ensure_column(conn, "facts", "normalized_key", "TEXT")
    ensure_column(conn, "facts", "normalized_value", "TEXT")
    ensure_column(conn, "conversations", "normalized_content", "TEXT")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_updated ON facts(updated DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_norm_key ON facts(normalized_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_norm_value ON facts(normalized_value)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_session_id ON conversations(session_id, id DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON memory_events(timestamp DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_stage ON pipeline_items(stage, updated DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_status ON pipeline_items(status, updated DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_due ON pipeline_items(due_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_activity_item ON pipeline_activity(item_id, timestamp DESC)")
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


def save_conversation_message(db_path: Path, session_id: str, role: str, content: str) -> None:
    conn = open_memory_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO conversations (session_id,role,content,normalized_content,timestamp) VALUES (?,?,?,?,?)",
            (session_id, role, content, normalize_text(content), datetime.now().isoformat()),
        )
        journal_event(conn, "conversation.save", {"session_id": session_id, "role": role})
        conn.commit()
    finally:
        conn.close()


def load_recent_history_records(db_path: Path, session_id: str | None = None, limit: int = 20) -> list[dict[str, str]]:
    conn = open_memory_connection(db_path)
    try:
        if session_id:
            rows = conn.execute(
                "SELECT role,content FROM conversations WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT role,content FROM conversations ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]
    finally:
        conn.close()


def get_session_summary_text(db_path: Path, limit: int = 5) -> str:
    conn = open_memory_connection(db_path)
    try:
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
        now = datetime.now().isoformat()
        stage_norm = normalize_stage(stage)
        conf = max(0, min(100, safe_int(confidence, 30)))
        item_value = max(0.0, safe_float(value, 0.0))
        cur = conn.execute(
            """
            INSERT INTO pipeline_items
            (title, company, contact_name, stage, value, confidence, next_action, due_date, source, notes, created, updated)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                title,
                company,
                contact_name,
                stage_norm,
                item_value,
                conf,
                next_action,
                due_date,
                source,
                notes,
                now,
                now,
            ),
        )
        item_id = cur.lastrowid
        journal_event(conn, "pipeline.add", {"item_id": item_id, "title": title, "stage": stage_norm})
        conn.execute(
            "INSERT INTO pipeline_activity (item_id,activity_type,note,timestamp) VALUES (?,?,?,?)",
            (item_id, "create", f"Created pipeline item at stage {stage_norm}", now),
        )
        conn.commit()
        return f"Pipeline item added: [{item_id}] {title} ({stage_norm})"
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
        row = conn.execute(
            "SELECT id, stage, value, confidence, status FROM pipeline_items WHERE id=?",
            (item_id,),
        ).fetchone()
        if not row:
            return f"Pipeline item not found: {item_id}"

        stage_new = normalize_stage(stage) if stage else row[1]
        value_new = max(0.0, safe_float(value, row[2])) if value is not None else row[2]
        conf_new = max(0, min(100, safe_int(confidence, row[3]))) if confidence is not None else row[3]
        status_new = (status or row[4] or "open").strip().lower()
        if status_new not in {"open", "won", "lost", "archived"}:
            status_new = "open"

        now = datetime.now().isoformat()
        conn.execute(
            """
            UPDATE pipeline_items
            SET stage=?, value=?, confidence=?, next_action=COALESCE(?, next_action),
                due_date=COALESCE(?, due_date), status=?, notes=COALESCE(?, notes), updated=?
            WHERE id=?
            """,
            (stage_new, value_new, conf_new, next_action, due_date, status_new, notes, now, item_id),
        )
        journal_event(conn, "pipeline.update", {"item_id": item_id, "stage": stage_new, "status": status_new})
        conn.execute(
            "INSERT INTO pipeline_activity (item_id,activity_type,note,timestamp) VALUES (?,?,?,?)",
            (item_id, "update", f"Stage={stage_new}, status={status_new}, confidence={conf_new}", now),
        )
        conn.commit()
        return f"Pipeline item updated: [{item_id}] stage={stage_new}, status={status_new}"
    finally:
        conn.close()


def log_pipeline_activity_record(db_path: Path, item_id: int, note: str, activity_type: str = "note") -> str:
    conn = open_memory_connection(db_path)
    try:
        exists = conn.execute("SELECT id FROM pipeline_items WHERE id=?", (item_id,)).fetchone()
        if not exists:
            return f"Pipeline item not found: {item_id}"
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO pipeline_activity (item_id,activity_type,note,timestamp) VALUES (?,?,?,?)",
            (item_id, activity_type or "note", note, now),
        )
        conn.execute("UPDATE pipeline_items SET updated=? WHERE id=?", (now, item_id))
        journal_event(conn, "pipeline.activity", {"item_id": item_id, "activity_type": activity_type})
        conn.commit()
        return f"Pipeline activity logged for item {item_id}."
    finally:
        conn.close()


def get_pipeline_items_text(db_path: Path, stage: str = "", status: str = "open", limit: int = 30) -> str:
    conn = open_memory_connection(db_path)
    try:
        params = []
        where = []
        if stage:
            where.append("stage=?")
            params.append(normalize_stage(stage))
        if status:
            where.append("status=?")
            params.append(status.strip().lower())

        sql = "SELECT id,title,company,stage,value,confidence,next_action,due_date,status,updated FROM pipeline_items"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated DESC LIMIT ?"
        params.append(max(1, min(100, safe_int(limit, 30))))

        rows = conn.execute(sql, tuple(params)).fetchall()
        if not rows:
            return "No pipeline items found."

        lines = []
        for row in rows:
            lines.append(
                f"[{row[0]}] {row[1]} | {row[2] or '-'} | {row[3]} | ${row[4]:,.0f} | conf {row[5]}%"
                + (f" | next: {row[6]}" if row[6] else "")
                + (f" | due: {row[7]}" if row[7] else "")
            )
        return "\n".join(lines)
    finally:
        conn.close()


def get_revenue_dashboard_data_map(db_path: Path) -> dict:
    conn = open_memory_connection(db_path)
    try:
        open_items = conn.execute(
            "SELECT id,title,stage,value,confidence,next_action,due_date,updated FROM pipeline_items WHERE status='open'"
        ).fetchall()
        all_rows = conn.execute("SELECT stage,status,value,confidence FROM pipeline_items").fetchall()

        stage_counts = {stage: 0 for stage in PIPELINE_STAGES}
        status_counts = {"open": 0, "won": 0, "lost": 0, "archived": 0}
        total_pipeline = 0.0
        weighted_pipeline = 0.0

        for stage, status, value, confidence in all_rows:
            if stage in stage_counts:
                stage_counts[stage] += 1
            status_counts[status if status in status_counts else "open"] += 1
            if status == "open":
                val = safe_float(value)
                conf = max(0, min(100, safe_int(confidence, 0)))
                total_pipeline += val
                weighted_pipeline += val * (conf / 100.0)

        top_open = sorted(
            [
                {
                    "id": row[0],
                    "title": row[1],
                    "stage": row[2],
                    "value": safe_float(row[3]),
                    "confidence": safe_int(row[4], 0),
                    "next_action": row[5] or "",
                    "due_date": row[6] or "",
                    "updated": row[7],
                }
                for row in open_items
            ],
            key=lambda item: (item["value"] * (item["confidence"] / 100.0), item["updated"]),
            reverse=True,
        )[:7]

        return {
            "generated_at": datetime.now().isoformat(),
            "open_count": status_counts["open"],
            "won_count": status_counts["won"],
            "lost_count": status_counts["lost"],
            "archived_count": status_counts["archived"],
            "stage_counts": stage_counts,
            "total_pipeline": round(total_pipeline, 2),
            "weighted_pipeline": round(weighted_pipeline, 2),
            "top_open": top_open,
            "due_soon": [item for item in top_open if item["due_date"]],
        }
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


def get_recent_messages_text(db_path: Path, exclude_session: str | None = None, limit: int = 10) -> str:
    conn = open_memory_connection(db_path)
    try:
        if exclude_session:
            row = conn.execute(
                "SELECT session_id FROM conversations WHERE session_id != ? ORDER BY id DESC LIMIT 1",
                (exclude_session,),
            ).fetchone()
        else:
            row = conn.execute("SELECT session_id FROM conversations ORDER BY id DESC LIMIT 1").fetchone()

        if not row:
            return ""

        prior_session = row[0]
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
