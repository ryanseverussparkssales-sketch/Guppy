import os
import sys
import types

import ui.launcher.views.voices_view as voices_view_module
from ui.launcher.views.voices_view import VoicesView


def test_voice_exists_for_engine_validates_catalog_membership() -> None:
    assert VoicesView._voice_exists_for_engine("EDGE TTS", "en-GB-RyanNeural")
    assert not VoicesView._voice_exists_for_engine("EDGE TTS", "not-a-real-voice")


def test_engine_capability_for_elevenlabs_depends_on_api_key() -> None:
    old = os.environ.get("ELEVENLABS_API_KEY")
    try:
        os.environ.pop("ELEVENLABS_API_KEY", None)
        ok, reason = VoicesView._engine_capability("ELEVENLABS")
        assert not ok
        assert "missing" in reason.lower()

        os.environ["ELEVENLABS_API_KEY"] = "dummy-key"
        ok, reason = VoicesView._engine_capability("ELEVENLABS")
        assert ok
        assert "present" in reason.lower()
    finally:
        if old is None:
            os.environ.pop("ELEVENLABS_API_KEY", None)
        else:
            os.environ["ELEVENLABS_API_KEY"] = old


def test_describe_voice_choice_surfaces_voice_and_engine() -> None:
    assert VoicesView._describe_voice_choice("EDGE TTS", "en-GB-RyanNeural") == "en-GB-RyanNeural on EDGE TTS"


def test_provider_owner_note_routes_cloud_voice_keys_back_to_settings() -> None:
    assert "Settings > Device & Accounts" in VoicesView._provider_owner_note("ELEVENLABS")
    assert VoicesView._provider_owner_note("EDGE TTS") == ""


def test_refresh_voice_evidence_mentions_bindings_and_default_runtime_voice() -> None:
    view = VoicesView()

    view._refresh_voice_evidence()

    assert "Ready now:" in view._voice_evidence_lbl.text()
    assert "Default runtime voice stays" in view._voice_evidence_lbl.text()
    assert "Local engines stay machine-local" in view._voice_evidence_lbl.text()
    assert "Settings > Device & Accounts" in view._engine_status_lbl.toolTip()


def test_preview_voice_restores_backend_env_and_reports_completion(monkeypatch) -> None:
    seen: list[tuple[str, str, str | None, str]] = []

    class FakeVoice:
        def __init__(self, default_voice: str) -> None:
            self.default_voice = default_voice

        def speak(self, text: str, voice: str | None = None) -> None:
            seen.append(
                (
                    os.environ.get("GUPPY_TTS_PROVIDER", ""),
                    os.environ.get("GUPPY_TTS_VOICE", ""),
                    voice,
                    text,
                )
            )

        def stop_tts(self) -> None:
            return

    class ImmediateThread:
        def __init__(self, *, target, daemon: bool = False) -> None:
            self._target = target
            self.daemon = daemon

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(voices_view_module, "GuppyVoice", FakeVoice)
    monkeypatch.setattr(voices_view_module.threading, "Thread", ImmediateThread)
    monkeypatch.setenv("GUPPY_TTS_PROVIDER", "auto")
    monkeypatch.setenv("GUPPY_TTS_VOICE", "baseline-voice")

    view = VoicesView()
    view._engine_capabilities["WINDOWS SAPI"] = {"ok": "1", "reason": "pyttsx3 available"}

    view._preview_voice("WINDOWS SAPI", "Microsoft Zira Desktop")

    assert seen == [
        (
            "sapi",
            "Microsoft Zira Desktop",
            "Microsoft Zira Desktop",
            "Hey, I'm your AI assistant. How can I help you today?",
        )
    ]
    assert os.environ["GUPPY_TTS_PROVIDER"] == "auto"
    assert os.environ["GUPPY_TTS_VOICE"] == "baseline-voice"
    assert view._assign_status.text() == "Preview finished for Microsoft Zira Desktop on WINDOWS SAPI."


def test_cancel_preview_stops_runtime_and_updates_status(monkeypatch) -> None:
    stopped = {"sounddevice": 0, "voice": 0}

    class FakeVoice:
        def stop_tts(self) -> None:
            stopped["voice"] += 1

    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        types.SimpleNamespace(stop=lambda: stopped.__setitem__("sounddevice", stopped["sounddevice"] + 1)),
    )

    view = VoicesView()
    view._guppy_voice = FakeVoice()
    view._assign_status.setText("Previewing Microsoft Zira Desktop with WINDOWS SAPI.")
    initial_generation = view._preview_generation

    view._cancel_preview()

    assert view._preview_generation == initial_generation + 1
    assert stopped == {"sounddevice": 1, "voice": 1}
    assert view._assign_status.text() == "Preview stopped."
