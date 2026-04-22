from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI


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
        validate_environment()
        ensure_instance_scaffold()
        owner = module_owner()
        await startup_host(owner)
        try:
            yield
        finally:
            await shutdown_host(owner)

    return lifespan
