"""Lightweight GitHub API helpers for Guppy tools."""

from __future__ import annotations

import base64
import os
from typing import Any, Dict, Optional

import requests

API_BASE = "https://api.github.com"


def _token() -> str:
    return os.environ.get("GITHUB_TOKEN", "").strip()


def _headers() -> Dict[str, str]:
    tok = _token()
    if not tok:
        return {}
    return {
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _require_token() -> Optional[str]:
    if not _token():
        return "GitHub unavailable: set GITHUB_TOKEN in .env (repo scope recommended)."
    return None


def _request(method: str, path: str, **kwargs) -> requests.Response:
    url = f"{API_BASE}{path}"
    headers = kwargs.pop("headers", {})
    headers = {**_headers(), **headers}
    r = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    return r


def _parse_repo(repo: str) -> tuple[str, str] | tuple[None, None]:
    text = (repo or "").strip()
    if "/" not in text:
        return None, None
    owner, name = text.split("/", 1)
    owner = owner.strip()
    name = name.strip()
    if not owner or not name:
        return None, None
    return owner, name


def github_action(action: str, repo: str = "", title: str = "", body: str = "", path: str = "", ref: str = "") -> str:
    token_err = _require_token()
    if token_err:
        return token_err

    act = (action or "").strip().lower()
    if not act:
        return "GitHub action is required."

    try:
        if act == "list_repos":
            r = _request("GET", "/user/repos", params={"per_page": 30, "sort": "updated"})
            if r.status_code >= 400:
                return f"GitHub error {r.status_code}: {r.text[:300]}"
            rows = r.json()
            if not rows:
                return "No repositories found."
            lines = ["GitHub repositories:"]
            for it in rows[:20]:
                lines.append(f"- {it.get('full_name')} ({'private' if it.get('private') else 'public'})")
            return "\n".join(lines)

        owner, name = _parse_repo(repo)
        if not owner or not name:
            return "Invalid repo. Use owner/repo format."

        if act == "list_issues":
            r = _request("GET", f"/repos/{owner}/{name}/issues", params={"state": "open", "per_page": 30})
            if r.status_code >= 400:
                return f"GitHub error {r.status_code}: {r.text[:300]}"
            rows = [x for x in r.json() if "pull_request" not in x]
            if not rows:
                return f"No open issues in {owner}/{name}."
            lines = [f"Open issues in {owner}/{name}:"]
            for it in rows[:20]:
                lines.append(f"- #{it.get('number')}: {it.get('title')}")
            return "\n".join(lines)

        if act == "create_issue":
            if not title.strip():
                return "Title is required for create_issue."
            payload: Dict[str, Any] = {"title": title.strip()}
            if body.strip():
                payload["body"] = body
            r = _request("POST", f"/repos/{owner}/{name}/issues", json=payload)
            if r.status_code >= 400:
                return f"GitHub error {r.status_code}: {r.text[:300]}"
            it = r.json()
            return f"Issue created: #{it.get('number')} {it.get('title')}"

        if act == "list_prs":
            r = _request("GET", f"/repos/{owner}/{name}/pulls", params={"state": "open", "per_page": 30})
            if r.status_code >= 400:
                return f"GitHub error {r.status_code}: {r.text[:300]}"
            rows = r.json()
            if not rows:
                return f"No open pull requests in {owner}/{name}."
            lines = [f"Open PRs in {owner}/{name}:"]
            for it in rows[:20]:
                lines.append(f"- #{it.get('number')}: {it.get('title')}")
            return "\n".join(lines)

        if act == "get_file":
            if not path.strip():
                return "Path is required for get_file."
            params = {"ref": ref.strip()} if ref.strip() else None
            safe_path = "/" + path.strip().lstrip("/")
            r = _request("GET", f"/repos/{owner}/{name}/contents{safe_path}", params=params)
            if r.status_code >= 400:
                return f"GitHub error {r.status_code}: {r.text[:300]}"
            data = r.json()
            if isinstance(data, list):
                lines = [f"Directory listing for {owner}/{name}:{safe_path}"]
                for it in data[:50]:
                    lines.append(f"- {it.get('type')}: {it.get('path')}")
                return "\n".join(lines)
            if data.get("type") != "file":
                return f"Path is not a file: {path}"
            content_b64 = data.get("content", "")
            decoded = base64.b64decode(content_b64).decode("utf-8", errors="replace") if content_b64 else ""
            if len(decoded) > 8000:
                return decoded[:8000] + f"\n[Truncated {len(decoded)} chars total]"
            return decoded

        return "Unsupported action. Use: list_repos, list_issues, create_issue, list_prs, get_file"
    except Exception as e:
        return f"GitHub tool error: {e}"
