import { useState, useEffect, useCallback } from 'react'
import { Volume2, Mic, Play, Square, Check, Activity, Headphones, RefreshCw, Wifi, WifiOff } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import api from '../api/client'

interface VoiceProvider { id: string; name: string; available: boolean }
interface VoiceOption  { id: string; name: string; lang: string }
interface STTModel     { id: string; name: string }

interface VoiceData {
  tts: {
    active_provider: string
    providers: VoiceProvider[]
    voices: Record<string, VoiceOption[]>
    active_voice: string
    speed: string
  }
  stt: { active_model: string; models: STTModel[]; deepgram_available: boolean }
  voice_available: boolean
}

function parseSpeed(raw: string): number {
  const n = parseFloat(raw.replace(/[^0-9.+-]/g, ''))
  return isNaN(n) ? 1.0 : Math.max(0.5, Math.min(2.0, n))
}

export default function VoicesView() {
  const [data, setData] = useState<VoiceData | null>(null)
  const [loading, setLoading] = useState(true)

  // Editable state
  const [ttsProvider, setTtsProvider] = useState('auto')
  const [ttsVoice, setTtsVoice]       = useState('bm_lewis')
  const [speed, setSpeed]             = useState(1.0)
  const [sttModel, setSttModel]       = useState('large-v3')

  // Audio devices (browser enumeration)
  const [inputDevices, setInputDevices]   = useState<MediaDeviceInfo[]>([])
  const [outputDevices, setOutputDevices] = useState<MediaDeviceInfo[]>([])
  const [inputDevice, setInputDevice]     = useState('')
  const [outputDevice, setOutputDevice]   = useState('')

  // Test playback
  const [isTesting, setIsTesting]   = useState(false)
  const [testAudio, setTestAudio]   = useState<HTMLAudioElement | null>(null)

  // ── Fetch voice config ───────────────────────────────────────────────────
  const fetchVoices = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/api/voices')
      const d: VoiceData = res.data
      setData(d)
      setTtsProvider(d.tts.active_provider || 'auto')
      setTtsVoice(d.tts.active_voice || 'bm_lewis')
      setSpeed(parseSpeed(d.tts.speed || '1.0'))
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
      // Request permission first so labels are populated
      await navigator.mediaDevices.getUserMedia({ audio: true }).then(s => s.getTracks().forEach(t => t.stop())).catch(() => {})
      const devices = await navigator.mediaDevices.enumerateDevices()
      setInputDevices(devices.filter(d => d.kind === 'audioinput'))
      setOutputDevices(devices.filter(d => d.kind === 'audiooutput'))
    } catch { /* permission denied — leave lists empty */ }
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
    toast.success(`TTS provider set to ${id}`)
  }

  const handleVoiceChange = async (id: string) => {
    setTtsVoice(id)
    await saveSettings({ tts_voice: id })
  }

  const handleSpeedChange = async (v: number) => {
    setSpeed(v)
    await saveSettings({ tts_speed: `${v >= 1 ? '+' : ''}${Math.round((v - 1) * 100)}%` })
  }

  const handleSttModelChange = async (id: string) => {
    setSttModel(id)
    await saveSettings({ stt_model: id })
    toast.success('STT model updated')
  }

  // ── Test voice ────────────────────────────────────────────────────────────
  const handleTestVoice = async () => {
    if (isTesting) {
      testAudio?.pause()
      setTestAudio(null)
      setIsTesting(false)
      return
    }
    setIsTesting(true)
    try {
      const res = await api.post('/api/voices/speak',
        { text: 'Voice test. Guppy is ready.', voice: ttsVoice, speed },
        { responseType: 'blob' }
      )
      const url = URL.createObjectURL(res.data)
      const audio = new Audio(url)
      setTestAudio(audio)
      audio.onended = () => { setIsTesting(false); setTestAudio(null); URL.revokeObjectURL(url) }
      audio.onerror = () => { setIsTesting(false); setTestAudio(null); URL.revokeObjectURL(url); toast.error('Playback failed') }
      await audio.play()
    } catch {
      // Fallback: trigger server-side test (plays through server speakers)
      try {
        await api.post('/api/voices/test', { text: 'Voice test. Guppy is ready.' })
        toast.success('Playing on server speakers')
      } catch {
        toast.error('Voice test failed — check backend logs')
      }
      setIsTesting(false)
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
      <div className="p-6 border-b border-border flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Voice Settings</h1>
          <p className="text-muted-foreground mt-1">Configure text-to-speech and speech recognition</p>
        </div>
        <div className="flex items-center gap-2">
          {data?.voice_available
            ? <span className="flex items-center gap-1.5 text-xs text-success"><Wifi className="w-3.5 h-3.5" /> Voice Ready</span>
            : <span className="flex items-center gap-1.5 text-xs text-muted-foreground"><WifiOff className="w-3.5 h-3.5" /> Voice Unavailable</span>
          }
          <button onClick={fetchVoices} className="p-2 rounded-lg hover:bg-muted text-muted-foreground">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <div className="max-w-4xl mx-auto p-6 space-y-8">

          {/* ── TTS ─────────────────────────────────────────────────────── */}
          <section className="space-y-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10 text-primary"><Volume2 className="w-5 h-5" /></div>
              <div>
                <h2 className="text-lg font-medium text-foreground">Text-to-Speech</h2>
                <p className="text-sm text-muted-foreground">Convert AI responses to speech</p>
              </div>
            </div>

            {/* Provider grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {(data?.tts.providers || []).map(p => (
                <button
                  key={p.id}
                  onClick={() => handleProviderChange(p.id)}
                  disabled={!p.available}
                  className={cn(
                    "relative p-4 rounded-xl border-2 transition-all text-left",
                    !p.available && "opacity-40 cursor-not-allowed",
                    ttsProvider === p.id
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50"
                  )}
                >
                  <h3 className="font-medium text-foreground text-sm">{p.name}</h3>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {p.available ? 'Available' : 'Not configured'}
                  </p>
                  {ttsProvider === p.id && (
                    <Check className="absolute bottom-2 right-2 w-4 h-4 text-primary" />
                  )}
                </button>
              ))}
            </div>

            {/* Voice selection */}
            {providerVoices.length > 0 && (
              <div className="p-4 rounded-xl bg-card border border-border space-y-3">
                <label className="text-sm font-medium text-foreground">Voice</label>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {providerVoices.map(v => (
                    <button
                      key={v.id}
                      onClick={() => handleVoiceChange(v.id)}
                      className={cn(
                        "p-3 rounded-lg border transition-all text-left",
                        ttsVoice === v.id
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border hover:border-primary/50 text-foreground"
                      )}
                    >
                      <span className="text-sm font-medium block">{v.name}</span>
                      <span className="text-xs text-muted-foreground">{v.lang}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Speed slider */}
            <div className="p-4 rounded-xl bg-card border border-border">
              <label className="text-sm text-muted-foreground mb-2 block">Speed: {speed.toFixed(1)}×</label>
              <input
                type="range" min="0.5" max="2" step="0.1"
                value={speed}
                onChange={e => setSpeed(parseFloat(e.target.value))}
                onMouseUp={e => handleSpeedChange(parseFloat((e.target as HTMLInputElement).value))}
                onTouchEnd={e => handleSpeedChange(parseFloat((e.target as HTMLInputElement).value))}
                className="w-full accent-primary"
              />
            </div>

            {/* Test button */}
            <button
              onClick={handleTestVoice}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 rounded-lg transition-colors font-medium text-sm",
                isTesting
                  ? "bg-destructive text-destructive-foreground"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              )}
            >
              {isTesting ? <><Square className="w-4 h-4" /> Stop</> : <><Play className="w-4 h-4" /> Test Voice</>}
              {isTesting && <Activity className="w-4 h-4 animate-pulse ml-1" />}
            </button>
          </section>

          <div className="border-t border-border" />

          {/* ── STT ─────────────────────────────────────────────────────── */}
          <section className="space-y-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-success/10 text-success"><Mic className="w-5 h-5" /></div>
              <div>
                <h2 className="text-lg font-medium text-foreground">Speech-to-Text</h2>
                <p className="text-sm text-muted-foreground">
                  Convert voice to text
                  {data?.stt.deepgram_available && <span className="ml-2 text-xs text-primary">· Deepgram available</span>}
                </p>
              </div>
            </div>

            <div className="space-y-2">
              {(data?.stt.models || []).map(m => (
                <button
                  key={m.id}
                  onClick={() => handleSttModelChange(m.id)}
                  className={cn(
                    "w-full flex items-center gap-3 p-4 rounded-xl border-2 transition-all text-left",
                    sttModel === m.id ? "border-success bg-success/5" : "border-border hover:border-success/50"
                  )}
                >
                  <div className={cn(
                    "w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center",
                    sttModel === m.id ? "border-success bg-success" : "border-muted-foreground"
                  )}>
                    {sttModel === m.id && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </div>
                  <span className="font-medium text-foreground text-sm">{m.name}</span>
                </button>
              ))}
            </div>
          </section>

          <div className="border-t border-border" />

          {/* ── Audio Devices ────────────────────────────────────────────── */}
          <section className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-warning/10 text-warning"><Headphones className="w-5 h-5" /></div>
              <div>
                <h2 className="text-lg font-medium text-foreground">Audio Devices</h2>
                <p className="text-sm text-muted-foreground">Microphone and speaker selection</p>
              </div>
              <button onClick={enumerateDevices} className="ml-auto p-1.5 rounded hover:bg-muted text-muted-foreground">
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-card border border-border">
                <label className="text-sm font-medium text-foreground mb-2 block">Microphone</label>
                <select
                  value={inputDevice}
                  onChange={e => setInputDevice(e.target.value)}
                  className="w-full p-2.5 rounded-lg bg-muted border border-border text-foreground text-sm"
                >
                  <option value="">System default</option>
                  {inputDevices.map(d => (
                    <option key={d.deviceId} value={d.deviceId}>{d.label || `Microphone ${d.deviceId.slice(0, 6)}`}</option>
                  ))}
                </select>
              </div>
              <div className="p-4 rounded-xl bg-card border border-border">
                <label className="text-sm font-medium text-foreground mb-2 block">Speakers</label>
                <select
                  value={outputDevice}
                  onChange={e => setOutputDevice(e.target.value)}
                  className="w-full p-2.5 rounded-lg bg-muted border border-border text-foreground text-sm"
                >
                  <option value="">System default</option>
                  {outputDevices.map(d => (
                    <option key={d.deviceId} value={d.deviceId}>{d.label || `Speaker ${d.deviceId.slice(0, 6)}`}</option>
                  ))}
                </select>
              </div>
            </div>
          </section>

        </div>
      </div>
    </div>
  )
}
