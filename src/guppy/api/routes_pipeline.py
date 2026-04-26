"""Multi-agent pipeline executor with SSE streaming.

POST /api/pipeline                    — create & start a pipeline run
GET  /api/pipeline/{id}/stream        — SSE event stream (no auth, run_id is capability token)
GET  /api/pipeline/history?limit=10   — recent runs

Templates reference agents by ID (builtin or custom from /api/agents).
Each step's model is resolved at execution time via the agents DB, so
live agent edits affect subsequent pipeline runs without a restart.

agent_overrides in the POST body maps role name → agent_id, overriding
the template default for that step:
    {"agent_overrides": {"Triage": "builtin-fast", "Code Expert": "my-uuid"}}

Supported backends per step:
  - Ollama (guppy, guppy-fast, etc.)
  - llama.cpp via OpenAI-compat (gemma-4-heretic-ara, qwen3-35b-uncensored, assistant-pepe-8b)
  Cloud providers are not yet supported in pipeline steps (async boundary).
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import urllib.request
import uuid
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.guppy.api.server_context import ServerContext
from src.guppy.paths import ensure_user_data_dir
from src.guppy.inference.local_client import (
    _LLAMACPP_MODEL_ROUTE,
    _resolve_url,
    _BACKENDS,
)


# ── Template definitions ──────────────────────────────────────────────────────
# Steps reference agent IDs. Resolved at execution time so live agent edits
# take effect on the next pipeline run without a restart.

TEMPLATES: dict[str, dict[str, Any]] = {
    "query_to_code": {
        "label": "Query → Code Review",
        "steps": [
            {
                "role": "Triage",
                "agent": "builtin-fast",
                "system": (
                    "You are a fast, concise analyst. Summarize the request in clear bullet points "
                    "and identify the core problem or goal. Be brief."
                ),
            },
            {
                "role": "Code Expert",
                "agent": "builtin-code",
                "system": (
                    "You are an expert software engineer. Given the triage analysis below, "
                    "write clean, idiomatic code that solves the problem. Include a brief usage example."
                ),
                "use_prev": True,
            },
        ],
    },
    "triage_to_analysis": {
        "label": "Triage → Deep Analysis",
        "steps": [
            {
                "role": "Triage",
                "agent": "builtin-fast",
                "system": "Summarize the request in 3-5 bullet points. Be brief and precise.",
            },
            {
                "role": "Analyst",
                "agent": "builtin-deep",
                "system": (
                    "You are a thorough analyst. Given the triage below, provide a deep analysis "
                    "exploring tradeoffs, risks, and concrete recommendations."
                ),
                "use_prev": True,
            },
        ],
    },
    "analysis_to_teach": {
        "label": "Analysis → Teaching",
        "steps": [
            {
                "role": "Analyst",
                "agent": "builtin-deep",
                "system": "Provide a thorough analysis of the topic with key insights and takeaways.",
            },
            {
                "role": "Teacher",
                "agent": "builtin-teach",
                "system": (
                    "You are a Socratic teacher. Given the analysis below, guide understanding "
                    "through analogies, targeted questions, and layered examples. Never just restate facts."
                ),
                "use_prev": True,
            },
        ],
    },
    "parallel_perspectives": {
        "label": "Parallel Perspectives",
        "parallel_step": {
            "agents": [
                {
                    "role": "Quick Take",
                    "agent": "builtin-fast",
                    "system": "Give a quick, direct perspective. Be concise and confident.",
                },
                {
                    "role": "Deep Dive",
                    "agent": "builtin-deep",
                    "system": "Give a thorough, detailed analysis. Explore tradeoffs and nuance.",
                },
            ],
        },
        "synthesis_step": {
            "role": "Synthesis",
            "agent": "builtin-deep",
            "system": (
                "Synthesize the following two perspectives into a single balanced, comprehensive answer. "
                "Preserve the best of both and resolve any tensions."
            ),
        },
    },
}


# ── Persistent storage ────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              TEXT PRIMARY KEY,
    template        TEXT NOT NULL,
    label           TEXT NOT NULL,
    input           TEXT NOT NULL,
    agent_overrides TEXT,
    status          TEXT NOT NULL DEFAULT 'running',
    error           TEXT,
    started_at      REAL NOT NULL,
    finished_at     REAL
);
"""

# Migration: add agent_overrides column to existing DBs that predate it.
_MIGRATION_SQL = """
ALTER TABLE pipeline_runs ADD COLUMN agent_overrides TEXT;
"""


def _db_path() -> str:
    return str(ensure_user_data_dir() / "pipeline.db")


def _init_db() -> None:
    with sqlite3.connect(_db_path()) as conn:
        conn.executescript(_SCHEMA)
        try:
            conn.execute(_MIGRATION_SQL)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists


def _create_run(
    run_id: str,
    template: str,
    label: str,
    user_input: str,
    agent_overrides: dict | None,
) -> None:
    with sqlite3.connect(_db_path()) as conn:
        conn.execute(
            "INSERT INTO pipeline_runs (id, template, label, input, agent_overrides, status, started_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                run_id,
                template,
                label,
                user_input,
                json.dumps(agent_overrides) if agent_overrides else None,
                "running",
                time.time(),
            ),
        )


