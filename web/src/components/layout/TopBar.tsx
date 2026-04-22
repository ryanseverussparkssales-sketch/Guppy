import { cn } from "@/lib/utils"
import {
  Search,
  Bell,
  Settings,
  Wifi,
  WifiOff,
} from "lucide-react"
import { useConnectionStatus } from "@/hooks/useApi"

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

  return (
    <header className="bg-surface flex justify-between items-center w-full px-12 py-4 sticky top-0 z-10 transition-all duration-300 ease-viscous">
      {/* Left: Brand + Navigation */}
      <div className="flex items-center gap-12">
        <h1 className="font-headline text-2xl italic text-primary">{title}</h1>
        <nav className="flex items-center gap-8">
          <a href="#" className="font-headline text-on-surface/60 hover:text-on-surface transition-colors">
            Drafts
          </a>
          <a href="#" className="font-headline text-on-surface/60 hover:text-on-surface transition-colors">
            Archive
          </a>
          <a href="#" className="font-headline text-primary font-bold border-b-2 border-primary pb-1">
            Curation
          </a>
        </nav>
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
