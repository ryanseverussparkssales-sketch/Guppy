/**
 * Frontend Error Codes
 *
 * Mirrors backend error codes for consistency.
 * Used for error categorization, recovery logic, and telemetry.
 */

export enum ErrorCode {
  // ========== AUTHENTICATION (AUTH_*) ==========
  AUTH_JWT_NOT_CONFIGURED = 'AUTH_JWT_NOT_CONFIGURED',
  AUTH_JWT_INVALID = 'AUTH_JWT_INVALID',
  AUTH_JWT_EXPIRED = 'AUTH_JWT_EXPIRED',
  AUTH_JWT_REFRESH_FAILED = 'AUTH_JWT_REFRESH_FAILED',
  AUTH_TURNSTILE_FAILED = 'AUTH_TURNSTILE_FAILED',
  AUTH_UNAUTHORIZED = 'AUTH_UNAUTHORIZED',
  AUTH_FORBIDDEN = 'AUTH_FORBIDDEN',

  // ========== DATABASE (DB_*) ==========
  DB_CONNECTION_FAILED = 'DB_CONNECTION_FAILED',
  DB_QUERY_FAILED = 'DB_QUERY_FAILED',
  DB_TRANSACTION_FAILED = 'DB_TRANSACTION_FAILED',
  DB_INTEGRITY_VIOLATION = 'DB_INTEGRITY_VIOLATION',
  DB_NOT_FOUND = 'DB_NOT_FOUND',
  DB_CONSTRAINT_VIOLATION = 'DB_CONSTRAINT_VIOLATION',

  // ========== VALIDATION (VALIDATION_*) ==========
  VALIDATION_INVALID_INPUT = 'VALIDATION_INVALID_INPUT',
  VALIDATION_MISSING_FIELD = 'VALIDATION_MISSING_FIELD',
  VALIDATION_INVALID_FORMAT = 'VALIDATION_INVALID_FORMAT',
  VALIDATION_OUT_OF_RANGE = 'VALIDATION_OUT_OF_RANGE',

  // ========== WORKSPACE (WORKSPACE_*) ==========
  WORKSPACE_NOT_FOUND = 'WORKSPACE_NOT_FOUND',
  WORKSPACE_ALREADY_EXISTS = 'WORKSPACE_ALREADY_EXISTS',
  WORKSPACE_CREATION_FAILED = 'WORKSPACE_CREATION_FAILED',
  WORKSPACE_DELETION_FAILED = 'WORKSPACE_DELETION_FAILED',
  WORKSPACE_ACCESS_DENIED = 'WORKSPACE_ACCESS_DENIED',

  // ========== CHAT (CHAT_*) ==========
  CHAT_CONVERSATION_NOT_FOUND = 'CHAT_CONVERSATION_NOT_FOUND',
  CHAT_MESSAGE_NOT_FOUND = 'CHAT_MESSAGE_NOT_FOUND',
  CHAT_FAILED_TO_SEND = 'CHAT_FAILED_TO_SEND',
  CHAT_AI_RESPONSE_FAILED = 'CHAT_AI_RESPONSE_FAILED',
  CHAT_MESSAGE_TOO_LONG = 'CHAT_MESSAGE_TOO_LONG',

  // ========== MODELS (MODEL_*) ==========
  MODEL_NOT_FOUND = 'MODEL_NOT_FOUND',
  MODEL_NOT_AVAILABLE = 'MODEL_NOT_AVAILABLE',
  MODEL_LOAD_FAILED = 'MODEL_LOAD_FAILED',
  MODEL_INFERENCE_FAILED = 'MODEL_INFERENCE_FAILED',
  MODEL_OUT_OF_MEMORY = 'MODEL_OUT_OF_MEMORY',

  // ========== PROVIDER (PROVIDER_*) ==========
  PROVIDER_INVALID = 'PROVIDER_INVALID',
  PROVIDER_NOT_CONFIGURED = 'PROVIDER_NOT_CONFIGURED',
  PROVIDER_API_FAILED = 'PROVIDER_API_FAILED',
  PROVIDER_RATE_LIMITED = 'PROVIDER_RATE_LIMITED',
  PROVIDER_CREDENTIAL_INVALID = 'PROVIDER_CREDENTIAL_INVALID',
  PROVIDER_CREDENTIAL_EXPIRED = 'PROVIDER_CREDENTIAL_EXPIRED',

