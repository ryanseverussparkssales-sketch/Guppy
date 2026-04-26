/**
 * =============================================================================
 * JWT TOKEN REFRESH HOOK (useTokenRefresh)
 * =============================================================================
 *
 * Proactively refreshes JWT tokens before expiry to prevent 401 errors.
 *
 * Features:
 * - Decodes JWT to extract expiry time
 * - Automatically schedules refresh 5 minutes before expiry
 * - Prevents race conditions (only one refresh in flight at a time)
 * - Handles errors gracefully (logs but doesn't crash)
 * - Cleans up timers on unmount
 *
 * Usage in main.tsx or ApiProvider:
 *   useTokenRefresh()
 *
 * =============================================================================
 */

import { useEffect, useRef } from 'react'
import { api } from '../api/client'

/**
 * Decode JWT payload without verification (client-side only)
 * WARNING: This does NOT verify the signature. Only safe for client-side
 * token inspection because server validates the token on each request.
 */
function decodeJWT(token: string): { exp?: number; [key: string]: any } | null {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null

    // Decode the payload (second part)
    const payload = parts[1]
    const decoded = JSON.parse(
      atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    )
    return decoded
  } catch (error) {
    console.error('Failed to decode JWT:', error)
    return null
  }
}

/**
 * Hook to manage proactive JWT token refresh
 *
 * Integrates with axios client to automatically refresh tokens before expiry.
 * Should be called once in the app root (e.g., inside ApiProvider or main.tsx).
 *
 * Refresh timing:
 * - Refresh window: 5 minutes before expiry
 * - On success: Token persisted to localStorage, next refresh scheduled
 * - On failure: Logs warning, relies on reactive 401 interceptor fallback
 */
export function useTokenRefresh(): void {
  const refreshTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isRefreshingRef = useRef(false)

  /**
   * Schedule the next token refresh based on current token expiry
   */
  const scheduleRefresh = () => {
    // Clear any pending refresh
    if (refreshTimeoutRef.current) {
      clearTimeout(refreshTimeoutRef.current)
    }

    const token = localStorage.getItem('accessToken')
    if (!token) {
      console.debug('No token in storage, skipping refresh schedule')
      return
    }

    const decoded = decodeJWT(token)
    if (!decoded || !decoded.exp) {
      console.warn('Could not decode token exp claim, skipping refresh')
      return
    }

    // exp is in seconds, convert to milliseconds
    const expiryTime = decoded.exp * 1000
    const nowTime = Date.now()
    const timeUntilExpiry = expiryTime - nowTime

    // Refresh window: 5 minutes before expiry
    const REFRESH_WINDOW = 5 * 60 * 1000 // 5 minutes

    if (timeUntilExpiry <= REFRESH_WINDOW) {
      // Token is expiring soon, refresh immediately
      console.debug(
        `Token expires in ${Math.round(timeUntilExpiry / 1000)}s, refreshing now`
      )
      performRefresh()
    } else {
      // Schedule refresh for 5 minutes before expiry
      const delayUntilRefresh = timeUntilExpiry - REFRESH_WINDOW
      console.debug(
        `Token expires in ${Math.round(timeUntilExpiry / 1000)}s, scheduling refresh in ${Math.round(delayUntilRefresh / 1000)}s`
      )

      refreshTimeoutRef.current = setTimeout(() => {
        performRefresh()
      }, delayUntilRefresh)
    }
  }

  /**
   * Perform the actual token refresh request
   */
  const performRefresh = async () => {
    // Prevent concurrent refresh attempts
    if (isRefreshingRef.current) {
      console.debug('Refresh already in flight, skipping duplicate')
      return
    }

    isRefreshingRef.current = true

    try {
      // Call the refresh endpoint (matches auth.py reactive 401 logic)
      // This endpoint should return { access_token: "new_token" }
      const response = await api.post('/auth/local')

      if (response.data?.access_token) {
        const newToken = response.data.access_token
        localStorage.setItem('accessToken', newToken)
        console.debug('Token refreshed successfully')

        // Schedule the next refresh based on new token
        scheduleRefresh()
      } else {
        console.warn('Token refresh response missing access_token field')
        // Rely on 401 interceptor to force re-auth
      }
    } catch (error) {
      console.warn(
        'Token refresh failed:',
        error instanceof Error ? error.message : error
      )
      // Don't show toast here — reactive 401 interceptor will handle it
      // and redirect to login if needed
    } finally {
      isRefreshingRef.current = false
    }
  }

  /**
   * Initialize token refresh on mount, clean up on unmount
   */
  useEffect(() => {
    scheduleRefresh()

    return () => {
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current)
      }
    }
  }, [])
}

/**
 * Alternative: Use in a provider context if you want to expose refresh status
 *
 * export interface TokenRefreshContextType {
 *   isRefreshing: boolean
 *   scheduleRefresh: () => void
 * }
 *
 * export const TokenRefreshContext = createContext<TokenRefreshContextType>({
 *   isRefreshing: false,
 *   scheduleRefresh: () => {},
 * })
 */
