# Web UI Complete Rewire & Integration Plan
## Focus: Chat Persistence + Settings + State Management
**Date:** 2026-04-22 | **Status:** Execution Ready

---

## 📊 Current State Assessment

### API Integration Status
From debugging session:
- ✅ API running on `http://127.0.0.1:8081`
- ✅ CORS enabled (wildcard in dev mode)
- ✅ Auth bypass working (dev-user)
- ✅ Client baseURL correct: `http://127.0.0.1:8081`
- ✅ API endpoints exist: `/api/chat/history`, `/api/settings`, `/api/providers`
- ✅ Network calls returning 200 OK (except status 404 - non-critical)

### Web UI Current Issues
- ❌ **Chat persistence broken** - Messages not saving to DB
- ❌ **Settings broken** - Click handlers don't work, no state sync
- ❌ **No state management** - No Zustand/Redux, hooks disconnected from UI
- ❌ **Components not calling hooks** - Data fetched but not displayed
- ❌ **Missing chat UI** - No message display, no conversation sidebar working properly

### Component Structure
```
web/src/
├── views/
│   ├── AssistantView.tsx        ← Chat interface (BROKEN - not showing messages)
│   ├── SettingsView.tsx         ← Settings (BROKEN - click handlers don't work)
│   ├── AdvancedAssistantView.tsx
│   ├── AdminPanel.tsx
│   ├── DashboardView.tsx
│   └── InstancesView.tsx
├── components/
│   ├── chat/
│   │   └── ChatHistorySidebar.tsx  ← Conversation list (needs wiring)
│   ├── layout/
│   │   ├── AppShell.tsx
│   │   ├── Sidebar.tsx
│   │   ├── TopBar.tsx
│   │   └── CommandPalette.tsx
│   └── ui/                        ← shadcn/ui components (button, input, card, etc.)
├── hooks/
│   ├── useSettings.ts            ← Settings hook (partially wired)
│   ├── useChatHistory.ts         ← Chat hook (not wired to UI)
│   └── useTheme.ts
├── api/
│   └── client.ts                 ← Axios config (FIXED - correct baseURL)
└── App.tsx                       ← Root component (doesn't initialize state)
```

---

## 🎯 Execution Strategy: 3-Phase Implementation

### **PHASE 1: State Management Foundation (2-3 hours)**
Create the central nervous system before wiring components.

#### Task 1.1: Create Zustand Store
**File:** `web/src/store/appStore.ts`

```typescript
// Central state management for:
// - Chat conversations and messages
// - Settings and credentials
// - Workspace selection
// - UI state (sidebar, theme, modals)
// - Sync status (loading, errors, timestamps)

Key selectors:
- getConversations() → conversation list
- getActiveConversation() → current chat
- getMessages(convId) → messages in conversation
- getSettings() → provider config
- getActiveProvider() → current model
- getSyncStatus() → { loading, error, lastSync }
```

**Tools to use:**
- `web-artifacts-builder` skill to scaffold the store architecture
- TypeScript interfaces for type safety

#### Task 1.2: Create API Sync Manager
**File:** `web/src/store/syncManager.ts`

Purpose: Orchestrate data flow between UI, Zustand store, and API
- Debounce rapid updates (100ms)
- Handle errors gracefully
- Retry failed requests
- Show loading/error states

**Methods:**
```
- fetchConversations(workspaceId)     → API → Store
- createConversation(title)            → API → Store
- addMessage(convId, text)             → API → Store + optimistic UI
- saveSettings(settings)               → API → Store
- setActiveProvider(provider)          → API → Store
- retryFailedRequest(requestId)        → API → Store
```

#### Task 1.3: Add Zustand Store Initialization
**File:** `web/src/App.tsx` (modify)

On app load:
1. Check localStorage for workspace ID
2. Call `syncManager.fetchConversations(workspaceId)`
3. Call `syncManager.getSettings()`
4. Initialize store with loaded data
5. Subscribe to store changes

---

### **PHASE 2: Component Wiring (3-4 hours)**
Connect UI components to the store and API.

#### Task 2.1: Fix AssistantView (Chat Interface)
**File:** `web/src/views/AssistantView.tsx` (rewrite)

