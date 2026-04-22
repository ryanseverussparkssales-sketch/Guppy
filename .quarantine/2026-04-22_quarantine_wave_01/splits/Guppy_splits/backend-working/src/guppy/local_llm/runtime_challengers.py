from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.guppy.local_llm.manifest import load_local_llm_manifest

WhichFn = Callable[[str], str | None]


@dataclass(frozen=True)
class HostRuntimeFacts:
    platform_system: str
    gpu_names: tuple[str, ...]
    total_memory_bytes: int | None = None

    @property
    def is_windows(self) -> bool:
        return self.platform_system.lower().startswith("win")

    @property
    def is_linux(self) -> bool:
        return self.platform_system.lower().startswith("linux")

    @property
    def has_amd_gpu(self) -> bool:
        return any("amd" in name.lower() or "radeon" in name.lower() for name in self.gpu_names)

    @property
    def has_high_end_amd_gpu(self) -> bool:
        hot_words = ("7900", "w7900", "gfx110", "rdna3", "7900 xtx", "7900 xt", "7800 xt")
        return any(any(word in name.lower() for word in hot_words) for name in self.gpu_names)


def get_runtime_challenger_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    runtime = manifest.get("runtime") or {}
    entries = runtime.get("runtime_challengers") or []
    return [entry for entry in entries if isinstance(entry, dict)]


def _candidate_command_names(runtime_id: str) -> tuple[str, ...]:
    runtime_id = str(runtime_id or "").strip().lower()
    if runtime_id == "llama.cpp":
        return ("llama-server", "llama-cli")
    if runtime_id == "lemonade":
        return ("lemonade", "lemond")
    if runtime_id == "vllm-rocm":
        return ("vllm",)
    return ()


def _integration_surface_state(runtime_id: str) -> dict[str, Any]:
    normalized = str(runtime_id or "").strip().lower()
    if normalized == "lemonade":
        return {
            "integration_surface": "external_openai_compatible_runtime",
            "integration_contract": "Use the configured base URL plus /models and /chat/completions. No repo-local vendor clone is required.",
        }
    if normalized == "llama.cpp":
        return {
            "integration_surface": "external_binary_runtime",
            "integration_contract": "Use installed llama.cpp binaries and benchmark harnesses. No repo-local vendor clone is required.",
        }
    if normalized == "vllm-rocm":
        return {
            "integration_surface": "external_service_runtime",
            "integration_contract": "Treat as an external serving stack when this research lane is activated.",
        }
    return {
        "integration_surface": "unknown",
        "integration_contract": "No integration contract is defined for this runtime yet.",
    }


def _host_fit(runtime_id: str, host: HostRuntimeFacts) -> tuple[str, str]:
    runtime_id = str(runtime_id or "").strip().lower()
    if runtime_id == "llama.cpp":
        if host.is_windows or host.is_linux:
            if host.has_amd_gpu:
                return (
                    "strong",
                    "Direct low-level challenger with a credible Windows/Linux AMD path on this host.",
                )
            return ("possible", "Direct challenger is usable, but this host fit is less specialized.")
        return ("unsupported", "Direct llama.cpp benchmarking is not a current target on this host OS.")
    if runtime_id == "lemonade":
        if host.is_windows and host.has_high_end_amd_gpu:
            return (
                "strong",
                "Best product-fit runtime challenger here: Windows support, AMD-friendly path, and API compatibility.",
            )
        if (host.is_windows or host.is_linux) and host.has_amd_gpu:
            return ("strong", "Promising runtime challenger with explicit AMD-oriented positioning.")
        if host.is_windows or host.is_linux:
            return ("possible", "Server looks installable, but this host is less aligned with its strongest path.")
        return ("unsupported", "Lemonade is not a realistic first challenger on this host OS.")
    if runtime_id == "vllm-rocm":
        if host.is_linux and host.has_amd_gpu:
            return ("research", "Research-only ROCm serving candidate for a future Linux host.")
        if host.is_windows:
            return ("research", "Research-only candidate; Windows host keeps this out of the near-term path.")
        return ("unsupported", "Research-only candidate outside the current host envelope.")
    return ("unknown", "No host-fit policy is defined for this runtime challenger yet.")


