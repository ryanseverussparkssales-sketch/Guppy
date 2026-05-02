/**
 * useSurfaceEvents — subscribes to /api/surface/events SSE with exponential backoff.
 *
 * Reconnects automatically on disconnect using backoff: 2 → 4 → 8 → 16 → 32 → 60 s.
 * Resets the delay after a connection stays alive for 10 s (healthy connection).
 *
 * Usage:
 *   useSurfaceEvents((type, payload) => { ... })
 */
import { useEffect, useRef } from 'react'

type EventHandler = (type: string, payload: unknown) => void

const BASE_DELAY_MS = 2_000
const MAX_DELAY_MS  = 60_000

export function useSurfaceEvents(onEvent: EventHandler) {
  // Keep handler ref so the SSE loop always sees the latest version without
  // being included in the reconnect useEffect deps.
  const handlerRef = useRef<EventHandler>(onEvent)
  useEffect(() => { handlerRef.current = onEvent })

  useEffect(() => {
    const token   = localStorage.getItem('accessToken') || ''
    let cancelled = false
    let delay     = BASE_DELAY_MS
    let retryHandle: ReturnType<typeof setTimeout> | null = null
    let abortCtrl = new AbortController()

    async function connect() {
      if (cancelled) return
      const connectTime = Date.now()
      try {
        const res = await fetch('/api/surface/events', {
          headers: { Authorization: `Bearer ${token}` },
          signal: abortCtrl.signal,
        })
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

        const reader = res.body.getReader()
        const dec    = new TextDecoder()
        let buf      = ''
        let evType   = ''

        try {
          while (!cancelled) {
            const { done, value } = await reader.read()
            if (done) break
            buf += dec.decode(value, { stream: true })
            const lines = buf.split('\n')
            buf = lines.pop() ?? ''
            for (const line of lines) {
              if (line.startsWith('event: ')) {
                evType = line.slice(7).trim()
              } else if (line.startsWith('data: ')) {
                try {
                  const payload = JSON.parse(line.slice(6))
                  if (evType) handlerRef.current(evType, payload)
                } catch { /* ignore non-JSON */ }
                evType = ''
              }
            }
          }
        } finally {
          reader.releaseLock()
        }

        // Connection stayed healthy for >10 s → reset backoff
        if (Date.now() - connectTime > 10_000) delay = BASE_DELAY_MS

      } catch (e: any) {
        if (e?.name === 'AbortError') return  // intentional unmount — don't retry
        /* expected on disconnect — fall through to retry */
      }

      if (!cancelled) {
        retryHandle = setTimeout(() => {
          delay = Math.min(delay * 2, MAX_DELAY_MS)
          abortCtrl = new AbortController()
          connect()
        }, delay)
      }
    }

    connect()
    return () => {
      cancelled = true
      abortCtrl.abort()
      if (retryHandle) clearTimeout(retryHandle)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
}