def _finish_run(run_id: str, *, error: str | None = None) -> None:
    status = "error" if error else "done"
    with sqlite3.connect(_db_path()) as conn:
        conn.execute(
            "UPDATE pipeline_runs SET status=?, error=?, finished_at=? WHERE id=?",
            (status, error, time.time(), run_id),
        )


def _get_history(limit: int = 10) -> list[dict]:
    with sqlite3.connect(_db_path()) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?",
            (min(limit, 50),),
        ).fetchall()
    return [dict(r) for r in rows]


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ── Agent resolution ──────────────────────────────────────────────────────────

def _lookup_agent(agent_id: str) -> dict | None:
    """Read one agent from the agents DB. Returns None if not found."""
    try:
        from src.guppy.api.routes_agents import _get_agent
        return _get_agent(agent_id)
    except Exception:
        return None


def _resolve_step(step: dict, agent_overrides: dict | None) -> dict:
    """Resolve the effective model and system for a step.

    Priority: agent_overrides[role] > step['agent'] > step['model'] (legacy fallback).
    System prompt in the template always takes precedence over the agent's default.
    """
    role = step.get("role", "")
    agent_id = (agent_overrides or {}).get(role) or step.get("agent")

    if agent_id:
        agent = _lookup_agent(agent_id)
        if agent:
            return {
                "role": role,
                "model": agent["model"],
                # Template system overrides agent default — lets templates be specific
                # while still benefiting from agent model selection.
                "system": step.get("system") or agent["system_prompt"],
                "use_prev": step.get("use_prev", False),
                "agent_id": agent_id,
                "agent_name": agent["name"],
            }

    # Fallback: legacy "model" field in step (or bare default)
    return {
        "role": role,
        "model": step.get("model", "guppy"),
        "system": step.get("system", ""),
        "use_prev": step.get("use_prev", False),
        "agent_id": None,
        "agent_name": None,
    }


# ── Inference routing ─────────────────────────────────────────────────────────

_OLLAMA_BASE = "http://127.0.0.1:11434"


def _call_step_model(model: str, system: str, user_text: str, timeout: int = 180) -> str:
    """Call the right backend for a model name — Ollama or llama.cpp.

    Routes by checking _LLAMACPP_MODEL_ROUTE first. Falls back to Ollama for
    unknown model names (correct for all guppy-* Ollama models).
    """
    backend = _LLAMACPP_MODEL_ROUTE.get(model)
    if backend:
        cfg = _BACKENDS.get(backend, {})
        url = f"{_resolve_url(backend)}{cfg.get('chat_path', '/v1/chat/completions')}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            "stream": False,
            "max_tokens": 2048,
            "temperature": 0.8,
            "top_p": 0.95,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        choices = data.get("choices", [])
        if not choices:
            return ""
        return str(choices[0].get("message", {}).get("content", "") or "").strip()

    # Default: Ollama
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
    }
    req = urllib.request.Request(
        f"{_OLLAMA_BASE}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return str(data.get("message", {}).get("content", "") or "").strip()


# ── Sequential pipeline runner ────────────────────────────────────────────────

async def _run_sequential(
    run_id: str,
    steps: list[dict],
    user_input: str,
    agent_overrides: dict | None,
) -> AsyncGenerator[str, None]:
    prev_output = ""
    try:
        for i, raw_step in enumerate(steps):
            step = _resolve_step(raw_step, agent_overrides)
            yield _sse({
                "type": "step_start",
                "step": i,
                "role": step["role"],
                "model": step["model"],
                "agent_id": step["agent_id"],
                "agent_name": step["agent_name"],
            })

            if step["use_prev"] and prev_output:
                user_msg = (
                    f"Previous step output:\n{prev_output}\n\n"
                    f"---\n\nOriginal request:\n{user_input}"
                )
            else:
                user_msg = user_input

            response = await asyncio.to_thread(
                _call_step_model, step["model"], step["system"], user_msg
            )
            prev_output = response

            yield _sse({"type": "token", "step": i, "token": response})
            yield _sse({"type": "step_done", "step": i})

        yield _sse({"type": "done"})
        await asyncio.to_thread(_finish_run, run_id)
    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})
        await asyncio.to_thread(_finish_run, run_id, error=str(exc))


# ── Parallel pipeline runner ──────────────────────────────────────────────────

