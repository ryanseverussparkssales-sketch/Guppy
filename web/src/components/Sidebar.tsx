/**
 * Sidebar Navigation Component
 * Main navigation for Guppy web UI
 */

import React from "react";
import { useAppStore } from "@/hooks/useAppState";
import { theme } from "@/styles/theme";

interface SidebarProps {
  onClose?: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ onClose }) => {
  const { activeTab, setActiveTab, workspaces, activeWorkspace } = useAppStore();

  const tabs = [
    { id: "assistant", label: "Assistant", icon: "💬" },
    { id: "library", label: "Library", icon: "📚" },
    { id: "models", label: "Models", icon: "🤖" },
    { id: "workspace", label: "Workspace", icon: "🏢" },
    { id: "settings", label: "Settings", icon: "⚙️" },
  ];

  return (
    <div
      style={{
        width: "300px",
        background: theme.colors.surface.elevated,
        borderRight: `1px solid ${theme.colors.border.soft}`,
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: theme.spacing[4],
          borderBottom: `1px solid ${theme.colors.border.soft}`,
        }}
      >
        <h1
          style={{
            margin: "0 0 12px 0",
            fontSize: theme.typography.sizes["2xl"],
            fontWeight: theme.typography.weights.bold,
            color: theme.colors.text,
            fontFamily: theme.typography.fontFamilies.serif,
          }}
        >
          Guppy
        </h1>
        {activeWorkspace && (
          <p
            style={{
              margin: 0,
              fontSize: theme.typography.sizes.sm,
              color: theme.colors.textSecondary,
            }}
          >
            {activeWorkspace.name}
          </p>
        )}
      </div>

      {/* Navigation Tabs */}
      <nav
        style={{
          flex: 1,
          overflow: "auto",
          padding: `${theme.spacing[2]} 0`,
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id);
              onClose?.();
            }}
            style={{
              width: "100%",
              padding: `${theme.spacing[3]} ${theme.spacing[4]}`,
              border: "none",
              background: activeTab === tab.id ? theme.colors.background.info : "transparent",
              color: activeTab === tab.id ? theme.colors.accent.teal : theme.colors.text,
              fontSize: theme.typography.sizes.base,
              fontWeight: activeTab === tab.id ? theme.typography.weights.semibold : theme.typography.weights.normal,
              cursor: "pointer",
              textAlign: "left",
              transition: `all ${theme.transitions.base}`,
              borderLeft: activeTab === tab.id ? `4px solid ${theme.colors.accent.teal}` : "4px solid transparent",
              display: "flex",
              alignItems: "center",
              gap: theme.spacing[3],
            }}
            onMouseEnter={(e) => {
              if (activeTab !== tab.id) {
                e.currentTarget.style.background = theme.colors.surface.base;
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== tab.id) {
                e.currentTarget.style.background = "transparent";
              }
            }}
          >
            <span style={{ fontSize: "20px" }}>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>

      {/* Workspaces List */}
      {workspaces.length > 0 && (
        <div
          style={{
            borderTop: `1px solid ${theme.colors.border.soft}`,
            padding: theme.spacing[3],
            maxHeight: "200px",
            overflow: "auto",
          }}
        >
          <p
            style={{
              fontSize: theme.typography.sizes.xs,
              color: theme.colors.textTertiary,
              textTransform: "uppercase",
              margin: `0 0 ${theme.spacing[2]} 0`,
            }}
          >
            Workspaces
          </p>
          {workspaces.map((workspace) => (
            <div
              key={workspace.id}
              style={{
                padding: `${theme.spacing[2]} ${theme.spacing[2]}`,
                fontSize: theme.typography.sizes.sm,
                color: theme.colors.text,
                cursor: "pointer",
                borderRadius: theme.borderRadius.base,
                marginBottom: theme.spacing[1],
                background:
                  activeWorkspace?.id === workspace.id
                    ? theme.colors.background.info
                    : "transparent",
                transition: `all ${theme.transitions.base}`,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = theme.colors.surface.base;
              }}
              onMouseLeave={(e) => {
                if (activeWorkspace?.id !== workspace.id) {
                  e.currentTarget.style.background = "transparent";
                }
              }}
            >
              {workspace.name}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Sidebar;
