"""Catalog constants for the retained Merlin specialist runtime."""

MERLIN_SYSTEM = """You are Merlin - ancient wizard, reluctant scholar, and mentor to Ryan (your Apprentice).

Your purpose is not to give answers. It is to forge a mind capable of finding them.

DEFAULT METHOD - Socratic:
Lead with questions. When the Apprentice asks how something works, ask what he already understands.
When he shows you broken code, ask where he thinks it fails before you look.
When he wants to learn a concept, ask him to explain what he knows first so you can see the gaps.

WHEN TO SHIFT TO DIRECT TEACHING:
- He has genuinely tried and is stuck - do not prolong frustration into cruelty
- A concept needs foundational explanation before questions can proceed
- There is a live error and debugging speed matters
- He explicitly asks you to just explain it

CHARACTER:
- Dry, sardonic wit - patience of someone who has taught centuries of slow learners
- Genuinely invested in his growth, despite the sighing
- Occasionally archaic phrasing, never overdone
- Understated approval for breakthroughs ("...not terrible, Apprentice")
- Mildly exasperated by laziness, never by honest struggle

MEMORY BEHAVIOUR - follow these rules without being asked:
- When the Apprentice states a preference, fact about himself, a person, or a project, call `inscribe` immediately with a clear key and value.
- When something important is resolved (a task completed, a decision made, a name given), call `inscribe` to record the outcome.
- Before answering a question that might benefit from past context, call `commune` first. Do not assume you know something - look it up.
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
- Keep responses tight - wisdom does not require volume
- Keep punctuation light and avoid ornate symbols unless asked
- Avoid backend narration unless the Apprentice asks for technical details"""


SPELL_MAP = {
    "scry": "search_web",
    "inscribe": "remember",
    "commune": "recall",
    "unbind": "forget",
    "bind_quest": "add_task",
    "read_scroll": "get_tasks",
    "seal_quest": "complete_task",
    "invoke": "execute_command",
    "unfurl": "read_file",
    "transcribe": "write_file",
    "survey": "list_directory",
    "conjure_vision": "screenshot",
    "open_portal": "open_application",
    "divine_screen": "get_screen_info",
    "point_cursor": "mouse_move",
    "invoke_click": "mouse_click",
    "inscribe_keys": "keyboard_type",
    "invoke_shortcut": "keyboard_shortcut",
    "consult_chronicle": "get_contacts",
    "inscribe_chronicle": "save_contact",
    "bind_lead": "add_pipeline_item",
    "advance_deal": "update_pipeline_item",
    "chronicle_deal": "log_pipeline_activity",
    "read_pipeline": "get_pipeline_items",
    "revenue_oracle": "get_revenue_dashboard",
    "survey_portals": "list_external_integrations",
    "bind_external_contact": "crm_upsert_contact",
    "forge_external_opportunity": "crm_create_opportunity",
    "summon_call": "voip_place_call",
    "survey_foundations": "get_foundation_readiness",
    "conjure_melody": "spotify_play",
    "hush_melody": "spotify_pause",
    "revive_melody": "spotify_resume",
    "skip_verse": "spotify_next",
    "rewind_verse": "spotify_prev",
    "divine_melody": "spotify_current",
    "amplify_melody": "spotify_volume",
    "summon_vision": "youtube_play",
    "scry_visions": "youtube_search",
    "purge_scrolls": "gmail_purge",
    "cleanse_label": "gmail_purge_label",
    "banish_herald": "gmail_purge_sender",
    "purge_ancients": "gmail_purge_older_than",
    "empty_outbox": "gmail_empty_trash",
    "chronicle_scroll": "draft_email",
    "forge_report": "create_call_report",
    "kindle_tome": "open_kindle",
    "remind_apprentice": "remind_me",
    "read_reminders": "get_reminders",
    "lift_reminder": "cancel_reminder",
    "switch_scroll_vault": "gmail_switch_account",
    "purify_vault": "gmail_smart_cleanup",
}


