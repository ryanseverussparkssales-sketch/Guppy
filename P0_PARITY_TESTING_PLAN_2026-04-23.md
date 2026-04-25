# P0 Parity Testing Plan — 2026-04-23

**Status:** CRITICAL BLOCKER for P6 freeze-readiness (June 12 deadline)  
**Requirement:** Web UI and Desktop Launcher must use shared contracts, no inventory drift

---

## What We're Testing

From commit ff40fcb, P0 features are complete:
1. **Model Management** — Dynamic model discovery from Ollama
2. **Workspace Management** — CRUD + activation across surfaces
3. **Chat Persistence** — Scoped conversation history
4. **Settings/Credentials** — Provider selection and API key storage

**Critical question:** Do both launcher and Web UI agree on state?

---

## Test Setup

### Prerequisites
1. **Ollama running:** `http://127.0.0.1:11434` with models `fast`, `code`, `main` available
2. **Desktop launcher running:** `python src/guppy/cli/launch.py launcher`
3. **Web UI running:** `python src/guppy/cli/launch.py hub` or similar
4. **API running:** `python src/guppy/cli/launch.py api`
5. **Both windows visible side-by-side**

### Environment
```bash
GUPPY_DEV_MODE=1
GUPPY_JWT_SECRET=dev-secret-for-testing
```

---

## Test Plan

### **Section A: Model Inventory Parity**

#### A1. Model Discovery
**Step 1:** Check /providers endpoint (both should see same models)

```bash
# Terminal: Verify API returns clean aliases
curl -s http://localhost:8000/api/providers -H "X-Repair-Token: dev"
# Expected: "fast", "code", "main" only (not "guppy-fast", "guppy-code", etc.)
```

**Step 2:** Desktop launcher — Open Models hub
- [ ] Dropdown shows: fast, code, main
- [ ] No duplicate or old names (guppy-*, unversioned)

**Step 3:** Web UI — Open chat, ensure Local mode selected
- [ ] Model dropdown populated with: fast, code, main
- [ ] Same list as launcher

**Test Result:** ✅ / ❌  
**Notes:**

---

#### A2. Model Selection Consistency
**Step 4:** Launcher — Select "code" model, send test message

```json
{
  "message": "test",
  "model": "code"
}
```

- [ ] Message sent successfully
- [ ] Model name "code" in request log

**Step 5:** Web UI — Select "code" from dropdown, send test message
- [ ] Request includes `"model": "code"`
- [ ] Response uses code model (verify in logs)

**Step 6:** Launcher — Switch to "main", send message
- [ ] Model changes in next request
- [ ] No stale model state

**Test Result:** ✅ / ❌  
**Notes:**

---

### **Section B: Workspace Parity**

#### B1. Workspace CRUD
**Step 7:** API — Create workspace via endpoint

```bash
curl -X POST http://localhost:8000/api/workspaces \
  -H "Content-Type: application/json" \
  -H "X-Repair-Token: dev" \
  -d '{"name":"test-ws-1","description":"parity test"}'
```

**Step 8:** Launcher — Does workspace switcher show new workspace?
- [ ] Dropdown updated
- [ ] Can select and activate

**Step 9:** Web UI — Does workspace switcher show same?
- [ ] Dropdown matches launcher
- [ ] Can select and activate

**Test Result:** ✅ / ❌  
**Notes:**

---

#### B2. Workspace Activation
**Step 10:** Launcher — Activate test-ws-1
- [ ] UI reflects active workspace
- [ ] Note the workspace ID

**Step 11:** Web UI — Check active workspace
- [ ] Same workspace shown as active
- [ ] Can confirm via GET /api/workspaces

**Step 12:** Both — Send messages in workspace
- [ ] Chat history scoped to this workspace
- [ ] Verify via: `GET /api/chat/history?workspace_id=...`

**Test Result:** ✅ / ❌  
**Notes:**

---

### **Section C: Chat Persistence Parity**

#### C1. History Visibility
**Step 13:** Launcher — Create 3 conversations in test-ws-1
- [ ] Send different messages
- [ ] View history sidebar (if present)

**Step 14:** Web UI — Check chat history sidebar
- [ ] Same 3 conversations visible
- [ ] Same titles/timestamps
- [ ] Click restore—loads correct messages

**Step 15:** API — Verify database state

```bash
curl http://localhost:8000/api/chat/history?workspace_id=test-ws-1 \
  -H "X-Repair-Token: dev"
```

- [ ] Returns 3 conversations
- [ ] Matches both UIs' view

**Test Result:** ✅ / ❌  
**Notes:**

---

#### C2. Auto-Save Across Surfaces
**Step 16:** Launcher — Send message "test from launcher"
- [ ] Saved to workspace history

**Step 17:** Web UI — Open history, search for message
- [ ] Message appears in search results
- [ ] Can click to restore conversation

**Step 18:** Launcher — Refresh/reopen launcher
- [ ] Same conversation history visible

**Test Result:** ✅ / ❌  
**Notes:**

---

### **Section D: Settings/Credentials Parity**

#### D1. Provider Configuration
**Step 19:** Web UI — Go to Settings
- [ ] Provider dropdown shows: Local, Anthropic, OpenAI, Google
- [ ] Current active provider displayed

**Step 20:** API — Check settings state

```bash
curl http://localhost:8000/api/settings/provider \
  -H "X-Repair-Token: dev"
```

- [ ] Returns current active provider
- [ ] Matches Web UI display

**Step 21:** Launcher — (If settings exposed) check provider
- [ ] Same active provider
- [ ] Options match Web UI

**Test Result:** ✅ / ❌  
**Notes:**

---

#### D2. Credential Storage
**Step 22:** Web UI — Store test API key for Anthropic
- [ ] UI accepts input
- [ ] Confirmation message shown (no key exposed)

**Step 23:** API — Verify credential registered

```bash
curl http://localhost:8000/api/settings/credentials \
  -H "X-Repair-Token: dev"
```

- [ ] Returns credential status for Anthropic
- [ ] Does NOT return actual key

**Step 24:** Switch to Anthropic provider
- [ ] Web UI — Able to select and activate
- [ ] Launcher (if exposed) — shows option
- [ ] Chat should attempt Anthropic route (verify in logs)

**Test Result:** ✅ / ❌  
**Notes:**

---

## Critical Path: What Must Pass

| Feature | Must Work | Why |
|---------|-----------|-----|
| Model inventory match | ✅ | Else users see different models on each surface |
| Workspace state sync | ✅ | Else chat context lost when switching surfaces |
| Chat history visibility | ✅ | Else users can't access conversations |
| Provider switching | ✅ | Else can't fallback local→cloud |

---

## Failure Handling

**If any test fails:**
1. Document the exact discrepancy (e.g., "Launcher shows guppy-code but Web UI doesn't")
2. Check API response vs. UI state (data mismatch or display bug?)
3. Review filter logic in `routes_providers.py` (model filtering)
4. Check workspace scoping in `routes_workspaces.py`
5. Review useWorkspaces hook in Web UI

---

## Success Criteria

**All sections A–D pass** → P6 parity validation complete ✅  
**Ready for:** P1 feature work (May 1), freeze-readiness tranches, June 12 deadline

---

## Execution Notes

- Run tests in **development mode** (`GUPPY_DEV_MODE=1`)
- Keep API logs open to trace requests
- Use Postman/curl for endpoint verification
- Document screenshots of any discrepancies
- Update this doc with results

**Estimated time:** 45–60 minutes (full cycle)

---

**Next:** Start Section A (Model Inventory) now.
