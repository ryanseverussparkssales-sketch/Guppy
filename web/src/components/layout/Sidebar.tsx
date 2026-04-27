import { useState } from "react"
import { useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"
import { Tooltip } from "@/components/ui/tooltip"
import {
  Sparkles,
  MessageSquare,
  BookOpen,
  BookText,
  Plus,
  HelpCircle,
  LogOut,
  Brain,
  Wrench,
  Mic,
  Activity,
  Settings,
  Monitor,
  Rocket,
} from "lucide-react"

/**
 * BACKEND INTEGRATION:
 * - User profile data from GET /api/user/profile
 * - Navigation state can sync with backend for workspace persistence
 */

interface NavItem {
  id: string
  label: string
  icon: React.ReactNode
  view: string
}

const primaryNavItems: NavItem[] = [
  { id: "dashboard",     label: "Dashboard",     icon: <Sparkles className="w-5 h-5" />,       view: "dashboard" },
  { id: "chat",          label: "Chat",          icon: <MessageSquare className="w-5 h-5" />,   view: "assistant" },
  { id: "launch-control", label: "Launch Control", icon: <Rocket className="w-5 h-5" />,       view: "launch-control" },
  { id: "library",       label: "Library",       icon: <BookOpen className="w-5 h-5" />,        view: "library" },
  { id: "instructions",  label: "Instructions",  icon: <BookText className="w-5 h-5" />,        view: "instructions" },
]

const secondaryNavItems: NavItem[] = [
  { id: "tools",    label: "Tools",    icon: <Wrench className="w-5 h-5" />,   view: "tools" },
  { id: "voices",   label: "Voices",   icon: <Mic className="w-5 h-5" />,      view: "voices" },
  { id: "desktop",  label: "Desktop",  icon: <Monitor className="w-5 h-5" />,  view: "desktop" },
  { id: "status",   label: "Status",   icon: <Activity className="w-5 h-5" />, view: "status" },
  { id: "settings", label: "Settings", icon: <Settings className="w-5 h-5" />, view: "settings" },
]

interface SidebarProps {
  collapsed: boolean
  onToggleCollapse: () => void
}

const ROUTE_TO_VIEW: Record<string, string> = {
  '/':          'dashboard',
  '/assistant': 'assistant',
  '/agents':    'agents',
  '/instances': 'instances',
  '/models':    'models',
  '/library':       'library',
  '/instructions':  'instructions',
  '/tools':          'tools',
  '/voices':         'voices',
  '/desktop':        'desktop',
  '/launch-control': 'launch-control',
  '/status':         'status',
  '/settings':       'settings',
  '/admin':          'admin',
}

export function Sidebar({ collapsed }: SidebarProps) {
  const location = useLocation()
  const activeView = ROUTE_TO_VIEW[location.pathname] ?? 'dashboard'
  const [hoveredItem, setHoveredItem] = useState<string | null>(null)

  const handleNavClick = (view: string) => {
    window.dispatchEvent(new CustomEvent("guppy:navigate", { detail: { view } }))
  }

  const renderNavItem = (item: NavItem) => {
    const isActive = activeView === item.view
    const isHovered = hoveredItem === item.id

    const button = (
      <button
        key={item.id}
        onClick={() => handleNavClick(item.view)}
        onMouseEnter={() => setHoveredItem(item.id)}
        onMouseLeave={() => setHoveredItem(null)}
        className={cn(
          "w-full flex items-center font-body text-sm font-semibold tracking-tight transition-all duration-200 ease-viscous",
          collapsed ? "justify-center px-4 py-3" : "py-3",
          isActive
            ? "text-primary bg-white shadow-sm rounded-r-full pl-6 pr-4"
            : "text-on-surface/70 hover:text-primary px-6",
          !isActive && isHovered && !collapsed && "translate-x-1"
        )}
      >
        <span className={cn(collapsed ? "" : "mr-4")}>{item.icon}</span>
        {!collapsed && item.label}
      </button>
    )

    if (collapsed) {
      return (
        <Tooltip key={item.id} content={item.label} side="right">
          {button}
        </Tooltip>
      )
    }

    return button
  }

  return (
    <aside
      className={cn(
        "bg-surface-container-low flex flex-col h-full py-8 gap-y-2 overflow-y-auto custom-scrollbar transition-all duration-300 ease-viscous",
        collapsed ? "w-20" : "w-72"
      )}
    >
      {/* Header - Curator Identity */}
      <div className={cn("px-8 mb-10 flex items-center gap-4", collapsed && "px-4 justify-center")}>
        <div className="w-10 h-10 rounded-lg overflow-hidden bg-primary-container flex items-center justify-center flex-shrink-0">
          <Brain className="w-6 h-6 text-white" />
        </div>
        {!collapsed && (
          <div>
            <h2 className="font-body text-sm font-semibold tracking-tight text-primary">Guppy</h2>
            <p className="text-xs text-on-surface-variant/70 uppercase tracking-wider">Technical Intelligence</p>
          </div>
        )}
      </div>

      {/* Primary Navigation */}
      <nav className="flex-1 space-y-1">
        {primaryNavItems.map(renderNavItem)}
      </nav>

      {/* Secondary Navigation */}
      <div className="space-y-1 border-t border-outline-variant/10 pt-4 mt-4">
        {secondaryNavItems.map(renderNavItem)}
      </div>

      {/* New Briefing Button */}
      <div className={cn("px-6 my-6", collapsed && "px-3")}>
        <button
          onClick={() => handleNavClick("assistant")}
          className={cn(
            "w-full signature-gradient text-white py-3 rounded-lg font-bold text-sm shadow-md flex items-center justify-center gap-2 transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5",
            collapsed && "px-2"
          )}
        >
          <Plus className="w-4 h-4" />
          {!collapsed && "New Briefing"}
        </button>
      </div>

      {/* Footer */}
      <footer className="mt-auto space-y-1">
        <button
          onMouseEnter={() => setHoveredItem("help")}
          onMouseLeave={() => setHoveredItem(null)}
          className={cn(
            "w-full flex items-center text-on-surface/70 font-body text-sm font-semibold tracking-tight hover:text-primary transition-all duration-200",
            collapsed ? "justify-center px-4 py-3" : "px-6 py-3",
            hoveredItem === "help" && !collapsed && "translate-x-1"
          )}
        >
          <span className={cn(collapsed ? "" : "mr-4")}><HelpCircle className="w-5 h-5" /></span>
          {!collapsed && "Help Center"}
        </button>
        <button
          onMouseEnter={() => setHoveredItem("logout")}
          onMouseLeave={() => setHoveredItem(null)}
          className={cn(
            "w-full flex items-center text-on-surface/70 font-body text-sm font-semibold tracking-tight hover:text-primary transition-all duration-200",
            collapsed ? "justify-center px-4 py-3" : "px-6 py-3",
            hoveredItem === "logout" && !collapsed && "translate-x-1"
          )}
        >
          <span className={cn(collapsed ? "" : "mr-4")}><LogOut className="w-5 h-5" /></span>
          {!collapsed && "Log Out"}
        </button>
      </footer>
    </aside>
  )
}
