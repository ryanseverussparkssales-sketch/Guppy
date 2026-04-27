import { useState, useEffect, useCallback, useRef } from 'react'
import { Volume2, Mic, Play, Square, Check, Activity, Headphones, RefreshCw, Wifi, WifiOff, ChevronDown } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import api from '../api/client'

interface VoiceProvider { id: string; name: string; available: boolean }
interface VoiceOption   { id: string; name: string; lang: string }
interface STTModel      { id: string; name: string }

interface VoiceData {
  tts: {
    active_provider: string
    providers: VoiceProvider[]
    voices: Record<string, VoiceOption[]>
    active_voice: string
    speed: string
  }
  stt: {
    active_provider: string
    active_model: string
    providers: VoiceProvider[]
    models: STTModel[]
    deepgram_available: boolean
  }
  voice_available: boolean
}

function parseSpeed(raw: string): number {
  const n = parseFloat(raw.replace(/[^0-9.+-]/g, ''))
  return isNaN(n) ? 1.0 : Math.max(0.5, Math.min(2.0, n))
}

export default function VoicesView() {
  const [data, setData]       = useState<VoiceData | null>(null)
  const [loading, setLoading] = useState(true)

  // TTS state
  const [ttsProvider, setTtsProvider] = useState('auto')
  const [ttsVoice, setTtsVoice]       = useState('bm_lewis')
  const [speed, setSpeed]             = useState(1.0)

  // STT state
  const [sttProvider, setSttProvider] = useState('auto')
  const [sttModel, setSttModel]       = useState('large-v3')

  // Audio devices
  const [inputDevices, setInputDevices]   = useState<MediaDeviceInfo[]>([])
  const [outputDevices, setOutputDevices] = useState<MediaDeviceInfo[]>([])
  const [inputDevice, setInputDevice]     = useState('')
  const [outputDevice, setOutputDevice]   = useState('')

  // Test playback
  const [isTesting, setIsTesting]   = useState(false)
  const [testAudio, setTestAudio]   = useState<HTMLAudioElement | null>(null)

  // STT live test
  const [isRecording, setIsRecording]   = useState(false)
  const [testTranscript, setTestTranscript] = useState('')

  // ── Fetch voice config ───────────────────────────────────────────────────
  const fetchVoices = useCallback(async () => {
    setLoading(true)
    try {
      const res    = await api.get('/api/voices')
      const d: VoiceData = res.data
      setData(d)
      setTtsProvider(d.tts.active_provider || 'auto')
      setTtsVoice(d.tts.active_voice || 'bm_lewis')
      setSpeed(parseSpeed(d.tts.speed || '1.0'))
      setSttProvider(d.stt.active_provider || 'auto')
      setSttModel(d.stt.active_model || 'large-v3')
    } catch {
      toast.error('Could not load voice settings')
    } finally {
      setLoading(false)
    }
  }, [])

  // ── Enumerate audio devices ──────────────────────────────────────────────
  const enumerateDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true })
        .then(s => s.getTracks().forEach(t => t.stop())).catch(() => {})
      const devices = await navigator.mediaDevices.enumerateDevices()
      setInputDevices(devices.filter(d => d.kind === 'audioinput'))
      setOutputDevices(devices.filter(d => d.kind === 'audiooutput'))
    } catch { /* permission denied */ }
  }, [])

  useEffect(() => {
    fetchVoices()
    enumerateDevices()
  }, [fetchVoices, enumerateDevices])

  // ── Persist settings ─────────────────────────────────────────────────────
  const saveSettings = useCallback(async (patch: Record<string, unknown>) => {
    try {
      await api.put('/api/voices/settings', patch)
    } catch {
      toast.error('Failed to save voice settings')
    }
  }, [])

  const handleProviderChange = async (id: string) => {
    setTtsProvider(id)
    await saveSettings({ tts_provider: id })
    toast.success(`TTS: ${id}`)
  }

  const handleVoiceChange = async (id: string) => {
    setTtsVoice(id)
    await saveSettings({ tts_voice: id })
  }

  const handleSpeedChange = async (v: number) => {
    setSpeed(v)
    await saveSettings({ tts_speed: String(v) })
  }

  const handleSttProviderChange = async (id: string) => {
    setSttProvider(id)
    await saveSettings({ stt_provider: id })
    toast.success(`STT: ${id}`)
  }

  const handleSttModelChange = async (id: string) => {
    setSttModel(id)
    await saveSettings({ stt_model: id })
  }

  // ── TTS test ──────────────────────────────────────────────────────────────
  const handleTestVoice = async () => {
    if (isTesting) {
      testAudio?.pause()
      setTestAudio(null)
      setIsTesting(false)
      return
    }
    setIsTesting(true)
    try {
      const res = await api.post(
        '/api/voices/speak',
        { text: 'Voice test. Guppy is ready.', voice: ttsVoice, speed, provider: ttsProvider },
        { responseType: 'blob' }
      )
      const url   = URL.createObjectURL(res.data)
      const audio = new Audio(url)
      setTestAudio(audio)
      audio.onended = () => { setIsTesting(false); setTestAudio(null); URL.revokeObjectURL(url) }
      audio.onerror = () => { setIsTesting(false); setTestAudio(null); URL.revokeObjectURL(url); toast.error('Playback failed') }
      await audio.play()
    } catch {
      try {
        await api.post('/api/voices/test', { text: 'Voice test. Guppy is ready.' })
        toast.success('Playing on server speakers')
      } catch {
        toast.error('Voice test failed — check backend logs')
      }
      setIsTesting(false)
    }
  }

  // ── STT test (record → /transcribe) ──────────────────────────────────────
  const sttRecorderRef = useRef<MediaRecorder | null>(null)

  const handleTestStt = async () => {
    if (isRecording) {
      sttRecorderRef.current?.stop()
      setIsRecording(false)
      return
    }
    setTestTranscript('')
    setIsRecording(true)
    try {
      const stream   = await navigator.mediaDevices.getUserMedia({ audio: true })
      const chunks: Blob[] = []
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus' : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType })
      sttRecorderRef.current = recorder
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data) }
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunks, { type: mimeType })
        try {
          const form = new FormData()
          form.append('file', blob, 'test.webm')
          const res = await api.post('/api/voices/transcribe', form, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
          setTestTranscript(res.data.transcript || '(no transcript)')
          toast.success(`Transcribed via ${res.data.provider}`)
        } catch {
          toast.error('Transcription failed')
          setTestTranscript('(error)')
        }
      }
      recorder.start(250)
      // Auto-stop after 5 s
      setTimeout(() => {
        if (recorder.state === 'recording') recorder.stop()
        setIsRecording(false)
      }, 5000)
    } catch {
      toast.error('Microphone access denied')
      setIsRecording(false)
    }
  }

  // ── Voices for current provider ───────────────────────────────────────────
  const providerVoices: VoiceOption[] = data?.tts.voices[ttsProvider] || data?.tts.voices['kokoro'] || []

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 border-b border-border flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Voice Settings</h1>
          <p className="text-muted-foreground mt-1">Text-to-speech and speech recognition</p>
        </div>
        <div className="flex items-center gap-3">
          {data?.voice_available
            ? <span className="flex items-center gap-1.5 text-xs text-success"><Wifi className="w-3.5 h-3.5" />Voice Ready</span>
            : <span className="flex items-center gap-1.5 text-xs text-muted-foreground"><WifiOff className="w-3.5 h-3.5" />Voice Unavailable</span>
          }
          {data?.stt.deepgram_available && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary">Deepgram</span>
          )}
          <button onClick={fetchVoices} className="p-2 rounded-lg hover:bg-muted text-muted-foreground">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <div className="max-w-4xl mx-auto p-6 space-y-10">

          {/* ── TTS ─────────────────────────────────────────────────────── */}
          <section className="space-y-5">
            <SectionHeader icon={<Volume2 className="w-5 h-5" />} color="primary"
              title="Text-to-Speech" sub="Convert AI responses to speech" />

            {/* Provider */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {(data?.tts.providers || []).map(p => (
                <ProviderCard
                  key={p.id}
                  provider={p}
                  active={ttsProvider === p.id}
                  onClick={() => handleProviderChange(p.id)}
                />
              ))}
            </div>

            {/* Voice list */}
            {providerVoices.length > 0 && (
              <div className="p-4 rounded-xl bg-card border border-border space-y-3">
                <label className="text-sm font-medium text-foreground">Voice</label>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {providerVoices.map(v => (
                    <button
                      key={v.id}
                      onClick={() => handleVoiceChange(v.id)}
                      className={cn(
                        'p-3 rounded-lg border transition-all text-left',
                        ttsVoice === v.id
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border hover:border-primary/50 text-foreground'
                      )}
                    >
                      <span className="text-sm font-medium block">{v.name}</span>
                      <span className="text-xs text-muted-foreground">{v.lang}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Speed */}
            <div className="p-4 rounded-xl bg-card border border-border">
              <label className="text-sm text-muted-foreground mb-2 block">Speed: {speed.toFixed(1)}×</label>
              <input
                type="range" min="0.5" max="2" step="0.1"
                value={speed}
                onChange={e => setSpeed(parseFloat(e.target.value))}
                onMouseUp={e  => handleSpeedChange(parseFloat((e.target as HTMLInputElement).value))}
                onTouchEnd={e => handleSpeedChange(parseFloat((e.target as HTMLInputElement).value))}
                className="w-full accent-primary"
              />
            </div>

            {/* Test TTS */}
            <button
              onClick={handleTestVoice}
              className={cn(
                'flex items-center gap-2 px-4 py-2.5 rounded-lg transition-colors font-medium text-sm',
                isTesting
                  ? 'bg-destructive text-destructive-foreground'
                  : 'bg-primary text-primary-foreground hover:bg-primary/90'
              )}
            >
              {isTesting
                ? <><Square className="w-4 h-4" />Stop<Activity className="w-4 h-4 animate-pulse ml-1" /></>
                : <><Play className="w-4 h-4" />Test Voice</>
              }
            </button>
          </section>

          <div className="border-t border-border" />

          {/* ── STT ─────────────────────────────────────────────────────── */}
          <section className="space-y-5">
            <SectionHeader icon={<Mic className="w-5 h-5" />} color="success"
              title="Speech-to-Text" sub="Convert voice to text" />

            {/* STT provider */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {(data?.stt.providers || []).map(p => (
                <ProviderCard
                  key={p.id}
                  provider={p}
                  active={sttProvider === p.id}
                  onClick={() => handleSttProviderChange(p.id)}
                  accentColor="success"
                />
              ))}
            </div>

            {/* Whisper model sub-selector (only shown when whisper/auto selected) */}
            {(sttProvider === 'whisper' || sttProvider === 'auto') && (
              <div className="p-4 rounded-xl bg-card border border-border space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-foreground">Whisper Model</label>
                  <span className="text-xs text-muted-foreground">Used as fallback in auto mode</span>
                </div>
                <div className="space-y-1.5">
                  {(data?.stt.models || []).map(m => (
                    <button
                      key={m.id}
                      onClick={() => handleSttModelChange(m.id)}
                      className={cn(
                        'w-full flex items-center gap-3 p-3 rounded-xl border-2 transition-all text-left',
                        sttModel === m.id
                          ? 'border-success bg-success/5'
                          : 'border-border hover:border-success/40'
                      )}
                    >
                      <div className={cn(
                        'w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center',
                        sttModel === m.id ? 'border-success bg-success' : 'border-muted-foreground'
                      )}>
                        {sttModel === m.id && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                      </div>
                      <span className="text-sm font-medium text-foreground">{m.name}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Test STT */}
            <div className="flex items-center gap-3">
              <button
                onClick={handleTestStt}
                className={cn(
                  'flex items-center gap-2 px-4 py-2.5 rounded-lg transition-colors font-medium text-sm',
                  isRecording
                    ? 'bg-error text-white animate-pulse'
                    : 'bg-success text-white hover:bg-success/90'
                )}
              >
                {isRecording
                  ? <><Square className="w-4 h-4" />Stop recording</>
                  : <><Mic className="w-4 h-4" />Test STT (5 s)</>
                }
              </button>
              {testTranscript && (
                <span className="text-sm text-foreground bg-muted px-3 py-2 rounded-lg flex-1 truncate">
                  {testTranscript}
                </span>
              )}
            </div>
          </section>

          <div className="border-t border-border" />

          {/* ── Audio Devices ────────────────────────────────────────────── */}
          <section className="space-y-4">
            <div className="flex items-center gap-3">
              <SectionHeader icon={<Headphones className="w-5 h-5" />} color="warning"
                title="Audio Devices" sub="Microphone and speaker selection" />
              <button onClick={enumerateDevices} className="ml-auto p-1.5 rounded hover:bg-muted text-muted-foreground">
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <DeviceSelect
                label="Microphone"
                value={inputDevice}
                onChange={setInputDevice}
                devices={inputDevices}
                fallbackPrefix="Microphone"
              />
              <DeviceSelect
                label="Speakers"
                value={outputDevice}
                onChange={setOutputDevice}
                devices={outputDevices}
                fallbackPrefix="Speaker"
              />
            </div>
          </section>

        </div>
      </div>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({
  icon, color, title, sub,
}: { icon: React.ReactNode; color: string; title: string; sub: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`p-2 rounded-lg bg-${color}/10 text-${color}`}>{icon}</div>
      <div>
        <h2 className="text-lg font-medium text-foreground">{title}</h2>
        <p className="text-sm text-muted-foreground">{sub}</p>
      </div>
    </div>
  )
}

function ProviderCard({
  provider, active, onClick, accentColor = 'primary',
}: {
  provider: { id: string; name: string; available: boolean }
  active: boolean
  onClick: () => void
  accentColor?: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={!provider.available}
      className={cn(
        'relative p-4 rounded-xl border-2 transition-all text-left',
        !provider.available && 'opacity-40 cursor-not-allowed',
        active
          ? `border-${accentColor} bg-${accentColor}/5`
          : 'border-border hover:border-primary/50'
      )}
    >
      <h3 className="font-medium text-foreground text-sm leading-tight">{provider.name}</h3>
      <p className="text-xs text-muted-foreground mt-0.5">
        {provider.available ? 'Available' : 'Not configured'}
      </p>
      {active && <Check className="absolute bottom-2 right-2 w-4 h-4 text-primary" />}
    </button>
  )
}

function DeviceSelect({
  label, value, onChange, devices, fallbackPrefix,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  devices: MediaDeviceInfo[]
  fallbackPrefix: string
}) {
  return (
    <div className="p-4 rounded-xl bg-card border border-border">
      <label className="text-sm font-medium text-foreground mb-2 block">{label}</label>
      <div className="relative">
        <select
          value={value}
          onChange={e => onChange(e.target.value)}
          className="w-full p-2.5 rounded-lg bg-muted border border-border text-foreground text-sm appearance-none pr-8"
        >
          <option value="">System default</option>
          {devices.map(d => (
            <option key={d.deviceId} value={d.deviceId}>
              {d.label || `${fallbackPrefix} ${d.deviceId.slice(0, 6)}`}
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-2.5 top-3 w-4 h-4 text-muted-foreground pointer-events-none" />
      </div>
    </div>
  )
}

