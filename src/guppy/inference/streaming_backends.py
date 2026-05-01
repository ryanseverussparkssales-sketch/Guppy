"""Streaming inference backend helpers.

Provides low-level async generators for each supported cloud and local
inference provider, plus shared JSON-repair and OOM-detection utilities.

Moved from ``src.guppy.api.realtime_inference_support`` to keep that module
readable.  All names remain importable from the original location via
re-export.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re

import httpx
from typing import Any, AsyncGenerator

from src.guppy.inference.local_client import (
    _BACKENDS as _LOCAL_BACKENDS,
    _resolve_url as _local_resolve_url,
)

_log = logging.getLogger(__name__)

# ── OOM detection ─────────────────────────────────────────────────────────────

_OOM_PATTERNS = re.compile(
    r"out of memory|cudaMalloc failed|hipMalloc failed|"
    r"CUDA error.*memory|HIP error.*memory|ggml_cuda_pool_alloc|"
    r"failed to allocate|ROCm.*memory|memory.*exhausted",
    re.IGNORECASE,
)


def _parse_oom_error(text: str, backend: str = "") -> str | None:
    """Return an actionable error string if text contains an OOM indicator, else None."""
    if _OOM_PATTERNS.search(text):
        suffix = f" (backend: {backend})" if backend else ""
        return (
            f"Local model ran out of GPU memory{suffix}. "
            "Restart the model server or reduce the context window. "
            "Use Settings → Backends to switch to a lighter model."
        )
    return None


# ── GBNF grammar constant ─────────────────────────────────────────────────────
# Constrains llamacpp output to a single JSON tool-call object.
# Applied to non-streaming task-executor calls where the entire response should
# be a tool call (or a plain JSON object with a "response" key for prose).
# Callers can pass this to _stream_llamacpp_tokens(grammar=...) or include it
# in a direct httpx payload as "grammar": _TOOL_CALL_GBNF.
_TOOL_CALL_GBNF: str = r"""
root   ::= object
value  ::= object | array | string | number | ("true" | "false" | "null") ws
object ::= "{" ws (pair ("," ws pair)*)? "}" ws
pair   ::= string ":" ws value
array  ::= "[" ws (value ("," ws value)*)? "]" ws
string ::= "\"" (
    [^\x00-\x1f\x22\x5c] |
    "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4})
)* "\"" ws
number ::= ("-"? ([0-9] | [1-9][0-9]*)) ("." [0-9]+)? ([eE][-+]? [0-9]+)? ws
ws     ::= [ \t\n\r]*
""".strip()


def _repair_tool_json(s: str) -> dict | None:
    """Try to parse a JSON string from a <tool_call> block, applying common repairs.

    Models occasionally emit: trailing commas, unclosed braces, or extra whitespace.
    Returns the parsed dict or None if all repair attempts fail.
    """
    # Direct parse
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Strip trailing commas before } or ]
    repaired = re.sub(r",\s*([}\]])", r"\1", s)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass
    # Add missing closing braces
    open_count = repaired.count("{") - repaired.count("}")
    if 0 < open_count <= 3:
        try:
            return json.loads(repaired + "}" * open_count)
        except json.JSONDecodeError:
            pass
    return None


# ── Background tool-outcome persistence ───────────────────────────────────────

def _bg_store_tool_outcome(name: str, args: dict, result: str) -> None:
    """Fire-and-forget: persist successful tool call outcome to semantic memory."""
    import threading
    import hashlib

    def _store() -> None:
        try:
            from src.guppy.memory.semantic import remember_semantic
            args_str = str(sorted((args or {}).items()))[:200]
            key = f"tool_outcome:{name}:{hashlib.md5(args_str.encode()).hexdigest()[:8]}"
            value = f"{name}({args_str[:150]}) → {result[:500]}"
            remember_semantic(key, value, category="tool_outcome")
        except Exception:
            pass

    threading.Thread(target=_store, daemon=True, name="tool-outcome-mem").start()


# ── OpenAI-compatible SSE streaming ───────────────────────────────────────────

async def _stream_openai_compat_tokens(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: float = 120.0,
) -> AsyncGenerator[str, None]:
    """Yield content from any OpenAI-compatible SSE streaming endpoint.

    Used for Mistral (native OpenAI-compat API) and Cohere (via their
    /compatibility endpoint).  No tool-call loop — text streaming only.
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 2048,
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    content = (choices[0].get("delta") or {}).get("content") or ""
                    if content:
                        yield content
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Cloud API returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.ConnectError as exc:
        raise RuntimeError("Cannot reach cloud provider API") from exc


