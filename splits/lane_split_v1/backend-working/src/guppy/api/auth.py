"""
guppy_api_auth.py — Authentication middleware for Guppy API
===========================================================

Handles Cloudflare Turnstile verification and JWT session management.
Provides dependency injection for FastAPI routes requiring authentication.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, ExpiredSignatureError, jwt
from pydantic import BaseModel

from src.guppy.paths import ensure_user_data_dir
from utils.env_bootstrap import load_env_file
from utils.db_utils import open_db
try:
    from utils import secret_store as _secret_store
    _SECRET_STORE_AVAILABLE = True
except ImportError:
    _secret_store = None  # type: ignore[assignment]
    _SECRET_STORE_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

load_env_file(override=True)

DEV_MODE = os.getenv("GUPPY_DEV_MODE", "").strip().lower() in {"1", "true", "yes", "on"}

# Prefer OS credential store; fall back to env-var so existing deployments
# continue to work with no migration step.
_env_jwt = os.getenv("GUPPY_JWT_SECRET", "").strip()
SECRET_KEY = (_secret_store.get_secret("jwt_secret", fallback=_env_jwt) or "").strip() if _SECRET_STORE_AVAILABLE else _env_jwt
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60  # 24 hours

TURNSTILE_SECRET = os.getenv("TURNSTILE_SECRET", "").strip()
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _refresh_runtime_config() -> None:
    """Reload env-backed auth settings for reloader and alternate import paths."""
    global DEV_MODE, SECRET_KEY, TURNSTILE_SECRET

    load_env_file(override=True)
    DEV_MODE = os.getenv("GUPPY_DEV_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    _env_jwt_now = os.getenv("GUPPY_JWT_SECRET", "").strip()
    SECRET_KEY = (
        (_secret_store.get_secret("jwt_secret", fallback=_env_jwt_now) or "").strip()
        if _SECRET_STORE_AVAILABLE
        else _env_jwt_now
    )
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

def _verify_token_credentials(credentials: Optional[HTTPAuthorizationCredentials]) -> str:
    """Verify bearer credentials and return the caller identity."""
    _refresh_runtime_config()
    if _is_placeholder_secret(SECRET_KEY):
        raise HTTPException(
            status_code=503,
            detail={"code": "auth_jwt_not_configured", "message": "JWT signing key is not configured"},
        )

    if not credentials:
        raise HTTPException(
            status_code=401,
            detail={"code": "auth_missing_bearer", "message": "Authentication required"},
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail={"code": "auth_invalid_payload", "message": "Invalid token payload"},
            )
        return user_id
    except ExpiredSignatureError as e:
        logger.warning("JWT verification failed [auth_token_expired]: %s", e)
        raise HTTPException(
            status_code=401,
            detail={"code": "auth_token_expired", "message": "Invalid or expired token"},
        )
    except JWTError as e:
        logger.warning("JWT verification failed [auth_token_invalid]: %s", e)
        raise HTTPException(
            status_code=401,
            detail={"code": "auth_token_invalid", "message": "Invalid or expired token"},
        )

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    _refresh_runtime_config()
    if _is_placeholder_secret(SECRET_KEY):
        raise RuntimeError("GUPPY_JWT_SECRET is not configured")

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify JWT token and return user ID."""
    return _verify_token_credentials(credentials)

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
_RATE_LIMIT_DB_PATH = (
    os.getenv("GUPPY_RATE_LIMIT_DB_PATH", "").strip()
    or str(ensure_user_data_dir() / "guppy_rate_limits.sqlite3")
)
_RATE_LIMIT_ROW_CAP = max(1000, int(os.getenv("GUPPY_RATE_LIMIT_ROW_CAP", "50000")))
_RATE_LIMIT_RETENTION_MINUTES = max(10, int(os.getenv("GUPPY_RATE_LIMIT_RETENTION_MINUTES", "1440")))
_RATE_LIMIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS rate_limit_events (
    principal TEXT NOT NULL,
    timestamp_utc TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_limit_principal_ts
    ON rate_limit_events(principal, timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_rate_limit_ts
    ON rate_limit_events(timestamp_utc);
"""


def _clear_rate_limit_backend() -> None:
    try:
        with open_db(_RATE_LIMIT_DB_PATH, schema_sql=_RATE_LIMIT_SCHEMA) as conn:
            conn.execute("DELETE FROM rate_limit_events")
            conn.commit()
    except Exception:
        pass


class _RateLimitStoreMirror(dict):
    """Compatibility mirror for tests; sqlite is the enforcement source of truth."""

    def clear(self) -> None:  # type: ignore[override]
        super().clear()
        _clear_rate_limit_backend()


rate_limit_store: dict = _RateLimitStoreMirror()

_POLL_PATHS = {
    "/status",
    "/metrics",
    "/startup/check",
    "/logs/recent",
    "/telemetry/query",
    "/telemetry/report",
}


def _get_int_env(name: str, default: int) -> int:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except Exception:
        return default


def _resolve_rate_limit_policy(request: Request) -> tuple[str, int, int]:
    """Return (bucket, max_requests, window_minutes) for this request path/method."""
    path = (getattr(getattr(request, "url", None), "path", "") or "").strip().lower()
    method = (getattr(request, "method", "") or "").strip().upper()

    # Launcher polls every few seconds; keep these in a separate, higher-cap bucket.
    if method == "GET" and path in _POLL_PATHS:
        return (
            "poll",
            _get_int_env("GUPPY_RATE_LIMIT_POLL_MAX", 6000),
            _get_int_env("GUPPY_RATE_LIMIT_POLL_WINDOW_MIN", 60),
        )

    # Chat should be protected, but must not be starved by status polling traffic.
    if path == "/chat" or path.startswith("/chat/"):
        return (
            "chat",
            _get_int_env("GUPPY_RATE_LIMIT_CHAT_MAX", 600),
            _get_int_env("GUPPY_RATE_LIMIT_CHAT_WINDOW_MIN", 60),
        )

    return (
        "default",
        _get_int_env("GUPPY_RATE_LIMIT_DEFAULT_MAX", 2000),
        _get_int_env("GUPPY_RATE_LIMIT_DEFAULT_WINDOW_MIN", 60),
    )

def check_rate_limit(user_id: str, max_requests: int = 100, window_minutes: int = 60) -> bool:
    """Check if user has exceeded rate limit across local processes."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=window_minutes)
    retention_start = now - timedelta(minutes=_RATE_LIMIT_RETENTION_MINUTES)
    timestamp_now = now.isoformat()
    timestamp_window_start = window_start.isoformat()
    timestamp_retention_start = retention_start.isoformat()

    with open_db(_RATE_LIMIT_DB_PATH, schema_sql=_RATE_LIMIT_SCHEMA) as conn:
        conn.execute(
            "DELETE FROM rate_limit_events WHERE timestamp_utc <= ?",
            (timestamp_retention_start,),
        )
        count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM rate_limit_events
                WHERE principal = ? AND timestamp_utc > ?
                """,
                (user_id, timestamp_window_start),
            ).fetchone()[0]
        )
        if count >= max_requests:
            conn.commit()
            return False

        conn.execute(
            "INSERT INTO rate_limit_events (principal, timestamp_utc) VALUES (?, ?)",
            (user_id, timestamp_now),
        )
        total_rows = int(
            conn.execute("SELECT COUNT(*) FROM rate_limit_events").fetchone()[0]
        )
        if total_rows > _RATE_LIMIT_ROW_CAP:
            rows_to_trim = total_rows - _RATE_LIMIT_ROW_CAP
            conn.execute(
                """
                DELETE FROM rate_limit_events
                WHERE rowid IN (
                    SELECT rowid
                    FROM rate_limit_events
                    ORDER BY timestamp_utc ASC
                    LIMIT ?
                )
                """,
                (rows_to_trim,),
            )
        conn.commit()

    # Keep a tiny compatibility mirror for tests and debug visibility.
    current = rate_limit_store.get(user_id, [])
    if isinstance(current, list):
        filtered = [req_time for req_time in current if req_time > window_start]
        filtered.append(now)
        rate_limit_store[user_id] = filtered[-max_requests:]
    else:
        rate_limit_store[user_id] = [now]
    return True

def _is_localhost_request(request: Request) -> bool:
    """Return True when the caller is on the same machine (loopback address)."""
    # Bypass only when there is no forwarding proxy header — a forwarded request
    # arriving with X-Forwarded-For is not a direct loopback call.
    if request.headers.get("X-Forwarded-For") or request.headers.get("CF-Connecting-IP"):
        return False
    host = (request.client.host if request.client else "") or ""
    return host in {"127.0.0.1", "::1", "localhost"}


def require_rate_limit(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependency to enforce rate limiting.

    Localhost requests (direct loopback, no proxy headers) are exempt from rate
    limiting, but not from bearer authentication. Rate limits apply only to
    externally forwarded requests so that tunnel/remote access is protected
    without blocking normal launcher usage.
    """
    user_id = _verify_token_credentials(credentials)
    if _is_localhost_request(request):
        logger.info("Localhost rate-limit bypass applied for %s", user_id)
        return user_id
    bucket, max_requests, window_minutes = _resolve_rate_limit_policy(request)
    bucketed_user = f"{user_id}:{bucket}"
    if not check_rate_limit(bucketed_user, max_requests=max_requests, window_minutes=window_minutes):
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
