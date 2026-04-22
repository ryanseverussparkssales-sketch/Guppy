/**
 * Page Exports
 * Placeholder pages for all tabs
 */

import React from "react";
import { theme } from "@/styles/theme";

const PlaceholderPage = ({ title, emoji }: { title: string; emoji: string }) => {
  return (
    <div style={{ textAlign: "center", paddingTop: theme.spacing[12] }}>
      <div style={{ fontSize: "64px", marginBottom: theme.spacing[4] }}>{emoji}</div>
      <h1
        style={{
          fontSize: theme.typography.sizes["3xl"],
          fontWeight: theme.typography.weights.bold,
          fontFamily: theme.typography.fontFamilies.serif,
        }}
      >
        {title}
      </h1>
      <p style={{ color: theme.colors.textSecondary }}>
        This page is under development
      </p>
    </div>
  );
};

export const LibraryPage = () => (
  <PlaceholderPage title="Library" emoji="📚" />
);

export const ModelsPage = () => (
  <PlaceholderPage title="Models" emoji="🤖" />
);

export const WorkspacePage = () => (
  <PlaceholderPage title="Workspace" emoji="🏢" />
);

export const SettingsPage = () => (
  <PlaceholderPage title="Settings" emoji="⚙️" />
);