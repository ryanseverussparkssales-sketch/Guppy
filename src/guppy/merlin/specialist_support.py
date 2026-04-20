"""Support helpers for the retained Merlin specialist runtime surface.

This module holds the mixed research, media, clipboard, and code-analysis
helpers so ``core.py`` can stay focused on spell catalog wiring and dispatch.
"""

from __future__ import annotations

import base64
import hashlib
import os
import subprocess
import urllib.parse
from pathlib import Path

_ANALYSIS_CACHE: dict[str, dict[str, str]] = {}


def _hash_file(filepath: str) -> str:
    """MD5 hash of file contents for cache keying."""
    try:
        content = Path(filepath).read_bytes()
        return hashlib.md5(content).hexdigest()
    except Exception:
        return ""


def _get_analysis_cached(filepath: str, force_fresh: bool = False) -> dict[str, str]:
    """Read file with caching. Returns {hash, path, content}."""
    if not force_fresh:
        fhash = _hash_file(filepath)
        if fhash in _ANALYSIS_CACHE:
            return _ANALYSIS_CACHE[fhash]

    try:
        full_path = Path(filepath).resolve()
        content = full_path.read_text(encoding="utf-8")
        fhash = hashlib.md5(content.encode()).hexdigest()
        result = {"hash": fhash, "path": str(full_path), "content": content}
        _ANALYSIS_CACHE[fhash] = result
        return result
    except Exception as exc:
        return {"hash": "", "path": filepath, "content": f"Error reading file: {exc}"}


def merlin_clear_cache() -> str:
    """Clear the analysis cache when starting fresh reviews."""
    _ANALYSIS_CACHE.clear()
    return "Analysis cache cleared."


def _get_clipboard() -> str:
    """Read the Windows clipboard via PowerShell."""
    try:
        extra: dict[str, object] = {}
        if os.name == "nt":
            extra["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
            startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
            extra["startupinfo"] = startupinfo
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            timeout=5,
            **extra,
        )
        return result.stdout.strip() or "(clipboard is empty)"
    except Exception as exc:
        return f"Failed to read clipboard: {exc}"


def _set_clipboard(text: str) -> str:
    """Write text to the Windows clipboard."""
    try:
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        extra: dict[str, object] = {}
        if os.name == "nt":
            extra["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
            startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
            extra["startupinfo"] = startupinfo
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{b64}')) | Set-Clipboard",
            ],
            capture_output=True,
            timeout=5,
            **extra,
        )
        return f"Clipboard filled ({len(text)} chars)."
    except Exception as exc:
        return f"Failed to write clipboard: {exc}"


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
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            lines = [line.strip() for line in soup.get_text(separator="\n").splitlines() if line.strip()]
            text = "\n".join(lines)
            suffix = f"\n\n[Truncated - {len(text)} chars total]" if len(text) > 8000 else ""
            return text[:8000] + suffix
        except Exception as exc:
            return f"Failed to fetch {url}: {exc}"

    if query:
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            response = requests.get(search_url, timeout=15, headers=headers)
            soup = BeautifulSoup(response.text, "html.parser")
            results: list[str] = []
            for result in soup.select(".result")[:6]:
                title = result.select_one(".result__title")
                snippet = result.select_one(".result__snippet")
                link = result.select_one(".result__url")
                if title and snippet:
                    results.append(
                        f"**{title.get_text(strip=True)}**\n"
                        f"{snippet.get_text(strip=True)}"
                        + (f"\n{link.get_text(strip=True)}" if link else "")
                    )
            return "\n\n---\n\n".join(results) if results else "No results found."
        except Exception as exc:
            return f"Search failed: {exc}"

    return "Provide either 'query' or 'url'."


