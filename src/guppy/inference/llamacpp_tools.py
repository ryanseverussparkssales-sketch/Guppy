"""Tool definitions and executors for llama.cpp OpenAI-compat function calling.

All tools follow the OpenAI tool spec so they can be passed directly in the
`tools` array of a /v1/chat/completions request.  Each executor maps a tool
name to a callable that accepts **kwargs matching the tool's JSON schema and
returns a plain string result.

Adding a new tool:
1. Add an entry to TOOL_DEFINITIONS (OpenAI format).
2. Add a function to _EXECUTORS keyed on the same name.
"""
from __future__ import annotations

import ast
import json
import logging
import operator as _op
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_datetime",
            "description": "Returns the current date and time in the user's local timezone.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Safely evaluate a mathematical expression. "
                "Supports +, -, *, /, **, (, ) and numeric literals. "
                "Use this for any arithmetic, not Python eval."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression to evaluate, e.g. '17 * 43 + 12'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the web for current information. "
                "Use for recent events, prices, local businesses, news, facts. "
                "Returns a list of titles, URLs, and snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 5, max 10)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Safe calculator
# ---------------------------------------------------------------------------

_ALLOWED_OPS = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
    ast.FloorDiv: _op.floordiv,
    ast.Mod: _op.mod,
    ast.Pow: _op.pow,
    ast.USub: _op.neg,
    ast.UAdd: _op.pos,
}


def _safe_eval(expr: str) -> float:
    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](_eval(node.operand))
        raise ValueError(f"Unsupported expression element: {ast.dump(node)}")

    tree = ast.parse(expr.strip(), mode="eval")
    return _eval(tree.body)


# ---------------------------------------------------------------------------
# Tool executors
# ---------------------------------------------------------------------------

