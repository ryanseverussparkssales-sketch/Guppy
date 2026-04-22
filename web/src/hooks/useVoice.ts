import { useState, useCallback, useRef, useEffect } from 'react'

interface UseVoiceOptions {
  onTranscript?: (text: string) => void
  onError?: (error: Error) => void
  language?: string
}

export const useVoice = (options: UseVoiceOptions = {}) => {
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [transcript, setTranscript] = useState('')
  const recognitionRef = useRef<any>(null)
  const synthesisRef = useRef<SpeechSynthesis>(window.speechSynthesis)

  useEffect(() => {
    // Initialize speech recognition
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition()
      recognitionRef.current.continuous = true
      recognitionRef.current.interimResults = true
      recognitionRef.current.language = options.language || 'en-US'

      recognitionRef.current.onstart = () => {
        setIsListening(true)
      }

      recognitionRef.current.onend = () => {
        setIsListening(false)
      }

      recognitionRef.current.onresult = (event: any) => {
        let interimTranscript = ''
        let finalTranscript = ''

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript

          if (event.results[i].isFinal) {
            finalTranscript += transcript + ' '
          } else {
            interimTranscript += transcript
          }
        }

        const text = finalTranscript || interimTranscript
        setTranscript(text)
        if (finalTranscript && options.onTranscript) {
          options.onTranscript(finalTranscript)
        }
      }

      recognitionRef.current.onerror = (event: any) => {
        const error = new Error(`Speech recognition error: ${event.error}`)
        if (options.onError) {
          options.onError(error)
        }
      }
    }
  }, [options])

  const startListening = useCallback(() => {
    if (recognitionRef.current && !isListening) {
      setTranscript('')
      recognitionRef.current.start()
    }
  }, [isListening])

  const stopListening = useCallback(() => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop()
    }
  }, [isListening])

  const speak = useCallback(
    (text: string, rate = 1, pitch = 1, voice?: SpeechSynthesisVoice) => {
      if (!synthesisRef.current) return

      // Cancel any ongoing speech
      synthesisRef.current.cancel()

      const utterance = new SpeechSynthesisUtterance(text)
      utterance.rate = rate
      utterance.pitch = pitch
      if (voice) {
        utterance.voice = voice
      }

      utterance.onstart = () => setIsSpeaking(true)
      utterance.onend = () => setIsSpeaking(false)
      utterance.onerror = () => setIsSpeaking(false)

      synthesisRef.current.speak(utterance)
    },
    []
  )

  const stopSpeaking = useCallback(() => {
    if (synthesisRef.current) {
      synthesisRef.current.cancel()
      setIsSpeaking(false)
    }
  }, [])

  const getAvailableVoices = useCallback(() => {
    return synthesisRef.current?.getVoices() || []
  }, [])

  return {
    isListening,
    isSpeaking,
    transcript,
    startListening,
    stopListening,
    speak,
    stopSpeaking,
    getAvailableVoices,
  }
}
