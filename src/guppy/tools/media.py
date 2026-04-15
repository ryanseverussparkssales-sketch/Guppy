"""
media_tools.py - Gmail, Calendar, Spotify, and YouTube helpers.

Spotify and YouTube live in `src.guppy.tools.media_streaming` so this module
stays below the structural line cap while preserving the long-lived import
surface that the rest of the repo uses.
"""

from __future__ import annotations

import os
from pathlib import Path

from src.guppy.tools.media_streaming import (
    _get_spotify,
    _media_key,
    spotify_current,
    spotify_next,
    spotify_pause,
    spotify_play,
    spotify_prev,
    spotify_resume,
    spotify_volume,
    youtube_play,
    youtube_search,
)


_GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
_GMAIL_CREDS_DEFAULT = str(Path.home() / "gmail_credentials.json")
_GMAIL_ACCOUNTS: dict[str, tuple[str, str]] = {
    "main": ("ryanseverussparkssales@gmail.com", str(Path.home() / "gmail_credentials_main.json")),
    "sales": ("trsparkssales@gmail.com", str(Path.home() / "gmail_credentials_sales.json")),
    "personal": ("ryanseverussparks@gmail.com", str(Path.home() / "gmail_credentials_personal.json")),
}
_current_gmail_account: str = "main"


def _token_path(alias: str) -> str:
    return str(Path.home() / f".guppy_gmail_token_{alias}.json")


def gmail_switch_account(alias: str) -> str:
    """Switch the active Gmail account by alias (main / sales / personal)."""
    global _current_gmail_account
    alias = alias.strip().lower()
    if alias not in _GMAIL_ACCOUNTS:
        for candidate_alias, (email, _creds_path) in _GMAIL_ACCOUNTS.items():
            if alias in email.lower():
                alias = candidate_alias
                break
        else:
            known = ", ".join(f"{item_alias} ({email})" for item_alias, (email, _creds) in _GMAIL_ACCOUNTS.items())
            return f"Unknown account '{alias}'. Known accounts:\n  {known}"

    _current_gmail_account = alias
    email, _ = _GMAIL_ACCOUNTS[alias]
    _service, err = _get_gmail()
    if err:
        return f"Switched to '{alias}' but auth failed: {err}"
    return f"Active Gmail account: {alias} ({email})"


def gmail_list_accounts() -> str:
    """List all configured Gmail accounts and show which is active."""
    lines = ["Gmail accounts:"]
    for alias, (email, creds_path) in _GMAIL_ACCOUNTS.items():
        token_exists = Path(_token_path(alias)).exists()
        creds_exists = Path(creds_path).exists()
        active = " [active]" if alias == _current_gmail_account else ""
        authed = "authed" if token_exists else "not yet authed"
        missing = "  [creds missing]" if not creds_exists else ""
        lines.append(f"  {alias:10s} {email}  [{authed}]{missing}{active}")
    return "\n".join(lines)


