"""
guppy_agent.py — Terminal interface for Guppy
==============================================
Handles terminal I/O, Claude API turns, llamacpp local turns,
voice mode, and the Open WebUI browser launcher.
All shared tool logic lives in guppy_core.py.
"""

import os, sys, json, subprocess, time, threading, webbrowser
import urllib.request
from pathlib import Path

try:
    import anthropic
    ANT = True
except ImportError:
    ANT = False

from guppy_core import SYSTEM, TOOLS, run_tool, is_online, get_startup_system

CLAUDE_MODEL = (os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6")
CLAUDE_BACKUP_MODEL = os.environ.get("ANTHROPIC_BACKUP_MODEL", "claude-haiku-4-5-20251001").strip()

try:
    from src.guppy.memory.memory import save_message as _save_msg
    from datetime import datetime as _dt
    SESSION_ID = _dt.now().strftime("%Y%m%d_%H%M%S")
    _SAVE = True
except ImportError:
    _SAVE = False



# -- History sanitiser -----------------------------------------------------------------------

def sanitise_history(msgs: list) -> list:
    """Strip orphaned tool_result blocks (no matching tool_use) to prevent
    Claude API 400: unexpected tool_use_id in tool_result blocks."""
    valid_ids: set = set()
    clean = []
    for msg in msgs:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "assistant":
            if isinstance(content, list):
                for block in content:
                    bid   = getattr(block, "id", None) or (block.get("id") if isinstance(block, dict) else None)
                    btype = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
                    if btype == "tool_use" and bid:
                        valid_ids.add(bid)
            clean.append(msg)
        elif role == "user":
            if isinstance(content, list):
                filtered = [
                    b for b in content
                    if not (isinstance(b, dict) and b.get("type") == "tool_result"
                            and b.get("tool_use_id") not in valid_ids)
                ]
                if not filtered:
                    continue
                msg = dict(msg); msg["content"] = filtered
            clean.append(msg)
        else:
            clean.append(msg)
    return clean

# ── Claude turn (terminal) ─────────────────────────────────────────────────────

def claude_turn(client, msgs, user, system: str):
    if _SAVE: _save_msg(SESSION_ID, "user", user)
    msgs.append({"role": "user", "content": user})
    active_model = CLAUDE_MODEL
    backup_model = CLAUDE_BACKUP_MODEL
    while True:
        msgs = sanitise_history(msgs)
        model_chain = [active_model]
        if backup_model and backup_model != active_model:
            model_chain.append(backup_model)

        r = None
        last_err = None
        for model_name in model_chain:
            try:
                r = client.messages.create(
                    model=model_name,
                    max_tokens=8096,
                    system=system,
                    tools=TOOLS,
                    messages=msgs,
                )
                if model_name != active_model:
                    print(f"\nGuppy: Primary Claude model unavailable. Switched to backup ({model_name}).")
                    active_model = model_name
                break
            except Exception as e:
                last_err = e

        if r is None:
            raise RuntimeError(f"Claude request failed on all configured models: {last_err}")

        msgs.append({"role": "assistant", "content": r.content})
        for b in r.content:
            if b.type == "text" and b.text.strip():
                print(f"\nGuppy: {b.text}")
                if _SAVE: _save_msg(SESSION_ID, "assistant", b.text)
        tus = [b for b in r.content if b.type == "tool_use"]
        if not tus or r.stop_reason == "end_turn":
            break
        results = []
        for tu in tus:
            preview = str(list(tu.input.values())[0])[:60] if tu.input else ""
            print(f"\n  ⚙️  [{tu.name}] {preview}")
            res = run_tool(tu.name, tu.input)
            # Screenshots return a dict with base64 image data for Claude vision
            if isinstance(res, dict) and res.get("_screenshot"):
                print(f"     ↳ 📸 Captured: {res['path']} ({res['size']})")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": [
                        {"type": "text", "text": f"Screenshot saved to {res['path']} ({res['size']}). Image:"},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": res["image_base64"]}},
                    ],
                })
            else:
                res_str = str(res)
                print(f"     ↳ {res_str[:120]}{'...' if len(res_str) > 120 else ''}")
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": res_str})
        msgs.append({"role": "user", "content": results})
    return msgs


# ── llamacpp turn (terminal) ──────────────────────────────────────────────────