async def _stream_mistral_tokens(
    *,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: float = 120.0,
) -> AsyncGenerator[str, None]:
    """Yield content tokens from Mistral's OpenAI-compatible streaming API."""
    async for token in _stream_openai_compat_tokens(
        base_url="https://api.mistral.ai/v1",
        api_key=api_key,
        model=model,
        messages=messages,
        timeout=timeout,
    ):
        yield token


async def _stream_cohere_tokens(
    *,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout: float = 120.0,
) -> AsyncGenerator[str, None]:
    """Yield content tokens from Cohere's OpenAI-compatible streaming endpoint."""
    async for token in _stream_openai_compat_tokens(
        base_url="https://api.cohere.com/compatibility/v1",
        api_key=api_key,
        model=model,
        messages=messages,
        timeout=timeout,
    ):
        yield token


async def _stream_claude_with_tools(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    messages: list[dict],
    tools: list | None = None,
    tool_runner: Any | None = None,
    max_tokens: int = 4096,
    max_tool_rounds: int = 6,
) -> AsyncGenerator[str, None]:
    """Yield content tokens from Anthropic Claude using the async streaming SDK.

    Handles multi-round tool-call loops: each round's text streams token-by-token
    to the UI; tool execution happens between rounds in a thread pool.
    """
    try:
        import anthropic as _ant
        client = _ant.AsyncAnthropic(api_key=api_key)
    except ImportError:
        raise RuntimeError("anthropic SDK not installed or too old — pip install anthropic>=0.21")

    msgs: list[dict] = list(messages)
    for _round in range(max_tool_rounds + 1):
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": msgs,
        }
        if tools:
            kwargs["tools"] = tools

        tool_use_blocks: list = []
        try:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()

            tool_use_blocks = [b for b in final.content if getattr(b, "type", None) == "tool_use"]

            if not tool_use_blocks or getattr(final, "stop_reason", "") == "end_turn":
                return

        except Exception as exc:
            raise RuntimeError(f"Claude streaming error: {exc}") from exc

        if _round >= max_tool_rounds:
            _log.warning("Claude streaming tool loop hit max_tool_rounds=%d — stopping", max_tool_rounds)
            return

        if not tool_runner:
            return

        msgs.append({"role": "assistant", "content": final.content})
        results = []
        for tu in tool_use_blocks:
            try:
                result = await asyncio.to_thread(
                    tool_runner, tu.name, dict(tu.input) if tu.input else {}
                )
                result_str = str(result)
            except Exception as exc:
                result_str = f"[tool error: {exc}]"
                _log.warning("Claude streaming tool_runner(%r) error: %s", tu.name, exc)
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": result_str})
        msgs.append({"role": "user", "content": results})


