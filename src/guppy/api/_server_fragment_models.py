"""Shared request/response models for the split FastAPI server fragments."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None  # Workspace context for organizing conversations
    mode: Optional[str] = None
    persona: Optional[str] = None
    history: Optional[List[Dict[str, str]]] = None
    use_claude: Optional[bool] = True
    model: Optional[str] = None  # Model to use: "fast", "code", "main", or any Ollama model name
    idempotency_key: Optional[str] = None
    image_base64: Optional[str] = None  # base64-encoded image for multimodal backends (MiniCPM-o)
    surface: Optional[str] = None  # "companion", "workspace", "codespace" — used for system prompt context


class VoiceChatRequest(BaseModel):
    session_id: Optional[str] = None
    use_claude: Optional[bool] = True


class TurnstileToken(BaseModel):
    token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RepairRequest(BaseModel):
    action: str
    dry_run: bool = False


class InstanceQueryRequest(BaseModel):
    message: str
    source_instance: Optional[str] = None
    timeout_s: float = 30.0
    mode: Optional[str] = None  # override routing: "auto", "local", "claude", "code", etc.


class InstanceConfigRequest(BaseModel):
    name: str
    description: str = ""
    mode: str = "auto"
    persona: str = "guppy"
    voice: str = "default"
    enabled: bool = True
    type: str = "user_instance"


class InstanceGovernanceRequest(BaseModel):
    auth_mode: str = "runtime_default"
    tool_allow: List[str] = []
    tool_block: List[str] = []
    endpoint_allow: List[str] = []
    endpoint_block: List[str] = []
    policy_note: str = ""


class ConnectorActionRequest(BaseModel):
    provider: str = ""
    account_id: str = ""
    secret_key: str = ""
    secret_value: str = ""


class InstanceConnectorBindingRequest(BaseModel):
    enabled: bool = False
    account_id: str = ""
    provider: str = ""
    action_allow: List[str] = []
    action_block: List[str] = []
    endpoint_allow: List[str] = []
    endpoint_block: List[str] = []
    note: str = ""
