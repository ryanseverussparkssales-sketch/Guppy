# Web UI Parity Assessment vs Desktop Launcher

**Date:** 2026-04-22  
**Goal:** Identify missing features to achieve full parity with desktop launcher  
**Target:** P6 compliance (dual web/desktop without conflicts)

---

## What is "Parity"?

Both interfaces should offer:
- Same available models and model sources
- Same workspace management
- Same chat history and context
- Same tool inventory and permissions
- Same admin/settings controls
- Shared state (what's true in one should be true in the other)

---

## Parity Assessment Matrix

### 1. Model Management

| Feature | Desktop Launcher | Web UI | Gap | Priority |
|---------|-----------------|--------|-----|----------|
| **View installed models** | ✅ Models Hub shows list | ❌ Hardcoded in API | HIGH | P0 |
| **Install new model** | ✅ One-click install | ❌ Not available | HIGH | P0 |
| **Uninstall model** | ✅ Remove from UI | ❌ Not available | HIGH | P0 |
| **Select active model (MAIN)** | ✅ Drag-drop or click | ⚠️ Partial (API only) | MEDIUM | P1 |
| **Sub-model selection (SUB A/B)** | ✅ Full routing control | ❌ Not available | MEDIUM | P1 |
| **Local model discovery** | ✅ Probes Ollama | ⚠️ Static config | MEDIUM | P1 |
| **Cloud provider selection** | ✅ OpenAI/Anthropic picker | ❌ API hardcoded | HIGH | P0 |
| **Model health/benchmarks** | ✅ Status indicators | ❌ Not visible | LOW | P2 |
| **Model installers** | ✅ Huggingface, LM Studio | ❌ Not available | MEDIUM | P1 |

**Gap Summary:**
- **P0 (Critical):** Model install/uninstall, provider switching
- **P1 (Important):** Model discovery, sub-selections, local detection
- **P2 (Nice-to-have):** Health indicators, benchmarks

---

### 2. Workspace Management

| Feature | Desktop | Web UI | Gap | Priority |
|---------|---------|--------|-----|----------|
| **Create workspace** | ✅ New workspace dialog | ❌ Not available | HIGH | P0 |
| **Switch workspace** | ✅ Topbar workspace cluster | ❌ Not available | HIGH | P0 |
| **Delete workspace** | ✅ Context menu | ❌ Not available | HIGH | P0 |
| **Rename workspace** | ✅ Inline rename | ❌ Not available | MEDIUM | P1 |
| **Workspace persistence** | ✅ Saved to database | ⚠️ Not shared | MEDIUM | P1 |
| **Context carry-over** | ✅ Files, notes in workspace | ⚠️ Partial (chat only) | MEDIUM | P1 |

**Gap Summary:**
- **P0:** Workspace CRUD operations
- **P1:** Persistence and sync across surfaces

---

### 3. Chat History & Context

| Feature | Desktop | Web UI | Gap | Priority |
|---------|---------|--------|-----|----------|
| **Chat history** | ✅ Searchable history | ⚠️ Session only | MEDIUM | P1 |
| **Persist conversations** | ✅ Saved to database | ❌ Lost on refresh | HIGH | P0 |
| **Attached files** | ✅ File browser, drag-drop | ⚠️ No file access | HIGH | P0 |
| **Context chips** | ✅ Visible in chat | ⚠️ Not visible in web | MEDIUM | P1 |
| **Message edit/delete** | ✅ Available | ❌ Not available | LOW | P2 |
| **Export conversation** | ✅ Available | ❌ Not available | LOW | P2 |

**Gap Summary:**
- **P0:** Conversation persistence, file access
- **P1:** Chat history search, context visibility
- **P2:** Message editing, export

---

### 4. Tool Management

| Feature | Desktop | Web UI | Gap | Priority |
|---------|---------|--------|-----|----------|
| **View available tools** | ✅ Tools Hub | ❌ Not visible | HIGH | P0 |
| **Enable/disable tool** | ✅ Toggle switches | ❌ Not available | MEDIUM | P1 |
| **Set tool permissions** | ✅ Per-tool controls | ❌ Not available | MEDIUM | P1 |
| **View tool status** | ✅ Health indicators | ❌ Not visible | MEDIUM | P1 |
| **Tool execution traces** | ✅ Recent invocations | ❌ Not available | LOW | P2 |
| **Add custom tool** | ✅ Advanced mode | ❌ Not available | LOW | P3 |

**Gap Summary:**
- **P0:** Tool visibility
- **P1:** Permissions and status
- **P2-P3:** Advanced features

---

### 5. Settings & Admin Controls

| Feature | Desktop | Web UI | Gap | Priority |
|---------|---------|--------|-----|----------|
| **API credentials** | ✅ Settings Hub | ❌ Not available | HIGH | P0 |
| **Model preferences** | ✅ Settings Hub | ⚠️ Partial | MEDIUM | P1 |
| **Voice settings** | ✅ Voice Hub | ❌ Not available | MEDIUM | P1 |
| **Diagnostics** | ✅ System health panel | ❌ Not available | MEDIUM | P1 |
| **Recovery tools** | ✅ Reset options | ❌ Not available | LOW | P2 |
| **Daemon controls** | ✅ Start/stop/restart | ❌ Not available | LOW | P2 |
| **Connector management** | ✅ Settings panel | ❌ Not available | MEDIUM | P1 |

**Gap Summary:**
- **P0:** Credentials management
- **P1:** Model/voice/connector settings, diagnostics
- **P2:** Recovery, daemon control

---

### 6. Library & Files

| Feature | Desktop | Web UI | Gap | Priority |
|---------|---------|--------|-----|----------|
| **File browser** | ✅ Approved root paths | ❌ Not available | HIGH | P0 |
| **Pinned notes** | ✅ Quick access | ❌ Not available | MEDIUM | P1 |
| **Media playback** | ✅ Audio/video in Library | ❌ Not available | LOW | P2 |
| **Use file in chat** | ✅ Drag-drop to Home | ⚠️ Copy-paste only | MEDIUM | P1 |
| **Save chat to Library** | ✅ One-click save | ❌ Not available | MEDIUM | P1 |

**Gap Summary:**
- **P0:** File access
- **P1:** Notes, integration with chat
- **P2:** Media features

---

## Feature Prioritization by Phase

### Phase 1: Critical Parity (P0 Features)
**Timeline:** Now - May 1, 2026  
**Goal:** Web UI achieves minimum viable feature parity

1. **Model Management (P0)**
   - [ ] Dynamic model list from Ollama (not hardcoded)
   - [ ] Cloud provider selection (OpenAI vs Anthropic)
   - [ ] View available models by source

2. **Workspace Management (P0)**
   - [ ] Create/switch/delete workspaces
   - [ ] Persist workspace context
   - [ ] Show active workspace

3. **Chat Persistence (P0)**
   - [ ] Save conversations to database
   - [ ] Restore on refresh
   - [ ] Show chat history

4. **Admin (P0)**
   - [ ] API credential input (OpenAI, Anthropic keys)
   - [ ] Provider selection interface

**Acceptance:** User can switch models, manage workspaces, and save chats on web UI same as desktop

---

### Phase 2: Important Parity (P1 Features)
**Timeline:** May 1 - May 22, 2026  
**Goal:** User experience reaches feature parity

1. **Advanced Model Control (P1)**
   - [ ] MAIN/SUB A/B routing
   - [ ] Local model installation/uninstall
   - [ ] Model health indicators

2. **Settings Integration (P1)**
   - [ ] Voice preferences
   - [ ] Connector management
   - [ ] System diagnostics

3. **Library & Files (P1)**
   - [ ] File browser with approved paths
   - [ ] File context in chat
   - [ ] Pinned notes

---

### Phase 3: Polish & Parity (P2 Features)
**Timeline:** May 22 - June 12, 2026  
**Goal:** Full feature parity, ready for freeze

1. **Advanced Controls (P2)**
   - [ ] Message edit/delete
   - [ ] Export conversations
   - [ ] Tool execution traces
   - [ ] Recovery tools

2. **Media & UX (P2)**
   - [ ] Media playback in Library
   - [ ] Media upload
   - [ ] Better file preview

---

## Implementation Roadmap

### Immediate Action Items (This Week)

**Backend API Enhancements:**

1. **Dynamic Model Discovery**
   ```
   GET /api/models
   Response: {
     "local_models": ["guppy", "guppy-fast", ...],
     "cloud_models": {
       "openai": ["gpt-4", "gpt-4o-mini"],
       "anthropic": ["claude-opus-4-6", "claude-haiku-4-5"]
     },
     "configured_provider": "local"
   }
   ```

2. **Workspace API**
   ```
   GET /api/workspaces
   POST /api/workspaces (create)
   PUT /api/workspaces/{id} (update)
   DELETE /api/workspaces/{id}
   ```

3. **Chat History**
   ```
   GET /api/chat/history/{workspace_id}
   POST /api/chat (save message with workspace context)
   ```

4. **Settings API**
   ```
   GET/POST /api/settings/credentials
   GET/POST /api/settings/preferences
   ```

**Frontend Components Needed:**

1. **Model Selector** (replaces hardcoded)
   - Dropdown with local + cloud models
   - Provider toggle
   - Install button (if available)

2. **Workspace Manager**
   - Dropdown to switch
   - "New workspace" dialog
   - Context display

3. **Chat History Sidebar**
   - List of saved conversations
   - Search
   - Delete option

4. **Settings Panel**
   - API credentials input
   - Provider selection
   - Preferences

---

## Shared State Architecture

### Current Problem

Web UI and desktop may show different:
- Active model (if changed in desktop, web doesn't know)
- Workspace (if switched on web, desktop doesn't sync)
- Credentials (if added in desktop settings, web can't use them)

### Solution: Centralized State

All state should come from **single source of truth** (backend API):

```
Desktop Launcher → API State → Web UI
   ↓                              ↓
Both sync with API, never local-only state
```

**Implementation:**
1. All settings stored in backend (`src/guppy/api/`)
2. Both UI surfaces read from same endpoints
3. Changes in one surface immediately visible in other
4. No local-only caching (use API as cache)

---

## Testing Strategy

### Manual Testing

1. **Desktop → Web Sync**
   - [ ] Switch model in desktop
   - [ ] Check web shows new model selected
   - [ ] Create workspace in desktop
   - [ ] Check workspace appears in web

2. **Web → Desktop Sync**
   - [ ] Add API key in web
   - [ ] Check desktop can use it
   - [ ] Switch workspace in web
   - [ ] Check desktop reflects change

3. **Simultaneous Operation**
   - [ ] Open desktop + web side-by-side
   - [ ] Change setting in one
   - [ ] Verify other refreshes
   - [ ] No conflicting state

### Automated Testing

- Add test: `test_web_desktop_model_sync.py`
- Add test: `test_web_desktop_workspace_sync.py`
- Add test: `test_shared_state_consistency.py`

---

## Success Criteria

**P6 Parity Acceptance:**
- [ ] Web UI can manage models (view, select, switch)
- [ ] Web UI can manage workspaces (create, switch, delete)
- [ ] Chat history persists across sessions
- [ ] Settings sync between web and desktop
- [ ] Both show same active model
- [ ] Both show same available tools
- [ ] File context works in web UI
- [ ] User can set API credentials in web
- [ ] No conflicting state between surfaces
- [ ] Release-check still passing

**P6 Deadline:** June 12, 2026

---

## Next Steps

1. **Confirm current Web UI baseline**
   - Run web UI locally and desktop side-by-side
   - Document what works, what's missing
   - Screenshot feature gaps

2. **API Improvements**
   - Enhance `/api/catalog` to include workspaces
   - Add workspace CRUD endpoints
   - Add chat history endpoints
   - Add settings endpoints

3. **Frontend Implementation**
   - Add model selector component
   - Add workspace switcher
   - Add settings panel
   - Add chat history sidebar

4. **State Sync Testing**
   - Test desktop → web sync
   - Test web → desktop sync
   - Test concurrent edits

---

## Appendix: Feature Comparison Table

**Quick Reference:**

| Category | Feature | Desktop | Web | Priority |
|----------|---------|---------|-----|----------|
| Models | View | ✅ | ❌ | P0 |
| Models | Install | ✅ | ❌ | P0 |
| Models | Switch | ✅ | ⚠️ | P0 |
| Workspaces | Create | ✅ | ❌ | P0 |
| Workspaces | Switch | ✅ | ❌ | P0 |
| Chat | History | ✅ | ❌ | P0 |
| Chat | Persist | ✅ | ❌ | P0 |
| Settings | Credentials | ✅ | ❌ | P0 |
| Tools | View | ✅ | ❌ | P1 |
| Files | Browse | ✅ | ❌ | P0 |
| Files | Attach | ✅ | ❌ | P0 |
| Admin | Diagnostics | ✅ | ❌ | P1 |
| Voice | Settings | ✅ | ❌ | P1 |

**Legend:**
- ✅ = Fully implemented
- ⚠️ = Partial/limited
- ❌ = Missing
- P0 = Critical for parity
- P1 = Important for parity
- P2 = Nice-to-have