def _get_gmail():
    """Return (service, None) or (None, error_str) for the active account."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        return None, (
            "Gmail API packages not installed.\n"
            "Run: pip install google-api-python-client google-auth-oauthlib"
        )

    email, default_creds = _GMAIL_ACCOUNTS.get(_current_gmail_account, ("unknown", _GMAIL_CREDS_DEFAULT))
    creds_path = os.environ.get("GMAIL_CREDENTIALS_PATH", default_creds)
    token = _token_path(_current_gmail_account)
    creds = None

    if Path(token).exists():
        creds = Credentials.from_authorized_user_file(token, _GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                return None, (
                    f"Token refresh failed for {email}: {exc}\n"
                    f"Delete {token} and switch accounts again to re-authenticate."
                )
        else:
            if not Path(creds_path).exists():
                return None, (
                    f"Gmail credentials not found at: {creds_path}\n\n"
                    "One-time setup:\n"
                    "  1. console.cloud.google.com -> APIs & Services -> Credentials\n"
                    "  2. Create OAuth 2.0 Client ID (Desktop app) -> download JSON\n"
                    "  3. Place at ~/gmail_credentials.json\n"
                    "  4. Run gmail_switch_account to trigger browser auth per account."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, _GMAIL_SCOPES)
            creds = flow.run_local_server(port=0, login_hint=email)

        Path(token).write_text(creds.to_json())

    try:
        return build("gmail", "v1", credentials=creds), None
    except Exception as exc:
        return None, f"Gmail service error: {exc}"


def _fetch_ids(service, query: str, max_results: int) -> list:
    ids, page_token = [], None
    while len(ids) < max_results:
        kw = {"userId": "me", "q": query, "maxResults": min(500, max_results - len(ids))}
        if page_token:
            kw["pageToken"] = page_token
        result = service.users().messages().list(**kw).execute()
        ids += [message["id"] for message in result.get("messages", [])]
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return ids


def _trash_ids(service, ids: list) -> int:
    trashed = 0
    for index in range(0, len(ids), 1000):
        chunk = ids[index:index + 1000]
        service.users().messages().batchModify(
            userId="me",
            body={"ids": chunk, "addLabelIds": ["TRASH"], "removeLabelIds": ["INBOX"]},
        ).execute()
        trashed += len(chunk)
    return trashed


def gmail_unread_count(alias: str | None = None) -> tuple[int, str]:
    """Return (unread_count, error_str) for a Gmail account."""
    global _current_gmail_account
    original = _current_gmail_account
    try:
        if alias and alias != _current_gmail_account:
            _current_gmail_account = alias
        service, err = _get_gmail()
        if err:
            return -1, err
        label = service.users().labels().get(userId="me", id="INBOX").execute()
        return label.get("messagesUnread", 0), ""
    except Exception as exc:
        return -1, str(exc)
    finally:
        _current_gmail_account = original


def gmail_purge(query: str, max_results: int = 500) -> str:
    """Move emails matching a Gmail search query to trash."""
    service, err = _get_gmail()
    if err:
        return err
    try:
        ids = _fetch_ids(service, query, max_results)
        if not ids:
            return f"No emails found matching: {query}"
        count = _trash_ids(service, ids)
        return f"Moved {count} email(s) to trash.  Query: {query}"
    except Exception as exc:
        return f"Gmail purge error: {exc}"


def gmail_purge_label(label: str) -> str:
    """Move all emails in a Gmail label/category to trash."""
    labels = {
        "promotions": "CATEGORY_PROMOTIONS",
        "social": "CATEGORY_SOCIAL",
        "updates": "CATEGORY_UPDATES",
        "forums": "CATEGORY_FORUMS",
        "spam": "SPAM",
        "trash": "TRASH",
        "inbox": "INBOX",
        "unread": "UNREAD",
    }
    label_id = labels.get(label.lower(), label.upper())
    return gmail_purge(f"label:{label_id}")


def gmail_purge_sender(email: str) -> str:
    return gmail_purge(f"from:{email}")


def gmail_purge_older_than(days: int) -> str:
    return gmail_purge(f"older_than:{days}d")


def gmail_empty_trash() -> str:
    service, err = _get_gmail()
    if err:
        return err
    try:
        service.users().emptyTrash(userId="me").execute()
        return "Trash permanently emptied."
    except Exception as exc:
        return f"Empty trash error: {exc}"


def _mark_read_ids(service, ids: list) -> int:
    marked = 0
    for index in range(0, len(ids), 1000):
        chunk = ids[index:index + 1000]
        service.users().messages().batchModify(
            userId="me",
            body={"ids": chunk, "removeLabelIds": ["UNREAD"]},
        ).execute()
        marked += len(chunk)
    return marked


_SMART_CLEANUP_STEPS = [
    ("Unsubscribe mail", "unsubscribe -in:trash -in:starred", "trash"),
    ("No-reply bulk mail", "from:noreply -in:trash -in:starred", "trash"),
    ("Newsletters", "newsletter -in:trash -in:starred", "trash"),
    ("Old promotions (1y+)", "older_than:1y category:promotions -in:starred -in:trash", "trash"),
    ("Old mail (1y+)", "older_than:1y -in:important -in:starred -in:trash", "trash"),
    ("Old unread (30d+)", "is:unread older_than:30d -in:trash", "read"),
]


def gmail_smart_cleanup(max_per_step: int = 500) -> str:
    """Run a standard inbox cleanup sequence."""
    service, err = _get_gmail()
    if err:
        return err

    lines = ["Gmail Smart Cleanup - starting...\n"]
    total_trashed = 0
    total_read = 0

    for label, query, action in _SMART_CLEANUP_STEPS:
        try:
            ids = _fetch_ids(service, query, max_per_step)
            if not ids:
                lines.append(f"  OK {label}: nothing to clean")
                continue
            if action == "trash":
                count = _trash_ids(service, ids)
                total_trashed += count
                lines.append(f"  TRASH {label}: {count} moved to trash")
            elif action == "read":
                count = _mark_read_ids(service, ids)
                total_read += count
                lines.append(f"  READ {label}: {count} marked as read")
        except Exception as exc:
            lines.append(f"  WARN {label}: error -> {exc}")

    lines.append(f"\nDone. Trashed: {total_trashed}  |  Marked read: {total_read}")
    return "\n".join(lines)


def gmail_scan_inbox(
    max_emails: int = 30,
    account: str = "",
    auto_task: bool = True,
    dry_run: bool = False,
) -> str:
    """Scan unread inbox emails, classify them with AI, and auto-create tasks/reminders."""
    import json as _json
    import os as _os
    import re as _re

    if account:
        gmail_switch_account(account)

    service, err = _get_gmail()
    if err:
        return err

    try:
        result = service.users().messages().list(
            userId="me",
            q="is:unread in:inbox",
            maxResults=max_emails,
        ).execute()
    except Exception as exc:
        return f"Error fetching inbox: {exc}"

    messages = result.get("messages", [])
    if not messages:
        return "No unread emails in inbox."

    email_summaries = []
    for message in messages:
        try:
            msg = service.users().messages().get(
                userId="me",
                id=message["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {header["name"]: header["value"] for header in msg.get("payload", {}).get("headers", [])}
            snippet = msg.get("snippet", "")[:200]
            email_summaries.append(
                {
                    "id": message["id"],
                    "from": headers.get("From", "unknown"),
                    "subject": headers.get("Subject", "(no subject)"),
                    "date": headers.get("Date", ""),
                    "snippet": snippet,
                }
            )
        except Exception:
            continue

    if not email_summaries:
        return "Could not fetch email details."

    emails_text = "\n".join(
        f"[{index + 1}] FROM: {row['from']}\n"
        f"    SUBJECT: {row['subject']}\n"
        f"    DATE: {row['date']}\n"
        f"    PREVIEW: {row['snippet']}"
        for index, row in enumerate(email_summaries)
    )

    classify_prompt = f"""You are classifying emails for Ryan Sparks, a business owner.