async def _run_parallel(
    run_id: str,
    template_def: dict,
    user_input: str,
    agent_overrides: dict | None,
) -> AsyncGenerator[str, None]:
    raw_agents = template_def["parallel_step"]["agents"]
    raw_synth = template_def["synthesis_step"]

    agents = [_resolve_step(a, agent_overrides) for a in raw_agents]
    synth = _resolve_step(raw_synth, agent_overrides)

    try:
        yield _sse({
            "type": "parallel_start",
            "step": 0,
            "agents": [{"role": a["role"], "model": a["model"], "agent_id": a["agent_id"]} for a in agents],
        })

        tasks = [
            asyncio.to_thread(_call_step_model, a["model"], a["system"], user_input)
            for a in agents
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        agent_outputs: list[str] = []
        for ai, result in enumerate(results):
            output = f"[Error: {result}]" if isinstance(result, Exception) else str(result)
            agent_outputs.append(output)
            yield _sse({"type": "parallel_token", "step": 0, "agent": ai, "token": output})
            yield _sse({"type": "parallel_agent_done", "step": 0, "agent": ai})

        yield _sse({"type": "step_done", "step": 0})

        yield _sse({
            "type": "step_start",
            "step": 1,
            "role": synth["role"],
            "model": synth["model"],
            "agent_id": synth["agent_id"],
        })

        synthesis_input = (
            f"Perspective 1 — {agents[0]['role']}:\n{agent_outputs[0]}\n\n"
            f"Perspective 2 — {agents[1]['role']}:\n{agent_outputs[1]}\n\n"
            f"Original question: {user_input}"
        )
        synthesis_output = await asyncio.to_thread(
            _call_step_model, synth["model"], synth["system"], synthesis_input
        )

        yield _sse({"type": "token", "step": 1, "token": synthesis_output})
        yield _sse({"type": "step_done", "step": 1})
        yield _sse({"type": "done"})
        await asyncio.to_thread(_finish_run, run_id)

    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})
        await asyncio.to_thread(_finish_run, run_id, error=str(exc))


# ── Router ────────────────────────────────────────────────────────────────────

def build_pipeline_router(ctx: ServerContext) -> APIRouter:
    _init_db()
    router = APIRouter(prefix="/api/pipeline")

    @router.post("")
    async def start_pipeline(
        payload: dict,
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> dict:
        """Create a pipeline run and return its ID for SSE streaming.

        Body fields:
          template       — template ID (required)
          input          — user prompt (required)
          agent_overrides — dict mapping role name → agent_id (optional)
                            e.g. {"Triage": "builtin-fast", "Code Expert": "<uuid>"}
        """
        template_id = str(payload.get("template", "")).strip()
        user_input = str(payload.get("input", "")).strip()
        agent_overrides = payload.get("agent_overrides")
        if agent_overrides is not None and not isinstance(agent_overrides, dict):
            agent_overrides = None

        if not template_id or template_id not in TEMPLATES:
            raise HTTPException(400, f"Unknown template '{template_id}'")
        if not user_input:
            raise HTTPException(400, "input is required")

        template_def = TEMPLATES[template_id]
        run_id = str(uuid.uuid4())
        await asyncio.to_thread(
            _create_run, run_id, template_id, template_def["label"], user_input, agent_overrides
        )

        return {
            "pipeline_id": run_id,
            "template": template_id,
            "label": template_def["label"],
        }

    @router.get("/history")
    async def pipeline_history(
        limit: int = 10,
        _user_id: str = Depends(ctx.require_rate_limit),
    ) -> list:
        return await asyncio.to_thread(_get_history, limit)

    @router.get("/templates")
    async def list_templates(_user_id: str = Depends(ctx.require_rate_limit)) -> dict:
        """List available pipeline templates with their step/agent definitions."""
        return {
            tid: {
                "label": tdef["label"],
                "parallel": "parallel_step" in tdef,
                "steps": (
                    [{"role": s["role"], "agent": s.get("agent"), "use_prev": s.get("use_prev", False)}
                     for s in tdef.get("steps", [])]
                    if "steps" in tdef
                    else (
                        [{"role": a["role"], "agent": a.get("agent")} for a in tdef["parallel_step"]["agents"]]
                        + [{"role": tdef["synthesis_step"]["role"], "agent": tdef["synthesis_step"].get("agent")}]
                    )
                ),
            }
            for tid, tdef in TEMPLATES.items()
        }

    @router.get("/{run_id}/stream")
    async def stream_pipeline(run_id: str) -> StreamingResponse:
        """SSE stream — no auth required; run_id acts as capability token."""
        with sqlite3.connect(_db_path()) as conn:
            row = conn.execute(
                "SELECT template, input, agent_overrides FROM pipeline_runs WHERE id=?", (run_id,)
            ).fetchone()
        if not row:
            raise HTTPException(404, "pipeline run not found")

        template_id, user_input, overrides_json = row
        agent_overrides: dict | None = None
        if overrides_json:
            try:
                agent_overrides = json.loads(overrides_json)
            except Exception:
                pass

        template_def = TEMPLATES.get(template_id)
        if not template_def:
            raise HTTPException(400, f"Unknown template '{template_id}'")

        is_parallel = "parallel_step" in template_def

        async def event_gen() -> AsyncGenerator[str, None]:
            if is_parallel:
                async for chunk in _run_parallel(run_id, template_def, user_input, agent_overrides):
                    yield chunk
            else:
                async for chunk in _run_sequential(
                    run_id, template_def["steps"], user_input, agent_overrides
                ):
                    yield chunk

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
