"""Guppy launch CLI — replaces verbose env-setup bat boilerplate.

Usage:
    python src/guppy/cli/launch.py <surface> [--profile PROFILE] [--no-hub] [--start DESTINATION]

Surfaces:
    guppy        — standard Guppy launcher   (profile: standard)
    launcher     — unified launcher + hub    (profile: standard)
    guppyprime   — full fleet launcher       (profile: power)
    hub          — Omnissiah hub only
    api          — API server (guppy_api.py)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.text import Text

_console = Console(highlight=False)

# Three parents up from src/guppy/cli/ → project root
ROOT = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def _get_win_user_env(name: str) -> str:
    """Read a user-scope environment variable from the Windows registry."""
    try:
        import winreg  # noqa: PLC0415 (lazy import, Windows-only)
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
        val, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return val or ""
    except (FileNotFoundError, OSError, ImportError):
        return ""


def _load_dotenv(root: Path) -> None:
    """Load environment variables from .env and .env.local files.

    .env.local (if present) overrides .env values.
    Variables already in os.environ are not overwritten.
    """
    for env_file_name in (".env", ".env.local"):
        env_file = root / env_file_name
        if not env_file.exists():
            continue
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            # .env.local values override .env values, but don't override os.environ
            if key:
                if env_file_name == ".env.local" or key not in os.environ:
                    os.environ[key] = val.strip()


def setup_env(root: Path, profile: str = "standard") -> None:
    """Populate os.environ with credentials, .env values, and defaults."""
    # Windows user-scope secrets (not visible in system env by default)
    for var in ("ANTHROPIC_API_KEY", "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"):
        if not os.environ.get(var):
            val = _get_win_user_env(var)
            if val:
                os.environ[var] = val

    # .env file (does not overwrite already-set vars)
    _load_dotenv(root)

    # Haiku boost tracks whether a cloud API key is present
    if os.environ.get("ANTHROPIC_API_KEY"):
        os.environ.setdefault("GUPPY_HAIKU_BOOST", "1")
    else:
        os.environ.setdefault("GUPPY_HAIKU_BOOST", "0")

    # Standard defaults
    os.environ.setdefault("GUPPY_ROUTER_MODE", "auto")
    os.environ.setdefault("GUPPY_TOOL_BUDGET", "6")
    os.environ.setdefault("GUPPY_WHISPER_MODEL", "large-v3")
    os.environ.setdefault("GUPPY_SEMANTIC_CLASSIFIER", "1")
    os.environ.setdefault("OLLAMA_MODEL", "guppy")
    os.environ.setdefault("OLLAMA_FAST_MODEL", "guppy-fast")
    os.environ.setdefault("OLLAMA_TEACH_MODEL", "guppy-teach")
    os.environ.setdefault("OLLAMA_CODE_MODEL", "guppy-code")
    os.environ.setdefault("OLLAMA_VAULT_MODEL", "vault-scraper")
    os.environ.setdefault("WEATHER_UNITS", "imperial")
    os.environ.pop("GUPPY_DEFAULT_SURFACE", None)
    os.environ.pop("GUPPY_SHOW_ADVANCED_SURFACES", None)

    # Profile
    os.environ["GUPPY_RUNTIME_PROFILE"] = profile


def _resolve_python_executable(root: Path, *, prefer_windowed: bool = False) -> str:
    """Resolve the preferred virtualenv interpreter for this launch path."""
    scripts_dir = root / ".venv" / "Scripts"
    pythonw = scripts_dir / "pythonw.exe"
    python = scripts_dir / "python.exe"
    if prefer_windowed and pythonw.exists():
        return str(pythonw)
    if python.exists():
        return str(python)
    if pythonw.exists():
        return str(pythonw)
    return sys.executable


# ---------------------------------------------------------------------------
# Hub management
# ---------------------------------------------------------------------------

def _poll_hub_ready(root: Path, timeout: float = 10.0, interval: float = 0.4) -> None:
    """Poll the hub health endpoint until it responds or timeout elapses."""
    import urllib.request
    hub_health = "http://127.0.0.1:8080/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(hub_health, timeout=1) as r:
                if r.status == 200:
                    _console.print("[bold green][launch][/bold green] Hub is ready.")
                    return
        except Exception:
            pass
        time.sleep(interval)
    _console.print("[bold yellow][launch][/bold yellow] WARNING: Hub did not respond within timeout — continuing anyway")


def _check_port_available(port: int) -> bool:
    """Return True if the TCP port is not bound by any process."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def start_hub_background(root: Path) -> subprocess.Popen | None:
    """Start guppy_hub.py in the background without a console window."""
    exe = _resolve_python_executable(root, prefer_windowed=True)
    hub_script = root / "guppy_hub.py"
    if not hub_script.exists():
        _console.print("[bold yellow][launch][/bold yellow] WARNING: guppy_hub.py not found — skipping hub start")
        return None
    return subprocess.Popen(
        [exe, str(hub_script)],
        cwd=str(root),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


# ---------------------------------------------------------------------------
# Surface map
# ---------------------------------------------------------------------------

#: Maps surface name → (script, needs_hub, default_profile)
SURFACES: dict[str, tuple[str, bool, str]] = {
    "guppy":       ("guppy_launcher.py",  False, "standard"),
    "launcher":    ("guppy_launcher.py",  True,  "standard"),
    "guppyprime":  ("guppy_launcher.py",  True,  "power"),
    "hub":         ("guppy_hub.py",       False, "standard"),
    "api":         ("guppy_api.py",       False, "standard"),
    "fishbowl":    ("guppy_fishbowl.py",  False, "standard"),
    "tray":        ("__tray__",           False, "standard"),
}
START_DESTINATIONS = ["home", "tools", "appmgmt", "automation-test"]
GUI_SCRIPTS = {"guppy_launcher.py", "guppy_hub.py", "guppy_fishbowl.py"}


def _setup_api_env() -> None:
    """Set API-server-specific environment defaults."""
    os.environ.setdefault("GUPPY_API_OWNS_DAEMON", "0")
    os.environ.setdefault("GUPPY_API_RELOAD", "0")
    os.environ.setdefault("GUPPY_JWT_SECRET", "dev-secret-key-change-in-production")
    os.environ.setdefault("TURNSTILE_SECRET", "dev-turnstile-secret")
    # Default to local inference via Ollama (GPU-accelerated on Windows via HIP).
    # Switch backends with GUPPY_LOCAL_RUNTIME_BACKEND=lmstudio|vllm|lemonade|auto
    # Only falls back to cloud (Claude) if ANTHROPIC_API_KEY is explicitly set.
    os.environ.setdefault("GUPPY_DEFAULT_MODE", "local")
    os.environ.setdefault("GUPPY_LOCAL_RUNTIME_BACKEND", "ollama")
    if not os.environ.get("GUPPY_JWT_SECRET") or os.environ.get("GUPPY_JWT_SECRET") == "dev-secret-key-change-in-production":
        _console.print("[bold yellow][launch][/bold yellow] WARNING: GUPPY_JWT_SECRET is not set — using dev default")
    if not os.environ.get("TURNSTILE_SECRET") or os.environ.get("TURNSTILE_SECRET") == "dev-turnstile-secret":
        _console.print("[bold yellow][launch][/bold yellow] WARNING: TURNSTILE_SECRET is not set — Turnstile verification disabled")


def _launch_gui_surface(python: str, script: str) -> int:
    creationflags = 0
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    subprocess.Popen(
        [python, script],
        cwd=str(ROOT),
        creationflags=creationflags,
    )
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="launch",
        description="Launch a Guppy surface with environment fully configured.",
    )
    parser.add_argument(
        "surface",
        choices=list(SURFACES),
        help="Which surface to launch",
    )
    parser.add_argument(
        "--profile",
        default=None,
        metavar="PROFILE",
        help="Runtime profile: standard or power (default: surface-specific)",
    )
    parser.add_argument(
        "--no-hub",
        action="store_true",
        help="Skip automatic hub background start",
    )
    parser.add_argument(
        "--start",
        choices=START_DESTINATIONS,
        default=None,
        metavar="DESTINATION",
        help="Open the launcher on a specific destination",
    )
    args = parser.parse_args(argv)

    script, hub_by_default, default_profile = SURFACES[args.surface]
    profile = args.profile or default_profile

    setup_env(ROOT, profile=profile)
    if script == "guppy_launcher.py":
        if args.start:
            os.environ["GUPPY_START_DESTINATION"] = args.start
        else:
            os.environ.pop("GUPPY_START_DESTINATION", None)
    else:
        if args.start:
            _console.print(
                f"[bold yellow][launch][/bold yellow] WARNING: --start only applies to launcher surfaces; ignoring '{args.start}' for {args.surface}"
            )
        os.environ.pop("GUPPY_START_DESTINATION", None)

    should_start_hub = hub_by_default and not args.no_hub and script != "guppy_launcher.py"
    if hub_by_default and not args.no_hub and script == "guppy_launcher.py":
        _console.print("[bold green][launch][/bold green] Launcher surface manages hub bootstrap internally; skipping pre-launch hub spawn")

    if should_start_hub:
        _console.print("[bold green][launch][/bold green] Starting hub in background...")
        start_hub_background(ROOT)
        _poll_hub_ready(ROOT)

    if args.surface == "tray":
        setup_env(ROOT, profile=profile)
        from src.guppy.apps.tray_app import main as _tray_main
        return _tray_main() or 0

    if args.surface == "api":
        _setup_api_env()
        _api_port = int(os.environ.get("GUPPY_API_PORT", "8081"))
        if not _check_port_available(_api_port):
            _console.print(f"[bold red][launch][/bold red] ERROR: Port {_api_port} is already in use. Stop the existing process or change GUPPY_API_PORT.")
            return 1

    python = _resolve_python_executable(
        ROOT,
        prefer_windowed=script in {"guppy_launcher.py", "guppy_hub.py", "guppy_fishbowl.py"},
    )
    _console.print(f"[bold green][launch][/bold green] Starting [cyan]{script}[/cyan] (profile=[italic]{profile}[/italic])...")
    if script in GUI_SCRIPTS:
        return _launch_gui_surface(python, script)
    result = subprocess.run([python, script], cwd=str(ROOT))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