For each email, return a JSON array. Each element must have:
  - "index": (1-based int matching the list below)
  - "category": one of: bill_due | interview | client_request | client_message | calendar_invite | action_required | fyi
  - "priority": high | medium | low
  - "action": short imperative task string (e.g. "Pay electricity bill by May 5", "Reply to John re: proposal", "Prepare for 2pm interview with Acme")
  - "due_hint": natural language date if inferable from email (e.g. "May 5", "tomorrow 2pm"), else ""
  - "skip_task": true if category is fyi and no action needed, else false

Emails to classify:
{emails_text}

Return ONLY the JSON array. No markdown, no explanation."""

    try:
        import anthropic as _ant

        client = _ant.Anthropic(api_key=_os.environ.get("ANTHROPIC_API_KEY", ""))
        resp = client.messages.create(
            model=_os.environ.get("ANTHROPIC_BACKUP_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=2000,
            messages=[{"role": "user", "content": classify_prompt}],
        )
        raw = resp.content[0].text.strip()
        raw = _re.sub(r"^```[a-z]*\n?", "", raw)
        raw = _re.sub(r"\n?```$", "", raw)
        classifications = _json.loads(raw)
    except Exception as exc:
        return f"Classification error: {exc}"

    cls_map = {item["index"]: item for item in classifications if isinstance(item, dict)}
    lines = [f"Inbox scan - {len(email_summaries)} unread emails\n"]
    tasks_created = 0
    category_icons = {
        "bill_due": "[BILL]",
        "interview": "[INT]",
        "client_request": "[REQ]",
        "client_message": "[MSG]",
        "calendar_invite": "[CAL]",
        "action_required": "[ACT]",
        "fyi": "[FYI]",
    }

    for index, email in enumerate(email_summaries, start=1):
        cls = cls_map.get(index, {})
        cat = cls.get("category", "fyi")
        priority = cls.get("priority", "low")
        action = cls.get("action", "")
        due_hint = cls.get("due_hint", "")
        skip = cls.get("skip_task", False)
        icon = category_icons.get(cat, "[ ]")

        sender_short = email["from"].split("<")[0].strip() or email["from"]
        lines.append(f"{icon} [{priority.upper()}]  {email['subject']}")
        lines.append(f"   From: {sender_short}")
        if action:
            lines.append(f"   Action: {action}")

        if auto_task and not dry_run and not skip and action:
            try:
                import guppy_memory as _gmem

                due = due_hint if due_hint else ""
                _gmem.add_task(action, due)
                tasks_created += 1
                lines.append("   -> Task created")

                if cat in ("bill_due", "interview") and due_hint and DAEMON:
                    try:
                        from guppy_daemon import get_daemon_manager

                        mgr = get_daemon_manager()
                        mgr.task_scheduler.schedule_reminder(action, due_hint)
                        lines.append(f"   -> Reminder set for: {due_hint}")
                    except Exception:
                        pass
            except Exception as task_err:
                lines.append(f"   -> Task error: {task_err}")
        elif dry_run and not skip and action:
            tasks_created += 1
            lines.append("   -> [DRY RUN] Would create task")

        lines.append("")

    lines.append(f"Summary: {tasks_created} task{'s' if tasks_created != 1 else ''} created from {len(email_summaries)} emails")
    if dry_run:
        lines.append("(dry_run=True - no tasks were actually written)")
    return "\n".join(lines)


DAEMON = False
try:
    from guppy_daemon import get_daemon_manager as _get_dm  # noqa: F401

    DAEMON = True
except ImportError:
    pass


def gmail_send(to: str, subject: str, body: str, cc: str = "", account: str = "") -> str:
    """Send an email from the active (or specified) Gmail account."""
    import base64
    import email.mime.multipart
    import email.mime.text

    if account:
        gmail_switch_account(account)

    service, err = _get_gmail()
    if err:
        return err

    msg = email.mime.multipart.MIMEMultipart()
    msg["to"] = to
    msg["subject"] = subject
    if cc:
        msg["cc"] = cc
    msg.attach(email.mime.text.MIMEText(body, "plain"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent. Message ID: {sent['id']}  |  To: {to}  |  Subject: {subject}"
    except Exception as exc:
        return f"Error sending email: {exc}"


_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
_CALENDAR_CREDS_DEFAULT = str(Path.home() / "google_calendar_credentials.json")
_CALENDAR_TOKEN = str(Path.home() / ".guppy_calendar_token.json")


def _get_calendar():
    """Return (service, None) or (None, error_str)."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        return None, "google-api-python-client not installed."

    creds_path = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS_PATH", _CALENDAR_CREDS_DEFAULT)
    creds = None

    if Path(_CALENDAR_TOKEN).exists():
        creds = Credentials.from_authorized_user_file(_CALENDAR_TOKEN, _CALENDAR_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                return None, f"Calendar token refresh failed: {exc}\nDelete {_CALENDAR_TOKEN} to re-auth."
        else:
            if not Path(creds_path).exists():
                return None, (
                    f"Google Calendar credentials not found at: {creds_path}\n\n"
                    "One-time setup:\n"
                    "  1. console.cloud.google.com -> APIs & Services -> Enable Google Calendar API\n"
                    "  2. Create OAuth 2.0 Client ID (Desktop app) -> download JSON\n"
                    "  3. Save as ~/google_calendar_credentials.json\n"
                    "     OR set GOOGLE_CALENDAR_CREDENTIALS_PATH in .env"
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, _CALENDAR_SCOPES)
            creds = flow.run_local_server(port=0)
        Path(_CALENDAR_TOKEN).write_text(creds.to_json())

    try:
        return build("calendar", "v3", credentials=creds), None
    except Exception as exc:
        return None, f"Calendar service error: {exc}"


def calendar_events(days: int = 1, max_results: int = 20, calendar_id: str = "primary") -> str:
    """Fetch upcoming calendar events."""
    from datetime import datetime, timedelta, timezone

    service, err = _get_calendar()
    if err:
        return err

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)

    try:
        result = service.events().list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception as exc:
        return f"Error fetching calendar events: {exc}"

    events = result.get("items", [])
    if not events:
        label = "today" if days == 1 else f"the next {days} days"
        return f"No events found for {label}."

    lines = [f"Calendar events - next {days} day(s):"]
    for event in events:
        start = event.get("start", {})
        dt_str = start.get("dateTime", start.get("date", ""))
        try:
            if "T" in dt_str:
                dt = datetime.fromisoformat(dt_str)
                time_label = dt.strftime("%a %b %d  %I:%M %p").lstrip("0").replace("  ", " ")
            else:
                dt = datetime.fromisoformat(dt_str)
                time_label = dt.strftime("%a %b %d  (all day)")
        except Exception:
            time_label = dt_str

        summary = event.get("summary", "(no title)")
        location = event.get("location", "")
        loc_str = f"  @ {location}" if location else ""
        lines.append(f"  {time_label}  -  {summary}{loc_str}")

    return "\n".join(lines)
