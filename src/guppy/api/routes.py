"""
FastAPI Routes for Guppy API
Provides endpoints for both desktop and web UIs
"""
from fastapi import APIRouter, HTTPException, WebSocket, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Optional, List
import logging

from .service import (
    GuppyAPIClient,
    APIResponse,
    APIError,
    ErrorSeverity,
    WorkspaceService,
    ModelsService,
    AssistantService,
    LibraryService,
    SettingsService,
)

logger = logging.getLogger(__name__)

# Initialize API client
api_client = GuppyAPIClient()

# Create routers
router = APIRouter(prefix="/api", tags=["api"])
workspace_router = APIRouter(prefix="/workspaces", tags=["workspaces"])
models_router = APIRouter(prefix="/models", tags=["models"])
assistant_router = APIRouter(prefix="/assistant", tags=["assistant"])
library_router = APIRouter(prefix="/library", tags=["library"])
settings_router = APIRouter(prefix="/settings", tags=["settings"])

# ─── Health Check ─────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """API health check."""
    response = await api_client.health_check()
    status_code = 200 if response.success else 503
    return JSONResponse(response.to_dict(), status_code=status_code)


# ─── Workspace Endpoints ──────────────────────────────────────────────

@workspace_router.get("/")
async def list_workspaces():
    """Get all workspace instances."""
    response = await api_client.workspaces.get_instances()
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error.message)
    return response.to_dict()


@workspace_router.post("/")
async def create_workspace(config: dict):
    """Create new workspace instance."""
    response = await api_client.workspaces.create_instance(config)
    if not response.success:
        raise HTTPException(status_code=400, detail=response.error.message)
    return response.to_dict()


@workspace_router.put("/{instance_id}")
async def update_workspace(instance_id: str, config: dict):
    """Update workspace instance."""
    response = await api_client.workspaces.update_instance(instance_id, config)
    if not response.success:
        raise HTTPException(status_code=400, detail=response.error.message)
    return response.to_dict()


@workspace_router.delete("/{instance_id}")
async def delete_workspace(instance_id: str):
    """Delete workspace instance."""
    response = await api_client.workspaces.delete_instance(instance_id)
    if not response.success:
        raise HTTPException(status_code=400, detail=response.error.message)
    return response.to_dict()


# ─── Models Endpoints ─────────────────────────────────────────────────

@models_router.get("/")
async def list_models():
    """Get available models."""
    response = await api_client.models.get_models()
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error.message)
    return response.to_dict()


@models_router.get("/runtime-status")
async def get_runtime_status():
    """Get runtime status and health."""
    response = await api_client.models.get_runtime_status()
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error.message)
    return response.to_dict()


@models_router.post("/{model_id}/activate")
async def activate_model(model_id: str):
    """Set model as active."""
    response = await api_client.models.set_active_model(model_id)
    if not response.success:
        raise HTTPException(status_code=400, detail=response.error.message)
    return response.to_dict()


# ─── Assistant Endpoints ──────────────────────────────────────────────

@assistant_router.post("/message")
async def send_message(workspace_id: str, message: str, context: Optional[dict] = None):
    """Send message to assistant."""
    response = await api_client.assistant.send_message(workspace_id, message, context)
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error.message)
    return response.to_dict()


@assistant_router.get("/{workspace_id}/history")
async def get_conversation_history(workspace_id: str, limit: int = 50):
    """Get conversation history."""
    response = await api_client.assistant.get_conversation_history(workspace_id, limit)
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error.message)
    return response.to_dict()


# ─── Library Endpoints ────────────────────────────────────────────────

@library_router.get("/{workspace_id}")
async def get_library(workspace_id: str):
    """Get library items for workspace."""
    response = await api_client.library.get_library_items(workspace_id)
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error.message)
    return response.to_dict()


@library_router.post("/{workspace_id}")
async def save_artifact(workspace_id: str, content: str, artifact_type: str):
    """Save artifact to library."""
    response = await api_client.library.save_artifact(workspace_id, content, artifact_type)
    if not response.success:
        raise HTTPException(status_code=400, detail=response.error.message)
    return response.to_dict()


# ─── Settings Endpoints ───────────────────────────────────────────────

@settings_router.get("/")
async def get_settings(scope: str = "user"):
    """Get settings."""
    response = await api_client.settings.get_settings(scope)
    if not response.success:
        raise HTTPException(status_code=500, detail=response.error.message)
    return response.to_dict()


@settings_router.put("/")
async def update_settings(scope: str, settings: dict):
    """Update settings."""
    response = await api_client.settings.update_settings(scope, settings)
    if not response.success:
        raise HTTPException(status_code=400, detail=response.error.message)
    return response.to_dict()


# ─── WebSocket for Real-time Updates ──────────────────────────────────

@router.websocket("/ws/subscribe/{event_type}")
async def websocket_subscribe(websocket: WebSocket, event_type: str):
    """WebSocket subscription for real-time updates."""
    await websocket.accept()
    
    async def callback(data):
        """Send update to connected client."""
        try:
            await websocket.send_json({
                "event": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            logger.exception(f"Error sending WebSocket message: {e}")
    
    # Subscribe to events
    api_client.subscribe(event_type, callback)
    
    try:
        # Keep connection open
        while True:
            # Receive but ignore client messages
            await websocket.receive_text()
    except Exception as e:
        logger.debug(f"WebSocket closed: {e}")
    finally:
        # Unsubscribe on disconnect
        api_client.unsubscribe(event_type, callback)
        await websocket.close()


# ─── Include routers in main app ──────────────────────────────────────

def include_routes(app):
    """Register all routers with FastAPI app."""
    app.include_router(router)
    app.include_router(workspace_router)
    app.include_router(models_router)
    app.include_router(assistant_router)
    app.include_router(library_router)
    app.include_router(settings_router)
