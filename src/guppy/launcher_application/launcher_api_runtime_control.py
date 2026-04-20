from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import src.guppy.launcher_application as launcher_app
from src.guppy.runtime_application import fetch_startup_readiness

from .launch_attempt_guard import (
    clear_launch_attempt,
    launch_attempt_recent,
    mark_launch_attempt,
)


def api_base_url(owner) -> str:
    port = owner._api_port() if hasattr(owner, "_api_port") else "8081"
    return f"http://127.0.0.1:{port}"


def refresh_api_auth_state(owner, reason: str) -> str:
    owner._api_bearer_token = owner._build_local_bearer_token()
    owner._auth_self_check_ok = False
    owner._auth_self_check_inflight = False
    owner._auth_self_check_last_attempt = 0.0
    owner._log_launcher_event(
        "auth_token_refreshed",
        reason=reason,
        token_source=owner._api_token_source,
        has_token=bool(owner._api_bearer_token),
    )
    return owner._api_bearer_token


def read_repair_token(
    owner,
    *,
    runtime_dir: Path,
    secret_store_available: bool,
    secret_store,
    get_secret,
) -> str:
    if secret_store_available and secret_store is not None:
        try:
            if hasattr(secret_store, "get_secret"):
                ks_token = secret_store.get_secret("repair_token")
            else:
                ks_token = get_secret("repair_token")
            if ks_token and launcher_app.is_valid_repair_token(ks_token):
                return ks_token
        except Exception:
            pass
    tok_path = runtime_dir / "repair_token.txt"
    try:
        if not tok_path.exists() or not tok_path.is_file():
            return ""
        token = tok_path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    return token if launcher_app.is_valid_repair_token(token) else ""


def http_json(
    owner,
    path: str,
    *,
    request_module,
    error_module,
    method: str = "GET",
    payload: dict | None = None,
    timeout: float = 8.0,
    retry_auth_on_401: bool = False,
    auth_retry_reason: str = "",
) -> dict:
    url = owner._api_base_url() + path
    data = None
    headers = {"Accept": "application/json"}
    if owner._api_bearer_token:
        headers["Authorization"] = f"Bearer {owner._api_bearer_token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if path == "/repair":
        repair_token = owner._read_repair_token()
        if repair_token:
            headers["X-Repair-Token"] = repair_token
    req = request_module.Request(url, data=data, headers=headers, method=method)
    try:
        with request_module.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}
    except error_module.HTTPError as e:
        err_code = ""
        if e.code == 403 and path == "/repair":
            try:
                body = e.read().decode("utf-8", errors="replace")
                parsed = json.loads(body) if body.strip() else {}
                detail_payload = parsed.get("detail", "")
                err_code = detail_payload.get("code", "") if isinstance(detail_payload, dict) else ""
            except Exception:
                err_code = ""
            if err_code.startswith("repair_token_"):
                refreshed = owner._refresh_repair_token_from_api(timeout=timeout)
                if refreshed:
                    headers["X-Repair-Token"] = refreshed
                    retry_req = request_module.Request(url, data=data, headers=headers, method=method)
                    try:
                        with request_module.urlopen(retry_req, timeout=timeout) as resp:
                            raw = resp.read().decode("utf-8", errors="replace")
                        owner._log_launcher_event("repair_token_resynced", ok=True)
                        return json.loads(raw) if raw.strip() else {}
                    except Exception as retry_exc:
                        owner._log_launcher_event(
                            "repair_token_resync_failed",
                            ok=False,
                            reason="retry_failed",
                            error=str(retry_exc),
                            auth_code=err_code,
                        )
                else:
                    owner._log_launcher_event(
                        "repair_token_resync_failed",
                        ok=False,
                        reason="invalid_or_missing_refresh_token",
                        auth_code=err_code,
                    )
        detail = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body.strip() else {}
            detail_payload = parsed.get("detail", "") if isinstance(parsed, dict) else ""
            if isinstance(detail_payload, dict):
                err_code = detail_payload.get("code", "")
                message = detail_payload.get("message", "")
                detail = message or err_code
            elif isinstance(detail_payload, str):
                detail = detail_payload
        except Exception:
            detail = ""

        if e.code == 401 and retry_auth_on_401:
            refreshed = owner._refresh_api_auth_state(auth_retry_reason or f"{path}_401")
            owner._log_launcher_event(
                "auth_retry",
                path=path,
                reason=auth_retry_reason or path,
                auth_code=err_code,
                has_token=bool(refreshed),
            )
            if refreshed:
                retry_headers = dict(headers)
                retry_headers["Authorization"] = f"Bearer {refreshed}"
                retry_req = request_module.Request(url, data=data, headers=retry_headers, method=method)
                try:
                    with request_module.urlopen(retry_req, timeout=timeout) as resp:
                        raw = resp.read().decode("utf-8", errors="replace")
                    owner._log_launcher_event(
                        "auth_retry_result",
                        path=path,
                        reason=auth_retry_reason or path,
                        auth_code=err_code,
                        ok=True,
                    )
                    return json.loads(raw) if raw.strip() else {}
                except Exception as retry_error:
                    owner._log_launcher_event(
                        "auth_retry_result",
                        path=path,
                        reason=auth_retry_reason or path,
                        auth_code=err_code,
                        ok=False,
                        error=str(retry_error),
                    )
                    raise RuntimeError(str(retry_error)) from retry_error

        if detail:
            if err_code:
                raise RuntimeError(f"HTTP {e.code} {e.reason} [{err_code}]: {detail}") from e
            raise RuntimeError(f"HTTP {e.code} {e.reason}: {detail}") from e
        raise RuntimeError(f"HTTP {e.code} {e.reason}") from e
    except error_module.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}") from e


