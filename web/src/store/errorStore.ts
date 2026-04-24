/**
 * Error State Store (Zustand)
 *
 * Global error management for displaying error toasts and tracking error history.
 * Allows any part of the application to show error notifications via updateError().
 *
 * Usage:
 *   import { useErrorStore } from './store/errorStore'
 *
 *   // In a component:
 *   const { updateError, errors } = useErrorStore()
 *   updateError('CHAT_FAILED_TO_SEND', 'Failed to send message')
 *
 *   // In syncManager or API code:
 *   import { useErrorStore } from './store/errorStore'
 *   useErrorStore.getState().updateError(errorCode, message, onRetry)
 */

import { create } from 'zustand'
import { FormattedError, parseApiError } from '@/utils/errorMessages'

export interface ErrorEntry {
  /**
   * Unique error ID (timestamp + random)
   */
  id: string

  /**
   * Error code
   */
  code: string

  /**
   * User-friendly message
   */
  message: string

  /**
   * When error occurred
   */
  timestamp: Date

  /**
   * Optional retry callback
   */
  onRetry?: () => Promise<void>

  /**
   * Parsed error details
   */
  details?: FormattedError
}

interface ErrorState {
  /**
   * Currently active errors (to display as toasts)
   */
  errors: ErrorEntry[]

  /**
   * History of all errors (for debugging/telemetry)
   */
  history: ErrorEntry[]

  /**
   * Maximum errors to keep in history
   */
  maxHistorySize: number

  /**
   * Add or update an error
   */
  updateError: (code: string, message: string, onRetry?: () => Promise<void>) => void

  /**
   * Add error from Error object or error string
   */
  addError: (error: Error | string | FormattedError, message?: string, onRetry?: () => Promise<void>) => void

  /**
   * Remove specific error by ID
   */
  removeError: (id: string) => void

  /**
   * Clear all current errors
   */
  clearErrors: () => void

  /**
   * Clear error history
   */
  clearHistory: () => void
}

export const useErrorStore = create<ErrorState>((set, get) => ({
  errors: [],
  history: [],
  maxHistorySize: 100,

  updateError: (code: string, message: string, onRetry?: () => Promise<void>) => {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    const entry: ErrorEntry = {
      id,
      code,
      message,
      timestamp: new Date(),
      onRetry,
    }

    set((state) => ({
      errors: [...state.errors, entry],
      history: [entry, ...state.history].slice(0, state.maxHistorySize),
    }))

    return id
  },

  addError: (error: Error | string | FormattedError, message?: string, onRetry?: () => Promise<void>) => {
    let code = 'UNKNOWN_ERROR'
    let displayMessage = message

    // Parse error
    if (typeof error === 'string') {
      code = error
      if (!displayMessage) {
        const parsed = parseApiError(error)
        displayMessage = parsed.message
      }
    } else if (error instanceof Error) {
      const parsed = parseApiError(error)
      code = parsed.code
      displayMessage = displayMessage || parsed.message
    } else if ('code' in error) {
      code = error.code
      displayMessage = displayMessage || error.message
    }

    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    const entry: ErrorEntry = {
      id,
      code,
      message: displayMessage || 'An error occurred',
      timestamp: new Date(),
      onRetry,
      details: typeof error === 'string' ? parseApiError(error) : error instanceof Error ? parseApiError(error) : error,
    }

    set((state) => ({
      errors: [...state.errors, entry],
      history: [entry, ...state.history].slice(0, state.maxHistorySize),
    }))

    return id
  },

  removeError: (id: string) => {
    set((state) => ({
      errors: state.errors.filter((e) => e.id !== id),
    }))
  },

  clearErrors: () => {
    set({ errors: [] })
  },

  clearHistory: () => {
    set({ history: [] })
  },
}))

/**
 * Get error store instance without React hook
 * Useful in non-React code like syncManager
 *
 * Usage:
 *   import { getErrorStore } from './store/errorStore'
 *   getErrorStore().updateError(code, message)
 */
export function getErrorStore() {
  return useErrorStore.getState()
}
