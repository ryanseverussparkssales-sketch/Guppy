from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

_DEFAULT_LEMONADE_BASE_URL = "http://localhost:13305/api/v1"
_DEFAULT_LMSTUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
_DEFAULT_LOCAL_HARNESS_BASE_URL = "http://127.0.0.1:8001"


class LocalRuntimeFetchThread(QThread):
    finished = Signal(dict)

    def __init__(self, backend: str, base_url: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._backend = (backend or "ollama").strip().lower()
        self._base_url = (base_url or "").strip()

    def run(self) -> None:
        try:
            if self._backend == "lemonade":
                url = f"{(self._base_url or _DEFAULT_LEMONADE_BASE_URL).rstrip('/')}/models"
                req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read())
                models = [
                    {
                        "name": str(item.get("id", "")).strip(),
                        "display": str(item.get("id", "")).strip().replace("-", " ").replace("_", " ").title(),
                        "size": 0,
                        "context": "GGUF / OpenAI API",
                        "note": "Downloaded in Lemonade",
                    }
                    for item in data.get("data", [])
                    if isinstance(item, dict) and str(item.get("id", "")).strip()
                ]
            else:
                req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read())
                models = [
                    {
                        "name": str(item.get("name", "")).strip(),
                        "display": str(item.get("name", "")).strip().split(":")[0].replace("-", " ").title(),
                        "size": int(item.get("size", 0) or 0),
                        "context": "Installed on this PC",
                        "note": "",
                    }
                    for item in data.get("models", [])
                    if isinstance(item, dict) and str(item.get("name", "")).strip()
                ]
            self.finished.emit({"backend": self._backend, "models": models, "error": ""})
        except Exception as exc:
            self.finished.emit({"backend": self._backend, "models": [], "error": str(exc)})


class ModelWarmSpawnThread(QThread):
    finished = Signal(dict)

    def __init__(self, models: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._models = [str(item or "").strip() for item in models if str(item or "").strip()]

    def run(self) -> None:
        warmed: list[str] = []
        failed: list[str] = []
        for model in self._models:
            try:
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/generate",
                    data=json.dumps(
                        {
                            "model": model,
                            "prompt": "warmup",
                            "stream": False,
                            "keep_alive": "20m",
                            "options": {"num_predict": 1},
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=8):
                    pass
                warmed.append(model)
            except Exception:
                failed.append(model)
        self.finished.emit({"warmed": warmed, "failed": failed})


class ModelHealthCheckThread(QThread):
    finished = Signal(dict)

    def __init__(self, lemonade_base_url: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lemonade_base_url = (lemonade_base_url or _DEFAULT_LEMONADE_BASE_URL).strip() or _DEFAULT_LEMONADE_BASE_URL

    def _probe_json(self, url: str, timeout: float = 3.5) -> tuple[bool, str]:
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read() or b"{}")
            count = len(data.get("data", data.get("models", [])) if isinstance(data, dict) else 0)
            return True, f"ok ({count} models)"
        except Exception as exc:
            return False, str(exc)

    def run(self) -> None:
        statuses: dict[str, str] = {}
        anth_key = bool((os.environ.get("ANTHROPIC_API_KEY", "") or "").strip())
        openai_key = bool((os.environ.get("OPENAI_API_KEY", "") or "").strip())
        gemini_key = bool((os.environ.get("GEMINI_API_KEY", "") or "").strip())
        ollama_api_key = bool((os.environ.get("OLLAMA_API_KEY", "") or "").strip())
        statuses["anthropic"] = "key configured" if anth_key else "missing API key"
        statuses["openai"] = "key configured" if openai_key else "missing API key"
        statuses["gemini"] = "key configured" if gemini_key else "missing API key"
        statuses["ollama_api"] = "key configured" if ollama_api_key else "missing API key"

        ok_ollama, detail_ollama = self._probe_json("http://127.0.0.1:11434/api/tags")
        statuses["ollama_local"] = detail_ollama if ok_ollama else f"offline ({detail_ollama})"

        lmstudio_base = (os.environ.get("GUPPY_LMSTUDIO_BASE_URL", _DEFAULT_LMSTUDIO_BASE_URL) or _DEFAULT_LMSTUDIO_BASE_URL).rstrip("/")
        ok_lms, detail_lms = self._probe_json(f"{lmstudio_base}/models")
        statuses["lmstudio_local"] = detail_lms if ok_lms else f"offline ({detail_lms})"

        lemonade_base = self._lemonade_base_url.rstrip("/")
        ok_lem, detail_lem = self._probe_json(f"{lemonade_base}/models")
        statuses["lemonade_local"] = detail_lem if ok_lem else f"offline ({detail_lem})"

        harness_base = (os.environ.get("GUPPY_LOCAL_HARNESS_BASE_URL", _DEFAULT_LOCAL_HARNESS_BASE_URL) or _DEFAULT_LOCAL_HARNESS_BASE_URL).rstrip("/")
        ok_harness, detail_harness = self._probe_json(f"{harness_base}/health")
        statuses["local_harness"] = detail_harness if ok_harness else f"offline ({detail_harness})"

        self.finished.emit(statuses)


class OllamaModelOpThread(QThread):
    finished = Signal(dict)

    def __init__(self, operation: str, model_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._operation = (operation or "pull").strip().lower()
        self._model_name = (model_name or "").strip()

    def run(self) -> None:
        if not self._model_name:
            self.finished.emit({"ok": False, "summary": "model name is required"})
            return
        if shutil.which("ollama") is None:
            self.finished.emit({"ok": False, "summary": "ollama CLI was not found in PATH"})
            return
        verb = "pull" if self._operation == "pull" else "rm"
        try:
            result = subprocess.run(
                ["ollama", verb, self._model_name],
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
            ok = result.returncode == 0
            summary = (result.stdout or result.stderr or "").strip()
            if len(summary) > 260:
                summary = summary[:260] + "..."
            if not summary:
                summary = "completed"
            self.finished.emit({"ok": ok, "summary": summary})
        except Exception as exc:
            self.finished.emit({"ok": False, "summary": str(exc)})
