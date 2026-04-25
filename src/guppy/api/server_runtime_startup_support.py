from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI

_log = logging.getLogger(__name__)


def _install_windows_asyncio_exception_filter() -> None:
    """Suppress the harmless WinError 10054 noise from asyncio on Windows.

    When a remote client disconnects abruptly, Windows raises ConnectionResetError
    inside asyncio's ProactorBasePipeTransport._call_connection_lost. This is not
    a server error — it is normal keep-alive teardown — but it pollutes the log
    at ERROR level. We install a loop exception handler that demotes it to DEBUG.
    """
    if sys.platform != "win32":
        return

    loop = asyncio.get_event_loop()

    def _handler(loop: asyncio.AbstractEventLoop, ctx: dict) -> None:
        exc = ctx.get("exception")
        if isinstance(exc, ConnectionResetError) and getattr(exc, "winerror", None) == 10054:
            _log.debug("asyncio WinError 10054 suppressed: %s", ctx.get("message", ""))
            return
        loop.default_exception_handler(ctx)

    loop.set_exception_handler(_handler)


@dataclass(frozen=True, slots=True)
class ServerRuntimeStartupBindings:
    read_repair_token: Callable[..., str]
    restart_managed_daemon: Callable[..., dict[str, Any]]
    set_repair_token: Callable[..., str]
    secret_ready: Callable[[], bool]
    build_startup_readiness_payload: Callable[[], dict[str, Any]]
    startup_readiness_snapshot: Callable[[], dict[str, Any]]
    startup_readiness_cached_or_unknown: Callable[[], dict[str, Any]]
    startup_readiness_cached_or_snapshot: Callable[[], dict[str, Any]]
    startup_readiness_cache_expired: Callable[[], bool]
    trigger_startup_readiness_refresh: Callable[[], None]


def bind_startup_support(
    *,
    bind_owner: Callable[[Callable[..., Any]], Callable[..., Any]],
    services_host_module: Any,
    services_runtime_module: Any,
) -> ServerRuntimeStartupBindings:
    return ServerRuntimeStartupBindings(
        read_repair_token=bind_owner(services_host_module.read_repair_token),
        restart_managed_daemon=bind_owner(services_host_module.restart_managed_daemon),
        set_repair_token=bind_owner(services_host_module.set_repair_token),
        secret_ready=services_runtime_module.secret_ready,
        build_startup_readiness_payload=bind_owner(services_runtime_module.build_startup_readiness_payload),
        startup_readiness_snapshot=bind_owner(services_runtime_module.startup_readiness_snapshot),
        startup_readiness_cached_or_unknown=bind_owner(services_runtime_module.startup_readiness_cached_or_unknown),
        startup_readiness_cached_or_snapshot=bind_owner(services_runtime_module.startup_readiness_cached_or_snapshot),
        startup_readiness_cache_expired=bind_owner(services_runtime_module.startup_readiness_cache_expired),
        trigger_startup_readiness_refresh=bind_owner(services_runtime_module.trigger_startup_readiness_refresh),
    )


def _check_ollama_reachable() -> None:
    """Warn (don't fail) if Ollama is unreachable at startup.

    A missing Ollama is a recoverable state — the user may start it later.
    We surface a clear warning now so the logs tell the story upfront.
    """
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2):
            _log.info("Ollama reachable on port 11434")
    except Exception as exc:
        _log.warning(
            "Ollama not reachable on port 11434 (%s). "
            "Chat requests will fail until Ollama is started.",
            exc,
        )


def build_lifespan(
    *,
    module_owner: Callable[[], Any],
    validate_environment: Callable[[], Any],
    ensure_instance_scaffold: Callable[[], Any],
    startup_host: Callable[[Any], Awaitable[Any]],
    shutdown_host: Callable[[Any], Awaitable[Any]],
):
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        _install_windows_asyncio_exception_filter()
        try:
            validate_environment()
        except Exception:
            _log.exception("validate_environment() raised — server may be misconfigured")
        try:
            ensure_instance_scaffold()
        except Exception:
            _log.exception("ensure_instance_scaffold() raised — instance state may be incomplete")
        _check_ollama_reachable()
        owner = module_owner()
        try:
            await startup_host(owner)
        except Exception:
            _log.exception("startup_host() raised — some subsystems may not be available")
        try:
            yield
        finally:
            try:
                await shutdown_host(owner)
            except Exception:
                _log.exception("shutdown_host() raised during cleanup")

    return lifespan
