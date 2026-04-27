/**
 * useReminders — polls /api/reminders/due every 30 s and fires browser Notification toasts.
 *
 * Call this once near the top of App or AppShell.  It:
 *   1. Requests Notification permission on first use.
 *   2. Polls the API every 30 s for due reminders.
 *   3. Shows a browser Notification for each one (works even when tab is backgrounded).
 *   4. Optionally speaks the reminder via TTS if voiceEnabled is passed.
 */
import { useEffect, useRef } from 'react'
import api from '../api/client'

interface DueReminder {
  id: string
  message: string
  due_at: string
}

export function useReminders({ voiceEnabled = false } = {}) {
  const permissionRef = useRef<NotificationPermission>('default')

  // Request permission once
  useEffect(() => {
    if (!('Notification' in window)) return
    if (Notification.permission === 'granted') {
      permissionRef.current = 'granted'
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission().then((p) => {
        permissionRef.current = p
      })
    } else {
      permissionRef.current = Notification.permission
    }
  }, [])

  useEffect(() => {
    if (!('Notification' in window)) return

    const fire = (reminder: DueReminder) => {
      // Browser toast
      if (permissionRef.current === 'granted') {
        const n = new Notification('⏰ Guppy Reminder', {
          body: reminder.message,
          icon: '/favicon.ico',
          tag: reminder.id,
          requireInteraction: true,   // stays until dismissed
        })
        n.onclick = () => { window.focus(); n.close() }
      }

      // TTS fallback — speak via the voice API if enabled
      if (voiceEnabled) {
        api.post('/api/voices/speak', { text: reminder.message }).catch(() => {})
      }
    }

    const poll = async () => {
      try {
        const res = await api.get<DueReminder[]>('/api/reminders/due')
        const due = Array.isArray(res.data) ? res.data : []
        due.forEach(fire)
      } catch {
        // silently ignore — server may not be up yet
      }
    }

    // Poll immediately then every 30 s
    poll()
    const interval = setInterval(poll, 30_000)
    return () => clearInterval(interval)
  }, [voiceEnabled])
}