  // ========== OLLAMA (OLLAMA_*) ==========
  OLLAMA_NOT_RUNNING = 'OLLAMA_NOT_RUNNING',
  OLLAMA_CONNECTION_FAILED = 'OLLAMA_CONNECTION_FAILED',
  OLLAMA_MODEL_NOT_FOUND = 'OLLAMA_MODEL_NOT_FOUND',
  OLLAMA_INFERENCE_FAILED = 'OLLAMA_INFERENCE_FAILED',
  OLLAMA_PULL_FAILED = 'OLLAMA_PULL_FAILED',

  // ========== SETTINGS (SETTINGS_*) ==========
  SETTINGS_NOT_FOUND = 'SETTINGS_NOT_FOUND',
  SETTINGS_UPDATE_FAILED = 'SETTINGS_UPDATE_FAILED',
  SETTINGS_INVALID = 'SETTINGS_INVALID',
  CREDENTIAL_STORAGE_FAILED = 'CREDENTIAL_STORAGE_FAILED',

  // ========== LIBRARY (LIBRARY_*) ==========
  LIBRARY_ITEM_NOT_FOUND = 'LIBRARY_ITEM_NOT_FOUND',
  LIBRARY_SAVE_FAILED = 'LIBRARY_SAVE_FAILED',
  LIBRARY_LOAD_FAILED = 'LIBRARY_LOAD_FAILED',
  LIBRARY_DELETE_FAILED = 'LIBRARY_DELETE_FAILED',

  // ========== SYSTEM (SYSTEM_*) ==========
  SYSTEM_INTERNAL_ERROR = 'SYSTEM_INTERNAL_ERROR',
  SYSTEM_SERVICE_UNAVAILABLE = 'SYSTEM_SERVICE_UNAVAILABLE',
  SYSTEM_NOT_IMPLEMENTED = 'SYSTEM_NOT_IMPLEMENTED',
  SYSTEM_TIMEOUT = 'SYSTEM_TIMEOUT',
  SYSTEM_TOO_MANY_REQUESTS = 'SYSTEM_TOO_MANY_REQUESTS',
  SYSTEM_MAINTENANCE = 'SYSTEM_MAINTENANCE',

  // ========== CLIENT-SIDE ERRORS (CLIENT_*) ==========
  CLIENT_NETWORK_ERROR = 'CLIENT_NETWORK_ERROR',
  CLIENT_REQUEST_TIMEOUT = 'CLIENT_REQUEST_TIMEOUT',
  CLIENT_OFFLINE = 'CLIENT_OFFLINE',
  CLIENT_PARSE_ERROR = 'CLIENT_PARSE_ERROR',
  CLIENT_CACHE_MISS = 'CLIENT_CACHE_MISS',
}

export interface ErrorMetadata {
  statusCode: number
  userMessage: string
  category: string
  severity: 'info' | 'warning' | 'critical'
}

