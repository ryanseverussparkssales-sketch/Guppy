import { useState, useCallback, useEffect, useRef } from 'react'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  metadata?: {
    files?: string[]
    confidence?: number
    source?: string
  }
}

export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}

const DB_NAME = 'GuppyDB'
const STORE_NAME = 'chatSessions'
const VERSION = 1

export const useChatHistory = () => {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const dbRef = useRef<IDBDatabase | null>(null)

  // Initialize IndexedDB
  useEffect(() => {
    const openDB = async () => {
      return new Promise<IDBDatabase>((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, VERSION)

        request.onerror = () => reject(request.error)
        request.onsuccess = () => resolve(request.result)

        request.onupgradeneeded = () => {
          const db = request.result
          if (!db.objectStoreNames.contains(STORE_NAME)) {
            const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' })
            store.createIndex('updatedAt', 'updatedAt', { unique: false })
          }
        }
      })
    }

    openDB()
      .then((db) => {
        dbRef.current = db
        loadSessions()
      })
      .catch((error) => console.error('Failed to initialize IndexedDB:', error))
  }, [])

  const loadSessions = useCallback(async () => {
    if (!dbRef.current) return

    const transaction = dbRef.current.transaction([STORE_NAME], 'readonly')
    const store = transaction.objectStore(STORE_NAME)
    const index = store.index('updatedAt')

    return new Promise<ChatSession[]>((resolve) => {
      const request = index.getAll()

      request.onsuccess = () => {
        const allSessions = request.result.sort(
          (a: ChatSession, b: ChatSession) => b.updatedAt - a.updatedAt
        )
        setSessions(allSessions)
        setIsLoading(false)
        resolve(allSessions)
      }

      request.onerror = () => {
        setIsLoading(false)
        resolve([])
      }
    })
  }, [])

  const saveSession = useCallback(
    async (session: ChatSession) => {
      if (!dbRef.current) return

      const transaction = dbRef.current.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)

      const updated = {
        ...session,
        updatedAt: Date.now(),
      }

      return new Promise<void>((resolve) => {
        const request = store.put(updated)

        request.onsuccess = () => {
          setSessions((prev) => {
            const index = prev.findIndex((s) => s.id === updated.id)
            if (index >= 0) {
              const newSessions = [...prev]
              newSessions[index] = updated
              return newSessions.sort((a, b) => b.updatedAt - a.updatedAt)
            }
            return [updated, ...prev]
          })
          resolve()
        }

        request.onerror = () => resolve()
      })
    },
    []
  )

  const createSession = useCallback(
    async (title: string = 'New Chat') => {
      const session: ChatSession = {
        id: `session-${Date.now()}`,
        title,
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      }

      await saveSession(session)
      setCurrentSession(session)
      return session
    },
    [saveSession]
  )

  const updateSessionTitle = useCallback(
    async (sessionId: string, title: string) => {
      const session = sessions.find((s) => s.id === sessionId)
      if (session) {
        await saveSession({ ...session, title })
      }
    },
    [sessions, saveSession]
  )

  const deleteSession = useCallback(
    async (sessionId: string) => {
      if (!dbRef.current) return

      const transaction = dbRef.current.transaction([STORE_NAME], 'readwrite')
      const store = transaction.objectStore(STORE_NAME)

      return new Promise<void>((resolve) => {
        const request = store.delete(sessionId)

        request.onsuccess = () => {
          setSessions((prev) => prev.filter((s) => s.id !== sessionId))
          if (currentSession?.id === sessionId) {
            setCurrentSession(null)
          }
          resolve()
        }

        request.onerror = () => resolve()
      })
    },
    [currentSession]
  )

  const addMessage = useCallback(
    async (message: ChatMessage) => {
      if (!currentSession) return

      const updated = {
        ...currentSession,
        messages: [...currentSession.messages, message],
      }

      setCurrentSession(updated)
      await saveSession(updated)
    },
    [currentSession, saveSession]
  )

  const clearSession = useCallback(
    async (sessionId: string) => {
      const session = sessions.find((s) => s.id === sessionId)
      if (session) {
        const cleared = { ...session, messages: [] }
        await saveSession(cleared)
        if (currentSession?.id === sessionId) {
          setCurrentSession(cleared)
        }
      }
    },
    [sessions, currentSession, saveSession]
  )

  return {
    sessions,
    currentSession,
    isLoading,
    setCurrentSession,
    createSession,
    saveSession,
    updateSessionTitle,
    deleteSession,
    addMessage,
    clearSession,
    loadSessions,
  }
}
