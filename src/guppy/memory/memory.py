"""Persistent memory facade for Guppy."""

from datetime import datetime

from src.guppy.paths import MEMORY_DB_PATH

from .memory_store import (
    journal_event as _journal_event,
    open_memory_connection,
    remember_fact,
    recall_facts,
    forget_fact,
    save_conversation_message,
    load_recent_history_records,
    get_session_summary_text,
    save_contact_record,
    get_contacts_text,
    add_task_record,
    get_tasks_text,
    complete_task_record,
    add_pipeline_item_record,
    update_pipeline_item_record,
    log_pipeline_activity_record,
    get_pipeline_items_text,
    get_revenue_dashboard_data_map,
    get_session_summaries_text,
    get_recent_messages_text,
    get_workspace_memory_snapshot as get_workspace_memory_snapshot_map,
)
from .memory_support import (
    PIPELINE_STAGES,
    clean_memory_fragment as _clean_memory_fragment,
    dedupe_memory_candidates as _dedupe_memory_candidates,
    extract_decision_candidates as _extract_decision_candidates,
    extract_identity_candidates as _extract_identity_candidates,
    extract_preference_candidates as _extract_preference_candidates,
    extract_scope_candidates as _extract_scope_candidates,
    looks_like_product_memory as _looks_like_product_memory,
    memory_candidate as _memory_candidate,
    normalize_stage as _normalize_stage,
    normalize_text as _normalize_text,
    safe_float as _safe_float,
    safe_int as _safe_int,
    slug_memory_fragment as _slug_memory_fragment,
)

DB_PATH = MEMORY_DB_PATH


def promote_durable_chat_memory(
    user_text: str,
    assistant_text: str = "",
    *,
    session_id: str = "",
    persona_id: str = "",
    max_items: int = 6,
) -> list[dict[str, str]]:
    from src.guppy.memory.semantic import remember_semantic

    del assistant_text

    candidates = _dedupe_memory_candidates(
        _extract_preference_candidates(user_text, speaker="user")
        + _extract_identity_candidates(user_text, speaker="user")
        + _extract_decision_candidates(user_text, speaker="user")
        + _extract_scope_candidates(user_text, speaker="user")
    )

    promoted: list[dict[str, str]] = []
    for candidate in candidates[: max(1, int(max_items or 6))]:
        status = remember_semantic(candidate["key"], candidate["value"], candidate["category"])
        promoted.append({**candidate, "status": status})

    if promoted:
        conn = _conn()
        try:
            _journal_event(
                conn,
                "semantic.promote_chat_memory",
                {
                    "session_id": session_id,
                    "persona_id": persona_id,
                    "keys": [item["key"] for item in promoted],
                },
            )
            conn.commit()
        finally:
            conn.close()
    return promoted

def _conn():
    """Get a ready SQLite connection for the current memory DB path."""
    return open_memory_connection(DB_PATH)

# ── Facts ─────────────────────────────────────────────────

def remember(key: str, value: str, category: str = "general") -> str:
    return remember_fact(DB_PATH, key, value, category)

def recall(query: str = "", category: str = "") -> str:
    return recall_facts(DB_PATH, query, category)

def forget(key: str) -> str:
    return forget_fact(DB_PATH, key)

# ── Conversation history ───────────────────────────────────

def save_message(
    session_id: str,
    role: str,
    content: str,
    *,
    workspace_name: str | None = None,
):
    save_conversation_message(DB_PATH, session_id, role, content, workspace_name=workspace_name)

def load_recent_history(
    session_id: str = None,
    limit: int = 20,
    *,
    workspace_name: str | None = None,
) -> list:
    return load_recent_history_records(DB_PATH, session_id, limit, workspace_name=workspace_name)

def get_session_summary(limit: int = 5, *, workspace_name: str | None = None) -> str:
    return get_session_summary_text(DB_PATH, limit, workspace_name=workspace_name).replace(" - ", " â€” ")
    return get_session_summary_text(DB_PATH, limit).replace(" - ", " — ")

# ── Contacts ──────────────────────────────────────────────

