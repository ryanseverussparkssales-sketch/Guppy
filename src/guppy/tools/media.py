"""
media_tools.py — Spotify, YouTube, and Gmail purge tools
=========================================================

Spotify
  Requires env vars:  SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
  Optional:           SPOTIFY_REDIRECT_URI  (default: http://localhost:8888/callback)
  Get credentials:    developer.spotify.com → Create App (free)
  Falls back to Windows media keys + spotify: URI launch when API is not configured.

YouTube
  Uses yt-dlp when installed (pip install yt-dlp) for direct video lookup.
  Falls back to opening a browser search when yt-dlp is absent.

Gmail
  Requires:   gmail_credentials.json from Google Cloud Console
  Placement:  ~/gmail_credentials.json  OR  set GMAIL_CREDENTIALS_PATH env var
  Scopes:     gmail.modify  (moves to trash — recoverable)
  Setup:
    1. console.cloud.google.com → New Project
    2. Enable Gmail API
    3. Create OAuth credentials (Desktop app) → download as gmail_credentials.json
    4. Place at ~/gmail_credentials.json or set GMAIL_CREDENTIALS_PATH env var
    5. First run opens a browser for one-time auth; token is cached at ~/.guppy_gmail_token.json
"""

import os
import subprocess
import urllib.parse
import webbrowser
from pathlib import Path

from utils.connector_manager import read_machine_secret


# ── Spotify ────────────────────────────────────────────────────────────────────

def _get_spotify():
    """Return (spotipy.Spotify, None) or (None, setup_instructions_str)."""
    cid     = read_machine_secret("SPOTIFY_CLIENT_ID")
    csecret = read_machine_secret("SPOTIFY_CLIENT_SECRET")
    if not cid or not csecret:
        return None, (
            "Spotify API not configured. Add to launch_guppy.bat / launch_council.bat:\n"
            "  set SPOTIFY_CLIENT_ID=your-client-id\n"
            "  set SPOTIFY_CLIENT_SECRET=your-client-secret\n"
            "Get free credentials at developer.spotify.com → Create App."
        )
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=cid,
            client_secret=csecret,
            redirect_uri=read_machine_secret("SPOTIFY_REDIRECT_URI", fallback="http://localhost:8888/callback"),
            scope=(
                "user-modify-playback-state "
                "user-read-playback-state "
                "user-read-currently-playing"
            ),
            cache_path=str(Path.home() / ".guppy_spotify_token"),
            open_browser=True,
        ))
        return sp, None
    except ImportError:
        return None, "spotipy not installed — run: pip install spotipy"
    except Exception as e:
        return None, f"Spotify auth error: {e}"


def _media_key(action: str) -> str:
    """Send a Windows media key via PowerShell virtual key codes."""
    vk = {"play_pause": "0xB3", "next": "0xB0", "prev": "0xB1", "stop": "0xB2"}.get(action)
    if not vk:
        return f"Unknown media action: {action}"
    ps = (
        "Add-Type -TypeDefinition '"
        "using System; using System.Runtime.InteropServices; public class MK {"
        "[DllImport(\"user32.dll\")] public static extern void keybd_event(byte bVk, byte bScan, int dwFlags, int extra);"
        "}'; "
        f"[MK]::keybd_event({vk},0,0,0); Start-Sleep -Milliseconds 50; [MK]::keybd_event({vk},0,2,0)"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, timeout=5)
    return f"Media key sent: {action}"


