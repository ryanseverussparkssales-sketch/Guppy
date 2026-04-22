import React from "react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Search,
  Sun,
  Moon,
  Wifi,
  WifiOff,
  Bell,
  Command,
} from "lucide-react"
import { useTheme } from "@/hooks/useTheme"
import { useConnectionStatus } from "@/hooks/useApi"

interface TopBarProps {
  onOpenCommandPalette: () => void
}

/**
 * TopBar - Application header with search, status, and controls
 * 
 * BACKEND INTEGRATION:
 * - Connection status indicator shows WebSocket/API connectivity
 * - Uses useConnectionStatus() hook to get real-time status
 * - Theme toggle persists preference to localStorage
 */
export function TopBar({ onOpenCommandPalette }: TopBarProps) {
  const { theme, toggleTheme } = useTheme()
  const { isConnected, latency } = useConnectionStatus()

  return (
    <header className="flex items-center justify-between h-14 px-6 bg-background border-b border-border">
      {/* Search / Command Palette Trigger */}
      <button
        onClick={onOpenCommandPalette}
        className="flex items-center gap-3 h-9 px-3 w-72 rounded-lg border border-border bg-muted/50 text-muted-foreground hover:bg-muted transition-colors"
      >
        <Search size={16} />
        <span className="text-sm">Search or run command...</span>
        <kbd className="ml-auto flex items-center gap-1 text-xs bg-background px-1.5 py-0.5 rounded border border-border">
          <Command size={12} />K
        </kbd>
      </button>

      {/* Right Side Controls */}
      <div className="flex items-center gap-4">
        {/* Connection Status */}
        <ConnectionIndicator isConnected={isConnected} latency={latency} />

        {/* Notifications */}
        <Button variant="ghost" size="icon" className="relative">
          <Bell size={18} />
          {/* Notification badge - show when there are unread notifications */}
          {/* <span className="absolute top-1 right-1 w-2 h-2 bg-destructive rounded-full" /> */}
        </Button>

        {/* Theme Toggle */}
        <Button variant="ghost" size="icon" onClick={toggleTheme}>
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </Button>
      </div>
    </header>
  )
}

interface ConnectionIndicatorProps {
  isConnected: boolean
  latency?: number
}

/**
 * ConnectionIndicator - Shows backend connection status
 * 
 * BACKEND INTEGRATION:
 * - Green: Connected to backend API/WebSocket
 * - Red: Disconnected or error state
 * - Shows latency when connected
 */
function ConnectionIndicator({ isConnected, latency }: ConnectionIndicatorProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium",
        isConnected
          ? "bg-success/10 text-success"
          : "bg-destructive/10 text-destructive"
      )}
    >
      {isConnected ? (
        <>
          <Wifi size={14} />
          <span>Connected</span>
          {latency !== undefined && (
            <span className="text-success/70">{latency}ms</span>
          )}
        </>
      ) : (
        <>
          <WifiOff size={14} />
          <span>Disconnected</span>
        </>
      )}
    </div>
  )
}