def refresh_repair_token_from_api(owner, *, request_module, timeout: float = 4.0) -> str:
    try:
        bearer = str(owner._api_bearer_token or "").strip()
        if not bearer:
            try:
                bearer = str(owner._build_local_bearer_token() or "").strip()
            except Exception:
                bearer = ""
        if bearer:
            owner._api_bearer_token = bearer
        refresh_url = owner._api_base_url() + "/repair-token/refresh"
        headers = {"Accept": "application/json"}
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        req = request_module.Request(refresh_url, headers=headers, method="GET")
        with request_module.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        token = (json.loads(raw) if raw.strip() else {}).get("repair_token", "")
        return token if launcher_app.is_valid_repair_token(token) else ""
    except Exception:
        return ""


def startup_readiness_status(
    owner,
    *,
    timeout: float = 1.5,
    deep: bool = False,
) -> tuple[str, str, dict[str, object]]:
    return fetch_startup_readiness(
        owner._http_json,
        timeout=timeout,
        deep=deep,
        unauthorized_error=owner._is_unauthorized_error,
    )


def api_reachability_status(owner, *, timeout: float = 1.5) -> tuple[str, str]:
    state, detail, _snapshot = owner._startup_readiness_status(timeout=timeout)
    return state, detail


def api_reachable(owner, *, timeout: float = 1.5) -> bool:
    state, _detail = owner._api_reachability_status(timeout=timeout)
    return state == "reachable"


def run_auth_self_check(owner) -> None:
    try:
        payload = owner._http_json(
            "/auth/self-check",
            method="GET",
            timeout=2.5,
            retry_auth_on_401=True,
            auth_retry_reason="auth_self_check",
        )
        ok = bool(payload.get("ok", False))
        owner._log_launcher_event(
            "auth_self_check",
            ok=ok,
            mode=str(payload.get("mode", "unknown")),
            user_id=str(payload.get("user_id", "")),
            token_source=owner._api_token_source,
        )
        owner._auth_self_check_ok = ok
        if ok:
            owner._status_panel.append_syslog("auth self-check: OK")
        else:
            owner._status_panel.append_syslog("auth self-check: ERROR")
    except Exception as exc:
        fallback_ok = False
        if "404" in str(exc):
            try:
                owner._http_json(
                    "/status",
                    method="GET",
                    timeout=2.5,
                    retry_auth_on_401=True,
                    auth_retry_reason="auth_self_check_status_fallback",
                )
                fallback_ok = True
            except Exception:
                fallback_ok = False
        if fallback_ok:
            owner._auth_self_check_ok = True
            owner._log_launcher_event(
                "auth_self_check",
                ok=True,
                mode="status_fallback",
                user_id="",
                token_source=owner._api_token_source,
            )
            owner._status_panel.append_syslog("auth self-check: OK (status fallback)")
        else:
            owner._auth_self_check_ok = False
            auth_code = owner._extract_error_code(str(exc))
            owner._log_launcher_event(
                "auth_self_check",
                ok=False,
                token_source=owner._api_token_source,
                auth_code=auth_code,
                error=str(exc),
            )
            if auth_code:
                owner._status_panel.append_syslog(f"auth self-check failed [{auth_code}]: {exc}")
            else:
                owner._status_panel.append_syslog(f"auth self-check failed: {exc}")
    finally:
        owner._auth_self_check_inflight = False


