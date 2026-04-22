/**
 * TopBar Component
 * Global search, model selector, runtime status
 */

import React, { useState } from "react";
import { useAppStore } from "@/hooks/useAppState";
import { theme } from "@/styles/theme";

const TopBar: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const { activeModel, runtimeStatus, toggleSidebar } = useAppStore();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Search:", searchQuery);
  };

  return (
    <div
      style={{
        height: "64px",
        background: theme.colors.surface.elevated,
        borderBottom: `1px solid ${theme.colors.border.soft}`,
        display: "flex",
        alignItems: "center",
        paddingLeft: theme.spacing[4],
        paddingRight: theme.spacing[4],
        gap: theme.spacing[4],
      }}
    >
      <button
        onClick={toggleSidebar}
        style={{
          background: "none",
          border: "none",
          fontSize: "24px",
          cursor: "pointer",
          padding: 0,
        }}
        aria-label="Toggle sidebar"
      >
        =
      </button>

      <form
        onSubmit={handleSearch}
        style={{
          flex: 1,
          display: "flex",
          maxWidth: "400px",
        }}
      >
        <input
          type="text"
          placeholder="Search..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{
            ...theme.componentStyles.input,
            width: "100%",
            flex: 1,
          }}
        />
      </form>

      <div style={{ flex: 1 }} />

      {activeModel && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: theme.spacing[2],
            padding: `${theme.spacing[2]} ${theme.spacing[3]}`,
            background: theme.colors.background.info,
            borderRadius: theme.borderRadius.md,
            fontSize: theme.typography.sizes.sm,
            color: theme.colors.accent.teal,
          }}
        >
          <span style={{ fontSize: "14px" }}>AI</span>
          {activeModel.name}
        </div>
      )}

      {runtimeStatus && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: theme.spacing[2],
            padding: `${theme.spacing[2]} ${theme.spacing[3]}`,
            background:
              runtimeStatus.status === "healthy"
                ? theme.colors.background.success
                : runtimeStatus.status === "degraded"
                  ? theme.colors.background.warning
                  : theme.colors.background.error,
            borderRadius: theme.borderRadius.md,
            fontSize: theme.typography.sizes.sm,
            color:
              runtimeStatus.status === "healthy"
                ? theme.colors.status.success
                : runtimeStatus.status === "degraded"
                  ? theme.colors.status.warning
                  : theme.colors.status.error,
          }}
        >
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background:
                runtimeStatus.status === "healthy"
                  ? theme.colors.status.success
                  : runtimeStatus.status === "degraded"
                    ? theme.colors.status.warning
                    : theme.colors.status.error,
            }}
          />
          {runtimeStatus.launcherLabel ||
            (runtimeStatus.status.charAt(0).toUpperCase() + runtimeStatus.status.slice(1))}
        </div>
      )}
    </div>
  );
};

export default TopBar;
