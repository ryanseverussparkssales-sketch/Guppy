/**
 * Store Module Re-export Shim
 *
 * This file acts as the main entry point for store imports.
 * It re-exports all store modules from the ./store directory.
 *
 * Module resolution will find this file when importing @/store,
 * ensuring all exports (including syncManager) are available.
 */

export { useAppStore, useChatStore, useSettingsStore, useWorkspaceStore, useUIStore } from './store/appStore'
export type { AppState, Provider } from './store/appStore'
export { syncManager, SyncManager, APIError } from './store/syncManager'