def start_api_subprocess(
    owner,
    *,
    runtime_dir: Path,
    ttl_seconds: float,
) -> tuple[bool, str]:
    root = Path(__file__).resolve().parent.parent.parent.parent
    script = root / "guppy_api.py"
    if not script.exists():
        return False, "guppy_api.py not found"
    if launch_attempt_recent(runtime_dir, "launcher_command_api", ttl_seconds=ttl_seconds):
        owner._log_launcher_event("api_command_launch_debounced", mode="direct")
        return False, "api launch already attempted recently"
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    python = str(venv_python) if venv_python.exists() else sys.executable
    flags = {}
    if sys.platform == "win32":
        flags["creationflags"] = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        flags["startupinfo"] = startupinfo
    try:
        mark_launch_attempt(runtime_dir, "launcher_command_api")
        subprocess.Popen([python, str(script)], cwd=str(root), **flags)
        deadline = time.time() + 6.0
        while time.time() < deadline:
            time.sleep(0.5)
            state, detail = owner._api_reachability_status(timeout=0.8)
            if state == "reachable":
                clear_launch_attempt(runtime_dir, "launcher_command_api")
                return True, detail or "api started and published startup readiness"
            if state == "auth_failed":
                return False, detail or "api requires refreshed auth"
        return False, "api process started but not yet reachable"
    except Exception as exc:
        clear_launch_attempt(runtime_dir, "launcher_command_api")
        return False, str(exc)


def start_supervised_api_subprocess(
    owner,
    *,
    runtime_dir: Path,
    ttl_seconds: float,
) -> tuple[bool, str]:
    root = Path(__file__).resolve().parent.parent.parent.parent
    script = root / "bin" / "launch_api_supervised.bat"
    if not script.exists():
        return False, "launch_api_supervised.bat not found"
    if launch_attempt_recent(runtime_dir, "launcher_command_supervised_api", ttl_seconds=ttl_seconds):
        owner._log_launcher_event("api_command_launch_debounced", mode="supervised")
        return False, "supervised api launch already attempted recently"
    try:
        kwargs: dict[str, object] = {"cwd": str(root)}
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
            startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
            kwargs["startupinfo"] = startupinfo
            mark_launch_attempt(runtime_dir, "launcher_command_supervised_api")
            subprocess.Popen(["cmd.exe", "/c", str(script)], **kwargs)
        else:
            mark_launch_attempt(runtime_dir, "launcher_command_supervised_api")
            subprocess.Popen([str(script)], **kwargs)
        deadline = time.time() + 8.0
        while time.time() < deadline:
            time.sleep(0.5)
            state, detail = owner._api_reachability_status(timeout=0.8)
            if state == "reachable":
                clear_launch_attempt(runtime_dir, "launcher_command_supervised_api")
                return True, detail or "supervised api started and published startup readiness"
            if state == "auth_failed":
                return False, detail or "api requires refreshed auth"
        return False, "supervised api launcher started but the API is not yet reachable"
    except Exception as exc:
        clear_launch_attempt(runtime_dir, "launcher_command_supervised_api")
        return False, str(exc)


def ensure_api_reachable_for_command(owner) -> tuple[bool, str]:
    state, detail = owner._api_reachability_status(timeout=0.8)
    if state == "reachable":
        return True, detail or "api already reachable"
    started, detail = owner._start_api_subprocess()
    if started:
        return True, detail
    owner._log_launcher_event(
        "api_command_start_failed",
        mode="direct_only",
        reason=detail,
    )
    return False, detail
