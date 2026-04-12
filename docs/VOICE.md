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

The system uses **Windows SAPI 5.1** for native speech synthesis:

```powershell
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Speak("Hello, world!")
```

**Advantages:**
- No additional TTS service required
- Fast, low-latency synthesis
- Multiple voices available (depends on Windows)
- Fully offline

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

**Voice System Status:** ✓ Fully functional (Google STT + Windows SAPI 5.1)
