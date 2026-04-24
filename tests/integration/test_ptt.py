import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.guppy.voice.voice import GuppyVoice, VoiceConfig


def _print_status(label: str, voice: GuppyVoice):
    status = voice.backend_status() if hasattr(voice, "backend_status") else {}
    print(f"[{label}] tts={status.get('tts_backend')} stt={status.get('stt_backend')} wake={status.get('wake_backend')} fallback={status.get('tts_fallback_active')}")
    if status.get("tts_fallback_active"):
        print(f"[{label}] NOTE: SAPI fallback active (more robotic). Install/enable Kokoro for natural voice.")
    if status.get("stt_backend") == "none":
        print(f"[{label}] ERROR: No STT backend available. PTT cannot function.")


def main():
    guppy_cfg = VoiceConfig(tts_voice="bm_lewis", tts_rate="+28%", tts_pitch="+12Hz")
    merlin_cfg = VoiceConfig(tts_voice="bm_lewis", tts_rate="-18%", tts_pitch="-14Hz")

    guppy_voice = GuppyVoice(guppy_cfg)
    merlin_voice = GuppyVoice(merlin_cfg)

    print("=== Voice Backend Status ===")
    _print_status("GUPPY", guppy_voice)
    _print_status("MERLIN", merlin_voice)

    print("\n=== TTS Smoke ===")
    guppy_voice.speak("Voice system online, sir. Diagnostics check complete.")
    time.sleep(1.5)
    merlin_voice.speak("Patience, Apprentice. The diagnostics are complete.")
    time.sleep(1.5)

    interactive = os.environ.get("GUPPY_PTT_INTERACTIVE", "0").strip().lower() in {"1", "true", "yes", "on"}
    if not interactive:
        print("\nPTT interactive test skipped. Set GUPPY_PTT_INTERACTIVE=1 to capture microphone input.")
        return

    print("\n=== PTT Interactive Test ===")
    print("Speak a short sentence after this prompt...")
    result = guppy_voice.listen_once(timeout=8)
    print("PTT result:", result)


if __name__ == "__main__":
    main()
