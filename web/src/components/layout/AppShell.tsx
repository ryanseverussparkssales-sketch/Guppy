import { useState, useEffect } from "react"
import { useLocation } from "react-router-dom"
import { useHotkeys } from "react-hotkeys-hook"
import { Sidebar } from "./Sidebar"
import { TopBar } from "./TopBar"
import { CommandPalette } from "@/components/CommandPalette"
import { useReminders } from "@/hooks/useReminders"

interface AppShellProps {
  children: React.ReactNode
}

// Routes where the TopBar is suppressed — the view owns its own chrome
const TOPBAR_HIDDEN_ROUTES = new Set(["/companion", "/workspace", "/codespace", "/assistant"])

/**
 * AppShell - Main layout wrapper for the Guppy application
 *
 * BACKEND INTEGRATION:
 * - Wraps all views and provides layout context
 * - Manages sidebar collapse state (persisted to localStorage)
 * - Handles global keyboard shortcuts (Cmd+K for command palette)
 * - On /assistant the TopBar is hidden (view owns its chrome) and the
 *   global sidebar auto-collapses to icon-only mode to maximise chat space.
 */
export function AppShell({ children }: AppShellProps) {
  const location = useLocation()
  const isChatRoute = TOPBAR_HIDDEN_ROUTES.has(location.pathname)
  // On all three primary surfaces, collapse nav to icon-only to maximise content area
  const isPrimarySurface = ['/companion', '/workspace', '/codespace'].includes(location.pathname)

  // Global reminder poller — fires browser notifications when due
  useReminders()

  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const stored = localStorage.getItem("guppy-sidebar-collapsed")
    return stored ? JSON.parse(stored) : false
  })
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false)

  useEffect(() => {
    localStorage.setItem("guppy-sidebar-collapsed", JSON.stringify(sidebarCollapsed))
  }, [sidebarCollapsed])

  useHotkeys("ctrl+k, meta+k", () => setCommandPaletteOpen(true), { preventDefault: true })
  useHotkeys("escape", () => setCommandPaletteOpen(false))

  // On primary surfaces: force nav sidebar to icon-only so content has maximum room
  const effectiveCollapsed = isPrimarySurface ? true : sidebarCollapsed

  return (
    <div className="flex h-screen bg-surface text-on-surface overflow-hidden">
      {/* Nav Sidebar */}
      <Sidebar
        collapsed={effectiveCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        {/* TopBar hidden on chat route */}
        {!isChatRoute && (
          <TopBar onOpenCommandPalette={() => setCommandPaletteOpen(true)} />
        )}
        <main className={isChatRoute ? "flex-1 overflow-hidden" : "flex-1 overflow-auto custom-scrollbar"}>
          {children}
        </main>
      </div>

      {/* Command Palette Modal */}
      <CommandPalette
        open={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
      />
    </div>
  )
}
