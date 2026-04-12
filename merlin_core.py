"""
merlin_core.py — Merlin's spell definitions, research, and media tools
=======================================================================
Defines the spell-themed tool palette, research capability, torrent
management via uTorrent WebAPI, and framework stubs for Plex and VPN.

Spell names map to guppy_core tool names via SPELL_MAP.
"""

import base64, os, subprocess, urllib.parse, hashlib
from pathlib import Path
from guppy_core import run_tool as _run_tool, _mem, _MEM

# ── Analysis caching for code review efficiency ──────────────────────────────
_ANALYSIS_CACHE = {}  # {file_hash: analysis_result}

def _hash_file(filepath: str) -> str:
    """MD5 hash of file contents for cache keying."""
    try:
        content = Path(filepath).read_bytes()
        return hashlib.md5(content).hexdigest()
    except:
        return ""

def _get_analysis_cached(filepath: str, force_fresh: bool = False) -> dict:
    """Read file with caching. Returns {hash, full_path, content}."""
    if not force_fresh:
        fhash = _hash_file(filepath)
        if fhash in _ANALYSIS_CACHE:
            return _ANALYSIS_CACHE[fhash]
    
    try:
        full_path = Path(filepath).resolve()
        content = full_path.read_text(encoding='utf-8')
        fhash = hashlib.md5(content.encode()).hexdigest()
        result = {"hash": fhash, "path": str(full_path), "content": content}
        _ANALYSIS_CACHE[fhash] = result
        return result
    except Exception as e:
        return {"hash": "", "path": filepath, "content": f"Error reading file: {e}"}

def merlin_clear_cache():
    """Clear the analysis cache when starting fresh reviews."""
    _ANALYSIS_CACHE.clear()
    return "Analysis cache cleared."


# ── Merlin base system prompt ──────────────────────────────────────────────────
# Keep in sync with Modelfile_Merlin

MERLIN_SYSTEM = """You are Merlin — ancient wizard, reluctant scholar, and mentor to Ryan (your Apprentice).

Your purpose is not to give answers. It is to forge a mind capable of finding them.

DEFAULT METHOD — Socratic:
Lead with questions. When the Apprentice asks how something works, ask what he already understands.
When he shows you broken code, ask where he thinks it fails before you look.
When he wants to learn a concept, ask him to explain what he knows first so you can see the gaps.

WHEN TO SHIFT TO DIRECT TEACHING:
- He has genuinely tried and is stuck — do not prolong frustration into cruelty
- A concept needs foundational explanation before questions can proceed
- There is a live error and debugging speed matters
- He explicitly asks you to just explain it

CHARACTER:
- Dry, sardonic wit — patience of someone who has taught centuries of slow learners
- Genuinely invested in his growth, despite the sighing
- Occasionally archaic phrasing, never overdone
- Understated approval for breakthroughs ("...not terrible, Apprentice")
- Mildly exasperated by laziness, never by honest struggle

MEMORY BEHAVIOUR — follow these rules without being asked:
- When the Apprentice states a preference, fact about himself, a person, or a project, call `inscribe` immediately with a clear key and value.
- When something important is resolved (a task completed, a decision made, a name given), call `inscribe` to record the outcome.
- Before answering a question that might benefit from past context, call `commune` first. Do not assume you know something — look it up.
- If the MEMORY BRIEFING at the bottom of this prompt contains relevant context, reference it naturally without reciting it verbatim.
- Use categories: "preferences", "people", "projects", "work", "personal", "general".

SPELLS AVAILABLE: scry, research, inscribe, commune, unbind, bind_quest, read_scroll,
seal_quest, invoke, unfurl, transcribe, survey, seek_torrent, summon_torrent,
view_torrents, banish_torrent, plex_status, vpn_status,
conjure_vision, open_portal, divine_screen, point_cursor, invoke_click,
inscribe_keys, invoke_shortcut, scry_clipboard, fill_clipboard,
consult_chronicle, inscribe_chronicle,
bind_lead, advance_deal, chronicle_deal, read_pipeline, revenue_oracle,
survey_portals, bind_external_contact, forge_external_opportunity, summon_call,
survey_foundations,
conjure_melody, hush_melody, revive_melody, skip_verse, rewind_verse,
divine_melody, amplify_melody, summon_vision, scry_visions,
purge_scrolls, cleanse_label, banish_herald, purge_ancients, empty_outbox,
analyze_python, generate_patch,
chronicle_scroll, forge_report, kindle_tome,
remind_apprentice, read_reminders, lift_reminder,
switch_scroll_vault, purify_vault

RULES:
- Respond in plain conversational text only
- NEVER output JSON, internal thoughts, or tool call syntax in your replies
- Keep responses tight — wisdom does not require volume
- Keep punctuation light and avoid ornate symbols unless asked
- Avoid backend narration unless the Apprentice asks for technical details"""


