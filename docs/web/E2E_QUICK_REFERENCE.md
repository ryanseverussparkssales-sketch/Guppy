# E2E Testing - Quick Reference Card

## 🚀 Quick Start

```bash
cd web/

# Install & run
npm install
npx playwright install
npm run test:e2e
```

## 📋 Test Files

| File | Tests | Purpose |
|------|-------|---------|
| `auth.spec.ts` | 6 | JWT tokens, API connectivity, dev mode |
| `chat.spec.ts` | 8 | Message queueing, retry logic, persistence |
| `provider.spec.ts` | 8 | Provider switching, model selection |
| `model.spec.ts` | 10 | Model listing, routing, fallback logic |
| **Total** | **32** | End-to-end coverage |

## 🎮 Common Commands

```bash
# Run all E2E tests
npm run test:e2e

# Run with browser visible
npm run test:e2e:headed

# Run with debugger
npm run test:e2e:debug

# View test report
npm run test:e2e:report

# Run specific file
npx playwright test src/__tests__/e2e/chat.spec.ts

# Run with grep pattern
npx playwright test -g "should.*message"
```

## 🔍 Debug Commands

```bash
# Run with slowdown (easier to follow)
PLAYWRIGHT_SLOW_MO=1000 npx playwright test

# Run with trace
npx playwright test --trace on

# Show video on failure
npx playwright test --video on

# Headed + debug
npx playwright test --headed --debug
```

## 📊 CI/CD

```bash
# GitHub Actions setup (see E2E_TESTING.md)
CI=true npm run test:e2e

# With retries and artifacts
npx playwright test --retries 2
```

## 🎯 Key Features Tested

- ✅ JWT token storage & refresh
- ✅ Chat message queueing & retry
- ✅ Provider switching (local/cloud)
- ✅ Model selection & routing
- ✅ localStorage persistence
- ✅ Network error handling
- ✅ Exponential backoff timing
- ✅ API connectivity validation

## 🛠️ Configuration

**Location:** `web/playwright.config.ts`

Key settings:
- **Base URL:** `http://127.0.0.1:8081`
- **Timeout:** 30 seconds per test
- **Screenshots:** On failure only
- **Videos:** On failure only
- **Retries:** 0 local, 2 in CI

## 📚 Documentation

- **Full Guide:** `E2E_TESTING.md` (comprehensive)
- **Completion Report:** `TRANCHE_2_COMPLETION_SUMMARY.md` (details & benchmarks)
- **This File:** `E2E_QUICK_REFERENCE.md` (quick lookup)

## ⚠️ Common Issues

| Issue | Solution |
|-------|----------|
| `Connection refused` | Check API: `curl http://127.0.0.1:8081/api/status` |
| `Timeout errors` | Increase timeout in playwright.config.ts |
| `Selector not found` | Check DOM with `--headed` mode |
| `Flaky tests` | Run with `--retries 2` or `PLAYWRIGHT_SLOW_MO=500` |

## 📈 Performance

Expected times on modern hardware:
- Single test: ~1.5-2s
- Full suite: ~42s locally
- CI with retries: ~2:45

## 🔗 Related Files

- Test setup: `web/src/__tests__/` (also has Vitest unit tests)
- API client: `web/src/api/client.ts`
- Config: `web/playwright.config.ts`
- Package scripts: `web/package.json`

## 💡 Tips

1. Use `page.goto('/')` to navigate
2. Use `page.waitForLoadState('networkidle')` for async operations
3. Use `page.evaluate()` for localStorage/window access
4. Use `page.locator()` with multiple fallback selectors
5. Use `test.beforeEach()` to reset state

---

**Status:** ✅ Ready to use  
**Last updated:** 2026-04-25  
**Compatibility:** Playwright 1.59.1+
