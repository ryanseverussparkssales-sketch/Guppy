import { useState } from "react"
import { useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"
import { Tooltip } from "@/components/ui/tooltip"
import {
  MessageCircle,
  LayoutDashboard,
  Code2,
  Settings,
  Plus,
  HelpCircle,
  BookText,
  LayoutGrid,
} from "lucide-react"

interface NavItem {
  id: string
  label: string
  icon: React.ReactNode
  view: string
  route: string
}

// Three primary surfaces — these are the top-level destinations
const primaryNavItems: NavItem[] = [
  {
    id: "companion",
    label: "Companion",
    icon: <MessageCircle className="w-5 h-5" />,
    view: "companion",
    route: "/companion",
  },
  {
    id: "workspace",
    label: "Workspace",
    icon: <LayoutDashboard className="w-5 h-5" />,
    view: "workspace",
    route: "/workspace",
  },
  {
    id: "codespace",
    label: "Codespace",
    icon: <Code2 className="w-5 h-5" />,
    view: "codespace",
    route: "/codespace",
  },
]

// Secondary: control + config destinations
const secondaryNavItems: NavItem[] = [
  { id: "control",      label: "Control Panel", icon: <LayoutGrid className="w-4 h-4" />, view: "control",      route: "/control" },
  { id: "settings",     label: "Settings",      icon: <Settings className="w-4 h-4" />,  view: "settings",     route: "/settings" },
  { id: "instructions", label: "Instructions",  icon: <BookText className="w-4 h-4" />,  view: "instructions", route: "/instructions" },
]

const ROUTE_TO_VIEW: Record<string, string> = {
  '/':               'companion',
  '/companion':      'companion',
  '/workspace':      'workspace',
  '/codespace':      'codespace',
  '/control':        'control',
  '/settings':       'settings',
  '/instructions':   'instructions',
  '/admin':          'settings',
  '/assistant':      'companion',
  '/launch-control': 'workspace',
  '/agents':         'workspace',
  '/instances':      'workspace',
  '/models':         'workspace',
}

interface SidebarProps {
  collapsed: boolean
  onToggleCollapse: () => void
}

export function Sidebar({ collapsed }: SidebarProps) {
  const location   = useLocation()
  const activeView = ROUTE_TO_VIEW[location.pathname] ?? 'companion'
  const [hoveredItem, setHoveredItem] = useState<string | null>(null)

  const handleNavClick = (view: string) => {
    window.dispatchEvent(new CustomEvent("guppy:navigate", { detail: { view } }))
  }

  const renderPrimaryItem = (item: NavItem) => {
    const isActive  = activeView === item.view
    const isHovered = hoveredItem === item.id

    const button = (
      <button
        key={item.id}
        onClick={() => handleNavClick(item.view)}
        onMouseEnter={() => setHoveredItem(item.id)}
        onMouseLeave={() => setHoveredItem(null)}
        className={cn(
          "w-full flex items-center font-body text-sm font-semibold tracking-tight transition-all duration-200 ease-viscous",
          collapsed ? "justify-center px-4 py-3.5" : "py-3",
          isActive
            ? "text-primary bg-white shadow-sm rounded-r-full pl-6 pr-4"
            : "text-on-surface/70 hover:text-primary px-6",
          !isActive && isHovered && !collapsed && "translate-x-1"
        )}
      >
        <span className={cn(collapsed ? "" : "mr-3")}>{item.icon}</span>
        {!collapsed && item.label}
      </button>
    )

    return collapsed
      ? <Tooltip key={item.id} content={item.label} side="right">{button}</Tooltip>
      : button
  }

  const renderSecondaryItem = (item: NavItem) => {
    const isActive  = activeView === item.view
    const isHovered = hoveredItem === item.id

    const button = (
      <button
        key={item.id}
        onClick={() => handleNavClick(item.view)}
        onMouseEnter={() => setHoveredItem(item.id)}
        onMouseLeave={() => setHoveredItem(null)}
        className={cn(
          "w-full flex items-center font-body text-xs font-medium tracking-tight transition-all duration-200 ease-viscous",
          collapsed ? "justify-center px-4 py-2.5" : "py-2",
          isActive
            ? "text-primary pl-6 pr-4"
            : "text-on-surface/50 hover:text-on-surface/80 px-6",
          !isActive && isHovered && !collapsed && "translate-x-1"
        )}
      >
        <span className={cn(collapsed ? "" : "mr-3")}>{item.icon}</span>
        {!collapsed && item.label}
      </button>
    )

    return collapsed
      ? <Tooltip key={item.id} content={item.label} side="right">{button}</Tooltip>
      : button
  }

  const activeSurface = ['companion', 'workspace', 'codespace'].includes(activeView)
    ? activeView
    : 'companion'

  return (
    <aside
      className={cn(
        "bg-surface-container-low flex flex-col h-full py-6 gap-y-1 overflow-y-auto custom-scrollbar transition-all duration-300 ease-viscous",
        collapsed ? "w-20" : "w-60"
      )}
    >
      {/* Logo */}
      <div className={cn("px-6 mb-8 flex items-center gap-3", collapsed && "px-4 justify-center")}>
        <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center flex-shrink-0">
          <span className="text-white font-bold text-base leading-none">G</span>
        </div>
        {!collapsed && (
          <div>
            <h2 className="font-body text-sm font-bold tracking-tight text-on-surface leading-none">Guppy</h2>
            <p className="text-xs text-on-surface-variant/50 mt-0.5">Personal AI</p>
          </div>
        )}
      </div>

      {/* Primary navigation — three surfaces */}
      <nav className="flex-1 space-y-0.5">
        {!collapsed && (
          <p className="px-6 text-[10px] font-semibold uppercase tracking-widest text-on-surface-variant/40 mb-2">
            Surfaces
          </p>
        )}
        {primaryNavItems.map(renderPrimaryItem)}
      </nav>

      {/* Secondary navigation */}
      <div className="space-y-0.5 border-t border-outline-variant/10 pt-3 mt-3">
        {!collapsed && (
          <p className="px-6 text-[10px] font-semibold uppercase tracking-widest text-on-surface-variant/30 mb-1">
            Config
          </p>
        )}
        {secondaryNavItems.map(renderSecondaryItem)}
      </div>

      {/* New session button — context-aware label */}
      <div className={cn("px-4 mt-4", collapsed && "px-3")}>
        <button
          onClick={() => handleNavClick(activeSurface)}
          className={cn(
            "w-full bg-primary text-white py-2.5 rounded-xl font-semibold text-xs shadow-sm flex items-center justify-center gap-2 transition-all duration-200 hover:bg-primary/90",
            collapsed && "px-2"
          )}
        >
          <Plus className="w-3.5 h-3.5" />
          {!collapsed && `New ${activeSurface === 'companion' ? 'Chat' : activeSurface === 'codespace' ? 'Session' : 'Task'}`}
        </button>
      </div>

      {/* Help */}
      <footer className="mt-2">
        <button
          onMouseEnter={() => setHoveredItem("help")}
          onMouseLeave={() => setHoveredItem(null)}
          className={cn(
            "w-full flex items-center text-on-surface/40 font-body text-xs font-medium hover:text-on-surface/70 transition-all duration-200",
            collapsed ? "justify-center px-4 py-3" : "px-6 py-3",
            hoveredItem === "help" && !collapsed && "translate-x-1"
          )}
        >
          <span className={cn(collapsed ? "" : "mr-3")}><HelpCircle className="w-4 h-4" /></span>
          {!collapsed && "Help"}
        </button>
      </footer>
    </aside>
  )
}
