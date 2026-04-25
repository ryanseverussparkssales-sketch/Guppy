# Error Code Reference Guide

Complete reference for all error codes used in Guppy's resilience layer.

## Overview

Error codes follow a hierarchical naming convention:
- **Category** (AUTH, DB, VALIDATION, etc.)
- **Specific condition** (INVALID, FAILED, NOT_FOUND, etc.)

Example: `AUTH_JWT_EXPIRED` means an Authentication JWT that has Expired

## Error Categories

### 🔐 Authentication (AUTH_*)

| Code | Status | User Message | Recovery |
|------|--------|-------------|----------|
| AUTH_JWT_EXPIRED | 401 | "Your session has expired. Please sign in again." | Redirect to login, clear token |
| AUTH_JWT_INVALID | 401 | "Invalid authentication token" | Clear token, re-authenticate |
| AUTH_UNAUTHORIZED | 401 | "You are not authorized to access this resource" | Check permissions, contact admin |
| AUTH_FORBIDDEN | 403 | "You don't have permission to perform this action" | Verify credentials, check role |
| AUTH_JWT_REFRESH_FAILED | 401 | "Failed to refresh session" | Re-login required |
| AUTH_JWT_NOT_CONFIGURED | 503 | "Authentication not configured" | Contact system admin |
| AUTH_TURNSTILE_FAILED | 400 | "CAPTCHA verification failed" | Try again, enable JavaScript |

**When to trigger:** After receiving 401/403 status codes

**Auto-retry:** No (auth errors are not retried)

---

### 💾 Database (DB_*)

| Code | Status | User Message | Recovery |
|------|--------|-------------|----------|
| DB_CONNECTION_FAILED | 500 | "Cannot reach database" | Retry, check network |
| DB_QUERY_FAILED | 500 | "Database query failed" | Retry, check data format |
| DB_NOT_FOUND | 404 | "Resource not found" | Check ID, refresh data |
| DB_CONSTRAINT_VIOLATION | 400 | "Data validation failed" | Fix input, try again |
| DB_INTEGRITY_VIOLATION | 400 | "Data integrity violation" | Check for duplicates |
| DB_TRANSACTION_FAILED | 500 | "Operation failed" | Retry |

**When to trigger:** API returns 4xx/5xx from database operations

**Auto-retry:** 500-level errors ✓, 400-level errors ✗

---

### ✓ Validation (VALIDATION_*)

| Code | Status | User Message | Recovery |
|------|--------|-------------|----------|
| VALIDATION_INVALID_INPUT | 400 | "Invalid input provided" | Fix form data |
| VALIDATION_MISSING_FIELD | 400 | "Required field missing" | Complete all fields |
| VALIDATION_INVALID_FORMAT | 400 | "Invalid format (email, URL, etc.)" | Check format, try again |
| VALIDATION_OUT_OF_RANGE | 400 | "Value out of acceptable range" | Check min/max bounds |

**When to trigger:** API returns 400 Bad Request

**Auto-retry:** No (validation errors require user action)

---

### 💬 Chat (CHAT_*)

| Code | Status | User Message | Recovery |
|------|--------|-------------|----------|
| CHAT_FAILED_TO_SEND | 500 | "Failed to send message" | Retry, check message |
| CHAT_AI_RESPONSE_FAILED | 500 | "AI response generation failed" | Retry, try simpler prompt |
| CHAT_MESSAGE_TOO_LONG | 400 | "Message exceeds maximum length" | Shorten message |
| CHAT_CONVERSATION_NOT_FOUND | 404 | "Conversation not found" | Refresh, create new |
| CHAT_MESSAGE_NOT_FOUND | 404 | "Message not found" | Refresh conversation |

**When to trigger:** Chat operations fail

**Auto-retry:** 500-level ✓, 404/400 ✗

---

### 🤖 Models (MODEL_*)

| Code | Status | User Message | Recovery |
|------|--------|-------------|----------|
| MODEL_NOT_FOUND | 404 | "Model not available" | Select different model |
| MODEL_NOT_AVAILABLE | 503 | "Model temporarily unavailable" | Wait, try different model |
| MODEL_LOAD_FAILED | 500 | "Failed to load model" | Retry, check GPU memory |
| MODEL_INFERENCE_FAILED | 500 | "Model inference failed" | Retry, simplify input |
| MODEL_OUT_OF_MEMORY | 503 | "Insufficient GPU memory" | Use smaller model, wait |

**When to trigger:** Ollama/provider model operations fail

