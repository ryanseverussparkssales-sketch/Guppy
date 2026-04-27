import { useState } from "react"
import { useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"
import { Tooltip } from "@/components/ui/tooltip"
import {
  MessageSquare,
  Users,
  BookText,
  Plus,
  HelpCircle,
  Wrench,
  Settings,
  Rocket,
} from "lucide-react"

interface NavItem {
  id: string
  label: string
  icon: React.ReactNode
  view: string
}

const primaryNavItems: NavItem[] = [
  { id: "chat",          label: "Chat",          icon: <MessageSquare className="w-5 h-5" />, view: "assistant" },
  { id: "launch-control", label: "Launch Control", icon: <Rocket className="w-5 h-5" />,      view: "launch-control" },
  { id: "personas",      label: "Personas",      icon: <Users className="w-5 h-5" />,         view: "personas" },
  { id: "instructions",  label: "Instructions",  icon: <BookText className="w-5 h-5" />,      view: "instructions" },
  { id: "tools",         label: "Tools",         icon: <Wrench className="w-5 h-5" />,        view: "tools" },
]

const secondaryNavItems: NavItem[] = [
  { id: "settings", label: "Settings", icon: <Settings className="w-5 h-5" />, view: "settings" },
]

interface SidebarProps {
  collapsed: boolean
  onToggleCollapse: () => void
}

const ROUTE_TO_VIEW: Record<string, string> = {
  '/':               'assistant',
  '/assistant':      'assistant',
  '/launch-control': 'launch-control',
  '/personas':       'personas',
  '/library':        'personas',
  '/instructions':   'instructions',
  '/tools':          'tools',
  '/voices':         'tools',
  '/desktop':        'tools',
  '/settings':       'settings',
  '/status':         'settings',
  '/admin':          'settings',
  '/agents':         'launch-control',
  '/instances':      'launch-control',
  '/models':         'launch-control',
}

export function Sidebar({ collapsed }: SidebarProps) {
  const location  = useLocation()
  const activeView = ROUTE_TO_VIEW[location.pathname] ?? 'assistant'
  const [hoveredItem, setHoveredItem] = useState<string | null>(null)

  const handleNavClick = (view: string) => {
    window.dispatchEvent(new CustomEvent("guppy:navigate", { detail: { view } }))
  }

  const renderNavItem = (item: NavItem) => {
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
        collapsed ? "w-20" : "w-64"
      )}
    >
      {/* Logo */}
      <div className={cn("px-8 mb-10 flex items-center gap-3", collapsed && "px-4 justify-center")}>
        <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center flex-shrink-0">
          <span className="text-white font-bold text-base leading-none">G</span>
        </div>
        {!collapsed && (
          <h2 className="font-body text-base font-bold tracking-tight text-on-surface">Guppy</h2>
        )}
      </div>

      {/* Primary Navigation */}
      <nav className="flex-1 space-y-0.5">
        {primaryNavItems.map(renderNavItem)}
      </nav>

      {/* Secondary Navigation */}
      <div className="space-y-0.5 border-t border-outline-variant/10 pt-3 mt-3">
        {secondaryNavItems.map(renderNavItem)}
      </div>

      {/* New Chat button */}
      <div className={cn("px-5 my-5", collapsed && "px-3")}>
        <button
          onClick={() => handleNavClick("assistant")}
          className={cn(
            "w-full bg-primary text-white py-2.5 rounded-xl font-semibold text-sm shadow-sm flex items-center justify-center gap-2 transition-all duration-200 hover:bg-primary/90",
            collapsed && "px-2"
          )}
        >
          <Plus className="w-4 h-4" />
          {!collapsed && "New Chat"}
        </button>
      </div>

      {/* Help footer */}
      <footer className="space-y-0.5">
        <button
          onMouseEnter={() => setHoveredItem("help")}
          onMouseLeave={() => setHoveredItem(null)}
          className={cn(
            "w-full flex items-center text-on-surface/50 font-body text-sm font-medium hover:text-on-surface transition-all duration-200",
            collapsed ? "justify-center px-4 py-3" : "px-6 py-3",
            hoveredItem === "help" && !collapsed && "translate-x-1"
          )}
        >
          <span className={cn(collapsed ? "" : "mr-4")}><HelpCircle className="w-5 h-5" /></span>
          {!collapsed && "Help"}
        </button>
      </footer>
    </aside>
  )
}
