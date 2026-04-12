from __future__ import annotations

import os
import queue
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

try:
    from utils.env_bootstrap import load_env_file
except Exception:
    load_env_file = None

if callable(load_env_file):
    load_env_file()

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


TTS_ENABLED = True


def clean_for_tts(text: str) -> str:
    """Strip markdown and symbol noise before passing text to speech synthesis."""
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"_{1,3}(.*?)_{1,3}", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text, flags=re.DOTALL)
    text = re.sub(r"\|[-: ]+\|[-| :]*", "", text)
    text = text.replace("|", " ")
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"https?://\S+", "", text)
    text = text.replace("\u2013", " - ").replace("\u2014", " - ")  # en-dash, em-dash → spoken pause
    text = re.sub(r"[^\x00-\x7F\u00A0-\u024F]", "", text)
    text = re.sub(r"[#>~^\\`]", "", text)
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


@dataclass(slots=True)
class VoiceConfig:
    tts_voice: str = "en-GB-RyanNeural"
    tts_rate: str = "+8%"
    tts_pitch: str = "+4Hz"
    stt_model: str = os.environ.get("GUPPY_WHISPER_MODEL", "large-v3")
    stt_fallback: str = "google"
    samplerate: int = 22050
    lang_code: str = "en-us"
    noise_reduction: bool = False
    min_silence_threshold: int = 150
    min_duration: float = 0.3
    max_duration: float = 45.0
    # VAD: stop recording after this many seconds of silence once speech has been detected.
    # Lower = snappier cutoff; raise if commands get clipped. Override: GUPPY_SILENCE_CUTOFF env var.
    silence_cutoff: float = float(os.environ.get("GUPPY_SILENCE_CUTOFF", "0.7"))
    # RMS amplitude above which audio counts as "speech". Override: GUPPY_SPEECH_THRESHOLD env var.
    speech_threshold: float = float(os.environ.get("GUPPY_SPEECH_THRESHOLD", "0.01"))


