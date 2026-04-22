/**
 * Error Message Formatting & User-Friendly Conversion
 *
 * Converts error codes and HTTP errors into user-friendly messages.
 */

import { ErrorCode, getErrorMessage, getErrorSeverity } from './errorCodes'

export interface FormattedError {
  code: string
  message: string
  severity: 'info' | 'warning' | 'critical'
  timestamp: string
  action?: 'retry' | 'signin' | 'settings' | 'offline'
}

/**
 * Parse API error response and convert to FormattedError
 */
export function parseApiError(error: any): FormattedError {
  const timestamp = new Date().toISOString()

  // If error has code property, use structured error
  if (error?.code) {
    const code = error.code as ErrorCode
    return {
      code,
      message: error.message || getErrorMessage(code),
      severity: getErrorSeverity(code) as any,
      timestamp,
      action: getErrorAction(code),
    }
  }

  // If error has response from Axios
  if (error?.response) {
    const status = error.response.status
    const data = error.response.data

    // Try to extract code from response
    if (data?.code) {
      return parseApiError(data)
    }

    // Map HTTP status to error code
    const code = mapHttpStatusToErrorCode(status)
    return {
      code,
      message: data?.detail || data?.message || getErrorMessage(code as ErrorCode),
      severity: getErrorSeverity(code) as any,
      timestamp,
      action: getErrorAction(code as ErrorCode),
    }
  }

  // Network error (request made but no response)
  if (error?.request) {
    return {
      code: ErrorCode.CLIENT_NETWORK_ERROR,
      message: 'Network connection failed. Please check your internet.',
      severity: 'warning',
      timestamp,
      action: 'retry',
    }
  }

  // Request setup error
  if (error instanceof Error) {
    // Check for timeout
    if (error.message.includes('timeout')) {
      return {
        code: ErrorCode.CLIENT_REQUEST_TIMEOUT,
        message: 'Request timed out. Please try again.',
        severity: 'warning',
        timestamp,
        action: 'retry',
      }
    }

    return {
      code: 'UNKNOWN_ERROR',
      message: error.message || 'An unexpected error occurred',
      severity: 'warning',
      timestamp,
    }
  }

  // Fallback
  return {
    code: 'UNKNOWN_ERROR',
    message: 'An unexpected error occurred',
    severity: 'warning',
    timestamp,
  }
}

/**
 * Map HTTP status code to error code
 */
function mapHttpStatusToErrorCode(status: number): string {
  switch (status) {
    case 400:
      return ErrorCode.VALIDATION_INVALID_INPUT
    case 401:
      return ErrorCode.AUTH_UNAUTHORIZED
    case 403:
      return ErrorCode.AUTH_FORBIDDEN
    case 404:
      return ErrorCode.DB_NOT_FOUND
    case 429:
      return ErrorCode.SYSTEM_TOO_MANY_REQUESTS
    case 500:
    case 502:
    case 503:
      return ErrorCode.SYSTEM_SERVICE_UNAVAILABLE
    case 504:
      return ErrorCode.SYSTEM_TIMEOUT
    default:
      return ErrorCode.SYSTEM_INTERNAL_ERROR
  }
}

/**
 * Get recommended action for error
 */
function getErrorAction(code: string): 'retry' | 'signin' | 'settings' | 'offline' | undefined {
  // Auth errors → sign in
  if (code.startsWith('AUTH_')) {
    return 'signin'
  }

  // Provider/credential errors → settings
  if (code.startsWith('PROVIDER_') || code === ErrorCode.CREDENTIAL_STORAGE_FAILED) {
    return 'settings'
  }

  // Network/timeout → retry
  if (
    code === ErrorCode.CLIENT_NETWORK_ERROR ||
    code === ErrorCode.CLIENT_REQUEST_TIMEOUT ||
    code === ErrorCode.SYSTEM_TIMEOUT ||
    code === ErrorCode.SYSTEM_SERVICE_UNAVAILABLE ||
    code === ErrorCode.OLLAMA_CONNECTION_FAILED
  ) {
    return 'retry'
  }

  // Offline → offline
  if (code === ErrorCode.CLIENT_OFFLINE) {
    return 'offline'
  }

  return undefined
}

/**
 * Format error with action buttons/suggestions
 */
export function formatErrorWithSuggestion(error: FormattedError): string {
  let message = error.message

  // Add action suggestion
  switch (error.action) {
    case 'retry':
      message += '\n\nTry clicking "Retry" or refresh the page.'
      break
    case 'signin':
      message += '\n\nPlease sign in again to continue.'
      break
    case 'settings':
      message += '\n\nPlease check your settings and credentials.'
      break
    case 'offline':
      message += '\n\nSome features may be unavailable offline.'
      break
  }

  return message
}

/**
 * Get icon/emoji for error severity
 */
export function getSeverityIcon(severity: string): string {
  switch (severity) {
    case 'critical':
      return '🚨'
    case 'warning':
      return '⚠️'
    case 'info':
      return 'ℹ️'
    default:
      return '❓'
  }
}

/**
 * Check if error indicates offline status
 */
export function isOfflineError(code: string): boolean {
  return code === ErrorCode.CLIENT_OFFLINE || code === ErrorCode.CLIENT_NETWORK_ERROR
}

/**
 * Check if error is temporary (should retry)
 */
export function isTemporaryError(code: string): boolean {
  const temporaryCodes = [
    ErrorCode.SYSTEM_TIMEOUT,
    ErrorCode.SYSTEM_TOO_MANY_REQUESTS,
    ErrorCode.SYSTEM_SERVICE_UNAVAILABLE,
    ErrorCode.CLIENT_NETWORK_ERROR,
    ErrorCode.CLIENT_REQUEST_TIMEOUT,
    ErrorCode.OLLAMA_NOT_RUNNING,
    ErrorCode.OLLAMA_CONNECTION_FAILED,
  ]
  return temporaryCodes.includes(code as ErrorCode)
}

/**
 * Check if error requires user interaction
 */
export function requiresUserInteraction(code: string): boolean {
  const interactionCodes = [
    ErrorCode.AUTH_JWT_EXPIRED,
    ErrorCode.AUTH_UNAUTHORIZED,
    ErrorCode.AUTH_FORBIDDEN,
    ErrorCode.PROVIDER_CREDENTIAL_INVALID,
    ErrorCode.PROVIDER_CREDENTIAL_EXPIRED,
    ErrorCode.VALIDATION_INVALID_INPUT,
    ErrorCode.CHAT_MESSAGE_TOO_LONG,
  ]
  return interactionCodes.includes(code as ErrorCode)
}
