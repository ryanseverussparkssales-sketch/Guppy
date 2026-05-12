"""
Mullvad VPN management API.

Uses the Mullvad CLI (`mullvad`) which must be installed and accessible on PATH.
All commands run as the current user — no admin elevation needed for status/connect/disconnect.

GET  /api/vpn/status          — connection status + current relay
GET  /api/vpn/account         — account info (expiry, device name)
GET  /api/vpn/relays          — available relay locations (country/city/hostname)
POST /api/vpn/connect         — connect (optionally set relay first: { country?, city?, hostname? })
POST /api/vpn/disconnect      — disconnect
POST /api/vpn/reconnect       — reconnect (cycle relay)
GET  /api/vpn/relay           — currently selected relay constraint
POST /api/vpn/relay           — set relay constraint { country?, city?, hostname? }
GET  /api/vpn/killswitch      — lockdown mode (kill-switch) state
POST /api/vpn/killswitch      — set lockdown mode { enabled: bool }
"""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext


# ── Mullvad CLI helper ────────────────────────────────────────────────────────

def _mullvad(*args: str, timeout: int = 10) -> str:
    """Run `mullvad <args>` and return stdout. Raises HTTPException if CLI missing."""
    exe = shutil.which("mullvad")
    if not exe:
        raise HTTPException(503, "Mullvad CLI not found — install Mullvad VPN desktop app")
    result = subprocess.run(
        [exe, *args],
        capture_output=True, text=True, timeout=timeout,
    )
    return result.stdout.strip()


def _mullvad_json(*args: str, timeout: int = 10) -> Any:
    """Run `mullvad <args> --json` and return parsed dict/list."""
    raw = _mullvad(*args, "--json", timeout=timeout)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def _mullvad_available() -> bool:
    return shutil.which("mullvad") is not None


# ── Schemas ───────────────────────────────────────────────────────────────────

class RelayConstraint(BaseModel):
    country:  str | None = None   # e.g. "se"
    city:     str | None = None   # e.g. "got"
    hostname: str | None = None   # e.g. "se-got-wg-001"


class KillSwitchRequest(BaseModel):
    enabled: bool


# ── Router ────────────────────────────────────────────────────────────────────

def build_vpn_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/vpn", tags=["vpn"])

    @router.get("/status")
    async def vpn_status(_u = Depends(ctx.require_rate_limit)):
        """Return Mullvad connection status."""
        if not _mullvad_available():
            return {"available": False, "connected": False, "status": "Mullvad not installed"}
        try:
            data = _mullvad_json("status")
            # CLI JSON: {"state": "connected"|"disconnected"|"connecting"|..., "details": {...}}
            state = data.get("state", "unknown")
            details = data.get("details") or {}
            return {
                "available": True,
                "connected": state == "connected",
                "state": state,
                "relay": details.get("endpoint", {}).get("address"),
                "location": details.get("location"),
                "tunnel_type": details.get("tunnel_type"),
            }
        except Exception as e:
            return {"available": True, "connected": False, "state": "unknown", "error": str(e)}

    @router.get("/account")
    async def vpn_account(_u = Depends(ctx.require_rate_limit)):
        """Return Mullvad account info."""
        try:
            data = _mullvad_json("account", "get")
            return data
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    @router.get("/relays")
    async def vpn_relays(_u = Depends(ctx.require_rate_limit)):
        """Return available relay countries/cities."""
        try:
            data = _mullvad_json("relay", "list")
            # Returns list of {name, code, cities: [{name, code, relays: [...]}]}
            return data if isinstance(data, list) else []
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    @router.post("/connect")
    async def vpn_connect(body: RelayConstraint | None = None, _u = Depends(ctx.require_rate_limit)):
        """Optionally set relay, then connect."""
        try:
            if body and any([body.hostname, body.city, body.country]):
                args: list[str] = ["relay", "set", "location"]
                if body.country:
                    args.append(body.country)
                if body.city:
                    args.append(body.city)
                if body.hostname:
                    args.append(body.hostname)
                _mullvad(*args)
            out = _mullvad("connect")
            return {"ok": True, "output": out}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    @router.post("/disconnect")
    async def vpn_disconnect(_u = Depends(ctx.require_rate_limit)):
        """Disconnect from Mullvad."""
        try:
            out = _mullvad("disconnect")
            return {"ok": True, "output": out}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    @router.post("/reconnect")
    async def vpn_reconnect(_u = Depends(ctx.require_rate_limit)):
        """Reconnect (cycles to next relay if connected)."""
        try:
            out = _mullvad("reconnect")
            return {"ok": True, "output": out}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    @router.get("/relay")
    async def vpn_relay_get(_u = Depends(ctx.require_rate_limit)):
        """Get the currently configured relay constraint."""
        try:
            data = _mullvad_json("relay", "get")
            return data
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    @router.post("/relay")
    async def vpn_relay_set(body: RelayConstraint, _u = Depends(ctx.require_rate_limit)):
        """Set relay location constraint."""
        try:
            args = ["relay", "set", "location"]
            if body.country:
                args.append(body.country)
            if body.city:
                args.append(body.city)
            if body.hostname:
                args.append(body.hostname)
            if len(args) == 3:
                raise HTTPException(400, "Provide at least country, city, or hostname")
            out = _mullvad(*args)
            return {"ok": True, "output": out}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    @router.get("/killswitch")
    async def vpn_killswitch_get(_u = Depends(ctx.require_rate_limit)):
        """Get lockdown mode (kill-switch) state."""
        try:
            out = _mullvad("lockdown-mode", "get")
            return {"enabled": "on" in out.lower()}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    @router.post("/killswitch")
    async def vpn_killswitch_set(body: KillSwitchRequest, _u = Depends(ctx.require_rate_limit)):
        """Enable or disable lockdown mode (kill-switch)."""
        try:
            out = _mullvad("lockdown-mode", "on" if body.enabled else "off")
            return {"ok": True, "enabled": body.enabled, "output": out}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    return router
