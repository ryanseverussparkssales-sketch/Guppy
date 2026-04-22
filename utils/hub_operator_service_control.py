from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any


def start_service(
    owner: Any,
    service: str,
    *,
    root: Path,
    win_detached: dict[str, Any],
    dry_run: bool = False,
    verify_timeout_sec: float = 4.0,
) -> dict[str, Any]:
    svc = (service or "").lower()
    if not owner.service_allowed(svc):
        return {"ok": False, "status": "blocked_by_allowlist"}

    if dry_run:
        return {"ok": True, "status": f"dry_run:start:{svc}"}

    if svc == "api":
        pre = owner._api_preflight()
        if not pre.get("ok"):
            status = pre.get("status", "api_preflight_failed")
            hint = pre.get("hint", "")
            outcome = f"{status} | {hint}" if hint else status
            owner.record_event("hub", "service_start_api", "operator", outcome)
            return {"ok": False, "status": outcome}

    if svc == "cloudflared":
        pre = owner._cloudflared_preflight()
        if not pre.get("ok"):
            status = pre.get("status", "cloudflared_preflight_failed")
            hint = pre.get("hint", "")
            outcome = f"{status} | {hint}" if hint else status
            owner.record_event("hub", "service_start_cloudflared", "operator", outcome)
            return {"ok": False, "status": outcome}

    try:
        if svc == "api":
            py = root / ".venv" / "Scripts" / "python.exe"
            python_exe = str(py) if py.exists() else "python"
            cmd = [python_exe, "guppy_api.py"]
            launch = subprocess.Popen(cmd, cwd=str(root), **win_detached)
        elif svc == "cloudflared":
            bat = root / "bin" / "start_tunnel.bat"
            if bat.exists():
                cmd = [str(bat)]
            else:
                cmd = ["cloudflared", "tunnel", "run"]
            launch = subprocess.Popen(cmd, cwd=str(root), **win_detached)
        elif svc == "ollama":
            cmd = ["ollama", "serve"]
            launch = subprocess.Popen(cmd, cwd=str(root), **win_detached)
        else:
            return {"ok": False, "status": "unsupported"}

        _ = launch.pid
        deadline = time.time() + verify_timeout_sec
        running = False
        while time.time() < deadline:
            if owner._check_service_running(svc):
                running = True
                break
            time.sleep(0.4)
        if running:
            owner.record_event("hub", f"service_start_{svc}", "operator", "ok")
            return {"ok": True, "status": "started_verified"}
        owner.record_event("hub", f"service_start_{svc}", "operator", "start_unverified")
        return {"ok": False, "status": "start_unverified"}
    except Exception as e:
        owner.record_event("hub", f"service_start_{svc}", "operator", f"error:{e}")
        return {"ok": False, "status": str(e)[:80]}


def stop_service(
    owner: Any,
    service: str,
    *,
    dry_run: bool = False,
    verify_timeout_sec: float = 4.0,
) -> dict[str, Any]:
    svc = (service or "").lower()
    if not owner.service_allowed(svc):
        return {"ok": False, "status": "blocked_by_allowlist"}

    if dry_run:
        return {"ok": True, "status": f"dry_run:stop:{svc}"}

    if not owner._check_service_running(svc):
        owner.record_event("hub", f"service_stop_{svc}", "operator", "already_stopped")
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
            cmd_res = owner._run_command(["powershell", "-NoProfile", "-Command", ps], timeout_sec=8)
        elif svc == "cloudflared":
            cmd_res = owner._run_command(["taskkill", "/IM", "cloudflared.exe", "/F"], timeout_sec=8)
        elif svc == "ollama":
            ps = (
                "$ErrorActionPreference = 'SilentlyContinue'; "
                "Get-Process | Where-Object { $_.ProcessName -like 'ollama*' } | "
                "ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }; "
                "exit 0"
            )
            cmd_res = owner._run_command(["powershell", "-NoProfile", "-Command", ps], timeout_sec=8)
        else:
            return {"ok": False, "status": "unsupported"}

        if not cmd_res.get("ok"):
            err_mix = f"{cmd_res.get('stdout', '')} {cmd_res.get('stderr', '')}".lower()
            if "not found" in err_mix or "no running instance" in err_mix or "cannot find" in err_mix:
                cmd_res = {"ok": True, "status": "already_stopped"}

        if svc == "api":
            running_check = owner._api_process_running
        elif svc == "ollama":
            running_check = owner._ollama_process_running
        else:
            running_check = lambda: owner._check_service_running(svc)

        deadline = time.time() + verify_timeout_sec
        stopped = False
        while time.time() < deadline:
            if not running_check():
                stopped = True
                break
            time.sleep(0.4)
        if stopped and cmd_res.get("ok"):
            owner.record_event("hub", f"service_stop_{svc}", "operator", "ok")
            return {"ok": True, "status": cmd_res.get("status", "stopped_verified")}
        outcome = f"stop_unverified:{cmd_res.get('status', 'unknown')}"
        owner.record_event("hub", f"service_stop_{svc}", "operator", outcome)
        return {"ok": False, "status": outcome}
    except Exception as e:
        owner.record_event("hub", f"service_stop_{svc}", "operator", f"error:{e}")
        return {"ok": False, "status": str(e)[:80]}


def restart_service(owner: Any, service: str, *, dry_run: bool = False) -> dict[str, Any]:
    svc = (service or "").lower()
    if not owner.service_allowed(svc):
        return {"ok": False, "status": "blocked_by_allowlist"}

    if dry_run:
        return {"ok": True, "status": f"dry_run:restart:{svc}"}

    stop_res = owner.stop_service(svc)
    time.sleep(0.5)
    start_res = owner.start_service(svc)
    ok = bool(stop_res.get("ok") and start_res.get("ok"))
    status = f"stop={stop_res.get('status')} start={start_res.get('status')}"
    owner.record_event("hub", f"service_restart_{svc}", "operator", status)
    return {"ok": ok, "status": status}
