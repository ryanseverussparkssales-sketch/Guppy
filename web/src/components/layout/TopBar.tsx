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
  Cpu,
  Cloud,
} from "lucide-react"
import { useConnectionStatus, useActiveModel } from "@/hooks/useApi"
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
export function TopBar({ title = "Guppy", onOpenCommandPalette }: TopBarProps) {
  const { isConnected } = useConnectionStatus()
  const { workspaces, activeWorkspace, switchWorkspace, createWorkspace } = useWorkspaces()
  const { activeProvider, modelName, modelTags, providers, setProvider, setModel } = useActiveModel()
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false)
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
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

      {/* Right: Model Pill + Search + Controls */}
      <div className="flex items-center gap-6">
        {/* Active Model Indicator */}
        <div className="relative">
          <button
            onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-container-low hover:bg-surface-container transition-all text-xs font-medium"
          >
            {activeProvider === "local" ? (
              <Cpu className="w-3.5 h-3.5 text-primary" />
            ) : (
              <Cloud className="w-3.5 h-3.5 text-tertiary" />
            )}
            <span className="text-on-surface max-w-28 truncate">{modelName || "No model"}</span>
            {modelTags.slice(0, 2).map(tag => (
              <span key={tag} className="px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[10px]">{tag}</span>
            ))}
            <ChevronDown className={cn("w-3 h-3 text-on-surface-variant/60 transition-transform", modelDropdownOpen && "rotate-180")} />
          </button>

          {modelDropdownOpen && providers && (
            <div className="absolute top-full mt-1 right-0 bg-surface-container rounded-xl shadow-xl border border-outline-variant/20 z-50 min-w-72 max-h-96 overflow-y-auto">
              {/* Local models */}
              {providers.local?.models?.length > 0 && (
                <div className="p-2">
                  <div className="px-2 py-1 text-[10px] font-bold text-on-surface-variant/60 uppercase tracking-wider flex items-center gap-1">
                    <Cpu className="w-3 h-3" /> Local
                  </div>
                  {providers.local.models.map((m: any) => {
                    const isOffline = m.alive === false
                    const isActive = providers.local.active_model === m.id && activeProvider === "local"
                    return (
                      <button
                        key={m.id}
                        onClick={isOffline ? undefined : async () => {
                          await setProvider("local")
                          await setModel("local", m.id)
                          setModelDropdownOpen(false)
                        }}
                        disabled={isOffline}
                        className={cn(
                          "w-full text-left px-3 py-2 rounded-lg text-xs transition-colors flex items-center justify-between gap-2",
                          isActive
                            ? "bg-primary/10 text-primary"
                            : isOffline
                              ? "text-on-surface-variant/40 cursor-not-allowed"
                              : "text-on-surface hover:bg-surface-container-high"
                        )}
                      >
                        <span className="font-medium truncate">{m.name}</span>
                        <div className="flex gap-1 shrink-0">
                          {isOffline && (
                            <span className="px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-500 text-[10px]">offline</span>
                          )}
                          {!isOffline && (m.tags ?? []).slice(0, 2).map((tag: string) => (
                            <span key={tag} className="px-1.5 py-0.5 rounded bg-surface-variant text-on-surface-variant text-[10px]">{tag}</span>
                          ))}
                        </div>
                      </button>
                    )
                  })}
                </div>
              )}
              {/* Cloud providers */}
              {(["anthropic", "openai", "google", "cohere", "mistral"] as const).map(p => {
                const info = providers[p]
                if (!info?.configured) return null
                const label =
                  p === "anthropic" ? "Anthropic" :
                  p === "openai"    ? "OpenAI"    :
                  p === "google"    ? "Google"    :
                  p === "cohere"    ? "Cohere"    : "Mistral"
                return (
                  <div key={p} className="p-2 border-t border-outline-variant/10">
                    <div className="px-2 py-1 text-[10px] font-bold text-on-surface-variant/60 uppercase tracking-wider flex items-center gap-1">
                      <Cloud className="w-3 h-3" /> {label}
                    </div>
                    {info.models.map((m: any) => (
                      <button
                        key={m.id}
                        onClick={async () => {
                          await setProvider(p)
                          await setModel(p, m.id)
                          setModelDropdownOpen(false)
                        }}
                        className={cn(
                          "w-full text-left px-3 py-2 rounded-lg text-xs transition-colors flex items-center justify-between gap-2",
                          info.active_model === m.id && activeProvider === p
                            ? "bg-primary/10 text-primary"
                            : "text-on-surface hover:bg-surface-container-high"
                        )}
                      >
                        <span className="font-medium truncate">{m.name}</span>
                        <div className="flex items-center gap-1 shrink-0">
                          {m.free && (
                            <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 text-[10px] font-semibold">free</span>
                          )}
                          <span className="px-1.5 py-0.5 rounded bg-surface-variant text-on-surface-variant text-[10px]">{m.tier}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                )
              })}
            </div>
          )}
        </div>

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
