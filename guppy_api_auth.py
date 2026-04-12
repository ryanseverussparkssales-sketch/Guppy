"""
guppy_api_auth.py — Authentication middleware for Guppy API
===========================================================

Handles Cloudflare Turnstile verification and JWT session management.
Provides dependency injection for FastAPI routes requiring authentication.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, ExpiredSignatureError, jwt
from pydantic import BaseModel

from utils.env_bootstrap import load_env_file

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

load_env_file(override=True)

DEV_MODE = os.getenv("GUPPY_DEV_MODE", "").strip().lower() in {"1", "true", "yes", "on"}

SECRET_KEY = os.getenv("GUPPY_JWT_SECRET", "").strip()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60  # 24 hours

TURNSTILE_SECRET = os.getenv("TURNSTILE_SECRET", "").strip()
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _refresh_runtime_config() -> None:
    """Reload env-backed auth settings for reloader and alternate import paths."""
    global DEV_MODE, SECRET_KEY, TURNSTILE_SECRET

    load_env_file(override=True)
    DEV_MODE = os.getenv("GUPPY_DEV_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    SECRET_KEY = os.getenv("GUPPY_JWT_SECRET", "").strip()
    TURNSTILE_SECRET = os.getenv("TURNSTILE_SECRET", "").strip()


def _is_placeholder_secret(value: str) -> bool:
    lowered = (value or "").strip().lower()
    return lowered in {
        "",
        "your-secret-key-change-in-production",
        "your-turnstile-secret",
        "changeme",
        "replace-me",
    }

# ── Models ────────────────────────────────────────────────────────────────────

class TurnstileToken(BaseModel):
    token: str

class TokenData(BaseModel):
    user_id: Optional[str] = None

# ── Security ──────────────────────────────────────────────────────────────────

security = HTTPBearer(auto_error=False)

# ── JWT Functions ─────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    _refresh_runtime_config()
    if _is_placeholder_secret(SECRET_KEY):
        raise RuntimeError("GUPPY_JWT_SECRET is not configured")

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify JWT token and return user ID."""
    _refresh_runtime_config()
    if _is_placeholder_secret(SECRET_KEY):
        raise HTTPException(status_code=503, detail="JWT signing key is not configured")

    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def get_token_expiry(token: str) -> Optional[datetime]:
    """Get token expiry time without full verification."""
    _refresh_runtime_config()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp)
    except JWTError:
        pass
    return None

# ── Turnstile Functions ───────────────────────────────────────────────────────

async def verify_turnstile_token(token: str) -> bool:
    """Verify Cloudflare Turnstile token with siteverify API."""
    _refresh_runtime_config()
    if _is_placeholder_secret(TURNSTILE_SECRET):
        if DEV_MODE:
            logger.warning("TURNSTILE_SECRET not set - allowing all tokens in development mode")
            return True
        logger.error("TURNSTILE_SECRET not configured in strict mode")
        return False

    if not token or len(token.strip()) == 0:
        return False

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                TURNSTILE_VERIFY_URL,
                data={
                    "secret": TURNSTILE_SECRET,
                    "response": token
                }
            )

            if response.status_code != 200:
                logger.error(f"Turnstile API error: {response.status_code}")
                return False

            result = response.json()

            if not result.get("success", False):
                logger.warning(f"Turnstile verification failed: {result.get('error-codes', [])}")
                return False

            # Log successful verification
            logger.info("Turnstile token verified successfully")
            return True

        except httpx.TimeoutException:
            logger.error("Turnstile verification timed out")
            return False
        except Exception as e:
            logger.error(f"Turnstile verification error: {e}")
            return False

# ── Middleware Functions ──────────────────────────────────────────────────────

async def require_turnstile(request: Request) -> str:
    """Middleware to require and verify Turnstile token for first-time auth."""
    # Check for Turnstile token in header or form data
    turnstile_token = None

    # Check Authorization header (custom format for Turnstile)
    auth_header = request.headers.get("X-Turnstile-Token")
    if auth_header:
        turnstile_token = auth_header
    else:
        # Check form data
        form_data = await request.form()
        turnstile_token = form_data.get("cf-turnstile-response")

    if not turnstile_token:
        raise HTTPException(
            status_code=400,
            detail="Turnstile verification required. Please complete the captcha."
        )

    if not await verify_turnstile_token(turnstile_token):
        raise HTTPException(
            status_code=400,
            detail="Turnstile verification failed. Please try again."
        )

    return turnstile_token

# ── Rate Limiting (Basic) ─────────────────────────────────────────────────────

# Simple in-memory rate limiting (use Redis/external service for production)
rate_limit_store: dict = {}

def check_rate_limit(user_id: str, max_requests: int = 100, window_minutes: int = 60) -> bool:
    """Check if user has exceeded rate limit."""
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=window_minutes)

    if user_id not in rate_limit_store:
        rate_limit_store[user_id] = []

    # Clean old requests
    rate_limit_store[user_id] = [
        req_time for req_time in rate_limit_store[user_id]
        if req_time > window_start
    ]

    # Check limit
    if len(rate_limit_store[user_id]) >= max_requests:
        return False

    # Add current request
    rate_limit_store[user_id].append(now)
    return True

def require_rate_limit(user_id: str = Depends(verify_token)):
    """Dependency to enforce rate limiting."""
    if not check_rate_limit(user_id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    return user_id


def require_auth_rate_limit(request: Request):
    """Rate-limit auth verification by client IP to reduce abuse."""
    client_ip = (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    key = f"auth:{client_ip or 'unknown'}"
    if not check_rate_limit(key, max_requests=30, window_minutes=10):
        raise HTTPException(status_code=429, detail="Too many auth attempts. Please try again later.")
    return key

# ── Utility Functions ─────────────────────────────────────────────────────────

def get_token_data(token: str) -> Optional[TokenData]:
    """Extract data from JWT token without verification."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        return TokenData(user_id=payload.get("sub"))
    except JWTError:
        return None

def is_token_expired(token: str) -> bool:
    """Check if JWT token is expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return False  # If decode succeeds, token is valid
    except ExpiredSignatureError:
        return True
    except JWTError:
        return True

# ── Development Helpers ──────────────────────────────────────────────────────

def create_development_token(user_id: str = "dev_user") -> str:
    """Create a development token that bypasses Turnstile (for testing only)."""
    _refresh_runtime_config()
    return create_access_token({"sub": user_id})

def validate_environment():
    """Validate that required environment variables are set."""
    _refresh_runtime_config()
    missing = []
    if _is_placeholder_secret(SECRET_KEY):
        missing.append("GUPPY_JWT_SECRET")
    if _is_placeholder_secret(TURNSTILE_SECRET):
        missing.append("TURNSTILE_SECRET")

    if missing:
        if DEV_MODE:
            logger.warning(f"Missing environment variables in dev mode: {', '.join(missing)}")
            logger.warning("Development mode enabled (GUPPY_DEV_MODE=1); strict checks are bypassed.")
        else:
            raise RuntimeError(
                f"Missing required environment variables in strict mode: {', '.join(missing)}. "
                "Set GUPPY_DEV_MODE=1 only for local development."
            )

    return len(missing) == 0