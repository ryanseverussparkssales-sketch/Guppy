# Error Handling Best Practices

Guidelines for effective error handling in Guppy using the resilience layer.

## Principles

### 1. **Never Show Technical Errors to Users**

❌ BAD:
```typescript
catch (error) {
  showToast(error.message) // "ECONNREFUSED: Connection refused"
}
```

✅ GOOD:
```typescript
catch (error) {
  const userMessage = ERROR_METADATA[error.details?.errorCode]?.userMessage
  showToast(userMessage || 'An error occurred. Please try again.')
}
```

### 2. **Let Circuit Breaker and Queue Handle Recovery**

❌ BAD:
```typescript
// Manual retry logic
for (let i = 0; i < 5; i++) {
  try {
    return await api.post('/api/chat', data)
  } catch {
    await delay(Math.random() * 1000)
  }
}
```

✅ GOOD:
```typescript
// Let client handle it automatically
try {
  return await api.post('/api/chat', data)
  // If circuit is open, request is queued automatically
  // If retryable, queue handles retries
} catch (error) {
  if (error.queued) {
    showToast('Request queued - will be sent when service available')
  }
}
```

### 3. **Distinguish Between Retryable and Non-Retryable Errors**

Retryable (5xx, 503, 429):
- Auto-queue and retry
- User should wait or try later
- Show message: "We're having issues. Retrying automatically..."

Non-Retryable (4xx, 401, 403):
- Require user action
- Don't retry automatically
- Show message: "Please fix this and try again"

```typescript
const isRetryable = error.response?.status >= 500 || 
                    error.response?.status === 429 ||
                    !error.response // Network error

if (isRetryable) {
  showToast('Retrying automatically...')
} else {
  showToast('Please fix the issue and try again')
}
```

### 4. **Show Progress During Offline Operations**

```typescript
const queueStatus = useQueueMonitoring()

if (queueStatus.queuedCount > 0) {
  <div className="status-bar">
    📦 {queueStatus.queuedCount} requests waiting to sync
    {queueStatus.isFlushing && ' - syncing...'}
  </div>
}
```

### 5. **Group Related Error Handling**

❌ BAD:
```typescript
try { await api.post(...) } catch (e) { /* handle */ }
try { await api.get(...) } catch (e) { /* handle */ }
try { await api.put(...) } catch (e) { /* handle */ }
```

✅ GOOD:
```typescript
try {
  const [chatRes, settingsRes] = await Promise.all([
    api.post('/api/chat', data),
    api.get('/api/settings'),
  ])
  // Both succeeded
  updateUI(chatRes, settingsRes)
} catch (error) {
  // Handle all errors together
  const code = error.details?.errorCode
  if (code === ErrorCode.AUTH_UNAUTHORIZED) {
    redirect('/login')
  } else if (isRetryableError(code)) {
    showToast('Retrying...')
  }
}
```

---

## Error Handling Patterns

### Pattern 1: User-Initiated Actions (Buttons, Forms)

```typescript
async function handleSendMessage() {
  try {
    setLoading(true)
    const response = await syncManager.addMessage(conversationId, 'user', messageText)
    addMessageToUI(response)
    clearInputField()
  } catch (error) {
    // Error already reported by syncManager
    // Show action-specific guidance
    if (error.details?.errorCode === ErrorCode.CHAT_MESSAGE_TOO_LONG) {
      showToast('Message is too long. Please shorten it.')
    } else if (error.queued) {
      showToast('Message queued - will be sent when available')
    }
  } finally {
    setLoading(false)
  }
}
```

### Pattern 2: Background Initialization

```typescript
useEffect(() => {
  const initialize = async () => {
    try {
      await syncManager.initializeApp()
      setInitialized(true)
    } catch (error) {
      // Show offline fallback UI
      setInitialized(false)
      showOfflineFallback()
      
      // Retry after delay
      setTimeout(initialize, 5000)
    }
  }

  initialize()
}, [])
```

### Pattern 3: Resource Loading

