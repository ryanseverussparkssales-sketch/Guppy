/**
 * StatusPanel Component
 * Right-side drawer showing status and quick actions
 */

import React from "react";
import { useAppStore } from "@/hooks/useAppState";
import { theme } from "@/styles/theme";

const StatusPanel: React.FC = () => {
  const { messagesLoading, workspacesLoading, modelsLoading, isOnline } = useAppStore();

  const tools = [
    { id: "files", label: "Files", icon: "📄" },
    { id: "notes", label: "Notes", icon: "📝" },
    { id: "debug", label: "Debug", icon: "🐛" },
    { id: "terminal", label: "Terminal", icon: "⌨️" },
  ];

  const isLoading = messagesLoading || workspacesLoading || modelsLoading;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        gap: theme.spacing[4],
        padding: theme.spacing[4],
      }}
    >
      {/* Status Header */}
      <div>
        <h3
          style={{
            margin: "0 0 12px 0",
            fontSize: theme.typography.sizes.sm,
            color: theme.colors.textTertiary,
            textTransform: "uppercase",
            letterSpacing: "1px",
          }}
        >
          Status
        </h3>
        <div
          style={{
            padding: theme.spacing[3],
            background: theme.colors.surface.base,
            borderRadius: theme.borderRadius.md,
            display: "flex",
            alignItems: "center",
            gap: theme.spacing[2],
          }}
        >
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: isOnline ? theme.colors.status.success : theme.colors.status.error,
            }}
          />
          <span style={{ fontSize: theme.typography.sizes.sm }}>
            {isOnline ? "Online" : "Offline"}
          </span>
          {isLoading && (
            <span style={{ marginLeft: "auto", fontSize: "12px", animation: "spin 1s linear infinite" }}>
              ⟳
            </span>
          )}
        </div>
      </div>

      {/* Quick Tools */}
      <div>
        <h3
          style={{
            margin: "0 0 12px 0",
            fontSize: theme.typography.sizes.sm,
            color: theme.colors.textTertiary,
            textTransform: "uppercase",
            letterSpacing: "1px",
          }}
        >
          Tools
        </h3>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: theme.spacing[2],
          }}
        >
          {tools.map((tool) => (
            <button
              key={tool.id}
              style={{
                ...theme.componentStyles.button.secondary,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: theme.spacing[1],
                padding: theme.spacing[3],
              }}
            >
              <span style={{ fontSize: "24px" }}>{tool.icon}</span>
              <span style={{ fontSize: theme.typography.sizes.xs }}>{tool.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Activity Log */}
      <div style={{ flex: 1, overflow: "hidden" }}>
        <h3
          style={{
            margin: "0 0 12px 0",
            fontSize: theme.typography.sizes.sm,
            color: theme.colors.textTertiary,
            textTransform: "uppercase",
            letterSpacing: "1px",
          }}
        >
          Activity
        </h3>
        <div
          style={{
            height: "100%",
            overflow: "auto",
            background: theme.colors.surface.base,
            borderRadius: theme.borderRadius.md,
            padding: theme.spacing[3],
            fontSize: theme.typography.sizes.xs,
            color: theme.colors.textSecondary,
          }}
        >
          <p style={{ margin: 0 }}>
            {isLoading ? "Loading activity..." : "Ready"}
          </p>
        </div>
      </div>

      {/* Settings */}
      <button
        style={{
          ...theme.componentStyles.button.secondary,
          width: "100%",
        }}
      >
        Settings
      </button>
    </div>
  );
};

export default StatusPanel;
