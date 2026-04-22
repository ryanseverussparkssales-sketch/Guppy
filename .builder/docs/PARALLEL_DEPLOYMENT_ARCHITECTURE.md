# Guppy Parallel Deployment Architecture

## Overview

This document outlines the strategy for deploying both a refactored **desktop UI** and a modern **web UI** simultaneously, sharing a common **API service layer**.

**Timeline**: 4-6 weeks  
**Tracks**: A (Desktop Refactoring) + B (Web UI Development) running in parallel

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Guppy Platform                       │
├────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────┐           ┌──────────────────┐    │
│  │  Desktop UI      │           │  Web UI          │    │
│  │  (PySide6/Qt)    │           │  (React/TS)      │    │
│  │                  │           │                  │    │
│  │  - Refactored    │           │  - Modern        │    │
│  │  - Services      │           │  - Responsive    │    │
│  │  - State mgmt    │           │  - Real-time     │    │
│  └────────┬─────────┘           └────────┬─────────┘    │
│           │                              │                │
│           └──────────────────┬───────────┘                │
│                              │                            │
│  ┌───────────────────────────▼──────────────────────┐   │
│  │   Shared API Service Layer                       │   │
│  │   (src/guppy/api/service.py)                    │   │
│  │                                                   │   │
│  │  - GuppyAPIClient                               │   │
│  │  - WorkspaceService                             │   │
│  │  - ModelsService                                │   │
│  │  - AssistantService                             │   │
│  │  - LibraryService                               │   │
│  │  - SettingsService                              │   │
│  │  - Structured error handling                    │   │
│  │  - Real-time update callbacks                   │   │
│  └───────────────────────────┬──────────────────────┘   │
│                              │                            │
│  ┌───────────────────────────▼──────────────────────┐   │
│  │   FastAPI Backend                                │   │
│  │   (src/guppy/runtime_api/)                       │   │
│  │                                                   │   │
│  │  - Workspace endpoints                          │   │
│  │  - Model management                             │   │
│  │  - Chat/assistant endpoints                     │   │
│  │  - Library endpoints                            │   │
│  │  - Settings endpoints                           │   │
│  │  - WebSocket for real-time updates              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## Track A: Desktop UI Refactoring

### Goals
1. Refactor monolithic `LauncherWindow` into modular services
2. Centralize state management
3. Improve error handling and async safety
4. Prepare desktop UI to use shared API layer

### Key Changes

#### 1. Service Architecture
Move from controller-heavy to service-based:

```
LauncherWindow (composition root only)
├── StateManager (centralized state)
├── ShellController (layout & navigation)
├── StartupService (initialization)
├── PollingService (health checks)
└── SyncService (backend sync)
```

#### 2. StateManager
Replaces 50+ mutable widget attributes with structured state.

```python
@dataclass
class LauncherState:
    # Session
    active_instance: str
    chat_session_id: str
    
    # Workspaces
    instances: list[Workspace]
    instance_snapshots: dict[str, dict]
    
    # Models
    active_model: Optional[Model]
    models: list[Model]
    runtime_status: RuntimeStatus
    
    # Chat
    messages: list[Message]
    pending_context: Optional[dict]
    
    # Library
    library_items: list[LibraryItem]
    active_context: list[str]
    
    # Settings
    settings: UserSettings
    
    # Startup
    startup_phase: str
    startup_complete: bool
    
    # Health
    is_healthy: bool
    last_poll: datetime
```

#### 3. Service Responsibilities

**StateManager**
- Single source of truth for all mutable state
- Snapshot invalidation
- Queue management
- Type-safe state access

**ShellController**
- UI layout assembly
- Navigation and tab management
- Sidebar/topbar/panel coordination
- Focus and visibility management

**StartupService**
- Boot sequence orchestration
- Phase timing and tracking
- Initial feature bootstrap
- Readiness signals

**PollingService**
- Periodic health checks
- Status updates
- Queue draining
- First-poll detection

**SyncService**
- Snapshot fetching and caching
- Backend requests
- Library context persistence
- Connector coordination

#### 4. Error Handling Improvements

```python
class DesktopErrorHandler:
    """Structured error reporting for desktop UI"""
    
    async def handle_error(self, error: Exception, context: str):
        # Log structured error
        logger.error(
            "operation_failed",
            exc_info=error,
            context=context,
            subsystem="desktop_ui",
        )
        
        # Convert to user-facing error
        user_message = self.humanize(error)
        severity = self.classify_severity(error)
        
        # Show in UI
        self.status_panel.show_error(
            message=user_message,
            severity=severity,
            dismissible=True,
            retry_callback=retry_fn if recoverable else None,
        )
```

#### 5. Async Safety