```typescript
async function loadConversation(id: string) {
  try {
    setLoading(true)
    const conversation = await syncManager.loadConversation(id)
    renderConversation(conversation)
  } catch (error) {
    if (error.response?.status === 404) {
      showMessage('Conversation not found')
      navigate('/conversations')
    } else if (error.queued) {
      // Show cached version if available
      showCachedConversation(id)
    } else {
      showRetryButton(() => loadConversation(id))
    }
  } finally {
    setLoading(false)
  }
}
```

### Pattern 4: Optimistic Updates

```typescript
async function updateTitle(conversationId: string, newTitle: string) {
  // Optimistically update UI
  const oldTitle = getTitle(conversationId)
  setTitle(conversationId, newTitle)

  try {
    await syncManager.updateConversationTitle(conversationId, newTitle)
    // Success, keep UI as-is
  } catch (error) {
    // Revert optimistic update on error
    setTitle(conversationId, oldTitle)
    
    if (error.queued) {
      showToast('Title update queued')
    } else {
      showError('Failed to update title', () => 
        updateTitle(conversationId, newTitle)
      )
    }
  }
}
```

---

## Error Reporting and Telemetry

### Recording Errors Manually

```typescript
import { telemetry } from '@/utils/telemetry'

try {
  await riskyOperation()
} catch (error) {
  telemetry.recordRequestError(
    'POST /api/custom',
    ErrorCode.CUSTOM_OPERATION_FAILED,
    500,
    duration
  )
  throw error
}
```

### Monitoring Error Patterns

```typescript
function ErrorMonitor() {
  const errorStatus = useErrorMonitoring()

  return (
    <div>
      <p>Total Errors: {errorStatus.totalErrors}</p>
      <p>Recovery Rate: {errorStatus.recoveryRate}%</p>
      
      {errorStatus.topErrors.map(err => (
        <div key={err.code}>
          {err.code}: {err.count}
        </div>
      ))}
    </div>
  )
}
```

---

## Common Error Scenarios and Solutions

### Scenario 1: Offline User Sends Message

**Flow:**
1. User types message (UI optimistic)
2. Network unavailable
3. Request fails → queued
4. Message shows "⏳ Syncing..." badge
5. Network comes back
6. Queue flushes automatically
7. Badge removed, message confirmed

**Implementation:**
```typescript
async function sendMessage(text) {
  const msgId = addOptimisticMessage(text)
  
  try {
    await api.post('/api/chat', { text })
    confirmMessage(msgId)
  } catch (error) {
    if (error.queued) {
      markMessageAsQueued(msgId)
      // Auto-confirm when queue flushes
    } else {
      markMessageAsFailed(msgId)
    }
  }
}
```

### Scenario 2: API Server Crashes

**Flow:**
1. First request fails (network error)
2. Circuit breaker records failure
3. After 5 failures → circuit opens
4. Requests queued instead of sent
5. User sees: "Service temporarily unavailable"
6. Server comes back
7. Circuit tries recovery (HALF_OPEN)
8. Request succeeds
9. Circuit closes, queue flushes

**No code needed** — handled automatically by circuit breaker + queue

### Scenario 3: Rate Limited by API

**Flow:**
1. Many rapid requests
2. API returns 429 (rate limit)
3. Circuit breaker records failure
4. Request is queued
5. Queue uses exponential backoff
6. Retries after delay
7. Success when rate limit expires

**Implementation:**
```typescript
// Use debounce for user input
const debouncedSearch = debounce(
  (query) => api.post('/api/search', { query }),
  300 // 300ms debounce
)
```

### Scenario 4: Invalid Authentication

**Flow:**
1. Request sent with expired token
2. API returns 401
3. Interceptor detects 401
4. Token cleared
5. User redirected to login
6. NOT queued (401 not retryable)

**No code needed** — handled by auth interceptor

---

## Dos and Don'ts

### Do ✅

- **Do** use error codes for categorization
- **Do** show user-friendly messages from ERROR_METADATA
- **Do** let circuit breaker handle cascading failures
- **Do** let queue handle offline scenarios
- **Do** monitor error patterns with telemetry
- **Do** use optimistic updates for better UX
- **Do** provide manual retry buttons for critical actions
- **Do** log technical errors for debugging (not for users)

