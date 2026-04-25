# Fix & Test Plan - Guppy Web UI
**Created:** 2026-04-22

---

## Issues Identified in Code Review

### CRITICAL (Blocks Testing)
1. ❌ **RequestQueue.flush() doesn't send requests** 
   - **Status:** CLARIFIED (not actually broken, behavior documented)
   - **Explanation:** Queue holds requests when service is unavailable. Actual retry happens via circuit breaker recovery in client.ts when service comes back online.
   - **Action:** No fix needed, but needs documentation update

2. ✅ **API Client cleanup is solid**
   - **Status:** VERIFIED WORKING
   - **Details:** AbortController and timeout cleanup properly handled in both success and error paths

### HIGH (Should fix before production)
1. **Race condition on rapid message sends**
   - **File:** `src/store/syncManager.ts`
   - **Fix:** Add per-conversation send lock
   - **Effort:** 2-4 hours
   - **Impact:** Prevents duplicate messages if user clicks send multiple times

2. **Error display doesn't clear after success**
   - **File:** `src/views/AssistantView.tsx`
   - **Fix:** Clear localError in finally block after message send
   - **Effort:** 15 minutes
   - **Impact:** UI shows stale errors to user

3. **Missing error boundary on DiagnosticDashboard**
   - **File:** `src/views/SettingsView.tsx`
   - **Fix:** Wrap DiagnosticDashboard in error boundary
   - **Effort:** 30 minutes
   - **Impact:** Dashboard failure crashes entire settings view

### MEDIUM (Should fix before full production)
1. **Type safety in API client**
   - **File:** `src/api/client.ts`
   - **Issue:** Using `(config as any)` loses type safety
   - **Fix:** Create proper interface for enhanced config
   - **Effort:** 1-2 hours

2. **Telemetry localStorage performance**
   - **File:** `src/utils/telemetry.ts`
   - **Issue:** Saves to localStorage on every event
   - **Fix:** Debounce saves or batch updates
   - **Effort:** 1 hour
   - **Impact:** High CPU usage under heavy load

---

## Fix Implementation Order

### Phase 1: Critical Fixes (Required before testing)
**Time: ~30 minutes**

#### 1. Fix AssistantView error display (15 min)
```diff
// src/views/AssistantView.tsx line 86-93
} catch (error: any) {
  setLocalError(error?.message || 'Failed to send message')
  // Re-populate input on error
  setInputValue(messageText)
+ } finally {
+   setIsSending(false)
+   inputRef.current?.focus()
+   // Clear error after 3 seconds
+   if (!error) {
+     setTimeout(() => setLocalError(null), 3000)
+   }
}
```

#### 2. Add error boundary to Settings (15 min)
```diff
// src/views/SettingsView.tsx
import { ErrorBoundary } from 'react-error-boundary'

// In diagnostics tab:
<ErrorBoundary fallback={<div>Diagnostics failed to load</div>}>
  <DiagnosticDashboard expanded={true} />
</ErrorBoundary>
```

### Phase 2: High Priority Fixes (Before production)
**Time: ~4 hours**

#### 3. Add send lock to syncManager (2 hours)
```typescript
// src/store/syncManager.ts
private sendingByConversation = new Map<string, Promise<void>>()

async addMessage(conversationId: string, ...) {
  // Check if already sending in this conversation
  if (this.sendingByConversation.has(conversationId)) {
    return // Silently ignore duplicate send
  }

  const sendPromise = this._doAddMessage(...)
  this.sendingByConversation.set(conversationId, sendPromise)
  
  try {
    await sendPromise
  } finally {
    this.sendingByConversation.delete(conversationId)
  }
}
```

#### 4. Add conversation message caching (2 hours)
```typescript
// src/store/syncManager.ts
private conversationCache = new Map<string, {
  messages: ChatMessage[]
  timestamp: number
  ttl: number
}>()

async loadConversation(conversationId: string) {
  const cached = this.conversationCache.get(conversationId)
  if (cached && Date.now() - cached.timestamp < cached.ttl) {
    return cached.messages
  }
  
  // Fetch and cache...
}
```

### Phase 3: Medium Priority (Polish)
**Time: ~3 hours**

#### 5. Improve telemetry performance (1 hour)
```typescript
// src/utils/telemetry.ts
private saveToStorageDebounced = debounce(() => {
  this._actuallySerializeAndSave()
}, 5000)

recordEvent(...) {
  this.events.push(...)
  this.saveToStorageDebounced() // Debounce instead of immediate
}
```

#### 6. Add proper typing (2 hours)
```typescript
// src/api/client-types.ts
interface EnhancedAxiosConfig extends InternalAxiosRequestConfig {
  _timeoutId?: NodeJS.Timeout
  _controller?: AbortController
  _endpoint?: string
}
```

---

## Testing Strategy

### Unit Tests (2 hours)
```bash
# Test individual components
npm run test -- src/utils/requestQueue.test.ts
npm run test -- src/utils/circuitBreaker.test.ts
npm run test -- src/store/syncManager.test.ts
```

### Integration Tests (3 hours)
```bash
# Test component interactions
npm run test:integration -- AssistantView
npm run test:integration -- OfflineFlow
npm run test:integration -- ErrorRecovery
```

### E2E Tests (4 hours)
```bash
# Full user flows
npm run test:e2e -- SendMessage
npm run test:e2e -- OfflineToOnline
npm run test:e2e -- CircuitBreakerRecovery
npm run test:e2e -- MultipleErrors
```

### Manual Testing Checklist

