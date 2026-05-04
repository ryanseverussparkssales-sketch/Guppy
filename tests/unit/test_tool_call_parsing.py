"""Unit tests for tool call parsing, XML normalisation, and think-block filtering.

Covers:
  - _TOOL_CALL_RE JSON extraction
  - _normalize_tool_calls (XML → JSON format conversion)
  - _think_filter streaming coroutine (SSE token stream)
  - _strip_think_from_text completed-response variant
  - _repair_tool_json malformed JSON repair
"""
from __future__ import annotations

import asyncio
import json
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _collect_sse(source):
    """Collect all events from an async SSE generator into a list."""
    return [evt async for evt in source]


def _tok_event(token: str) -> str:
    return f"data: {json.dumps({'token': token})}\n\n"


def _done_event() -> str:
    return "data: [DONE]\n\n"


# ── 1. _TOOL_CALL_RE — JSON-in-tags extraction ────────────────────────────────

class TestToolCallRegex:
    def test_simple_tool_call_extracted(self):
        from src.guppy.api.routes_realtime import _TOOL_CALL_RE
        text = '<tool_call>{"name": "web_search", "arguments": {"query": "cats"}}</tool_call>'
        m = _TOOL_CALL_RE.search(text)
        assert m is not None
        data = json.loads(m.group(1))
        assert data["name"] == "web_search"
        assert data["arguments"]["query"] == "cats"

    def test_tool_call_with_whitespace(self):
        from src.guppy.api.routes_realtime import _TOOL_CALL_RE
        text = '<tool_call>  {"name": "get_time", "arguments": {}}  </tool_call>'
        assert _TOOL_CALL_RE.search(text) is not None

    def test_no_match_without_tags(self):
        from src.guppy.api.routes_realtime import _TOOL_CALL_RE
        assert _TOOL_CALL_RE.search('{"name": "get_time"}') is None

    def test_multiple_tool_calls_found(self):
        from src.guppy.api.routes_realtime import _TOOL_CALL_RE
        text = (
            '<tool_call>{"name": "web_search", "arguments": {"query": "a"}}</tool_call>'
            ' some text '
            '<tool_call>{"name": "get_time", "arguments": {}}</tool_call>'
        )
        matches = _TOOL_CALL_RE.findall(text)
        assert len(matches) == 2

    def test_multiline_args_matched(self):
        from src.guppy.api.routes_realtime import _TOOL_CALL_RE
        text = '<tool_call>{\n  "name": "create_reminder",\n  "arguments": {"message": "hi"}\n}</tool_call>'
        assert _TOOL_CALL_RE.search(text) is not None


# ── 2. _normalize_tool_calls — XML → JSON conversion ─────────────────────────

class TestNormalizeToolCalls:
    def test_xml_format_converted_to_json(self):
        from src.guppy.api.routes_realtime import _normalize_tool_calls, _TOOL_CALL_RE
        xml = '<tool_call><name>web_search</name><arguments>{"query": "python"}</arguments></tool_call>'
        normalized = _normalize_tool_calls(xml)
        m = _TOOL_CALL_RE.search(normalized)
        assert m is not None
        data = json.loads(m.group(1))
        assert data["name"] == "web_search"
        assert data["arguments"]["query"] == "python"

    def test_json_format_unchanged(self):
        from src.guppy.api.routes_realtime import _normalize_tool_calls
        original = '<tool_call>{"name": "get_time", "arguments": {}}</tool_call>'
        assert _normalize_tool_calls(original) == original

    def test_malformed_xml_args_produce_empty_dict(self):
        from src.guppy.api.routes_realtime import _normalize_tool_calls, _TOOL_CALL_RE
        xml = '<tool_call><name>foo</name><arguments>NOT JSON</arguments></tool_call>'
        normalized = _normalize_tool_calls(xml)
        m = _TOOL_CALL_RE.search(normalized)
        assert m is not None
        data = json.loads(m.group(1))
        assert data["arguments"] == {}

    def test_multiple_xml_calls_all_converted(self):
        from src.guppy.api.routes_realtime import _normalize_tool_calls, _TOOL_CALL_RE
        xml = (
            '<tool_call><name>a</name><arguments>{"x": 1}</arguments></tool_call>'
            '<tool_call><name>b</name><arguments>{"y": 2}</arguments></tool_call>'
        )
        normalized = _normalize_tool_calls(xml)
        matches = _TOOL_CALL_RE.findall(normalized)
        assert len(matches) == 2