def _binary_state(runtime_id: str, which_fn: WhichFn) -> dict[str, Any]:
    command_names = _candidate_command_names(runtime_id)
    discovered = []
    for command_name in command_names:
        resolved = which_fn(command_name)
        discovered.append(
            {
                "command": command_name,
                "present": bool(resolved),
                "path": str(resolved or ""),
            }
        )
    installed = any(item["present"] for item in discovered)
    return {
        "command_names": list(command_names),
        "installed": installed,
        "discovered_commands": discovered,
    }


def _benchmark_priority(runtime_id: str) -> int:
    order = {
        "llama.cpp": 10,
        "lemonade": 20,
        "vllm-rocm": 90,
    }
    return order.get(str(runtime_id or "").strip().lower(), 999)


def _integration_priority(runtime_id: str, host_fit: str) -> int:
    runtime_id = str(runtime_id or "").strip().lower()
    if runtime_id == "lemonade" and host_fit == "strong":
        return 10
    if runtime_id == "llama.cpp":
        return 20
    if runtime_id == "lemonade":
        return 30
    if runtime_id == "vllm-rocm":
        return 90
    return 999


def probe_runtime_challengers(
    manifest: dict[str, Any],
    host: HostRuntimeFacts,
    which_fn: WhichFn | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    del repo_root
    active_which = which_fn or shutil.which
    rows: list[dict[str, Any]] = []
    for entry in get_runtime_challenger_entries(manifest):
        runtime_id = str(entry.get("id") or "").strip()
        host_fit, host_note = _host_fit(runtime_id, host)
        binary_state = _binary_state(runtime_id, active_which)
        integration_state = _integration_surface_state(runtime_id)
        rows.append(
            {
                "id": runtime_id,
                "status": str(entry.get("status") or ""),
                "priority": str(entry.get("priority") or ""),
                "notes": str(entry.get("notes") or ""),
                "host_fit": host_fit,
                "host_note": host_note,
                "benchmark_priority": _benchmark_priority(runtime_id),
                "integration_priority": _integration_priority(runtime_id, host_fit),
                **binary_state,
                **integration_state,
            }
        )

    benchmark_candidates = [
        row for row in rows if row["host_fit"] in {"strong", "possible"} and row["id"] != "vllm-rocm"
    ]
    integration_candidates = [row for row in rows if row["host_fit"] == "strong" and row["id"] != "vllm-rocm"]
    research_candidates = [row for row in rows if row["host_fit"] == "research"]

    benchmark_first = min(benchmark_candidates, key=lambda row: row["benchmark_priority"], default=None)
    integration_first = min(integration_candidates, key=lambda row: row["integration_priority"], default=None)
    research_track = min(research_candidates, key=lambda row: row["benchmark_priority"], default=None)

    return {
        "host": {
            "platform_system": host.platform_system,
            "gpu_names": list(host.gpu_names),
            "total_memory_bytes": host.total_memory_bytes,
            "has_amd_gpu": host.has_amd_gpu,
            "has_high_end_amd_gpu": host.has_high_end_amd_gpu,
        },
        "challengers": rows,
        "recommended_next": {
            "benchmark_first": benchmark_first["id"] if benchmark_first else "",
            "integration_first": integration_first["id"] if integration_first else "",
            "research_track": research_track["id"] if research_track else "",
        },
    }


def default_host_runtime_facts() -> HostRuntimeFacts:
    return HostRuntimeFacts(platform_system=platform.system(), gpu_names=tuple())


def load_manifest_runtime_probe(
    manifest_path: str | Path,
    host: HostRuntimeFacts,
    which_fn: WhichFn | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    manifest = load_local_llm_manifest(manifest_path)
    return probe_runtime_challengers(manifest, host=host, which_fn=which_fn, repo_root=repo_root)
