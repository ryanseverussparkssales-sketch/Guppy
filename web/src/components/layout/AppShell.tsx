import React, { useState, useEffect } from "react"
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
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar
          onOpenCommandPalette={() => setCommandPaletteOpen(true)}
        />
        <main
          className={cn(
            "flex-1 overflow-auto p-6 transition-all duration-300",
            sidebarCollapsed ? "ml-0" : "ml-0"
          )}
        >
          {children}
        </main>
      </div>
      <CommandPalette
        open={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
      />
    </div>
  )
}
