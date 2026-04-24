"""
Centralized error code definitions for Guppy API.

Error codes follow pattern: [COMPONENT]_[CATEGORY]_[ERROR]
Example: AUTH_JWT_EXPIRED, CHAT_DB_NOTFOUND, API_TIMEOUT

All error responses include:
  - code: string (e.g., "AUTH_JWT_EXPIRED")
  - message: string (user-facing message)
  - statusCode: int (HTTP status code)
  - details: dict (optional technical details)
  - timestamp: ISO string
  - requestId: string (for tracing)
"""

from enum import Enum
from typing import Dict, Tuple


class ErrorCode(str, Enum):
    """
    Centralized error codes.
    Value = (http_status_code, user_message, category)
    """

    # ========== AUTHENTICATION (AUTH_*) ==========
    AUTH_JWT_NOT_CONFIGURED = "AUTH_JWT_NOT_CONFIGURED"
    AUTH_JWT_INVALID = "AUTH_JWT_INVALID"
    AUTH_JWT_EXPIRED = "AUTH_JWT_EXPIRED"
    AUTH_JWT_REFRESH_FAILED = "AUTH_JWT_REFRESH_FAILED"
    AUTH_TURNSTILE_FAILED = "AUTH_TURNSTILE_FAILED"
    AUTH_UNAUTHORIZED = "AUTH_UNAUTHORIZED"
    AUTH_FORBIDDEN = "AUTH_FORBIDDEN"

    # ========== DATABASE (DB_*) ==========
    DB_CONNECTION_FAILED = "DB_CONNECTION_FAILED"
    DB_QUERY_FAILED = "DB_QUERY_FAILED"
    DB_TRANSACTION_FAILED = "DB_TRANSACTION_FAILED"
    DB_INTEGRITY_VIOLATION = "DB_INTEGRITY_VIOLATION"
    DB_NOT_FOUND = "DB_NOT_FOUND"
    DB_CONSTRAINT_VIOLATION = "DB_CONSTRAINT_VIOLATION"

    # ========== VALIDATION (VALIDATION_*) ==========
    VALIDATION_INVALID_INPUT = "VALIDATION_INVALID_INPUT"
    VALIDATION_MISSING_FIELD = "VALIDATION_MISSING_FIELD"
    VALIDATION_INVALID_FORMAT = "VALIDATION_INVALID_FORMAT"
    VALIDATION_OUT_OF_RANGE = "VALIDATION_OUT_OF_RANGE"

    # ========== WORKSPACE (WORKSPACE_*) ==========
    WORKSPACE_NOT_FOUND = "WORKSPACE_NOT_FOUND"
    WORKSPACE_ALREADY_EXISTS = "WORKSPACE_ALREADY_EXISTS"
    WORKSPACE_CREATION_FAILED = "WORKSPACE_CREATION_FAILED"
    WORKSPACE_DELETION_FAILED = "WORKSPACE_DELETION_FAILED"
    WORKSPACE_ACCESS_DENIED = "WORKSPACE_ACCESS_DENIED"

    # ========== CHAT (CHAT_*) ==========
    CHAT_CONVERSATION_NOT_FOUND = "CHAT_CONVERSATION_NOT_FOUND"
    CHAT_MESSAGE_NOT_FOUND = "CHAT_MESSAGE_NOT_FOUND"
    CHAT_FAILED_TO_SEND = "CHAT_FAILED_TO_SEND"
    CHAT_AI_RESPONSE_FAILED = "CHAT_AI_RESPONSE_FAILED"
    CHAT_MESSAGE_TOO_LONG = "CHAT_MESSAGE_TOO_LONG"

    # ========== MODELS (MODEL_*) ==========
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
    MODEL_LOAD_FAILED = "MODEL_LOAD_FAILED"
    MODEL_INFERENCE_FAILED = "MODEL_INFERENCE_FAILED"
    MODEL_OUT_OF_MEMORY = "MODEL_OUT_OF_MEMORY"

    # ========== PROVIDER (PROVIDER_*) ==========
    PROVIDER_INVALID = "PROVIDER_INVALID"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    PROVIDER_API_FAILED = "PROVIDER_API_FAILED"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_CREDENTIAL_INVALID = "PROVIDER_CREDENTIAL_INVALID"
    PROVIDER_CREDENTIAL_EXPIRED = "PROVIDER_CREDENTIAL_EXPIRED"

    # ========== OLLAMA (OLLAMA_*) ==========
    OLLAMA_NOT_RUNNING = "OLLAMA_NOT_RUNNING"
    OLLAMA_CONNECTION_FAILED = "OLLAMA_CONNECTION_FAILED"
    OLLAMA_MODEL_NOT_FOUND = "OLLAMA_MODEL_NOT_FOUND"
    OLLAMA_INFERENCE_FAILED = "OLLAMA_INFERENCE_FAILED"
    OLLAMA_PULL_FAILED = "OLLAMA_PULL_FAILED"

    # ========== SETTINGS (SETTINGS_*) ==========
    SETTINGS_NOT_FOUND = "SETTINGS_NOT_FOUND"
    SETTINGS_UPDATE_FAILED = "SETTINGS_UPDATE_FAILED"
    SETTINGS_INVALID = "SETTINGS_INVALID"
    CREDENTIAL_STORAGE_FAILED = "CREDENTIAL_STORAGE_FAILED"

    # ========== LIBRARY (LIBRARY_*) ==========
    LIBRARY_ITEM_NOT_FOUND = "LIBRARY_ITEM_NOT_FOUND"
    LIBRARY_SAVE_FAILED = "LIBRARY_SAVE_FAILED"
    LIBRARY_LOAD_FAILED = "LIBRARY_LOAD_FAILED"
    LIBRARY_DELETE_FAILED = "LIBRARY_DELETE_FAILED"

    # ========== SYSTEM (SYSTEM_*) ==========
    SYSTEM_INTERNAL_ERROR = "SYSTEM_INTERNAL_ERROR"
    SYSTEM_SERVICE_UNAVAILABLE = "SYSTEM_SERVICE_UNAVAILABLE"
    SYSTEM_NOT_IMPLEMENTED = "SYSTEM_NOT_IMPLEMENTED"
    SYSTEM_TIMEOUT = "SYSTEM_TIMEOUT"
    SYSTEM_TOO_MANY_REQUESTS = "SYSTEM_TOO_MANY_REQUESTS"
    SYSTEM_MAINTENANCE = "SYSTEM_MAINTENANCE"


