"""Spotify and YouTube helpers split out of media.py to keep file sizes healthy."""

from __future__ import annotations

import os
import subprocess
import urllib.parse
import webbrowser
from pathlib import Path

from utils.connector_manager import read_machine_secret


def _win_hidden_run_flags() -> dict[str, object]:
    if os.name != "nt":
        return {}
    flags: dict[str, object] = {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    flags["startupinfo"] = startupinfo
    return flags


def _get_spotify():
    """Return (spotipy.Spotify, None) or (None, setup_instructions_str)."""
    cid = read_machine_secret("SPOTIFY_CLIENT_ID")
    csecret = read_machine_secret("SPOTIFY_CLIENT_SECRET")
    if not cid or not csecret:
        return None, (
            "Spotify API not configured. Add to launch_guppy.bat / launch_council.bat:\n"
            "  set SPOTIFY_CLIENT_ID=your-client-id\n"
            "  set SPOTIFY_CLIENT_SECRET=your-client-secret\n"
            "Get free credentials at developer.spotify.com -> Create App."
        )
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=cid,
                client_secret=csecret,
                redirect_uri=read_machine_secret(
                    "SPOTIFY_REDIRECT_URI",
                    fallback="http://localhost:8888/callback",
                ),
                scope=(
                    "user-modify-playback-state "
                    "user-read-playback-state "
                    "user-read-currently-playing"
                ),
                cache_path=str(Path.home() / ".guppy_spotify_token"),
                open_browser=True,
            )
        )
        return sp, None
    except ImportError:
        return None, "spotipy not installed -> run: pip install spotipy"
    except Exception as exc:
        return None, f"Spotify auth error: {exc}"


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
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        timeout=5,
        **_win_hidden_run_flags(),
    )
    return f"Media key sent: {action}"


def spotify_play(query: str) -> str:
    """Search Spotify and play the top track, artist, or playlist result."""
    sp, err = _get_spotify()
    if err:
        webbrowser.open(f"spotify:search:{urllib.parse.quote(query)}")
        return f"Opened Spotify search for: {query}\n(API not configured -> {err})"
    try:
        results = sp.search(q=query, type="track,artist,playlist", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        if tracks:
            uri = tracks[0]["uri"]
            name = tracks[0]["name"]
            artist = tracks[0]["artists"][0]["name"]
            sp.start_playback(uris=[uri])
            return f"Now playing: {name} -> {artist}"
        artists = results.get("artists", {}).get("items", [])
        if artists:
            sp.start_playback(context_uri=artists[0]["uri"])
            return f"Playing artist: {artists[0]['name']}"
        playlists = results.get("playlists", {}).get("items", [])
        if playlists:
            sp.start_playback(context_uri=playlists[0]["uri"])
            return f"Playing playlist: {playlists[0]['name']}"
        return f"No Spotify results for: {query}"
    except Exception as exc:
        return f"Spotify play error: {exc}"


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
        item = playing["item"]
        name = item["name"]
        artist = ", ".join(artist["name"] for artist in item["artists"])
        album = item["album"]["name"]
        prog_ms = playing.get("progress_ms", 0)
        dur_ms = item["duration_ms"]
        progress = f"{prog_ms // 60000}:{(prog_ms // 1000) % 60:02d}"
        total = f"{dur_ms // 60000}:{(dur_ms // 1000) % 60:02d}"
        status = ">" if playing.get("is_playing") else "||"
        return f"{status} {name}\n  Artist: {artist}\n  Album: {album}\n  {progress} / {total}"
    except Exception as exc:
        return f"Could not get current track: {exc}"


def spotify_volume(level: int) -> str:
    sp, err = _get_spotify()
    if err:
        return f"Volume control requires Spotify API.\n{err}"
    level = max(0, min(100, level))
    try:
        sp.volume(level)
        return f"Spotify volume: {level}%"
    except Exception as exc:
        return f"Volume error: {exc}"


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
                title = entry.get("title", query)
                url = f"https://www.youtube.com/watch?v={vid_id}"
                webbrowser.open(url)
                return f"Opened: {title}\n{url}"
    except ImportError:
        pass
    except Exception:
        pass
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    webbrowser.open(url)
    return (
        f"Opened YouTube search for: {query}\n"
        "Tip: install yt-dlp for direct video lookup -> pip install yt-dlp"
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
            lines = [f"YouTube -> top results for '{query}':"]
            for index, item in enumerate(info["entries"][:5], 1):
                title = item.get("title", "Unknown")
                vid_id = item.get("id", "")
                dur = item.get("duration")
                dur_s = f"  [{dur // 60}:{dur % 60:02d}]" if dur else ""
                lines.append(f"{index}. {title}{dur_s}\n   https://youtube.com/watch?v={vid_id}")
            return "\n".join(lines)
    except ImportError:
        pass
    except Exception:
        pass
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(
            f"https://html.duckduckgo.com/html/?q=site:youtube.com+{urllib.parse.quote(query)}",
            headers=headers,
            timeout=10,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for result in soup.select(".result")[:5]:
            title = result.select_one(".result__title")
            url = result.select_one(".result__url")
            if title:
                results.append(title.get_text(strip=True) + ("\n   " + url.get_text(strip=True) if url else ""))
        return "\n\n".join(results) if results else "No results found."
    except Exception as exc:
        return f"Search failed: {exc}"
