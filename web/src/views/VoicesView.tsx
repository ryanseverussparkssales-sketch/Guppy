/**
 * =============================================================================
 * VOICES VIEW
 * =============================================================================
 * 
 * Configure Text-to-Speech (TTS) and Speech-to-Text (STT) settings.
 * 
 * BACKEND ENDPOINTS:
 * - GET /api/voices - Get available voice providers and configurations
 * - PUT /api/voices/tts - Update TTS settings
 * - PUT /api/voices/stt - Update STT settings
 * - POST /api/voices/test - Test audio playback
 * =============================================================================
 */

import { useState } from 'react'
import { 
  Volume2, 
  Mic, 
  Play, 
  Square,
  Check,
  Waveform,
  Headphones,
  RefreshCw
} from 'lucide-react'
import { cn } from '@/lib/utils'

// Voice provider configurations
interface VoiceProvider {
  id: string
  name: string
  description: string
  isAvailable: boolean
  isPremium?: boolean
}

interface VoiceOption {
  id: string
  name: string
  gender: 'male' | 'female' | 'neutral'
  language: string
  preview?: string
}

// Mock data - replace with API data
const TTS_PROVIDERS: VoiceProvider[] = [
  { id: 'kokoro', name: 'Kokoro', description: 'Fast local TTS', isAvailable: true },
  { id: 'elevenlabs', name: 'ElevenLabs', description: 'Premium quality', isAvailable: true, isPremium: true },
  { id: 'openai', name: 'OpenAI TTS', description: 'Natural voices', isAvailable: true, isPremium: true },
  { id: 'system', name: 'System TTS', description: 'Built-in voices', isAvailable: true },
]

const STT_MODELS = [
  { id: 'whisper-large', name: 'Whisper Large', description: 'Most accurate, slower', size: '2.9GB' },
  { id: 'whisper-medium', name: 'Whisper Medium', description: 'Balanced accuracy', size: '1.5GB' },
  { id: 'whisper-small', name: 'Whisper Small', description: 'Fastest, good accuracy', size: '461MB' },
  { id: 'whisper-tiny', name: 'Whisper Tiny', description: 'Ultra fast, basic', size: '72MB' },
]

const VOICES: VoiceOption[] = [
  { id: 'alloy', name: 'Alloy', gender: 'neutral', language: 'en-US' },
  { id: 'echo', name: 'Echo', gender: 'male', language: 'en-US' },
  { id: 'fable', name: 'Fable', gender: 'female', language: 'en-US' },
  { id: 'onyx', name: 'Onyx', gender: 'male', language: 'en-US' },
  { id: 'nova', name: 'Nova', gender: 'female', language: 'en-US' },
  { id: 'shimmer', name: 'Shimmer', gender: 'female', language: 'en-US' },
]

