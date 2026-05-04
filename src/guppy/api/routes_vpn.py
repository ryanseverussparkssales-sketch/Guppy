"""
VPN management API — Windows built-in VPN + WireGuard detection.

GET  /api/vpn/connections          — list configured VPN connections
GET  /api/vpn/status               — current connection state
POST /api/vpn/connect              — connect a VPN by name { name, username?, password? }
POST /api/vpn/disconnect           — disconnect a VPN by name { name }
POST /api/vpn/add                  — add a new VPN connection
DELETE /api/vpn/connections/{name} — remove a VPN connection
GET  /api/vpn/wireguard            — WireGuard tunnel status (if installed)
POST /api/vpn/wireguard/up         — bring up a WireGuard tunnel { tunnel }
POST /api/vpn/wireguard/down       — bring down a WireGuard tunnel { tunnel }
"""
from __future__ import annotations

import json
import subprocess
import shutil
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.guppy.api.server_context import ServerContext


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ps(script: str, timeout: int = 15) -> str:
    """Run a PowerShell script and return stdout."""
    result = subprocess.run(
        ["powershell", "-NonInteractive", "-NoProfile", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
    )
    return result.stdout.strip()


def _ps_json(script: str) -> Any:
    """Run a PowerShell script that outputs JSON and parse it."""
    raw = _ps(script + " | ConvertTo-Json -Depth 4")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        # PowerShell ConvertTo-Json wraps single objects — normalize to list
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        return []


def _normalize_vpn(raw: dict) -> dict:
    return {
        "name":          raw.get("Name", ""),
        "server":        raw.get("ServerAddress", ""),
        "status":        raw.get("ConnectionStatus", "Disconnected"),
        "tunnel_type":   raw.get("TunnelType", ""),
        "auth_method":   raw.get("AuthenticationMethod", []),
        "split_tunnel":  raw.get("SplitTunneling", False),
    }


# ── Models ────────────────────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    name: str
    username: str = ""
    password: str = ""


class DisconnectRequest(BaseModel):
    name: str


class AddVpnRequest(BaseModel):
    name: str
    server: str
    tunnel_type: str = "Automatic"   # Automatic | L2tp | Pptp | Sstp | IkeV2
    auth_method: str = "MSChapv2"    # MSChapv2 | Pap | Chap | Eap | MachineCertificate
    remember_credential: bool = True
    split_tunnel: bool = False
    l2tp_psk: str = ""               # Pre-shared key for L2TP


class WireGuardRequest(BaseModel):
    tunnel: str   # tunnel name (matches .conf file name in WireGuard directory)


# ── Router ────────────────────────────────────────────────────────────────────

def build_vpn_router(ctx: ServerContext) -> APIRouter:
    router = APIRouter(prefix="/api/vpn", tags=["vpn"])

    @router.get("/connections")
    def list_connections(_uid: str = Depends(ctx.require_rate_limit)):
        """List all configured Windows VPN connections."""
        try:
            rows = _ps_json("Get-VpnConnection -ErrorAction SilentlyContinue | Select-Object Name, ServerAddress, ConnectionStatus, TunnelType, AuthenticationMethod, SplitTunneling")
            return [_normalize_vpn(r) for r in rows]
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "PowerShell timed out")
        except Exception as e:
            raise HTTPException(500, f"Could not list VPN connections: {e}")

    @router.get("/status")
    def vpn_status(_uid: str = Depends(ctx.require_rate_limit)):
        """Return connection status for all VPN connections."""
        try:
            rows = _ps_json("Get-VpnConnection -ErrorAction SilentlyContinue | Select-Object Name, ConnectionStatus")
            connected = [r.get("Name", "") for r in rows if r.get("ConnectionStatus") == "Connected"]
            return {"connected": connected, "all": [{"name": r.get("Name", ""), "status": r.get("ConnectionStatus", "Disconnected")} for r in rows]}
        except Exception as e:
            raise HTTPException(500, f"Could not get VPN status: {e}")

    @router.post("/connect")
    def connect_vpn(body: ConnectRequest, _uid: str = Depends(ctx.require_rate_limit)):
        """Connect a Windows VPN connection by name."""
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "name is required")
        try:
            if body.username and body.password:
                cmd = f'rasdial "{name}" "{body.username}" "{body.password}"'
            else:
                cmd = f'rasdial "{name}"'
            out = _ps(cmd, timeout=30)
            if "error" in out.lower() or "failed" in out.lower():
                raise HTTPException(500, f"Connection failed: {out}")
            return {"ok": True, "name": name, "output": out}
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "Connection timed out (30s)")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Connect failed: {e}")

    @router.post("/disconnect")
    def disconnect_vpn(body: DisconnectRequest, _uid: str = Depends(ctx.require_rate_limit)):
        """Disconnect a Windows VPN connection by name."""
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "name is required")
        try:
            out = _ps(f'rasdial "{name}" /disconnect', timeout=15)
            return {"ok": True, "name": name, "output": out}
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "Disconnect timed out")
        except Exception as e:
            raise HTTPException(500, f"Disconnect failed: {e}")

    @router.post("/add")
    def add_vpn(body: AddVpnRequest, _uid: str = Depends(ctx.require_rate_limit)):
        """Add a new Windows VPN connection."""
        if not body.name.strip() or not body.server.strip():
            raise HTTPException(400, "name and server are required")
        try:
            psk_part = f' -L2tpPsk "{body.l2tp_psk}"' if body.l2tp_psk else ""
            script = (
                f'Add-VpnConnection -Name "{body.name}" -ServerAddress "{body.server}" '
                f'-TunnelType {body.tunnel_type} -AuthenticationMethod {body.auth_method} '
                f'-RememberCredential:${str(body.remember_credential).lower()} '
                f'-SplitTunneling:${str(body.split_tunnel).lower()}'
                f'{psk_part} -Force -ErrorAction Stop'
            )
            out = _ps(script, timeout=15)
            return {"ok": True, "name": body.name, "output": out}
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "Add VPN timed out")
        except Exception as e:
            raise HTTPException(500, f"Add VPN failed: {e}")

    @router.delete("/connections/{name}")
    def remove_vpn(name: str, _uid: str = Depends(ctx.require_rate_limit)):
        """Remove a configured Windows VPN connection."""
        try:
            out = _ps(f'Remove-VpnConnection -Name "{name}" -Force -ErrorAction Stop', timeout=10)
            return {"ok": True, "name": name, "output": out}
        except Exception as e:
            raise HTTPException(500, f"Remove VPN failed: {e}")

    # ── WireGuard ─────────────────────────────────────────────────────────────

    def _wg_available() -> bool:
        return shutil.which("wireguard") is not None or shutil.which("wg") is not None

    @router.get("/wireguard")
    def wireguard_status(_uid: str = Depends(ctx.require_rate_limit)):
        """List WireGuard tunnels and their status (requires WireGuard installed)."""
        if not _wg_available():
            return {"available": False, "tunnels": []}
        try:
            raw = _ps("wg show all 2>$null", timeout=10)
            if not raw:
                return {"available": True, "tunnels": [], "raw": ""}
            return {"available": True, "tunnels": [], "raw": raw}
        except Exception as e:
            return {"available": True, "tunnels": [], "error": str(e)}

    @router.post("/wireguard/up")
    def wireguard_up(body: WireGuardRequest, _uid: str = Depends(ctx.require_rate_limit)):
        """Bring up a WireGuard tunnel by name."""
        if not _wg_available():
            raise HTTPException(503, "WireGuard not installed")
        try:
            out = _ps(f'wireguard /installtunnelservice "{body.tunnel}" 2>$null', timeout=15)
            return {"ok": True, "tunnel": body.tunnel, "output": out}
        except Exception as e:
            raise HTTPException(500, f"WireGuard up failed: {e}")

    @router.post("/wireguard/down")
    def wireguard_down(body: WireGuardRequest, _uid: str = Depends(ctx.require_rate_limit)):
        """Bring down a WireGuard tunnel by name."""
        if not _wg_available():
            raise HTTPException(503, "WireGuard not installed")
        try:
            out = _ps(f'wireguard /uninstalltunnelservice "{body.tunnel}" 2>$null', timeout=15)
            return {"ok": True, "tunnel": body.tunnel, "output": out}
        except Exception as e:
            raise HTTPException(500, f"WireGuard down failed: {e}")

    return router
