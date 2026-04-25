# T1-1 Implementation Plan: Error Handling & Recovery

**Task:** Add comprehensive error logging, graceful degradation, retry logic, and error telemetry  
**Timeline:** May 1-7, 2026  
**Status:** Planning → Implementation

---

## Current State Audit

### ✅ Already in Place
- Basic APIError class (statusCode, message, details)
- Retry logic with exponential backoff (syncManager)
- Debouncing to prevent duplicate requests
- Optimistic UI updates with rollback on error
- Error messages stored in sync status
- Try-catch blocks in most syncManager methods
- Basic HTTP error handling in routes.py

### ❌ Critical Gaps

#### API (Backend)
- [ ] No structured error codes (only HTTP status codes)
- [ ] No error telemetry/logging system
- [ ] Limited error context (where did it fail? why?)
- [ ] No graceful degradation strategies
- [ ] Routes don't handle all edge cases
- [ ] No request timeout handling
- [ ] No rate limiting or circuit breaker
- [ ] Database errors not distinguished from API errors

#### Web UI (Frontend)
- [ ] No error boundaries (React component crashes take down UI)
- [ ] No error recovery UI (user can't see what went wrong)
- [ ] No telemetry on errors (can't debug user issues)
- [ ] No request timeout handling (hangs indefinitely)
- [ ] No graceful degradation (no offline mode or cached fallback)
- [ ] Limited user-facing error messages (technical jargon)
- [ ] No error toast/notification system

#### Shared
- [ ] No structured error codes across both systems
- [ ] No error documentation for API consumers
- [ ] No error tracking dashboard or monitoring

---

## Implementation Plan (5 Sub-Tranches)

### Phase 1: Error Infrastructure (1 day)
Create the foundation for structured error handling.

**Files to create:**
1. `src/guppy/api/error_codes.py` — Centralized error code definitions
2. `web/src/utils/errorCodes.ts` — Frontend error code definitions
3. `web/src/utils/errorMessages.ts` — User-friendly error message mapping

**Files to modify:**
1. `src/guppy/api/logging.py` — Add structured logging
2. `web/src/utils/logger.ts` — Frontend logging utility

### Phase 2: API Error Handling (2 days)
Standardize and improve backend error handling.

**Files to modify:**
1. `src/guppy/api/routes.py` — Add error context to all endpoints
2. `src/guppy/api/_server_fragment_routes_core.py` — Wrap routes with error handler
3. `src/guppy/api/auth.py` — Improve auth error messages
4. `src/guppy/api/service.py` — Add error telemetry

**Files to create:**
1. `src/guppy/api/error_handler.py` — Central error handling middleware
2. `src/guppy/api/telemetry.py` — Error telemetry and logging

### Phase 3: Frontend Error Recovery (2 days)
Add error boundaries and recovery UI.

**Files to create:**
1. `web/src/components/ErrorBoundary.tsx` — Catch component crashes
2. `web/src/components/ErrorToast.tsx` — User-friendly error notifications
3. `web/src/hooks/useErrorRecovery.ts` — Recovery logic

**Files to modify:**
1. `web/src/App.tsx` — Wrap with ErrorBoundary
2. `web/src/views/AssistantView.tsx` — Add error recovery UI
3. `web/src/store/syncManager.ts` — Add timeout handling and graceful degradation
4. `web/src/api/client.ts` — Add request timeout, request/response interceptors

### Phase 4: Request Resilience (1 day)
Add timeouts, circuit breaker, and request queue.

**Files to modify:**
1. `web/src/api/client.ts` — Add request timeout and retry queue
2. `web/src/store/syncManager.ts` — Add circuit breaker pattern

**Files to create:**
1. `web/src/utils/circuitBreaker.ts` — Circuit breaker implementation
2. `web/src/utils/requestQueue.ts` — Request queueing for offline scenarios

### Phase 5: Monitoring & Documentation (1 day)
Add error tracking, telemetry, and documentation.

**Files to create:**
1. `docs/ERROR_CODES.md` — Complete error code reference
2. `docs/ERROR_HANDLING.md` — Guidelines for error handling
3. `web/src/utils/errorTelemetry.ts` — Client-side error tracking

---

## Success Criteria

### API
- [ ] All endpoints return structured errors with codes
- [ ] Error logs include request ID, timestamp, user, endpoint, error code
- [ ] All database errors caught and wrapped with context
- [ ] All HTTP errors have appropriate status codes (400, 401, 403, 404, 500, 503)
- [ ] Timeout threshold: 30s for most requests, 60s for long-running
- [ ] Error telemetry logs to file with rotation

### Web UI
- [ ] No unhandled React errors (caught by error boundary)
- [ ] All API errors show user-friendly toast notifications
- [ ] Retry buttons on connection errors
- [ ] Request timeout shows "Connection timeout" message
- [ ] Offline mode gracefully degrades (uses cached data, shows notifications)
- [ ] Error recovery doesn't require page reload

### Testing
- [ ] Unit tests for error handler, circuit breaker, retry logic
- [ ] Integration tests for error scenarios (500, 503, timeout)
- [ ] End-to-end test of error → user notification → recovery

---

## Files Summary

### New Files (7 total)
```
Backend:
  src/guppy/api/error_codes.py
  src/guppy/api/error_handler.py
  src/guppy/api/telemetry.py

Frontend:
  web/src/utils/errorCodes.ts
  web/src/utils/errorMessages.ts
  web/src/components/ErrorBoundary.tsx
  web/src/components/ErrorToast.tsx
  web/src/hooks/useErrorRecovery.ts
  web/src/utils/circuitBreaker.ts
  web/src/utils/requestQueue.ts
  web/src/utils/errorTelemetry.ts

Documentation:
  docs/ERROR_CODES.md
  docs/ERROR_HANDLING.md
```

### Modified Files (8 total)
```
Backend:
  src/guppy/api/routes.py
  src/guppy/api/_server_fragment_routes_core.py
  src/guppy/api/auth.py
  src/guppy/api/service.py
  src/guppy/api/logging.py

Frontend:
  web/src/App.tsx
  web/src/api/client.ts
  web/src/store/syncManager.ts
  web/src/views/AssistantView.tsx
```

---

## Risk Mitigations

1. **Large surface area** → Phase it into 5 days, commit after each phase
2. **Breaking existing code** → Write tests first, use feature flags
3. **Performance impact** → Profile with telemetry disabled in dev
4. **Complexity** → Document each error code and recovery pattern

---

## Next Steps

1. ✅ Audit complete (this document)
2. → **Start Phase 1:** Error infrastructure (error_codes.py, error_codes.ts, errorMessages.ts)
3. → Implement and test before moving to Phase 2

**Commit Message Pattern:**
```
T1-1 Phase N: [description]

- File 1: change
- File 2: change

Resolves: [phase X/5]
```
