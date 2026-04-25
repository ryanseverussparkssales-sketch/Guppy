"""
utils/tool_registry.py
Canonical TOOLS list and input schema validation.
Safe to import from both the launcher and the cloud API surface.
"""
from __future__ import annotations

TOOLS = [
    {
        "name": "execute_command",
        "description": "Run a PowerShell command. Returns stdout/stderr.",
        "input_schema": {"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}}, "required": ["command"]},
    },
    {
        "name": "read_file",
        "description": "Read a file.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "write_file",
        "description": "Write a file. mode w=overwrite, a=append.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "mode": {"type": "string", "default": "w"}}, "required": ["path", "content"]},
    },
    {
        "name": "apply_patch",
        "description": "Apply a unified diff patch to the repo using git apply. Suitable for targeted edits without full-file rewrites.",
        "input_schema": {"type": "object", "properties": {"patch": {"type": "string", "description": "Unified diff string (output of git diff or similar)"}}, "required": ["patch"]},
    },
    {
        "name": "list_directory",
        "description": "List directory contents.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "open_application",
        "description": "Open an app, file, or URL.",
        "input_schema": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]},
    },
    {
        "name": "screenshot",
        "description": "Take a screenshot.",
        "input_schema": {"type": "object", "properties": {"save_path": {"type": "string"}}},
    },
    {
        "name": "mouse_move",
        "description": "Move mouse to x, y.",
        "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "duration": {"type": "number", "default": 0.3}}, "required": ["x", "y"]},
    },
    {
        "name": "mouse_click",
        "description": "Click mouse at x, y.",
        "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "string", "default": "left"}, "clicks": {"type": "integer", "default": 1}}, "required": ["x", "y"]},
    },
    {
        "name": "keyboard_type",
        "description": "Type text.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}, "interval": {"type": "number", "default": 0.03}}, "required": ["text"]},
    },
    {
        "name": "keyboard_shortcut",
        "description": "Press a shortcut, e.g. ctrl+c.",
        "input_schema": {"type": "object", "properties": {"keys": {"type": "string"}}, "required": ["keys"]},
    },
    {
        "name": "get_screen_info",
        "description": "Get screen resolution and current mouse position.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_gmail",
        "description": "Open Gmail. Optionally pre-fill a compose window.",
        "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}, "compose": {"type": "boolean", "default": False}}},
    },
    {
        "name": "draft_email",
        "description": "Write an email and open it in Gmail compose.",
        "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["subject", "body"]},
    },
    {
        "name": "create_call_report",
        "description": "Generate a call report and save it to Documents.",
        "input_schema": {"type": "object", "properties": {"contact_name": {"type": "string"}, "company": {"type": "string"}, "call_date": {"type": "string"}, "summary": {"type": "string"}, "action_items": {"type": "string"}, "outcome": {"type": "string"}, "next_steps": {"type": "string"}}, "required": ["contact_name", "summary"]},
    },
    {
        "name": "create_order_note",
        "description": "Generate an order note and save it to Documents.",
        "input_schema": {"type": "object", "properties": {"customer": {"type": "string"}, "order_details": {"type": "string"}, "quantity": {"type": "string"}, "value": {"type": "string"}, "notes": {"type": "string"}, "follow_up": {"type": "string"}}, "required": ["customer", "order_details"]},
    },
    {
        "name": "open_kindle",
        "description": "Open the Kindle app or a specific ebook file.",
        "input_schema": {"type": "object", "properties": {"book_title": {"type": "string"}, "file_path": {"type": "string"}}},
    },
    {
        "name": "search_web",
        "description": (
            "Search the web. If PERPLEXITY_API_KEY is set, returns a real AI-synthesised answer with citations. "
            "Otherwise opens a Google search in the browser. Use for current events, facts, prices, how-to questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query":  {"type": "string", "description": "What to search for."},
                "detail": {"type": "boolean", "description": "If true, request a more detailed answer (uses more tokens). Default false."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Fetch the text content of any URL and return it so you can read it. "
            "Use to read news articles, documentation pages, RSS feeds, or any webpage. "
            "Returns up to 4000 characters of cleaned plain text. "
            "Prefer this over search_web when you need actual article content, not just a summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url":    {"type": "string", "description": "Full URL to fetch (must include https://)."},
                "max_chars": {"type": "integer", "description": "Max characters to return. Default 4000."},
            },
            "required": ["url"],
        },
    },
    {
        "name": "get_news",
        "description": (
            "Get current news headlines with titles, sources, and links. "
            "Uses Google News RSS — no API key required, always returns real current stories. "
            "Use for 'what's in the news', 'top stories', or topic-specific news like 'tech news' or 'sports headlines'. "
            "Returns 8-10 real headlines with clickable links."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "News topic or search query. Leave empty for top headlines."},
                "count": {"type": "integer", "description": "Number of headlines to return. Default 8, max 15."},
            },
        },
    },
    {
        "name": "get_weather",
        "description": "Get current weather and today's forecast for a location. Defaults to Ryan's home location if not specified.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name or 'lat,lon'. Omit to use default location from WEATHER_LOCATION env var."},
                "units":    {"type": "string", "description": "metric (°C) or imperial (°F). Default imperial."},
            },
        },
    },
    # ── Memory tools ───────────────────────────────────────────────────────────
    {
        "name": "remember",
        "description": "Store a fact in persistent memory. Use proactively when Master Ryan tells you something worth keeping between sessions.",
        "input_schema": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}, "category": {"type": "string", "default": "general"}}, "required": ["key", "value"]},
    },
    {
        "name": "recall",
        "description": "Search persistent memory for stored facts. Use when you need to look something up that Master Ryan may have told you before.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "category": {"type": "string"}}},
    },
    {
        "name": "semantic_remember",
        "description": "Store a memory in semantic vector memory for meaning-based recall.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"},
                "category": {"type": "string", "default": "general"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "semantic_recall",
        "description": "Recall relevant memory by semantic similarity (not keyword match).",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "forget",
        "description": "Delete a fact from persistent memory.",
        "input_schema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
    },
    {
        "name": "add_task",
        "description": "Add a task to Master Ryan's persistent task list.",
        "input_schema": {"type": "object", "properties": {"task": {"type": "string"}, "due_date": {"type": "string"}}, "required": ["task"]},
    },
    {
        "name": "get_tasks",
        "description": "Get tasks from Master Ryan's task list.",
        "input_schema": {"type": "object", "properties": {"status": {"type": "string", "default": "pending"}}},
    },
    {
        "name": "complete_task",
        "description": "Mark a task as complete by its numeric ID.",
        "input_schema": {"type": "object", "properties": {"task_id": {"type": "integer"}}, "required": ["task_id"]},
    },
    {
        "name": "save_contact",
        "description": "Save or update a contact in the persistent address book.",
        "input_schema": {"type": "object", "properties": {"name": {"type": "string"}, "company": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}, "notes": {"type": "string"}}, "required": ["name"]},
    },
    {
        "name": "get_contacts",
        "description": "Search or list contacts in the address book.",
        "input_schema": {"type": "object", "properties": {"search": {"type": "string"}}},
    },
    {
        "name": "add_pipeline_item",
        "description": "Add a lead/opportunity to the revenue pipeline.",
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
        "name": "update_pipeline_item",
        "description": "Update stage, value, confidence, or status for a pipeline item.",
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
        "name": "log_pipeline_activity",
        "description": "Log a note or activity entry against a pipeline item.",
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
        "name": "get_pipeline_items",
        "description": "List pipeline items by stage and/or status.",
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
        "name": "get_revenue_dashboard",
        "description": "Get a concise revenue and pipeline dashboard summary.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_external_integrations",
        "description": "List readiness for external CRM and VoIP integrations.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "crm_upsert_contact",
        "description": "Create or update a contact in an external CRM provider (stub).",
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
        "name": "crm_create_opportunity",
        "description": "Create an opportunity in an external CRM provider (stub).",
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
        "name": "voip_place_call",
        "description": "Prepare a VoIP outbound call via configured provider (stub).",
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
        "name": "get_foundation_readiness",
        "description": "Get a full readiness report for planned integrations and account connections.",
        "input_schema": {"type": "object", "properties": {}},
    },
    # ── Spotify ────────────────────────────────────────────────────────────────
    {
        "name": "spotify_play",
        "description": "Search Spotify and play the top result (track, artist, or playlist).",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "spotify_pause",
        "description": "Pause Spotify playback.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_resume",
        "description": "Resume Spotify playback.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_next",
        "description": "Skip to the next track on Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_prev",
        "description": "Go back to the previous track on Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_current",
        "description": "Get the currently playing track on Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_volume",
        "description": "Set Spotify volume (0–100).",
        "input_schema": {"type": "object", "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 100}}, "required": ["level"]},
    },
    # ── YouTube ────────────────────────────────────────────────────────────────
    {
        "name": "youtube_play",
        "description": "Find and open a YouTube video in the browser. Accepts a search query or direct URL.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "youtube_search",
        "description": "Search YouTube and return the top 5 results with titles and URLs.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    # ── Gmail purge ────────────────────────────────────────────────────────────
    {
        "name": "gmail_purge",
        "description": "Move emails matching a Gmail search query to trash. Supports any Gmail search syntax.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer", "default": 500}}, "required": ["query"]},
    },
    {
        "name": "gmail_purge_label",
        "description": "Move all emails in a Gmail label to trash. Labels: promotions, social, updates, forums, spam, inbox.",
        "input_schema": {"type": "object", "properties": {"label": {"type": "string"}}, "required": ["label"]},
    },
    {
        "name": "gmail_purge_sender",
        "description": "Move all emails from a sender email address to trash.",
        "input_schema": {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]},
    },
    {
        "name": "gmail_purge_older_than",
        "description": "Move emails older than N days to trash.",
        "input_schema": {"type": "object", "properties": {"days": {"type": "integer"}}, "required": ["days"]},
    },
    {
        "name": "gmail_empty_trash",
        "description": "Permanently delete all messages in the Gmail trash. Irreversible.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gmail_switch_account",
        "description": "Switch the active Gmail account. Use before any gmail_ tool to target a different inbox. Accepts alias (main, sales, personal) or the email address.",
        "input_schema": {"type": "object", "properties": {"alias": {"type": "string"}}, "required": ["alias"]},
    },
    {
        "name": "gmail_list_accounts",
        "description": "List all configured Gmail accounts and show which is currently active.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gmail_smart_cleanup",
        "description": (
            "Run a standard inbox cleanup sequence: moves unsubscribe mail, no-reply bulk mail, "
            "newsletters, and old mail (1yr+) to trash, and marks old unread mail (30d+) as read. "
            "Use when Master Ryan says 'clean up my inbox' or similar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "max_per_step": {
                    "type": "integer",
                    "description": "Max emails to process per cleanup step. Default 500.",
                    "default": 500,
                }
            },
        },
    },
    # ── Reminders & Tasks ──────────────────────────────────────────────────────
    {
        "name": "remind_me",
        "description": "Schedule a reminder for Master Ryan at a specific time. Accepts natural language times like '3pm', 'tomorrow at 10am', 'in 30 minutes', etc.",
        "input_schema": {"type": "object", "properties": {"message": {"type": "string"}, "time": {"type": "string"}}, "required": ["message", "time"]},
    },
    {
        "name": "get_reminders",
        "description": "Get all active reminders scheduled for Master Ryan.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "cancel_reminder",
        "description": "Cancel a scheduled reminder by its ID. Use get_reminders to see active reminder IDs.",
        "input_schema": {"type": "object", "properties": {"reminder_id": {"type": "string"}}, "required": ["reminder_id"]},
    },
    {
        "name": "morning_brief",
        "description": (
            "Generate a morning brief for Master Ryan. "
            "Pulls today's reminders, pending tasks, recent memory context (work + projects), "
            "and Gmail unread counts. Returns a formatted summary and optionally fires a toast notification. "
            "Use this first thing each morning or whenever Ryan asks for a daily status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "include_gmail": {
                    "type": "boolean",
                    "description": "Include Gmail unread counts (requires Gmail auth). Default true.",
                },
                "notify": {
                    "type": "boolean",
                    "description": "Fire a Windows toast notification with a one-line summary. Default false.",
                },
            },
        },
    },
    # ── Screen OCR ────────────────────────────────────────────────────────────
    {
        "name": "read_screen_text",
        "description": (
            "Take a screenshot of the current screen (or a region) and extract all visible text using Claude vision. "
            "Use when Ryan says 'read what's on my screen', 'what does that error say', or references something visible "
            "that he hasn't explicitly typed out."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "description": "Optional screen region: 'full' (default), 'top', 'bottom', 'left', 'right', or 'active_window'.",
                },
                "instruction": {
                    "type": "string",
                    "description": "What to extract or focus on. E.g. 'extract the error message', 'list all visible text'. Defaults to extract all text.",
                },
            },
        },
    },
    # ── Calendar ──────────────────────────────────────────────────────────────
    {
        "name": "calendar_events",
        "description": "Fetch upcoming Google Calendar events. Use for morning briefs, scheduling questions, or 'what do I have today/this week'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days ahead to look. 1=today, 7=this week. Default 1.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max events to return. Default 20.",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "Calendar ID. 'primary' for main calendar. Default 'primary'.",
                },
            },
        },
    },
    # ── Inbox scan ────────────────────────────────────────────────────────────
    {
        "name": "gmail_scan_inbox",
        "description": (
            "Scan Ryan's unread Gmail inbox, classify emails using AI, and auto-create tasks and reminders. "
            "Detects: bills due, interviews, client requests, client messages, calendar invites, and action items. "
            "Use this when Ryan says 'check my inbox', 'scan my emails', or 'what do I need to action'. "
            "Set dry_run=true to preview what would be created without writing anything."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "max_emails": {"type": "integer", "description": "Max unread emails to scan. Default 30."},
                "account":    {"type": "string",  "description": "Gmail account alias: main, sales, personal. Defaults to active account."},
                "auto_task":  {"type": "boolean", "description": "Auto-create tasks from actionable emails. Default true."},
                "dry_run":    {"type": "boolean", "description": "Classify and report without writing tasks. Default false."},
            },
        },
    },
    # ── Send Email ────────────────────────────────────────────────────────────
    {
        "name": "send_email",
        "description": (
            "Send an email from Ryan's Gmail account. "
            "Use after drafting and confirming with Ryan. "
            "Always confirm the recipient, subject, and body before calling this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string", "description": "Recipient email address (or comma-separated list)."},
                "subject": {"type": "string", "description": "Email subject line."},
                "body":    {"type": "string", "description": "Plain-text email body."},
                "cc":      {"type": "string", "description": "Optional CC addresses, comma-separated."},
                "account": {
                    "type": "string",
                    "description": "Gmail account alias to send from: main, sales, or personal. Defaults to currently active account.",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    # ── Clipboard ─────────────────────────────────────────────────────────────
    {
        "name": "clipboard_read",
        "description": "Read the current contents of the Windows clipboard. Use this when Ryan says 'summarize what I copied', 'what's on my clipboard', or pastes context implicitly.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "clipboard_write",
        "description": "Write text to the Windows clipboard so Ryan can paste it anywhere.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to place on the clipboard."},
            },
            "required": ["text"],
        },
    },
    # ── Window context ────────────────────────────────────────────────────────
    {
        "name": "get_active_window",
        "description": "Return the title and process name of the window Ryan currently has focused. Use this to understand what Ryan is working on without asking.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "focus_window",
        "description": "Bring a window to the foreground by application name or partial title. E.g. 'Chrome', 'VS Code', 'Spotify'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "Application name or partial window title to focus."},
            },
            "required": ["app"],
        },
    },
    # ── GitHub ───────────────────────────────────────────────────────────────
    {
        "name": "github",
        "description": "Interact with GitHub: list repos/issues/PRs, create issue, or fetch a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "list_repos|list_issues|create_issue|list_prs|get_file",
                },
                "repo": {"type": "string", "description": "owner/repo format"},
                "title": {"type": "string"},
                "body": {"type": "string"},
                "path": {"type": "string"},
                "ref": {"type": "string", "description": "branch, tag, or commit SHA for get_file"},
            },
            "required": ["action"],
        },
    },
    # ── Run Python ───────────────────────────────────────────────────────────
    {
        "name": "run_python",
        "description": "Execute a Python snippet and return stdout/stderr. Use for calculations, data transforms, quick scripts, and anything that benefits from real computation. Runs in a subprocess so it cannot corrupt Guppy's state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute."},
                "timeout": {"type": "integer", "description": "Max seconds to wait. Default 10."},
            },
            "required": ["code"],
        },
    },
    # ── Code Ops ────────────────────────────────────────────────────────────
    {
        "name": "test_targeted",
        "description": "Run targeted pytest tests on a file/path with optional -k filter. Use for fast verification after code edits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Test file, folder, or node id (e.g. tests/test_api.py::test_status)."},
                "k": {"type": "string", "description": "Optional pytest -k expression."},
                "maxfail": {"type": "integer", "description": "Stop after N failures. Default 1.", "default": 1},
                "quiet": {"type": "boolean", "description": "Use -q output. Default true.", "default": True},
            },
            "required": ["target"],
        },
    },
    {
        "name": "lint_fix",
        "description": "Run ruff lint checks with optional --fix against one or more paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "description": "Files/directories to lint. Default ['.'].",
                    "items": {"type": "string"},
                },
                "fix": {"type": "boolean", "description": "Apply auto-fixes. Default true.", "default": True},
            },
        },
    },
    {
        "name": "typecheck_targeted",
        "description": "Run mypy type checking on one target path/module.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Path or module to type-check."},
                "strict": {"type": "boolean", "description": "Enable strict mode for this run.", "default": False},
            },
            "required": ["target"],
        },
    },
    {
        "name": "git_patch_summary",
        "description": "Summarize git changes with status and compact diff stats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "staged": {"type": "boolean", "description": "Include staged diff stats.", "default": True},
                "unstaged": {"type": "boolean", "description": "Include unstaged diff stats.", "default": True},
                "name_only": {"type": "boolean", "description": "Include changed file lists.", "default": True},
            },
        },
    },
    # ── Windows Notification ─────────────────────────────────────────────────
    {
        "name": "notify",
        "description": "Send a Windows 11 toast notification to Ryan. Use for async alerts, reminders that fire mid-task, or when completing long background work.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title":   {"type": "string", "description": "Notification title."},
                "message": {"type": "string", "description": "Notification body."},
                "duration": {"type": "string", "enum": ["short", "long"], "description": "Display duration. Default: short."},
            },
            "required": ["title", "message"],
        },
    },
    # ── Web Summarize ────────────────────────────────────────────────────────
    {
        "name": "web_summarize",
        "description": "Fetch a URL and return a summary or extracted content. Uses Firecrawl if FIRECRAWL_API_KEY is set (handles JS-heavy pages), otherwise falls back to plain HTTP + Claude summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch and summarize."},
                "instruction": {"type": "string", "description": "What to extract or summarize. Default: summarize the main content."},
            },
            "required": ["url"],
        },
    },
]


def _validate_tool_input(name: str, inp: dict) -> str:
    schema = next((t.get("input_schema", {}) for t in TOOLS if t.get("name") == name), None)
    if schema is None:
        return ""
    required = schema.get("required", []) if isinstance(schema, dict) else []
    missing = [k for k in required if k not in inp]
    if missing:
        return f"Missing required input fields: {', '.join(missing)}"
