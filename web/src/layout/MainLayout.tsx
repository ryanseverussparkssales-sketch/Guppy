/**
 * Main Layout Component
 * Root layout for the Guppy web UI with navigation, content area, and status panel
 */

import React, { useEffect } from "react";
import { useAppStore } from "@/hooks/useAppState";
import { theme } from "@/styles/theme";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import StatusPanel from "@/components/StatusPanel";
import ContentArea from "@/components/ContentArea";

const MainLayout: React.FC = () => {
  const { sidebarOpen, toggleSidebar, fetchWorkspaces, fetchModels, getRuntimeStatus, isOnline } = useAppStore();

  // Initialize data on mount
  useEffect(() => {
    fetchWorkspaces();
    fetchModels();
    getRuntimeStatus();

    // Check online status
    const handleOnline = () => useAppStore.setState({ isOnline: true });
    const handleOffline = () => useAppStore.setState({ isOnline: false });

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        background: theme.colors.surface.base,
        color: theme.colors.text,
        fontFamily: theme.typography.fontFamilies.sans,
      }}
    >
      {/* Sidebar */}
      {sidebarOpen && <Sidebar onClose={toggleSidebar} />}

      {/* Main content area */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          flex: 1,
          overflow: "hidden",
          position: "relative",
        }}
      >
        {/* Top bar */}
        <TopBar />

        {/* Content and status panel */}
        <div
          style={{
            display: "flex",
            flex: 1,
            overflow: "hidden",
            gap: "1px",
            background: theme.colors.border.soft,
          }}
        >
          {/* Main content */}
          <div
            style={{
              flex: 1,
              overflow: "auto",
              background: theme.colors.surface.base,
            }}
          >
            <ContentArea />
          </div>

          {/* Right status panel */}
          <div
            style={{
              width: "320px",
              background: theme.colors.surface.elevated,
              borderLeft: `1px solid ${theme.colors.border.soft}`,
              overflow: "auto",
            }}
          >
            <StatusPanel />
          </div>
        </div>
      </div>

      {/* Offline indicator */}
      {!isOnline && (
        <div
          style={{
            position: "fixed",
            bottom: theme.spacing[4],
            right: theme.spacing[4],
            background: theme.colors.status.warning,
            color: theme.colors.text,
            padding: `${theme.spacing[2]} ${theme.spacing[4]}`,
            borderRadius: theme.borderRadius.base,
            fontSize: theme.typography.sizes.sm,
            boxShadow: theme.shadows.md,
            zIndex: 1000,
          }}
        >
          Offline - Changes will sync when reconnected
        </div>
      )}
    </div>
  );
};

export default MainLayout;
