# Voice and Audio System

This document describes the current behavior implemented in `guppy_voice.py`.
It is intentionally implementation-first and avoids roadmap claims.

## Runtime Components

- Capture: `sounddevice` input stream (`float32`, mono)
- WAV serialization: `soundfile`
- STT primary: `faster-whisper` (CPU, `compute_type="int8"`)
- STT fallback: `speech_recognition` Google recognizer
- TTS providers:
  - `kokoro` (when import/init succeeds)
  - ElevenLabs (when explicitly selected and configured)
  - Windows SAPI PowerShell fallback

## Push-to-Talk Flow

1. `listen_once()` waits until active speech synthesis completes.
2. It records microphone audio with timeout (`VoiceConfig.max_duration`, default 45s).
3. RMS VAD logic marks speech when RMS > `speech_threshold` and then stops early after `silence_cutoff` seconds of silence.
4. Captured audio is written to a temp WAV file.
5. `_transcribe_file()` transcribes with Whisper if available, otherwise Google SpeechRecognition if available.
6. It returns a dict: `{"text": <str>, "error": <str>}`.

`hold_to_talk()` is a convenience wrapper around `listen_once(timeout=10)`.

## Wake Word Modes

Wake mode is started with `start_wake_word_detection()`.

- Default mode: transcription loop (`_wake_word_listener`)
  - Repeated 2-second listens
  - Checks configured phrases in recognized text
  - Higher CPU than model-based wake detection
- Optional mode: openwakeword (`_wake_word_listener_oww`)
  - Used only when `GUPPY_OWW_MODEL` is set and openwakeword imports successfully
  - Falls back to transcription mode on init/stream failure

Configured wake phrases include: `guppy`, `hey guppy`, `butler`, and additional common misrecognitions.

## TTS Selection Logic

Provider preference comes from `GUPPY_TTS_PROVIDER` (`auto` by default).

Resolution order in `speak()`:

1. `elevenlabs` if explicitly requested
2. `sapi` if explicitly requested
3. `kokoro` when available and provider is `auto`
4. ElevenLabs in `auto` mode when API key exists and `requests` is available
5. SAPI fallback

`quiet_mode` disables playback without changing routing state.

## Interruption Behavior

- `stop_speaking()` sets a stop event and stops audio output (`sounddevice.stop()` when available).
- If SAPI is active, the spawned PowerShell process is terminated.
- `stop_tts()` delegates to `stop_speaking()`.
- `stop_listening()` sets the listen stop event.

This supports immediate user interruption while speech is active.

## Key Settings

`VoiceConfig` defaults:

- `stt_model`: `GUPPY_WHISPER_MODEL` or `large-v3`
- `samplerate`: `22050`
- `max_duration`: `45.0`
- `silence_cutoff`: `GUPPY_SILENCE_CUTOFF` or `0.7`
- `speech_threshold`: `GUPPY_SPEECH_THRESHOLD` or `0.01`

TTS-related env vars used by the implementation:

- `GUPPY_TTS_PROVIDER` (`auto`, `kokoro`, `sapi`, `elevenlabs`)
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_MODEL_ID`
- `ELEVENLABS_DEFAULT_VOICE_ID`
- `GUPPY_SAPI_VOICE`
- `GUPPY_OWW_MODEL`

## Diagnostics

Use `backend_status()` to inspect active backend decisions at runtime. It reports:

- selected TTS backend
- selected STT backend
- wake backend state
- quiet mode
- configured Whisper model
- fallback activation flags
- last backend errors (`tts_error`, `stt_error`)

## Known Constraints

- Without `faster-whisper` and `speech_recognition`, transcription is unavailable.
- Without `kokoro` and ElevenLabs configuration, TTS falls back to SAPI.
- openwakeword mode requires a configured model path; otherwise transcription wake mode is used.
- Wake callbacks depend on microphone capture quality and current backend availability.
# Voice & Audio System

## Push-to-Talk (PTT)

### How It Works

1. **Recording Phase**
   - User presses and holds the "HOLD TO TALK" button in Guppy GUI
   - `guppy_voice.py` starts recording via `sounddevice` (16kHz, mono)
   - Audio frames are queued in real-time
   - Orb state changes to "listening"

2. **Transcription Phase**
   - User releases the button (or timeout after 30s)
   - Recorded audio frames are concatenated into a WAV file (temp)
   - Google Speech Recognition API transcribes the audio
   - Result returned as `{"text": str, "error": str|None}`

3. **Response Phase**
   - Text sent to Claude/Ollama for processing
   - AI response spoken aloud via Windows TTS (PowerShell)
   - Chat bubbles updated in real-time

### Microphone Selection

The system auto-detects the default input device:

```python
from sounddevice import default
print(default.device)  # (1, 6) = input device 1, output device 6
```

**For manual override**, edit `guppy_voice.py`:

```python
class VoiceConfig:
    def __init__(self, device=1, samplerate=16000, ...):
        self.device = device  # Use device index from sounddevice.query_devices()
