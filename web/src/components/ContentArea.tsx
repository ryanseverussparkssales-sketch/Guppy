/**
 * ContentArea Component
 * Routes to different pages based on active tab
 */

import React from "react";
import { useAppStore } from "@/hooks/useAppState";
import { theme } from "@/styles/theme";
import AssistantPage from "@/pages/Assistant";
import LibraryPage from "@/pages/Library";
import ModelsPage from "@/pages/Models";
import WorkspacePage from "@/pages/Workspace";
import SettingsPage from "@/pages/Settings";

const ContentArea: React.FC = () => {
  const { activeTab } = useAppStore();

  const renderContent = () => {
    switch (activeTab) {
      case "assistant":
        return <AssistantPage />;
      case "library":
        return <LibraryPage />;
      case "models":
        return <ModelsPage />;
      case "workspace":
        return <WorkspacePage />;
      case "settings":
        return <SettingsPage />;
      default:
        return <AssistantPage />;
    }
  };

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        overflow: "auto",
        padding: theme.spacing[6],
      }}
    >
      {renderContent()}
    </div>
  );
};

export default ContentArea;
