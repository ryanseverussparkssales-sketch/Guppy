from __future__ import annotations

from src.guppy.launcher_application.voice_catalog_support import (
    build_bindings_summary_text,
    build_engine_capabilities,
    build_engine_status_summary,
    build_voice_evidence_text,
    engine_capability,
)


def test_engine_capability_for_elevenlabs_depends_on_api_key() -> None:
    ok, reason = engine_capability("ELEVENLABS", env={})
    assert not ok
    assert "missing" in reason.lower()

    ok, reason = engine_capability("ELEVENLABS", env={"ELEVENLABS_API_KEY": "dummy-key"})
    assert ok
    assert "present" in reason.lower()


def test_build_engine_capabilities_and_status_summary_cover_ready_and_unavailable() -> None:
    finder = lambda name: object() if name == "edge_tts" else None
    capabilities = build_engine_capabilities(
        {"EDGE TTS": [], "ELEVENLABS": []},
        env={},
        spec_finder=finder,
    )

    assert capabilities["EDGE TTS"]["ok"] == "1"
    assert capabilities["ELEVENLABS"]["ok"] == "0"
    assert build_engine_status_summary({"EDGE TTS": [], "ELEVENLABS": []}, capabilities) == (
        "ENGINES: EDGE TTS:READY | ELEVENLABS:UNAVAILABLE"
    )


def test_build_bindings_summary_text_reports_default_bindings_and_imports() -> None:
    text = build_bindings_summary_text(
        {
            "bindings": {
                "by_persona": {"guppy": {"engine": "EDGE TTS", "voice_id": "en-GB-RyanNeural"}},
                "by_model": {"guppy": {"engine": "EDGE TTS", "voice_id": "en-GB-RyanNeural"}},
            },
            "imports": [{"engine": "KOKORO", "voice_id": "custom_voice"}],
        },
        default_choice="en-GB-RyanNeural on EDGE TTS",
    )

    assert "Default: en-GB-RyanNeural on EDGE TTS" in text
    assert "Persona bindings: 1" in text
    assert "Model bindings: 1" in text
    assert "Imports: 1" in text


def test_build_voice_evidence_text_mentions_default_and_bindings() -> None:
    text = build_voice_evidence_text(
        active_engine="EDGE TTS",
        active_voice="en-GB-RyanNeural",
        default_choice="en-GB-RyanNeural on EDGE TTS",
        describe_voice_choice=lambda engine, voice_id: f"{voice_id} on {engine}",
        voice_bindings={
            "bindings": {
                "by_persona": {"guppy": {"engine": "EDGE TTS", "voice_id": "en-GB-RyanNeural"}},
                "by_model": {"guppy": {"engine": "EDGE TTS", "voice_id": "en-GB-RyanNeural"}},
            }
        },
        engine_capabilities={"EDGE TTS": {"ok": "1", "reason": "edge-tts installed"}},
    )

    assert "Ready now:" in text
    assert "Default runtime voice stays en-GB-RyanNeural on EDGE TTS." in text
    assert "Live bindings: 1 persona, 1 model." in text