class GuppyVoice:
    _whisper_singleton: "WhisperModel | None" = None  # type: ignore[name-defined]
    _whisper_singleton_name: str = ""

    def __init__(
        self,
        config: VoiceConfig | str | None = None,
        whisper_model: str = os.environ.get("GUPPY_WHISPER_MODEL", "large-v3"),
        sample_rate: int = 22050,
        lang_code: str = "en-us",
        default_voice: str = "bm_lewis",
    ):
        if isinstance(config, VoiceConfig):
            self.cfg = config
        elif isinstance(config, str):
            whisper_model = config
            self.cfg = VoiceConfig(
                stt_model=whisper_model,
                samplerate=sample_rate,
                lang_code=lang_code,
                tts_voice=default_voice,
            )
        else:
            self.cfg = VoiceConfig(
                stt_model=whisper_model,
                samplerate=sample_rate,
                lang_code=lang_code,
                tts_voice=default_voice,
            )

        self.sample_rate = int(self.cfg.samplerate)
        self.default_voice = self.cfg.tts_voice or default_voice
        self.whisper_model = None
        self.kokoro_pipeline = None
        self._whisper_error = ""
        self._tts_error = ""
        self._sr_module = None
        self.quiet_mode = False

        self.wake_words = [
            "guppy",
            "hey guppy",
            "butler",
            "copy",
            "gopi",
            "goppy",
            "gaby",
            "gabby",
            "hey copy",
            "hey gopi",
        ]
        self.is_listening_for_wake_word = False
        self.wake_word_thread = None
        self.wake_word_callback = None
        self._oww_available: bool | None = None  # None = not yet checked

        self._is_speaking = False
        self.speaking_lock = threading.Lock()
        self._listening = threading.Event()
        self._stop_listening = threading.Event()
        self._stop_speaking = threading.Event()
        self._record_q: queue.Queue = queue.Queue()
        self._tts_process = None

        self._init_stt_backends()
        self._init_tts_backend()

    def _init_stt_backends(self) -> None:
        try:
            from faster_whisper import WhisperModel

            model_name = self.cfg.stt_model
            if GuppyVoice._whisper_singleton is None or GuppyVoice._whisper_singleton_name != model_name:
                GuppyVoice._whisper_singleton = WhisperModel(model_name, device="cpu", compute_type="int8")
                GuppyVoice._whisper_singleton_name = model_name
            self.whisper_model = GuppyVoice._whisper_singleton
            self._whisper_error = ""
        except Exception as e:
            self.whisper_model = None
            self._whisper_error = str(e)

        try:
            import speech_recognition as sr

            self._sr_module = sr
        except Exception:
            self._sr_module = None

    def _init_tts_backend(self) -> None:
        try:
            from kokoro import KPipeline

            self.kokoro_pipeline = KPipeline(lang_code=self.cfg.lang_code, device="cpu")
            self._tts_error = ""
        except Exception as e:
            self.kokoro_pipeline = None
            self._tts_error = str(e)

    @staticmethod
    def _tts_provider_pref() -> str:
        return (os.environ.get("GUPPY_TTS_PROVIDER", "auto") or "auto").strip().lower()

    @staticmethod
    def _eleven_model_id() -> str:
        return (os.environ.get("ELEVENLABS_MODEL_ID", "eleven_turbo_v2_5") or "eleven_turbo_v2_5").strip()

    @staticmethod
    def _eleven_api_key() -> str:
        return (os.environ.get("ELEVENLABS_API_KEY", "") or "").strip()

    def backend_status(self) -> dict:
        provider = self._tts_provider_pref()
        eleven_ready = bool(self._eleven_api_key()) and requests is not None
        if provider == "elevenlabs" and eleven_ready:
            tts_backend = "elevenlabs"
        elif provider == "sapi":
            tts_backend = "sapi"
        elif self.kokoro_pipeline is not None:
            tts_backend = "kokoro"
        elif eleven_ready:
            tts_backend = "elevenlabs"
        else:
            tts_backend = "sapi"
        stt_backend = "whisper" if self.whisper_model is not None else ("google" if self._sr_module is not None else "none")
        wake_backend = "openwakeword" if self._oww_available is True else ("transcription" if self.is_listening_for_wake_word else "idle")
        return {
            "tts_backend": tts_backend,
            "tts_provider_pref": provider,
            "stt_backend": stt_backend,
            "wake_backend": wake_backend,
            "wake_enabled": bool(self.is_listening_for_wake_word),
            "quiet_mode": bool(self.quiet_mode),
            "whisper_model": (self.cfg.stt_model or "").strip(),
            "tts_fallback_active": bool(tts_backend == "sapi" and provider not in {"sapi"}),
            "tts_error": (self._tts_error or "").strip(),
            "stt_error": (self._whisper_error or "").strip(),
        }

    def toggle_quiet(self) -> bool:
        self.quiet_mode = not self.quiet_mode
        return self.quiet_mode

    def _resolve_kokoro_voice(self, voice: str | None) -> str:
        requested = (voice or self.default_voice or "").strip()
        voice_l = requested.lower()
        if voice_l.startswith(("af_", "am_", "bf_", "bm_")):
            return requested
        if any(name in voice_l for name in ("ryan", "thomas", "connor", "lewis", "merlin", "guppy")):
            return "bm_lewis"
        return "bm_lewis"

    @staticmethod
    def _sapi_rate_value(rate_text: str | None) -> int:
        text = (rate_text or "").strip()
        if not text:
            return 1
        try:
            if text.endswith("%"):
                num = int(text.replace("%", "").replace("+", "").replace("-", "").strip())
                sign = -1 if text.strip().startswith("-") else 1
                val = int((num / 100.0) * 6) * sign
            else:
                val = int(text)
        except Exception:
            val = 1
        return max(-6, min(6, val))

    @staticmethod
    def _preferred_sapi_voice(requested: str | None) -> str:
        req = (requested or "").strip()
        req_low = req.lower()
        if req and ("neural" not in req_low) and ("bm_" not in req_low) and ("af_" not in req_low):
            return req
        return os.environ.get("GUPPY_SAPI_VOICE", "Microsoft Zira Desktop").strip() or "Microsoft Zira Desktop"

    @staticmethod
    def _kokoro_speed_value(rate_text: str | None, base_speed: float = 1.0) -> float:
        text = (rate_text or "").strip()
        speed = float(base_speed or 1.0)
        if not text:
            return max(0.7, min(1.45, speed))
        try:
            if text.endswith("%"):
                num = float(text.replace("%", "").replace("+", "").replace("-", "").strip())
                sign = -1.0 if text.startswith("-") else 1.0
                speed *= 1.0 + ((num / 100.0) * sign)
            else:
                speed *= float(text)
        except Exception:
            pass
        return max(0.7, min(1.45, speed))

    def _clear_record_queue(self) -> None:
        while not self._record_q.empty():
            try:
                self._record_q.get_nowait()
            except queue.Empty:
                break

    def _record_worker(self, timeout: float | None = None) -> None:
        if sd is None:
            self._stop_listening.set()
            self._listening.clear()
            return

        deadline = time.time() + float(timeout or self.cfg.max_duration or 30.0)
        silence_cutoff   = self.cfg.silence_cutoff
        speech_threshold = self.cfg.speech_threshold

        # VAD state — written from the sounddevice callback thread, read from the poll loop.
        # Benign race: worst case we cut off 50 ms early/late, which is acceptable.
        speech_detected  = False
        last_speech_time = [time.time()]   # list so the closure can rebind

        def _callback(indata, _frames, _time_info, _status):
            nonlocal speech_detected
            if not (self._listening.is_set() and not self._stop_listening.is_set()):
                return
            self._record_q.put(indata.copy())
            # Lightweight RMS VAD — numpy is always available when sounddevice is
            if np is not None:
                rms = float(np.sqrt(np.mean(indata ** 2)))
                if rms > speech_threshold:
                    speech_detected = True
                    last_speech_time[0] = time.time()

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=_callback,
            ):
                while self._listening.is_set() and not self._stop_listening.is_set():
                    if timeout and time.time() >= deadline:
                        break
                    # Early cutoff: speech started then went quiet for silence_cutoff seconds
                    if speech_detected and (time.time() - last_speech_time[0]) >= silence_cutoff:
                        break
                    time.sleep(0.05)
        finally:
            self._stop_listening.set()
            self._listening.clear()

    def _transcribe_file(self, audio_path: str) -> str:
        if self.whisper_model:
            segments, _info = self.whisper_model.transcribe(audio_path, beam_size=5)
            return " ".join(segment.text.strip() for segment in segments if segment.text).strip()

        if self._sr_module:
            recognizer = self._sr_module.Recognizer()
            with self._sr_module.AudioFile(audio_path) as src:
                audio = recognizer.record(src)
            return recognizer.recognize_google(audio).strip()

        errors = []
        if self._whisper_error:
            errors.append(f"Whisper unavailable: {self._whisper_error}")
        if not self._sr_module:
            errors.append("SpeechRecognition unavailable")
        raise RuntimeError("; ".join(errors) or "No transcription backend available")

    def _speak_with_kokoro(self, text: str, voice: str, speed: float) -> None:
        if self.kokoro_pipeline is None or np is None or sd is None:
            raise RuntimeError("Kokoro TTS backend unavailable")

        audio_generator = self.kokoro_pipeline(text, voice=self._resolve_kokoro_voice(voice), speed=speed)
        audio_chunks = []
        for chunk in audio_generator:
            if self._stop_speaking.is_set():
                break
            if hasattr(chunk, "audio") and chunk.audio is not None:
                audio_chunks.append(chunk.audio.flatten())

        if not audio_chunks or self._stop_speaking.is_set():
            return

        audio_data = np.concatenate(audio_chunks)
        sd.play(audio_data, self.sample_rate)
        while sd.get_stream() and sd.get_stream().active:
            if self._stop_speaking.is_set():
                sd.stop()
                break
            time.sleep(0.05)

    def _speak_with_windows_tts(self, text: str, voice: str | None) -> None:
        script = (
            "Add-Type -AssemblyName System.Speech;"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            "try { if ($env:GUPPY_TTS_VOICE) { $s.SelectVoice($env:GUPPY_TTS_VOICE) } } catch {};"
            "try { if ($env:GUPPY_TTS_RATE) { $s.Rate = [int]$env:GUPPY_TTS_RATE } } catch {};"
            "$s.Speak([Console]::In.ReadToEnd())"
        )
        env = os.environ.copy()
        env["GUPPY_TTS_VOICE"] = self._preferred_sapi_voice(voice or self.default_voice)
        env["GUPPY_TTS_RATE"] = str(self._sapi_rate_value(self.cfg.tts_rate))
        self._tts_process = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
        )
        try:
            if self._tts_process.stdin:
                self._tts_process.stdin.write(text)
                self._tts_process.stdin.close()
            while self._tts_process.poll() is None:
                if self._stop_speaking.is_set():
                    self._tts_process.terminate()
                    break
                time.sleep(0.05)
        finally:
            self._tts_process = None

    def _speak_with_elevenlabs(self, text: str, voice: str | None) -> None:
        if requests is None:
            raise RuntimeError("requests package unavailable for ElevenLabs TTS")
        api_key = self._eleven_api_key()
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not configured")

        # Default voice IDs are placeholders; override via env for production use.
        voice_id = (voice or "").strip() or os.environ.get("ELEVENLABS_DEFAULT_VOICE_ID", "")
        if not voice_id:
            raise RuntimeError("No ElevenLabs voice id set (configure GUPPY_TTS_VOICE / MERLIN_TTS_VOICE)")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self._eleven_model_id(),
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.85,
                "style": 0.2,
                "use_speaker_boost": True,
            },
        }
        params = {"output_format": "pcm_22050"}

        resp = requests.post(url, headers=headers, params=params, json=payload, timeout=45)
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
            if self._stop_speaking.is_set():
                sd.stop()
                break
            time.sleep(0.05)

    def speak(self, text, voice=None, speed=1.0):
        if not TTS_ENABLED or self.quiet_mode:
            return

        text = clean_for_tts(str(text or ""))
        if not text:
            return

        self._stop_speaking.clear()
        with self.speaking_lock:
            self._is_speaking = True

        try:
            provider = self._tts_provider_pref()
            if provider == "elevenlabs":
                self._speak_with_elevenlabs(text, voice or self.default_voice)
            elif provider == "sapi":
                self._speak_with_windows_tts(text, voice or self.default_voice)
            elif self.kokoro_pipeline is not None:
                kokoro_speed = self._kokoro_speed_value(self.cfg.tts_rate, speed)
                self._speak_with_kokoro(text, voice or self.default_voice, kokoro_speed)
            elif provider == "auto" and self._eleven_api_key() and requests is not None:
                self._speak_with_elevenlabs(text, voice or self.default_voice)
            else:
                self._speak_with_windows_tts(text, voice or self.default_voice)

            if not self._stop_speaking.is_set():
                time.sleep(0.2)
        except Exception as e:
            self._tts_error = str(e)
        finally:
            with self.speaking_lock:
                self._is_speaking = False
            self._stop_speaking.clear()

    def stop_speaking(self):
        self._stop_speaking.set()
        if sd is not None:
            try:
                sd.stop()
            except Exception:
                pass
        if self._tts_process and self._tts_process.poll() is None:
            try:
                self._tts_process.terminate()
            except Exception:
                pass
        with self.speaking_lock:
            self._is_speaking = False

    def stop_tts(self):
        self.stop_speaking()

    def stop_listening(self):
        self._stop_listening.set()

    def listen_once(self, timeout: float | None = None) -> dict:
        if sd is None or sf is None or np is None:
            return {"text": "", "error": "Audio dependencies unavailable"}

        while self._is_speaking:
            time.sleep(0.05)

        # If another recording is in progress (e.g. wake word loop), abort it and
        # wait for the stream to close before opening a new one.  Without this,
        # two concurrent _record_worker calls race on the same InputStream and
        # shared events — the loser gets an empty queue → "No audio captured".
        if self._listening.is_set():
            self._stop_listening.set()
            for _ in range(40):   # up to 2 s
                if not self._listening.is_set():
                    break
                time.sleep(0.05)

        self._clear_record_queue()
        self._stop_listening.clear()
        self._listening.set()

        try:
            self._record_worker(timeout=timeout or self.cfg.max_duration)
            chunks = []
            while not self._record_q.empty():
                try:
                    chunks.append(self._record_q.get_nowait())
                except queue.Empty:
                    break

            if not chunks:
                return {"text": "", "error": "No audio captured"}

            audio_data = np.concatenate(chunks, axis=0)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                sf.write(temp_file.name, audio_data, self.sample_rate)
                temp_filename = temp_file.name

            try:
                text = self._transcribe_file(temp_filename)
                return {"text": text, "error": ""}
            except Exception as e:
                return {"text": "", "error": str(e)}
            finally:
                try:
                    Path(temp_filename).unlink(missing_ok=True)
                except Exception:
                    pass
        finally:
            self._stop_listening.set()
            self._listening.clear()

    def listen(self, duration=5, silence_threshold=0.01):
        del silence_threshold
        result = self.listen_once(timeout=duration)
        return result.get("text", "") if isinstance(result, dict) else ""

    def _wake_word_listener(self):
        """Fallback: transcription-based wake word loop. Works without openwakeword.
        Uses ~30% CPU (full STT per 2-second chunk). Handles custom wake words."""
        cooldown_until = 0.0
        while self.is_listening_for_wake_word:
            if self._is_speaking or time.time() < cooldown_until:
                time.sleep(0.1)
                continue

            result = self.listen_once(timeout=2)
            transcription = (result.get("text") or "").lower().strip()
            if transcription:
                for wake_word in self.wake_words:
                    if wake_word in transcription:
                        cooldown_until = time.time() + 2.5
                        if self.wake_word_callback:
                            threading.Thread(
                                target=self.wake_word_callback,
                                args=(transcription,),
                                daemon=True,
                            ).start()
                        break
            time.sleep(0.05)

    def _wake_word_listener_oww(self):
        """openwakeword-based listener. <1% CPU, 80ms latency.
        Only called when GUPPY_OWW_MODEL env var points to a custom model file.
        Falls back to transcription loop if import or stream fails."""
        _OWW_CHUNK = 1280   # 80 ms at 16 kHz (openwakeword requirement)
        _OWW_RATE  = 16000
        cooldown_until = 0.0

        custom_model = os.environ.get("GUPPY_OWW_MODEL", "").strip()
        try:
            from openwakeword.model import Model as _OWW
            model_args = [custom_model] if custom_model else []
            oww = _OWW(wakeword_models=model_args, inference_framework="onnx")
            logger.info(f"[WAKE] OWW loaded model: {custom_model or 'all pretrained'}")
        except Exception as e:
            logger.warning(f"[WAKE] OWW init failed: {e}. Falling back to transcription.")
            self._oww_available = False
            self._wake_word_listener()
            return

        try:
            stream = sd.InputStream(
                samplerate=_OWW_RATE,
                channels=1,
                dtype="int16",
                blocksize=_OWW_CHUNK,
            )
            stream.start()
        except Exception:
            self._oww_available = False
            self._wake_word_listener()
            return

        self._oww_available = True
        try:
            while self.is_listening_for_wake_word:
                if self._is_speaking or time.time() < cooldown_until:
                    time.sleep(0.05)
                    continue

                try:
                    chunk, _ = stream.read(_OWW_CHUNK)
                    audio = chunk.flatten()
                    predictions = oww.predict(audio)
                    for _model, score in predictions.items():
                        if score > 0.5:
                            cooldown_until = time.time() + 2.5
                            if self.wake_word_callback:
                                threading.Thread(
                                    target=self.wake_word_callback,
                                    args=(_model,),
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

    def start_wake_word_detection(self, callback_function=None):
        if self.is_listening_for_wake_word:
            return

        self.wake_word_callback = callback_function
        self.is_listening_for_wake_word = True

        # Use openwakeword ONLY if a custom model path is explicitly configured.
        # Without a custom "hey_guppy" model, the pretrained models (alexa, hey_jarvis, etc.)
        # won't respond to "hey guppy". The transcription-based fallback catches custom
        # phrases reliably on Ryan's hardware. Set GUPPY_OWW_MODEL=<path> to opt into OWW
        # once a custom model is trained.
        custom_oww_model = os.environ.get("GUPPY_OWW_MODEL", "").strip()
        use_oww = False
        if custom_oww_model and sd is not None:
            try:
                from openwakeword.model import Model  # noqa: F401
                use_oww = True
            except ImportError:
                self._oww_available = False

        target = self._wake_word_listener_oww if use_oww else self._wake_word_listener
        mode = "openwakeword" if use_oww else "transcription"
        logger.info(f"Wake word detection starting (mode: {mode}, phrases: {self.wake_words})")
        self.wake_word_thread = threading.Thread(target=target, daemon=True)
        self.wake_word_thread.start()
        self.speak("Wake word detection activated, Master Ryan.")

    def stop_wake_word_detection(self):
        if not self.is_listening_for_wake_word:
            return

        self.is_listening_for_wake_word = False
        self.stop_listening()
        if self.wake_word_thread:
            self.wake_word_thread.join(timeout=3)
        self.speak("Wake word detection deactivated, sir.")

    def hold_to_talk(self, on_result=None):
        result = self.listen_once(timeout=10)
        text = result.get("text", "") if isinstance(result, dict) else ""
        if on_result and text:
            on_result(text)
        return text
