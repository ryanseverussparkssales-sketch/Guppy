"""Auth refresh endpoint — POST /auth/refresh.

Exchanges a valid (non-expired) JWT for a new one with a full 24-hour TTL.
No API-key re-presentation needed; the existing token is the credential.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from api.auth import create_access_token, verify_token
from api.routes.auth_token import TokenResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=TokenResponse)
async def refresh_token(user_id: str = Depends(verify_token)) -> TokenResponse:
    """Refresh a valid JWT for a new one with a full 24-hour TTL.

    The caller must present the current token in ``Authorization: Bearer <token>``.
    Expired tokens cannot be refreshed — the caller must re-authenticate via
    ``POST /auth/token`` with their API key.
    """
    new_token = create_access_token(sub=user_id)
    logger.info("POST /auth/refresh: new JWT issued for %s", user_id)
    return TokenResponse(access_token=new_token)
