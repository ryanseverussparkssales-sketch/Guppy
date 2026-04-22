"""Runtime check helpers for hub status/operator cards."""
from __future__ import annotations

import json
import os
import socket
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def is_set(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def safe_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)).strip())
    except Exception:
        return default


def cloudflare_cert_paths() -> list[Path]:
    home = Path.home()
    return [
        home / ".cloudflared" / "cert.pem",
        home / ".cloudflare-warp" / "cert.pem",
        home / "cloudflare-warp" / "cert.pem",
    ]


def check_api_server(port: int = 8081) -> str:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return "LIVE"
    except OSError:
        return "DOWN"


def check_cloudflared(psutil_ok: bool) -> str:
    if not psutil_ok:
        return "UNKNOWN"
    try:
        import psutil

        for proc in psutil.process_iter(["name"]):
            if "cloudflared" in (proc.info.get("name") or "").lower():
                return "RUNNING"
    except Exception:
        pass
    return "STOPPED"


def check_auth_config() -> str:
    dev_jwt = {"", "dev-secret-key-change-in-production"}
    dev_ts = {"", "dev-turnstile-secret"}
    jwt_ok = os.environ.get("GUPPY_JWT_SECRET", "") not in dev_jwt
    ts_ok = os.environ.get("TURNSTILE_SECRET", "") not in dev_ts
    if jwt_ok and ts_ok:
        return "CONFIGURED"
    if jwt_ok or ts_ok:
        return "PARTIAL"
    return "DEV MODE"


def model_for_agent(agent_id: str) -> str:
    if agent_id == "guppy":
        return (os.environ.get("OLLAMA_MODEL", "guppy") or "guppy").strip()
    return ""


def tail_agent_performance(runtime_dir: Path, safe_io: bool, limit: int = 200) -> list[dict]:
    if safe_io:
        from utils.safe_io import read_jsonl_tail

        return read_jsonl_tail(runtime_dir / "agent_performance.jsonl", limit)
    path = runtime_dir / "agent_performance.jsonl"
    if not path.exists():
        return []
    try:
        out = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    out.append(row)
            except Exception:
                continue
        return out
    except Exception:
        return []


def tail_session_events(runtime_dir: Path, safe_io: bool, limit: int = 200) -> list[dict]:
    if safe_io:
        from utils.safe_io import read_jsonl_tail

        return read_jsonl_tail(runtime_dir / "session_events.jsonl", limit)
    path = runtime_dir / "session_events.jsonl"
    if not path.exists():
        return []
    try:
        out = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    out.append(row)
            except Exception:
                continue
        return out
    except Exception:
        return []


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = max(0.0, min(1.0, q)) * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def parse_iso_ts(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        norm = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(norm)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def rolling_agent_stats(
    perf_rows: list[dict],
    session_rows: list[dict],
    window_seconds: int = 900,
) -> dict[str, dict]:
    now = datetime.now(timezone.utc)
    stats = {
        aid: {
            "latest": {},
            "latencies": [],
            "inflight": 0,
            "seen_start_ids": set(),
            "seen_complete_ids": set(),
        }
        for aid in ("guppy",)
    }

    cutoff = now.timestamp() - max(60, int(window_seconds))

    for row in perf_rows:
        aid = str(row.get("agent", "")).strip().lower()
        if aid not in stats:
            continue
        ts = parse_iso_ts(str(row.get("ts", "")))
        if ts is None or ts.timestamp() < cutoff:
            continue

        stats[aid]["latest"] = row
        evt = str(row.get("event", "")).strip().lower()
        req_id = str(row.get("request_id", "")).strip()

        if evt == "request_started":
            if req_id:
                stats[aid]["seen_start_ids"].add(req_id)
            else:
                stats[aid]["inflight"] += 1

        if evt == "request_complete":
            if isinstance(row.get("latency_ms"), (int, float)):
                stats[aid]["latencies"].append(float(row.get("latency_ms")))
            if req_id:
                stats[aid]["seen_complete_ids"].add(req_id)
            else:
                stats[aid]["inflight"] = max(0, stats[aid]["inflight"] - 1)

    for row in session_rows:
        aid = "guppy" if str(row.get("source", "")).strip().lower() == "ui" else ""
        if aid not in stats:
            continue
        ts = parse_iso_ts(str(row.get("ts", "")))
        if ts is None or ts.timestamp() < cutoff:
            continue
        evt = str(row.get("event", "")).strip().lower()
        if evt == "request_started":
            stats[aid]["inflight"] += 1
        elif evt == "request_finished":
            stats[aid]["inflight"] = max(0, stats[aid]["inflight"] - 1)

    out = {}
    for aid, payload in stats.items():
        started = payload["seen_start_ids"]
        completed = payload["seen_complete_ids"]
        id_inflight = len(started - completed)
        queue_depth = max(0, payload["inflight"] + id_inflight)
        lats = payload["latencies"]
        out[aid] = {
            "latest": payload["latest"],
            "queue_depth": queue_depth,
            "p95_ms": round(pct(lats, 0.95), 1) if lats else 0.0,
            "p99_ms": round(pct(lats, 0.99), 1) if lats else 0.0,
            "samples": len(lats),
        }
    return out


def warm_ollama_model(model: str, keep_alive: str = "20m") -> tuple[bool, str]:
    payload = {
        "model": model,
        "prompt": "warmup",
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"num_predict": 1},
    }
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
        if body.get("error"):
            return False, str(body.get("error"))
        return True, "warm"
    except Exception as e:
        return False, str(e)