# Error metadata: code → (status_code, user_message, category, severity)
ERROR_METADATA: Dict[ErrorCode, Tuple[int, str, str, str]] = {
    # AUTHENTICATION
    ErrorCode.AUTH_JWT_NOT_CONFIGURED: (503, "Authentication not configured", "auth", "critical"),
    ErrorCode.AUTH_JWT_INVALID: (401, "Invalid authentication token", "auth", "warning"),
    ErrorCode.AUTH_JWT_EXPIRED: (401, "Your session has expired. Please sign in again.", "auth", "info"),
    ErrorCode.AUTH_JWT_REFRESH_FAILED: (401, "Failed to refresh session", "auth", "warning"),
    ErrorCode.AUTH_TURNSTILE_FAILED: (400, "CAPTCHA verification failed", "auth", "info"),
    ErrorCode.AUTH_UNAUTHORIZED: (401, "You are not authorized to access this resource", "auth", "warning"),
    ErrorCode.AUTH_FORBIDDEN: (403, "You don't have permission to perform this action", "auth", "warning"),

    # DATABASE
    ErrorCode.DB_CONNECTION_FAILED: (503, "Database connection failed. Please try again.", "database", "critical"),
    ErrorCode.DB_QUERY_FAILED: (500, "Database query failed", "database", "critical"),
    ErrorCode.DB_TRANSACTION_FAILED: (500, "Database transaction failed", "database", "critical"),
    ErrorCode.DB_INTEGRITY_VIOLATION: (400, "Data integrity violation", "database", "warning"),
    ErrorCode.DB_NOT_FOUND: (404, "Resource not found", "database", "info"),
    ErrorCode.DB_CONSTRAINT_VIOLATION: (400, "Constraint violation", "database", "warning"),

    # VALIDATION
    ErrorCode.VALIDATION_INVALID_INPUT: (400, "Invalid input provided", "validation", "info"),
    ErrorCode.VALIDATION_MISSING_FIELD: (400, "Required field is missing", "validation", "info"),
    ErrorCode.VALIDATION_INVALID_FORMAT: (400, "Invalid format", "validation", "info"),
    ErrorCode.VALIDATION_OUT_OF_RANGE: (400, "Value out of acceptable range", "validation", "info"),

    # WORKSPACE
    ErrorCode.WORKSPACE_NOT_FOUND: (404, "Workspace not found", "workspace", "info"),
    ErrorCode.WORKSPACE_ALREADY_EXISTS: (400, "Workspace already exists", "workspace", "info"),
    ErrorCode.WORKSPACE_CREATION_FAILED: (500, "Failed to create workspace", "workspace", "warning"),
    ErrorCode.WORKSPACE_DELETION_FAILED: (500, "Failed to delete workspace", "workspace", "warning"),
    ErrorCode.WORKSPACE_ACCESS_DENIED: (403, "You don't have access to this workspace", "workspace", "warning"),

    # CHAT
    ErrorCode.CHAT_CONVERSATION_NOT_FOUND: (404, "Conversation not found", "chat", "info"),
    ErrorCode.CHAT_MESSAGE_NOT_FOUND: (404, "Message not found", "chat", "info"),
    ErrorCode.CHAT_FAILED_TO_SEND: (500, "Failed to send message. Please try again.", "chat", "warning"),
    ErrorCode.CHAT_AI_RESPONSE_FAILED: (503, "AI service is currently unavailable", "chat", "warning"),
    ErrorCode.CHAT_MESSAGE_TOO_LONG: (400, "Message is too long", "chat", "info"),

    # MODELS
    ErrorCode.MODEL_NOT_FOUND: (404, "Model not found", "models", "info"),
    ErrorCode.MODEL_NOT_AVAILABLE: (503, "Model is not currently available", "models", "warning"),
    ErrorCode.MODEL_LOAD_FAILED: (500, "Failed to load model", "models", "warning"),
    ErrorCode.MODEL_INFERENCE_FAILED: (500, "Model inference failed", "models", "warning"),
    ErrorCode.MODEL_OUT_OF_MEMORY: (503, "Out of memory for model inference", "models", "warning"),

    # PROVIDER
    ErrorCode.PROVIDER_INVALID: (400, "Invalid provider", "provider", "info"),
    ErrorCode.PROVIDER_NOT_CONFIGURED: (400, "Provider not configured", "provider", "info"),
    ErrorCode.PROVIDER_API_FAILED: (502, "Provider API error", "provider", "warning"),
    ErrorCode.PROVIDER_RATE_LIMITED: (429, "Rate limit exceeded. Please wait before trying again.", "provider", "warning"),
    ErrorCode.PROVIDER_CREDENTIAL_INVALID: (400, "Invalid provider credentials", "provider", "warning"),
    ErrorCode.PROVIDER_CREDENTIAL_EXPIRED: (401, "Provider credentials have expired", "provider", "warning"),

    # OLLAMA
    ErrorCode.OLLAMA_NOT_RUNNING: (503, "Local AI service (Ollama) is not running", "ollama", "warning"),
    ErrorCode.OLLAMA_CONNECTION_FAILED: (503, "Cannot connect to local AI service", "ollama", "warning"),
    ErrorCode.OLLAMA_MODEL_NOT_FOUND: (404, "AI model not found locally", "ollama", "info"),
    ErrorCode.OLLAMA_INFERENCE_FAILED: (500, "AI inference failed", "ollama", "warning"),
    ErrorCode.OLLAMA_PULL_FAILED: (500, "Failed to download AI model", "ollama", "warning"),

    # SETTINGS
    ErrorCode.SETTINGS_NOT_FOUND: (404, "Settings not found", "settings", "info"),
    ErrorCode.SETTINGS_UPDATE_FAILED: (500, "Failed to update settings", "settings", "warning"),
    ErrorCode.SETTINGS_INVALID: (400, "Invalid settings", "settings", "info"),
    ErrorCode.CREDENTIAL_STORAGE_FAILED: (500, "Failed to store credentials", "settings", "warning"),

    # LIBRARY
    ErrorCode.LIBRARY_ITEM_NOT_FOUND: (404, "Library item not found", "library", "info"),
    ErrorCode.LIBRARY_SAVE_FAILED: (500, "Failed to save to library", "library", "warning"),
    ErrorCode.LIBRARY_LOAD_FAILED: (500, "Failed to load library", "library", "warning"),
    ErrorCode.LIBRARY_DELETE_FAILED: (500, "Failed to delete library item", "library", "warning"),

    # SYSTEM
    ErrorCode.SYSTEM_INTERNAL_ERROR: (500, "An unexpected error occurred", "system", "critical"),
    ErrorCode.SYSTEM_SERVICE_UNAVAILABLE: (503, "Service is temporarily unavailable. Please try again later.", "system", "warning"),
    ErrorCode.SYSTEM_NOT_IMPLEMENTED: (501, "This feature is not yet implemented", "system", "info"),
    ErrorCode.SYSTEM_TIMEOUT: (504, "Request timed out. Please try again.", "system", "warning"),
    ErrorCode.SYSTEM_TOO_MANY_REQUESTS: (429, "Too many requests. Please wait a moment before trying again.", "system", "warning"),
    ErrorCode.SYSTEM_MAINTENANCE: (503, "Service is under maintenance. Please try again later.", "system", "info"),
}


