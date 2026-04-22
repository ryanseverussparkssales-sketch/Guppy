from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, File, Request, UploadFile, WebSocket

from src.guppy.api._server_fragment_models import ChatRequest, RepairRequest
from src.guppy.api import snapshot_realtime_support, snapshot_route_support, snapshot_telemetry_support


def register_misc_routes(
    app,
    owner: Any,
    *,
    require_rate_limit,
    require_repair_token,
) -> None:
    @app.get("/logs/recent")
    async def get_recent_logs(
        limit: int = 100,
        user_id: str = Depends(require_rate_limit),
    ):
        del user_id
        return snapshot_route_support.recent_logs_response(owner, limit=limit)

    @app.get("/telemetry/query")
    async def telemetry_query(
        stream: Optional[str] = None,
        event: Optional[str] = None,
        level: Optional[str] = None,
        since_minutes: int = 1440,
        limit: int = 200,
        backend: str = "auto",
        user_id: str = Depends(require_rate_limit),
    ):
        del user_id
        return snapshot_telemetry_support.build_telemetry_query_response(
            owner,
            stream=stream,
            event=event,
            level=level,
            since_minutes=since_minutes,
            limit=limit,
            backend=backend,
        )

    @app.get("/telemetry/report")
    async def telemetry_report(
        stream: Optional[str] = None,
        since_minutes: int = 1440,
        limit: int = 1000,
        backend: str = "auto",
        user_id: str = Depends(require_rate_limit),
    ):
        del user_id
        return snapshot_telemetry_support.build_telemetry_report_response(
            owner,
            stream=stream,
            since_minutes=since_minutes,
            limit=limit,
            backend=backend,
        )

    @app.get("/repair-token/refresh")
    async def repair_token_refresh(_req: Request):
        client_ip = _req.client.host if _req.client else ""
        return snapshot_route_support.repair_token_refresh_response(owner, client_ip)

    @app.post("/repair")
    async def repair_runtime(
        request: RepairRequest,
        _req: Request,
        user_id: str = Depends(require_rate_limit),
        _tok: None = Depends(require_repair_token),
    ):
        del user_id
        return await snapshot_route_support.repair_runtime_response(owner, request)

    @app.get("/revenue/dashboard")
    async def get_revenue_dashboard(user_id: str = Depends(require_rate_limit)):
        del user_id
        return snapshot_route_support.revenue_dashboard_response(owner)

    @app.post("/chat")
    async def chat(request: ChatRequest, user_id: str = Depends(require_rate_limit)):
        del user_id
        return await snapshot_realtime_support.chat_response(owner, request)

    @app.post("/chat/voice")
    async def chat_voice(
        file: UploadFile = File(...),
        session_id: Optional[str] = None,
        use_claude: Optional[bool] = True,
        user_id: str = Depends(require_rate_limit),
    ):
        del user_id
        return await snapshot_realtime_support.chat_voice_response(
            owner,
            file=file,
            session_id=session_id,
            use_claude=use_claude,
        )

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await snapshot_realtime_support.websocket_response(owner, websocket)
