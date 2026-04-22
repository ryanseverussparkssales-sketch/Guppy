"""utils/hub_operator.py — Intelligent hub orchestration brain
============================================================
Shared brain used by both guppy_hub.py (UI) and guppy_daemon.py (background).

Capabilities:
  - IPC: send commands to running agents via runtime/{id}.cmd files
  - Pattern logging: append events to runtime/hub_patterns.jsonl
  - Pattern analysis: periodic Haiku review (throttled 1/hour)
  - Agent repair: clear stale heartbeat/activity/cmd files
  - Health checks: Ollama, API server, Cloudflare, Anthropic key
  - Smart recommendations: rule-based, no API call

Integrates with:
  - Phase 8 (Proactive/Daemon Mode): ProactiveLoop in guppy_daemon.py
  - Phase 11 (Ambient Awareness): AmbientWatcher in guppy_daemon.py
  - Phase 14 (Self-Improvement): pattern log feeds Haiku review
  - guppy_hub.py OperatorCard: shows insight + NUDGE/REPAIR controls
"""

from __future__ import annotations

import json
import os
import sys
import time
import logging
import urllib.request
import subprocess
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Suppress console windows on Windows for all subprocess calls
_WIN_NO_WINDOW = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if sys.platform == "win32" else {}
)
_WIN_DETACHED = (
    {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW}
    if sys.platform == "win32" else {}
)

logger = logging.getLogger(__name__)

try:
    from utils.safe_io import write_json_atomic as _write_json_atomic
except ImportError:
    def _write_json_atomic(path, data):  # type: ignore[misc]
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")
        tmp.replace(path)

_RUNTIME = Path(__file__).parent.parent / "runtime"
_PATTERN_LOG = _RUNTIME / "hub_patterns.jsonl"
_ANALYSIS_CACHE = _RUNTIME / "hub_analysis_cache.json"
_THROTTLE_SECONDS = 3600  # 1 hour between Haiku analysis calls
_ROOT = Path(__file__).parent.parent

_SERVICE_ALLOWLIST = {
    "api",
    "cloudflared",
    "ollama",
}


