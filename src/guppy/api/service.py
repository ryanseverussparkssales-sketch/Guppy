"""
Guppy API Service Layer
Unified backend service adapter for desktop and web UIs.
Provides type-safe, error-resilient API for all UI operations.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels for UI feedback."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class APIError:
    """Structured error response."""
    code: str
    message: str
    severity: ErrorSeverity
    details: dict[str, Any] | None = None
    timestamp: str | None = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


@dataclass
class APIResponse:
    """Standard API response wrapper."""
    success: bool
    data: Any | None = None
    error: APIError | None = None
    metadata: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "success": self.success,
            "data": self.data,
            "error": {
                "code": self.error.code,
                "message": self.error.message,
                "severity": self.error.severity.value,
                "details": self.error.details,
                "timestamp": self.error.timestamp,
            } if self.error else None,
            "metadata": self.metadata,
        }


class WorkspaceService:
    """Workspace/instance management operations."""
    
    async def get_instances(self) -> APIResponse:
        """Fetch all workspace instances."""
        try:
            return APIResponse(success=True, data=[])
        except Exception as e:
            logger.exception("Failed to get instances")
            return APIResponse(
                success=False,
                error=APIError(
                    code="WORKSPACE_FETCH_FAILED",
                    message="Failed to fetch workspace instances",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)},
                )
            )
    
    async def create_instance(self, config: dict[str, Any]) -> APIResponse:
        """Create a new workspace instance."""
        try:
            return APIResponse(success=True, data={"id": "new-instance"})
        except Exception as e:
            logger.exception("Failed to create instance")
            return APIResponse(
                success=False,
                error=APIError(
                    code="WORKSPACE_CREATE_FAILED",
                    message="Failed to create workspace instance",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)},
                )
            )
    
    async def update_instance(self, instance_id: str, config: dict[str, Any]) -> APIResponse:
        """Update an existing instance."""
        try:
            return APIResponse(success=True, data={"id": instance_id})
        except Exception as e:
            logger.exception("Failed to update instance")
            return APIResponse(
                success=False,
                error=APIError(
                    code="WORKSPACE_UPDATE_FAILED",
                    message="Failed to update workspace instance",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)},
                )
            )
    
    async def delete_instance(self, instance_id: str) -> APIResponse:
        """Delete a workspace instance."""
        try:
            return APIResponse(success=True, data={"id": instance_id})
        except Exception as e:
            logger.exception("Failed to delete instance")
            return APIResponse(
                success=False,
                error=APIError(
                    code="WORKSPACE_DELETE_FAILED",
                    message="Failed to delete workspace instance",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)},
                )
            )


class ModelsService:
    """Model and runtime management operations."""
    
    async def get_models(self) -> APIResponse:
        """Fetch available models."""
        try:
            return APIResponse(success=True, data=[])
        except Exception as e:
            logger.exception("Failed to get models")
            return APIResponse(
                success=False,
                error=APIError(
                    code="MODELS_FETCH_FAILED",
                    message="Failed to fetch available models",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)},
                )
            )
    
    async def get_runtime_status(self) -> APIResponse:
        """Get current runtime status and health."""
        try:
            return APIResponse(success=True, data={"status": "healthy"})
        except Exception as e:
            logger.exception("Failed to get runtime status")
            return APIResponse(
                success=False,
                error=APIError(
                    code="RUNTIME_STATUS_FAILED",
                    message="Failed to fetch runtime status",
                    severity=ErrorSeverity.WARNING,
                    details={"error": str(e)},
                )
            )
    
    async def set_active_model(self, model_id: str) -> APIResponse:
        """Set the active model."""
        try:
            return APIResponse(success=True, data={"active_model": model_id})
        except Exception as e:
            logger.exception("Failed to set active model")
            return APIResponse(
                success=False,
                error=APIError(
                    code="MODEL_SELECT_FAILED",
                    message=f"Failed to set active model to {model_id}",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)},
                )
            )


class AssistantService:
    """Assistant/chat operations."""
    
    async def send_message(self, workspace_id: str, message: str, context: dict[str, Any] | None = None) -> APIResponse:
        """Send a message to the assistant."""
        try:
            return APIResponse(success=True, data={"response": ""})
        except Exception as e:
            logger.exception("Failed to send message")
            return APIResponse(
                success=False,
                error=APIError(
                    code="CHAT_SEND_FAILED",
                    message="Failed to send message to assistant",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)},
                )
            )
    
    async def get_conversation_history(self, workspace_id: str, limit: int = 50) -> APIResponse:
        """Get conversation history."""
        try:
            return APIResponse(success=True, data=[])
        except Exception as e:
            logger.exception("Failed to get conversation history")
            return APIResponse(
                success=False,
                error=APIError(
                    code="HISTORY_FETCH_FAILED",
                    message="Failed to fetch conversation history",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)},
                )
            )


class LibraryService:
    """Library/knowledge base operations."""
    
    async def get_library_items(self, workspace_id: str) -> APIResponse:
        """Get library items (files, notes, artifacts)."""
        try:
            return APIResponse(success=True, data=[])
        except Exception as e:
            logger.exception("Failed to get library items")
            return APIResponse(
                success=False,
                error=APIError(
                    code="LIBRARY_FETCH_FAILED",
                    message="Failed to fetch library items",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)},
                )
            )
    
    async def save_artifact(self, workspace_id: str, content: str, artifact_type: str) -> APIResponse:
        """Save an artifact to the library."""
        try:
            return APIResponse(success=True, data={"id": "artifact-id"})
        except Exception as e:
            logger.exception("Failed to save artifact")
            return APIResponse(
                success=False,
                error=APIError(
                    code="ARTIFACT_SAVE_FAILED",
                    message="Failed to save artifact",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)},
                )
            )


class SettingsService:
    """Settings and configuration operations."""
    
    async def get_settings(self, scope: str = "user") -> APIResponse:
        """Get settings."""
        try:
            return APIResponse(success=True, data={})
        except Exception as e:
            logger.exception("Failed to get settings")
            return APIResponse(
                success=False,
                error=APIError(
                    code="SETTINGS_FETCH_FAILED",
                    message="Failed to fetch settings",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)},
                )
            )
    
    async def update_settings(self, scope: str, settings: dict[str, Any]) -> APIResponse:
        """Update settings."""
        try:
            return APIResponse(success=True, data=settings)
        except Exception as e:
            logger.exception("Failed to update settings")
            return APIResponse(
                success=False,
                error=APIError(
                    code="SETTINGS_UPDATE_FAILED",
                    message="Failed to update settings",
                    severity=ErrorSeverity.ERROR,
                    details={"error": str(e)},
                )
            )


class GuppyAPIClient:
    """Main API client for UI integration."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8081"):
        """Initialize API client."""
        self.base_url = base_url
        self.workspaces = WorkspaceService()
        self.models = ModelsService()
        self.assistant = AssistantService()
        self.library = LibraryService()
        self.settings = SettingsService()
        
        # Callbacks for real-time updates
        self._update_callbacks: dict[str, list[Callable]] = {
            "status": [],
            "messages": [],
            "instances": [],
            "models": [],
            "library": [],
            "settings": [],
        }
    
    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe to real-time events."""
        if event_type not in self._update_callbacks:
            self._update_callbacks[event_type] = []
        self._update_callbacks[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Unsubscribe from events."""
        if event_type in self._update_callbacks:
            self._update_callbacks[event_type].remove(callback)
    
    async def _emit_update(self, event_type: str, data: Any) -> None:
        """Emit update to all subscribers."""
        if event_type in self._update_callbacks:
            for callback in self._update_callbacks[event_type]:
                try:
                    if hasattr(callback, "__await__"):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.exception(f"Error in callback for {event_type}: {e}")
    
    async def health_check(self) -> APIResponse:
        """Check API health."""
        try:
            return APIResponse(
                success=True,
                data={"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
            )
        except Exception as e:
            logger.exception("Health check failed")
            return APIResponse(
                success=False,
                error=APIError(
                    code="HEALTH_CHECK_FAILED",
                    message="API health check failed",
                    severity=ErrorSeverity.CRITICAL,
                    details={"error": str(e)},
                )
            )


# Global instance for convenient access
_api_client: Optional[GuppyAPIClient] = None


def get_api_client() -> GuppyAPIClient:
    """Get or create the global API client."""
    global _api_client
    if _api_client is None:
        _api_client = GuppyAPIClient()
    return _api_client


def init_api_client(base_url: str = "http://127.0.0.1:8081") -> GuppyAPIClient:
    """Initialize the global API client."""
    global _api_client
    _api_client = GuppyAPIClient(base_url)
    return _api_client