def _exec_get_datetime(**_kwargs: Any) -> str:
    now = datetime.now()
    utc = datetime.now(timezone.utc)
    return (
        f"Current local date/time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}\n"
        f"UTC: {utc.strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )


def _exec_calculator(expression: str = "", **_kwargs: Any) -> str:
    if not expression.strip():
        return "Error: expression is required."
    try:
        result = _safe_eval(expression)
        if result == int(result):
            return str(int(result))
        return str(round(result, 10))
    except ZeroDivisionError:
        return "Error: division by zero."
    except Exception as exc:
        return f"Error evaluating '{expression}': {exc}"


def _exec_web_search(query: str = "", max_results: int = 5, **_kwargs: Any) -> str:
    if not query.strip():
        return "Error: query is required."
    max_results = min(int(max_results or 5), 10)
    try:
        from ddgs import DDGS
        results = list(DDGS().text(query, max_results=max_results))
    except Exception as exc:
        # Fallback: try old package name
        try:
            from duckduckgo_search import DDGS as _DDGS  # type: ignore
            results = list(_DDGS().text(query, max_results=max_results))
        except Exception:
            return f"Web search unavailable: {exc}"

    if not results:
        return f"No results found for: {query!r}"

    lines = [f"Web search results for: {query!r}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("href", r.get("url", ""))
        body = r.get("body", r.get("snippet", ""))
        lines.append(f"{i}. {title}\n   {url}\n   {body}\n")
    return "\n".join(lines)


_EXECUTORS: Dict[str, Any] = {
    "get_datetime": _exec_get_datetime,
    "calculator": _exec_calculator,
    "web_search": _exec_web_search,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def execute_tool(name: str, arguments: str | dict) -> str:
    """Execute a tool by name with JSON arguments. Returns a string result."""
    executor = _EXECUTORS.get(name)
    if executor is None:
        return f"Unknown tool: {name!r}. Available: {list(_EXECUTORS)}"
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as exc:
            return f"Invalid JSON arguments for tool {name!r}: {exc}"
    else:
        args = arguments or {}
    try:
        return executor(**args)
    except Exception as exc:
        logger.error("[TOOLS] %s(%s) raised: %s", name, args, exc)
        return f"Tool {name!r} failed: {exc}"


def tool_names() -> List[str]:
    return list(_EXECUTORS)


# ---------------------------------------------------------------------------
# Synchronous tool-calling loop (non-streaming)
# ---------------------------------------------------------------------------

def call_with_tools(
    *,
    backend: str,
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    max_tool_rounds: int = 6,
    timeout: int = 120,
    num_predict: int = 2048,
) -> str:
    """Run a full tool-calling loop against a llama.cpp OpenAI-compat backend.

    Sends the request, executes any tool calls the model makes, feeds results
    back, and repeats until the model produces a final `stop` response or
    `max_tool_rounds` is reached.  Returns the assistant's final text content.
    """
    import urllib.request as _req

    from src.guppy.inference.local_client import _BACKENDS, _resolve_url

    cfg = _BACKENDS.get(backend, {})
    url = f"{_resolve_url(backend)}{cfg.get('chat_path', '/v1/chat/completions')}"
    active_tools = tools if tools is not None else TOOL_DEFINITIONS
    history = list(messages)

    for round_num in range(max_tool_rounds):
        payload = json.dumps({
            "model": model,
            "messages": history,
            "tools": active_tools,
            "tool_choice": "auto",
            "max_tokens": num_predict,
            "temperature": 0.7,
            "top_p": 0.95,
        }).encode()

        request = _req.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with _req.urlopen(request, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
        except Exception as exc:
            raise RuntimeError(f"llama.cpp backend '{backend}' request failed: {exc}") from exc

        choice = data.get("choices", [{}])[0]
        finish_reason = choice.get("finish_reason", "stop")
        message = choice.get("message", {})
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []

        if finish_reason != "tool_calls" or not tool_calls:
            # Final answer — return whatever text the model produced
            return content.strip() or "(no response)"

        # Add the assistant turn with its tool calls to history
        history.append({
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls,
        })

        # Execute each requested tool and append results
        for tc in tool_calls:
            tc_id = tc.get("id", "")
            fn = tc.get("function", {})
            name = fn.get("name", "")
            arguments = fn.get("arguments", "{}")
            logger.info("[TOOLS] round=%d executing %s(%s)", round_num + 1, name, arguments[:120])
            result = execute_tool(name, arguments)
            logger.info("[TOOLS] %s → %s", name, result[:120])
            history.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result,
            })

    # Exceeded max rounds — ask for a final answer without tools
    logger.warning("[TOOLS] max_tool_rounds=%d reached, forcing final response", max_tool_rounds)
    history.append({
        "role": "user",
        "content": "Please summarize your findings and give your final answer now.",
    })
    payload = json.dumps({
        "model": model,
        "messages": history,
        "max_tokens": num_predict,
        "temperature": 0.7,
    }).encode()
    request = _req.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _req.urlopen(request, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
    except Exception:
        return "(Tool loop exhausted — no final response produced.)"


# ---------------------------------------------------------------------------
# Async streaming tool-calling loop
# ---------------------------------------------------------------------------

async def stream_with_tools(
    *,
    backend: str,
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    max_tool_rounds: int = 6,
    timeout: float = 120.0,
    num_predict: int = 2048,
):
    """Async generator that runs the tool loop and yields str tokens.

    Non-final rounds (tool execution) yield a status token so the UI can show
    progress.  The final model response streams token-by-token via SSE.
    """
    import asyncio
    import httpx

    from src.guppy.inference.local_client import _BACKENDS, _resolve_url

    cfg = _BACKENDS.get(backend, {})
    url = f"{_resolve_url(backend)}{cfg.get('chat_path', '/v1/chat/completions')}"
    active_tools = tools if tools is not None else TOOL_DEFINITIONS
    history = list(messages)

    for round_num in range(max_tool_rounds):
        is_last_allowed = round_num == max_tool_rounds - 1
        payload: Dict[str, Any] = {
            "model": model,
            "messages": history,
            "max_tokens": num_predict,
            "temperature": 0.7,
            "top_p": 0.95,
        }
        if not is_last_allowed:
            payload["tools"] = active_tools
            payload["tool_choice"] = "auto"

        # ── non-streaming call to detect tool_calls finish_reason ──────────
        # We can't know whether the model will call tools until it finishes,
        # so we do a blocking (non-streamed) call for tool rounds, then stream
        # only the final answer.
        non_stream_payload = json.dumps({**payload, "stream": False}).encode()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    url,
                    content=non_stream_payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            raise RuntimeError(f"llama.cpp '{backend}' failed: {exc}") from exc

        choice = data.get("choices", [{}])[0]
        finish_reason = choice.get("finish_reason", "stop")
        message = choice.get("message", {})
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []

        if finish_reason != "tool_calls" or not tool_calls:
            # Stream the final answer token-by-token
            stream_payload = json.dumps({**payload, "stream": True, "tools": []}).encode()
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "POST", url, content=stream_payload,
                        headers={"Content-Type": "application/json"},
                    ) as stream_resp:
                        stream_resp.raise_for_status()
                        async for raw_line in stream_resp.aiter_lines():
                            line = raw_line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                return
                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue
                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            tok = delta.get("content") or ""
                            if tok:
                                yield tok
                return
            except Exception:
                # Fallback: yield the non-streamed content we already have
                if content.strip():
                    yield content.strip()
                return

        # Tool round — emit a status token, then execute tools
        history.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

        for tc in tool_calls:
            tc_id = tc.get("id", "")
            fn = tc.get("function", {})
            name = fn.get("name", "")
            arguments = fn.get("arguments", "{}")
            yield f"\n\n_[using tool: **{name}**…]_\n\n"
            result = await asyncio.to_thread(execute_tool, name, arguments)
            logger.info("[TOOLS/stream] round=%d %s → %s", round_num + 1, name, result[:120])
            history.append({"role": "tool", "tool_call_id": tc_id, "content": result})

    yield "\n\n_(max tool rounds reached)_"
