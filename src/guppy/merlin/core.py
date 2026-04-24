"""
merlin_core.py — Merlin's spell definitions, research, and media tools
=======================================================================
Defines the spell-themed tool palette, research capability, torrent
management via uTorrent WebAPI, and framework stubs for Plex and VPN.

Spell names map to guppy_core tool names via SPELL_MAP.
"""

from guppy_core import run_tool as _run_tool, _mem, _MEM
from src.guppy.merlin.catalog import MERLIN_SYSTEM, MERLIN_TOOLS, SPELL_MAP
from src.guppy.merlin import specialist_support as _specialist_support

merlin_clear_cache = _specialist_support.merlin_clear_cache
try:
    from src.guppy.memory.semantic import build_semantic_prompt_context as _build_semantic_prompt_context
except Exception:
    _build_semantic_prompt_context = None

# Retained specialist surface note:
# Merlin is a bounded compatibility runtime, not a product surface.
# New heavy helper logic should land in specialist_support.py, leaving this file
# to own dispatch rules, startup prompt assembly, and the imported spell catalog.
# Keep in sync with Modelfile_Merlin

def _set_clipboard(text: str) -> str:
    """Write text to the Windows clipboard — base64-encoded to avoid quoting issues."""
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
            ["powershell", "-NoProfile", "-Command",
             f"[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{b64}')) | Set-Clipboard"],
            capture_output=True, timeout=5,
            **extra,
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
    return _specialist_support.run_spells_parallel(
        spells_and_args,
        spell_runner=run_spell,
    )


# ── Spell runner ───────────────────────────────────────────────────────────────

def run_spell(name: str, inp: dict):
    """Translate a spell name to its implementation and execute it."""
    support_result = _specialist_support.run_spell(name, inp, run_tool=_run_tool)
    if support_result is not None:
        return support_result
    core_name = SPELL_MAP.get(name, name)
    return _run_tool(core_name, inp)


# ── Startup system with memory ─────────────────────────────────────────────────

def get_merlin_startup_system(query_context: str = None) -> str:
    """Return Merlin's system prompt enriched with the memory briefing."""
    try:
        from guppy_core import _needs_memory_context
    except Exception:
        def _needs_memory_context(_query_context):
            return False

    return _specialist_support.get_merlin_startup_system(
        memory_enabled=bool(_MEM),
        base_system=MERLIN_SYSTEM,
        query_context=query_context,
        memory_module=None,
        memory_store=_mem,
        needs_memory_context=_needs_memory_context,
        build_semantic_prompt_context=_build_semantic_prompt_context,
    )




