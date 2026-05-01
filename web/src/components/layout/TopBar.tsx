import { toast } from "sonner"
import { cn } from "@/lib/utils"
import {
  Bell,
  Settings,
  Wifi,
  WifiOff,
} from "lucide-react"
import { useConnectionStatus } from "@/hooks/useApi"

const navigate = (view: string) =>
  window.dispatchEvent(new CustomEvent("guppy:navigate", { detail: { view } }))

interface TopBarProps {
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
export function TopBar({ onOpenCommandPalette: _onOpenCommandPalette }: TopBarProps) {
  const { isConnected } = useConnectionStatus()

  return (
    <header className="bg-surface flex justify-end items-center w-full px-12 py-4 sticky top-0 z-10 transition-all duration-300 ease-viscous">
      <div className="flex items-center gap-4">
        {/* Connection Status */}
        <ConnectionIndicator isConnected={isConnected} />

        {/* Notifications */}
        <button
          onClick={() => toast.info("No new notifications")}
          className="text-on-surface-variant hover:bg-surface-container p-2 rounded-md transition-all"
          title="Notifications"
        >
          <Bell className="w-5 h-5" />
        </button>

        {/* Settings */}
        <button
          onClick={() => navigate("settings")}
          className="text-on-surface-variant hover:bg-surface-container p-2 rounded-md transition-all"
          title="Settings"
        >
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
