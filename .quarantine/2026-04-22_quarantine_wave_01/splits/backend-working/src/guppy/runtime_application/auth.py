"""Authentication helpers owned by the runtime application seam."""

from __future__ import annotations

import os
from typing import Callable, Mapping


def _load_access_token_builder() -> Callable[[dict[str, str]], str] | None:
    try:
        from src.guppy.api.auth import create_access_token
    except Exception:
        return None
    return create_access_token


def build_local_bearer_token(
    *,
    env: Mapping[str, str] | None = None,
    create_token: Callable[[dict[str, str]], str] | None = None,
) -> tuple[str, str]:
    """Return the launcher's local bearer token plus a short source label."""
    env_map = env if env is not None else os.environ
    env_token = str(env_map.get("GUPPY_API_BEARER_TOKEN", "") or "").strip()
    if env_token:
        return env_token, "env_bearer_token"

    token_builder = create_token or _load_access_token_builder()
    if token_builder is None:
        return "", "jwt_helper_unavailable"

    try:
        return token_builder({"sub": "launcher_local"}), "jwt_helper"
    except Exception as exc:
        return "", f"jwt_helper_error:{type(exc).__name__}"