class HubOperator:
    """
    Hub orchestration brain.

    Thread-safe for concurrent access from hub UI + daemon background threads.
    Uses file-based IPC so agents can run in separate processes.
    """

    def __init__(self):
        self._last_analysis_time: float = 0.0
        self._last_insight: str = ""
        _RUNTIME.mkdir(parents=True, exist_ok=True)
        self._load_analysis_cache()

    # ── Analysis Cache ──────────────────────────────────────────────────────────

    def _load_analysis_cache(self) -> None:
        try:
            if _ANALYSIS_CACHE.exists():
                data = json.loads(_ANALYSIS_CACHE.read_text(encoding="utf-8"))
                self._last_analysis_time = float(data.get("ts", 0.0))
                self._last_insight = str(data.get("insight", ""))
        except Exception:
            pass

    def _save_analysis_cache(self) -> None:
        try:
            _ANALYSIS_CACHE.write_text(
                json.dumps({"ts": self._last_analysis_time, "insight": self._last_insight}),
                encoding="utf-8",
            )
        except Exception as e:
            logger.debug(f"_save_analysis_cache: {e}")

    @property
    def last_insight(self) -> str:
        return self._last_insight or "No analysis yet."

    @property
    def analysis_age_str(self) -> str:
        if not self._last_analysis_time:
            return "never"
        age = time.time() - self._last_analysis_time
        if age < 120:
            return "just now"
        if age < 3600:
            return f"{int(age // 60)}m ago"
        return f"{int(age // 3600)}h ago"

    # ── Event Logging ───────────────────────────────────────────────────────────

    def record_event(
        self,
        agent: str,
        action: str,
        reason: str = "",
        outcome: str = "",
    ) -> None:
        """Append one event to hub_patterns.jsonl. Used by hub UI + daemon."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "action": action,
            "reason": reason,
            "outcome": outcome,
        }
        try:
            with open(_PATTERN_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning(f"record_event failed: {e}")

    # ── Pattern Analysis (Haiku, throttled) ─────────────────────────────────────

    def analyze_patterns(self, force: bool = False) -> str:
        """
        Run a Haiku analysis of recent hub events. Throttled to 1/hour.
        Returns bullet-point insight string.

        Called by: OperatorCard "ANALYZE" button (force=True),
                   Phase 14 self-improvement loop (scheduled, force=False).
        """
        now = time.time()
        if not force and (now - self._last_analysis_time) < _THROTTLE_SECONDS:
            return self._last_insight

        lines = self._read_recent_events(max_lines=200)
        if not lines:
            return "Not enough events to analyze yet."

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return "No API key — pattern analysis unavailable."

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=300,
                system=(
                    "You are an operations analyst reviewing agent event logs. "
                    "Identify patterns: frequent crashes, stalls, slow starts, "
                    "or unusual sequences. Reply with 3-5 bullet points only. Be terse."
                ),
                messages=[{"role": "user", "content": "\n".join(lines)}],
            )
            insight = resp.content[0].text.strip() if resp.content else "No insight returned."
        except Exception as e:
            logger.warning(f"analyze_patterns: Haiku call failed: {e}")
            return f"Analysis failed: {e}"

        self._last_analysis_time = now
        self._last_insight = insight
        self._save_analysis_cache()
        self.record_event("hub", "pattern_analysis", "periodic", "ok")
        return insight

    def _read_recent_events(self, max_lines: int = 200) -> list[str]:
        try:
            if not _PATTERN_LOG.exists():
                return []
            lines = _PATTERN_LOG.read_text(encoding="utf-8").strip().splitlines()
            return lines[-max_lines:]
        except Exception:
            return []

    # ── IPC: Send Commands to Running Agents ─────────────────────────────────────

    def send_command(
        self, agent_id: str, cmd: str, payload: dict[str, Any] | None = None
    ) -> bool:
        """
        Write runtime/{agent_id}.cmd for the agent to pick up on its next poll.
        Returns True if written successfully.

        Supported commands (agents must implement poll logic):
          nudge          — refresh/re-init orb and context
          clear_history  — clear conversation history
          reset_context  — reset system prompt cache
          report_status  — write diagnostics to runtime/{id}.status
        """
        cmd_path = _RUNTIME / f"{agent_id}.cmd"
        try:
            _write_json_atomic(cmd_path, {
                "cmd": cmd,
                "payload": payload or {},
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            self.record_event(agent_id, f"cmd_{cmd}", "hub_sent", "pending")
            return True
        except Exception as e:
            logger.warning(f"send_command({agent_id}, {cmd}): {e}")
            return False

    def nudge_agent(self, agent_id: str) -> bool:
        """Send a nudge command — ask agent to refresh/re-init."""
        return self.send_command(agent_id, "nudge")

    def clear_agent_history(self, agent_id: str) -> bool:
        """Ask agent to clear its conversation history."""
        return self.send_command(agent_id, "clear_history")

    def reset_agent_context(self, agent_id: str) -> bool:
        """Ask agent to reset its system prompt cache."""
        return self.send_command(agent_id, "reset_context")

    # ── Agent Repair ────────────────────────────────────────────────────────────

    def repair_agent(self, agent_id: str) -> list[str]:
        """
        Clear stale runtime files for an agent so it can restart cleanly.
        Returns list of file names removed.
        """
        removed = []
        for suffix in (".heartbeat", ".activity", ".cmd"):
            path = _RUNTIME / f"{agent_id}{suffix}"
            if path.exists():
                try:
                    path.unlink()
                    removed.append(path.name)
                except Exception as e:
                    logger.warning(f"repair_agent: could not remove {path.name}: {e}")
        if removed:
            self.record_event(
                agent_id, "repair", "stale_files", f"removed: {', '.join(removed)}"
            )
        return removed

    # ── Health Checks ───────────────────────────────────────────────────────────

    def check_ollama(self, timeout: float = 3.0) -> dict:
        """Check Ollama availability."""
        try:
            urllib.request.urlopen("http://localhost:11434/", timeout=timeout)
            return {"ok": True, "status": "running"}
        except Exception as e:
            return {"ok": False, "status": str(e)[:60]}

    def check_api_server(self, timeout: float = 3.0) -> dict:
        """Check Guppy API server health endpoint."""
        port = os.environ.get("GUPPY_API_PORT", "8081")
        try:
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=timeout)
            return {"ok": True, "status": "running"}
        except Exception as e:
            return {"ok": False, "status": str(e)[:60]}

    def check_anthropic(self) -> dict:
        """Check Anthropic API key presence (no network call, instant)."""
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return {"ok": False, "status": "no key"}
        if not api_key.startswith("sk-ant"):
            return {"ok": False, "status": "key format invalid"}
        return {"ok": True, "status": "key present"}

    def check_cloudflared(self) -> dict:
        """Check whether cloudflared tunnel process is running."""
        try:
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq cloudflared.exe", "/NH"],
                capture_output=True,
                text=True,
                timeout=3,
                **_WIN_NO_WINDOW,
            )
            if "cloudflared.exe" in out.stdout:
                return {"ok": True, "status": "running"}
            return {"ok": False, "status": "not running"}
        except Exception as e:
            return {"ok": False, "status": str(e)[:60]}

    def full_system_check(self) -> dict:
        """Run all health checks. Returns dict: service → {ok, status}."""
        return {
            "ollama": self.check_ollama(),
            "api": self.check_api_server(),
            "anthropic": self.check_anthropic(),
            "cloudflared": self.check_cloudflared(),
        }

    # ── Runtime Status Readers ────────────────────────────────────────────────

    def read_agent_status(self, agent_id: str) -> dict:
        """Read runtime/{agent_id}.status and return parsed JSON if present."""
        status_path = _RUNTIME / f"{agent_id}.status"
        if not status_path.exists():
            return {"ok": False, "status": "missing"}
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
            return {"ok": True, "status": "ok", "data": data}
        except Exception as e:
            return {"ok": False, "status": f"invalid:{str(e)[:40]}"}

    def get_agent_status_snapshot(self) -> dict:
        """Return quick status snapshot for guppy/merlin/council status files."""
        return {
            "guppy": self.read_agent_status("guppy"),
            "merlin": self.read_agent_status("merlin"),
            "council": self.read_agent_status("council"),
        }

    # ── Third-Party Lifecycle Controls (allowlist only) ───────────────────────

    def service_allowed(self, service: str) -> bool:
        return (service or "").lower() in _SERVICE_ALLOWLIST

    @staticmethod
    def _cloudflare_cert_paths() -> list[Path]:
        home = Path.home()
        return [
            home / ".cloudflared" / "cert.pem",
            home / ".cloudflare-warp" / "cert.pem",
            home / "cloudflare-warp" / "cert.pem",
        ]

    def _read_env_var(self, key: str) -> str:
        # Prefer process env, then fallback to .env parsing.
        val = os.environ.get(key, "").strip()
        if val:
            return val
        env_file = _ROOT / ".env"
        if not env_file.exists():
            return ""
        try:
            for raw in env_file.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == key:
                    return v.strip().strip('"').strip("'")
        except Exception:
            return ""
        return ""

    def _cloudflared_preflight(self) -> dict:
        cert_override = self._read_env_var("TUNNEL_ORIGIN_CERT")
        cert_ok = bool(cert_override and Path(cert_override).exists())
        if not cert_ok:
            cert_ok = any(p.exists() for p in self._cloudflare_cert_paths())

        tunnel_id = self._read_env_var("CLOUDFLARE_TUNNEL_ID")
        tunnel_ok = bool(tunnel_id and tunnel_id != "your-tunnel-uuid-here")

        if not cert_ok:
            return {
                "ok": False,
                "status": "cloudflared_missing_origin_cert",
                "hint": "Run: bin\\cloudflared.exe tunnel login",
            }
        if not tunnel_ok:
            return {
                "ok": False,
                "status": "cloudflared_missing_tunnel_id",
                "hint": "Run: bin\\cloudflared.exe tunnel create guppy; then set CLOUDFLARE_TUNNEL_ID in .env",
            }
        return {"ok": True, "status": "ok", "tunnel_id": tunnel_id}

    def _api_preflight(self) -> dict:
        """Validate API startup requirements for strict mode vs dev mode."""
        dev_mode = self._read_env_var("GUPPY_DEV_MODE").lower() in {"1", "true", "yes", "on"}
        if dev_mode:
            return {"ok": True, "status": "ok", "mode": "dev"}

        jwt_secret = self._read_env_var("GUPPY_JWT_SECRET")
        turnstile = self._read_env_var("TURNSTILE_SECRET")
        missing = []
        if not jwt_secret:
            missing.append("GUPPY_JWT_SECRET")
        if not turnstile:
            missing.append("TURNSTILE_SECRET")
        if missing:
            return {
                "ok": False,
                "status": "api_missing_auth_env",
                "hint": (
                    "Set " + ", ".join(missing) +
                    " or set GUPPY_DEV_MODE=1 for local development"
                ),
            }
        return {"ok": True, "status": "ok", "mode": "strict"}

    def _check_service_running(self, service: str) -> bool:
        svc = (service or "").lower()
        if svc == "api":
            return bool(self.check_api_server().get("ok"))
        if svc == "cloudflared":
            return bool(self.check_cloudflared().get("ok"))
        if svc == "ollama":
            return bool(self.check_ollama().get("ok"))
        return False

    def _api_process_running(self) -> bool:
        """Detect api process by command line, independent of HTTP health timing."""
        ps = (
            "$p = Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -match 'guppy_api.py' }; "
            "if ($p) { 'running' }"
        )
        res = self._run_command(["powershell", "-NoProfile", "-Command", ps], timeout_sec=4)
        out = f"{res.get('stdout', '')} {res.get('stderr', '')}".lower()
        return "running" in out

    def _ollama_process_running(self) -> bool:
        """Detect ollama process presence directly."""
        res = self._run_command(["tasklist", "/NH"], timeout_sec=4)
        text = f"{res.get('stdout', '')} {res.get('stderr', '')}".lower()
        return bool(re.search(r"\bollama(\.exe| app\.exe)?\b", text))

    @staticmethod
    def _normalize_result(completed: subprocess.CompletedProcess, timeout_sec: float) -> dict:
        code = int(completed.returncode or 0)
        out = (completed.stdout or "").strip()
        err = (completed.stderr or "").strip()
        if code == 0:
            return {"ok": True, "status": "ok", "code": code, "stdout": out[:200], "stderr": err[:200]}
        status = f"exit_{code}"
        if code == 128:
            status = "not_found_or_permission"
        return {"ok": False, "status": status, "code": code, "stdout": out[:200], "stderr": err[:200]}

    def _run_command(self, args: list[str], timeout_sec: float = 8.0) -> dict:
        try:
            cp = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                **_WIN_NO_WINDOW,
            )
            return self._normalize_result(cp, timeout_sec)
        except subprocess.TimeoutExpired:
            return {"ok": False, "status": f"timeout_{int(timeout_sec)}s", "code": -1, "stdout": "", "stderr": ""}
        except Exception as e:
            return {"ok": False, "status": f"exception:{str(e)[:60]}", "code": -1, "stdout": "", "stderr": ""}

    def start_service(self, service: str, dry_run: bool = False, verify_timeout_sec: float = 4.0) -> dict:
        """
        Start supported service in detached mode.
        Allowed: api, cloudflared, ollama.
        """
        svc = (service or "").lower()
        if not self.service_allowed(svc):
            return {"ok": False, "status": "blocked_by_allowlist"}

        if dry_run:
            return {"ok": True, "status": f"dry_run:start:{svc}"}

        if svc == "api":
            pre = self._api_preflight()
            if not pre.get("ok"):
                status = pre.get("status", "api_preflight_failed")
                hint = pre.get("hint", "")
                outcome = f"{status} | {hint}" if hint else status
                self.record_event("hub", "service_start_api", "operator", outcome)
                return {"ok": False, "status": outcome}

        if svc == "cloudflared":
            pre = self._cloudflared_preflight()
            if not pre.get("ok"):
                status = pre.get("status", "cloudflared_preflight_failed")
                hint = pre.get("hint", "")
                outcome = f"{status} | {hint}" if hint else status
                self.record_event("hub", "service_start_cloudflared", "operator", outcome)
                return {"ok": False, "status": outcome}

        try:
            if svc == "api":
                py = _ROOT / ".venv" / "Scripts" / "python.exe"
                python_exe = str(py) if py.exists() else "python"
                cmd = [python_exe, "guppy_api.py"]
                launch = subprocess.Popen(cmd, cwd=str(_ROOT), **_WIN_DETACHED)
            elif svc == "cloudflared":
                bat = _ROOT / "bin" / "start_tunnel.bat"
                if bat.exists():
                    cmd = [str(bat)]
                else:
                    cmd = ["cloudflared", "tunnel", "run"]
                launch = subprocess.Popen(cmd, cwd=str(_ROOT), **_WIN_DETACHED)
            elif svc == "ollama":
                cmd = ["ollama", "serve"]
                launch = subprocess.Popen(cmd, cwd=str(_ROOT), **_WIN_DETACHED)
            else:
                return {"ok": False, "status": "unsupported"}

            # Detached start command returns quickly; verify expected running state.
            _ = launch.pid
            deadline = time.time() + verify_timeout_sec
            running = False
            while time.time() < deadline:
                if self._check_service_running(svc):
                    running = True
                    break
                time.sleep(0.4)
            if running:
                self.record_event("hub", f"service_start_{svc}", "operator", "ok")
                return {"ok": True, "status": "started_verified"}
            self.record_event("hub", f"service_start_{svc}", "operator", "start_unverified")
            return {"ok": False, "status": "start_unverified"}
        except Exception as e:
            self.record_event("hub", f"service_start_{svc}", "operator", f"error:{e}")
            return {"ok": False, "status": str(e)[:80]}

    def stop_service(self, service: str, dry_run: bool = False, verify_timeout_sec: float = 4.0) -> dict:
        """
        Stop supported service safely.
        Allowed: api, cloudflared, ollama.
        """
        svc = (service or "").lower()
        if not self.service_allowed(svc):
            return {"ok": False, "status": "blocked_by_allowlist"}

        if dry_run:
            return {"ok": True, "status": f"dry_run:stop:{svc}"}

        # If it's already down, don't attempt kill commands that can produce noisy exit codes.
        if not self._check_service_running(svc):
            self.record_event("hub", f"service_stop_{svc}", "operator", "already_stopped")
            return {"ok": True, "status": "already_stopped"}

        try:
            if svc == "api":
                ps = (
                    "$ErrorActionPreference = 'SilentlyContinue'; "
                    "$p = Get-CimInstance Win32_Process | "
                    "Where-Object { $_.CommandLine -match 'guppy_api.py' }; "
                    "if ($p) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } }; "
                    "exit 0"
                )
                cmd_res = self._run_command(["powershell", "-NoProfile", "-Command", ps], timeout_sec=8)
            elif svc == "cloudflared":
                cmd_res = self._run_command(["taskkill", "/IM", "cloudflared.exe", "/F"], timeout_sec=8)
            elif svc == "ollama":
                ps = (
                    "$ErrorActionPreference = 'SilentlyContinue'; "
                    "Get-Process | Where-Object { $_.ProcessName -like 'ollama*' } | "
                    "ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }; "
                    "exit 0"
                )
                cmd_res = self._run_command(["powershell", "-NoProfile", "-Command", ps], timeout_sec=8)
            else:
                return {"ok": False, "status": "unsupported"}

            # taskkill may return non-zero if process absent; treat already-stopped as success.
            if not cmd_res.get("ok"):
                err_mix = f"{cmd_res.get('stdout','')} {cmd_res.get('stderr','')}".lower()
                if "not found" in err_mix or "no running instance" in err_mix or "cannot find" in err_mix:
                    cmd_res = {"ok": True, "status": "already_stopped"}

            if svc == "api":
                running_check = self._api_process_running
            elif svc == "ollama":
                running_check = self._ollama_process_running
            else:
                running_check = lambda: self._check_service_running(svc)

            deadline = time.time() + verify_timeout_sec
            stopped = False
            while time.time() < deadline:
                if not running_check():
                    stopped = True
                    break
                time.sleep(0.4)
            if stopped and cmd_res.get("ok"):
                self.record_event("hub", f"service_stop_{svc}", "operator", "ok")
                return {"ok": True, "status": cmd_res.get("status", "stopped_verified")}
            outcome = f"stop_unverified:{cmd_res.get('status','unknown')}"
            self.record_event("hub", f"service_stop_{svc}", "operator", outcome)
            return {"ok": False, "status": outcome}
        except Exception as e:
            self.record_event("hub", f"service_stop_{svc}", "operator", f"error:{e}")
            return {"ok": False, "status": str(e)[:80]}

    def restart_service(self, service: str, dry_run: bool = False) -> dict:
        """Restart supported service via stop then start."""
        svc = (service or "").lower()
        if not self.service_allowed(svc):
            return {"ok": False, "status": "blocked_by_allowlist"}

        if dry_run:
            return {"ok": True, "status": f"dry_run:restart:{svc}"}

        stop_res = self.stop_service(svc)
        time.sleep(0.5)
        start_res = self.start_service(svc)
        ok = bool(stop_res.get("ok") and start_res.get("ok"))
        status = f"stop={stop_res.get('status')} start={start_res.get('status')}"
        self.record_event("hub", f"service_restart_{svc}", "operator", status)
        return {"ok": ok, "status": status}

    # ── Smart Recommendations (no API) ─────────────────────────────────────────

    def smart_recommend(
        self,
        agent_id: str,
        crash_count: int = 0,
        queue_depth: int = 0,
        is_stalled: bool = False,
        last_seen_seconds: float = 0.0,
    ) -> str:
        """
        Rule-based recommendation for an agent. No API call.
        Returns: 'repair' | 'nudge' | 'ok'

        Called by:
          - OperatorCard (hub UI refresh)
          - ProactiveLoop (background daemon tick)
        """
        if crash_count >= 3:
            return "repair"
        if is_stalled and last_seen_seconds > 120:
            return "repair"
        if is_stalled:
            return "nudge"
        if queue_depth > 5:
            return "nudge"
        if last_seen_seconds > 300:
            return "nudge"
        return "ok"


# ── Singleton ───────────────────────────────────────────────────────────────────

_operator: HubOperator | None = None


def get_operator() -> HubOperator:
    """Get or create the global HubOperator instance."""
    global _operator
    if _operator is None:
        _operator = HubOperator()
    return _operator