### Don't ❌

- **Don't** show technical error messages to users
- **Don't** implement manual retry loops (queue does this)
- **Don't** retry non-retryable errors (4xx, auth)
- **Don't** ignore network errors (let queue handle them)
- **Don't** forget to handle queued requests in UI
- **Don't** clear error state without user action
- **Don't** retry same error forever (use maxRetries)
- **Don't** overwhelm users with error notifications

---

## Testing Error Scenarios

### Simulate Network Offline

```typescript
// In browser console
navigator.onLine = false // Simulate offline
// Make requests - they'll be queued
navigator.onLine = true // Simulate online
// Queue auto-flushes
```

### Simulate Circuit Breaker Open

```typescript
import { getCircuitBreaker } from '@/utils/circuitBreaker'

const breaker = getCircuitBreaker('GET /api/test')
// Force 5 failures to open
for (let i = 0; i < 5; i++) {
  breaker.recordFailure()
}
// Next request will be queued
```

### Check Queue Status

```typescript
import { RequestQueue } from '@/utils/requestQueue'

const queue = RequestQueue.getInstance()
console.log(queue.getStats())
// { total: 3, byPriority: { HIGH: 2, NORMAL: 1 }, ... }
```

---

## Debugging Tips

### View All Errors

```typescript
import { telemetry } from '@/utils/telemetry'

// Get last 10 errors
const errors = telemetry.getEvents({ type: 'request_failed', limit: 10 })
console.table(errors)
```

### Export Telemetry Data

```typescript
import { telemetry } from '@/utils/telemetry'

const data = telemetry.export()
console.log(JSON.stringify(data, null, 2))

// Or use diagnostic dashboard
// Click "📥 Export Telemetry"
```

### Check Circuit Breaker State

```typescript
import { getAllCircuitBreakerStates } from '@/utils/circuitBreaker'

const states = getAllCircuitBreakerStates()
console.table(states)
// { 'POST /api/chat': 'OPEN', 'GET /api/settings': 'CLOSED', ... }
```

---

## Performance Considerations

1. **Minimal Telemetry Overhead**
   - Telemetry uses ~1KB per event
   - Events auto-cleanup (keep last 1000)
   - localStorage limited to 500 most recent events

2. **Queue Memory Usage**
   - ~500 bytes per queued request
   - Typical queue: 1-10 requests = 0.5-5KB
   - Large queue (1000 reqs) = 500KB max

3. **Circuit Breaker Efficiency**
   - O(1) state check
   - No performance impact on requests
   - Per-endpoint tracking

---

## Migration from Legacy Error Handling

### Before (Legacy)

```typescript
try {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
} catch (error) {
  console.error(error.message)
  alert('Something went wrong!')
}
```

### After (Resilience Layer)

```typescript
import { ErrorCode, ERROR_METADATA } from '@/utils/errorCodes'

try {
  const response = await api.get(url)
  // Automatically handles retries, queueing, circuit breaking
} catch (error) {
  const metadata = ERROR_METADATA[error.details?.errorCode]
  const message = metadata?.userMessage || 'An error occurred'
  showToast(message)
}
```

---

## Support and Troubleshooting

### "Request is stuck in queue"

Check queue status:
```typescript
const queue = RequestQueue.getInstance()
console.log(queue.getStats())
```

Manual flush:
```typescript
await queue.flush()
```

### "Circuit breaker won't close"

Check breaker state:
```typescript
const breaker = getCircuitBreaker('POST /api/endpoint')
console.log(breaker.getDiagnostics())
```

Manual reset:
```typescript
breaker.reset()
```

### "Can't see telemetry"

Open diagnostic dashboard:
```typescript
// In your app or dev tools
<DiagnosticDashboard expanded={true} />
```

---

## Further Reading

- [ERROR_CODE_REFERENCE.md](./ERROR_CODE_REFERENCE.md) — Complete error code catalog
- [PHASE4_IMPLEMENTATION_SUMMARY.md](../PHASE4_IMPLEMENTATION_SUMMARY.md) — Architecture details
- Diagnostic Dashboard — Built-in monitoring UI
