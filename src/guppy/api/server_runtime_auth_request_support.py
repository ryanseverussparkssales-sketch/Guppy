from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(frozen=True, slots=True)
class ServerRuntimeAuthRequestBindings:
    require_rate_limit: Callable[..., Any]
    require_auth_rate_limit: Callable[..., Any]
    require_repair_token: Callable[..., Any]
    verify_turnstile_token_auth: Callable[[str], Awaitable[bool]]
    create_access_token: Callable[..., str]
    access_token_expire_minutes: int
    request_timing_middleware: Callable[..., Awaitable[Any]]


def bind_auth_request_support(
    *,
    bind_owner: Callable[[Callable[..., Any]], Callable[..., Any]],
    module_owner: Callable[[], Any],
    services_host_module: Any,
    services_ops_module: Any,
    require_rate_limit: Callable[..., Any],
    require_auth_rate_limit: Callable[..., Any],
    verify_turnstile_token_auth: Callable[[str], Awaitable[bool]],
    create_access_token: Callable[..., str],
    access_token_expire_minutes: int,
) -> ServerRuntimeAuthRequestBindings:
    require_repair_token = bind_owner(services_ops_module.require_repair_token)

    async def request_timing_middleware(request: Any, call_next: Callable[[Any], Awaitable[Any]]) -> Any:
        import time

        started = time.perf_counter()
        status_code = 500
        owner = module_owner()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            services_host_module.record_request_failure(
                owner,
                request,
                status_code,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        services_host_module.record_request_completion(
            owner,
            request,
            response,
            elapsed_ms,
        )
        return response

    return ServerRuntimeAuthRequestBindings(
        require_rate_limit=require_rate_limit,
        require_auth_rate_limit=require_auth_rate_limit,
        require_repair_token=require_repair_token,
        verify_turnstile_token_auth=verify_turnstile_token_auth,
        create_access_token=create_access_token,
        access_token_expire_minutes=access_token_expire_minutes,
        request_timing_middleware=request_timing_middleware,
    )