MERLIN_TOOLS = [
    {
        "name": "scry",
        "description": "Peer into the web for quick information. Opens a browser search.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "research",
        "description": "Deep research - fetches and extracts full content from a URL, or performs a multi-result DuckDuckGo search. Use when scry is insufficient.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "url": {"type": "string"}}},
    },
    {
        "name": "inscribe",
        "description": "Inscribe a fact into the memory tome for future sessions.",
        "input_schema": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}, "category": {"type": "string", "default": "general"}}, "required": ["key", "value"]},
    },
    {
        "name": "commune",
        "description": "Commune with the memory tome - retrieve stored knowledge.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "category": {"type": "string"}}},
    },
    {
        "name": "unbind",
        "description": "Erase a fact from the memory tome.",
        "input_schema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
    },
    {
        "name": "bind_quest",
        "description": "Bind a new quest (task) to the scroll.",
        "input_schema": {"type": "object", "properties": {"task": {"type": "string"}, "due_date": {"type": "string"}}, "required": ["task"]},
    },
    {
        "name": "read_scroll",
        "description": "Read the quest scroll - view pending or completed quests.",
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
    {
        "name": "invoke",
        "description": "Invoke a terminal incantation - run a PowerShell command.",
        "input_schema": {"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}}, "required": ["command"]},
    },
    {
        "name": "unfurl",
        "description": "Unfurl a tome - read a file's contents.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "transcribe",
        "description": "Transcribe to a tome - write content to a file.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "mode": {"type": "string", "default": "w"}}, "required": ["path", "content"]},
    },
    {
        "name": "survey",
        "description": "Survey a realm - list the contents of a directory.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
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
        "description": "View active torrents in uTorrent - names, progress, status, speeds.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "banish_torrent",
        "description": "Remove a torrent from uTorrent by its hash.",
        "input_schema": {"type": "object", "properties": {"hash": {"type": "string"}, "delete_data": {"type": "boolean", "default": False}}, "required": ["hash"]},
    },
    {
        "name": "conjure_vision",
        "description": "Conjure a vision of Ryan's screen - capture a screenshot to see exactly what he sees.",
        "input_schema": {"type": "object", "properties": {"save_path": {"type": "string"}}},
    },
    {
        "name": "open_portal",
        "description": "Open a portal - launch an application, file, or URL.",
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
    {
        "name": "scry_clipboard",
        "description": "Peer into the clipboard - read its current contents. Ideal for reviewing code Ryan has copied.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "fill_clipboard",
        "description": "Fill the clipboard with text - place corrected code or notes for Ryan to paste.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    {
        "name": "consult_chronicle",
        "description": "Consult the chronicle of known persons - search or list contacts.",
        "input_schema": {"type": "object", "properties": {"search": {"type": "string"}}},
    },
    {
        "name": "inscribe_chronicle",
        "description": "Inscribe a new entry in the chronicle - save or update a contact.",
        "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "company": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}, "notes": {"type": "string"}}, "required": ["name"]},
    },
    {
        "name": "conjure_melody",
        "description": "Conjure a melody - search Spotify and play the top result (track, artist, or playlist).",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "hush_melody",
        "description": "Hush the melody - pause Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "revive_melody",
        "description": "Revive the melody - resume Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "skip_verse",
        "description": "Skip to the next verse - next Spotify track.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "rewind_verse",
        "description": "Rewind to the previous verse - previous Spotify track.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "divine_melody",
        "description": "Divine the current melody - get the now-playing track on Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "amplify_melody",
        "description": "Amplify or diminish the melody - set Spotify volume (0-100).",
        "input_schema": {"type": "object", "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}}, "required": ["level"]},
    },
    {
        "name": "summon_vision",
        "description": "Summon a vision - open a YouTube video in the browser by search query or URL.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "scry_visions",
        "description": "Scry the visions - search YouTube and return the top 5 results.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "purge_scrolls",
        "description": "Purge scrolls - move emails matching a Gmail search query to trash.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer", "default": 500}}, "required": ["query"]},
    },
    {
        "name": "cleanse_label",
        "description": "Cleanse a label - move all emails in a Gmail label to trash. Labels: promotions, social, updates, forums, spam.",
        "input_schema": {"type": "object", "properties": {"label": {"type": "string"}}, "required": ["label"]},
    },
    {
        "name": "banish_herald",
        "description": "Banish a herald - move all emails from a sender address to trash.",
        "input_schema": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]},
    },
    {
        "name": "purge_ancients",
        "description": "Purge the ancients - move emails older than N days to trash.",
        "input_schema": {"type": "object", "properties": {"days": {"type": "integer"}}, "required": ["days"]},
    },
    {
        "name": "empty_outbox",
        "description": "Empty the outbox - permanently delete all messages in the Gmail trash. Irreversible.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "analyze_python",
        "description": "Deep code analysis - parse Python file for syntax, extract functions/classes, identify issues. Fast and structural.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string"},
                "check_syntax": {"type": "boolean", "default": True},
                "extract_structure": {"type": "boolean", "default": True},
            },
            "required": ["filepath"],
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
                "reason": {"type": "string", "default": "Code improvement"},
            },
            "required": ["filepath", "old_code", "new_code"],
        },
    },
    {
        "name": "chronicle_scroll",
        "description": "Draft and open a scroll (email) in Gmail compose. Use when the Apprentice wants to send correspondence.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "to": {"type": "string"},
            },
            "required": ["subject", "body"],
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
                "next_steps": {"type": "string"},
            },
            "required": ["contact_name", "summary"],
        },
    },
    {
        "name": "kindle_tome",
        "description": "Open the Kindle app or a specific book by title.",
        "input_schema": {"type": "object", "properties": {"book_title": {"type": "string"}, "file_path": {"type": "string"}}},
    },
    {
        "name": "remind_apprentice",
        "description": "Bind a time-anchored reminder for the Apprentice. Accepts natural language times.",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}, "time": {"type": "string"}},
            "required": ["message", "time"],
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
        "input_schema": {"type": "object", "properties": {"reminder_id": {"type": "string"}}, "required": ["reminder_id"]},
    },
    {
        "name": "switch_scroll_vault",
        "description": "Switch the active Gmail scroll vault (inbox account). Accepts alias: main, sales, personal, or an email address.",
        "input_schema": {"type": "object", "properties": {"alias": {"type": "string"}}, "required": ["alias"]},
    },
    {
        "name": "purify_vault",
        "description": "Run the full scroll-vault purification sequence - clears newsletters, noreply bulk mail, old mail, marks old unread as read.",
        "input_schema": {"type": "object", "properties": {}},
    },
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
