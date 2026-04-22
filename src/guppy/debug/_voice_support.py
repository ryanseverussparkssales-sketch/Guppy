from __future__ import annotations


def _collect_voice_objects(parent_window, specs: tuple[tuple[str, str], ...]) -> list[tuple[str, object]]:
    pairs: list[tuple[str, object]] = []
    for label, attr in specs:
        voice = getattr(parent_window, attr, None)
        if voice:
            pairs.append((label, voice))
    return pairs


def voice_objects(parent_window) -> list[tuple[str, object]]:
    return _collect_voice_objects(
        parent_window,
        (("Guppy Voice", "_voice"), ("Guppy Voice", "_g_voice"), ("Merlin Voice", "_m_voice")),
    )


def record_voice_objects(parent_window) -> list[tuple[str, object]]:
    return _collect_voice_objects(
        parent_window,
        (("Guppy", "_voice"), ("Guppy", "_g_voice"), ("Merlin", "_m_voice")),
    )


def transcribe_voice_recording(voice, *, seconds: float = 3.0) -> str:
    import os
    import queue
    import tempfile
    import threading
    import time

    import numpy as np
    import soundfile as sf
    import speech_recognition as sr

    voice._listening.set()
    recorder = threading.Thread(target=voice._record_worker, daemon=True)
    recorder.start()
    time.sleep(seconds)
    voice.stop_listening()

    chunks = []
    while not voice._record_q.empty():
        try:
            chunks.append(voice._record_q.get_nowait())
        except queue.Empty:
            break
        except Exception:
            break
    if not chunks:
        return "No audio captured."

    try:
        audio = np.concatenate(chunks, axis=0)
        temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(temp_fd)
        try:
            sf.write(temp_path, audio, voice.cfg.samplerate)
            recognizer = sr.Recognizer()
            with sr.AudioFile(temp_path) as source:
                audio_data = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio_data)
                return f"Heard: {text}"
            except sr.UnknownValueError:
                return "Could not understand audio."
            except Exception as exc:
                return f"Error: {exc}"
        finally:
            try:
                os.remove(temp_path)
            except Exception:
                pass
    except Exception as exc:
        return f"Processing error: {exc}"