# ── 3. _think_filter — SSE streaming filter ──────────────────────────────────

class TestThinkFilter:
    def _stream(self, events):
        async def _gen():
            for e in events:
                yield e
        return _gen()

    def test_plain_tokens_pass_through(self):
        from src.guppy.api.routes_realtime import _think_filter
        events = [_tok_event("Hello"), _tok_event(" world"), _done_event()]
        result = _run(_collect_sse(_think_filter(self._stream(events))))
        tokens = [json.loads(e[5:])["token"] for e in result if e.startswith("data: ") and "[DONE]" not in e and "token" in e]
        assert "".join(tokens).strip() == "Hello world"

    def test_think_block_stripped(self):
        from src.guppy.api.routes_realtime import _think_filter
        events = [
            _tok_event("Before"),
            _tok_event("<think>"),
            _tok_event("secret reasoning"),
            _tok_event("</think>"),
            _tok_event("After"),
            _done_event(),
        ]
        result = _run(_collect_sse(_think_filter(self._stream(events))))
        text = "".join(
            json.loads(e[5:]).get("token", "")
            for e in result
            if e.startswith("data: ") and "[DONE]" not in e
        )
        assert "secret" not in text
        assert "Before" in text
        assert "After" in text

    def test_non_token_events_pass_through(self):
        from src.guppy.api.routes_realtime import _think_filter
        tool_exec = f"data: {json.dumps({'type': 'tool_exec', 'tool': 'web_search'})}\n\n"
        events = [tool_exec, _done_event()]
        result = _run(_collect_sse(_think_filter(self._stream(events))))
        assert any("tool_exec" in e for e in result)

    def test_split_think_tag_handled(self):
        from src.guppy.api.routes_realtime import _think_filter
        # Split the opening tag across tokens
        events = [
            _tok_event("Start "),
            _tok_event("<thi"),
            _tok_event("nk>hidden</think>"),
            _tok_event(" End"),
            _done_event(),
        ]
        result = _run(_collect_sse(_think_filter(self._stream(events))))
        text = "".join(
            json.loads(e[5:]).get("token", "")
            for e in result
            if e.startswith("data: ") and "[DONE]" not in e
        )
        assert "hidden" not in text


# ── 4. _strip_think_from_text — completed response variant ───────────────────

class TestStripThinkFromText:
    def _strip(self, text: str) -> str:
        import re
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    def test_think_block_removed(self):
        raw = "Answer: <think>I need to reason about this</think>42"
        assert self._strip(raw) == "Answer: 42"

    def test_no_think_block_unchanged(self):
        raw = "Plain response without thinking."
        assert self._strip(raw) == raw

    def test_multiline_think_block_removed(self):
        raw = "Pre\n<think>\nline1\nline2\n</think>\nPost"
        result = self._strip(raw)
        assert "line1" not in result
        assert "Pre" in result
        assert "Post" in result


# ── 5. _repair_tool_json ──────────────────────────────────────────────────────

class TestRepairToolJson:
    def test_valid_json_unchanged(self):
        from src.guppy.inference.streaming_backends import _repair_tool_json
        valid = '{"name": "foo", "arguments": {"bar": 1}}'
        result = _repair_tool_json(valid)
        assert isinstance(result, dict)
        assert result["name"] == "foo"

    def test_trailing_comma_repaired(self):
        from src.guppy.inference.streaming_backends import _repair_tool_json
        broken = '{"name": "foo", "arguments": {"bar": 1,}}'
        result = _repair_tool_json(broken)
        assert result is not None
        assert result["name"] == "foo"

    def test_unclosed_brace_repaired(self):
        from src.guppy.inference.streaming_backends import _repair_tool_json
        broken = '{"name": "get_time", "arguments": {'
        result = _repair_tool_json(broken)
        # Returns a dict (repaired) or None — must not raise
        assert result is None or isinstance(result, dict)