// Error metadata: mirrors backend ERROR_METADATA
export const ERROR_METADATA: Record<ErrorCode, ErrorMetadata> = {
  // AUTHENTICATION
  [ErrorCode.AUTH_JWT_NOT_CONFIGURED]: {
    statusCode: 503,
    userMessage: 'Authentication not configured',
    category: 'auth',
    severity: 'critical',
  },
  [ErrorCode.AUTH_JWT_INVALID]: {
    statusCode: 401,
    userMessage: 'Invalid authentication token',
    category: 'auth',
    severity: 'warning',
  },
  [ErrorCode.AUTH_JWT_EXPIRED]: {
    statusCode: 401,
    userMessage: 'Your session has expired. Please sign in again.',
    category: 'auth',
    severity: 'info',
  },
  [ErrorCode.AUTH_JWT_REFRESH_FAILED]: {
    statusCode: 401,
    userMessage: 'Failed to refresh session',
    category: 'auth',
    severity: 'warning',
  },
  [ErrorCode.AUTH_TURNSTILE_FAILED]: {
    statusCode: 400,
    userMessage: 'CAPTCHA verification failed',
    category: 'auth',
    severity: 'info',
  },
  [ErrorCode.AUTH_UNAUTHORIZED]: {
    statusCode: 401,
    userMessage: 'You are not authorized to access this resource',
    category: 'auth',
    severity: 'warning',
  },
  [ErrorCode.AUTH_FORBIDDEN]: {
    statusCode: 403,
    userMessage: "You don't have permission to perform this action",
    category: 'auth',
    severity: 'warning',
  },

  // DATABASE
  [ErrorCode.DB_CONNECTION_FAILED]: {
    statusCode: 503,
    userMessage: 'Database connection failed. Please try again.',
    category: 'database',
    severity: 'critical',
  },
  [ErrorCode.DB_QUERY_FAILED]: {
    statusCode: 500,
    userMessage: 'Database query failed',
    category: 'database',
    severity: 'critical',
  },
  [ErrorCode.DB_TRANSACTION_FAILED]: {
    statusCode: 500,
    userMessage: 'Database transaction failed',
    category: 'database',
    severity: 'critical',
  },
  [ErrorCode.DB_INTEGRITY_VIOLATION]: {
    statusCode: 400,
    userMessage: 'Data integrity violation',
    category: 'database',
    severity: 'warning',
  },
  [ErrorCode.DB_NOT_FOUND]: {
    statusCode: 404,
    userMessage: 'Resource not found',
    category: 'database',
    severity: 'info',
  },
  [ErrorCode.DB_CONSTRAINT_VIOLATION]: {
    statusCode: 400,
    userMessage: 'Constraint violation',
    category: 'database',
    severity: 'warning',
  },

  // VALIDATION
  [ErrorCode.VALIDATION_INVALID_INPUT]: {
    statusCode: 400,
    userMessage: 'Invalid input provided',
    category: 'validation',
    severity: 'info',
  },
  [ErrorCode.VALIDATION_MISSING_FIELD]: {
    statusCode: 400,
    userMessage: 'Required field is missing',
    category: 'validation',
    severity: 'info',
  },
  [ErrorCode.VALIDATION_INVALID_FORMAT]: {
    statusCode: 400,
    userMessage: 'Invalid format',
    category: 'validation',
    severity: 'info',
  },
  [ErrorCode.VALIDATION_OUT_OF_RANGE]: {
    statusCode: 400,
    userMessage: 'Value out of acceptable range',
    category: 'validation',
    severity: 'info',
  },

  // WORKSPACE
  [ErrorCode.WORKSPACE_NOT_FOUND]: {
    statusCode: 404,
    userMessage: 'Workspace not found',
    category: 'workspace',
    severity: 'info',
  },
  [ErrorCode.WORKSPACE_ALREADY_EXISTS]: {
    statusCode: 400,
    userMessage: 'Workspace already exists',
    category: 'workspace',
    severity: 'info',
  },
  [ErrorCode.WORKSPACE_CREATION_FAILED]: {
    statusCode: 500,
    userMessage: 'Failed to create workspace',
    category: 'workspace',
    severity: 'warning',
  },
  [ErrorCode.WORKSPACE_DELETION_FAILED]: {
    statusCode: 500,
    userMessage: 'Failed to delete workspace',
    category: 'workspace',
    severity: 'warning',
  },
  [ErrorCode.WORKSPACE_ACCESS_DENIED]: {
    statusCode: 403,
    userMessage: "You don't have access to this workspace",
    category: 'workspace',
    severity: 'warning',
  },

  // CHAT
  [ErrorCode.CHAT_CONVERSATION_NOT_FOUND]: {
    statusCode: 404,
    userMessage: 'Conversation not found',
    category: 'chat',
    severity: 'info',
  },
  [ErrorCode.CHAT_MESSAGE_NOT_FOUND]: {
    statusCode: 404,
    userMessage: 'Message not found',
    category: 'chat',
    severity: 'info',
  },
  [ErrorCode.CHAT_FAILED_TO_SEND]: {
    statusCode: 500,
    userMessage: 'Failed to send message. Please try again.',
    category: 'chat',
    severity: 'warning',
  },
  [ErrorCode.CHAT_AI_RESPONSE_FAILED]: {
    statusCode: 503,
    userMessage: 'AI service is currently unavailable',
    category: 'chat',
    severity: 'warning',
  },
  [ErrorCode.CHAT_MESSAGE_TOO_LONG]: {
    statusCode: 400,
    userMessage: 'Message is too long',
    category: 'chat',
    severity: 'info',
  },

  // MODELS
  [ErrorCode.MODEL_NOT_FOUND]: {
    statusCode: 404,
    userMessage: 'Model not found',
    category: 'models',
    severity: 'info',
  },
  [ErrorCode.MODEL_NOT_AVAILABLE]: {
    statusCode: 503,
    userMessage: 'Model is not currently available',
    category: 'models',
    severity: 'warning',
  },
  [ErrorCode.MODEL_LOAD_FAILED]: {
    statusCode: 500,
    userMessage: 'Failed to load model',
    category: 'models',
    severity: 'warning',
  },
  [ErrorCode.MODEL_INFERENCE_FAILED]: {
    statusCode: 500,
    userMessage: 'Model inference failed',
    category: 'models',
    severity: 'warning',
  },
  [ErrorCode.MODEL_OUT_OF_MEMORY]: {
    statusCode: 503,
    userMessage: 'Out of memory for model inference',
    category: 'models',
    severity: 'warning',
  },

  // PROVIDER
  [ErrorCode.PROVIDER_INVALID]: {
    statusCode: 400,
    userMessage: 'Invalid provider',
    category: 'provider',
    severity: 'info',
  },
  [ErrorCode.PROVIDER_NOT_CONFIGURED]: {
    statusCode: 400,
    userMessage: 'Provider not configured',
    category: 'provider',
    severity: 'info',
  },
  [ErrorCode.PROVIDER_API_FAILED]: {
    statusCode: 502,
    userMessage: 'Provider API error',
    category: 'provider',
    severity: 'warning',
  },
  [ErrorCode.PROVIDER_RATE_LIMITED]: {
    statusCode: 429,
    userMessage: 'Rate limit exceeded. Please wait before trying again.',
    category: 'provider',
    severity: 'warning',
  },
  [ErrorCode.PROVIDER_CREDENTIAL_INVALID]: {
    statusCode: 400,
    userMessage: 'Invalid provider credentials',
    category: 'provider',
    severity: 'warning',
  },
  [ErrorCode.PROVIDER_CREDENTIAL_EXPIRED]: {
    statusCode: 401,
    userMessage: 'Provider credentials have expired',
    category: 'provider',
    severity: 'warning',
  },

  // OLLAMA
  [ErrorCode.OLLAMA_NOT_RUNNING]: {
    statusCode: 503,
    userMessage: 'Local AI service (Ollama) is not running',
    category: 'ollama',
    severity: 'warning',
  },
  [ErrorCode.OLLAMA_CONNECTION_FAILED]: {
    statusCode: 503,
    userMessage: 'Cannot connect to local AI service',
    category: 'ollama',
    severity: 'warning',
  },
  [ErrorCode.OLLAMA_MODEL_NOT_FOUND]: {
    statusCode: 404,
    userMessage: 'AI model not found locally',
    category: 'ollama',
    severity: 'info',
  },
  [ErrorCode.OLLAMA_INFERENCE_FAILED]: {
    statusCode: 500,
    userMessage: 'AI inference failed',
    category: 'ollama',
    severity: 'warning',
  },
  [ErrorCode.OLLAMA_PULL_FAILED]: {
    statusCode: 500,
    userMessage: 'Failed to download AI model',
    category: 'ollama',
    severity: 'warning',
  },

  // SETTINGS
  [ErrorCode.SETTINGS_NOT_FOUND]: {
    statusCode: 404,
    userMessage: 'Settings not found',
    category: 'settings',
    severity: 'info',
  },
  [ErrorCode.SETTINGS_UPDATE_FAILED]: {
    statusCode: 500,
    userMessage: 'Failed to update settings',
    category: 'settings',
    severity: 'warning',
  },
  [ErrorCode.SETTINGS_INVALID]: {
    statusCode: 400,
    userMessage: 'Invalid settings',
    category: 'settings',
    severity: 'info',
  },
  [ErrorCode.CREDENTIAL_STORAGE_FAILED]: {
    statusCode: 500,
    userMessage: 'Failed to store credentials',
    category: 'settings',
    severity: 'warning',
  },

  // LIBRARY
  [ErrorCode.LIBRARY_ITEM_NOT_FOUND]: {
    statusCode: 404,
    userMessage: 'Library item not found',
    category: 'library',
    severity: 'info',
  },
  [ErrorCode.LIBRARY_SAVE_FAILED]: {
    statusCode: 500,
    userMessage: 'Failed to save to library',
    category: 'library',
    severity: 'warning',
  },
  [ErrorCode.LIBRARY_LOAD_FAILED]: {
    statusCode: 500,
    userMessage: 'Failed to load library',
    category: 'library',
    severity: 'warning',
  },
  [ErrorCode.LIBRARY_DELETE_FAILED]: {
    statusCode: 500,
    userMessage: 'Failed to delete library item',
    category: 'library',
    severity: 'warning',
  },

  // SYSTEM
  [ErrorCode.SYSTEM_INTERNAL_ERROR]: {
    statusCode: 500,
    userMessage: 'An unexpected error occurred',
    category: 'system',
    severity: 'critical',
  },
  [ErrorCode.SYSTEM_SERVICE_UNAVAILABLE]: {
    statusCode: 503,
    userMessage: 'Service is temporarily unavailable. Please try again later.',
    category: 'system',
    severity: 'warning',
  },
  [ErrorCode.SYSTEM_NOT_IMPLEMENTED]: {
    statusCode: 501,
    userMessage: 'This feature is not yet implemented',
    category: 'system',
    severity: 'info',
  },
  [ErrorCode.SYSTEM_TIMEOUT]: {
    statusCode: 504,
    userMessage: 'Request timed out. Please try again.',
    category: 'system',
    severity: 'warning',
  },
  [ErrorCode.SYSTEM_TOO_MANY_REQUESTS]: {
    statusCode: 429,
    userMessage: 'Too many requests. Please wait a moment before trying again.',
    category: 'system',
    severity: 'warning',
  },
  [ErrorCode.SYSTEM_MAINTENANCE]: {
    statusCode: 503,
    userMessage: 'Service is under maintenance. Please try again later.',
    category: 'system',
    severity: 'info',
  },

  // CLIENT-SIDE ERRORS
  [ErrorCode.CLIENT_NETWORK_ERROR]: {
    statusCode: 0,
    userMessage: 'Network connection failed. Please check your internet.',
    category: 'client',
    severity: 'warning',
  },
  [ErrorCode.CLIENT_REQUEST_TIMEOUT]: {
    statusCode: 0,
    userMessage: 'Request timed out. Please try again.',
    category: 'client',
    severity: 'warning',
  },
  [ErrorCode.CLIENT_OFFLINE]: {
    statusCode: 0,
    userMessage: 'You are offline. Some features may be unavailable.',
    category: 'client',
    severity: 'info',
  },
  [ErrorCode.CLIENT_PARSE_ERROR]: {
    statusCode: 0,
    userMessage: 'Failed to process server response',
    category: 'client',
    severity: 'warning',
  },
  [ErrorCode.CLIENT_CACHE_MISS]: {
    statusCode: 0,
    userMessage: 'Data not available. Please refresh.',
    category: 'client',
    severity: 'info',
  },
}

