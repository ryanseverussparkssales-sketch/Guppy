"""Auth stub shims and response-cache helpers for the runtime snapshot.

Extracted from server_runtime_snapshot.py as part of TR54 wave – auth/cache seam.
The try/except import blocks with fallback stubs live here so the snapshot module
only needs flat imports.
"""
from __future__ import annotations

from typing import Any

# -- Auth stubs -----------------------------------------------------------
try:
    from src.guppy.api.auth import (
        create_access_token,
        verify_token,
        require_turnstile,
        require_rate_limit,
        require_auth_rate_limit,
        verify_turnstile_token as verify_turnstile_token_auth,
        validate_environment,
    )
except ImportError as e:
    print(f"Warning: Auth module not available: {e}")

    def create_access_token(data: Any) -> str:  # type: ignore[misc]
        return "dev-token"

    def verify_token() -> str:  # type: ignore[misc]
        return "dev-user"

    def require_turnstile() -> str:  # type: ignore[misc]
        return "dev-token"

    def require_rate_limit(user_id: str = "dev") -> str:  # type: ignore[misc]
        return user_id

    def require_auth_rate_limit() -> str:  # type: ignore[misc]
        return "dev-auth"

    async def verify_turnstile_token_auth(token: str) -> bool:  # type: ignore[misc]
        return True

    def validate_environment() -> bool:  # type: ignore[misc]
        return False


# -- Response cache helpers -----------------------------------------------
try:
    from src.guppy.api.response_cache import (
        build_response_cache_key,
        get_cached_response,
        response_cache_enabled,
        set_cached_response,
    )
except Exception:
    def build_response_cache_key(  # type: ignore[misc]
        *,
        message: str,
        system_prompt: str,
        mode: str = "auto",
        instance_name: str | None = None,
        instance_type: str | None = None,
    ) -> str:
        return ""

    def get_cached_response(cache_key: str) -> str | None:  # type: ignore[misc]
        return None

    def response_cache_enabled() -> bool:  # type: ignore[misc]
        return False

    def set_cached_response(cache_key: str, response_text: str) -> None:  # type: ignore[misc]
        return None
