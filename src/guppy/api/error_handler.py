"""
Central error handling middleware for Guppy API.

All API errors are converted to structured JSON responses with:
  - code: ErrorCode (e.g., "AUTH_JWT_EXPIRED")
  - message: str (user-friendly message)
  - statusCode: int (HTTP status)
  - timestamp: ISO string
  - requestId: str (for tracing)
  - details: dict (optional technical details for debugging)

Usage:
  @router.get("/some/endpoint")
  @api_error_handler
  async def some_endpoint():
      # Raise APIErrorResponse to return structured error
      raise APIErrorResponse(ErrorCode.CHAT_NOT_FOUND, details={"conv_id": "123"})

      # Or convert caught exceptions
      try:
          ...
      except ValueError as e:
          raise APIErrorResponse(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
"""

import logging
import traceback
from functools import wraps
from typing import Optional, Dict, Any, Callable
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import sqlalchemy.exc

from .error_codes import ErrorCode, ERROR_METADATA, get_error_status_code, get_error_message

logger = logging.getLogger(__name__)


# ============ CUSTOM EXCEPTIONS ============

class APIErrorResponse(Exception):
    """
    Structured API error to be returned to clients.

    Usage:
        raise APIErrorResponse(ErrorCode.CHAT_NOT_FOUND, "Conversation not found", {"conv_id": "123"})
    """

    def __init__(
        self,
        code: ErrorCode,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.code = code
        self.message = message or get_error_message(code)
        self.details = details or {}
        self.status_code = get_error_status_code(code)
        super().__init__(self.message)


# ============ ERROR RESPONSE FORMATTING ============

def format_error_response(
    code: ErrorCode,
    message: str,
    status_code: int,
    request_id: str,
    details: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Format a structured error response."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    response = {
        "code": code.value,
        "message": message,
        "statusCode": status_code,
        "timestamp": timestamp,
        "requestId": request_id,
    }

    # Only include details if present (don't expose in production)
    if details:
        response["details"] = details

    return response


# ============ EXCEPTION MAPPING ============

def map_exception_to_error_code(error: Exception, request_id: str) -> tuple[ErrorCode, str, Optional[Dict]]:
    """
    Map caught exceptions to ErrorCode and log appropriately.

    Returns:
        (error_code, message, details_dict)
    """
    details = None

    # Database errors
    if isinstance(error, sqlalchemy.exc.IntegrityError):
        logger.warning(f"[{request_id}] Database integrity violation: {str(error)}")
        return ErrorCode.DB_INTEGRITY_VIOLATION, "Database integrity violation", {"error": str(error)[:100]}

    if isinstance(error, sqlalchemy.exc.OperationalError):
        logger.error(f"[{request_id}] Database operational error: {str(error)}")
        return ErrorCode.DB_CONNECTION_FAILED, "Database connection failed", None

    if isinstance(error, sqlalchemy.exc.DatabaseError):
        logger.error(f"[{request_id}] Database error: {str(error)}")
        return ErrorCode.DB_QUERY_FAILED, "Database query failed", None

    # Validation errors (from Pydantic)
    if isinstance(error, RequestValidationError):
        logger.info(f"[{request_id}] Validation error: {error.error_count()} errors")
        error_details = [
            {
                "field": ".".join(str(x) for x in e["loc"]),
                "error": e["msg"],
            }
            for e in error.errors()
        ]
        return ErrorCode.VALIDATION_INVALID_INPUT, "Invalid input provided", {"errors": error_details}

    # Value errors
    if isinstance(error, ValueError):
        logger.info(f"[{request_id}] Value error: {str(error)}")
        return ErrorCode.VALIDATION_INVALID_INPUT, str(error), None

    # Key errors (missing required fields)
    if isinstance(error, KeyError):
        logger.info(f"[{request_id}] Missing field: {str(error)}")
        return ErrorCode.VALIDATION_MISSING_FIELD, f"Missing field: {str(error)}", None

    # Type errors
    if isinstance(error, TypeError):
        logger.warning(f"[{request_id}] Type error: {str(error)}")
        return ErrorCode.VALIDATION_INVALID_FORMAT, "Invalid format", None

    # Timeout errors
    if isinstance(error, TimeoutError):
        logger.warning(f"[{request_id}] Request timeout")
        return ErrorCode.SYSTEM_TIMEOUT, "Request timed out", None

    # Generic errors
    logger.error(f"[{request_id}] Unhandled exception: {type(error).__name__}: {str(error)}")
    return ErrorCode.SYSTEM_INTERNAL_ERROR, "An unexpected error occurred", None


# ============ DECORATOR FOR ROUTE HANDLERS ============

def api_error_handler(func: Callable) -> Callable:
    """
    Decorator for async FastAPI route handlers that converts exceptions
    to structured error responses.

    Usage:
        @router.get("/endpoint")
        @api_error_handler
        async def my_endpoint():
            # Any exception here is caught and formatted
            pass
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request_id = str(uuid4())[:8]

        try:
            # Call the actual route handler
            result = await func(*args, **kwargs)
            return result

        except APIErrorResponse as e:
            # Structured error we raised deliberately
            logger.warning(
                f"[{request_id}] API error {e.code.value}: {e.message}",
                extra={"code": e.code.value, "status": e.status_code},
            )
            response = format_error_response(
                e.code,
                e.message,
                e.status_code,
                request_id,
                e.details if e.details else None,
            )
            return JSONResponse(response, status_code=e.status_code)

        except HTTPException as e:
            # FastAPI HTTPException (from auth, etc.)
            logger.warning(f"[{request_id}] HTTP exception {e.status_code}: {e.detail}")

            # Try to extract error code if available
            code = ErrorCode.SYSTEM_INTERNAL_ERROR
            message = str(e.detail) if e.detail else "An error occurred"

            if isinstance(e.detail, dict) and "code" in e.detail:
                try:
                    code = ErrorCode(e.detail["code"])
                    message = e.detail.get("message", get_error_message(code))
                except ValueError:
                    pass

            response = format_error_response(
                code,
                message,
                e.status_code,
                request_id,
            )
            return JSONResponse(response, status_code=e.status_code)

        except Exception as e:
            # Unhandled exception - map to error code
            code, message, details = map_exception_to_error_code(e, request_id)
            status_code = get_error_status_code(code)

            # Log full traceback for debugging
            logger.error(
                f"[{request_id}] Unhandled exception: {traceback.format_exc()}",
                extra={"code": code.value, "status": status_code},
            )

            response = format_error_response(
                code,
                message,
                status_code,
                request_id,
                details,
            )
            return JSONResponse(response, status_code=status_code)

    return wrapper


# ============ GLOBAL EXCEPTION HANDLERS ============

def register_exception_handlers(app):
    """
    Register global exception handlers with FastAPI app.

    Usage in main API server setup:
        from src.guppy.api.error_handler import register_exception_handlers

        app = FastAPI()
        register_exception_handlers(app)
    """

    @app.exception_handler(APIErrorResponse)
    async def api_error_handler_global(request, exc: APIErrorResponse):
        request_id = getattr(request.state, "request_id", str(uuid4())[:8])
        response = format_error_response(
            exc.code,
            exc.message,
            exc.status_code,
            request_id,
            exc.details if exc.details else None,
        )
        return JSONResponse(response, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc: Exception):
        request_id = getattr(request.state, "request_id", str(uuid4())[:8])

        code, message, details = map_exception_to_error_code(exc, request_id)
        status_code = get_error_status_code(code)

        logger.error(
            f"[{request_id}] Unhandled exception: {traceback.format_exc()}",
            extra={"code": code.value, "status": status_code},
        )

        response = format_error_response(
            code,
            message,
            status_code,
            request_id,
            details,
        )
        return JSONResponse(response, status_code=status_code)


# ============ MIDDLEWARE FOR REQUEST ID TRACKING ============

async def request_id_middleware(request, call_next):
    """
    Middleware that adds a unique request ID to each request.
    This ID is used for tracing and logging.
    """
    request_id = str(uuid4())[:8]
    request.state.request_id = request_id

    # Add request ID to response headers for client tracking
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response