**Auto-retry:** 500/503 ✓, 404 ✗

---

### 👥 Provider (PROVIDER_*)

| Code | Status | User Message | Recovery |
|------|--------|-------------|----------|
| PROVIDER_NOT_CONFIGURED | 400 | "Provider not configured" | Add credentials in Settings |
| PROVIDER_API_FAILED | 500 | "Provider API error" | Retry, check API status |
| PROVIDER_RATE_LIMITED | 429 | "Rate limit exceeded" | Wait before retrying |
| PROVIDER_CREDENTIAL_INVALID | 401 | "Invalid API credentials" | Update in Settings |
| PROVIDER_CREDENTIAL_EXPIRED | 401 | "API credentials expired" | Refresh in Settings |
| PROVIDER_INVALID | 400 | "Invalid provider selected" | Choose valid provider |

**When to trigger:** API provider (Claude, OpenAI, etc.) operations fail

**Auto-retry:** 500 ✓, 429 ✓ (with backoff), 401/400 ✗

---

### 🦙 Ollama (OLLAMA_*)

| Code | Status | User Message | Recovery |
|------|--------|-------------|----------|
| OLLAMA_NOT_RUNNING | 503 | "Ollama service not running" | Start Ollama service |
| OLLAMA_CONNECTION_FAILED | 503 | "Cannot connect to Ollama" | Check network, restart |
| OLLAMA_MODEL_NOT_FOUND | 404 | "Model not found" | Pull model: `ollama pull model-name` |
| OLLAMA_INFERENCE_FAILED | 500 | "Model inference failed" | Retry, check VRAM |
| OLLAMA_PULL_FAILED | 500 | "Failed to download model" | Retry, check disk space |

**When to trigger:** Ollama service errors

**Auto-retry:** 503/500 ✓, 404 ✗

**Triggers circuit breaker:** ✓ YES

---

### ⚙️ System (SYSTEM_*)

| Code | Status | User Message | Recovery |
|------|--------|-------------|----------|
| SYSTEM_SERVICE_UNAVAILABLE | 503 | "Service temporarily unavailable" | Wait, retry |
| SYSTEM_TIMEOUT | 504 | "Request timeout" | Retry with longer timeout |
| SYSTEM_TOO_MANY_REQUESTS | 429 | "Too many requests" | Wait before retrying |
| SYSTEM_MAINTENANCE | 503 | "System under maintenance" | Wait for maintenance |
| SYSTEM_INTERNAL_ERROR | 500 | "Internal server error" | Retry, contact support |
| SYSTEM_NOT_IMPLEMENTED | 501 | "Feature not implemented" | Use alternative, wait for update |

**When to trigger:** Generic server errors

**Auto-retry:** 500/503/504 ✓, 429 ✓ (with backoff)

**Triggers circuit breaker:** ✓ YES

---

### 🌐 Network (CLIENT_*)

| Code | Status | User Message | Recovery |
|------|--------|-------------|----------|
| CLIENT_NETWORK_ERROR | 0 | "Network connection failed" | Check internet, retry |
| CLIENT_REQUEST_TIMEOUT | 0 | "Request timeout" | Check connection, retry |
| CLIENT_OFFLINE | 0 | "Device is offline" | Wait for connection, requests queued |
| CLIENT_PARSE_ERROR | 0 | "Failed to parse response" | Retry, check API format |
| CLIENT_CACHE_MISS | 0 | "Data not in cache" | Retry |

**When to trigger:** Network-level errors, no HTTP response

**Auto-retry:** ✓ YES (handled by queue)

**Triggers circuit breaker:** ✓ YES

---

## Error Code Decision Tree

Use this to determine the correct error code:

