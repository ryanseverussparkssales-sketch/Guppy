"""Cloud-safe settings routes.

Reads and writes settings in-process.  Provider credentials are validated
for shape only — no desktop keyring or file system is touched.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["settings"])

_SUPPORTED_PROVIDERS = {"anthropic", "openai", "google", "local"}

_settings: dict[str, Any] = {}


def _current_settings() -> dict[str, Any]:
    if not _settings:
        _settings.update({
            "theme": os.environ.get("GUPPY_THEME", "dark"),
            "language": os.environ.get("GUPPY_LANGUAGE", "en"),
            "active_provider": os.environ.get("GUPPY_ACTIVE_PROVIDER", "anthropic"),
            "active_model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            "providers": {
                "anthropic": {"configured": bool(os.environ.get("ANTHROPIC_API_KEY"))},
                "openai": {"configured": bool(os.environ.get("OPENAI_API_KEY"))},
                "google": {"configured": bool(os.environ.get("GOOGLE_API_KEY"))},
                "local": {"configured": True},
            },
        })
    return _settings


class CredentialsUpdate(BaseModel):
    provider: str
    api_key: str


class ProviderUpdate(BaseModel):
    provider: str
    model: str = ""


class SettingUpdate(BaseModel):
    key: str
    value: Any


@router.get("/api/settings")
async def get_settings() -> dict[str, Any]:
    return _current_settings()


@router.post("/api/settings/credentials")
async def update_credentials(body: CredentialsUpdate) -> dict[str, Any]:
    if body.provider not in _SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider}")
    if not body.api_key:
        raise HTTPException(status_code=400, detail="api_key must not be empty")
    s = _current_settings()
    if body.provider in s.get("providers", {}):
        s["providers"][body.provider]["configured"] = True
    return {"ok": True, "provider": body.provider}


@router.delete("/api/settings/credentials/{provider}")
async def delete_credentials(provider: str) -> dict[str, Any]:
    s = _current_settings()
    if provider not in s.get("providers", {}):
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider}")
    s["providers"][provider]["configured"] = False
    return {"ok": True, "provider": provider}


@router.post("/api/settings/provider")
async def set_active_provider(body: ProviderUpdate) -> dict[str, Any]:
    if body.provider not in _SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {body.provider}")
    s = _current_settings()
    s["active_provider"] = body.provider
    if body.model:
        s["active_model"] = body.model
    return {"ok": True, "active_provider": body.provider, "active_model": s["active_model"]}


@router.patch("/api/settings")
async def update_setting(body: SettingUpdate) -> dict[str, Any]:
    s = _current_settings()
    s[body.key] = body.value
    return {"ok": True, "key": body.key, "value": body.value}
