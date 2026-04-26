"""Guppy terminal — command-line chat interface to the LLM stack.

Connects to the main API (port 8081), authenticates, and provides a
streaming REPL. Works as a fallback entry point when no GUI is available.

Commands:
  /mode <auto|local|cloud|fast|code|complex>  — change routing mode
  /status                                      — show API + model status
  /clear                                       — clear history
  /help                                        — show commands
  /quit  (or Ctrl-C / Ctrl-D)                 — exit
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]
API_URL = "http://127.0.0.1:8081"

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.text import Text
    from rich.live import Live
    from rich.spinner import Spinner
    _RICH = True
except ImportError:
    _RICH = False

import httpx


# ── helpers ───────────────────────────────────────────────────────────────────

def _api_alive() -> bool:
    try:
        with urllib.request.urlopen(f"{API_URL}/", timeout=2) as r:
            return r.status < 500
    except Exception:
        return False


def _authenticate(console: "Console") -> Optional[str]:
    try:
        resp = httpx.post(
            f"{API_URL}/auth/local",
            json={"client_id": "guppy-terminal"},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("access_token") or data.get("token")
    except Exception as exc:
        if _RICH:
            console.print(f"[red]Auth failed:[/red] {exc}")
        else:
            print(f"Auth failed: {exc}")
        return None


def _stream_response(
    message: str,
    history: list[dict],
    mode: str,
    token: str,
    console: "Console",
) -> str:
    """Stream a response from the API, printing tokens as they arrive.
    Returns the full response text."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "message": message,
        "history": history,
        "mode": mode,
        "session_id": "terminal-session",
    }

    full_text = ""

    if _RICH:
        console.print()
        console.rule("[dim cyan]Guppy[/dim cyan]", style="dim")

    try:
        with httpx.stream(
            "POST",
            f"{API_URL}/api/chat/stream",
            headers=headers,
            json=payload,
            timeout=90,
        ) as resp:
            resp.raise_for_status()

            if _RICH:
                # Stream tokens directly to terminal
                with console.capture() as _:
                    pass
                sys.stdout.write("\n")
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload_str = line[6:].strip()
                    if payload_str == "[DONE]":
                        break
                    try:
                        obj = json.loads(payload_str)
                        tok = obj.get("token") or obj.get("content") or ""
                        full_text += tok
                        sys.stdout.write(tok)
                        sys.stdout.flush()
                    except json.JSONDecodeError:
                        pass
                sys.stdout.write("\n")
            else:
                for line in resp.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload_str = line[6:].strip()
                    if payload_str == "[DONE]":
                        break
                    try:
                        obj = json.loads(payload_str)
                        tok = obj.get("token") or obj.get("content") or ""
                        full_text += tok
                        sys.stdout.write(tok)
                        sys.stdout.flush()
                    except json.JSONDecodeError:
                        pass
                print()

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            if _RICH:
                console.print("\n[red]Session expired — re-authenticate with /auth[/red]")
            else:
                print("\nSession expired.")
        else:
            if _RICH:
                console.print(f"\n[red]HTTP {exc.response.status_code}[/red]")
            else:
                print(f"\nHTTP error: {exc.response.status_code}")
    except KeyboardInterrupt:
        if _RICH:
            console.print("\n[dim]   (stopped)[/dim]")
        else:
            print("\n(stopped)")
    except Exception as exc:
        if _RICH:
            console.print(f"\n[red]Error:[/red] {exc}")
        else:
            print(f"\nError: {exc}")

    if _RICH:
        console.rule(style="dim")
        console.print()

    return full_text