#### Basic Functionality (30 min)
- [ ] Create workspace
- [ ] Create conversation
- [ ] Send message (appears immediately)
- [ ] Send multiple messages
- [ ] Delete conversation
- [ ] Settings view loads
- [ ] Theme switcher works
- [ ] Diagnostics tab shows metrics

#### Offline Scenarios (45 min)
1. **Offline then Online**
   - [ ] Open DevTools → Network → Offline
   - [ ] Try to send message
   - [ ] Observe queue status shows "Offline"
   - [ ] Go Online in DevTools
   - [ ] Message should process
   - [ ] Check diagnostics shows successful retry

2. **API Server Down**
   - [ ] Stop the API server
   - [ ] Try to send message
   - [ ] Observe circuit breaker opens after 5 failures
   - [ ] Queue fills up with HIGH priority messages
   - [ ] Start API server
   - [ ] Observe queue drains and messages process

3. **Rate Limiting**
   - [ ] Use Apache Bench to hit /api/chat endpoint 100x rapidly
   - [ ] Observe circuit breaker transitions to HALF_OPEN
   - [ ] Verify 429 errors queued properly
   - [ ] Wait 30 seconds
   - [ ] Verify circuit breaker attempts recovery

#### Error Scenarios (30 min)
- [ ] Send message with invalid workspace ID (400 error)
- [ ] Send message with missing auth token (401 error)
- [ ] Send message with large payload (413 error)
- [ ] Check error messages display correctly
- [ ] Verify errors don't appear stale after success
- [ ] Verify diagnostics shows error metrics

#### Performance (30 min)
- [ ] Send 50 messages rapid-fire (measure response time)
- [ ] Check memory usage in DevTools
- [ ] Check for memory leaks (heap snapshots)
- [ ] Verify telemetry doesn't cause lag
- [ ] Monitor CPU usage
- [ ] Check localStorage quota usage

#### UI/UX (30 min)
- [ ] Messages appear in correct order
- [ ] Timestamps format correctly
- [ ] Queue status indicator visible when queued
- [ ] Offline indicator shows during offline
- [ ] Error messages are clear and actionable
- [ ] Diagnostics dashboard is readable
- [ ] Theme change is immediate
- [ ] No console errors

---

## Build & Deploy Checklist

### Before Build
- [ ] All TypeScript files compile without errors
- [ ] No console.warn or console.error from our code
- [ ] All imports resolve correctly
- [ ] Environment variables set correctly

### Build Command
```bash
cd C:\Users\Ryan\Guppy\web
npm run build
```

### Post-Build
- [ ] dist/ folder created
- [ ] No errors in build output
- [ ] Source maps generated
- [ ] Bundle size acceptable (< 500KB gzipped)

### Before Deploy to Production
- [ ] Update GUPPY_JWT_SECRET (use strong random value)
- [ ] Update TURNSTILE_SECRET (if using Cloudflare)
- [ ] Set GUPPY_DEV_MODE=0
- [ ] Remove console logging from production
- [ ] Enable telemetry storage limits
- [ ] Setup monitoring/alerting
- [ ] Create database backups

---

## Rollback Plan

If issues occur in production:

1. **Immediate (< 5 min)**
   - Revert to previous stable build
   - Clear browser cache (Ctrl+Shift+Delete)
   - Verify API server is responding

2. **Diagnostics (5-15 min)**
   - Check API server logs
   - Check browser console
   - Check network requests in DevTools
   - Check circuit breaker state

3. **Communication**
   - Notify users of issue
   - Provide ETA for fix
   - Provide workaround if available

4. **Post-Incident**
   - Root cause analysis
   - Add monitoring to prevent recurrence
   - Update runbook

---

## Success Criteria

✅ **Testing is complete when:**
1. All manual test scenarios pass
2. No errors in browser console
3. No memory leaks detected
4. Offline → Online flow works reliably
5. Error recovery works correctly
6. Telemetry captures expected events
7. Performance is acceptable
8. All UI elements render correctly
9. No race conditions or timing issues
10. Load test passes (50+ concurrent messages)

✅ **Ready for production when:**
1. All issues above are fixed
2. Code review approved
3. Security review passed
4. Performance baselines established
5. Monitoring/alerting configured
6. Runbook and docs updated
7. Team trained on deployment
8. Rollback plan tested

---

## Timeline Estimate

| Phase | Task | Time | Owner |
|-------|------|------|-------|
| 1 | Critical Fixes | 30 min | Claude |
| 2 | High Priority Fixes | 4 hours | Dev |
| 3 | Medium Priority Polish | 3 hours | Dev |
| 1 | Unit Tests | 2 hours | QA |
| 2 | Integration Tests | 3 hours | QA |
| 3 | E2E Tests | 4 hours | QA |
| 4 | Manual Testing | 3 hours | QA |
| 5 | Code Review | 2 hours | Lead |
| 6 | Bug Fixes from Review | 2 hours | Dev |
| 7 | Final Testing | 2 hours | QA |

**Total: ~26 hours (~3 days with parallel work)**

---

## Next Steps

1. ✅ Code review complete - DONE
2. 👉 Implement Phase 1 critical fixes (30 min)
3. 👉 Run build and verify no errors
4. 👉 Manual smoke test (15 min)
5. 👉 Begin Phase 2 high-priority fixes
6. 👉 Setup test environment
7. 👉 Execute test plan
8. 👉 Address findings
9. 👉 Final verification
10. 👉 Deploy to production

---

**Status:** 🟡 **READY FOR FIXES**

The system architecture is sound. Critical issues identified and fix plan documented. Ready to implement fixes and begin testing.