Current state: 
- Probably renders something but doesn't show messages
- Doesn't load conversations on mount
- No hook to fetch messages

Changes needed:
1. **Import hooks:** `useAppStore`, `useSyncManager`
2. **On mount:** Load conversations and active conversation
3. **Message display:** Map store.getMessages() to UI
4. **Message input:** Call `syncManager.addMessage()` on send
5. **Loading states:** Show spinner while syncManager.loading
6. **Error states:** Display error messages from store

```typescript
Key state needed:
- conversations: Conversation[]           ← from store
- activeConversation: Conversation | null ← from store  
- messages: Message[]                     ← from store.getMessages()
- loading: boolean                        ← from syncManager.loading
- error: string | null                    ← from syncManager.error
- inputValue: string                      ← local state
- isSending: boolean                      ← local state while API call pending
```

**UI Structure:**
```
AssistantView
├── ChatHistorySidebar (left)
│   └── List of conversations (click to switch)
├── ChatPanel (main)
│   ├── Conversation header (title + options)
│   ├── Messages display
│   │   └── Map messages to Message components
│   ├── Loading spinner (while loading)
│   └── Error message (if failed)
└── MessageInput (bottom)
    ├── Input field
    └── Send button
```

#### Task 2.2: Fix SettingsView (Provider Configuration)
**File:** `web/src/views/SettingsView.tsx` (rewrite sections)

Current state:
- Renders provider cards but clicks don't work
- Shows UI but doesn't sync with store

Changes needed:
1. **Import hooks:** `useAppStore`, `useSyncManager`
2. **On mount:** Load settings from store
3. **Provider cards:** Map store.getSettings().credentials to UI
4. **Activate button:** Call `syncManager.setActiveProvider(provider)`
5. **Credential input:** Call `syncManager.saveSettings()`
6. **Loading/error states:** Show proper feedback

```typescript
Key state:
- settings: Settings         ← from store
- credentials: Credentials   ← from store.getSettings()
- activeProvider: Provider   ← from store.getActiveProvider()
- loading: boolean           ← from syncManager
- error: string | null       ← from syncManager
- forms: {[provider]: string}← local state for API key inputs
```

**Critical fix:**
The issue "doesn't allow clicks" is likely because:
1. Button handlers exist but component doesn't refresh after API call
2. OR store isn't being updated on successful save

Solution:
```typescript
const handleActivateProvider = async (provider: Provider) => {
  try {
    await syncManager.setActiveProvider(provider)
    // Store auto-updates via subscription
    // UI re-renders via store selector change
    showSuccessToast(`Switched to ${provider}`)
  } catch (err) {
    showErrorToast(`Failed to switch provider`)
  }
}
```

#### Task 2.3: Fix ChatHistorySidebar
**File:** `web/src/components/chat/ChatHistorySidebar.tsx` (modify)

Current state:
- Probably doesn't load conversations
- No click handler to switch conversations

Changes:
1. **Import:** `useAppStore`
2. **On mount:** Already handled by App.tsx loading conversations
3. **Display conversations:** Map `store.getConversations()` to list
4. **Handle click:** Call `setActiveConversation(id)` in store
5. **Highlight active:** Visual indicator for `activeConversation`

```typescript
Needs:
- conversations: store.getConversations()
- activeId: store.getActiveConversation().id
- onSelect: (id) => store.setActiveConversation(id)
- onDelete: (id) => syncManager.deleteConversation(id)
- onNewChat: () => syncManager.createConversation()
```

#### Task 2.4: Fix MessageInput Component
**File:** `web/src/components/chat/MessageInput.tsx` (create if missing)

This component needs to:
1. Accept `conversationId` prop
2. Have text input + send button
3. On send: Call `syncManager.addMessage(conversationId, text)`
4. Show loading state during API call
5. Clear input on success
6. Show error if failed

```typescript
Props:
- conversationId: string
- onMessageSent?: () => void
- disabled?: boolean

State:
- inputValue: string
- isSending: boolean
```

---

### **PHASE 3: Integration & Testing (2-3 hours)**

