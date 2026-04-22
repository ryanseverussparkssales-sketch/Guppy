from __future__ import annotations

import logging
import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path

try:
    import numpy as np
except Exception:
    np = None

try:
    import sounddevice as sd
except Exception:
    sd = None

try:
    import soundfile as sf
except Exception:
    sf = None

try:
    import requests
except Exception:
    requests = None


logger = logging.getLogger(__name__)


def init_stt_backends(owner, voice_cls) -> None:
    try:
        from faster_whisper import WhisperModel

        model_name = owner.cfg.stt_model
        if voice_cls._whisper_singleton is None or voice_cls._whisper_singleton_name != model_name:
            voice_cls._whisper_singleton = WhisperModel(model_name, device="cpu", compute_type="int8")
            voice_cls._whisper_singleton_name = model_name
        owner.whisper_model = voice_cls._whisper_singleton
        owner._whisper_error = ""
    except Exception as exc:
        owner.whisper_model = None
        owner._whisper_error = str(exc)

    try:
        import speech_recognition as sr

        owner._sr_module = sr
    except Exception:
        owner._sr_module = None


def init_tts_backend(owner) -> None:
    try:
        from kokoro import KPipeline

        owner.kokoro_pipeline = KPipeline(lang_code=owner.cfg.lang_code, device="cpu")
        owner._tts_error = ""
    except Exception as exc:
        owner.kokoro_pipeline = None
        owner._tts_error = str(exc)


def clear_record_queue(owner) -> None:
    while not owner._record_q.empty():
        try:
            owner._record_q.get_nowait()
        except queue.Empty:
            break


def record_worker(owner, timeout: float | None = None) -> None:
    if sd is None:
        owner._stop_listening.set()
        owner._listening.clear()
        return

    deadline = time.time() + float(timeout or owner.cfg.max_duration or 30.0)
    silence_cutoff = owner.cfg.silence_cutoff
    speech_threshold = owner.cfg.speech_threshold
    speech_detected = False
    last_speech_time = [time.time()]

    def _callback(indata, _frames, _time_info, _status):
        nonlocal speech_detected
        if not (owner._listening.is_set() and not owner._stop_listening.is_set()):
            return
        owner._record_q.put(indata.copy())
        if np is not None:
            rms = float(np.sqrt(np.mean(indata ** 2)))
            if rms > speech_threshold:
                speech_detected = True
                last_speech_time[0] = time.time()

    try:
        with sd.InputStream(
            samplerate=owner.sample_rate,
            channels=1,
            dtype="float32",
            callback=_callback,
        ):
            while owner._listening.is_set() and not owner._stop_listening.is_set():
                if timeout and time.time() >= deadline:
                    break
                if speech_detected and (time.time() - last_speech_time[0]) >= silence_cutoff:
                    break
                time.sleep(0.05)
    finally:
        owner._stop_listening.set()
        owner._listening.clear()


def transcribe_file(owner, audio_path: str) -> str:
    if owner.whisper_model:
        segments, _info = owner.whisper_model.transcribe(audio_path, beam_size=5)
        return " ".join(segment.text.strip() for segment in segments if segment.text).strip()

    if owner._sr_module:
        recognizer = owner._sr_module.Recognizer()
        with owner._sr_module.AudioFile(audio_path) as src:
            audio = recognizer.record(src)
        return recognizer.recognize_google(audio).strip()

    errors = []
    if owner._whisper_error:
        errors.append(f"Whisper unavailable: {owner._whisper_error}")
    if not owner._sr_module:
        errors.append("SpeechRecognition unavailable")
    raise RuntimeError("; ".join(errors) or "No transcription backend available")


def speak_with_kokoro(owner, text: str, voice: str, speed: float) -> None:
    if owner.kokoro_pipeline is None or np is None or sd is None:
        raise RuntimeError("Kokoro TTS backend unavailable")

    audio_generator = owner.kokoro_pipeline(text, voice=owner._resolve_kokoro_voice(voice), speed=speed)
    audio_chunks = []
    for chunk in audio_generator:
        if owner._stop_speaking.is_set():
            break
        if hasattr(chunk, "audio") and chunk.audio is not None:
            audio_chunks.append(chunk.audio.flatten())

    if not audio_chunks or owner._stop_speaking.is_set():
        return

    audio_data = np.concatenate(audio_chunks)
    sd.play(audio_data, owner.sample_rate)
    while sd.get_stream() and sd.get_stream().active:
        if owner._stop_speaking.is_set():
            sd.stop()
            break
        time.sleep(0.05)