def llamacpp_turn(msgs, user, system: str, port: int = 8087, model: str = "hermes-3-8b-lorablated"):
    """Send one turn to a llamacpp server via OpenAI-compat /v1/chat/completions."""
    if _SAVE: _save_msg(SESSION_ID, "user", user)
    msgs.append({"role": "user", "content": user})
    all_msgs = [{"role": "system", "content": system}] + msgs

    payload = json.dumps({
        "model": model,
        "messages": all_msgs,
        "stream": False,
        "temperature": 1.0,
    }).encode()
    req = urllib.request.Request(
        f"http://localhost:{port}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"\n❌ llamacpp error (port {port}): {e}")
        return msgs

    reply_text = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
    if reply_text:
        print(f"\nGuppy: {reply_text}")
        if _SAVE: _save_msg(SESSION_ID, "assistant", reply_text)
    msgs.append({"role": "assistant", "content": reply_text})
    return msgs


# ── Input helpers ──────────────────────────────────────────────────────────────

def get_multiline_input():
    """Collect multiline input until a closing \"\"\" marker on its own line."""
    print('📝 Multiline mode. Type your message and end with \"\"\" on a new line.')
    lines = []
    while True:
        try:
            line = input("... ")
            if line.strip() == '"""':
                break
            lines.append(line)
        except (EOFError, KeyboardInterrupt):
            print("\n❌ Multiline input cancelled.")
            return None
    content = "\n".join(lines)
    if not content.strip():
        print("❌ Empty multiline input ignored.")
        return None
    print(f"✅ Collected {len(lines)} lines ({len(content)} characters)")
    return content


# ── Open WebUI browser launcher ────────────────────────────────────────────────

def launch_browser():
    print("\n  📦 Checking Open WebUI...")
    r = subprocess.run(["python", "-m", "pip", "show", "open-webui"], capture_output=True, text=True)
    if r.returncode != 0:
        print("  Installing Open WebUI (one moment)...")
        subprocess.run(["python", "-m", "pip", "install", "open-webui"])
    env = os.environ.copy()
    data_dir = Path.home() / "Guppy" / "webui_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    env["DATA_DIR"] = str(data_dir)

    def serve():
        subprocess.run(
            ["python", "-m", "open_webui", "serve", "--port", "8080"],
            env=env, stderr=subprocess.DEVNULL,
        )
    threading.Thread(target=serve, daemon=True).start()
    print("  ⏳ Starting server", end="", flush=True)
    for _ in range(20):
        time.sleep(2)
        print(".", end="", flush=True)
        try:
            urllib.request.urlopen("http://localhost:8080", timeout=1)
            break
        except Exception:
            pass
    print("\n\n  ✅ Open WebUI ready at http://localhost:8080")
    print("  Select 'guppy' from the model dropdown\n")
    webbrowser.open("http://localhost:8080")


# ── Terminal REPL ──────────────────────────────────────────────────────────────

def terminal_mode():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    net = is_online()
    client = None
    mode = "local"
    if key and net and ANT:
        try:
            client = anthropic.Anthropic(api_key=key)
            client.messages.create(
                model=CLAUDE_BACKUP_MODEL, max_tokens=10,
                messages=[{"role": "user", "content": "hi"}],
            )
            mode = "claude"
        except Exception:
            pass
    if mode == "local":
        print("🔧 Local mode (llamacpp) — use /web for browser interface")
    else:
        print("☁️  Claude mode — full tool access with vision")
    system = get_startup_system()  # load memory briefing once for this session
    msgs = []
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input == '"""':
                user_input = get_multiline_input()
                if user_input is None:
                    continue
            if user_input == "/exit":
                break
            elif user_input == "/clear":
                msgs = []
                print("🧹 Chat cleared")
            elif user_input == "/web":
                launch_browser()
            elif user_input == "/mode":
                print(f"Current: {mode} mode")
            else:
                if mode == "claude":
                    msgs = claude_turn(client, msgs, user_input, system)
                else:
                    msgs = llamacpp_turn(msgs, user_input, system)
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye, Master Ryan!")
            break


# ── Voice mode ─────────────────────────────────────────────────────────────────

def voice_mode():
    """Interactive voice REPL — migrated to async Stack C facade (Phase 6.0)."""
    print("voice_mode() is deprecated. Use the web UI voice interface or call")
    print("  asyncio.run(guppy.voice.speak(text)) / asyncio.run(guppy.voice.transcribe(audio))")
    print("directly from Python.")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("GUPPY — Digital Butler (Terminal)")
    print("Commands: /exit /clear /web /mode")
    print('Type \"\"\" on a line by itself to enter multiline mode')
    print("-" * 50)
    if len(sys.argv) > 1 and sys.argv[1] == "voice":
        voice_mode()
    else:
        terminal_mode()
