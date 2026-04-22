import React from "react"
import { cn } from "@/lib/utils"
import { Tooltip } from "@/components/ui/tooltip"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  MessageSquare,
  Server,
  Library,
  Brain,
  Wrench,
  Mic,
  Settings,
  LayoutDashboard,
  ChevronLeft,
  ChevronRight,
  Shield,
  Activity,
} from "lucide-react"

interface SidebarProps {
  collapsed: boolean
  onToggleCollapse: () => void
}

interface NavItem {
  id: string
  label: string
  icon: React.ReactNode
  /** 
   * BACKEND: View ID that maps to route/view
   * Used by App.tsx to render the correct view
   */
  view: string
}

const mainNavItems: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: <LayoutDashboard size={20} />, view: "dashboard" },
  { id: "assistant", label: "Assistant", icon: <MessageSquare size={20} />, view: "assistant" },
  { id: "instances", label: "Instances", icon: <Server size={20} />, view: "instances" },
  { id: "library", label: "Library", icon: <Library size={20} />, view: "library" },
]

const configNavItems: NavItem[] = [
  { id: "models", label: "Models", icon: <Brain size={20} />, view: "models" },
  { id: "tools", label: "Tools", icon: <Wrench size={20} />, view: "tools" },
  { id: "voices", label: "Voices", icon: <Mic size={20} />, view: "voices" },
]

const systemNavItems: NavItem[] = [
  { id: "status", label: "Status", icon: <Activity size={20} />, view: "status" },
  { id: "admin", label: "Admin", icon: <Shield size={20} />, view: "admin" },
  { id: "settings", label: "Settings", icon: <Settings size={20} />, view: "settings" },
]

/**
 * Sidebar - Main navigation component
 * 
 * BACKEND INTEGRATION:
 * - Navigation items map to views via the `view` property
 * - The active view is stored in the global store (useStore)
 * - Collapsed state is persisted to localStorage
 */
export function Sidebar({ collapsed, onToggleCollapse }: SidebarProps) {
  // TODO: Connect to global store for active view
  const [activeView, setActiveView] = React.useState("dashboard")

  const handleNavClick = (view: string) => {
    setActiveView(view)
    // BACKEND: This should update the global store
    // store.setActiveView(view)
    window.dispatchEvent(new CustomEvent("guppy:navigate", { detail: { view } }))
  }

  return (
    <aside
      className={cn(
        "flex flex-col h-full bg-sidebar border-r border-sidebar-border transition-all duration-300 ease-in-out",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-4 border-b border-sidebar-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
            <span className="text-primary-foreground font-bold text-sm">G</span>
          </div>
          {!collapsed && (
            <span className="font-semibold text-sidebar-foreground">Guppy</span>
          )}
        </div>
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 py-4">
        <nav className="space-y-6 px-2">
          <NavSection
            title="Main"
            items={mainNavItems}
            collapsed={collapsed}
            activeView={activeView}
            onNavigate={handleNavClick}
          />
          <NavSection
            title="Configuration"
            items={configNavItems}
            collapsed={collapsed}
            activeView={activeView}
            onNavigate={handleNavClick}
          />
          <NavSection
            title="System"
            items={systemNavItems}
            collapsed={collapsed}
            activeView={activeView}
            onNavigate={handleNavClick}
          />
        </nav>
      </ScrollArea>

      {/* Collapse Toggle */}
      <div className="p-2 border-t border-sidebar-border">
        <button
          onClick={onToggleCollapse}
          className="w-full flex items-center justify-center h-10 rounded-lg text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
        </button>
      </div>
    </aside>
  )
}

interface NavSectionProps {
  title: string
  items: NavItem[]
  collapsed: boolean
  activeView: string
  onNavigate: (view: string) => void
}

function NavSection({ title, items, collapsed, activeView, onNavigate }: NavSectionProps) {
  return (
    <div className="space-y-1">
      {!collapsed && (
        <h3 className="px-3 mb-2 text-xs font-medium uppercase tracking-wider text-sidebar-foreground/50">
          {title}
        </h3>
      )}
      {items.map((item) => (
        <NavButton
          key={item.id}
          item={item}
          collapsed={collapsed}
          isActive={activeView === item.view}
          onClick={() => onNavigate(item.view)}
        />
      ))}
    </div>
  )
}

interface NavButtonProps {
  item: NavItem
  collapsed: boolean
  isActive: boolean
  onClick: () => void
}

function NavButton({ item, collapsed, isActive, onClick }: NavButtonProps) {
  const button = (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-3 px-3 h-10 rounded-lg transition-colors",
        isActive
          ? "bg-sidebar-accent text-sidebar-accent-foreground"
          : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
      )}
    >
      <span className="flex-shrink-0">{item.icon}</span>
      {!collapsed && <span className="text-sm font-medium">{item.label}</span>}
    </button>
  )

  if (collapsed) {
    return (
      <Tooltip content={item.label} side="right">
        {button}
      </Tooltip>
    )
  }

  return button
}
