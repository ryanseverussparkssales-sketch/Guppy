from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from src.guppy.api._server_fragment_models import RepairRequest
from src.guppy.api.server_context import ServerContext


def build_ops_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter()
    owner = ctx.owner
    repair_dependency = ctx.require_repair_token

    @router.get("/logs/recent")
    async def get_recent_logs(
        limit: int = 100,
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        lim = max(1, min(int(limit), 300))
        runtime_dir = ctx.paths.runtime_dir
        return {
            "session_events": ctx.tail_session_events(limit=lim),
            "agent_performance": ctx.read_jsonl_tail(
                runtime_dir / "agent_performance.jsonl", limit=lim
            ),
            "integration_events": ctx.read_jsonl_tail(
                runtime_dir / "integration_events.jsonl", limit=lim
            ),
        }

    @router.get("/telemetry/query")
    async def telemetry_query(
        stream: Optional[str] = None,
        event: Optional[str] = None,
        level: Optional[str] = None,
        since_minutes: int = 1440,
        limit: int = 200,
        backend: str = "auto",
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        lim = max(1, min(int(limit), 1000))
        since = max(0, int(since_minutes))
        stream_key = (stream or "").strip() or None
        event_key = (event or "").strip() or None
        level_key = (level or "").strip().lower() or None
        backend_key = (backend or "auto").strip().lower()
        if backend_key not in {"auto", "sqlite", "jsonl"}:
            raise HTTPException(status_code=400, detail="backend must be one of: auto, sqlite, jsonl")

        events: list[dict[str, Any]] = []
        source = backend_key
        if backend_key in {"auto", "sqlite"}:
            events = ctx.query_sqlite_telemetry(stream_key, event_key, level_key, since, lim)
            source = "sqlite"

        if backend_key == "jsonl" or (backend_key == "auto" and not events):
            events = ctx.query_jsonl_telemetry(stream_key, event_key, level_key, since, lim)
            source = "jsonl"

        return {
            "source": source,
            "count": len(events),
            "filters": {
                "stream": stream_key,
                "event": event_key,
                "level": level_key,
                "since_minutes": since,
                "limit": lim,
            },
            "events": events,
        }

    @router.get("/telemetry/report")
    async def telemetry_report(
        stream: Optional[str] = None,
        since_minutes: int = 1440,
        limit: int = 1000,
        backend: str = "auto",
        user_id: str = Depends(ctx.require_rate_limit),
    ):
        del user_id
        lim = max(1, min(int(limit), 2000))
        since = max(0, int(since_minutes))
        stream_key = (stream or "").strip() or None
        backend_key = (backend or "auto").strip().lower()
        if backend_key not in {"auto", "sqlite", "jsonl"}:
            raise HTTPException(status_code=400, detail="backend must be one of: auto, sqlite, jsonl")

        events: list[dict[str, Any]] = []
        source = backend_key
        if backend_key in {"auto", "sqlite"}:
            events = ctx.query_sqlite_telemetry(stream_key, None, None, since, lim)
            source = "sqlite"

        if backend_key == "jsonl" or (backend_key == "auto" and not events):
            events = ctx.query_jsonl_telemetry(stream_key, None, None, since, lim)
            source = "jsonl"

        report = ctx.build_telemetry_report(events)
        return {
            "source": source,
            "window": {
                "stream": stream_key,
                "since_minutes": since,
                "limit": lim,
            },
            "report": report,
        }

    @router.get("/repair-token/refresh")
    async def repair_token_refresh(_req: Request):
        client_ip = _req.client.host if _req.client else ""
        if client_ip not in ("127.0.0.1", "::1", "localhost", ""):
            owner.log_session_event(
                "api", "repair_token_refresh_rejected", level="warning", client_ip=client_ip
            )
            raise HTTPException(status_code=403, detail="localhost only")

        token = ctx.read_repair_token()

        owner.log_session_event(
            "api", "repair_token_refresh", level="info", client_ip=client_ip, has_token=bool(token)
        )
        return {"repair_token": token}

    @router.post("/repair")
    async def repair_runtime(
        request: RepairRequest,
        _req: Request,
        user_id: str = Depends(ctx.require_rate_limit),
        _tok: None = Depends(repair_dependency) if repair_dependency is not None else None,
    ):
        del user_id, _req, _tok
        action = (request.action or "").strip().lower()
        dry_run = bool(request.dry_run)
        result = await asyncio.to_thread(ctx.do_repair_action, action, dry_run)
        owner.log_session_event(
            "api",
            "repair_runtime",
            level="info",
            action=action,
            dry_run=dry_run,
            ok=bool(result.get("ok", False)),
            summary=str(result.get("summary", "")),
        )
        return {"action": action, "dry_run": dry_run, **result}

    @router.get("/revenue/dashboard")
    async def get_revenue_dashboard(user_id: str = Depends(ctx.require_rate_limit)):
        del user_id
        if not owner.GUPPY_MEMORY_AVAILABLE:
            raise HTTPException(status_code=503, detail="Memory module not available")
        if not hasattr(owner.memory, "get_revenue_dashboard_data"):
            raise HTTPException(status_code=503, detail="Revenue dashboard not configured")

        try:
            return owner.memory.get_revenue_dashboard_data()
        except Exception as e:
            owner.logger.error(f"Revenue dashboard failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    return router
