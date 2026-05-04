"""Unit tests for the _think_filter SSE stream processor.

Validates buffer-flush ordering, partial-tag detection, and nested-block
suppression.  All tests run without a live model server.
"""
from __future__ import annotations

import asyncio
import json
import pytest


def _make_stream(*events: str):
    """Async generator yielding pre-formatted SSE event strings."""
    async def _gen():
        for e in events:
            yield e
    return _gen()


def _tok(text: str) -> str:
    return f"data: {json.dumps({'token': text})}\n\n"


def _done() -> str:
    return "data: [DONE]\n\n"


async def _collect(source) -> list[str]:
    from src.guppy.api.routes_realtime import _think_filter
    return [e async for e in _think_filter(source)]


# ── 1. Normal pass-through ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_normal_tokens_pass_through():
    events = [_tok("Hello"), _tok(" world"), _done()]
    out = await _collect(_make_stream(*events))
    combined = "".join(
        json.loads(e[6:])["token"]
        for e in out
        if e.startswith("data: {")
    )
    assert "Hello world" in combined


# ── 2. Think block fully suppressed ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_think_block_suppressed():
    events = [
        _tok("Pre"),
        _tok("<think>"),
        _tok("internal reasoning"),
        _tok("</think>"),
        _tok("Post"),
        _done(),
    ]
    out = await _collect(_make_stream(*events))
    tokens = [
        json.loads(e[6:])["token"]
        for e in out
        if e.startswith("data: {") and "token" in json.loads(e[6:])
    ]
    combined = "".join(tokens)
    assert "Pre" in combined
    assert "Post" in combined
    assert "internal reasoning" not in combined
    assert "<think>" not in combined


# ── 3. Buffer flush before [DONE] — the core regression ──────────────────────

@pytest.mark.asyncio
async def test_buffer_flushed_before_done():
    """Final ≤6 chars must arrive BEFORE [DONE], not after.

    This reproduces the bug where "was AURORA" was received as "was A" because
    the 6-char safety buffer was emitted after the [DONE] sentinel.
    """
    # "AURORA" is 6 chars — exactly the SAFE buffer size
    events = [_tok("was "), _tok("AURORA"), _done()]
    out = await _collect(_make_stream(*events))

    # [DONE] must be the LAST event
    assert out[-1] == _done(), "done sentinel must be the final event"

    # Collect all token events in order
    token_events = [e for e in out if e.startswith("data: {") and "token" in json.loads(e[6:])]
    done_index = out.index(_done())
    for te in token_events:
        assert out.index(te) < done_index, (
            f"Token event emitted after [DONE]: {te!r}"
        )

    # Full text should be reconstructed
    combined = "".join(json.loads(e[6:])["token"] for e in token_events)
    assert "AURORA" in combined


# ── 4. Partial <think> tag split across tokens ─────────────────────────────

@pytest.mark.asyncio
async def test_partial_open_tag_split_across_tokens():
    """<think> split as '<thi' + 'nk>' must still be suppressed."""
    events = [
        _tok("Before"),
        _tok("<thi"),
        _tok("nk>hidden content</think>"),
        _tok("After"),
        _done(),
    ]
    out = await _collect(_make_stream(*events))
    tokens = [
        json.loads(e[6:])["token"]
        for e in out
        if e.startswith("data: {") and "token" in json.loads(e[6:])
    ]
    combined = "".join(tokens)
    assert "Before" in combined
    assert "After" in combined
    assert "hidden content" not in combined


# ── 5. Partial </think> tag split across tokens ────────────────────────────

@pytest.mark.asyncio
async def test_partial_close_tag_suppressed():
    """Content inside split </think> close tag should not leak."""
    events = [
        _tok("OK<think>skip this</"),
        _tok("think>"),
        _tok("visible"),
        _done(),
    ]
    out = await _collect(_make_stream(*events))
    tokens = [
        json.loads(e[6:])["token"]
        for e in out
        if e.startswith("data: {") and "token" in json.loads(e[6:])
    ]
    combined = "".join(tokens)
    assert "skip this" not in combined
    assert "visible" in combined


# ── 6. Non-token events pass through unchanged ────────────────────────────

@pytest.mark.asyncio
async def test_non_token_events_pass_through():
    replace_event = "data: {\"replace\": \"full text\"}\n\n"
    heartbeat = ": heartbeat\n\n"
    events = [replace_event, heartbeat, _done()]
    out = await _collect(_make_stream(*events))
    assert replace_event in out
    assert heartbeat in out
    assert _done() in out


# ── 7. Unclosed think block at end-of-stream ─────────────────────────────

@pytest.mark.asyncio
async def test_unclosed_think_block_suppressed():
    """If the model starts a <think> block but never closes it, nothing leaks."""
    events = [
        _tok("Visible"),
        _tok("<think>"),
        _tok("this should not appear"),
        _done(),
    ]
    out = await _collect(_make_stream(*events))
    tokens = [
        json.loads(e[6:])["token"]
        for e in out
        if e.startswith("data: {") and "token" in json.loads(e[6:])
    ]
    combined = "".join(tokens)
    assert "Visible" in combined
    assert "this should not appear" not in combined


# ── 8. Empty stream only yields [DONE] ───────────────────────────────────

@pytest.mark.asyncio
async def test_empty_stream():
    out = await _collect(_make_stream(_done()))
    assert out == [_done()]
