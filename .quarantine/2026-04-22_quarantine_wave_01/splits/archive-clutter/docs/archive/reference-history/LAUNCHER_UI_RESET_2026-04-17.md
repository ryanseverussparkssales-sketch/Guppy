# Launcher UI Reset

Date: 2026-04-17

## Why We Are Resetting

The previous launcher direction was over-indexing on system chrome, operator surfaces, and equal-weight panels.
That made Guppy feel harder to navigate than the local AI products it should learn from.

The new product direction is:

- chat first
- workspace organized
- file and study support easy to discover
- local power available, but secondary

## Product References

This reset is intentionally closer to:

- Open WebUI: project and document organization with power features behind the main chat flow
- AnythingLLM: workspace plus docs plus agents
- Chatbox / LibreChat: calmer chat-first navigation
- Jan: local workstation capability without making the home screen feel like an ops console

## Target Information Architecture

Primary path:

1. Chat
2. Workspaces
3. Tools
4. Settings

Advanced/system path:

1. Device
2. Local AI
3. Models
4. Runtime
5. Voice

## Core Design Rules

- The main surface should feel like a local assistant workspace, not a launcher dashboard.
- Chat owns the center of gravity.
- Workspaces own persistence, purpose, defaults, and memory.
- Tools own task actions, file help, study help, coding help, and connector actions.
- Settings owns setup, diagnostics, recovery, models, and logs.
- Advanced/system pages remain available, but they should not compete with daily use.

## Tranche 1 Changes

- Rename the primary shell language around Chat, Workspaces, Tools, and Settings.
- Demote advanced pages into a visually separate navigation group.
- Remove "App Mgmt" as the primary user-facing label.
- Remove "My PC" as the primary user-facing label.
- Reduce "tray" jargon in favor of clearer quick-action language.
- Reframe Tools as the task/action surface and Settings as the system/setup surface.

## Next Tranches

1. Build a true Library surface for files, notes, source sets, and study artifacts.
2. Move most diagnostics and connector setup fully behind Settings subsections.
3. Rework Chat so workspace memory, active files, and task chips are compact and contextual.
4. Add a clearer study/coding workflow with source lists, pinned files, and result artifacts.
