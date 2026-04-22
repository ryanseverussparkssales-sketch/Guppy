/**
 * Assistant Page
 * Main chat interface
 */

import React, { useState } from "react";
import { useAppStore } from "@/hooks/useAppState";
import { useAPI, getAPIClient } from "@/hooks/useAPI";
import { theme } from "@/styles/theme";

const AssistantPage: React.FC = () => {
  const { messages, sendMessage, activeWorkspace, messagesLoading, activeModel } = useAppStore();
  const [inputValue, setInputValue] = useState("");

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || !activeWorkspace) return;

    try {
      await sendMessage(inputValue);
      setInputValue("");
    } catch (error) {
      console.error("Failed to send message:", error);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        maxWidth: "900px",
        margin: "0 auto",
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: theme.spacing[6] }}>
        <h1
          style={{
            fontSize: theme.typography.sizes["3xl"],
            fontWeight: theme.typography.weights.bold,
            margin: "0 0 8px 0",
            fontFamily: theme.typography.fontFamilies.serif,
          }}
        >
          Assistant
        </h1>
        {activeModel && (
          <p style={{ color: theme.colors.textSecondary, margin: 0 }}>
            Using <strong>{activeModel}</strong> model
          </p>
        )}
      </div>

      {/* Messages Area */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          marginBottom: theme.spacing[4],
          display: "flex",
          flexDirection: "column",
          gap: theme.spacing[3],
        }}
      >
        {messages.length === 0 ? (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              color: theme.colors.textTertiary,
            }}
          >
            <p>Start a conversation by typing a message below</p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              style={{
                alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
                maxWidth: "70%",
                padding: theme.spacing[3],
                borderRadius: theme.borderRadius.lg,
                background:
                  msg.role === "user"
                    ? theme.colors.accent.teal
                    : theme.colors.surface.base,
                color:
                  msg.role === "user"
                    ? theme.colors.textInverse
                    : theme.colors.text,
              }}
            >
              {msg.content}
            </div>
          ))
        )}
        {messagesLoading && (
          <div style={{ color: theme.colors.textSecondary }}>
            <p>Assistant is thinking...</p>
          </div>
        )}
      </div>

      {/* Input Area */}
      <form onSubmit={handleSendMessage}>
        <div style={{ display: "flex", gap: theme.spacing[2] }}>
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Type your message..."
            disabled={messagesLoading || !activeWorkspace}
            style={{
              ...theme.componentStyles.input,
              flex: 1,
            }}
          />
          <button
            type="submit"
            disabled={messagesLoading || !inputValue.trim() || !activeWorkspace}
            style={{
              ...theme.componentStyles.button.primary,
              cursor: messagesLoading ? "not-allowed" : "pointer",
            }}
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
};

export default AssistantPage;
