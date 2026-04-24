from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.guppy.api.server_runtime_auth_request_support import bind_auth_request_support


def test_bind_auth_request_support_wraps_auth_and_repair_bindings() -> None:
    calls: list[tuple[str, object]] = []

    def bind_owner(func):
        def wrapper(*args, **kwargs):
            return func("OWNER", *args, **kwargs)

        return wrapper

    async def verify_turnstile_token_auth(token: str) -> bool:
        return token == "ok"

    services_host = SimpleNamespace(
        record_request_failure=lambda *args, **kwargs: None,
        record_request_completion=lambda *args, **kwargs: None,
    )
    services_ops = SimpleNamespace(
        require_repair_token=lambda owner, request: calls.append(("require_repair_token", owner)) or request,
    )

    support = bind_auth_request_support(
        bind_owner=bind_owner,
        module_owner=lambda: "MODULE",
        services_host_module=services_host,
        services_ops_module=services_ops,
        require_rate_limit=lambda: "rate-limit",
        require_auth_rate_limit=lambda: "auth-rate-limit",
        verify_turnstile_token_auth=verify_turnstile_token_auth,
        create_access_token=lambda data: f"token:{data['sub']}",
        access_token_expire_minutes=42,
    )

    assert support.require_rate_limit() == "rate-limit"
    assert support.require_auth_rate_limit() == "auth-rate-limit"
    assert support.require_repair_token("request") == "request"
    assert asyncio.run(support.verify_turnstile_token_auth("ok")) is True
    assert support.create_access_token({"sub": "guppy"}) == "token:guppy"
    assert support.access_token_expire_minutes == 42
    assert calls == [("require_repair_token", "OWNER")]


def test_request_timing_middleware_records_completion() -> None:
    events: list[tuple[str, object]] = []

    async def exercise() -> None:
        support = bind_auth_request_support(
            bind_owner=lambda func: func,
            module_owner=lambda: "MODULE",
            services_host_module=SimpleNamespace(
                record_request_failure=lambda *args, **kwargs: events.append(("failure", args[0])),
                record_request_completion=lambda *args, **kwargs: events.append(("completion", args[0])),
            ),
            services_ops_module=SimpleNamespace(require_repair_token=lambda request: request),
            require_rate_limit=lambda: "rate-limit",
            require_auth_rate_limit=lambda: "auth-rate-limit",
            verify_turnstile_token_auth=lambda token: asyncio.sleep(0, result=token == "ok"),
            create_access_token=lambda data: "token",
            access_token_expire_minutes=60,
        )
        request = SimpleNamespace(method="GET", url=SimpleNamespace(path="/status"))
        response = SimpleNamespace(status_code=200, headers={})

        async def call_next(current_request):
            assert current_request is request
            return response

        observed = await support.request_timing_middleware(request, call_next)
        assert observed is response

    asyncio.run(exercise())

    assert events == [("completion", "MODULE")]


def test_request_timing_middleware_records_failure_and_reraises() -> None:
    events: list[tuple[str, object]] = []

    async def exercise() -> None:
        support = bind_auth_request_support(
            bind_owner=lambda func: func,
            module_owner=lambda: "MODULE",
            services_host_module=SimpleNamespace(
                record_request_failure=lambda *args, **kwargs: events.append(("failure", args[0])),
                record_request_completion=lambda *args, **kwargs: events.append(("completion", args[0])),
            ),
            services_ops_module=SimpleNamespace(require_repair_token=lambda request: request),
            require_rate_limit=lambda: "rate-limit",
            require_auth_rate_limit=lambda: "auth-rate-limit",
            verify_turnstile_token_auth=lambda token: asyncio.sleep(0, result=token == "ok"),
            create_access_token=lambda data: "token",
            access_token_expire_minutes=60,
        )
        request = SimpleNamespace(method="GET", url=SimpleNamespace(path="/status"))

        async def call_next(_current_request):
            raise RuntimeError("boom")

        try:
            await support.request_timing_middleware(request, call_next)
        except RuntimeError as exc:
            assert str(exc) == "boom"
        else:
            raise AssertionError("expected RuntimeError")

    asyncio.run(exercise())

    assert events == [("failure", "MODULE")]