def save_contact(name: str, company: str = "", email: str = "", phone: str = "", notes: str = "") -> str:
    return save_contact_record(DB_PATH, name, company, email, phone, notes)

def get_contacts(search: str = "") -> str:
    return get_contacts_text(DB_PATH, search)

# ── Tasks ─────────────────────────────────────────────────

def add_task(task: str, due_date: str = "") -> str:
    return add_task_record(DB_PATH, task, due_date)

def get_tasks(status: str = "pending") -> str:
    return get_tasks_text(DB_PATH, status).replace(" - due ", " — due ")

def complete_task(task_id: int) -> str:
    return complete_task_record(DB_PATH, task_id)


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
    return add_pipeline_item_record(
        DB_PATH,
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
    return update_pipeline_item_record(
        DB_PATH,
        item_id,
        stage,
        value,
        confidence,
        next_action,
        due_date,
        status,
        notes,
    )


def log_pipeline_activity(item_id: int, note: str, activity_type: str = "note") -> str:
    return log_pipeline_activity_record(DB_PATH, item_id, note, activity_type)


def get_pipeline_items(stage: str = "", status: str = "open", limit: int = 30) -> str:
    return get_pipeline_items_text(DB_PATH, stage, status, limit)


def get_revenue_dashboard_data() -> dict:
    return get_revenue_dashboard_data_map(DB_PATH)


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
    return get_session_summaries_text(DB_PATH, limit)


# ── Recent conversation recall ─────────────────────────────

def get_recent_messages(
    exclude_session: str = None,
    limit: int = 10,
    *,
    workspace_name: str | None = None,
) -> str:
    """Return the last `limit` messages from the most recent prior session.

    Pass `exclude_session` (the current session_id) so we don't pull
    messages that are already live in the in-memory history.
    Returns an empty string if no prior messages exist.
    """
    return get_recent_messages_text(
        DB_PATH,
        exclude_session,
        limit,
        workspace_name=workspace_name,
    ).replace("...", "â€¦")
    return get_recent_messages_text(DB_PATH, exclude_session, limit).replace("...", "…")


# ── Startup context ───────────────────────────────────────

def get_startup_context(
    exclude_session: str = None,
    *,
    workspace_name: str | None = None,
) -> str:
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
        recent = get_recent_messages(
            exclude_session=exclude_session,
            limit=5,
            workspace_name=workspace_name,
        )  # Reduced limit
        recent = recent

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


def get_workspace_memory_snapshot(workspace_name: str | None = None) -> dict[str, object]:
    return get_workspace_memory_snapshot_map(DB_PATH, workspace_name)


# Canonical workspace-aware overrides retained here so older compatibility blocks
# above do not change the public runtime behavior.
def get_session_summary(limit: int = 5, *, workspace_name: str | None = None) -> str:
    return get_session_summary_text(DB_PATH, limit, workspace_name=workspace_name)


def get_recent_messages(
    exclude_session: str = None,
    limit: int = 10,
    *,
    workspace_name: str | None = None,
) -> str:
    return get_recent_messages_text(
        DB_PATH,
        exclude_session,
        limit,
        workspace_name=workspace_name,
    ).replace("...", "â€¦")


def get_startup_context(
    exclude_session: str = None,
    *,
    workspace_name: str | None = None,
) -> str:
    facts = recall()
    tasks = get_tasks("pending")
    conn = _conn()
    try:
        contacts_count = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    finally:
        conn.close()

    summaries = get_session_summaries(limit=5)

    need_recent = False
    if summaries:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT updated FROM facts WHERE category='session_summary' "
                "ORDER BY updated DESC LIMIT 1"
            ).fetchone()
            if row:
                from datetime import datetime, timedelta

                summary_date = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
                if datetime.now(summary_date.tzinfo) - summary_date > timedelta(days=7):
                    need_recent = True
        finally:
            conn.close()
    else:
        need_recent = True

    recent = ""
    if need_recent:
        recent = get_recent_messages(
            exclude_session=exclude_session,
            limit=5,
            workspace_name=workspace_name,
        )

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