#### Task 3.1: Full Data Flow Verification

**Chat Persistence Flow:**
```
User types "Hello" → sends message
    ↓
MessageInput.onSend() calls syncManager.addMessage()
    ↓
syncManager makes POST /api/chat/history/{convId}/messages
    ↓
Backend saves message to chat_history.db
    ↓
Backend returns {success: true, message: {...}}
    ↓
syncManager updates store.messages
    ↓
AssistantView re-renders, shows new message
    ↓
User refreshes page (F5)
    ↓
App.tsx loads store from API again
    ↓
Message still visible ✅
```

**Settings Persistence Flow:**
```
User clicks "Activate" on Anthropic
    ↓
SettingsView calls syncManager.setActiveProvider("anthropic")
    ↓
syncManager makes POST /api/settings/provider
    ↓
Backend saves provider to settings.db
    ↓
Backend returns {success: true, provider: "anthropic"}
    ↓
syncManager updates store.activeProvider
    ↓
SettingsView re-renders, shows "Current" badge ✅
```

#### Task 3.2: Error Scenarios
Test these scenarios:
1. **API unreachable** - syncManager catches error, shows toast
2. **Invalid input** - API returns 400, syncManager shows validation error
3. **Offline** - syncManager queues request, retries on reconnect
4. **Concurrent edits** - Last write wins (or implement conflict resolution)

#### Task 3.3: Manual Test Checklist
```
Chat Persistence:
☐ Create new conversation → appears in sidebar
☐ Send message → appears in chat
☐ Refresh page → message still there
☐ Switch conversations → shows correct messages
☐ Delete conversation → removed from sidebar and DB

Settings:
☐ Click "Activate" on Local → shows "Current" badge
☐ Save API key → shows "Configured" badge
☐ Refresh page → credentials still configured
☐ Error on invalid key → shows error message

Loading States:
☐ Show spinner while fetching conversations
☐ Show spinner while sending message
☐ Show spinner while saving settings
☐ Show error if API call fails

UI Polish:
☐ Buttons are clickable
☐ Toasts appear for success/error
☐ No console errors
☐ No 404 errors in Network tab (except status endpoint)
```

---

## 📋 Files to Create/Modify (In Order)

### **Critical Path (Do these first)**

1. ✅ **web/src/store/appStore.ts** (NEW)
   - Zustand store with chat, settings, workspace state
   - Selectors: getConversations, getMessages, getSettings, etc.
   - Time: 45 min

2. ✅ **web/src/store/syncManager.ts** (NEW)
   - Orchestrate API calls and store updates
   - Handle errors, retries, loading states
   - Time: 45 min

3. ✅ **web/src/App.tsx** (MODIFY)
   - Initialize store on mount
   - Load conversations + settings
   - Subscribe to store changes
   - Time: 30 min

4. ✅ **web/src/views/AssistantView.tsx** (REWRITE SECTIONS)
   - Wire to useAppStore hook
   - Display messages from store
   - Call syncManager.addMessage() on send
   - Time: 60 min

5. ✅ **web/src/views/SettingsView.tsx** (REWRITE SECTIONS)
   - Wire to useAppStore hook
   - Fix click handlers
   - Call syncManager.setActiveProvider()
   - Time: 45 min

6. ✅ **web/src/components/chat/ChatHistorySidebar.tsx** (MODIFY)
   - Load conversations from store
   - Handle conversation selection
   - Time: 30 min

7. ✅ **web/src/components/chat/MessageInput.tsx** (CREATE)
   - Message input + send button
   - Call syncManager.addMessage()
   - Time: 30 min

### **Supporting Files (For later refinement)**

8. web/src/hooks/useAppStore.ts (wrapper hook)
9. web/src/hooks/useSyncManager.ts (wrapper hook)
10. web/src/hooks/useChatHistory.ts (refactor existing)
11. web/src/hooks/useSettings.ts (refactor existing)
12. web/src/types/index.ts (update interfaces)

---

## 🛠️ Tools & Skills to Use

### **Skill: web-artifacts-builder**
- Scaffold complex components (AssistantView, SettingsView)
- Test component logic before putting in project
- Generate TypeScript interfaces

