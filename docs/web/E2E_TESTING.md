# Guppy E2E Testing Guide

This document describes how to run and develop Playwright E2E tests for the Guppy Web UI.

## Overview

The E2E test suite covers four key user flows:

- **auth.spec.ts** — JWT token handling, login flows, system status
- **chat.spec.ts** — Message sending, queueing, retry logic, persistence
- **provider.spec.ts** — Provider switching (local/anthropic/openai), model selection
- **model.spec.ts** — Model listing, selection, routing, fallback logic

## Prerequisites

### Local Environment
- Node.js ≥ 18.x
- Dependencies installed: `npm install` (in `web/` directory)
- Playwright browsers installed: `npx playwright install`

### Running Backend
The tests expect the Guppy API to be running on `http://127.0.0.1:8081`:

```powershell
# Terminal 1: Start the API server
python src/guppy/cli/launch.py api

# Terminal 2: Start LM Studio (or Ollama) for local model inference
# LM Studio: http://127.0.0.1:1234
# Ollama: http://127.0.0.1:11434
```

## Running Tests

### Run All E2E Tests
```bash
cd web/
npm run playwright
```

### Run Specific Test File
```bash
npx playwright test src/__tests__/e2e/auth.spec.ts
npx playwright test src/__tests__/e2e/chat.spec.ts
npx playwright test src/__tests__/e2e/provider.spec.ts
npx playwright test src/__tests__/e2e/model.spec.ts
```

### Run Tests with Debugging
```bash
# Run with visual debugging UI
npx playwright test --debug

# Run with tracing enabled (captures all network/DOM interactions)
npx playwright test --trace on

# Run in headed mode (browser visible)
npx playwright test --headed
```

### View Test Results
```bash
# Open the HTML report (created after test run)
npx playwright show-report
```

## Test Configuration

### playwright.config.ts
- **Base URL:** `http://127.0.0.1:8081` (Guppy API)
- **Test Directory:** `web/src/__tests__/e2e/`
- **Timeout:** 30 seconds per test
- **Screenshots/Videos:** Captured on failure
- **Retries:** 0 locally, 2 in CI

### Key Environment Variables
```bash
# Enable debug mode
PWDEBUG=1 npx playwright test

# Set custom base URL
PLAYWRIGHT_BASE_URL=http://localhost:8081 npx playwright test

# Slow down execution for observation
PLAYWRIGHT_SLOW_MO=1000 npx playwright test
```

## Test Coverage

### Auth Flow (auth.spec.ts)
- ✓ App loads and renders main UI
- ✓ JWT token stored/retrieved from localStorage
- ✓ Token persistence across page reloads
- ✓ System status endpoint validation
- ✓ Connected badge display
- ✓ Token refresh failure handling
- ✓ Dev mode API access

### Chat Flow (chat.spec.ts)
- ✓ Chat interface displays on load
- ✓ Message input accepts text
- ✓ Message queue persists to localStorage
- ✓ Stale messages (>1 hour) are cleaned up
- ✓ Network errors trigger retry queue
- ✓ Exponential backoff timing (1s → 2s → 4s)
- ✓ Toast notifications on permanent failure
- ✓ Message queue recovers after page reload

### Provider Selection (provider.spec.ts)
- ✓ Available providers display in UI
- ✓ Switch to local provider
- ✓ Provider selection persists across reloads
- ✓ Anthropic/OpenAI/Cohere/Mistral support
- ✓ POST request to `/providers/{p}/active-model`
- ✓ Active model returned in system status
- ✓ Circuit breaker prevents cascading failures
- ✓ Model list fetches from provider

### Model Selection (model.spec.ts)
- ✓ Models listed from backend API
- ✓ Model selector visible in UI
- ✓ User can select a specific model
- ✓ Selected model persisted to settings DB
- ✓ Model parameter sent in chat requests
- ✓ Graceful handling of unavailable models
- ✓ Model info in system status
- ✓ Model switching during conversation
- ✓ LM Studio and Ollama fallback logic

## CI/CD Integration

### GitHub Actions Example
```yaml
name: E2E Tests
on: [push, pull_request]
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '18'
      - run: npm ci
        working-directory: web/
      - run: npx playwright install --with-deps
        working-directory: web/
      - name: Start API (background)
        run: |
          cd ..
          python src/guppy/cli/launch.py api &
          sleep 5
      - run: npm run playwright
        working-directory: web/
      - uses: actions/upload-artifact@v3
        if: failure()
        with:
          name: playwright-report
          path: web/playwright-report/
```

## Troubleshooting

### Tests Fail: Connection Refused
- Verify API is running: `curl http://127.0.0.1:8081/api/status`
- Check port 8081 is not in use: `netstat -ano | findstr :8081`
- Restart API: `python src/guppy/cli/launch.py api`

### Tests Fail: Timeouts
- Increase timeout in `playwright.config.ts` if running on slow hardware
- Check network connectivity: `ping 127.0.0.1`
- Verify backend response time: `curl -w "%{time_total}\n" http://127.0.0.1:8081/api/status`

### Intermittent Failures
- Run with more retries: `npx playwright test --retries 3`
- Increase wait times: `PLAYWRIGHT_SLOW_MO=500 npx playwright test`
- Check for race conditions in chat queue tests

### Screenshot/Video Review
- Failed test artifacts saved in `playwright-report/`
- Open report: `npx playwright show-report`
- Screenshots and video clips available for each failed step

## Development Workflow

### Adding a New Test
1. Create test file: `web/src/__tests__/e2e/feature.spec.ts`
2. Import test utilities:
   ```typescript
   import { test, expect, Page } from '@playwright/test'
   ```
3. Structure with `test.describe()` and `test()` blocks
4. Use `test.beforeEach()` and `test.afterEach()` for setup/teardown
5. Run: `npx playwright test src/__tests__/e2e/feature.spec.ts`

### Common Patterns

#### Waiting for Navigation
```typescript
await page.goto('/')
await page.waitForLoadState('networkidle')
```

#### Filling Forms
```typescript
const input = page.locator('input[placeholder="Search"]')
await input.fill('test query')
await input.press('Enter')
```

#### Intercepting API Calls
```typescript
const requestPromise = page.waitForRequest(
  (request) => request.url().includes('/chat') && request.method() === 'POST'
)
// Trigger action...
const request = await requestPromise
expect(request.postDataJSON()).toHaveProperty('message')
```

#### Checking localStorage
```typescript
const token = await page.evaluate(() => localStorage.getItem('token'))
expect(token).toBe('expected-value')
```

## Known Limitations

- Tests do NOT require a real authentication token (dev mode disabled checks in playwright config)
- Tests assume LM Studio or Ollama may or may not be running (graceful fallback)
- Chat message sending test may not trigger actual response (depends on backend state)
- Provider/model switching tests are partially UI-dependent (exact selectors vary by theme)

## Performance Benchmarks

Expected test execution times (full suite, local machine):

- **auth.spec.ts:** ~8 seconds (6 tests)
- **chat.spec.ts:** ~12 seconds (8 tests)
- **provider.spec.ts:** ~10 seconds (8 tests)
- **model.spec.ts:** ~12 seconds (10 tests)
- **Total:** ~42 seconds for full E2E suite

On CI (with retries): ~2 minutes

## Related Documentation

- **Playwright Docs:** https://playwright.dev
- **Vitest (Unit Tests):** `web/src/__tests__/` (MarkdownMessage.test.tsx)
- **API Documentation:** `src/guppy/api/` (routes, schemas)
- **Project Brief:** `docs/PROJECT_BRIEF.md`