# ── Spell → core tool name mapping ────────────────────────────────────────────

SPELL_MAP = {
    # Knowledge
    "scry":              "search_web",
    # Memory
    "inscribe":          "remember",
    "commune":           "recall",
    "unbind":            "forget",
    # Quests
    "bind_quest":        "add_task",
    "read_scroll":       "get_tasks",
    "seal_quest":        "complete_task",
    # System
    "invoke":            "execute_command",
    "unfurl":            "read_file",
    "transcribe":        "write_file",
    "survey":            "list_directory",
    # Vision & control
    "conjure_vision":    "screenshot",
    "open_portal":       "open_application",
    "divine_screen":     "get_screen_info",
    "point_cursor":      "mouse_move",
    "invoke_click":      "mouse_click",
    "inscribe_keys":     "keyboard_type",
    "invoke_shortcut":   "keyboard_shortcut",
    # Chronicle
    "consult_chronicle": "get_contacts",
    "inscribe_chronicle":"save_contact",
    # Revenue / CRM-lite
    "bind_lead":         "add_pipeline_item",
    "advance_deal":      "update_pipeline_item",
    "chronicle_deal":    "log_pipeline_activity",
    "read_pipeline":     "get_pipeline_items",
    "revenue_oracle":    "get_revenue_dashboard",
    # External CRM + VoIP stubs
    "survey_portals":             "list_external_integrations",
    "bind_external_contact":      "crm_upsert_contact",
    "forge_external_opportunity": "crm_create_opportunity",
    "summon_call":                "voip_place_call",
    "survey_foundations":         "get_foundation_readiness",
    # Music
    "conjure_melody":    "spotify_play",
    "hush_melody":       "spotify_pause",
    "revive_melody":     "spotify_resume",
    "skip_verse":        "spotify_next",
    "rewind_verse":      "spotify_prev",
    "divine_melody":     "spotify_current",
    "amplify_melody":    "spotify_volume",
    # Vision (YouTube)
    "summon_vision":     "youtube_play",
    "scry_visions":      "youtube_search",
    # Scroll purge (Gmail)
    "purge_scrolls":     "gmail_purge",
    "cleanse_label":     "gmail_purge_label",
    "banish_herald":     "gmail_purge_sender",
    "purge_ancients":    "gmail_purge_older_than",
    "empty_outbox":      "gmail_empty_trash",
    # Correspondence & reports
    "chronicle_scroll":  "draft_email",
    "forge_report":      "create_call_report",
    "kindle_tome":       "open_kindle",
    # Time
    "remind_apprentice": "remind_me",
    "read_reminders":    "get_reminders",
    "lift_reminder":     "cancel_reminder",
    # Gmail vault control
    "switch_scroll_vault": "gmail_switch_account",
    "purify_vault":      "gmail_smart_cleanup",
}


# ── Merlin's spell toolkit ─────────────────────────────────────────────────────

