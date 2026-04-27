import { Routes, Route, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { AppShell } from './components/layout/index'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ErrorToastContainer } from './components/ErrorToast'
import AssistantView from './views/AssistantView'
import InstancesView from './views/InstancesView'
import PersonasView from './views/PersonasView'
import ModelsView from './views/ModelsView'
import ToolsView from './views/ToolsView'
import SettingsView from './views/SettingsView'
import LaunchpadView from './views/LaunchpadView'
import AdminPanel from './views/AdminPanel'
import InstructionsView from './views/InstructionsView'
import LoginView from './views/LoginView'
import AgentsView from './views/AgentsView'
import { Navigate } from 'react-router-dom'
import { useWorkspaceStore, syncManager } from './store'
import { useErrorStore } from './store/errorStore'
import { Toaster } from 'sonner'
import './index.css'

/**
 * App - Main application component
 *
 * INITIALIZATION FLOW:
 * 1. On mount: Initialize app with syncManager.initializeApp()
 *    - Fetches workspaces
 *    - Sets active workspace (first one if not set)
 *    - Fetches settings
 *    - Loads conversations for active workspace
 *
 * 2. Data flow: store (Zustand) ← syncManager ← API
 *    - All data fetched through syncManager
 *    - All mutations go through syncManager
 *    - Store is source of truth for UI
 *
 * 3. Error handling: ErrorBoundary catches React errors, ErrorToast shows API errors
 *    - Unhandled React component errors → ErrorBoundary fallback UI
 *    - API/async errors → ErrorToast notifications with retry buttons
 *    - All errors logged to telemetry on backend
 *
 * 4. Navigation is handled via react-router-dom
 *    - Custom events from sidebar/command palette trigger navigation
 */

// ── Module-level init guard ────────────────────────────────────────────────────
// Lives outside the component so React strict-mode double-invoke can't race it.
let _initDone = false
let _initInFlight = false
let _retryTimer: ReturnType<typeof setTimeout> | null = null

const RETRY_DELAYS = [3000, 6000, 12000, 20000, 30000]

async function _tryInit(attempt = 0): Promise<void> {
  if (_initInFlight) return
  _initInFlight = true
  try {
    console.log(`[App] Initializing application${attempt > 0 ? ` (retry ${attempt})` : ''}...`)
    await syncManager.initializeApp()
    _initDone = true
    console.log('[App] App initialization complete')
  } catch (err) {
    console.error('[App] Failed to initialize app:', err)
    if (attempt < RETRY_DELAYS.length) {
      const delay = RETRY_DELAYS[attempt]
      console.log(`[App] Will retry in ${delay / 1000}s...`)
      _retryTimer = setTimeout(() => _tryInit(attempt + 1), delay)
    }
  } finally {
    _initInFlight = false
  }
}

/**
 * AppContent - Inner component wrapped by ErrorBoundary
 * Separated to allow error boundary to catch initialization errors
 */
function AppContent() {
  const navigate = useNavigate()
  const { activeWorkspaceId } = useWorkspaceStore()
  const { errors, removeError } = useErrorStore()

  // Fire init exactly once per page load (module-level guard prevents strict-mode races)
  useEffect(() => {
    if (!_initDone && !_initInFlight) _tryInit()
    // Re-initialize on tab focus if workspaces still empty (API was down at load time)
    const handleVisibility = () => {
      if (document.visibilityState !== 'visible') return
      if (!_initDone && !_initInFlight) {
        if (_retryTimer) { clearTimeout(_retryTimer); _retryTimer = null }
        _tryInit()
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [])

  // Load workspace data when active workspace changes
  useEffect(() => {
    if (activeWorkspaceId) {
      syncManager
        .loadWorkspaceData(activeWorkspaceId)
        .catch((error) => console.error('[App] Failed to load workspace data:', error))
    }
  }, [activeWorkspaceId])

  // Listen for navigation events from sidebar/command palette
  useEffect(() => {
    const handleNavigate = (e: CustomEvent<{ view: string }>) => {
      const viewToRoute: Record<string, string> = {
        assistant:       '/assistant',
        chat:            '/assistant',
        'launch-control': '/launch-control',
        personas:        '/personas',
        library:         '/personas',
        instructions:    '/instructions',
        tools:           '/tools',
        voices:          '/tools',
        desktop:         '/tools',
        settings:        '/settings',
        status:          '/settings',
        admin:           '/admin',
        agents:          '/launch-control',
        instances:       '/launch-control',
        models:          '/launch-control',
      }
      const route = viewToRoute[e.detail.view] || '/'
      navigate(route)
    }

    window.addEventListener('guppy:navigate', handleNavigate as EventListener)
    return () => window.removeEventListener('guppy:navigate', handleNavigate as EventListener)
  }, [navigate])

  return (
    <>
      <AppShell>
        <Routes>
          <Route path="/" element={<Navigate to="/assistant" replace />} />
          <Route path="/assistant" element={<AssistantView />} />
          <Route path="/launch-control" element={<LaunchpadView />} />
          <Route path="/personas" element={<PersonasView />} />
          <Route path="/library" element={<Navigate to="/personas" replace />} />
          <Route path="/instructions" element={<InstructionsView />} />
          <Route path="/tools" element={<ToolsView />} />
          <Route path="/voices" element={<Navigate to="/tools" replace />} />
          <Route path="/desktop" element={<Navigate to="/tools" replace />} />
          <Route path="/settings" element={<SettingsView />} />
          <Route path="/status" element={<Navigate to="/settings" replace />} />
          <Route path="/agents" element={<AgentsView />} />
          <Route path="/instances" element={<InstancesView />} />
          <Route path="/models" element={<ModelsView />} />
          <Route path="/admin" element={<AdminPanel />} />
          <Route path="/login" element={<LoginView />} />
        </Routes>
      </AppShell>

      {/* Error toast container for displaying error notifications from error store */}
      <ErrorToastContainer
        toasts={errors.map((e) => ({
          id: e.id,
          error: e.details || e.code,
          message: e.message,
          onRetry: e.onRetry,
        }))}
        onDismiss={removeError}
        position="bottom-right"
      />
      <Toaster position="top-right" richColors closeButton />
    </>
  )
}

/**
 * App - Root component with error boundary
 * Wraps all app content to catch unhandled React errors
 */
function App() {
  return (
    <ErrorBoundary>
      <AppContent />
    </ErrorBoundary>
  )
}

export default App