### **Skill: design:design-system**
- Audit component consistency
- Document design patterns
- Ensure button/input/card usage is consistent

### **Skill: design:design-critique**
- Review UI layouts for usability
- Check if chat/settings interface makes sense

### **Tool: Read/Write/Edit**
- Read existing component code to understand current structure
- Write new store/sync manager files
- Edit existing components to wire hooks

### **Tool: Bash**
- Run tests to verify components work
- Check for console errors
- Inspect Network tab via curl tests

---

## ⚠️ Critical Implementation Notes

### Data Flow Rules
1. **All mutations through syncManager** - Never mutate store directly
2. **API as source of truth** - Store is local cache of API state
3. **Optimistic updates** - Show message in UI before API confirms
4. **Conflict resolution** - If offline edit conflicts with server, retry or merge

### Error Handling
1. **Network error** → Show toast + queue for retry
2. **Validation error (400)** → Show form error message
3. **Not found (404)** → Show "Resource not found" toast
4. **Server error (500)** → Show generic "Server error" + retry button

### Performance Considerations
1. **Debounce** rapid store updates (100ms)
2. **Memoize** selectors to prevent unnecessary re-renders
3. **Lazy load** conversation messages (pagination)
4. **Cache** API responses with SWR if needed

### Testing Strategy
1. **Unit tests** for syncManager (API call logic)
2. **Component tests** for AssistantView, SettingsView
3. **Integration tests** for full data flow
4. **Manual smoke test** checklist (see Phase 3)

---

## 📅 Timeline Estimate

| Phase | Task | Time | Dependency |
|-------|------|------|-----------|
| 1 | Create appStore.ts | 45 min | None |
| 1 | Create syncManager.ts | 45 min | appStore |
| 1 | Modify App.tsx | 30 min | appStore, syncManager |
| 2 | Rewrite AssistantView | 60 min | Phase 1 complete |
| 2 | Rewrite SettingsView | 45 min | Phase 1 complete |
| 2 | Modify ChatHistorySidebar | 30 min | Phase 1 complete |
| 2 | Create MessageInput | 30 min | Phase 1 complete |
| 3 | Integration testing | 90 min | Phase 2 complete |
| **TOTAL** | | **5-6 hours** | **1 day** |

---

## ✅ Success Criteria

### Minimum Viable (P0)
- [ ] Conversations load from API on app start
- [ ] New conversation saves to DB
- [ ] Message persists to DB on send
- [ ] Page refresh shows saved messages
- [ ] Provider activation saves to DB
- [ ] No console errors

### Nice to Have (P1)
- [ ] Optimistic updates (message appears immediately)
- [ ] Offline queue (requests retry when online)
- [ ] Loading spinners on all async operations
- [ ] Error toasts for failures
- [ ] Conversation search/filter

---

## 🚨 Known Issues to Avoid

1. **React state batching** - Use `flushSync` if needed for immediate updates
2. **Stale closures** - useCallback dependencies must include store selectors
3. **Infinite loops** - fetchConversations in useEffect needs proper dependencies
4. **Race conditions** - syncManager must deduplicate concurrent requests
5. **CORS errors** - Keep baseURL as `http://127.0.0.1:8081` (not `/api`)

---

## 📞 Quick Reference: API Endpoints

```bash
# Chat History
GET  /api/chat/history?workspace_id=X&limit=50&offset=0
POST /api/chat/history                                          # Create conversation
GET  /api/chat/history/{conv_id}                               # Get conversation
PUT  /api/chat/history/{conv_id}                               # Update title
DELETE /api/chat/history/{conv_id}                             # Delete
POST /api/chat/history/{conv_id}/messages                      # Add message

# Settings
GET  /api/settings                                              # Get all settings
GET  /api/settings/credentials                                 # Get provider status
POST /api/settings/credentials                                 # Save API key
DELETE /api/settings/credentials/{provider}                    # Delete credential
GET  /api/settings/provider                                    # Get active provider
POST /api/settings/provider                                    # Set active provider
```

---

**Next Step:** Ready to execute Phase 1 (State Management). Shall we start with appStore.ts?