```python
class RequestCoordinator:
    """Manage concurrent requests safely"""
    
    def __init__(self):
        self.active_requests: dict[str, AsyncRequest] = {}
        self.generation_token = 0
    
    async def make_request(self, key: str, coro):
        token = self.generation_token
        request = AsyncRequest(token, coro)
        self.active_requests[key] = request
        
        try:
            return await coro
        except Exception as e:
            if request.generation == self.generation_token:
                # Not stale, report error
                raise
            # Stale request, silently ignore
        finally:
            del self.active_requests[key]
```

### Implementation Timeline

**Week 1**: Extract StateManager, split LauncherWindow  
**Week 2**: Implement service classes  
**Week 3**: Rewire signals, update tests  
**Week 4**: Error handling, async safety  

---

## Track B: Web UI Development

### Goals
1. Create modern, responsive React/TypeScript UI
2. Match Stitch design system
3. Real-time updates via WebSocket
4. Production-grade quality

### Tech Stack

```json
{
  "framework": "React 18",
  "language": "TypeScript 5",
  "state": "Zustand with Immer",
  "styling": "CSS-in-JS with custom theme",
  "routing": "React Router 6",
  "http": "Axios",
  "build": "Vite",
  "testing": "Vitest"
}
```

### Structure

```
web/
├── src/
│   ├── components/
│   │   ├── Sidebar.tsx
│   │   ├── TopBar.tsx
│   │   ├── StatusPanel.tsx
│   │   ├── ContentArea.tsx
│   │   ├── Chat/
│   │   ├── Library/
│   │   ├── Models/
│   │   ├── Settings/
│   │   └── Workspace/
│   ├── layout/
│   │   └── MainLayout.tsx
│   ├── pages/
│   │   ├── Assistant.tsx
│   │   ├── Library.tsx
│   │   ├── Models.tsx
│   │   ├── Settings.tsx
│   │   └── Workspace.tsx
│   ├── hooks/
│   │   ├── useAppState.ts
│   │   ├── useAPI.ts
│   │   └── useWebSocket.ts
│   ├── services/
│   │   └── api.ts (uses src/guppy/api/service.py)
│   ├── styles/
│   │   └── theme.ts (Stitch tokens)
│   ├── types/
│   │   └── api.ts (shared with Python)
│   └── App.tsx
├── tailwind.config.js
├── vite.config.ts
└── package.json
```

### Key Components

**Sidebar**
- Navigation routes
- Workspace switcher
- Collapse/expand
- Real-time status indicators

**TopBar**
- Global search
- Instance selector
- Runtime status
- Notification badge

**ContentArea**
- Route-based page rendering
- Loading/error states
- Responsive layout

**StatusPanel**
- Right-side drawer
- Quick tools
- Status messages
- Real-time updates

### State Management

Using Zustand for simplicity and type-safety:

```typescript
const useAppStore = create<AppState & AppActions>((set) => ({
  // State
  workspaces: [],
  activeWorkspace: undefined,
  messages: [],
  
  // Actions
  fetchWorkspaces: async () => {
    // Calls shared API layer
    const response = await apiClient.workspaces.get_instances();
    set({ workspaces: response.data });
  },
  
  sendMessage: async (content) => {
    // Add to local state optimistically
    // API layer handles sync
  },
}));
```

### Real-time Updates

```typescript
useEffect(() => {
  const api = getApiClient();
  
  // Subscribe to events
  api.subscribe("messages", (message) => {
    useAppStore.setState(state => ({
      messages: [...state.messages, message]
    }));
  });
  
  api.subscribe("status", (status) => {
    useAppStore.setState({ runtimeStatus: status });
  });
  
  return () => {
    api.unsubscribe("messages", callback);
    api.unsubscribe("status", callback);
  };
}, []);
```

### Implementation Timeline

**Week 1**: Layout, components, styling  
**Week 2**: Page implementations, state integration  
**Week 3**: Real-time updates, WebSocket  
**Week 4**: Polish, responsive design, testing  

---

## Shared API Service Layer

### File: `src/guppy/api/service.py`

Unified interface for both UIs:

```python
# Synchronous usage (desktop)
api = GuppyAPIClient()
response = api.workspaces.get_instances()

# Async usage (web)
api = GuppyAPIClient()
response = await api.workspaces.get_instances()

# Real-time subscription (both)
api.subscribe("status", callback)
```

### Error Handling

Consistent error model across both UIs:

```python
APIError(
    code="WORKSPACE_FETCH_FAILED",
    message="Failed to fetch workspace instances",
    severity=ErrorSeverity.ERROR,
    details={"error": str(e)},
    timestamp=datetime.utcnow().isoformat(),
)
```

### Services

- **WorkspaceService**: Instance/workspace CRUD
- **ModelsService**: Model discovery, runtime status
- **AssistantService**: Chat, conversation history
- **LibraryService**: Artifacts, notes, files
- **SettingsService**: User preferences, configuration

---

## Integration Points

### 1. Type Sharing

Python -> TypeScript:
```python
# src/guppy/api/service.py
@dataclass
class Workspace:
    id: str
    name: str
    type: str
```

