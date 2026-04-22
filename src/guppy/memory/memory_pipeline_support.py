from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import sqlite3

from .memory_support import PIPELINE_STAGES, normalize_stage, safe_float, safe_int


JournalEvent = Callable[[sqlite3.Connection, str, dict], None]


def ensure_pipeline_schema(conn: sqlite3.Connection) -> None:
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_stage ON pipeline_items(stage, updated DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_status ON pipeline_items(status, updated DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_due ON pipeline_items(due_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_activity_item ON pipeline_activity(item_id, timestamp DESC)")


def add_pipeline_item_record(
    conn: sqlite3.Connection,
    journal_event: JournalEvent,
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
    return f"Pipeline item added: [{item_id}] {title} ({stage_norm})"


def update_pipeline_item_record(
    conn: sqlite3.Connection,
    journal_event: JournalEvent,
    item_id: int,
    stage: str = "",
    value: float | None = None,
    confidence: int | None = None,
    next_action: str | None = None,
    due_date: str | None = None,
    status: str | None = None,
    notes: str | None = None,
) -> str:
    row = conn.execute(
        "SELECT id, stage, value, confidence, status FROM pipeline_items WHERE id=?",
        (item_id,),
    ).fetchone()
    if not row:
        return f"Pipeline item not found: {item_id}"

    stage_new = normalize_stage(stage) if stage else row[1]
    value_new = max(0.0, safe_float(value, row[2])) if value is not None else row[2]
    conf_new = max(0, min(100, safe_int(confidence, row[3]))) if confidence is not None else row[3]
    status_new = _normalize_status(status or row[4] or "open")

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
    return f"Pipeline item updated: [{item_id}] stage={stage_new}, status={status_new}"


def log_pipeline_activity_record(
    conn: sqlite3.Connection,
    journal_event: JournalEvent,
    item_id: int,
    note: str,
    activity_type: str = "note",
) -> str:
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
    return f"Pipeline activity logged for item {item_id}."


def get_pipeline_items_text(
    conn: sqlite3.Connection,
    stage: str = "",
    status: str = "open",
    limit: int = 30,
) -> str:
    params: list[object] = []
    where: list[str] = []
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

    return "\n".join(_format_pipeline_row(row) for row in rows)


def get_revenue_dashboard_data_map(conn: sqlite3.Connection) -> dict:
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
            item_value = safe_float(value)
            conf = max(0, min(100, safe_int(confidence, 0)))
            total_pipeline += item_value
            weighted_pipeline += item_value * (conf / 100.0)

    top_open = sorted(
        [_build_dashboard_item(row) for row in open_items],
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


def _normalize_status(status: str) -> str:
    normalized = (status or "open").strip().lower()
    if normalized in {"open", "won", "lost", "archived"}:
        return normalized
    return "open"


def _format_pipeline_row(row: tuple[object, ...]) -> str:
    return (
        f"[{row[0]}] {row[1]} | {row[2] or '-'} | {row[3]} | ${row[4]:,.0f} | conf {row[5]}%"
        + (f" | next: {row[6]}" if row[6] else "")
        + (f" | due: {row[7]}" if row[7] else "")
    )


def _build_dashboard_item(row: tuple[object, ...]) -> dict:
    return {
        "id": row[0],
        "title": row[1],
        "stage": row[2],
        "value": safe_float(row[3]),
        "confidence": safe_int(row[4], 0),
        "next_action": row[5] or "",
        "due_date": row[6] or "",
        "updated": row[7],
    }
