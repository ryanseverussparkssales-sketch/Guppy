"""Safe web fetch utility with SSRF protection.

All tool-accessible web fetches must go through ``safe_web_fetch()`` to
prevent Server-Side Request Forgery (SSRF) attacks that could reach internal
services, localhost, or cloud metadata endpoints.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse


# ── SSRF blocklist ─────────────────────────────────────────────────────────────

_BLOCKED_SCHEMES = {"file", "ftp", "gopher", "data", "javascript"}

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("169.254.0.0/16"),    # link-local / AWS metadata
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 unique-local
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]

_BLOCKED_HOSTS = {
    "metadata.google.internal",
    "169.254.169.254",           # AWS/GCP/Azure IMDS
    "metadata.azure.internal",
    "instance-data",
}


def _is_safe_url(url: str) -> tuple[bool, str]:
    """Return (True, '') if safe, else (False, reason)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "invalid URL"

    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        return False, f"scheme '{scheme}' not allowed"

    host = (parsed.hostname or "").lower().strip("[]")
    if not host:
        return False, "no host"

    if host in _BLOCKED_HOSTS:
        return False, f"host '{host}' is blocked"

    # Resolve hostname to IPs and check each one
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for info in infos:
            addr = info[4][0]
            try:
                ip = ipaddress.ip_address(addr)
            except ValueError:
                continue
            for net in _PRIVATE_NETWORKS:
                if ip in net:
                    return False, f"resolved to private/reserved address {addr}"
    except socket.gaierror:
        return False, f"DNS resolution failed for '{host}'"

    return True, ""


async def safe_web_fetch(
    url: str,
    extract: str = "",
    timeout: float = 20.0,
    max_chars: int = 20000,
    return_chars: int = 8000,
) -> dict:
    """Fetch a URL safely. Returns ``{"ok": True, "text": ..., "url": ...}``
    or ``{"ok": False, "error": ..., "url": ...}``.

    Raises nothing — all errors are returned as ``ok: False`` dicts.
    """
    url = url.strip()
    if not url:
        return {"ok": False, "error": "url required", "url": url}

    safe, reason = _is_safe_url(url)
    if not safe:
        return {"ok": False, "error": f"URL blocked: {reason}", "url": url}

    try:
        import httpx

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 Guppy/1.0"})
            text = resp.text

        # Strip HTML tags to plain text
        if "<html" in text.lower()[:500]:
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"[ \t]{3,}", " ", text)
            text = re.sub(r"\n{4,}", "\n\n", text)

        text = text[:max_chars]

        if extract:
            extract = extract.lower()
            idx = text.lower().find(extract)
            if idx >= 0:
                text = text[max(0, idx - 100) : idx + 6000]

        return {"ok": True, "text": text[:return_chars], "url": url, "length": len(text)}

    except Exception as e:
        return {"ok": False, "error": str(e), "url": url}
