"""Multi-agent pipeline executor with SSE streaming.

POST /api/pipeline                    — create & start a pipeline run
GET  /api/pipeline/{id}/stream        — SSE event stream (no auth, run_id is capability token)
GET  /api/pipeline/history?limit=10   — recent runs
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


# ── Template definitions ──────────────────────────────────────────────────────

TEMPLATES: dict[str, dict[str, Any]] = {
    "query_to_code": {
        "label": "Query → Code Review",
        "steps": [
            {
                "role": "Triage",
                "model": "guppy-fast",
                "system": (
                    "You are a fast, concise analyst. Summarize the request in clear bullet points "
                    "and identify the core problem or goal. Be brief."
                ),
            },
            {
                "role": "Code Expert",
                "model": "guppy-code",
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
                "model": "guppy-fast",
                "system": "Summarize the request in 3-5 bullet points. Be brief and precise.",
            },
            {
                "role": "Analyst",
                "model": "guppy",
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
                "model": "guppy",
                "system": "Provide a thorough analysis of the topic with key insights and takeaways.",
            },
            {
                "role": "Teacher",
                "model": "guppy-teach",
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
                    "model": "guppy-fast",
                    "system": "Give a quick, direct perspective. Be concise and confident.",
                },
                {
                    "role": "Deep Dive",
                    "model": "guppy",
                    "system": "Give a thorough, detailed analysis. Explore tradeoffs and nuance.",
                },
            ],
        },
        "synthesis_step": {
            "role": "Synthesis",
            "model": "guppy",
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
    id          TEXT PRIMARY KEY,
    template    TEXT NOT NULL,
    label       TEXT NOT NULL,
    input       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'running',
    error       TEXT,
    started_at  REAL NOT NULL,
    finished_at REAL
);
"""


def _db_path() -> str:
    return str(ensure_user_data_dir() / "pipeline.db")


def _init_db() -> None:
    with sqlite3.connect(_db_path()) as conn:
        conn.executescript(_SCHEMA)


def _create_run(run_id: str, template: str, label: str, user_input: str) -> None:
    with sqlite3.connect(_db_path()) as conn:
        conn.execute(
            "INSERT INTO pipeline_runs (id, template, label, input, status, started_at) VALUES (?,?,?,?,?,?)",
            (run_id, template, label, user_input, "running", time.time()),
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


# ── Ollama inference (synchronous, called via asyncio.to_thread) ──────────────

_OLLAMA_BASE = "http://127.0.0.1:11434"


def _call_ollama(model: str, system: str, user_text: str, timeout: int = 180) -> str:
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
    run_id: str, steps: list[dict], user_input: str
) -> AsyncGenerator[str, None]:
    prev_output = ""
    try:
        for i, step in enumerate(steps):
            yield _sse({"type": "step_start", "step": i, "role": step["role"], "model": step["model"]})

            if step.get("use_prev") and prev_output:
                user_msg = (
                    f"Previous step output:\n{prev_output}\n\n"
                    f"---\n\nOriginal request:\n{user_input}"
                )
            else:
                user_msg = user_input

            response = await asyncio.to_thread(
                _call_ollama, step["model"], step["system"], user_msg
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
    run_id: str, template_def: dict, user_input: str
) -> AsyncGenerator[str, None]:
    agents = template_def["parallel_step"]["agents"]
    synth = template_def["synthesis_step"]

    try:
        # Step 0: parallel agents
        yield _sse({
            "type": "parallel_start",
            "step": 0,
            "agents": [{"role": a["role"], "model": a["model"]} for a in agents],
        })

        tasks = [
            asyncio.to_thread(_call_ollama, a["model"], a["system"], user_input)
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

        # Step 1: synthesis
        yield _sse({"type": "step_start", "step": 1, "role": synth["role"], "model": synth["model"]})

        synthesis_input = (
            f"Perspective 1 — {agents[0]['role']}:\n{agent_outputs[0]}\n\n"
            f"Perspective 2 — {agents[1]['role']}:\n{agent_outputs[1]}\n\n"
            f"Original question: {user_input}"
        )
        synthesis_output = await asyncio.to_thread(
            _call_ollama, synth["model"], synth["system"], synthesis_input
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
        """Create a pipeline run and return its ID for SSE streaming."""
        template_id = str(payload.get("template", "")).strip()
        user_input = str(payload.get("input", "")).strip()

        if not template_id or template_id not in TEMPLATES:
            raise HTTPException(400, f"Unknown template '{template_id}'")
        if not user_input:
            raise HTTPException(400, "input is required")

        template_def = TEMPLATES[template_id]
        run_id = str(uuid.uuid4())
        await asyncio.to_thread(_create_run, run_id, template_id, template_def["label"], user_input)

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

    @router.get("/{run_id}/stream")
    async def stream_pipeline(run_id: str) -> StreamingResponse:
        """SSE stream — no auth required; run_id acts as capability token."""
        with sqlite3.connect(_db_path()) as conn:
            row = conn.execute(
                "SELECT template, input FROM pipeline_runs WHERE id=?", (run_id,)
            ).fetchone()
        if not row:
            raise HTTPException(404, "pipeline run not found")

        template_id, user_input = row
        template_def = TEMPLATES.get(template_id)
        if not template_def:
            raise HTTPException(400, f"Unknown template '{template_id}'")

        is_parallel = "parallel_step" in template_def

        async def event_gen() -> AsyncGenerator[str, None]:
            if is_parallel:
                async for chunk in _run_parallel(run_id, template_def, user_input):
                    yield chunk
            else:
                async for chunk in _run_sequential(
                    run_id, template_def["steps"], user_input
                ):
                    yield chunk

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
