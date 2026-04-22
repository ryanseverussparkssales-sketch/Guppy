import React from "react";
import { useAppStore } from "@/hooks/useAppState";
import { theme } from "@/styles/theme";

const ModelsPage: React.FC = () => {
  const { models, activeModel, runtimeStatus, modelsLoading } = useAppStore();

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
          Models
        </h1>
        <p style={{ color: theme.colors.textSecondary, margin: 0 }}>
          Runtime: <strong>{runtimeStatus?.backend || "unknown"}</strong>
          {runtimeStatus?.activeModel ? ` | Active chat model: ${runtimeStatus.activeModel}` : ""}
        </p>
      </div>

      <div
        style={{
          ...theme.componentStyles.card,
          marginBottom: theme.spacing[4],
        }}
      >
        <p style={{ margin: 0, color: theme.colors.textSecondary }}>
          {runtimeStatus?.detail || "Runtime detail unavailable."}
        </p>
      </div>

      {modelsLoading ? (
        <p style={{ color: theme.colors.textSecondary }}>Loading models...</p>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: theme.spacing[4],
          }}
        >
          {models.map((model) => (
            <div
              key={model.id}
              style={{
                ...theme.componentStyles.card,
                borderColor:
                  activeModel?.id === model.id
                    ? theme.colors.accent.orange
                    : theme.colors.border.soft,
              }}
            >
              <h2
                style={{
                  margin: `0 0 ${theme.spacing[2]} 0`,
                  fontSize: theme.typography.sizes.lg,
                  fontFamily: theme.typography.fontFamilies.serif,
                }}
              >
                {model.name}
              </h2>
              <p style={{ margin: `0 0 ${theme.spacing[2]} 0`, color: theme.colors.textSecondary }}>
                Provider: {model.provider}
              </p>
              <p style={{ margin: 0, color: theme.colors.textTertiary, fontSize: theme.typography.sizes.sm }}>
                Size: {model.size} | Status: {model.status}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ModelsPage;
