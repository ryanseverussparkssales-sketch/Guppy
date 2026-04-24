import { useState } from "react"
import { cn } from "@/lib/utils"
import {
  Search,
  Bell,
  Settings,
  Wifi,
  WifiOff,
  ChevronDown,
  Plus,
  Trash2,
} from "lucide-react"
import { useConnectionStatus } from "@/hooks/useApi"
import { useWorkspaces } from "@/hooks/useWorkspaces"

interface TopBarProps {
  title?: string
  onOpenCommandPalette: () => void
}

/**
 * TopBar - Editorial-style application header
 * 
 * BACKEND INTEGRATION:
 * - Connection status indicator shows WebSocket/API connectivity
 * - Uses useConnectionStatus() hook to get real-time status
 * - Navigation tabs can link to different workspace modes
 */
export function TopBar({ title = "Editorial Intelligence", onOpenCommandPalette }: TopBarProps) {
  const { isConnected } = useConnectionStatus()
  const { workspaces, activeWorkspace, switchWorkspace, createWorkspace } = useWorkspaces()
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false)
  const [newWorkspaceName, setNewWorkspaceName] = useState("")
  const [showNewWorkspaceInput, setShowNewWorkspaceInput] = useState(false)

  const handleCreateWorkspace = async () => {
    if (!newWorkspaceName.trim()) return
    try {
      await createWorkspace(newWorkspaceName.trim())
      setNewWorkspaceName("")
      setShowNewWorkspaceInput(false)
    } catch (err) {
      console.error("Failed to create workspace:", err)
    }
  }

  return (
    <header className="bg-surface flex justify-between items-center w-full px-12 py-4 sticky top-0 z-10 transition-all duration-300 ease-viscous">
      {/* Left: Brand + Workspace Switcher */}
      <div className="flex items-center gap-12">
        <h1 className="font-headline text-2xl italic text-primary">{title}</h1>

        {/* Workspace Switcher */}
        <div className="relative">
          <button
            onClick={() => setWorkspaceDropdownOpen(!workspaceDropdownOpen)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-container-low text-on-surface font-bold text-sm hover:bg-surface-container transition-all"
          >
            <span className="max-w-32 truncate">{activeWorkspace?.name || "No workspace"}</span>
            <ChevronDown className={cn("w-4 h-4 transition-transform", workspaceDropdownOpen && "rotate-180")} />
          </button>

          {/* Workspace Dropdown */}
          {workspaceDropdownOpen && (
            <div className="absolute top-full mt-1 left-0 bg-surface-container rounded-lg shadow-lg border border-outline-variant/20 z-50 min-w-56">
              {/* Create New */}
              {!showNewWorkspaceInput ? (
                <button
                  onClick={() => setShowNewWorkspaceInput(true)}
                  className="w-full text-left px-4 py-2 text-xs font-bold text-primary hover:bg-surface-container-high transition-colors flex items-center gap-2"
                >
                  <Plus className="w-3 h-3" />
                  Create workspace
                </button>
              ) : (
                <div className="px-4 py-2 border-b border-outline-variant/10">
                  <input
                    autoFocus
                    type="text"
                    value={newWorkspaceName}
                    onChange={(e) => setNewWorkspaceName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleCreateWorkspace()
                      if (e.key === "Escape") setShowNewWorkspaceInput(false)
                    }}
                    placeholder="Workspace name..."
                    className="w-full bg-surface-container px-2 py-1.5 rounded text-xs text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              )}

              {/* Workspace List */}
              <div className="max-h-48 overflow-y-auto">
                {workspaces.map((ws) => (
                  <button
                    key={ws.id}
                    onClick={() => {
                      switchWorkspace(ws.id)
                      setWorkspaceDropdownOpen(false)
                    }}
                    className={cn(
                      "w-full text-left px-4 py-2 text-xs font-bold transition-colors flex items-center justify-between group",
                      activeWorkspace?.id === ws.id ? "bg-primary/10 text-primary" : "text-on-surface-variant hover:bg-surface-container-high"
                    )}
                  >
                    <span className="truncate">{ws.name}</span>
                    {activeWorkspace?.id === ws.id && <span className="text-xs">✓</span>}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right: Search + Controls */}
      <div className="flex items-center gap-6">
        {/* Search Input */}
        <button
          onClick={onOpenCommandPalette}
          className="flex items-center gap-2 bg-surface-container-low px-4 py-2 rounded-md hover:bg-surface-container transition-all"
        >
          <Search className="w-4 h-4 text-on-surface-variant/60" />
          <span className="text-sm text-on-surface-variant/60 w-40">Search models...</span>
        </button>

        {/* Connection Status */}
        <ConnectionIndicator isConnected={isConnected} />

        {/* Notifications */}
        <button className="text-on-surface-variant hover:bg-surface-container p-2 rounded-md transition-all">
          <Bell className="w-5 h-5" />
        </button>

        {/* Settings */}
        <button className="text-on-surface-variant hover:bg-surface-container p-2 rounded-md transition-all">
          <Settings className="w-5 h-5" />
        </button>

        {/* User Avatar */}
        <div className="w-8 h-8 rounded-full overflow-hidden ml-2 bg-primary-container flex items-center justify-center">
          <span className="text-white text-sm font-bold">G</span>
        </div>
      </div>
    </header>
  )
}

interface ConnectionIndicatorProps {
  isConnected: boolean
}

/**
 * ConnectionIndicator - Shows backend connection status
 */
function ConnectionIndicator({ isConnected }: ConnectionIndicatorProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium",
        isConnected
          ? "bg-primary/10 text-primary"
          : "bg-secondary/10 text-secondary"
      )}
    >
      {isConnected ? (
        <>
          <Wifi size={14} />
          <span>Connected</span>
        </>
      ) : (
        <>
          <WifiOff size={14} />
          <span>Offline</span>
        </>
      )}
    </div>
  )
}
