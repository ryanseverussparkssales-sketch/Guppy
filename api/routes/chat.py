"""Chat routes for the cloud backend surface.

These endpoints are intentionally stateless and avoid desktop/runtime imports.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.auth import check_rate_limit, verify_token, verify_turnstile

router = APIRouter()
logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1

_OPENAI_MODEL = "gpt-4o-mini"
_ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"
_MODEL_MAP = {
    "openai": _OPENAI_MODEL,
    "anthropic": _ANTHROPIC_MODEL,
    "mock-local": "mock-local",
}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    schema_version: int = Field(default=_SCHEMA_VERSION)
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=50)
    mode: str | None = None
    persona: str | None = None
    # Provided by the Qt client when GUPPY_TURNSTILE_SECRET is active.
    turnstile_token: str | None = None


class ChatResponse(BaseModel):
    schema_version: int = Field(default=_SCHEMA_VERSION)
    reply: str
    model: str
    latency_ms: int
    finish_reason: Literal["stop", "length", "error"] = "stop"


# ── Backend selection ──────────────────────────────────────────────────────────

def _select_backend() -> str:
    backend = os.environ.get("GUPPY_AI_BACKEND", "auto").strip().lower()
    if backend == "openai":
        return "openai"
    if backend == "anthropic":
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "mock-local"


# ── Persona / mode system prompts ──────────────────────────────────────────────

_PERSONA_BASE = {
    "guppy": (
        "You are Guppy, a friendly and efficient AI assistant. "
        "You are concise, helpful, and practical."
    ),
    "merlin": (
        "You are Merlin, a wise and thoughtful AI assistant with deep analytical "
        "abilities. You reason carefully before answering."
    ),
}

_MODE_SUFFIX = {
    "creative": " Lean toward imaginative, expansive answers.",
    "precise": " Be factual, terse, and avoid speculation.",
    "auto": "",
}

_DEFAULT_PERSONA = "guppy"
_DEFAULT_MODE = "auto"


def _system_prompt(request: ChatRequest) -> str:
    persona = (request.persona or _DEFAULT_PERSONA).strip().lower()
    mode = (request.mode or _DEFAULT_MODE).strip().lower()
    base = _PERSONA_BASE.get(persona, _PERSONA_BASE[_DEFAULT_PERSONA])
    suffix = _MODE_SUFFIX.get(mode, "")
    return base + suffix


def _build_messages(request: ChatRequest) -> list[dict]:
    system = _system_prompt(request)
    msgs: list[dict] = [{"role": "system", "content": system}]
    msgs.extend({"role": m.role, "content": m.content} for m in request.history)
    msgs.append({"role": "user", "content": request.message})
    return msgs


# ── Provider calls ─────────────────────────────────────────────────────────────

async def _call_openai(messages: list[dict]) -> tuple[str, str]:
    """Returns (reply, finish_reason)."""
    import openai  # deferred — not available in all environments

    client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    completion = await client.chat.completions.create(
        model=_OPENAI_MODEL,
        messages=messages,
        max_tokens=2048,
    )
    choice = completion.choices[0]
    return choice.message.content or "", choice.finish_reason or "stop"


async def _call_anthropic(messages: list[dict]) -> tuple[str, str]:
    """Returns (reply, finish_reason)."""
    import anthropic  # deferred — not available in all environments

    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    response = await client.messages.create(
        model=_ANTHROPIC_MODEL,
        max_tokens=2048,
        messages=messages,
    )
    text = response.content[0].text if response.content else ""
    return text, response.stop_reason or "stop"


def _mock_reply(request: ChatRequest) -> str:
    return f"[mock] {request.message.strip()}"


async def _generate_reply(request: ChatRequest) -> tuple[str, str, str]:
    """Returns (reply, model_id, finish_reason)."""
    backend = _select_backend()
    if backend == "openai":
        reply, finish = await _call_openai(_build_messages(request))
        return reply, _OPENAI_MODEL, finish
    if backend == "anthropic":
        reply, finish = await _call_anthropic(_build_messages(request))
        return reply, _ANTHROPIC_MODEL, finish
    return _mock_reply(request), "mock-local", "stop"


# ── Streaming helpers ──────────────────────────────────────────────────────────

async def _stream_openai(messages: list[dict]) -> AsyncIterator[str]:
    import openai

    client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    stream = await client.chat.completions.create(
        model=_OPENAI_MODEL,
        messages=messages,
        stream=True,
        max_tokens=2048,
    )
    async for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta


async def _stream_anthropic(messages: list[dict]) -> AsyncIterator[str]:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    async with client.messages.stream(
        model=_ANTHROPIC_MODEL,
        max_tokens=2048,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            if text:
                yield text


async def _sse_events(payload: ChatRequest, backend: str) -> AsyncIterator[str]:
    model = _MODEL_MAP.get(backend, "mock-local")
    start = time.perf_counter()
    messages = _build_messages(payload)

    if backend == "openai":
        async for delta in _stream_openai(messages):
            yield f"data: {json.dumps({'delta': delta, 'model': model, 'schema_version': _SCHEMA_VERSION})}\n\n"
    elif backend == "anthropic":
        async for delta in _stream_anthropic(messages):
            yield f"data: {json.dumps({'delta': delta, 'model': model, 'schema_version': _SCHEMA_VERSION})}\n\n"
    else:
        for chunk in _mock_reply(payload).split():
            yield f"data: {json.dumps({'delta': chunk + ' ', 'model': model, 'schema_version': _SCHEMA_VERSION})}\n\n"

    latency_ms = int((time.perf_counter() - start) * 1000)
    yield f"data: {json.dumps({'done': True, 'finish_reason': 'stop', 'latency_ms': latency_ms, 'schema_version': _SCHEMA_VERSION})}\n\n"


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("")
async def chat(
    payload: ChatRequest,
    user_id: str = Depends(verify_token),
) -> dict:
    await verify_turnstile(payload.turnstile_token or "")
    check_rate_limit(user_id)

    start = time.perf_counter()
    reply, model, finish_reason = await _generate_reply(payload)
    latency_ms = int((time.perf_counter() - start) * 1000)

    return ChatResponse(
        reply=reply,
        model=model,
        latency_ms=latency_ms,
        finish_reason=finish_reason,  # type: ignore[arg-type]
    ).model_dump()


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    user_id: str = Depends(verify_token),
) -> StreamingResponse:
    await verify_turnstile(payload.turnstile_token or "")
    check_rate_limit(user_id)

    backend = _select_backend()
    return StreamingResponse(
        _sse_events(payload, backend=backend),
        media_type="text/event-stream",
    )
