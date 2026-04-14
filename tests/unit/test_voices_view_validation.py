import os

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
