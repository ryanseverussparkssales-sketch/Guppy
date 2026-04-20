from __future__ import annotations

from src.guppy.voice import voice_support


def test_clean_for_tts_strips_markdown_links_and_urls() -> None:
    cleaned = voice_support.clean_for_tts("# Title\n- **Bold** text | cell |\nhttps://example.com")

    assert "Title" in cleaned
    assert "Bold text" in cleaned
    assert "https://example.com" not in cleaned
    assert "#" not in cleaned


def test_build_backend_status_reports_fallback_to_sapi() -> None:
    status = voice_support.build_backend_status(
        provider="auto",
        eleven_ready=False,
        has_kokoro=False,
        has_whisper=False,
        has_speech_recognition=True,
        oww_available=None,
        wake_enabled=False,
        quiet_mode=False,
        whisper_model_name="large-v3",
        tts_error="",
        stt_error="",
    )

    assert status["tts_backend"] == "sapi"
    assert status["tts_fallback_active"] is True
    assert status["stt_backend"] == "google"
