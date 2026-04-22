import React from "react";
import { useAppStore } from "@/hooks/useAppState";
import { theme } from "@/styles/theme";

const WorkspacePage: React.FC = () => {
  const { workspaces, activeWorkspace, workspacesLoading } = useAppStore();

  return (
    <div>
      <div style={{ marginBottom: theme.spacing[6] }}>
        <h1
          style={{
            fontSize: theme.typography.sizes["3xl"],
            fontWeight: theme.typography.weights.bold,
            fontFamily: theme.typography.fontFamilies.serif,
            margin: "0 0 8px 0",
          }}
        >
          Workspaces
        </h1>
        <p style={{ color: theme.colors.textSecondary, margin: 0 }}>
          Active workspace: <strong>{activeWorkspace?.name || "none"}</strong>
        </p>
      </div>

      {workspacesLoading ? (
        <p style={{ color: theme.colors.textSecondary }}>Loading workspaces...</p>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: theme.spacing[4],
          }}
        >
          {workspaces.map((workspace) => (
            <div
              key={workspace.id}
              style={{
                ...theme.componentStyles.card,
                borderColor:
                  activeWorkspace?.id === workspace.id
                    ? theme.colors.accent.teal
                    : theme.colors.border.soft,
              }}
            >
              <h2
                style={{
                  margin: `0 0 ${theme.spacing[2]} 0`,
                  fontSize: theme.typography.sizes.xl,
                  fontFamily: theme.typography.fontFamilies.serif,
                }}
              >
                {workspace.name}
              </h2>
              <p style={{ margin: `0 0 ${theme.spacing[2]} 0`, color: theme.colors.textSecondary }}>
                {workspace.description || "No description yet."}
              </p>
              <p style={{ margin: 0, color: theme.colors.textTertiary, fontSize: theme.typography.sizes.sm }}>
                Type: {workspace.type} | Status: {workspace.status}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default WorkspacePage;