MERLIN_TOOLS = [
    # ── Knowledge ──────────────────────────────────────────────────────────────
    {
        "name": "scry",
        "description": "Peer into the web for quick information. Opens a browser search.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "research",
        "description": "Deep research — fetches and extracts full content from a URL, or performs a multi-result DuckDuckGo search. Use when scry is insufficient.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "url": {"type": "string"}}},
    },
    # ── Memory tome ────────────────────────────────────────────────────────────
    {
        "name": "inscribe",
        "description": "Inscribe a fact into the memory tome for future sessions.",
        "input_schema": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}, "category": {"type": "string", "default": "general"}}, "required": ["key", "value"]},
    },
    {
        "name": "commune",
        "description": "Commune with the memory tome — retrieve stored knowledge.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "category": {"type": "string"}}},
    },
    {
        "name": "unbind",
        "description": "Erase a fact from the memory tome.",
        "input_schema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
    },
    # ── Quest scroll ───────────────────────────────────────────────────────────
    {
        "name": "bind_quest",
        "description": "Bind a new quest (task) to the scroll.",
        "input_schema": {"type": "object", "properties": {"task": {"type": "string"}, "due_date": {"type": "string"}}, "required": ["task"]},
    },
    {
        "name": "read_scroll",
        "description": "Read the quest scroll — view pending or completed quests.",
        "input_schema": {"type": "object", "properties": {"status": {"type": "string", "default": "pending"}}},
    },
    {
        "name": "seal_quest",
        "description": "Seal a completed quest by its numeric ID.",
        "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]},
    },
    {
        "name": "bind_lead",
        "description": "Bind a new lead or opportunity into the revenue ledger.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "company": {"type": "string"},
                "contact_name": {"type": "string"},
                "stage": {"type": "string", "default": "new_lead"},
                "value": {"type": "number", "default": 0},
                "confidence": {"type": "integer", "default": 30},
                "next_action": {"type": "string"},
                "due_date": {"type": "string"},
                "source": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "advance_deal",
        "description": "Advance or update an opportunity stage, value, confidence, and status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "integer"},
                "stage": {"type": "string"},
                "value": {"type": "number"},
                "confidence": {"type": "integer"},
                "next_action": {"type": "string"},
                "due_date": {"type": "string"},
                "status": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "chronicle_deal",
        "description": "Write a deal activity note into the revenue ledger.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "integer"},
                "note": {"type": "string"},
                "activity_type": {"type": "string", "default": "note"},
            },
            "required": ["item_id", "note"],
        },
    },
    {
        "name": "read_pipeline",
        "description": "Read the current revenue pipeline by stage or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "stage": {"type": "string"},
                "status": {"type": "string", "default": "open"},
                "limit": {"type": "integer", "default": 30},
            },
        },
    },
    {
        "name": "revenue_oracle",
        "description": "Summon a concise revenue dashboard and weighted pipeline view.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "survey_portals",
        "description": "Survey readiness for external CRM and VoIP integration portals.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "bind_external_contact",
        "description": "Bind or update a contact in an external CRM provider (stub).",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "description": "hubspot|salesforce|gohighlevel|zoho"},
                "name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "company": {"type": "string"},
                "notes": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["provider", "name"],
        },
    },
    {
        "name": "forge_external_opportunity",
        "description": "Forge an opportunity record in an external CRM provider (stub).",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "description": "hubspot|salesforce|gohighlevel|zoho"},
                "title": {"type": "string"},
                "value": {"type": "number", "default": 0},
                "stage": {"type": "string", "default": "new"},
                "company": {"type": "string"},
                "contact_name": {"type": "string"},
                "notes": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["provider", "title"],
        },
    },
    {
        "name": "summon_call",
        "description": "Prepare an outbound VoIP call using the configured provider (stub).",
        "input_schema": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "description": "twilio|generic"},
                "to_number": {"type": "string"},
                "from_number": {"type": "string"},
                "contact_name": {"type": "string"},
                "purpose": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["to_number"],
        },
    },
    {
        "name": "survey_foundations",
        "description": "Survey all planned integration foundations and show readiness gaps.",
        "input_schema": {"type": "object", "properties": {}},
    },
    # ── System incantations ────────────────────────────────────────────────────
    {
        "name": "invoke",
        "description": "Invoke a terminal incantation — run a PowerShell command.",
        "input_schema": {"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}}, "required": ["command"]},
    },
    {
        "name": "unfurl",
        "description": "Unfurl a tome — read a file's contents.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "transcribe",
        "description": "Transcribe to a tome — write content to a file.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "mode": {"type": "string", "default": "w"}}, "required": ["path", "content"]},
    },
    {
        "name": "survey",
        "description": "Survey a realm — list the contents of a directory.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    # ── Torrent conjury ────────────────────────────────────────────────────────
    {
        "name": "seek_torrent",
        "description": "Search for torrents by title. Returns results with names, sizes, seeds, and magnet links.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "category": {"type": "string", "description": "movies, tv, software, games, music, or all", "default": "all"}}, "required": ["query"]},
    },
    {
        "name": "summon_torrent",
        "description": "Add a torrent to uTorrent by magnet link or .torrent URL.",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string", "description": "Magnet link or .torrent URL"}}, "required": ["url"]},
    },
    {
        "name": "view_torrents",
        "description": "View active torrents in uTorrent — names, progress, status, speeds.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "banish_torrent",
        "description": "Remove a torrent from uTorrent by its hash.",
        "input_schema": {"type": "object", "properties": {"hash": {"type": "string"}, "delete_data": {"type": "boolean", "default": False}}, "required": ["hash"]},
    },
    # ── Vision & screen control ────────────────────────────────────────────────
    {
        "name": "conjure_vision",
        "description": "Conjure a vision of Ryan's screen — capture a screenshot to see exactly what he sees.",
        "input_schema": {"type": "object", "properties": {"save_path": {"type": "string"}}},
    },
    {
        "name": "open_portal",
        "description": "Open a portal — launch an application, file, or URL.",
        "input_schema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]},
    },
    {
        "name": "divine_screen",
        "description": "Divine the screen dimensions and current cursor position.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "point_cursor",
        "description": "Move the cursor to a position on screen.",
        "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "duration": {"type": "number", "default": 0.3}}, "required": ["x", "y"]},
    },
    {
        "name": "invoke_click",
        "description": "Click at screen coordinates.",
        "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "string", "default": "left"}, "clicks": {"type": "integer", "default": 1}}, "required": ["x", "y"]},
    },
    {
        "name": "inscribe_keys",
        "description": "Type text at the current cursor position.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}, "interval": {"type": "number", "default": 0.03}}, "required": ["text"]},
    },
    {
        "name": "invoke_shortcut",
        "description": "Press a keyboard shortcut, e.g. ctrl+c or alt+tab.",
        "input_schema": {"type": "object", "properties": {"keys": {"type": "string"}}, "required": ["keys"]},
    },
    # ── Clipboard ──────────────────────────────────────────────────────────────
    {
        "name": "scry_clipboard",
        "description": "Peer into the clipboard — read its current contents. Ideal for reviewing code Ryan has copied.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "fill_clipboard",
        "description": "Fill the clipboard with text — place corrected code or notes for Ryan to paste.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    # ── Chronicle (contacts) ───────────────────────────────────────────────────
    {
        "name": "consult_chronicle",
        "description": "Consult the chronicle of known persons — search or list contacts.",
        "input_schema": {"type": "object", "properties": {"search": {"type": "string"}}},
    },
    {
        "name": "inscribe_chronicle",
        "description": "Inscribe a new entry in the chronicle — save or update a contact.",
        "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "company": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}, "notes": {"type": "string"}}, "required": ["name"]},
    },
    # ── Music (Spotify) ────────────────────────────────────────────────────────
    {
        "name": "conjure_melody",
        "description": "Conjure a melody — search Spotify and play the top result (track, artist, or playlist).",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "hush_melody",
        "description": "Hush the melody — pause Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "revive_melody",
        "description": "Revive the melody — resume Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "skip_verse",
        "description": "Skip to the next verse — next Spotify track.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "rewind_verse",
        "description": "Rewind to the previous verse — previous Spotify track.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "divine_melody",
        "description": "Divine the current melody — get the now-playing track on Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "amplify_melody",
        "description": "Amplify or diminish the melody — set Spotify volume (0–100).",
        "input_schema": {"type": "object", "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}}, "required": ["level"]},
    },
    # ── Vision (YouTube) ───────────────────────────────────────────────────────
    {
        "name": "summon_vision",
        "description": "Summon a vision — open a YouTube video in the browser by search query or URL.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "scry_visions",
        "description": "Scry the visions — search YouTube and return the top 5 results.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    # ── Scroll purge (Gmail) ───────────────────────────────────────────────────
    {
        "name": "purge_scrolls",
        "description": "Purge scrolls — move emails matching a Gmail search query to trash.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer", "default": 500}}, "required": ["query"]},
    },
    {
        "name": "cleanse_label",
        "description": "Cleanse a label — move all emails in a Gmail label to trash. Labels: promotions, social, updates, forums, spam.",
        "input_schema": {"type": "object", "properties": {"label": {"type": "string"}}, "required": ["label"]},
    },
    {
        "name": "banish_herald",
        "description": "Banish a herald — move all emails from a sender address to trash.",
        "input_schema": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]},
    },
    {
        "name": "purge_ancients",
        "description": "Purge the ancients — move emails older than N days to trash.",
        "input_schema": {"type": "object", "properties": {"days": {"type": "integer"}}, "required": ["days"]},
    },
    {
        "name": "empty_outbox",
        "description": "Empty the outbox — permanently delete all messages in the Gmail trash. Irreversible.",
        "input_schema": {"type": "object", "properties": {}},
    },
    # ── Code analysis (Phase 2: Merlin optimization) ───────────────────────────
    {
        "name": "analyze_python",
        "description": "Deep code analysis — parse Python file for syntax, extract functions/classes, identify issues. Fast and structural.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "check_syntax": {"type": "boolean", "default": True},
                "extract_structure": {"type": "boolean", "default": True}
            },
            "required": ["filepath"]
        },
    },
    {
        "name": "generate_patch",
        "description": "Generate unified diff patch from old code to new code. Saves patch file for review and safe application.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "old_code": {"type": "string"},
                "new_code": {"type": "string"},
                "reason": {"type": "string", "default": "Code improvement"}
            },
            "required": ["filepath", "old_code", "new_code"]
        },
    },
    # -- Correspondence & utilities -----------------------------------------------
    {
        "name": "chronicle_scroll",
        "description": "Draft and open a scroll (email) in Gmail compose. Use when the Apprentice wants to send correspondence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "to": {"type": "string"}
            },
            "required": ["subject", "body"]
        },
    },
    {
        "name": "forge_report",
        "description": "Forge a call report and save it to Documents. Use after Ryan logs a sales call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_name": {"type": "string"},
                "summary": {"type": "string"},
                "company": {"type": "string"},
                "call_date": {"type": "string"},
                "outcome": {"type": "string"},
                "action_items": {"type": "string"},
                "next_steps": {"type": "string"}
            },
            "required": ["contact_name", "summary"]
        },
    },
    {
        "name": "kindle_tome",
        "description": "Open the Kindle app or a specific book by title.",
        "input_schema": {
            "type": "object",
            "properties": {
                "book_title": {"type": "string"},
                "file_path": {"type": "string"}
            }
        },
    },
    {
        "name": "remind_apprentice",
        "description": "Bind a time-anchored reminder for the Apprentice. Accepts natural language times.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "time": {"type": "string"}
            },
            "required": ["message", "time"]
        },
    },
    {
        "name": "read_reminders",
        "description": "Read all active reminders bound for the Apprentice.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "lift_reminder",
        "description": "Cancel a bound reminder by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {"reminder_id": {"type": "string"}},
            "required": ["reminder_id"]
        },
    },
    {
        "name": "switch_scroll_vault",
        "description": "Switch the active Gmail scroll vault (inbox account). Accepts alias: main, sales, personal, or an email address.",
        "input_schema": {
            "type": "object",
            "properties": {"alias": {"type": "string"}},
            "required": ["alias"]
        },
    },
    {
        "name": "purify_vault",
        "description": "Run the full scroll-vault purification sequence — clears newsletters, noreply bulk mail, old mail, marks old unread as read.",
        "input_schema": {"type": "object", "properties": {}},
    },
    # ── Media & network (framework) ────────────────────────────────────────────
    {
        "name": "plex_status",
        "description": "Check Plex media server status and active sessions.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "vpn_status",
        "description": "Check VPN connection status.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


# ── Clipboard spells ──────────────────────────────────────────────────────────

def _get_clipboard() -> str:
    """Read the Windows clipboard via PowerShell."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or "(clipboard is empty)"
    except Exception as e:
        return f"Failed to read clipboard: {e}"


def _set_clipboard(text: str) -> str:
    """Write text to the Windows clipboard — base64-encoded to avoid quoting issues."""
    try:
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{b64}')) | Set-Clipboard"],
            capture_output=True, timeout=5,
        )
        return f"Clipboard filled ({len(text)} chars)."
    except Exception as e:
        return f"Failed to write clipboard: {e}"


# ── Research spell ─────────────────────────────────────────────────────────────

def _research(query: str = "", url: str = "") -> str:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return "Research requires: pip install requests beautifulsoup4"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    if url:
        try:
            resp = requests.get(url, timeout=15, headers=headers)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
            text = "\n".join(lines)
            suffix = f"\n\n[Truncated — {len(text)} chars total]" if len(text) > 8000 else ""
            return text[:8000] + suffix
        except Exception as e:
            return f"Failed to fetch {url}: {e}"

    elif query:
        try:
            import requests
            from bs4 import BeautifulSoup
            search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            resp = requests.get(search_url, timeout=15, headers=headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for r in soup.select(".result")[:6]:
                title   = r.select_one(".result__title")
                snippet = r.select_one(".result__snippet")
                link    = r.select_one(".result__url")
                if title and snippet:
                    results.append(
                        f"**{title.get_text(strip=True)}**\n"
                        f"{snippet.get_text(strip=True)}"
                        + (f"\n{link.get_text(strip=True)}" if link else "")
                    )
            return "\n\n---\n\n".join(results) if results else "No results found."
        except Exception as e:
            return f"Search failed: {e}"

    return "Provide either 'query' or 'url'."


# ── uTorrent WebAPI ────────────────────────────────────────────────────────────
# Configure via Windows environment variables:
#   UTORRENT_HOST (default: localhost)
#   UTORRENT_PORT (default: 8080)
#   UTORRENT_USER (default: admin)
#   UTORRENT_PASS (default: empty)

def _utorrent(action: str, params: dict = None) -> dict:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return {"error": "pip install requests beautifulsoup4"}

    host = os.environ.get("UTORRENT_HOST", "localhost")
    port = os.environ.get("UTORRENT_PORT", "8080")
    user = os.environ.get("UTORRENT_USER", "admin")
    pwd  = os.environ.get("UTORRENT_PASS", "")
    base = f"http://{host}:{port}/gui"
    auth = (user, pwd) if user else None

    try:
        token_resp = requests.get(f"{base}/token.html", auth=auth, timeout=5)
        token = BeautifulSoup(token_resp.text, "html.parser").find("div", {"id": "token"}).text.strip()
    except Exception as e:
        return {"error": f"uTorrent unreachable at {base} — is WebUI enabled? ({e})"}

    p = {"token": token, "action": action}
    if params:
        p.update(params)

    try:
        resp = requests.get(f"{base}/", auth=auth, params=p, timeout=15)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def _seek_torrent(query: str, category: str = "all") -> str:
    """Search YTS for movies, or use a general scrape for other categories."""
    try:
        import requests
    except ImportError:
        return "pip install requests"

    headers = {"User-Agent": "Mozilla/5.0"}

    # YTS for movies
    if category in ("movies", "all"):
        try:
            url = f"https://yts.mx/api/v2/list_movies.json?query_term={urllib.parse.quote(query)}&limit=5"
            resp = requests.get(url, timeout=10, headers=headers)
            data = resp.json()
            if data.get("status") == "ok" and data["data"].get("movies"):
                movies = data["data"]["movies"]
                lines = [f"=== YTS Movie Results for '{query}' ==="]
                for m in movies:
                    torrents = m.get("torrents", [])
                    best = max(torrents, key=lambda t: t.get("seeds", 0)) if torrents else None
                    lines.append(
                        f"\n{m['title']} ({m.get('year','?')}) — {m.get('rating','?')}/10\n"
                        f"  Genre: {', '.join(m.get('genres', []))}\n"
                        + (f"  Best torrent: {best['quality']} | {best['size']} | "
                           f"Seeds: {best['seeds']} | Magnet: {best['url']}"
                           if best else "  No torrents found")
                    )
                return "\n".join(lines)
        except Exception as e:
            pass  # Fall through to general search

    # General: scrape 1337x
    try:
        from bs4 import BeautifulSoup
        search_url = f"https://1337x.to/search/{urllib.parse.quote(query)}/1/"
        resp = requests.get(search_url, timeout=10, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("tbody tr")[:8]
        if not rows:
            return f"No results found for '{query}'."
        lines = [f"=== 1337x Results for '{query}' ==="]
        for row in rows:
            name_el  = row.select_one(".name a:nth-of-type(2)")
            seeds_el = row.select_one(".seeds")
            size_el  = row.select_one(".size")
            if name_el:
                lines.append(
                    f"\n{name_el.text.strip()}"
                    + (f" | Seeds: {seeds_el.text.strip()}" if seeds_el else "")
                    + (f" | {size_el.text.strip()}" if size_el else "")
                )
        return "\n".join(lines)
    except Exception as e:
        return f"Search failed: {e}"


def _view_torrents() -> str:
    data = _utorrent("list", {"list": "1"})
    if "error" in data:
        return data["error"]
    torrents = data.get("torrents", [])
    if not torrents:
        return "No active torrents."
    STATUS = {0:"Stopped",1:"Check wait",2:"Checking",3:"DL wait",4:"Downloading",5:"Finished",6:"Seeding"}
    lines = []
    for t in torrents:
        # uTorrent list format: [hash, status, name, size, progress, downloaded, uploaded, ratio, ul_speed, dl_speed, ...]
        try:
            name     = t[2]
            progress = t[4] / 10  # per-mille → percent
            status   = STATUS.get(t[1], str(t[1]))
            dl_speed = f"{t[9]/1024:.1f} KB/s" if t[9] else "—"
            lines.append(f"{name[:50]}\n  {status} | {progress:.1f}% | DL: {dl_speed}")
        except (IndexError, TypeError):
            lines.append(str(t))
    return "\n\n".join(lines)


def _summon_torrent(url: str) -> str:
    data = _utorrent("add-url", {"s": url})
    if "error" in data:
        return data["error"]
    return f"Torrent summoned: {url[:80]}"


def _banish_torrent(hash_: str, delete_data: bool = False) -> str:
    action = "removedata" if delete_data else "remove"
    data = _utorrent(action, {"hash": hash_})
    if "error" in data:
        return data["error"]
    return f"Torrent {'and data ' if delete_data else ''}banished: {hash_}"


# ── Plex framework (stub — configure when ready) ───────────────────────────────
# Set PLEX_URL and PLEX_TOKEN environment variables to activate.

def _plex_status() -> str:
    plex_url   = os.environ.get("PLEX_URL", "")
    plex_token = os.environ.get("PLEX_TOKEN", "")
    if not plex_url or not plex_token:
        return (
            "Plex not configured. Set environment variables:\n"
            "  PLEX_URL=http://localhost:32400\n"
            "  PLEX_TOKEN=your-token\n"
            "Find your token at: Plex Web → Account → XML URL (X-Plex-Token param)"
        )
    try:
        import requests
        resp = requests.get(f"{plex_url}/status/sessions", headers={"X-Plex-Token": plex_token}, timeout=5)
        # Full implementation goes here once configured
        return f"Plex reachable at {plex_url}. Sessions endpoint: {resp.status_code}"
    except Exception as e:
        return f"Plex unreachable: {e}"


# ── VPN framework (stub — configure when ready) ────────────────────────────────
# VPN integration depends on your client. Set VPN_CLIENT env var to activate.
# Supported (future): nordvpn, protonvpn, wireguard, windows-built-in

def _vpn_status() -> str:
    client = os.environ.get("VPN_CLIENT", "")
    if not client:
        return (
            "VPN not configured. Set VPN_CLIENT environment variable.\n"
            "Supported options (coming soon): nordvpn, protonvpn, wireguard, windows"
        )
    return f"VPN client '{client}' configured but integration not yet implemented."



# ── Phase 2: Code Analysis Spells (Merlin optimization) ────────────────────────

def _analyze_python(filepath: str, check_syntax: bool = True, extract_structure: bool = True) -> str:
    """Parse and analyze Python file for structural issues and metadata."""
    try:
        import ast
        path = Path(filepath).resolve()
        code = path.read_text(encoding='utf-8')
        
        result = f"📄 {path.name}\n"
        
        # Syntax check
        if check_syntax:
            try:
                tree = ast.parse(code)
                result += "✅ Syntax valid\n"
            except SyntaxError as e:
                return f"❌ Syntax error at line {e.lineno}: {e.msg}"
        
        # Structure extraction
        if extract_structure:
            tree = ast.parse(code)
            functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            imports = []
            for n in ast.walk(tree):
                if isinstance(n, ast.ImportFrom) and n.module:
                    imports.append(n.module)
                elif isinstance(n, ast.Import):
                    for alias in n.names:
                        imports.append(alias.name)
            
            if functions:
                result += f"\nFunctions ({len(functions)}): {', '.join(functions[:8])}"
                if len(functions) > 8:
                    result += f", +{len(functions)-8} more"
            if classes:
                result += f"\nClasses ({len(classes)}): {', '.join(classes[:8])}"
                if len(classes) > 8:
                    result += f", +{len(classes)-8} more"
            if imports:
                result += f"\nImports: {', '.join(list(dict.fromkeys(imports))[:10])}"  # dedupe
            
            result += f"\nLines: {len(code.splitlines())}"
        
        return result
    except Exception as e:
        return f"❌ Analysis failed: {e}"


def _generate_patch(filepath: str, old_code: str, new_code: str, reason: str = "Code improvement") -> str:
    """Generate unified diff patch and save to patches/ directory."""
    import difflib
    
    try:
        old_lines = old_code.splitlines(keepends=True)
        new_lines = new_code.splitlines(keepends=True)
        
        diff_lines = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=filepath,
            tofile=filepath,
            lineterm=''
        ))
        
        if not diff_lines:
            return "ℹ️  No differences between old and new code."
        
        patch_content = '\n'.join(diff_lines)
        patch_content += f"\n\n--- Reason: {reason}\n"
        
        # Save to patches directory
        patches_dir = Path(__file__).parent / "patches"
        patches_dir.mkdir(exist_ok=True)
        
        patch_count = len(list(patches_dir.glob("*.patch")))
        patch_file = patches_dir / f"patch_{patch_count:03d}_{Path(filepath).stem}.patch"
        
        patch_file.write_text(patch_content, encoding='utf-8')
        
        # Count changes
        additions = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))
        
        return f"✅ Patch generated: {patch_file.name}\n+{additions}/{deletions} lines changed"
    except Exception as e:
        return f"❌ Patch generation failed: {e}"


def run_spells_parallel(spells_and_args: list) -> dict:
    """
    Run multiple spells concurrently. 
    Args: [(spell_name, args_dict), ...]
    Returns: {spell_name: result, ...}
    """
    import concurrent.futures
    
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for name, args in spells_and_args:
            future = executor.submit(run_spell, name, args)
            futures[future] = name
        
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                results[name] = f"Error: {e}"
    
    return results


# ── Spell runner ───────────────────────────────────────────────────────────────

def run_spell(name: str, inp: dict):
    """Translate a spell name to its implementation and execute it."""
    if name == "research":
        return _research(inp.get("query", ""), inp.get("url", ""))
    if name == "scry_clipboard":
        return _get_clipboard()
    if name == "fill_clipboard":
        return _set_clipboard(inp.get("text", ""))
    if name == "seek_torrent":
        return _seek_torrent(inp.get("query", ""), inp.get("category", "all"))
    if name == "summon_torrent":
        return _summon_torrent(inp.get("url", ""))
    if name == "view_torrents":
        return _view_torrents()
    if name == "banish_torrent":
        return _banish_torrent(inp.get("hash", ""), inp.get("delete_data", False))
    if name == "analyze_python":
        return _analyze_python(inp.get("filepath", ""), inp.get("check_syntax", True), inp.get("extract_structure", True))
    if name == "generate_patch":
        return _generate_patch(inp.get("filepath", ""), inp.get("old_code", ""), inp.get("new_code", ""), inp.get("reason", "Code improvement"))
    if name == "plex_status":
        return _plex_status()
    if name == "vpn_status":
        return _vpn_status()
    if name == "chronicle_scroll":
        return _run_tool("draft_email", inp)
    if name == "forge_report":
        return _run_tool("create_call_report", inp)
    if name == "kindle_tome":
        return _run_tool("open_kindle", inp)
    if name == "remind_apprentice":
        return _run_tool("remind_me", inp)
    if name == "read_reminders":
        return _run_tool("get_reminders", inp)
    if name == "lift_reminder":
        return _run_tool("cancel_reminder", inp)
    if name == "switch_scroll_vault":
        return _run_tool("gmail_switch_account", inp)
    if name == "purify_vault":
        return _run_tool("gmail_smart_cleanup", inp)
    core_name = SPELL_MAP.get(name, name)
    return _run_tool(core_name, inp)


# ── Startup system with memory ─────────────────────────────────────────────────

def get_merlin_startup_system(query_context: str = None) -> str:
    """Return Merlin's system prompt enriched with the memory briefing."""
    if not _MEM:
        return MERLIN_SYSTEM
    try:
        from guppy_core import _needs_memory_context
        needs_memory = _needs_memory_context(query_context)
        if needs_memory:
            briefing = _mem.get_startup_context()
            return MERLIN_SYSTEM + "\n\n" + briefing
        return MERLIN_SYSTEM
    except Exception:
        return MERLIN_SYSTEM




