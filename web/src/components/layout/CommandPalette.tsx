import { useState, useEffect, useRef } from "react"
import { cn } from "@/lib/utils"
import {
  Sparkles,
  Search,
  Brain,
  Settings,
  LayoutGrid,
  Plus,
  Play,
  StopCircle,
  FileText,
  BookOpen,
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

  const navigate = (view: string) => {
    window.dispatchEvent(new CustomEvent("guppy:navigate", { detail: { view } }))
    onClose()
  }

  const commands: Command[] = [
    // Navigation
    {
      id: "nav-intelligence",
      label: "Intelligence",
      description: "View system dashboard",
      icon: <Sparkles size={16} />,
      category: "Navigation",
      action: () => navigate("dashboard"),
    },
    {
      id: "nav-research",
      label: "Research",
      description: "Start a new conversation",
      icon: <Search size={16} />,
      category: "Navigation",
      action: () => navigate("assistant"),
    },
    {
      id: "nav-workspace",
      label: "Workspace",
      description: "Manage running instances",
      icon: <LayoutGrid size={16} />,
      category: "Navigation",
      action: () => navigate("instances"),
    },
    {
      id: "nav-briefings",
      label: "Briefings",
      description: "Configure neural architectures",
      icon: <FileText size={16} />,
      category: "Navigation",
      action: () => navigate("models"),
    },
    {
      id: "nav-library",
      label: "Library",
      description: "Browse knowledge base",
      icon: <BookOpen size={16} />,
      category: "Navigation",
      action: () => navigate("library"),
    },
    {
      id: "nav-settings",
      label: "Settings",
      description: "Configure system preferences",
      icon: <Settings size={16} />,
      category: "Navigation",
      action: () => navigate("settings"),
    },
    // Actions
    {
      id: "action-new-briefing",
      label: "New Briefing",
      description: "Start a fresh research session",
      icon: <Plus size={16} />,
      category: "Actions",
      action: () => navigate("assistant"),
    },
    {
      id: "action-new-instance",
      label: "Initialize Node",
      description: "Create a new neural instance",
      icon: <Brain size={16} />,
      category: "Actions",
      action: () => {
        // BACKEND: POST /api/instances
        console.log("TODO: Create new instance")
      },
    },
    {
      id: "action-start-instance",
      label: "Start Node",
      description: "Activate a dormant instance",
      icon: <Play size={16} />,
      category: "Actions",
      action: () => {
        // BACKEND: POST /api/instances/:id/start
        console.log("TODO: Start instance")
      },
    },
    {
      id: "action-stop-all",
      label: "Halt All Nodes",
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
        className="absolute inset-0 bg-surface/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Palette */}
      <div className="relative w-full max-w-lg bg-surface-container-lowest border border-outline-variant/10 rounded-xl shadow-soft-lg overflow-hidden animate-in fade-in-0 zoom-in-95">
        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 border-b border-outline-variant/10">
          <Search size={18} className="text-on-surface-variant" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelectedIndex(0)
            }}
            placeholder="Search commands..."
            className="flex-1 h-14 bg-transparent text-on-surface font-headline italic placeholder:text-on-surface-variant/50 outline-none"
          />
        </div>

        {/* Commands List */}
        <div className="max-h-80 overflow-y-auto p-2 custom-scrollbar">
          {Object.entries(groupedCommands).map(([category, cmds]) => (
            <div key={category} className="mb-3">
              <div className="px-3 py-2 text-[10px] font-bold text-on-surface-variant/60 uppercase tracking-widest">
                {category}
              </div>
              {cmds.map((cmd) => {
                const index = flatCommands.indexOf(cmd)
                return (
                  <button
                    key={cmd.id}
                    onClick={() => executeCommand(cmd)}
                    className={cn(
                      "w-full flex items-center gap-3 px-3 py-3 rounded-lg text-left transition-all duration-200",
                      index === selectedIndex
                        ? "bg-primary text-white"
                        : "text-on-surface hover:bg-surface-container"
                    )}
                  >
                    <span className={index === selectedIndex ? "text-white/70" : "text-on-surface-variant"}>
                      {cmd.icon}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-bold">{cmd.label}</div>
                      {cmd.description && (
                        <div className={cn(
                          "text-xs truncate",
                          index === selectedIndex ? "text-white/70" : "text-on-surface-variant/70"
                        )}>
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
            <div className="px-3 py-8 text-center text-on-surface-variant font-headline italic">
              No commands found for &ldquo;{query}&rdquo;
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-outline-variant/10 text-xs text-on-surface-variant/60">
          <div className="flex items-center gap-4">
            <span><kbd className="px-1.5 py-0.5 bg-surface-container rounded text-[10px]">↑↓</kbd> Navigate</span>
            <span><kbd className="px-1.5 py-0.5 bg-surface-container rounded text-[10px]">↵</kbd> Select</span>
          </div>
          <span><kbd className="px-1.5 py-0.5 bg-surface-container rounded text-[10px]">Esc</kbd> Close</span>
        </div>
      </div>
    </div>
  )
}
