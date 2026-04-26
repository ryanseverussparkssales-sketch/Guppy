import { Routes, Route, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { AppShell } from './components/layout/index'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ErrorToastContainer } from './components/ErrorToast'
import AssistantView from './views/AssistantView'
import InstancesView from './views/InstancesView'
import LibraryView from './views/LibraryView'
import ModelsView from './views/ModelsView'
import ToolsView from './views/ToolsView'
import VoicesView from './views/VoicesView'
import DesktopView from './views/DesktopView'
import SettingsView from './views/SettingsView'
import LauncherView from './views/LauncherView'
import StatusView from './views/StatusView'
import AdminPanel from './views/AdminPanel'
import InstructionsView from './views/InstructionsView'
import DashboardView from './views/DashboardView'
import LoginView from './views/LoginView'
import AgentsView from './views/AgentsView'
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

/**
 * AppContent - Inner component wrapped by ErrorBoundary
 * Separated to allow error boundary to catch initialization errors
 */
function AppContent() {
  const navigate = useNavigate()
  const { activeWorkspaceId } = useWorkspaceStore()
  const { errors, removeError } = useErrorStore()

  // Initialize app data on mount
  useEffect(() => {
    const initializeApp = async () => {
      try {
        console.log('[App] Initializing application...')
        await syncManager.initializeApp()
        console.log('[App] App initialization complete')
      } catch (error) {
        console.error('[App] Failed to initialize app:', error)
        // Don't crash - user can still navigate and try again
      }
    }

    initializeApp()
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
        dashboard: '/',
        assistant: '/assistant',
        agents: '/agents',
        instances: '/instances',
        library: '/library',
        models: '/models',
        tools: '/tools',
        voices: '/voices',
        desktop: '/desktop',
        'launch-control': '/launch-control',
        settings: '/settings',
        status: '/status',
        admin:        '/admin',
        instructions: '/instructions',
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
          <Route path="/" element={<DashboardView />} />
          <Route path="/assistant" element={<AssistantView />} />
          <Route path="/agents" element={<AgentsView />} />
          <Route path="/instances" element={<InstancesView />} />
          <Route path="/library" element={<LibraryView />} />
          <Route path="/models" element={<ModelsView />} />
          <Route path="/tools" element={<ToolsView />} />
          <Route path="/voices" element={<VoicesView />} />
          <Route path="/desktop" element={<DesktopView />} />
          <Route path="/launch-control" element={<LauncherView />} />
          <Route path="/settings" element={<SettingsView />} />
          <Route path="/status" element={<StatusView />} />
          <Route path="/admin" element={<AdminPanel />} />
          <Route path="/instructions" element={<InstructionsView />} />
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
