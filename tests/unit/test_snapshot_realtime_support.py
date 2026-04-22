from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from src.guppy.api import snapshot_realtime_support


class _FakeRouter:
    def _classify_task(self, _message: str, _system_prompt: str) -> str:
        return "simple"


class _FakeWebSocket:
    def __init__(self, inbound: list[dict[str, object]]) -> None:
        self._inbound = list(inbound)
        self.sent: list[dict[str, object]] = []
        self.accepted = False
        self.closed = False

    async def accept(self) -> None:
        self.accepted = True

    async def receive_json(self) -> dict[str, object]:
        if not self._inbound:
            raise snapshot_realtime_support.WebSocketDisconnect()
        return self._inbound.pop(0)

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True


def _chat_owner() -> SimpleNamespace:
    saved_messages: list[tuple[str, str, str, str | None]] = []
    completed: list[dict[str, object]] = []

    async def run_blocking(func, *args, **kwargs):
        timeout_seconds = kwargs.pop("timeout_seconds", None)
        del timeout_seconds
        return func(*args, **kwargs)

    def complete_chat_idempotency_key(key: str, **kwargs) -> None:
        completed.append({"key": key, **kwargs})

    return SimpleNamespace(
        GUPPY_CORE_AVAILABLE=True,
        GUPPY_MEMORY_AVAILABLE=True,
        INFERENCE_ROUTER_AVAILABLE=True,
        CHAT_TIMEOUT_SECONDS=30.0,
        logger=SimpleNamespace(error=lambda *args, **kwargs: None, debug=lambda *args, **kwargs: None),
        memory=SimpleNamespace(
            save_message=lambda session_id, role, content, workspace_name=None: saved_messages.append(
                (session_id, role, content, workspace_name)
            )
        ),
        log_session_event=lambda *args, **kwargs: None,
        build_chat_request_fingerprint=lambda **kwargs: f"fp:{kwargs['message']}",
        register_chat_idempotency_key=lambda key, fingerprint: (True, SimpleNamespace(wait=lambda: None)),
        resolve_chat_idempotency_key=lambda key, fingerprint: None,
        takeover_chat_idempotency_key=lambda key, fingerprint: (True, SimpleNamespace(wait=lambda: None), True),
        complete_chat_idempotency_key=complete_chat_idempotency_key,
        _get_active_instance_context=lambda: ("primary", "user_instance", "guide", "voice"),
        _request_is_morning_brief=lambda request: False,
        _build_morning_brief_response=lambda: "brief",
        _latest_daily_report_path=lambda: None,
        _build_chat_system_prompt=lambda **kwargs: "SYSTEM",
        _request_is_cacheable=lambda request: True,
        get_router=lambda: _FakeRouter(),
        build_response_cache_key=lambda **kwargs: "cache-key",
        get_cached_response=lambda key: "cached reply",
        set_cached_response=lambda key, response: None,
        _run_blocking=run_blocking,
        _call_unified_inference=lambda *args, **kwargs: "live reply",
        _saved_messages=saved_messages,
        _completed=completed,
    )


def test_chat_response_uses_cached_response_and_completes_idempotency() -> None:
    owner = _chat_owner()
    request = SimpleNamespace(
        message="hello",
        session_id="session-1",
        mode="auto",
        persona="guide",
        history=[],
        idempotency_key="idem-1",
        use_claude=True,
    )

    payload = asyncio.run(snapshot_realtime_support.chat_response(owner, request))

    assert payload == {"response": "cached reply", "session_id": "session-1", "cached": True}
    assert owner._completed[0]["key"] == "idem-1"
    assert owner._completed[0]["status_code"] == 200


def test_chat_response_serves_morning_brief_and_persists_messages() -> None:
    owner = _chat_owner()
    owner._request_is_morning_brief = lambda request: True
    request = SimpleNamespace(
        message="good morning",
        session_id="brief-session",
        mode="auto",
        persona="guide",
        history=[],
        idempotency_key="",
        use_claude=True,
    )

    payload = asyncio.run(snapshot_realtime_support.chat_response(owner, request))

    assert payload["brief"] is True
    assert payload["response"] == "brief"
    assert owner._saved_messages == [
        ("brief-session", "user", "good morning", "primary"),
        ("brief-session", "assistant", "brief", "primary"),
    ]


