"""
Error telemetry and structured logging for Guppy API.

Provides:
  - Structured logging with JSON format
  - Error tracking and aggregation
  - Performance metrics
  - Error telemetry export

Configuration:
  - Log files stored in: data/logs/api.log
  - Telemetry stored in: data/logs/telemetry.json
  - Rotating file handler (10MB per file, max 5 files)
"""

import logging
import logging.handlers
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from .error_codes import ErrorCode, get_error_severity, get_error_category

# ============ CONSTANTS ============

LOG_DIR = Path("data/logs")
API_LOG_FILE = LOG_DIR / "api.log"
TELEMETRY_FILE = LOG_DIR / "telemetry.json"

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ============ STRUCTURED LOGGING ============

class StructuredLogFormatter(logging.Formatter):
    """
    Formats log records as JSON with structured fields.

    Example output:
    {
      "timestamp": "2026-04-22T10:30:45.123Z",
      "level": "ERROR",
      "logger": "guppy.api",
      "message": "Chat message failed to send",
      "code": "CHAT_FAILED_TO_SEND",
      "statusCode": 500,
      "requestId": "abc12345",
      "userId": "user123",
      "extra": {...}
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "code"):
            log_data["code"] = record.code
        if hasattr(record, "status"):
            log_data["statusCode"] = record.status
        if hasattr(record, "request_id"):
            log_data["requestId"] = record.request_id
        if hasattr(record, "user_id"):
            log_data["userId"] = record.user_id
        if hasattr(record, "endpoint"):
            log_data["endpoint"] = record.endpoint

        # Add any other extra fields
        if record.args:
            log_data["args"] = record.args

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
            }

        return json.dumps(log_data)


# ============ LOGGER SETUP ============

def setup_api_logging(level: str = "INFO"):
    """
    Configure structured logging for Guppy API.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logger = logging.getLogger("guppy.api")
    logger.setLevel(level)

    # Clear any existing handlers
    logger.handlers = []

    # Create rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        API_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(StructuredLogFormatter())

    logger.addHandler(file_handler)

    # Also add console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(StructuredLogFormatter())
    logger.addHandler(console_handler)

    logger.info("API logging initialized")


# ============ ERROR TELEMETRY ============

class ErrorTelemetry:
    """
    Tracks and exports error telemetry.

    Usage:
        telemetry = ErrorTelemetry()
        telemetry.track_error(ErrorCode.CHAT_FAILED_TO_SEND, 500)
        stats = telemetry.get_stats()
    """

    def __init__(self):
        self.errors: Dict[str, int] = {}
        self.error_details: Dict[str, Any] = {}
        self.last_errors = []  # Keep last 100 errors for debugging

    def track_error(
        self,
        code: ErrorCode,
        status_code: int,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        """Track an error occurrence."""
        code_str = code.value
        category = get_error_category(code)
        severity = get_error_severity(code)

        # Count errors by code
        if code_str not in self.errors:
            self.errors[code_str] = 0
        self.errors[code_str] += 1

        # Store error details
        if code_str not in self.error_details:
            self.error_details[code_str] = {
                "code": code_str,
                "category": category,
                "severity": severity,
                "statusCode": status_code,
                "count": 0,
                "lastOccurred": None,
                "endpoints": {},
            }

        self.error_details[code_str]["count"] += 1
        self.error_details[code_str]["lastOccurred"] = datetime.now(timezone.utc).isoformat()

        # Track by endpoint
        if endpoint:
            if endpoint not in self.error_details[code_str]["endpoints"]:
                self.error_details[code_str]["endpoints"][endpoint] = 0
            self.error_details[code_str]["endpoints"][endpoint] += 1

        # Keep last 100 errors for debugging
        self.last_errors.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "code": code_str,
                "statusCode": status_code,
                "endpoint": endpoint,
                "userId": user_id,
                "requestId": request_id,
                "details": details,
            }
        )
        if len(self.last_errors) > 100:
            self.last_errors = self.last_errors[-100:]

    def get_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        return {
            "totalErrors": sum(self.errors.values()),
            "uniqueCodes": len(self.errors),
            "byCode": self.error_details,
            "lastErrors": self.last_errors[-10:],  # Last 10 for quick review
        }

    def export_telemetry(self) -> str:
        """Export telemetry as JSON string."""
        return json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stats": self.get_stats(),
            },
            indent=2,
        )

    def save_telemetry(self):
        """Save telemetry to file."""
        try:
            with open(TELEMETRY_FILE, "w") as f:
                f.write(self.export_telemetry())
        except Exception as e:
            logging.getLogger("guppy.api").error(f"Failed to save telemetry: {e}")


# ============ GLOBAL TELEMETRY INSTANCE ============

_global_telemetry: Optional[ErrorTelemetry] = None


def get_telemetry() -> ErrorTelemetry:
    """Get the global telemetry instance."""
    global _global_telemetry
    if _global_telemetry is None:
        _global_telemetry = ErrorTelemetry()
    return _global_telemetry


# ============ LOGGING HELPERS ============

def log_error(
    code: ErrorCode,
    message: str,
    request_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    user_id: Optional[str] = None,
    details: Optional[Dict] = None,
):
    """
    Log an error with telemetry tracking.

    Usage:
        from src.guppy.api.telemetry import log_error
        from src.guppy.api.error_codes import ErrorCode

        log_error(
            ErrorCode.CHAT_FAILED_TO_SEND,
            "Failed to get AI response",
            request_id="abc12345",
            endpoint="/api/chat",
            user_id="user123"
        )
    """
    logger = logging.getLogger("guppy.api")
    status_code = 500  # Default, should be passed in if needed

    # Track in telemetry
    get_telemetry().track_error(
        code,
        status_code,
        endpoint=endpoint,
        user_id=user_id,
        request_id=request_id,
        details=details,
    )

    # Log with extra context
    severity = get_error_severity(code)
    if severity == "critical":
        logger.critical(message, extra={
            "code": code.value,
            "request_id": request_id,
            "endpoint": endpoint,
            "user_id": user_id,
        })
    elif severity == "warning":
        logger.warning(message, extra={
            "code": code.value,
            "request_id": request_id,
            "endpoint": endpoint,
        })
    else:
        logger.info(message, extra={
            "code": code.value,
            "request_id": request_id,
        })


# ============ MIDDLEWARE FOR TELEMETRY ============

async def telemetry_middleware(request, call_next):
    """
    Middleware that tracks request telemetry.
    Must be used with request_id_middleware.
    """
    # Just pass through; error tracking happens in error_handler
    response = await call_next(request)
    return response


# ============ INITIALIZATION ============

# Initialize logging on module load
setup_api_logging()
