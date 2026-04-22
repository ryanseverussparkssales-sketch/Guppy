import React, { useState, useEffect, useRef } from "react"
import { cn } from "@/lib/utils"
import {
  MessageSquare,
  Server,
  Brain,
  Settings,
  Search,
  LayoutDashboard,
  Plus,
  Play,
  StopCircle,
} from "lucide-react"

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

interface Command {
  id: string
  label: string
  description?: string
  icon: React.ReactNode
  category: string
  /**
   * BACKEND: Action to execute when command is selected
   * Can be a navigation action or an API call
   */
  action: () => void
}

/**
 * CommandPalette - Keyboard-driven command interface (Cmd+K)
 * 
 * BACKEND INTEGRATION:
 * - Commands can trigger navigation or API actions
 * - "New Instance" -> POST /api/instances
 * - "Stop All Instances" -> POST /api/instances/stop-all
 * - Search queries could be sent to a search endpoint
 */
export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("")
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const commands: Command[] = [
    // Navigation
    {
      id: "nav-dashboard",
      label: "Go to Dashboard",
      icon: <LayoutDashboard size={16} />,
      category: "Navigation",
      action: () => navigate("dashboard"),
    },
    {
      id: "nav-assistant",
      label: "Go to Assistant",
      icon: <MessageSquare size={16} />,
      category: "Navigation",
      action: () => navigate("assistant"),
    },
    {
      id: "nav-instances",
      label: "Go to Instances",
      icon: <Server size={16} />,
      category: "Navigation",
      action: () => navigate("instances"),
    },
    {
      id: "nav-models",
      label: "Go to Models",
      icon: <Brain size={16} />,
      category: "Navigation",
      action: () => navigate("models"),
    },
    {
      id: "nav-settings",
      label: "Go to Settings",
      icon: <Settings size={16} />,
      category: "Navigation",
      action: () => navigate("settings"),
    },
    // Actions
    {
      id: "action-new-instance",
      label: "New Instance",
      description: "Create a new Guppy instance",
      icon: <Plus size={16} />,
      category: "Actions",
      action: () => {
        // BACKEND: POST /api/instances
        console.log("TODO: Create new instance")
      },
    },
    {
      id: "action-start-instance",
      label: "Start Instance",
      description: "Start a stopped instance",
      icon: <Play size={16} />,
      category: "Actions",
      action: () => {
        // BACKEND: POST /api/instances/:id/start
        console.log("TODO: Start instance")
      },
    },
    {
      id: "action-stop-all",
      label: "Stop All Instances",
      description: "Stop all running instances",
      icon: <StopCircle size={16} />,
      category: "Actions",
      action: () => {
        // BACKEND: POST /api/instances/stop-all
        console.log("TODO: Stop all instances")
      },
    },
  ]

  const filteredCommands = commands.filter(
    (cmd) =>
      cmd.label.toLowerCase().includes(query.toLowerCase()) ||
      cmd.description?.toLowerCase().includes(query.toLowerCase())
  )

  const groupedCommands = filteredCommands.reduce((acc, cmd) => {
    if (!acc[cmd.category]) acc[cmd.category] = []
    acc[cmd.category].push(cmd)
    return acc
  }, {} as Record<string, Command[]>)

  const flatCommands = Object.values(groupedCommands).flat()

  const navigate = (view: string) => {
    window.dispatchEvent(new CustomEvent("guppy:navigate", { detail: { view } }))
    onClose()
  }

  const executeCommand = (command: Command) => {
    command.action()
    onClose()
    setQuery("")
    setSelectedIndex(0)
  }

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus()
    }
  }, [open])

  useEffect(() => {
    if (!open) {
      setQuery("")
      setSelectedIndex(0)
    }
  }, [open])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!open) return

      if (e.key === "ArrowDown") {
        e.preventDefault()
        setSelectedIndex((i) => Math.min(i + 1, flatCommands.length - 1))
      } else if (e.key === "ArrowUp") {
        e.preventDefault()
        setSelectedIndex((i) => Math.max(i - 1, 0))
      } else if (e.key === "Enter" && flatCommands[selectedIndex]) {
        e.preventDefault()
        executeCommand(flatCommands[selectedIndex])
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [open, flatCommands, selectedIndex])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Palette */}
      <div className="relative w-full max-w-lg bg-popover border border-border rounded-xl shadow-2xl overflow-hidden animate-in fade-in-0 zoom-in-95">
        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 border-b border-border">
          <Search size={18} className="text-muted-foreground" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelectedIndex(0)
            }}
            placeholder="Type a command or search..."
            className="flex-1 h-12 bg-transparent text-foreground placeholder:text-muted-foreground outline-none"
          />
        </div>

        {/* Commands List */}
        <div className="max-h-80 overflow-y-auto p-2">
          {Object.entries(groupedCommands).map(([category, cmds]) => (
            <div key={category} className="mb-2">
              <div className="px-2 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                {category}
              </div>
              {cmds.map((cmd) => {
                const index = flatCommands.indexOf(cmd)
                return (
                  <button
                    key={cmd.id}
                    onClick={() => executeCommand(cmd)}
                    className={cn(
                      "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors",
                      index === selectedIndex
                        ? "bg-accent text-accent-foreground"
                        : "text-foreground hover:bg-accent/50"
                    )}
                  >
                    <span className="text-muted-foreground">{cmd.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium">{cmd.label}</div>
                      {cmd.description && (
                        <div className="text-xs text-muted-foreground truncate">
                          {cmd.description}
                        </div>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>
          ))}

          {flatCommands.length === 0 && (
            <div className="px-3 py-8 text-center text-muted-foreground">
              No commands found for "{query}"
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-2 border-t border-border text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <span><kbd className="px-1.5 py-0.5 bg-muted rounded">↑↓</kbd> Navigate</span>
            <span><kbd className="px-1.5 py-0.5 bg-muted rounded">↵</kbd> Select</span>
          </div>
          <span><kbd className="px-1.5 py-0.5 bg-muted rounded">Esc</kbd> Close</span>
        </div>
      </div>
    </div>
  )
}
