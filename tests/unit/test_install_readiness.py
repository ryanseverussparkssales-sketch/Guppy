"""Unit tests for PL-C5 readiness tracks.

Tests are designed to pass in CI regardless of whether Ollama is installed
or the Guppy runtime is running.
"""

from __future__ import annotations

import shutil

import pytest

import src.guppy.launcher_application.local_model_readiness as local_model_readiness_module
from src.guppy.launcher_application.install_readiness import (
    INSTALL_READINESS_CHECKS,
    InstallReadinessCheck,
    run_install_readiness,
)
from src.guppy.launcher_application.local_model_readiness import (
    LOCAL_MODEL_CHECKS,
    LocalModelCheck,
    run_local_model_readiness,
)


# ---------------------------------------------------------------------------
# Track 1 — Desktop Install
# ---------------------------------------------------------------------------


def test_run_install_readiness_returns_dict() -> None:
    result = run_install_readiness()
    assert isinstance(result, dict)
    assert "passed" in result
    assert "failed" in result
    assert "summary" in result
    assert isinstance(result["passed"], list)
    assert isinstance(result["failed"], list)
    assert isinstance(result["summary"], str)


def test_install_readiness_check_names_are_unique() -> None:
    names = [c.name for c in INSTALL_READINESS_CHECKS]
    assert len(names) == len(set(names)), "Duplicate check names in INSTALL_READINESS_CHECKS"


def test_install_readiness_passed_plus_failed_equals_total() -> None:
    result = run_install_readiness()
    total = len(INSTALL_READINESS_CHECKS)
    assert len(result["passed"]) + len(result["failed"]) == total  # type: ignore[arg-type]


def test_install_readiness_no_raise() -> None:
    """run_install_readiness must never raise — checks catch all exceptions internally."""
    run_install_readiness()  # if it raises, test fails


# ---------------------------------------------------------------------------
# Track 2 — Local Base Model
# ---------------------------------------------------------------------------


def test_run_local_model_readiness_returns_dict() -> None:
    result = run_local_model_readiness()
    assert isinstance(result, dict)
    assert "passed" in result
    assert "failed" in result
    assert "optional_absent" in result
    assert "summary" in result
    assert isinstance(result["passed"], list)
    assert isinstance(result["failed"], list)
    assert isinstance(result["optional_absent"], list)
    assert isinstance(result["summary"], str)


def test_local_model_readiness_check_names_are_unique() -> None:
    names = [c.name for c in LOCAL_MODEL_CHECKS]
    assert len(names) == len(set(names)), "Duplicate check names in LOCAL_MODEL_CHECKS"


def test_local_model_readiness_counts_add_up() -> None:
    result = run_local_model_readiness()
    check_count = (
        len(result["passed"])  # type: ignore[arg-type]
        + len(result["optional_absent"])  # type: ignore[arg-type]
    )
    assert check_count == len(LOCAL_MODEL_CHECKS)
    synthetic_failures = set(result["failed"]) - {check.name for check in LOCAL_MODEL_CHECKS}  # type: ignore[arg-type]
    assert synthetic_failures <= {"ready_local_runtime"}


def test_local_model_readiness_no_raise_on_missing_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch shutil.which to return None; run must not raise."""
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    result = run_local_model_readiness()
    assert isinstance(result, dict)
    # ollama_cli must be in failed (required) or optional_absent, never in passed
    assert "ollama_cli" not in result["passed"]


def test_local_model_readiness_no_raise() -> None:
    """run_local_model_readiness must never raise regardless of environment."""
    run_local_model_readiness()  # if it raises, test fails


def test_local_model_readiness_passes_when_lmstudio_is_the_ready_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        local_model_readiness_module,
        "LOCAL_MODEL_CHECKS",
        [
            LocalModelCheck("ollama_cli", "Ollama CLI", False, lambda: False),
            LocalModelCheck("ollama_daemon", "Ollama daemon", False, lambda: False),
            LocalModelCheck("ollama_model_pulled", "Ollama model", False, lambda: False),
            LocalModelCheck("lemonade_cli", "Lemonade CLI", True, lambda: False),
            LocalModelCheck("lemonade_runtime", "Lemonade runtime", True, lambda: False),
            LocalModelCheck("lmstudio_runtime", "LM Studio runtime", True, lambda: True),
            LocalModelCheck("local_harness_runtime", "Local harness", True, lambda: False),
            LocalModelCheck("runtime_hub_alive", "Runtime hub", True, lambda: False),
        ],
    )
    monkeypatch.setattr(local_model_readiness_module, "_declared_local_runtime_ids", lambda: ["lmstudio_local"])

    result = run_local_model_readiness()

    assert result["failed"] == []
    assert result["ready_runtimes"] == ["lmstudio"]
    assert "ready via: lmstudio" in result["summary"]


def test_local_model_readiness_fails_when_no_declared_local_route_is_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        local_model_readiness_module,
        "LOCAL_MODEL_CHECKS",
        [
            LocalModelCheck("ollama_cli", "Ollama CLI", False, lambda: False),
            LocalModelCheck("ollama_daemon", "Ollama daemon", False, lambda: False),
            LocalModelCheck("ollama_model_pulled", "Ollama model", False, lambda: False),
            LocalModelCheck("lemonade_cli", "Lemonade CLI", True, lambda: False),
            LocalModelCheck("lemonade_runtime", "Lemonade runtime", True, lambda: False),
            LocalModelCheck("lmstudio_runtime", "LM Studio runtime", True, lambda: False),
            LocalModelCheck("local_harness_runtime", "Local harness", True, lambda: False),
            LocalModelCheck("runtime_hub_alive", "Runtime hub", True, lambda: False),
        ],
    )
    monkeypatch.setattr(
        local_model_readiness_module,
        "_declared_local_runtime_ids",
        lambda: ["local", "lmstudio_local", "local_harness"],
    )

    result = run_local_model_readiness()

    assert result["failed"] == ["ready_local_runtime"]
    assert result["declared_but_unavailable"] == ["ollama", "lmstudio", "local_harness"]


def test_local_model_readiness_passes_when_lemonade_is_the_declared_ready_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        local_model_readiness_module,
        "LOCAL_MODEL_CHECKS",
        [
            LocalModelCheck("ollama_cli", "Ollama CLI", False, lambda: False),
            LocalModelCheck("ollama_daemon", "Ollama daemon", False, lambda: False),
            LocalModelCheck("ollama_model_pulled", "Ollama model", False, lambda: False),
            LocalModelCheck("lemonade_cli", "Lemonade CLI", True, lambda: False),
            LocalModelCheck("lemonade_runtime", "Lemonade runtime", True, lambda: True),
            LocalModelCheck("lmstudio_runtime", "LM Studio runtime", True, lambda: False),
            LocalModelCheck("local_harness_runtime", "Local harness", True, lambda: False),
            LocalModelCheck("runtime_hub_alive", "Runtime hub", True, lambda: False),
        ],
    )
    monkeypatch.setattr(local_model_readiness_module, "_declared_local_runtime_ids", lambda: ["lemonade_local"])

    result = run_local_model_readiness()

    assert result["failed"] == []
    assert result["ready_runtimes"] == ["lemonade"]
    assert "ready via: lemonade" in result["summary"]
