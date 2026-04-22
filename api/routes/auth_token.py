"""Auth token endpoint — POST /auth/token.

Issues a signed JWT to a caller that presents a valid API key.
The API key is compared against ``GUPPY_API_KEY`` (Vercel project secret).
No local runtime imports.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.auth import _is_placeholder, create_access_token

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Models ─────────────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    api_key: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # seconds (24 h)
    schema_version: int = 1


# ── Helpers ────────────────────────────────────────────────────────────────────

def _configured_api_key() -> str:
    return os.environ.get("GUPPY_API_KEY", "").strip()


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("", response_model=TokenResponse)
async def issue_token(body: TokenRequest) -> TokenResponse:
    """Exchange a pre-shared API key for a signed JWT.

    The API key is stored in the ``GUPPY_API_KEY`` Vercel project secret.
    When the secret is not configured (dev/local) the endpoint is disabled
    so credentials are not accidentally issued against an unconfigured instance.
    """
    configured = _configured_api_key()

    if _is_placeholder(configured):
        logger.warning("POST /auth/token called but GUPPY_API_KEY is not configured")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "auth_not_configured",
                "message": "Token issuance is not configured on this instance",
            },
        )

    # Constant-time-safe comparison via hmac to guard against timing attacks.
    import hmac

    if not hmac.compare_digest(
        body.api_key.encode("utf-8"),
        configured.encode("utf-8"),
    ):
        logger.warning("POST /auth/token: invalid API key presented")
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_api_key", "message": "Invalid API key"},
        )

    token = create_access_token(sub="api-client")
    logger.info("POST /auth/token: JWT issued for api-client")
    return TokenResponse(access_token=token)
