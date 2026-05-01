import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path


def create_diagnostics_bundle(agent_name: str, runtime_dir: Path | None = None) -> Path:
    root = Path(__file__).resolve().parent.parent
    rt = runtime_dir or (root / "runtime")
    rt.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = rt / f"diagnostics_{agent_name}_{ts}.json"

    logs = {}
    for name in ("session_events.jsonl", "agent_performance.jsonl", "integration_events.jsonl", "hub.log"):
        path = rt / name
        if not path.exists():
            logs[name] = [] if name.endswith(".jsonl") else ""
            continue
        try:
            if name.endswith(".jsonl"):
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                parsed = []
                for line in lines[-200:]:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parsed.append(json.loads(line))
                    except Exception:
                        parsed.append({"raw": line, "parse_error": True})
                logs[name] = parsed
            else:
                logs[name] = path.read_text(encoding="utf-8", errors="replace")[-20000:]
        except Exception as e:
            logs[name] = {"error": str(e)}

    env_subset = {
        "ANTHROPIC_API_KEY": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        "GUPPY_LOCAL_RUNTIME_BACKEND": os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", ""),
        "GUPPY_MAIN_MODEL": os.environ.get("GUPPY_MAIN_MODEL", ""),
        "GUPPY_LOCAL_COMPLEX_MODEL": os.environ.get("GUPPY_LOCAL_COMPLEX_MODEL", ""),
        "MERLIN_LOCAL_MODEL": os.environ.get("MERLIN_LOCAL_MODEL", ""),
        "MERLIN_HAIKU_BOOST": os.environ.get("MERLIN_HAIKU_BOOST", ""),
        "GUPPY_SHOW_BACKEND_DETAILS": os.environ.get("GUPPY_SHOW_BACKEND_DETAILS", ""),
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent": agent_name,
        "system": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
        },
        "env": env_subset,
        "logs": logs,
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return out_path
