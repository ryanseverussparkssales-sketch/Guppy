import { useState, useCallback, useRef, useEffect } from 'react'
import api from '../api/client'

interface UseVoiceOptions {
  onTranscript?: (text: string) => void
  /** Called with the final transcript after VAD-triggered auto-stop. */
  onAutoSubmit?: (text: string) => void
  onResponse?: (text: string) => void
  onError?: (error: Error) => void
  language?: string
  /** Active TTS voice ID (e.g. "bm_lewis", "21m00Tcm4TlvDq8ikWAM") */
  voiceId?: string
  /** Active TTS provider ("auto" | "kokoro" | "elevenlabs" | "sapi") */
  ttsProvider?: string
  /** When true, stream chunks to /api/voices/vad and auto-stop on 500ms silence. */
  vadAutoSend?: boolean
}

const RECORDER_MIME = (() => {
  for (const t of ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(t)) return t
  }
  return ''
})()

export const useVoice = (options: UseVoiceOptions = {}) => {
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking]   = useState(false)
  const [transcript, setTranscript]   = useState('')
  const [isSupported, setIsSupported] = useState(false)

  // Keep options in a ref so callbacks always see the latest version
  // without being in every useCallback dep array.
  const optionsRef = useRef(options)
  useEffect(() => { optionsRef.current = options })

  const recorderRef    = useRef<MediaRecorder | null>(null)
  const chunksRef      = useRef<Blob[]>([])
  const audioRef       = useRef<HTMLAudioElement | null>(null)
  const abortRef       = useRef<AbortController | null>(null)
  const vadTriggeredRef = useRef(false)
  const hadSpeechRef   = useRef(false)
  const silenceCountRef = useRef(0)

  // Sentence-queue refs for streaming TTS
  const sentenceQueueRef = useRef<string[]>([])
  const queueBusyRef     = useRef(false)

  // Web Speech API fallback refs
  const recognitionRef = useRef<any>(null)
  const synthesisRef   = useRef<SpeechSynthesis | null>(
    typeof window !== 'undefined' ? window.speechSynthesis : null
  )

  useEffect(() => {
    const hasMediaRecorder    = typeof MediaRecorder !== 'undefined' && !!navigator.mediaDevices
    const hasSpeechRecognition = !!(
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    )
    setIsSupported(hasMediaRecorder || hasSpeechRecognition)

    // Init Web Speech API fallback (STT)
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (SR) {
      const rec = new SR()
      rec.continuous      = false
      rec.interimResults  = true
      rec.language        = options.language || 'en-US'
      rec.onresult = (event: any) => {
        let interim = ''
        let final   = ''
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const t = event.results[i][0].transcript
          if (event.results[i].isFinal) final += t + ' '
          else interim += t
        }
        const text = final || interim
        setTranscript(text)
        if (final && optionsRef.current.onTranscript) optionsRef.current.onTranscript(final.trim())
      }
      rec.onerror = (e: any) => optionsRef.current.onError?.(new Error(`STT error: ${e.error}`))
      rec.onend   = () => setIsListening(false)
      recognitionRef.current = rec
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── STT: start recording ───────────────────────────────────────────────────
  const startListening = useCallback(async () => {
    if (isListening) return
    setTranscript('')
    vadTriggeredRef.current = false
    hadSpeechRef.current    = false
    silenceCountRef.current = 0

    if (RECORDER_MIME && navigator.mediaDevices) {
      try {
        const stream   = await navigator.mediaDevices.getUserMedia({ audio: true })
        const chunkMs  = optionsRef.current.vadAutoSend ? 100 : 250
        const recorder = new MediaRecorder(stream, { mimeType: RECORDER_MIME })
        chunksRef.current = []

        recorder.ondataavailable = async (e) => {
          if (e.data.size === 0) return
          chunksRef.current.push(e.data)

          if (optionsRef.current.vadAutoSend && recorderRef.current?.state === 'recording') {
            try {
              const buf = await e.data.arrayBuffer()
              const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)))
              const res = await api.post('/api/voices/vad', { audio_b64: b64 })
              if (res.data?.speech) {
                hadSpeechRef.current    = true
                silenceCountRef.current = 0
              } else if (hadSpeechRef.current) {
                silenceCountRef.current++
                if (silenceCountRef.current >= 5) {
                  vadTriggeredRef.current = true
                  recorderRef.current?.stop()
                }
              }
            } catch { /* VAD errors are non-fatal */ }
          }
        }

        recorder.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop())
          const blob = new Blob(chunksRef.current, { type: RECORDER_MIME })
          if (blob.size < 1000) { vadTriggeredRef.current = false; return }
          await _transcribeBlob(blob)
        }

        recorder.start(chunkMs)
        recorderRef.current = recorder
        setIsListening(true)
      } catch {
        optionsRef.current.onError?.(new Error('Microphone access denied'))
        _fallbackStartListening()
      }
    } else {
      _fallbackStartListening()
    }
  }, [isListening]) // eslint-disable-line react-hooks/exhaustive-deps

  const _fallbackStartListening = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.start()
      setIsListening(true)
    } else {
      optionsRef.current.onError?.(new Error('Speech recognition not supported'))
    }
  }, [])

  // ── STT: stop recording ────────────────────────────────────────────────────
  const stopListening = useCallback(() => {
    if (!isListening) return
    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop()
      recorderRef.current = null
    } else if (recognitionRef.current) {
      recognitionRef.current.stop()
    }
    setIsListening(false)
  }, [isListening])

  /** Send recorded audio to /api/voices/transcribe (Deepgram → Whisper).
   *  Falls back to browser Web Speech if transcribe returns 503.
   *  Calls onAutoSubmit if this transcription was VAD-triggered. */
  const _transcribeBlob = useCallback(async (blob: Blob) => {
    const wasVad = vadTriggeredRef.current
    vadTriggeredRef.current = false

    const form = new FormData()
    form.append('file', blob, 'recording.webm')

    try {
      const res = await api.post('/api/voices/transcribe', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const { transcript: text } = res.data
      if (text) {
        setTranscript(text)
        optionsRef.current.onTranscript?.(text)
        if (wasVad) optionsRef.current.onAutoSubmit?.(text)
      }
    } catch (err: any) {
      if (err?.response?.status === 503) {
        _fallbackStartListening()
        return
      }
      optionsRef.current.onError?.(new Error('Transcription failed'))
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Sentence-queue TTS helpers ────────────────────────────────────────────
  /** Speak a single sentence. Returns a Promise that resolves when audio ends. */
  const _speakOneSync = useCallback(async (text: string): Promise<void> => {
    const voiceId  = optionsRef.current.voiceId
    const provider = optionsRef.current.ttsProvider || 'auto'
    setIsSpeaking(true)

    return new Promise<void>((resolve) => {
      api.post(
        '/api/voices/speak',
        {
          text,
          ...(voiceId ? { voice: voiceId } : {}),
          ...(provider !== 'auto' ? { provider } : {}),
        },
        { responseType: 'blob' },
      )
        .then((res) => {
          const url   = URL.createObjectURL(res.data)
          const audio = new Audio(url)
          audioRef.current = audio
          const done = () => { URL.revokeObjectURL(url); resolve() }
          audio.onended = done
          audio.onpause = done
          audio.onerror = done
          audio.play().catch(() => resolve())
        })
        .catch(() => {
          // Fallback to Web Speech API
          if (synthesisRef.current) {
            const utt = new SpeechSynthesisUtterance(text)
            utt.onend   = () => resolve()
            utt.onerror = () => resolve()
            synthesisRef.current.speak(utt)
          } else {
            resolve()
          }
        })
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  /** Drain the sentence queue, speaking one sentence at a time.
   *  Each sentence is wrapped in try/catch so a single synthesis failure
   *  never kills the rest of the queued audio. */
  const _drainQueue = useCallback(async () => {
    if (queueBusyRef.current) return
    queueBusyRef.current = true
    while (sentenceQueueRef.current.length > 0) {
      const sentence = sentenceQueueRef.current.shift()
      if (sentence) {
        try { await _speakOneSync(sentence) } catch { /* skip broken sentence, continue queue */ }
      }
    }
    setIsSpeaking(false)
    queueBusyRef.current = false
  }, [_speakOneSync])

  /** Queue a sentence for TTS. Audio plays immediately if nothing is playing. */
  const speakQueued = useCallback((text: string) => {
    if (!text.trim()) return
    sentenceQueueRef.current.push(text.trim())
    _drainQueue()
  }, [_drainQueue])

  // ── TTS: speak via backend, fall back to Web Speech API ──────────────────
  const speak = useCallback(
    async (text: string, rate = 1, _pitch = 1, _voice?: SpeechSynthesisVoice) => {
      stopSpeaking()
      setIsSpeaking(true)

      const voiceId    = optionsRef.current.voiceId
      const provider   = optionsRef.current.ttsProvider || 'auto'

      // Try backend TTS — returns audio bytes for browser playback
      try {
        const ctrl = new AbortController()
        abortRef.current = ctrl
        const res = await api.post(
          '/api/voices/speak',
          {
            text,
            speed: rate,
            ...(voiceId   ? { voice: voiceId }     : {}),
            ...(provider !== 'auto' ? { provider } : {}),
          },
          { responseType: 'blob', signal: ctrl.signal }
        )
        const url   = URL.createObjectURL(res.data)
        const audio = new Audio(url)
        audioRef.current = audio
        audio.onended = () => {
          URL.revokeObjectURL(url)
          if (audioRef.current === audio) { audioRef.current = null; setIsSpeaking(false) }
        }
        audio.onerror = () => {
          URL.revokeObjectURL(url)
          if (audioRef.current === audio) { audioRef.current = null; setIsSpeaking(false); _fallbackSpeak(text, rate) }
        }
        await audio.play()
        return
      } catch (err: any) {
        if (err?.name === 'AbortError') { setIsSpeaking(false); return }
        // Backend unavailable — fall through to Web Speech API
      }

      _fallbackSpeak(text, rate)
    },
    [] // eslint-disable-line react-hooks/exhaustive-deps
  )

  const _fallbackSpeak = useCallback((text: string, rate = 1) => {
    if (!synthesisRef.current) { setIsSpeaking(false); return }
    synthesisRef.current.cancel()
    const utt   = new SpeechSynthesisUtterance(text)
    utt.rate    = rate
    utt.onstart = () => setIsSpeaking(true)
    utt.onend   = () => setIsSpeaking(false)
    utt.onerror = () => setIsSpeaking(false)
    synthesisRef.current.speak(utt)
  }, [])

  const stopSpeaking = useCallback(() => {
    sentenceQueueRef.current = []  // drain pending sentences
    queueBusyRef.current = false
    abortRef.current?.abort()
    abortRef.current = null
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    synthesisRef.current?.cancel()
    setIsSpeaking(false)
  }, [])

  const getAvailableVoices = useCallback(() => {
    return synthesisRef.current?.getVoices() || []
  }, [])

  return {
    isListening,
    isSpeaking,
    isSupported,
    transcript,
    startListening,
    stopListening,
    speak,
    speakQueued,
    stopSpeaking,
    getAvailableVoices,
  }
}