def spotify_play(query: str) -> str:
    """Search Spotify and play the top track, artist, or playlist result."""
    sp, err = _get_spotify()
    if err:
        webbrowser.open(f"spotify:search:{urllib.parse.quote(query)}")
        return f"Opened Spotify search for: {query}\n(API not configured — {err})"
    try:
        results = sp.search(q=query, type="track,artist,playlist", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        if tracks:
            uri    = tracks[0]["uri"]
            name   = tracks[0]["name"]
            artist = tracks[0]["artists"][0]["name"]
            sp.start_playback(uris=[uri])
            return f"Now playing: {name} — {artist}"
        artists = results.get("artists", {}).get("items", [])
        if artists:
            sp.start_playback(context_uri=artists[0]["uri"])
            return f"Playing artist: {artists[0]['name']}"
        playlists = results.get("playlists", {}).get("items", [])
        if playlists:
            sp.start_playback(context_uri=playlists[0]["uri"])
            return f"Playing playlist: {playlists[0]['name']}"
        return f"No Spotify results for: {query}"
    except Exception as e:
        return f"Spotify play error: {e}"


def spotify_pause() -> str:
    sp, err = _get_spotify()
    if err:
        return _media_key("play_pause")
    try:
        sp.pause_playback()
        return "Spotify paused."
    except Exception:
        return _media_key("play_pause")


def spotify_resume() -> str:
    sp, err = _get_spotify()
    if err:
        return _media_key("play_pause")
    try:
        sp.start_playback()
        return "Spotify resumed."
    except Exception:
        return _media_key("play_pause")


def spotify_next() -> str:
    sp, err = _get_spotify()
    if err:
        return _media_key("next")
    try:
        sp.next_track()
        return "Skipped to next track."
    except Exception:
        return _media_key("next")


def spotify_prev() -> str:
    sp, err = _get_spotify()
    if err:
        return _media_key("prev")
    try:
        sp.previous_track()
        return "Back to previous track."
    except Exception:
        return _media_key("prev")


def spotify_current() -> str:
    """Get the currently playing track on Spotify (requires API)."""
    sp, err = _get_spotify()
    if err:
        return f"Current track requires Spotify API.\n{err}"
    try:
        playing = sp.currently_playing()
        if not playing or not playing.get("item"):
            return "Nothing currently playing on Spotify."
        item       = playing["item"]
        name       = item["name"]
        artist     = ", ".join(a["name"] for a in item["artists"])
        album      = item["album"]["name"]
        prog_ms    = playing.get("progress_ms", 0)
        dur_ms     = item["duration_ms"]
        progress   = f"{prog_ms // 60000}:{(prog_ms // 1000) % 60:02d}"
        total      = f"{dur_ms // 60000}:{(dur_ms // 1000) % 60:02d}"
        status     = "▶" if playing.get("is_playing") else "⏸"
        return f"{status} {name}\n  Artist: {artist}\n  Album: {album}\n  {progress} / {total}"
    except Exception as e:
        return f"Could not get current track: {e}"


def spotify_volume(level: int) -> str:
    sp, err = _get_spotify()
    if err:
        return f"Volume control requires Spotify API.\n{err}"
    level = max(0, min(100, level))
    try:
        sp.volume(level)
        return f"Spotify volume: {level}%"
    except Exception as e:
        return f"Volume error: {e}"


# ── YouTube ────────────────────────────────────────────────────────────────────

def youtube_play(query: str) -> str:
    """Open a YouTube video in the browser. Accepts a search query or direct URL."""
    if "youtube.com" in query or "youtu.be" in query:
        webbrowser.open(query)
        return f"Opened: {query}"
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if info and info.get("entries"):
                entry = info["entries"][0]
                vid_id = entry.get("id", "")
                title  = entry.get("title", query)
                url    = f"https://www.youtube.com/watch?v={vid_id}"
                webbrowser.open(url)
                return f"Opened: {title}\n{url}"
    except ImportError:
        pass
    except Exception:
        pass
    # Fallback: open search page
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    webbrowser.open(url)
    return (
        f"Opened YouTube search for: {query}\n"
        "Tip: install yt-dlp for direct video lookup — pip install yt-dlp"
    )


def youtube_search(query: str) -> str:
    """Search YouTube and return top 5 results with titles and URLs."""
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            if not info or not info.get("entries"):
                return "No results found."
            lines = [f"YouTube — top results for '{query}':"]
            for i, e in enumerate(info["entries"][:5], 1):
                title  = e.get("title", "Unknown")
                vid_id = e.get("id", "")
                dur    = e.get("duration")
                dur_s  = f"  [{dur // 60}:{dur % 60:02d}]" if dur else ""
                lines.append(f"{i}. {title}{dur_s}\n   https://youtube.com/watch?v={vid_id}")
            return "\n".join(lines)
    except ImportError:
        pass
    except Exception:
        pass
    # Fallback: DuckDuckGo site:youtube.com search
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(
            f"https://html.duckduckgo.com/html/?q=site:youtube.com+{urllib.parse.quote(query)}",
            headers=headers, timeout=10,
        )
        soup    = BeautifulSoup(resp.text, "html.parser")
        results = []
        for r in soup.select(".result")[:5]:
            t = r.select_one(".result__title")
            u = r.select_one(".result__url")
            if t:
                results.append(t.get_text(strip=True) + ("\n   " + u.get_text(strip=True) if u else ""))
        return "\n\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search failed: {e}"


# ── Gmail — multi-account ──────────────────────────────────────────────────────

_GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Shared OAuth client credentials file (one file works for all accounts).
# Placed at ~/gmail_credentials.json by default.
_GMAIL_CREDS_DEFAULT = str(Path.home() / "gmail_credentials.json")

# Known accounts — alias → (email, credentials_file)
# Each account has its own Google Cloud project / OAuth client.
# Tokens cached at ~/.guppy_gmail_token_{alias}.json
_GMAIL_ACCOUNTS: dict[str, tuple[str, str]] = {
    "main":     ("ryanseverussparkssales@gmail.com", str(Path.home() / "gmail_credentials_main.json")),
    "sales":    ("trsparkssales@gmail.com",           str(Path.home() / "gmail_credentials_sales.json")),
    "personal": ("ryanseverussparks@gmail.com",       str(Path.home() / "gmail_credentials_personal.json")),
}

# Currently active account alias (module-level state, resets on restart)
_current_gmail_account: str = "main"


def _token_path(alias: str) -> str:
    return str(Path.home() / f".guppy_gmail_token_{alias}.json")


def gmail_switch_account(alias: str) -> str:
    """Switch the active Gmail account by alias (main / sales / personal).
    Triggers a browser OAuth flow on first use of a new account.
    """
    global _current_gmail_account
    alias = alias.strip().lower()

    # Accept email addresses too
    if alias not in _GMAIL_ACCOUNTS:
        for a, (email, _) in _GMAIL_ACCOUNTS.items():
            if alias in email.lower():
                alias = a
                break
        else:
            known = ", ".join(f"{a} ({e})" for a, (e, _) in _GMAIL_ACCOUNTS.items())
            return f"Unknown account '{alias}'. Known accounts:\n  {known}"

    _current_gmail_account = alias
    email, _ = _GMAIL_ACCOUNTS[alias]

    # Eagerly authenticate so the user sees any browser prompt now, not mid-task
    svc, err = _get_gmail()
    if err:
        return f"Switched to '{alias}' but auth failed: {err}"
    return f"Active Gmail account: {alias} ({email})"


def gmail_list_accounts() -> str:
    """List all configured Gmail accounts and show which is active."""
    lines = ["Gmail accounts:"]
    for alias, (email, creds_path) in _GMAIL_ACCOUNTS.items():
        token_exists = Path(_token_path(alias)).exists()
        creds_exists = Path(creds_path).exists()
        active  = " [active]" if alias == _current_gmail_account else ""
        authed  = "authed"     if token_exists else "not yet authed"
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
    token      = _token_path(_current_gmail_account)
    creds      = None

    if Path(token).exists():
        creds = Credentials.from_authorized_user_file(token, _GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                return None, (
                    f"Token refresh failed for {email}: {e}\n"
                    f"Delete {token} and switch accounts again to re-authenticate."
                )
        else:
            if not Path(creds_path).exists():
                return None, (
                    f"Gmail credentials not found at: {creds_path}\n\n"
                    "One-time setup:\n"
                    "  1. console.cloud.google.com → APIs & Services → Credentials\n"
                    "  2. Create OAuth 2.0 Client ID (Desktop app) → download JSON\n"
                    "  3. Place at ~/gmail_credentials.json\n"
                    "  4. Run gmail_switch_account to trigger browser auth per account."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, _GMAIL_SCOPES)
            # login_hint pre-fills the Google account chooser with the right email
            creds = flow.run_local_server(port=0, login_hint=email)

        Path(token).write_text(creds.to_json())

    try:
        return build("gmail", "v1", credentials=creds), None
    except Exception as e:
        return None, f"Gmail service error: {e}"


def _fetch_ids(service, query: str, max_results: int) -> list:
    ids, page_token = [], None
    while len(ids) < max_results:
        kw = {"userId": "me", "q": query, "maxResults": min(500, max_results - len(ids))}
        if page_token:
            kw["pageToken"] = page_token
        result     = service.users().messages().list(**kw).execute()
        ids       += [m["id"] for m in result.get("messages", [])]
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return ids


def _trash_ids(service, ids: list) -> int:
    trashed = 0
    for i in range(0, len(ids), 1000):
        chunk = ids[i:i + 1000]
        service.users().messages().batchModify(
            userId="me",
            body={"ids": chunk, "addLabelIds": ["TRASH"], "removeLabelIds": ["INBOX"]},
        ).execute()
        trashed += len(chunk)
    return trashed


def gmail_unread_count(alias: str | None = None) -> tuple[int, str]:
    """Return (unread_count, error_str) for a Gmail account.

    Uses the INBOX label's messagesUnread field — one API call, no pagination.
    Pass alias to query a specific account without switching the active account.
    Returns (-1, error_str) on any failure.
    """
    global _current_gmail_account
    original = _current_gmail_account
    try:
        if alias and alias != _current_gmail_account:
            _current_gmail_account = alias
        svc, err = _get_gmail()
        if err:
            return -1, err
        label = svc.users().labels().get(userId="me", id="INBOX").execute()
        return label.get("messagesUnread", 0), ""
    except Exception as e:
        return -1, str(e)
    finally:
        _current_gmail_account = original


def gmail_purge(query: str, max_results: int = 500) -> str:
    """Move emails matching a Gmail search query to trash."""
    svc, err = _get_gmail()
    if err:
        return err
    try:
        ids = _fetch_ids(svc, query, max_results)
        if not ids:
            return f"No emails found matching: {query}"
        n = _trash_ids(svc, ids)
        return f"Moved {n} email(s) to trash.  Query: {query}"
    except Exception as e:
        return f"Gmail purge error: {e}"


def gmail_purge_label(label: str) -> str:
    """Move all emails in a Gmail label/category to trash.
    Common labels: promotions, social, updates, forums, spam, inbox, unread."""
    LABELS = {
        "promotions": "CATEGORY_PROMOTIONS",
        "social":     "CATEGORY_SOCIAL",
        "updates":    "CATEGORY_UPDATES",
        "forums":     "CATEGORY_FORUMS",
        "spam":       "SPAM",
        "trash":      "TRASH",
        "inbox":      "INBOX",
        "unread":     "UNREAD",
    }
    label_id = LABELS.get(label.lower(), label.upper())
    return gmail_purge(f"label:{label_id}")


def gmail_purge_sender(email: str) -> str:
    """Move all emails from a sender address to trash."""
    return gmail_purge(f"from:{email}")


def gmail_purge_older_than(days: int) -> str:
    """Move emails older than N days to trash."""
    return gmail_purge(f"older_than:{days}d")


def gmail_empty_trash() -> str:
    """Permanently delete all messages currently in the trash (irreversible)."""
    svc, err = _get_gmail()
    if err:
        return err
    try:
        svc.users().emptyTrash(userId="me").execute()
        return "Trash permanently emptied."
    except Exception as e:
        return f"Empty trash error: {e}"


def _mark_read_ids(service, ids: list) -> int:
    """Remove UNREAD label from a batch of message IDs. Returns count modified."""
    marked = 0
    for i in range(0, len(ids), 1000):
        chunk = ids[i:i + 1000]
        service.users().messages().batchModify(
            userId="me",
            body={"ids": chunk, "removeLabelIds": ["UNREAD"]},
        ).execute()
        marked += len(chunk)
    return marked


# Standard cleanup passes — ordered from most aggressive to least.
# Each entry: (label, gmail_query, action)
# action: "trash" | "read"
_SMART_CLEANUP_STEPS = [
    ("Unsubscribe mail",     "unsubscribe -in:trash -in:starred",                        "trash"),
    ("No-reply bulk mail",   "from:noreply -in:trash -in:starred",                       "trash"),
    ("Newsletters",          "newsletter -in:trash -in:starred",                         "trash"),
    ("Old promotions (1y+)", "older_than:1y category:promotions -in:starred -in:trash",  "trash"),
    ("Old mail (1y+)",       "older_than:1y -in:important -in:starred -in:trash",        "trash"),
    ("Old unread (30d+)",    "is:unread older_than:30d -in:trash",                       "read"),
]


def gmail_smart_cleanup(max_per_step: int = 500) -> str:
    """Run a standard inbox cleanup sequence — newsletters, no-reply, old mail, etc.

    Each step is reported individually so you can see what was touched.
    Uses the same OAuth credentials as the other gmail_* tools.
    """
    svc, err = _get_gmail()
    if err:
        return err

    lines = ["📬 Gmail Smart Cleanup — starting...\n"]
    total_trashed = 0
    total_read    = 0

    for label, query, action in _SMART_CLEANUP_STEPS:
        try:
            ids = _fetch_ids(svc, query, max_per_step)
            if not ids:
                lines.append(f"  ✓ {label}: nothing to clean")
                continue
            if action == "trash":
                n = _trash_ids(svc, ids)
                total_trashed += n
                lines.append(f"  🗑  {label}: {n} moved to trash")
            elif action == "read":
                n = _mark_read_ids(svc, ids)
                total_read += n
                lines.append(f"  ✅ {label}: {n} marked as read")
        except Exception as e:
            lines.append(f"  ⚠️  {label}: error — {e}")

    lines.append(f"\nDone. Trashed: {total_trashed}  |  Marked read: {total_read}")
    return "\n".join(lines)


def gmail_scan_inbox(
    max_emails: int = 30,
    account: str = "",
    auto_task: bool = True,
    dry_run: bool = False,
) -> str:
    """Scan unread inbox emails, classify them with AI, and auto-create tasks/reminders.

    Classifications handled:
      - bill_due       → task "Pay: <sender>" with due date
      - interview      → task + reminder for interview prep / attendance
      - client_request → task "Reply: <sender> — <subject>"
      - client_message → task if action implied, else logged
      - calendar_invite → task to accept/decline
      - action_required → generic task
      - fyi            → logged only, no task created

    Args:
        max_emails: Max unread emails to scan. Default 30.
        account:    Gmail alias to scan (main/sales/personal). Defaults to active account.
        auto_task:  If True, create tasks/reminders automatically. Default True.
        dry_run:    If True, classify and report but don't write tasks.
    """
    import json as _json
    import os as _os
    import re as _re

    if account:
        gmail_switch_account(account)

    svc, err = _get_gmail()
    if err:
        return err

    # Fetch unread message IDs
    try:
        result = svc.users().messages().list(
            userId="me", q="is:unread in:inbox", maxResults=max_emails
        ).execute()
    except Exception as e:
        return f"Error fetching inbox: {e}"

    messages = result.get("messages", [])
    if not messages:
        return "No unread emails in inbox."

    # Pull subject + sender snippet for each message (minimal API calls)
    email_summaries = []
    for m in messages:
        try:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            snippet = msg.get("snippet", "")[:200]
            email_summaries.append({
                "id":      m["id"],
                "from":    headers.get("From", "unknown"),
                "subject": headers.get("Subject", "(no subject)"),
                "date":    headers.get("Date", ""),
                "snippet": snippet,
            })
        except Exception:
            continue

    if not email_summaries:
        return "Could not fetch email details."

    # Build classification prompt for Claude
    emails_text = "\n".join(
        f"[{i+1}] FROM: {e['from']}\n    SUBJECT: {e['subject']}\n    DATE: {e['date']}\n    PREVIEW: {e['snippet']}"
        for i, e in enumerate(email_summaries)
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
        # Strip markdown code fences if model wrapped them
        raw = _re.sub(r"^```[a-z]*\n?", "", raw)
        raw = _re.sub(r"\n?```$", "", raw)
        classifications = _json.loads(raw)
    except Exception as e:
        return f"Classification error: {e}"

    # Build index map
    cls_map = {c["index"]: c for c in classifications if isinstance(c, dict)}

    # Process results — create tasks where appropriate
    lines = [f"Inbox scan — {len(email_summaries)} unread emails\n"]
    tasks_created = 0
    category_icons = {
        "bill_due":        "💳",
        "interview":       "🎤",
        "client_request":  "📋",
        "client_message":  "💬",
        "calendar_invite": "📅",
        "action_required": "⚡",
        "fyi":             "ℹ️",
    }

    for i, email in enumerate(email_summaries, start=1):
        cls = cls_map.get(i, {})
        cat      = cls.get("category", "fyi")
        priority = cls.get("priority", "low")
        action   = cls.get("action", "")
        due_hint = cls.get("due_hint", "")
        skip     = cls.get("skip_task", False)
        icon     = category_icons.get(cat, "•")

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
                lines.append(f"   → Task created")

                # For bills and interviews, also set a reminder if due_hint is specific enough
                if cat in ("bill_due", "interview") and due_hint and DAEMON:
                    try:
                        from guppy_daemon import get_daemon_manager
                        mgr = get_daemon_manager()
                        mgr.task_scheduler.schedule_reminder(action, due_hint)
                        lines.append(f"   → Reminder set for: {due_hint}")
                    except Exception:
                        pass
            except Exception as task_err:
                lines.append(f"   → Task error: {task_err}")
        elif dry_run and not skip and action:
            tasks_created += 1
            lines.append(f"   → [DRY RUN] Would create task")

        lines.append("")

    lines.append(f"Summary: {tasks_created} task{'s' if tasks_created != 1 else ''} created from {len(email_summaries)} emails")
    if dry_run:
        lines.append("(dry_run=True — no tasks were actually written)")
    return "\n".join(lines)


DAEMON = False
try:
    from guppy_daemon import get_daemon_manager as _get_dm  # noqa: F401
    DAEMON = True
except ImportError:
    pass


def gmail_send(to: str, subject: str, body: str, cc: str = "", account: str = "") -> str:
    """Send an email from the active (or specified) Gmail account."""
    import email.mime.text
    import email.mime.multipart
    import base64

    if account:
        gmail_switch_account(account)

    svc, err = _get_gmail()
    if err:
        return err

    msg = email.mime.multipart.MIMEMultipart()
    msg["to"]      = to
    msg["subject"] = subject
    if cc:
        msg["cc"] = cc
    msg.attach(email.mime.text.MIMEText(body, "plain"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        sent = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent. Message ID: {sent['id']}  |  To: {to}  |  Subject: {subject}"
    except Exception as e:
        return f"Error sending email: {e}"


# ── Google Calendar ────────────────────────────────────────────────────────────

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
            except Exception as e:
                return None, f"Calendar token refresh failed: {e}\nDelete {_CALENDAR_TOKEN} to re-auth."
        else:
            if not Path(creds_path).exists():
                return None, (
                    f"Google Calendar credentials not found at: {creds_path}\n\n"
                    "One-time setup:\n"
                    "  1. console.cloud.google.com → APIs & Services → Enable Google Calendar API\n"
                    "  2. Create OAuth 2.0 Client ID (Desktop app) → download JSON\n"
                    "  3. Save as ~/google_calendar_credentials.json\n"
                    "     OR set GOOGLE_CALENDAR_CREDENTIALS_PATH in .env"
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, _CALENDAR_SCOPES)
            creds = flow.run_local_server(port=0)
        Path(_CALENDAR_TOKEN).write_text(creds.to_json())

    try:
        return build("calendar", "v3", credentials=creds), None
    except Exception as e:
        return None, f"Calendar service error: {e}"


def calendar_events(days: int = 1, max_results: int = 20, calendar_id: str = "primary") -> str:
    """Fetch upcoming calendar events."""
    from datetime import datetime, timezone, timedelta

    svc, err = _get_calendar()
    if err:
        return err

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)

    try:
        result = svc.events().list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception as e:
        return f"Error fetching calendar events: {e}"

    events = result.get("items", [])
    if not events:
        label = "today" if days == 1 else f"the next {days} days"
        return f"No events found for {label}."

    lines = [f"Calendar events — next {days} day(s):"]
    for ev in events:
        start = ev.get("start", {})
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

        summary  = ev.get("summary", "(no title)")
        location = ev.get("location", "")
        loc_str  = f"  @ {location}" if location else ""
        lines.append(f"  {time_label}  —  {summary}{loc_str}")

    return "\n".join(lines)
