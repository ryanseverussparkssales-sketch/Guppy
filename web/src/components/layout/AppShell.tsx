import { useState, useEffect } from "react"
import { cn } from "@/lib/utils"
import { Sidebar } from "./Sidebar"
import { TopBar } from "./TopBar"
import { CommandPalette } from "./CommandPalette"

interface AppShellProps {
  children: React.ReactNode
}

/**
 * AppShell - Main layout wrapper for the Guppy application
 * 
 * BACKEND INTEGRATION:
 * - Wraps all views and provides layout context
 * - Manages sidebar collapse state (persisted to localStorage)
 * - Handles global keyboard shortcuts (Cmd+K for command palette)
 */
export function AppShell({ children }: AppShellProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const stored = localStorage.getItem("guppy-sidebar-collapsed")
    return stored ? JSON.parse(stored) : false
  })
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false)

  useEffect(() => {
    localStorage.setItem("guppy-sidebar-collapsed", JSON.stringify(sidebarCollapsed))
  }, [sidebarCollapsed])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setCommandPaletteOpen(true)
      }
      if (e.key === "Escape") {
        setCommandPaletteOpen(false)
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

  return (
    <div className="flex h-screen bg-surface text-on-surface overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Content Area */}
      <div 
        className={cn(
          "flex flex-1 flex-col overflow-hidden transition-all duration-300 ease-viscous",
          sidebarCollapsed ? "ml-20" : "ml-72"
        )}
      >
        <TopBar onOpenCommandPalette={() => setCommandPaletteOpen(true)} />
        <main className="flex-1 overflow-auto custom-scrollbar">
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
