from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json_dict(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_jsonl_tail(path: Path, limit: int = 50) -> list[dict[str, Any]]:
    lim = max(1, min(int(limit), 500))
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for line in lines[-lim:]:
        text = str(line or "").strip()
        if not text:
            continue
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                out.append(parsed)
            else:
                out.append({"value": parsed})
        except Exception:
            out.append({"raw": text, "parse_error": True})
    return out