def speak_with_windows_tts(
    owner,
    text: str,
    voice: str | None,
    *,
    hidden_popen_flags,
    preferred_sapi_voice,
    sapi_rate_value,
) -> None:
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "try { if ($env:GUPPY_TTS_VOICE) { $s.SelectVoice($env:GUPPY_TTS_VOICE) } } catch {};"
        "try { if ($env:GUPPY_TTS_RATE) { $s.Rate = [int]$env:GUPPY_TTS_RATE } } catch {};"
        "$s.Speak([Console]::In.ReadToEnd())"
    )
    env = os.environ.copy()
    env["GUPPY_TTS_VOICE"] = preferred_sapi_voice(voice or owner.default_voice)
    env["GUPPY_TTS_RATE"] = str(sapi_rate_value(owner.cfg.tts_rate))
    owner._tts_process = subprocess.Popen(
        ["powershell", "-NoProfile", "-Command", script],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
        **hidden_popen_flags(),
    )
    try:
        if owner._tts_process.stdin:
            owner._tts_process.stdin.write(text)
            owner._tts_process.stdin.close()
        while owner._tts_process.poll() is None:
            if owner._stop_speaking.is_set():
                owner._tts_process.terminate()
                break
            time.sleep(0.05)
    finally:
        owner._tts_process = None


def speak_with_elevenlabs(
    owner,
    text: str,
    voice: str | None,
    *,
    eleven_api_key,
    eleven_model_id,
) -> None:
    if requests is None:
        raise RuntimeError("requests package unavailable for ElevenLabs TTS")
    api_key = eleven_api_key()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")

    voice_id = (voice or "").strip() or os.environ.get("ELEVENLABS_DEFAULT_VOICE_ID", "")
    if not voice_id:
        raise RuntimeError("No ElevenLabs voice id set (configure GUPPY_TTS_VOICE / MERLIN_TTS_VOICE)")

    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        params={"output_format": "pcm_22050"},
        json={
            "text": text,
            "model_id": eleven_model_id(),
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.85,
                "style": 0.2,
                "use_speaker_boost": True,
            },
        },
        timeout=45,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"ElevenLabs TTS failed ({resp.status_code}): {resp.text[:200]}")
    pcm = resp.content
    if not pcm:
        return

    if np is None or sd is None:
        raise RuntimeError("Audio playback dependencies unavailable")
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    sd.play(audio, 22050)
    while sd.get_stream() and sd.get_stream().active:
        if owner._stop_speaking.is_set():
            sd.stop()
            break
        time.sleep(0.05)


def stop_speaking(owner) -> None:
    owner._stop_speaking.set()
    if sd is not None:
        try:
            sd.stop()
        except Exception:
            pass
    if owner._tts_process and owner._tts_process.poll() is None:
        try:
            owner._tts_process.terminate()
        except Exception:
            pass
    with owner.speaking_lock:
        owner._is_speaking = False


def listen_once(owner, timeout: float | None = None) -> dict:
    if sd is None or sf is None or np is None:
        return {"text": "", "error": "Audio dependencies unavailable"}

    while owner._is_speaking:
        time.sleep(0.05)

    if owner._listening.is_set():
        owner._stop_listening.set()
        for _ in range(40):
            if not owner._listening.is_set():
                break
            time.sleep(0.05)

    owner._clear_record_queue()
    owner._stop_listening.clear()
    owner._listening.set()

    try:
        owner._record_worker(timeout=timeout or owner.cfg.max_duration)
        chunks = []
        while not owner._record_q.empty():
            try:
                chunks.append(owner._record_q.get_nowait())
            except queue.Empty:
                break

        if not chunks:
            return {"text": "", "error": "No audio captured"}

        audio_data = np.concatenate(chunks, axis=0)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            sf.write(temp_file.name, audio_data, owner.sample_rate)
            temp_filename = temp_file.name

        try:
            return {"text": owner._transcribe_file(temp_filename), "error": ""}
        except Exception as exc:
            return {"text": "", "error": str(exc)}
        finally:
            try:
                Path(temp_filename).unlink(missing_ok=True)
            except Exception:
                pass
    finally:
        owner._stop_listening.set()
        owner._listening.clear()


