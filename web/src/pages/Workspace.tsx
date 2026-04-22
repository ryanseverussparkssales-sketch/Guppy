import React from "react";
import { theme } from "@/styles/theme";

const WorkspacePage: React.FC = () => (
  <div style={{ textAlign: "center", paddingTop: theme.spacing[12] }}>
    <div style={{ fontSize: "64px", marginBottom: theme.spacing[4] }}>🏢</div>
    <h1 style={{ fontSize: theme.typography.sizes["3xl"], fontWeight: theme.typography.weights.bold, fontFamily: theme.typography.fontFamilies.serif }}>Workspace</h1>
    <p style={{ color: theme.colors.textSecondary }}>This page is under development</p>
  </div>
);

export default WorkspacePage;