def test_chat_voice_response_transcribes_and_cleans_tempfile(tmp_path: Path) -> None:
    temp_file = tmp_path / "voice.wav"
    temp_file.write_bytes(b"audio")
    saved_messages: list[tuple[str, str, str, str | None]] = []

    class _FakeVoice:
        def transcribe_audio(self, _path: str) -> str:
            return "hello from voice"

    async def run_blocking(func, *args, **kwargs):
        timeout_seconds = kwargs.pop("timeout_seconds", None)
        del timeout_seconds
        return func(*args, **kwargs)

    owner = SimpleNamespace(
        GUPPY_CORE_AVAILABLE=True,
        GUPPY_VOICE_AVAILABLE=True,
        GUPPY_MEMORY_AVAILABLE=True,
        CHAT_TIMEOUT_SECONDS=30.0,
        VOICE_TIMEOUT_SECONDS=10.0,
        voice=SimpleNamespace(GuppyVoice=lambda: _FakeVoice()),
        memory=SimpleNamespace(
            save_message=lambda session_id, role, content, workspace_name=None: saved_messages.append(
                (session_id, role, content, workspace_name)
            )
        ),
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        log_session_event=lambda *args, **kwargs: None,
        _get_active_instance_context=lambda: ("primary", "user_instance", "guide", "voice"),
        _save_voice_upload_tempfile=lambda _file: asyncio.sleep(0, result=str(temp_file)),
        _run_blocking=run_blocking,
        _build_chat_system_prompt=lambda **kwargs: "SYSTEM",
        _call_unified_inference=lambda *args, **kwargs: "voice reply",
    )

    payload = asyncio.run(
        snapshot_realtime_support.chat_voice_response(
            owner,
            file=object(),
            session_id="voice-session",
            use_claude=True,
        )
    )

    assert payload == {
        "transcription": "hello from voice",
        "response": "voice reply",
        "session_id": "voice-session",
    }
    assert saved_messages == [
        ("voice-session", "user", "[Voice] hello from voice", "primary"),
        ("voice-session", "assistant", "voice reply", "primary"),
    ]
    assert not temp_file.exists()


async def _stream_text(text: str):
    for chunk in text.split():
        yield chunk + " "


def test_websocket_response_rejects_missing_token() -> None:
    websocket = _FakeWebSocket([{}])
    owner = SimpleNamespace(
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        log_session_event=lambda *args, **kwargs: None,
    )

    asyncio.run(snapshot_realtime_support.websocket_response(owner, websocket))

    assert websocket.accepted is True
    assert websocket.closed is True
    assert websocket.sent == [{"error": "Authentication required"}]


def test_websocket_response_persists_workspace_scoped_messages() -> None:
    websocket = _FakeWebSocket(
        [
            {"token": "token"},
            {"message": "hello", "session_id": "ws-1", "mode": "auto"},
        ]
    )
    saved_messages: list[tuple[str, str, str, str | None]] = []

    async def run_blocking(func, *args, **kwargs):
        timeout_seconds = kwargs.pop("timeout_seconds", None)
        del timeout_seconds
        return func(*args, **kwargs)

    owner = SimpleNamespace(
        GUPPY_CORE_AVAILABLE=True,
        GUPPY_MEMORY_AVAILABLE=True,
        CHAT_TIMEOUT_SECONDS=30.0,
        SECRET_KEY="secret",
        ALGORITHM="HS256",
        JWTError=RuntimeError,
        jwt=SimpleNamespace(decode=lambda token, secret, algorithms: {"sub": "tester"}),
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        log_session_event=lambda *args, **kwargs: None,
        memory=SimpleNamespace(
            save_message=lambda session_id, role, content, workspace_name=None: saved_messages.append(
                (session_id, role, content, workspace_name)
            )
        ),
        _get_active_instance_context=lambda: ("primary", "user_instance", "guide", "voice"),
        _build_chat_system_prompt=lambda **kwargs: "SYSTEM",
        _run_blocking=run_blocking,
        _call_unified_inference=lambda *args, **kwargs: "streamed reply",
        _stream_chunks=_stream_text,
        _saved_messages=saved_messages,
    )

    asyncio.run(snapshot_realtime_support.websocket_response(owner, websocket))

    assert websocket.sent == [
        {"status": "authenticated"},
        {"chunk": "streamed "},
        {"chunk": "reply "},
        {"done": True},
    ]
    assert saved_messages == [
        ("ws-1", "user", "hello", "primary"),
        ("ws-1", "assistant", "streamed reply", "primary"),
    ]