def _utorrent(action: str, params: dict | None = None) -> dict:
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return {"error": "pip install requests beautifulsoup4"}

    host = os.environ.get("UTORRENT_HOST", "localhost")
    port = os.environ.get("UTORRENT_PORT", "8080")
    user = os.environ.get("UTORRENT_USER", "admin")
    password = os.environ.get("UTORRENT_PASS", "")
    base = f"http://{host}:{port}/gui"
    auth = (user, password) if user else None

    try:
        token_response = requests.get(f"{base}/token.html", auth=auth, timeout=5)
        token = BeautifulSoup(token_response.text, "html.parser").find("div", {"id": "token"}).text.strip()
    except Exception as exc:
        return {"error": f"uTorrent unreachable at {base} - is WebUI enabled? ({exc})"}

    payload = {"token": token, "action": action}
    if params:
        payload.update(params)

    try:
        response = requests.get(f"{base}/", auth=auth, params=payload, timeout=15)
        return response.json()
    except Exception as exc:
        return {"error": str(exc)}


def _seek_torrent(query: str, category: str = "all") -> str:
    """Search YTS for movies, or use a general scrape for other categories."""
    try:
        import requests
    except ImportError:
        return "pip install requests"

    headers = {"User-Agent": "Mozilla/5.0"}

    if category in ("movies", "all"):
        try:
            url = f"https://yts.mx/api/v2/list_movies.json?query_term={urllib.parse.quote(query)}&limit=5"
            response = requests.get(url, timeout=10, headers=headers)
            data = response.json()
            if data.get("status") == "ok" and data["data"].get("movies"):
                lines = [f"=== YTS Movie Results for '{query}' ==="]
                for movie in data["data"]["movies"]:
                    torrents = movie.get("torrents", [])
                    best = max(torrents, key=lambda item: item.get("seeds", 0)) if torrents else None
                    lines.append(
                        f"\n{movie['title']} ({movie.get('year', '?')}) - {movie.get('rating', '?')}/10\n"
                        f"  Genre: {', '.join(movie.get('genres', []))}\n"
                        + (
                            f"  Best torrent: {best['quality']} | {best['size']} | "
                            f"Seeds: {best['seeds']} | Magnet: {best['url']}"
                            if best
                            else "  No torrents found"
                        )
                    )
                return "\n".join(lines)
        except Exception:
            pass

    try:
        import requests
        from bs4 import BeautifulSoup

        search_url = f"https://1337x.to/search/{urllib.parse.quote(query)}/1/"
        response = requests.get(search_url, timeout=10, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("tbody tr")[:8]
        if not rows:
            return f"No results found for '{query}'."
        lines = [f"=== 1337x Results for '{query}' ==="]
        for row in rows:
            name_el = row.select_one(".name a:nth-of-type(2)")
            seeds_el = row.select_one(".seeds")
            size_el = row.select_one(".size")
            if name_el:
                lines.append(
                    f"\n{name_el.text.strip()}"
                    + (f" | Seeds: {seeds_el.text.strip()}" if seeds_el else "")
                    + (f" | {size_el.text.strip()}" if size_el else "")
                )
        return "\n".join(lines)
    except Exception as exc:
        return f"Search failed: {exc}"


def _view_torrents() -> str:
    data = _utorrent("list", {"list": "1"})
    if "error" in data:
        return data["error"]
    torrents = data.get("torrents", [])
    if not torrents:
        return "No active torrents."
    status_map = {
        0: "Stopped",
        1: "Check wait",
        2: "Checking",
        3: "DL wait",
        4: "Downloading",
        5: "Finished",
        6: "Seeding",
    }
    lines: list[str] = []
    for torrent in torrents:
        try:
            name = torrent[2]
            progress = torrent[4] / 10
            status = status_map.get(torrent[1], str(torrent[1]))
            dl_speed = f"{torrent[9] / 1024:.1f} KB/s" if torrent[9] else "-"
            lines.append(f"{name[:50]}\n  {status} | {progress:.1f}% | DL: {dl_speed}")
        except (IndexError, TypeError):
            lines.append(str(torrent))
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


def _plex_status() -> str:
    plex_url = os.environ.get("PLEX_URL", "")
    plex_token = os.environ.get("PLEX_TOKEN", "")
    if not plex_url or not plex_token:
        return (
            "Plex not configured. Set environment variables:\n"
            "  PLEX_URL=http://localhost:32400\n"
            "  PLEX_TOKEN=your-token\n"
            "Find your token at: Plex Web -> Account -> XML URL (X-Plex-Token param)"
        )
    try:
        import requests

        response = requests.get(
            f"{plex_url}/status/sessions",
            headers={"X-Plex-Token": plex_token},
            timeout=5,
        )
        return f"Plex reachable at {plex_url}. Sessions endpoint: {response.status_code}"
    except Exception as exc:
        return f"Plex unreachable: {exc}"


def _vpn_status() -> str:
    client = os.environ.get("VPN_CLIENT", "")
    if not client:
        return (
            "VPN not configured. Set VPN_CLIENT environment variable.\n"
            "Supported options (coming soon): nordvpn, protonvpn, wireguard, windows"
        )
    return f"VPN client '{client}' configured but integration not yet implemented."


def _analyze_python(filepath: str, check_syntax: bool = True, extract_structure: bool = True) -> str:
    """Parse and analyze Python file for structural issues and metadata."""
    try:
        import ast

        path = Path(filepath).resolve()
        code = path.read_text(encoding="utf-8")
        result = f"File: {path.name}\n"

        if check_syntax:
            try:
                tree = ast.parse(code)
                result += "Syntax: valid\n"
            except SyntaxError as exc:
                return f"Syntax error at line {exc.lineno}: {exc.msg}"
        else:
            tree = ast.parse(code)

        if extract_structure:
            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            imports: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)

            if functions:
                result += f"\nFunctions ({len(functions)}): {', '.join(functions[:8])}"
                if len(functions) > 8:
                    result += f", +{len(functions) - 8} more"
            if classes:
                result += f"\nClasses ({len(classes)}): {', '.join(classes[:8])}"
                if len(classes) > 8:
                    result += f", +{len(classes) - 8} more"
            if imports:
                result += f"\nImports: {', '.join(list(dict.fromkeys(imports))[:10])}"
            result += f"\nLines: {len(code.splitlines())}"

        return result
    except Exception as exc:
        return f"Analysis failed: {exc}"