export default function VoicesView() {
  const [selectedTTSProvider, setSelectedTTSProvider] = useState('kokoro')
  const [selectedVoice, setSelectedVoice] = useState('alloy')
  const [selectedSTTModel, setSelectedSTTModel] = useState('whisper-medium')
  const [isPlaying, setIsPlaying] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  
  // Settings
  const [speed, setSpeed] = useState(1.0)
  const [pitch, setPitch] = useState(1.0)
  const [autoDetectLanguage, setAutoDetectLanguage] = useState(true)

  const handleTestAudio = async () => {
    setIsTesting(true)
    setIsPlaying(true)
    // Simulate audio test - replace with actual API call
    // await api.post('/api/voices/test', { provider: selectedTTSProvider, voice: selectedVoice })
    setTimeout(() => {
      setIsPlaying(false)
      setIsTesting(false)
    }, 3000)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-6 border-b border-border">
        <h1 className="text-2xl font-semibold text-foreground">Voice Settings</h1>
        <p className="text-muted-foreground mt-1">
          Configure text-to-speech and speech recognition
        </p>
      </div>

      <div className="flex-1 overflow-auto">
        <div className="max-w-4xl mx-auto p-6 space-y-8">
          {/* Text-to-Speech Section */}
          <section className="space-y-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10 text-primary">
                <Volume2 className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-lg font-medium text-foreground">Text-to-Speech (TTS)</h2>
                <p className="text-sm text-muted-foreground">Convert AI responses to speech</p>
              </div>
            </div>

            {/* Provider Selection */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {TTS_PROVIDERS.map(provider => (
                <button
                  key={provider.id}
                  onClick={() => setSelectedTTSProvider(provider.id)}
                  className={cn(
                    "relative p-4 rounded-xl border-2 transition-all text-left",
                    selectedTTSProvider === provider.id
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50"
                  )}
                >
                  {provider.isPremium && (
                    <span className="absolute top-2 right-2 px-1.5 py-0.5 text-[10px] bg-warning/10 text-warning rounded">
                      PRO
                    </span>
                  )}
                  <h3 className="font-medium text-foreground">{provider.name}</h3>
                  <p className="text-xs text-muted-foreground mt-1">{provider.description}</p>
                  {selectedTTSProvider === provider.id && (
                    <div className="absolute bottom-2 right-2">
                      <Check className="w-4 h-4 text-primary" />
                    </div>
                  )}
                </button>
              ))}
            </div>

            {/* Voice Selection */}
            <div className="p-4 rounded-xl bg-card border border-border space-y-4">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-foreground">Voice</label>
                <button className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">
                  <RefreshCw className="w-3 h-3" />
                  Refresh voices
                </button>
              </div>
              <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                {VOICES.map(voice => (
                  <button
                    key={voice.id}
                    onClick={() => setSelectedVoice(voice.id)}
                    className={cn(
                      "p-3 rounded-lg border transition-all text-center",
                      selectedVoice === voice.id
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border hover:border-primary/50 text-foreground"
                    )}
                  >
                    <span className="text-sm font-medium">{voice.name}</span>
                    <span className="block text-xs text-muted-foreground capitalize">{voice.gender}</span>
                  </button>
                ))}
              </div>

              {/* Speed & Pitch */}
              <div className="grid grid-cols-2 gap-4 pt-2">
                <div>
                  <label className="text-sm text-muted-foreground mb-2 block">
                    Speed: {speed.toFixed(1)}x
                  </label>
                  <input
                    type="range"
                    min="0.5"
                    max="2"
                    step="0.1"
                    value={speed}
                    onChange={(e) => setSpeed(parseFloat(e.target.value))}
                    className="w-full accent-primary"
                  />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground mb-2 block">
                    Pitch: {pitch.toFixed(1)}
                  </label>
                  <input
                    type="range"
                    min="0.5"
                    max="2"
                    step="0.1"
                    value={pitch}
                    onChange={(e) => setPitch(parseFloat(e.target.value))}
                    className="w-full accent-primary"
                  />
                </div>
              </div>
            </div>

            {/* Test Button */}
            <button
              onClick={handleTestAudio}
              disabled={isTesting}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 rounded-lg transition-colors",
                isPlaying
                  ? "bg-destructive text-destructive-foreground"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              )}
            >
              {isPlaying ? (
                <>
                  <Square className="w-4 h-4" />
                  Stop
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Test Voice
                </>
              )}
              {isTesting && (
                <Waveform className="w-4 h-4 animate-pulse" />
              )}
            </button>
          </section>

          {/* Divider */}
          <div className="border-t border-border" />

          {/* Speech-to-Text Section */}
          <section className="space-y-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-success/10 text-success">
                <Mic className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-lg font-medium text-foreground">Speech-to-Text (STT)</h2>
                <p className="text-sm text-muted-foreground">Convert your voice to text input</p>
              </div>
            </div>

            {/* Model Selection */}
            <div className="space-y-3">
              {STT_MODELS.map(model => (
                <button
                  key={model.id}
                  onClick={() => setSelectedSTTModel(model.id)}
                  className={cn(
                    "w-full flex items-center justify-between p-4 rounded-xl border-2 transition-all",
                    selectedSTTModel === model.id
                      ? "border-success bg-success/5"
                      : "border-border hover:border-success/50"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "w-4 h-4 rounded-full border-2 flex items-center justify-center",
                      selectedSTTModel === model.id
                        ? "border-success bg-success"
                        : "border-muted-foreground"
                    )}>
                      {selectedSTTModel === model.id && (
                        <div className="w-1.5 h-1.5 rounded-full bg-white" />
                      )}
                    </div>
                    <div className="text-left">
                      <h3 className="font-medium text-foreground">{model.name}</h3>
                      <p className="text-sm text-muted-foreground">{model.description}</p>
                    </div>
                  </div>
                  <span className="text-sm text-muted-foreground">{model.size}</span>
                </button>
              ))}
            </div>

            {/* STT Settings */}
            <div className="p-4 rounded-xl bg-card border border-border space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-foreground">Auto-detect Language</h3>
                  <p className="text-xs text-muted-foreground">Automatically detect spoken language</p>
                </div>
                <button
                  onClick={() => setAutoDetectLanguage(!autoDetectLanguage)}
                  className={cn(
                    "relative w-11 h-6 rounded-full transition-colors",
                    autoDetectLanguage ? "bg-success" : "bg-muted"
                  )}
                >
                  <span
                    className={cn(
                      "absolute top-1 w-4 h-4 rounded-full bg-white transition-transform",
                      autoDetectLanguage ? "translate-x-6" : "translate-x-1"
                    )}
                  />
                </button>
              </div>
            </div>
          </section>

          {/* Audio Input/Output Section */}
          <section className="space-y-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-warning/10 text-warning">
                <Headphones className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-lg font-medium text-foreground">Audio Devices</h2>
                <p className="text-sm text-muted-foreground">Configure input and output devices</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-card border border-border">
                <label className="text-sm font-medium text-foreground mb-2 block">
                  Input Device (Microphone)
                </label>
                <select className="w-full p-2.5 rounded-lg bg-muted border border-border text-foreground">
                  <option>Default - System Microphone</option>
                  <option>USB Microphone</option>
                  <option>Headset Microphone</option>
                </select>
              </div>
              <div className="p-4 rounded-xl bg-card border border-border">
                <label className="text-sm font-medium text-foreground mb-2 block">
                  Output Device (Speakers)
                </label>
                <select className="w-full p-2.5 rounded-lg bg-muted border border-border text-foreground">
                  <option>Default - System Speakers</option>
                  <option>Headphones</option>
                  <option>External Speakers</option>
                </select>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