def _show_status(console: "Console", token: str, mode: str) -> None:
    try:
        resp = httpx.get(
            f"{API_URL}/status",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        data = resp.json()
        if _RICH:
            lines = [
                f"[bold]API[/bold]        {API_URL}",
                f"[bold]Status[/bold]     {data.get('status', '?')}",
                f"[bold]Mode[/bold]       {mode}",
                f"[bold]Backend[/bold]    {data.get('local_backend', {}).get('backend', '?')}",
                f"[bold]Model[/bold]      {data.get('local_backend', {}).get('model', '?')}",
            ]
            console.print(Panel("\n".join(lines), title="Guppy Status", border_style="cyan", expand=False))
        else:
            print(f"Status: {data.get('status', '?')} | Mode: {mode}")
    except Exception as exc:
        if _RICH:
            console.print(f"[red]Status check failed:[/red] {exc}")
        else:
            print(f"Status check failed: {exc}")


def _print_help(console: "Console") -> None:
    lines = [
        ("/mode <mode>", "Switch routing: auto local cloud fast code complex"),
        ("/status",      "Show API and model status"),
        ("/clear",       "Clear conversation history"),
        ("/help",        "Show this help"),
        ("/quit",        "Exit  (also Ctrl-C or Ctrl-D)"),
    ]
    if _RICH:
        rows = "\n".join(f"  [cyan]{cmd:16}[/cyan] {desc}" for cmd, desc in lines)
        console.print(Panel(rows, title="Commands", border_style="dim", expand=False))
    else:
        for cmd, desc in lines:
            print(f"  {cmd:20} {desc}")


def _banner(console: "Console") -> None:
    if _RICH:
        console.print(Panel(
            "[bold magenta]Guppy[/bold magenta] [dim]terminal interface[/dim]\n"
            "[dim]Type a message to chat · /help for commands[/dim]",
            border_style="magenta",
            expand=False,
        ))
    else:
        print("=" * 50)
        print("  Guppy Terminal  — /help for commands")
        print("=" * 50)


# ── main REPL ─────────────────────────────────────────────────────────────────

def main() -> None:
    console = Console() if _RICH else None

    # Check API
    if _RICH:
        with console.status("[cyan]Connecting to Guppy API…[/cyan]"):
            alive = _api_alive()
    else:
        print("Connecting to Guppy API…")
        alive = _api_alive()

    if not alive:
        msg = (
            f"Guppy API is not running at {API_URL}.\n"
            "Start it with:  python guppy_api.py\n"
            "Or via launcher:  python launch_platform.py"
        )
        if _RICH:
            console.print(Panel(msg, title="[red]Not Connected[/red]", border_style="red"))
        else:
            print(f"ERROR: {msg}")
        sys.exit(1)

    # Authenticate
    if _RICH:
        with console.status("[cyan]Authenticating…[/cyan]"):
            token = _authenticate(console)
    else:
        print("Authenticating…")
        token = _authenticate(console)

    if not token:
        sys.exit(1)

    _banner(console)

    VALID_MODES = {"auto", "local", "cloud", "fast", "code", "complex"}
    mode = "auto"
    history: list[dict] = []

    while True:
        try:
            if _RICH:
                prompt_str = f"[bold cyan]You[/bold cyan] [dim]({mode})[/dim]"
                console.print(prompt_str, end=" ")
                text = input()
            else:
                text = input(f"You ({mode}): ")
        except (EOFError, KeyboardInterrupt):
            if _RICH:
                console.print("\n[dim]Goodbye.[/dim]")
            else:
                print("\nGoodbye.")
            break

        text = text.strip()
        if not text:
            continue

        # ── commands ──────────────────────────────────────────────────────────
        if text.startswith("/"):
            parts = text.split(None, 1)
            cmd = parts[0].lower()

            if cmd in ("/quit", "/exit", "/q"):
                if _RICH:
                    console.print("[dim]Goodbye.[/dim]")
                else:
                    print("Goodbye.")
                break

            elif cmd == "/clear":
                history.clear()
                if _RICH:
                    console.print("[dim]History cleared.[/dim]")
                else:
                    print("History cleared.")

            elif cmd == "/help":
                _print_help(console)

            elif cmd == "/status":
                _show_status(console, token, mode)

            elif cmd == "/mode":
                if len(parts) < 2 or parts[1].strip() not in VALID_MODES:
                    valid = " | ".join(sorted(VALID_MODES))
                    if _RICH:
                        console.print(f"[yellow]Usage:[/yellow] /mode [{valid}]")
                    else:
                        print(f"Usage: /mode [{valid}]")
                else:
                    mode = parts[1].strip()
                    if _RICH:
                        console.print(f"[green]Mode →[/green] {mode}")
                    else:
                        print(f"Mode → {mode}")

            elif cmd == "/auth":
                token = _authenticate(console)
                if token:
                    if _RICH:
                        console.print("[green]Re-authenticated.[/green]")
                    else:
                        print("Re-authenticated.")

            else:
                if _RICH:
                    console.print(f"[yellow]Unknown command:[/yellow] {cmd}  (try /help)")
                else:
                    print(f"Unknown command: {cmd}  (try /help)")
            continue

        # ── chat ──────────────────────────────────────────────────────────────
        history.append({"role": "user", "content": text})
        response = _stream_response(text, history[:-1], mode, token, console)
        if response:
            history.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