```
Is it an authentication issue?
├─ JWT expired? → AUTH_JWT_EXPIRED
├─ JWT invalid? → AUTH_JWT_INVALID
├─ Unauthorized? → AUTH_UNAUTHORIZED
└─ Forbidden? → AUTH_FORBIDDEN

Is it a validation issue?
├─ Missing field? → VALIDATION_MISSING_FIELD
├─ Invalid format? → VALIDATION_INVALID_FORMAT
├─ Out of range? → VALIDATION_OUT_OF_RANGE
└─ Generic invalid? → VALIDATION_INVALID_INPUT

Is it a model/AI issue?
├─ Model not found? → MODEL_NOT_FOUND
├─ Out of memory? → MODEL_OUT_OF_MEMORY
├─ Inference failed? → MODEL_INFERENCE_FAILED
└─ Load failed? → MODEL_LOAD_FAILED

Is it a provider issue?
├─ Credentials invalid? → PROVIDER_CREDENTIAL_INVALID
├─ Rate limited? → PROVIDER_RATE_LIMITED
├─ API failed? → PROVIDER_API_FAILED
└─ Not configured? → PROVIDER_NOT_CONFIGURED

Is it Ollama?
├─ Not running? → OLLAMA_NOT_RUNNING
├─ Connection failed? → OLLAMA_CONNECTION_FAILED
├─ Model not found? → OLLAMA_MODEL_NOT_FOUND
└─ Inference failed? → OLLAMA_INFERENCE_FAILED

Is it a network issue?
├─ No connection? → CLIENT_NETWORK_ERROR
├─ Timeout? → CLIENT_REQUEST_TIMEOUT
├─ Offline? → CLIENT_OFFLINE
└─ Parse error? → CLIENT_PARSE_ERROR

Otherwise → SYSTEM_INTERNAL_ERROR
```

---

## Retry Behavior

### Auto-Retry Errors (Status 5xx, 503, 429)

These errors are automatically queued and retried:
- All 5xx Server Errors
- 503 Service Unavailable
- 429 Too Many Requests (with exponential backoff)

```typescript
// These WILL be retried
- SYSTEM_SERVICE_UNAVAILABLE (503)
- OLLAMA_INFERENCE_FAILED (500)
- PROVIDER_API_FAILED (500)
- DB_CONNECTION_FAILED (500)
```

### No-Retry Errors (Status 4xx, 401, 403)

These errors require user action and are NOT retried:
- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found

```typescript
// These WILL NOT be retried
- VALIDATION_INVALID_INPUT (400)
- AUTH_UNAUTHORIZED (401)
- AUTH_FORBIDDEN (403)
- MODEL_NOT_FOUND (404)
```

---

## Circuit Breaker Triggers

The circuit breaker opens after 5 consecutive errors of these types:

1. **OLLAMA_CONNECTION_FAILED** — Can't reach Ollama service
2. **OLLAMA_NOT_RUNNING** — Ollama service down
3. **PROVIDER_API_FAILED** — Cloud provider API errors
4. **SYSTEM_SERVICE_UNAVAILABLE** — Generic unavailable
5. **CLIENT_NETWORK_ERROR** — Network connectivity issues

When circuit is OPEN:
- New requests are immediately queued
- No requests sent to the service
- After 30 seconds, circuit transitions to HALF_OPEN
- First request in HALF_OPEN tests if service recovered

---

## Using Error Codes in Code

### Checking for Specific Errors

```typescript
import { ErrorCode } from '@/utils/errorCodes'

try {
  await api.post('/api/chat', data)
} catch (error) {
  if (error.details?.errorCode === ErrorCode.OLLAMA_NOT_RUNNING) {
    // Handle Ollama-specific error
    showMessage('Please start Ollama first')
  } else if (error.details?.errorCode === ErrorCode.VALIDATION_INVALID_INPUT) {
    // Handle validation error
    showMessage('Please check your input')
  }
}
```

### Adding Error Code to Custom Errors

```typescript
import { ErrorCode } from '@/utils/errorCodes'

throw new Error('Failed to send message', {
  cause: {
    errorCode: ErrorCode.CHAT_FAILED_TO_SEND,
    statusCode: 500,
  },
})
```

### Error Code Metadata

```typescript
import { ERROR_METADATA, ErrorCode } from '@/utils/errorCodes'

const metadata = ERROR_METADATA[ErrorCode.AUTH_JWT_EXPIRED]
console.log(metadata.userMessage) // "Your session has expired..."
console.log(metadata.severity) // 'info'
console.log(metadata.category) // 'auth'
```

---

## Severity Levels

- **critical**: System down, immediate user attention required
- **warning**: Error occurred, retry possible
- **info**: Normal operational issue, user action needed

---

## Best Practices

1. **Always include error codes** when throwing or reporting errors
2. **Show user-friendly messages** from ERROR_METADATA, not technical details
3. **Don't retry auth errors** (401, 403, INVALID credentials)
4. **Do retry server errors** (5xx, timeouts, 429)
5. **Let circuit breaker handle** cascading failures
6. **Queue requests** when circuit is open
7. **Monitor error patterns** using telemetry
8. **Set up alerts** for critical error codes

See [ERROR_HANDLING_BEST_PRACTICES.md](./ERROR_HANDLING_BEST_PRACTICES.md) for detailed guidance.