Generate TypeScript:
```typescript
// web/src/types/api.ts (manual or generated)
export interface Workspace {
  id: string;
  name: string;
  type: string;
}
```

### 2. API Endpoint Mapping

Desktop (async or sync):
```python
# Uses same service layer
response = await api.workspaces.get_instances()
```

Web (async):
```typescript
// Also uses same service layer via Python backend
const response = await apiClient.workspaces.get_instances();
```

### 3. WebSocket Real-time Updates

Both UIs subscribe to events:
```python
api.subscribe("messages", callback)
api.subscribe("status", callback)
```

Backend broadcasts updates:
```python
async def on_message_received(message):
    await api._emit_update("messages", message)
```

---

## Testing Strategy

### Desktop UI Tests

```python
# tests/unit/test_state_manager.py
def test_state_manager_workspace_update():
    state = StateManager()
    state.set_active_workspace(workspace)
    assert state.active_workspace == workspace

# tests/integration/test_desktop_api_client.py
async def test_desktop_api_workspace_sync():
    api = GuppyAPIClient()
    response = api.workspaces.get_instances()
    assert response.success
```

### Web UI Tests

```typescript
// web/src/__tests__/hooks/useAppState.test.ts
test('fetchWorkspaces updates state', async () => {
  const { result } = renderHook(() => useAppStore());
  await act(async () => {
    await result.current.fetchWorkspaces();
  });
  expect(result.current.workspaces).toHaveLength(2);
});

// web/src/__tests__/components/Sidebar.test.tsx
test('Sidebar renders navigation items', () => {
  render(<Sidebar />);
  expect(screen.getByText('Assistant')).toBeInTheDocument();
});
```

### Integration Tests

```python
# tests/integration/test_parallel_ui_api.py
async def test_desktop_and_web_ui_share_state():
    """Both UIs should see same data from API"""
    desktop_api = GuppyAPIClient("http://localhost:8000")
    
    # Desktop makes request
    response = desktop_api.workspaces.get_instances()
    workspaces_v1 = response.data
    
    # Web makes same request
    web_response = await web_api.workspaces.get_instances()
    workspaces_v2 = web_response.data
    
    # Should be identical
    assert workspaces_v1 == workspaces_v2
```

---

## Deployment

### Development Setup

```bash
# Install dependencies
pip install -e .
npm install --prefix web

# Run backend
python -m uvicorn src.guppy.runtime_api.main:app --reload

# Run desktop UI (existing)
python guppy_launcher.py

# Run web UI
npm run dev --prefix web
```

### Production Deployment

```bash
# Build web UI
npm run build --prefix web

# Serve via FastAPI
# (index.html served from static/ directory)

# Desktop: Single executable
pyinstaller guppy_launcher.spec
```

---

## Success Criteria

### Desktop UI
- [ ] LauncherWindow < 1000 lines (was 2500+)
- [ ] 100% of handlers use error model
- [ ] All async operations have cancellation
- [ ] State mutations only via StateManager
- [ ] Test coverage > 80%

### Web UI
- [ ] All pages implemented and tested
- [ ] Responsive on mobile/tablet/desktop
- [ ] Real-time updates working
- [ ] Offline support (queuing)
- [ ] Build size < 300KB (gzipped)

### Integration
- [ ] Both UIs use same API layer
- [ ] Error handling consistent
- [ ] Type definitions shared
- [ ] All E2E tests passing
- [ ] Zero data corruption scenarios

---

## Risk Mitigation

### Desktop Refactoring
- Start with StateManager (low risk)
- Keep temporary wrappers for compatibility
- Incremental signal rewiring
- Parallel test development

### Web UI
- Use proven tech stack (React, TypeScript)
- Start with static HTML shell
- Integrate API layer incrementally
- Test offline scenarios

### Integration
- Mock API responses in tests
- Gradual cutover to real backend
- Feature flags for new functionality
- Rollback plan for each component

---

## Timeline Summary

```
Week 1: Architecture setup
  Desktop: StateManager + split
  Web: Layout + components + theme

Week 2: Service implementation
  Desktop: Service classes
  Web: Page implementations

Week 3: Integration & signal rewiring
  Desktop: Connect services
  Web: API integration

Week 4: Polish, testing, hardening
  Both: Error handling, async safety
  Both: Comprehensive testing

Week 5: Real-time features
  Desktop: WebSocket support
  Web: Live updates

Week 6: Deployment & docs
  Both: Packaging
  Both: Documentation
  Both: Production readiness
```

---

## Next Steps

1. ✅ Create shared API service layer (`src/guppy/api/service.py`)
2. ✅ Create web UI project structure
3. Create desktop service classes (StateManager, ShellController, etc.)
4. Create web UI components (Sidebar, TopBar, Chat, etc.)
5. Implement WebSocket real-time updates
6. Integrate API layer into both UIs
7. Comprehensive testing across both UIs
8. Production hardening and deployment