def _generate_patch(filepath: str, old_code: str, new_code: str, reason: str = "Code improvement") -> str:
    """Generate unified diff patch and save it to the Merlin patches directory."""
    import difflib

    try:
        old_lines = old_code.splitlines(keepends=True)
        new_lines = new_code.splitlines(keepends=True)
        diff_lines = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=filepath,
                tofile=filepath,
                lineterm="",
            )
        )

        if not diff_lines:
            return "No differences between old and new code."

        patch_content = "\n".join(diff_lines)
        patch_content += f"\n\n--- Reason: {reason}\n"

        patches_dir = Path(__file__).parent / "patches"
        patches_dir.mkdir(exist_ok=True)
        patch_count = len(list(patches_dir.glob("*.patch")))
        patch_file = patches_dir / f"patch_{patch_count:03d}_{Path(filepath).stem}.patch"
        patch_file.write_text(patch_content, encoding="utf-8")

        additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        return f"Patch generated: {patch_file.name}\n+{additions}/{deletions} lines changed"
    except Exception as exc:
        return f"Patch generation failed: {exc}"


__all__ = [
    "_analyze_python",
    "_banish_torrent",
    "_generate_patch",
    "_get_analysis_cached",
    "_get_clipboard",
    "_plex_status",
    "_research",
    "_seek_torrent",
    "_set_clipboard",
    "_summon_torrent",
    "_utorrent",
    "_view_torrents",
    "_vpn_status",
    "merlin_clear_cache",
]