async def _stream_llamacpp_tokens(
    *,
    model: str,
    backend: str,
    messages: list[dict],
    timeout: float = 180.0,
    tools: list[dict] | None = None,
    tool_runner: Any | None = None,
    max_tool_rounds: int = 6,
    _loop_history: list[str] | None = None,
    escalate_on_all_tool_errors: bool = False,
    grammar: str | None = None,
) -> AsyncGenerator[str, None]:
    """Yield content tokens from a llama.cpp OpenAI-compatible SSE stream.

    Tokens are yielded eagerly as they arrive so the UI updates in real time.
    Tool-call rounds are handled transparently: the model's pre-tool text (if
    any) streams immediately, tools execute, then the follow-up answer also
    streams token by token.

    Requires ``--jinja`` on llama-server (default since llama.cpp b5000+) for
    structured tool_calls.  On older GGUFs without a Jinja template the model
    may emit text-embedded markup (``<tool_call>…</tool_call>``) which will
    reach the UI as-is; that trade-off is acceptable given the eager-yield
    goal.
    """
    cfg = _LOCAL_BACKENDS.get(backend, {})
    url = f"{_local_resolve_url(backend)}{cfg.get('chat_path', '/v1/chat/completions')}"

    current_messages = list(messages)
    # Loop detection: track (name, args_fingerprint) per round.
    # Two identical consecutive call-sets = model is stuck; break early.
    _loop_history = _loop_history if _loop_history is not None else []

    for _round in range(max_tool_rounds + 1):
        payload: dict = {
            "model": model,
            "messages": current_messages,
            "stream": True,
            "max_tokens": 2048,
            "temperature": 0.8,
            "top_p": 0.95,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if grammar:
            payload["grammar"] = grammar

        full_content = ""
        tool_calls_acc: dict[int, dict] = {}   # delta index → accumulated call
        finish_reason: str | None = None

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for raw_line in response.aiter_lines():
                        line = raw_line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices", [])
                        if not choices:
                            continue
                        choice = choices[0]
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]
                        delta = choice.get("delta", {})

                        # Accumulate and immediately yield text content
                        content = delta.get("content") or ""
                        if content:
                            full_content += content
                            yield content

                        # Accumulate tool_call deltas (OpenAI streaming format)
                        for tc_delta in (delta.get("tool_calls") or []):
                            idx = tc_delta.get("index", 0)
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": tc_delta.get("id", f"call_{_round}_{idx}"),
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            tc = tool_calls_acc[idx]
                            fn_delta = tc_delta.get("function", {})
                            if fn_delta.get("name"):
                                tc["function"]["name"] += fn_delta["name"]
                            if fn_delta.get("arguments"):
                                tc["function"]["arguments"] += fn_delta["arguments"]
                            if tc_delta.get("id"):
                                tc["id"] = tc_delta["id"]

        except httpx.HTTPStatusError as exc:
            body = ""
            try:
                body = exc.response.text
            except Exception:
                pass
            oom_msg = _parse_oom_error(body, backend)
            if oom_msg:
                raise RuntimeError(oom_msg) from exc
            raise RuntimeError(
                f"llama.cpp backend '{backend}' returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.ConnectError as exc:
            raise RuntimeError(
                f"Cannot reach llama.cpp backend '{backend}'. Is the server running?"
            ) from exc

        tool_calls_list = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]

        # ── Structured tool call detected ─────────────────────────────────────
        # Execute tool calls whenever the model emits them, regardless of
        # finish_reason. Some llamacpp builds report "stop" even when tool_calls
        # are present; silently dropping them causes the "I'm downloading it now"
        # hallucination where the model claims to act but no tool was called.
        _is_tool_turn = bool(tool_calls_list)
        if _is_tool_turn and tool_runner:
            if _round >= max_tool_rounds:
                _log.warning(
                    "llama.cpp tool loop hit max_tool_rounds=%d — stopping", max_tool_rounds
                )
                break

            # Append the assistant turn (may carry partial text + tool_calls)
            asst_msg: dict = {
                "role": "assistant",
                "content": full_content if full_content else None,
                "tool_calls": tool_calls_list,
            }
            current_messages.append(asst_msg)

            # Execute each requested tool and collect results
            _round_all_errors = True
            for tc in tool_calls_list:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args_raw = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
                except Exception:
                    args = {}

                try:
                    result = tool_runner(name, args if isinstance(args, dict) else {})
                    result_str = str(result)
                    _round_all_errors = False
                    # Persist outcome to semantic memory (background, non-blocking)
                    if len(result_str) > 50:
                        _bg_store_tool_outcome(name, args if isinstance(args, dict) else {}, result_str)
                except Exception as exc:
                    result_str = f"[tool error: {exc}]"
                    _log.warning("llamacpp tool_runner(%r) error: %s", name, exc)

                # Truncate very large results (screenshots, file dumps) so the
                # model's context window isn't blown out.
                if len(result_str) > 6000:
                    result_str = result_str[:6000] + "\n...[truncated for context]"

                _log.info(
                    "llamacpp tool call round=%d: %s → %d chars", _round, name, len(result_str)
                )
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result_str,
                })

            # Escalation: if every tool call in round 0 failed and no content was
            # streamed yet, raise so the caller can fall through to a stronger model.
            if escalate_on_all_tool_errors and _round == 0 and _round_all_errors and not full_content:
                raise RuntimeError(
                    f"all_tool_errors: all {len(tool_calls_list)} tool call(s) failed on round 0 — escalating"
                )

            # Loop detection: fingerprint this round's calls.
            # If the model issues the exact same set of calls twice in a row it's
            # stuck — break rather than burning all remaining rounds.
            _round_fp = "|".join(
                f"{tc['function']['name']}:{tc['function']['arguments'][:120]}"
                for tc in tool_calls_list
            )
            if _loop_history and _loop_history[-1] == _round_fp:
                _log.warning(
                    "llamacpp tool loop detected: round %d repeated identical calls (%s) — stopping",
                    _round, tool_calls_list[0]["function"]["name"] if tool_calls_list else "?",
                )
                yield "\n\n_(Loop detected: the model repeated the same tool call. Stopping to avoid cycling.)_"
                return
            _loop_history.append(_round_fp)

            continue  # send tool results back to the model

        # ── No tool calls — content already yielded token by token above ────
        return

    # Hit max_tool_rounds — final round's tokens were already yielded eagerly
    _log.warning("llamacpp tool loop exhausted after %d rounds", max_tool_rounds)