// Errors that can be retried
export const RETRYABLE_ERRORS = new Set([
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
  ErrorCode.CLIENT_NETWORK_ERROR,
  ErrorCode.CLIENT_REQUEST_TIMEOUT,
])

// Errors that should trigger circuit breaker
export const CIRCUIT_BREAKER_ERRORS = new Set([
  ErrorCode.OLLAMA_NOT_RUNNING,
  ErrorCode.OLLAMA_CONNECTION_FAILED,
  ErrorCode.PROVIDER_API_FAILED,
  ErrorCode.SYSTEM_SERVICE_UNAVAILABLE,
])

// Errors that need immediate user attention
export const ALERT_ERRORS = new Set([
  ErrorCode.AUTH_JWT_EXPIRED,
  ErrorCode.AUTH_UNAUTHORIZED,
  ErrorCode.AUTH_FORBIDDEN,
  ErrorCode.PROVIDER_CREDENTIAL_INVALID,
  ErrorCode.PROVIDER_CREDENTIAL_EXPIRED,
])

/**
 * Get user-friendly message for error code
 */
export function getErrorMessage(code: ErrorCode | string): string {
  if (code in ERROR_METADATA) {
    return (ERROR_METADATA as any)[code].userMessage
  }
  return 'An unexpected error occurred'
}

/**
 * Get error severity
 */
export function getErrorSeverity(code: ErrorCode | string): string {
  if (code in ERROR_METADATA) {
    return (ERROR_METADATA as any)[code].severity
  }
  return 'warning'
}

/**
 * Check if error is retryable
 */
export function isRetryable(code: ErrorCode | string): boolean {
  return RETRYABLE_ERRORS.has(code as ErrorCode)
}

/**
 * Check if error should trigger circuit breaker
 */
export function shouldTriggerCircuitBreaker(code: ErrorCode | string): boolean {
  return CIRCUIT_BREAKER_ERRORS.has(code as ErrorCode)
}

/**
 * Check if error needs immediate alert
 */
export function needsAlert(code: ErrorCode | string): boolean {
  return ALERT_ERRORS.has(code as ErrorCode)
}
