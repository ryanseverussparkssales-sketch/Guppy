"""
🎩 Guppy Memory Module
Persistent memory using SQLite — zero extra dependencies.
"""

import sqlite3, json, os
import re
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / "Guppy" / "guppy_memory.db"
PIPELINE_STAGES = [
    "new_lead",
    "contacted",
    "qualified",
    "proposal",
    "negotiation",
    "won",
    "lost",
]


def _normalize_text(value: str) -> str:
    """Create a stable search projection from markdown-heavy content."""
    text = (value or "").replace("\r\n", "\n")
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[`*_>#\[\]()]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _journal_event(conn: sqlite3.Connection, event_type: str, payload: dict) -> None:
    conn.execute(
        "INSERT INTO memory_events (event_type,payload,timestamp) VALUES (?,?,?)",
        (event_type, json.dumps(payload, ensure_ascii=True), datetime.now().isoformat()),
    )


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_stage(stage: str) -> str:
    candidate = _normalize_text(stage).replace(" ", "_")
    return candidate if candidate in PIPELINE_STAGES else "new_lead"

def _conn():
    """Get database connection with proper setup. Connections are managed by SQLite's built-in pooling."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("""CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT DEFAULT 'general',
        key TEXT,
        value TEXT,
        normalized_key TEXT,
        normalized_value TEXT,
        created TEXT,
        updated TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        normalized_content TEXT,
        timestamp TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        company TEXT,
        email TEXT,
        phone TEXT,
        notes TEXT,
        last_contact TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task TEXT,
        status TEXT DEFAULT 'pending',
        due_date TEXT,
        created TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS memory_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT,
        payload TEXT,
        timestamp TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS pipeline_items (
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
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS pipeline_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        activity_type TEXT,
        note TEXT,
        timestamp TEXT
    )""")

    _ensure_column(conn, "facts", "normalized_key", "TEXT")
    _ensure_column(conn, "facts", "normalized_value", "TEXT")
    _ensure_column(conn, "conversations", "normalized_content", "TEXT")

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

# ── Facts ─────────────────────────────────────────────────

def remember(key: str, value: str, category: str = "general") -> str:
    conn = _conn()
    try:
        now = datetime.now().isoformat()
        normalized_key = _normalize_text(key)
        normalized_value = _normalize_text(value)
        existing = conn.execute("SELECT id FROM facts WHERE key=?", (key,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE facts SET value=?, category=?, normalized_key=?, normalized_value=?, updated=? WHERE key=?",
                (value, category, normalized_key, normalized_value, now, key),
            )
            _journal_event(conn, "remember.update", {"key": key, "category": category})
            conn.commit()
            return f"Updated memory: [{category}] {key} = {value}"
        else:
            conn.execute(
                "INSERT INTO facts (category,key,value,normalized_key,normalized_value,created,updated) VALUES (?,?,?,?,?,?,?)",
                (category, key, value, normalized_key, normalized_value, now, now),
            )
            _journal_event(conn, "remember.insert", {"key": key, "category": category})
            conn.commit()
            return f"Remembered: [{category}] {key} = {value}"
    finally:
        conn.close()

def recall(query: str = "", category: str = "") -> str:
    conn = _conn()
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
            query_norm = _normalize_text(query)
            scored = []
            for row in rows:
                cat, key, value, updated, nkey, nvalue = row
                score = 0
                if query_norm == nkey:
                    score += 100
                if query_norm and query_norm in nkey:
                    score += 60
                if query_norm and query_norm in nvalue:
                    score += 40
                tokens = [t for t in query_norm.split(" ") if len(t) > 2]
                if tokens:
                    token_hits = sum(1 for t in tokens if t in nkey or t in nvalue)
                    score += token_hits * 5
                if score > 0:
                    scored.append((score, updated, cat, key, value))

            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            rows_out = [(cat, key, value, updated) for _score, updated, cat, key, value in scored[:20]]
        else:
            rows_sorted = sorted(rows, key=lambda r: r[3], reverse=True)
            rows_out = [(r[0], r[1], r[2], r[3]) for r in rows_sorted[:30]]

        if not rows_out:
            return "Nothing found in memory."
        return "\n".join(f"[{r[0]}] {r[1]}: {r[2]} (updated {r[3][:10]})" for r in rows_out)
    finally:
        conn.close()

def forget(key: str) -> str:
    conn = _conn()
    try:
        conn.execute("DELETE FROM facts WHERE key=?", (key,))
        _journal_event(conn, "forget", {"key": key})
        conn.commit()
        return f"Forgotten: {key}"
    finally:
        conn.close()

# ── Conversation history ───────────────────────────────────

def save_message(session_id: str, role: str, content: str):
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO conversations (session_id,role,content,normalized_content,timestamp) VALUES (?,?,?,?,?)",
            (session_id, role, content, _normalize_text(content), datetime.now().isoformat()),
        )
        _journal_event(conn, "conversation.save", {"session_id": session_id, "role": role})
        conn.commit()
    finally:
        conn.close()

def load_recent_history(session_id: str = None, limit: int = 20) -> list:
    conn = _conn()
    try:
        if session_id:
            rows = conn.execute("SELECT role,content FROM conversations WHERE session_id=? ORDER BY id DESC LIMIT ?",
                                 (session_id, limit)).fetchall()
        else:
            rows = conn.execute("SELECT role,content FROM conversations ORDER BY id DESC LIMIT ?",
                                 (limit,)).fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    finally:
        conn.close()

def get_session_summary(limit: int = 5) -> str:
    conn = _conn()
    try:
        rows = conn.execute("SELECT DISTINCT session_id, MIN(timestamp), COUNT(*) FROM conversations GROUP BY session_id ORDER BY MIN(timestamp) DESC LIMIT ?",
                             (limit,)).fetchall()
        if not rows: return "No previous sessions found."
        return "\n".join(f"Session {r[0][:8]}... — {r[1][:10]} — {r[2]} messages" for r in rows)
    finally:
        conn.close()

# ── Contacts ──────────────────────────────────────────────

def save_contact(name: str, company: str = "", email: str = "", phone: str = "", notes: str = "") -> str:
    conn = _conn()
    try:
        now = datetime.now().isoformat()
        existing = conn.execute("SELECT id FROM contacts WHERE name=?", (name,)).fetchone()
        if existing:
            conn.execute("UPDATE contacts SET company=?,email=?,phone=?,notes=?,last_contact=? WHERE name=?",
                          (company, email, phone, notes, now, name))
            _journal_event(conn, "contact.update", {"name": name})
            conn.commit()
            return f"Contact updated: {name}"
        else:
            conn.execute("INSERT INTO contacts (name,company,email,phone,notes,last_contact) VALUES (?,?,?,?,?,?)",
                          (name, company, email, phone, notes, now))
            _journal_event(conn, "contact.insert", {"name": name})
            conn.commit()
            return f"Contact saved: {name}"
    finally:
        conn.close()

def get_contacts(search: str = "") -> str:
    conn = _conn()
    try:
        if search:
            rows = conn.execute("SELECT name,company,email,phone,notes,last_contact FROM contacts WHERE name LIKE ? OR company LIKE ?",
                                 (f"%{search}%", f"%{search}%")).fetchall()
        else:
            rows = conn.execute("SELECT name,company,email,phone,notes,last_contact FROM contacts ORDER BY last_contact DESC").fetchall()
        if not rows: return "No contacts found."
        return "\n".join(f"{r[0]} | {r[1]} | {r[2]} | Last: {r[5][:10] if r[5] else 'Never'}" for r in rows)
    finally:
        conn.close()

# ── Tasks ─────────────────────────────────────────────────

def add_task(task: str, due_date: str = "") -> str:
    conn = _conn()
    try:
        conn.execute("INSERT INTO tasks (task,due_date,created) VALUES (?,?,?)",
                      (task, due_date, datetime.now().isoformat()))
        _journal_event(conn, "task.add", {"task": task, "due_date": due_date})
        conn.commit()
        return f"Task added: {task}"
    finally:
        conn.close()

def get_tasks(status: str = "pending") -> str:
    conn = _conn()
    try:
        rows = conn.execute("SELECT id,task,due_date,created FROM tasks WHERE status=? ORDER BY created DESC",
                             (status,)).fetchall()
        if not rows: return f"No {status} tasks."
        return "\n".join(f"[{r[0]}] {r[1]}{f' — due {r[2]}' if r[2] else ''}" for r in rows)
    finally:
        conn.close()

def complete_task(task_id: int) -> str:
    conn = _conn()
    try:
        conn.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
        _journal_event(conn, "task.complete", {"task_id": task_id})
        conn.commit()
        return f"Task {task_id} marked complete."
    finally:
        conn.close()


# ── Revenue pipeline / CRM-lite ──────────────────────────

def add_pipeline_item(
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
    conn = _conn()
    try:
        now = datetime.now().isoformat()
        stage_norm = _normalize_stage(stage)
        conf = max(0, min(100, _safe_int(confidence, 30)))
        item_value = max(0.0, _safe_float(value, 0.0))
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
        _journal_event(conn, "pipeline.add", {"item_id": item_id, "title": title, "stage": stage_norm})
        conn.execute(
            "INSERT INTO pipeline_activity (item_id,activity_type,note,timestamp) VALUES (?,?,?,?)",
            (item_id, "create", f"Created pipeline item at stage {stage_norm}", now),
        )
        conn.commit()
        return f"Pipeline item added: [{item_id}] {title} ({stage_norm})"
    finally:
        conn.close()


def update_pipeline_item(
    item_id: int,
    stage: str = "",
    value: float = None,
    confidence: int = None,
    next_action: str = None,
    due_date: str = None,
    status: str = None,
    notes: str = None,
) -> str:
    conn = _conn()
    try:
        row = conn.execute("SELECT id, stage, value, confidence, status FROM pipeline_items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return f"Pipeline item not found: {item_id}"

        stage_new = _normalize_stage(stage) if stage else row[1]
        value_new = max(0.0, _safe_float(value, row[2])) if value is not None else row[2]
        conf_new = max(0, min(100, _safe_int(confidence, row[3]))) if confidence is not None else row[3]
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
        _journal_event(conn, "pipeline.update", {"item_id": item_id, "stage": stage_new, "status": status_new})
        conn.execute(
            "INSERT INTO pipeline_activity (item_id,activity_type,note,timestamp) VALUES (?,?,?,?)",
            (item_id, "update", f"Stage={stage_new}, status={status_new}, confidence={conf_new}", now),
        )
        conn.commit()
        return f"Pipeline item updated: [{item_id}] stage={stage_new}, status={status_new}"
    finally:
        conn.close()


def log_pipeline_activity(item_id: int, note: str, activity_type: str = "note") -> str:
    conn = _conn()
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
        _journal_event(conn, "pipeline.activity", {"item_id": item_id, "activity_type": activity_type})
        conn.commit()
        return f"Pipeline activity logged for item {item_id}."
    finally:
        conn.close()


def get_pipeline_items(stage: str = "", status: str = "open", limit: int = 30) -> str:
    conn = _conn()
    try:
        params = []
        where = []
        if stage:
            where.append("stage=?")
            params.append(_normalize_stage(stage))
        if status:
            where.append("status=?")
            params.append(status.strip().lower())

        sql = "SELECT id,title,company,stage,value,confidence,next_action,due_date,status,updated FROM pipeline_items"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY updated DESC LIMIT ?"
        params.append(max(1, min(100, _safe_int(limit, 30))))

        rows = conn.execute(sql, tuple(params)).fetchall()
        if not rows:
            return "No pipeline items found."

        lines = []
        for r in rows:
            lines.append(
                f"[{r[0]}] {r[1]} | {r[2] or '-'} | {r[3]} | ${r[4]:,.0f} | conf {r[5]}%"
                + (f" | next: {r[6]}" if r[6] else "")
                + (f" | due: {r[7]}" if r[7] else "")
            )
        return "\n".join(lines)
    finally:
        conn.close()


def get_revenue_dashboard_data() -> dict:
    conn = _conn()
    try:
        open_items = conn.execute(
            "SELECT id,title,stage,value,confidence,next_action,due_date,updated FROM pipeline_items WHERE status='open'"
        ).fetchall()
        all_rows = conn.execute(
            "SELECT stage,status,value,confidence FROM pipeline_items"
        ).fetchall()

        stage_counts = {stage: 0 for stage in PIPELINE_STAGES}
        status_counts = {"open": 0, "won": 0, "lost": 0, "archived": 0}
        total_pipeline = 0.0
        weighted_pipeline = 0.0

        for stage, status, value, confidence in all_rows:
            if stage in stage_counts:
                stage_counts[stage] += 1
            status_counts[status if status in status_counts else "open"] += 1
            if status == "open":
                val = _safe_float(value)
                conf = max(0, min(100, _safe_int(confidence, 0)))
                total_pipeline += val
                weighted_pipeline += val * (conf / 100.0)

        top_open = sorted(
            [
                {
                    "id": r[0],
                    "title": r[1],
                    "stage": r[2],
                    "value": _safe_float(r[3]),
                    "confidence": _safe_int(r[4], 0),
                    "next_action": r[5] or "",
                    "due_date": r[6] or "",
                    "updated": r[7],
                }
                for r in open_items
            ],
            key=lambda i: (i["value"] * (i["confidence"] / 100.0), i["updated"]),
            reverse=True,
        )[:7]

        due_soon = [i for i in top_open if i["due_date"]]

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
            "due_soon": due_soon,
        }
    finally:
        conn.close()


def get_revenue_dashboard() -> str:
    data = get_revenue_dashboard_data()
    lines = [
        "REVENUE DASHBOARD",
        f"Open: {data['open_count']} | Won: {data['won_count']} | Lost: {data['lost_count']}",
        f"Pipeline total: ${data['total_pipeline']:,.0f}",
        f"Weighted pipeline: ${data['weighted_pipeline']:,.0f}",
        "",
        "By stage:",
    ]
    for stage in PIPELINE_STAGES:
        lines.append(f"- {stage}: {data['stage_counts'].get(stage, 0)}")

    lines.append("")
    lines.append("Top open opportunities:")
    if not data["top_open"]:
        lines.append("- none")
    else:
        for item in data["top_open"][:5]:
            lines.append(
                f"- [{item['id']}] {item['title']} ({item['stage']}) ${item['value']:,.0f} @ {item['confidence']}%"
                + (f" | next: {item['next_action']}" if item['next_action'] else "")
            )
    return "\n".join(lines)

# ── Session summaries ─────────────────────────────────────

def save_session_summary(session_id: str, summary: str) -> str:
    """Persist an AI-generated summary of a completed session as a fact."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    key = f"session_{date_str}_{session_id[-8:]}"
    return remember(key, summary, category="session_summary")

def get_session_summaries(limit: int = 3) -> str:
    """Return the most recent session summaries, newest first."""
    c = _conn()
    try:
        rows = c.execute(
            "SELECT key, value, updated FROM facts WHERE category='session_summary' "
            "ORDER BY updated DESC LIMIT ?",
            (limit,),
        ).fetchall()
        if not rows:
            return ""
        lines = ["PREVIOUS SESSION SUMMARIES:"]
        for key, value, updated in rows:
            lines.append(f"\n[{updated[:10]}]")
            lines.append(value)
        return "\n".join(lines)
    finally:
        c.close()


# ── Recent conversation recall ─────────────────────────────

def get_recent_messages(exclude_session: str = None, limit: int = 10) -> str:
    """Return the last `limit` messages from the most recent prior session.

    Pass `exclude_session` (the current session_id) so we don't pull
    messages that are already live in the in-memory history.
    Returns an empty string if no prior messages exist.
    """
    conn = _conn()
    try:
        if exclude_session:
            row = conn.execute(
                "SELECT session_id FROM conversations WHERE session_id != ? "
                "ORDER BY id DESC LIMIT 1",
                (exclude_session,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT session_id FROM conversations ORDER BY id DESC LIMIT 1"
            ).fetchone()

        if not row:
            return ""

        prior_session = row[0]
        rows = conn.execute(
            "SELECT role, content, timestamp FROM conversations "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (prior_session, limit),
        ).fetchall()

        if not rows:
            return ""

        rows = list(reversed(rows))  # chronological order
        date_str = rows[0][2][:10]
        lines = [f"LAST SESSION ({date_str}):"]
        for role, content, _ts in rows:
            label = "Ryan" if role == "user" else "Guppy"
            snippet = content[:250] + "…" if len(content) > 250 else content
            lines.append(f"  {label}: {snippet}")
        return "\n".join(lines)
    finally:
        conn.close()


# ── Startup context ───────────────────────────────────────

def get_startup_context(exclude_session: str = None) -> str:
    """Returns a summary of what Guppy should know on startup.

    Pass `exclude_session` (current session_id) to keep last-session
    recall from mixing in messages already in live history.

    Improved session history priority:
      1. AI-generated session summaries (compressed, high signal) - always preferred
      2. Recent messages from last session (fallback, limited to avoid bloat)
      3. If summaries exist but are old (>7 days), supplement with recent messages
    """
    facts = recall()
    tasks = get_tasks("pending")
    conn = _conn()
    try:
        contacts_count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    finally:
        conn.close()

    # Get session summaries (prioritize recent ones)
    summaries = get_session_summaries(limit=5)  # Increased limit for better context

    # Check if we need recent messages as supplement
    need_recent = False
    if summaries:
        # If summaries exist but are older than 7 days, add recent messages
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT updated FROM facts WHERE category='session_summary' "
                "ORDER BY updated DESC LIMIT 1"
            ).fetchone()
            if row:
                from datetime import datetime, timedelta
                summary_date = datetime.fromisoformat(row[0].replace('Z', '+00:00'))
                if datetime.now(summary_date.tzinfo) - summary_date > timedelta(days=7):
                    need_recent = True
        finally:
            conn.close()
    else:
        # No summaries exist, definitely need recent messages
        need_recent = True

    recent = ""
    if need_recent:
        recent = get_recent_messages(exclude_session=exclude_session, limit=5)  # Reduced limit

    parts = ["MEMORY BRIEFING FOR MASTER RYAN'S SESSION:"]

    parts.append("\nSTORED FACTS:")
    parts.append(facts if facts != "Nothing found in memory." else "No facts stored yet.")

    parts.append("\nPENDING TASKS:")
    parts.append(tasks)

    parts.append(f"\nCONTACTS: {contacts_count} in database")

    if summaries:
        parts.append(f"\n{summaries}")
    if recent:
        parts.append(f"\n{recent}")
    if not summaries and not recent:
        parts.append("\nNo previous sessions on record.")

    return "\n".join(parts)