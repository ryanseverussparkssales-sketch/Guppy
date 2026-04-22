from __future__ import annotations

import json
import os
import re
import sys
import urllib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import src.guppy.launcher_application as launcher_app
from src.guppy.launcher_application.launcher_api_runtime_control import (
    api_base_url,
    api_reachable,
    api_reachability_status,
    direct_audit_runtime,
    direct_health_snapshot,
    direct_warmup,
    ensure_api_reachable_for_command,
    http_json,
    read_repair_token,
    refresh_api_auth_state,
    refresh_repair_token_from_api,
    run_auth_self_check,
    start_api_subprocess,
    start_supervised_api_subprocess,
    startup_readiness_status,
)
from src.guppy.launcher_application.storage_io import (
    get_secret,
    secret_store_backend_available,
    secret_store_client,
)
from src.guppy.runtime_application import build_local_bearer_token, summarize_startup_readiness

_RUNTIME = Path(__file__).resolve().parent.parent.parent / "runtime"
_SECRET_STORE_AVAILABLE = secret_store_backend_available()
_SECRET_STORE = secret_store_client()
_COMMAND_START_TTL_SECONDS = float(os.environ.get("GUPPY_COMMAND_START_TTL_SECONDS", "20"))


def _compat_module_value(owner, name: str, default):
    module = sys.modules.get(owner.__class__.__module__)
    if module is not None and hasattr(module, name):
        return getattr(module, name)
    launcher_module = sys.modules.get("ui.launcher.launcher_window")
    if launcher_module is not None and hasattr(launcher_module, name):
        return getattr(launcher_module, name)
    return default


class LauncherRuntimeControlMixin:
    @staticmethod
    def _api_port() -> str:
        return os.environ.get("GUPPY_API_PORT", "8081").strip() or "8081"

    def _api_base_url(self) -> str:
        return api_base_url(self)

    def _build_local_bearer_token(self) -> str:
        token, token_source = build_local_bearer_token()
        self._api_token_source = token_source
        return token

    def _refresh_api_auth_state(self, reason: str) -> str:
        return refresh_api_auth_state(self, reason)

    @staticmethod
    def _is_unauthorized_error(error_text: str) -> bool:
        txt = (error_text or "").lower()
        return "http 401" in txt or "unauthorized" in txt

    @staticmethod
    def _extract_error_code(error_text: str) -> str:
        txt = (error_text or "").strip()
        match = re.search(r"\[([A-Za-z0-9_:-]+)\]", txt)
        return match.group(1) if match else ""

    def _read_repair_token(self) -> str:
        runtime_dir = _compat_module_value(self, "_RUNTIME", _RUNTIME)
        secret_store_available = _compat_module_value(
            self,
            "_SECRET_STORE_AVAILABLE",
            _SECRET_STORE_AVAILABLE,
        )
        secret_store = _compat_module_value(self, "_secret_store", _SECRET_STORE)
        return read_repair_token(
            self,
            runtime_dir=runtime_dir,
            secret_store_available=secret_store_available,
            secret_store=secret_store,
            get_secret=get_secret,
        )

    @staticmethod
    def _validate_repair_token(token: str) -> bool:
        return launcher_app.is_valid_repair_token(token)

    def _http_json(
        self,
        path: str,
        method: str = "GET",
        payload: dict | None = None,
        timeout: float = 8.0,
        retry_auth_on_401: bool = False,
        auth_retry_reason: str = "",
    ) -> dict:
        request_module = _compat_module_value(self, "urllib", urllib).request
        error_module = _compat_module_value(self, "urllib", urllib).error
        return http_json(
            self,
            path,
            request_module=request_module,
            error_module=error_module,
            method=method,
            payload=payload,
            timeout=timeout,
            retry_auth_on_401=retry_auth_on_401,
            auth_retry_reason=auth_retry_reason,
        )

    def _refresh_repair_token_from_api(self, timeout: float = 4.0) -> str:
        request_module = _compat_module_value(self, "urllib", urllib).request
        return refresh_repair_token_from_api(
            self,
            request_module=request_module,
            timeout=timeout,
        )

    @staticmethod
    def _payload_signature(payload: object) -> str:
        try:
            return json.dumps(
                payload,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        except Exception:
            try:
                return str(payload)
            except Exception:
                return ""

    @staticmethod
    def _summarize_startup_readiness(snapshot: dict[str, object] | None) -> str:
        return summarize_startup_readiness(snapshot)

    def _startup_readiness_status(
        self,
        timeout: float = 1.5,
        *,
        deep: bool = False,
    ) -> tuple[str, str, dict[str, object]]:
        return startup_readiness_status(self, timeout=timeout, deep=deep)

    def _api_reachable(self, timeout: float = 1.5) -> bool:
        return api_reachable(self, timeout=timeout)

    def _api_reachability_status(self, timeout: float = 1.5) -> tuple[str, str]:
        return api_reachability_status(self, timeout=timeout)

    def _run_auth_self_check(self) -> None:
        run_auth_self_check(self)

    def _start_api_subprocess(self) -> tuple[bool, str]:
        runtime_dir = _compat_module_value(self, "_RUNTIME", _RUNTIME)
        ttl_seconds = _compat_module_value(
            self,
            "_COMMAND_START_TTL_SECONDS",
            _COMMAND_START_TTL_SECONDS,
        )
        return start_api_subprocess(
            self,
            runtime_dir=runtime_dir,
            ttl_seconds=ttl_seconds,
        )

    def _start_supervised_api_subprocess(self) -> tuple[bool, str]:
        runtime_dir = _compat_module_value(self, "_RUNTIME", _RUNTIME)
        ttl_seconds = _compat_module_value(
            self,
            "_COMMAND_START_TTL_SECONDS",
            _COMMAND_START_TTL_SECONDS,
        )
        return start_supervised_api_subprocess(
            self,
            runtime_dir=runtime_dir,
            ttl_seconds=ttl_seconds,
        )

    def _ensure_api_reachable_for_command(self) -> tuple[bool, str]:
        return ensure_api_reachable_for_command(self)

    def _direct_warmup(self) -> dict:
        return direct_warmup(runtime_dir=_compat_module_value(self, "_RUNTIME", _RUNTIME))

    def _direct_audit_runtime(self) -> dict:
        return direct_audit_runtime(
            runtime_dir=_compat_module_value(self, "_RUNTIME", _RUNTIME),
            now_factory=lambda: datetime.now(timezone.utc),
        )

    def _direct_health_snapshot(self) -> dict:
        return direct_health_snapshot(runtime_dir=_compat_module_value(self, "_RUNTIME", _RUNTIME))
