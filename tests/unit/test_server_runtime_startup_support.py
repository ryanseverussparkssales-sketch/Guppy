from __future__ import annotations

from types import SimpleNamespace

from src.guppy.api.server_runtime_startup_support import (
    bind_startup_support,
    build_lifespan,
)


def test_bind_startup_support_wraps_host_and_readiness_functions() -> None:
    calls: list[tuple[str, object]] = []

    def bind_owner(func):
        def wrapper(*args, **kwargs):
            return func("OWNER", *args, **kwargs)

        return wrapper

    host_services = SimpleNamespace(
        read_repair_token=lambda owner, **_: calls.append(("read_repair_token", owner)) or "token",
        restart_managed_daemon=lambda owner, **_: calls.append(("restart_managed_daemon", owner)) or {"ok": True},
        set_repair_token=lambda owner, token: calls.append(("set_repair_token", owner)) or token,
    )
    runtime_services = SimpleNamespace(
        secret_ready=lambda: True,
        build_startup_readiness_payload=lambda owner: calls.append(("build_startup_readiness_payload", owner)) or {"overall": "READY"},
        startup_readiness_snapshot=lambda owner: calls.append(("startup_readiness_snapshot", owner)) or {"overall": "READY"},
        startup_readiness_cached_or_unknown=lambda owner: calls.append(("startup_readiness_cached_or_unknown", owner)) or {"overall": "READY"},
        startup_readiness_cached_or_snapshot=lambda owner: calls.append(("startup_readiness_cached_or_snapshot", owner)) or {"overall": "READY"},
        startup_readiness_cache_expired=lambda owner: calls.append(("startup_readiness_cache_expired", owner)) or False,
        trigger_startup_readiness_refresh=lambda owner: calls.append(("trigger_startup_readiness_refresh", owner)) or None,
    )

    support = bind_startup_support(
        bind_owner=bind_owner,
        services_host_module=host_services,
        services_runtime_module=runtime_services,
    )

    assert support.read_repair_token() == "token"
    assert support.restart_managed_daemon() == {"ok": True}
    assert support.set_repair_token("abc") == "abc"
    assert support.secret_ready() is True
    assert support.build_startup_readiness_payload() == {"overall": "READY"}
    assert support.startup_readiness_snapshot() == {"overall": "READY"}
    assert support.startup_readiness_cached_or_unknown() == {"overall": "READY"}
    assert support.startup_readiness_cached_or_snapshot() == {"overall": "READY"}
    assert support.startup_readiness_cache_expired() is False
    assert support.trigger_startup_readiness_refresh() is None
    assert all(owner == "OWNER" for _, owner in calls)


def test_build_lifespan_runs_startup_and_shutdown_in_order() -> None:
    events: list[tuple[str, object]] = []
    owner = object()

    async def exercise() -> None:
        async def startup_host(current_owner):
            events.append(("startup_host", current_owner))

        async def shutdown_host(current_owner):
            events.append(("shutdown_host", current_owner))

        lifespan = build_lifespan(
            module_owner=lambda: owner,
            validate_environment=lambda: events.append(("validate_environment", None)),
            ensure_instance_scaffold=lambda: events.append(("ensure_instance_scaffold", None)),
            startup_host=startup_host,
            shutdown_host=shutdown_host,
        )
        async with lifespan(None):
            events.append(("inside", None))

    import asyncio

    asyncio.run(exercise())

    assert events == [
        ("validate_environment", None),
        ("ensure_instance_scaffold", None),
        ("startup_host", owner),
        ("inside", None),
        ("shutdown_host", owner),
    ]