```

### Supported Microphones

Tested compatible:
- **USB PnP Audio Device** (index 1, 28)
- **Xonar SoundCard Microphone** (index 2, 13, 27)
- **NexiGo N930AF Webcam Audio** (index 4, 15, 30, 32)

To list all devices:

```python
import sounddevice as sd
print(sd.query_devices())
```

## Text-to-Speech (TTS)

### Engine

The system uses a **dual-path TTS stack**:

- Primary: Kokoro (when available)
- Fallback: Windows SAPI 5.1 (always available on Windows)

SAPI example:

```powershell
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Speak("Hello, world!")
```

**Advantages:**
- Kokoro path: higher voice quality and better naturalness
- SAPI fallback: no additional TTS service required
- Fast, low-latency synthesis
- Fully offline fallback on Windows

### Voice Configuration

Voices are set in `guppy_voice.py`:

```python
class VoiceConfig:
    def __init__(self, tts_voice="en-GB-RyanNeural", tts_rate="+8%", tts_pitch="+4Hz"):
        self.tts_voice = tts_voice
        self.tts_rate = tts_rate      # Speed: -50% to +50%
        self.tts_pitch = tts_pitch    # Pitch: -10Hz to +10Hz
```

### Available Voices (sample)

| Voice | Locale | Notes |
|-------|--------|-------|
| en-GB-RyanNeural | UK | Approx. Tim Curry (Guppy) |
| en-IE-ConnorNeural | Ireland | Deeper, magical tone (Merlin) |
| en-GB-ThomasNeural | UK | Crisp, authoritative |
| en-US-AriaNeural | US | Neutral, friendly |

**Note:** Exact voices depend on your Windows speech pack. Run `Get-InstalledVoices` in PowerShell to see available options.

## Troubleshooting

### "Could not understand audio"
- **Cause:** Google Speech Recognition failed to parse the audio
- **Fix:** Speak more clearly, reduce background noise, ensure internet connection

### No microphone input
- **Cause:** Device not selected or offline
- **Fix:** Check Windows Sound settings, verify device in `sounddevice.query_devices()`

### TTS not playing
- **Cause:** Audio output disabled or volume muted
- **Fix:** Check Windows volume, test with `python -c "import subprocess; subprocess.Popen(['powershell', '-Command', 'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\"Test\")'])"`

### Latency Issues
- **Issue:** Long delay between speech end and response
- **Cause:** Network latency (Google API), AI model slowness, or TTS generation
- **Fix:** For local inferencing, use Ollama with local persona models (`guppy` / `merlin`).

## Advanced: Using Azure Cognitive Services

To replace Google STT with Azure Speech Services:

1. Set up Azure subscription and Speech resource
2. In `guppy_voice.py`, replace Google API call with Azure SDK:

```python
speech_config = speechsdk.SpeechConfig(
    subscription=os.environ.get("AZURE_SPEECH_KEY"),
    region=os.environ.get("AZURE_SPEECH_REGION")
)
speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config)
result = speech_recognizer.recognize_once()
```

3. Install Azure SDK: `pip install azure-cognitiveservices-speech`

---

**Voice System Status:** ✓ Fully functional (Google/Whisper STT + Kokoro TTS with SAPI fallback)