def get_error_status_code(code: ErrorCode) -> int:
    """Get HTTP status code for error code."""
    return ERROR_METADATA[code][0]


def get_error_message(code: ErrorCode) -> str:
    """Get user-friendly message for error code."""
    return ERROR_METADATA[code][1]


def get_error_category(code: ErrorCode) -> str:
    """Get error category for grouping/filtering."""
    return ERROR_METADATA[code][2]


def get_error_severity(code: ErrorCode) -> str:
    """Get error severity: 'info', 'warning', 'critical'."""
    return ERROR_METADATA[code][3]


# Retry policy by error code
RETRYABLE_ERRORS = {
    ErrorCode.DB_CONNECTION_FAILED,
    ErrorCode.DB_QUERY_FAILED,
    ErrorCode.SYSTEM_TIMEOUT,
    ErrorCode.SYSTEM_TOO_MANY_REQUESTS,
    ErrorCode.OLLAMA_NOT_RUNNING,
    ErrorCode.OLLAMA_CONNECTION_FAILED,
    ErrorCode.OLLAMA_INFERENCE_FAILED,
    ErrorCode.PROVIDER_RATE_LIMITED,
    ErrorCode.PROVIDER_API_FAILED,
    ErrorCode.CHAT_AI_RESPONSE_FAILED,
    ErrorCode.MODEL_NOT_AVAILABLE,
    ErrorCode.SYSTEM_SERVICE_UNAVAILABLE,
}

CIRCUIT_BREAKER_ERRORS = {
    ErrorCode.OLLAMA_NOT_RUNNING,
    ErrorCode.OLLAMA_CONNECTION_FAILED,
    ErrorCode.PROVIDER_API_FAILED,
    ErrorCode.SYSTEM_SERVICE_UNAVAILABLE,
}

# Errors that should trigger immediate user notification
ALERT_ERRORS = {
    ErrorCode.AUTH_JWT_EXPIRED,
    ErrorCode.AUTH_UNAUTHORIZED,
    ErrorCode.AUTH_FORBIDDEN,
    ErrorCode.PROVIDER_CREDENTIAL_INVALID,
    ErrorCode.PROVIDER_CREDENTIAL_EXPIRED,
}