def wake_word_listener(owner) -> None:
    cooldown_until = 0.0
    while owner.is_listening_for_wake_word:
        if owner._is_speaking or time.time() < cooldown_until:
            time.sleep(0.1)
            continue

        result = owner.listen_once(timeout=2)
        transcription = (result.get("text") or "").lower().strip()
        if transcription:
            for wake_word in owner.wake_words:
                if wake_word in transcription:
                    cooldown_until = time.time() + 2.5
                    if owner.wake_word_callback:
                        threading.Thread(
                            target=owner.wake_word_callback,
                            args=(transcription,),
                            daemon=True,
                        ).start()
                    break
        time.sleep(0.05)


def wake_word_listener_oww(owner) -> None:
    oww_chunk = 1280
    oww_rate = 16000
    cooldown_until = 0.0
    custom_model = os.environ.get("GUPPY_OWW_MODEL", "").strip()
    try:
        from openwakeword.model import Model as OWWModel

        model_args = [custom_model] if custom_model else []
        oww = OWWModel(wakeword_models=model_args, inference_framework="onnx")
        logger.info("[WAKE] OWW loaded model: %s", custom_model or "all pretrained")
    except Exception as exc:
        logger.warning("[WAKE] OWW init failed: %s. Falling back to transcription.", exc)
        owner._oww_available = False
        owner._wake_word_listener()
        return

    try:
        stream = sd.InputStream(
            samplerate=oww_rate,
            channels=1,
            dtype="int16",
            blocksize=oww_chunk,
        )
        stream.start()
    except Exception:
        owner._oww_available = False
        owner._wake_word_listener()
        return

    owner._oww_available = True
    try:
        while owner.is_listening_for_wake_word:
            if owner._is_speaking or time.time() < cooldown_until:
                time.sleep(0.05)
                continue

            try:
                chunk, _ = stream.read(oww_chunk)
                audio = chunk.flatten()
                predictions = oww.predict(audio)
                for model_name, score in predictions.items():
                    if score > 0.5:
                        cooldown_until = time.time() + 2.5
                        if owner.wake_word_callback:
                            threading.Thread(
                                target=owner.wake_word_callback,
                                args=(model_name,),
                                daemon=True,
                            ).start()
                        break
            except Exception:
                pass
    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass


def start_wake_word_detection(owner, callback_function=None) -> None:
    if owner.is_listening_for_wake_word:
        return

    owner.wake_word_callback = callback_function
    owner.is_listening_for_wake_word = True
    custom_oww_model = os.environ.get("GUPPY_OWW_MODEL", "").strip()
    use_oww = False
    if custom_oww_model and sd is not None:
        try:
            from openwakeword.model import Model  # noqa: F401

            use_oww = True
        except ImportError:
            owner._oww_available = False

    target = owner._wake_word_listener_oww if use_oww else owner._wake_word_listener
    mode = "openwakeword" if use_oww else "transcription"
    logger.info("Wake word detection starting (mode: %s, phrases: %s)", mode, owner.wake_words)
    owner.wake_word_thread = threading.Thread(target=target, daemon=True)
    owner.wake_word_thread.start()
    owner.speak("Wake word detection activated, Master Ryan.")


def stop_wake_word_detection(owner) -> None:
    if not owner.is_listening_for_wake_word:
        return

    owner.is_listening_for_wake_word = False
    owner.stop_listening()
    if owner.wake_word_thread:
        owner.wake_word_thread.join(timeout=3)
    owner.speak("Wake word detection deactivated, sir.")


def hold_to_talk(owner, on_result=None):
    result = owner.listen_once(timeout=10)
    text = result.get("text", "") if isinstance(result, dict) else ""
    if on_result and text:
        on_result(text)
    return text
