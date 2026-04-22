import { useEffect, useRef, useCallback, useState } from 'react'

interface UseWebSocketOptions {
  url: string
  onMessage?: (data: any) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
  reconnect?: boolean
  reconnectInterval?: number
}

export const useWebSocket = (options: UseWebSocketOptions) => {
  const wsRef = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    setIsConnecting(true)

    try {
      wsRef.current = new WebSocket(options.url)

      wsRef.current.onopen = () => {
        setIsConnected(true)
        setIsConnecting(false)
        options.onOpen?.()
      }

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          options.onMessage?.(data)
        } catch {
          options.onMessage?.(event.data)
        }
      }

      wsRef.current.onerror = (event) => {
        setIsConnecting(false)
        options.onError?.(event)
      }

      wsRef.current.onclose = () => {
        setIsConnected(false)
        setIsConnecting(false)
        options.onClose?.()

        // Attempt to reconnect
        if (options.reconnect) {
          reconnectTimeoutRef.current = setTimeout(
            () => connect(),
            options.reconnectInterval || 3000
          )
        }
      }
    } catch (error) {
      setIsConnecting(false)
      console.error('WebSocket connection failed:', error)
    }
  }, [options])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
    }
  }, [])

  const send = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  useEffect(() => {
    connect()

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    isConnected,
    isConnecting,
    send,
    disconnect,
  }
}
