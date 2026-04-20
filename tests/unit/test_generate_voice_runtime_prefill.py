from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "guppy_voice_runtime_prefill",
        ROOT / "tools" / "generate_voice_runtime_prefill.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_matrix_summary_counts_scenarios_and_pending(tmp_path: Path) -> None:
    module = _load_module()
    matrix = tmp_path / "MATRIX.md"
    matrix.write_text(
        "\n".join(
            [
                "| ID | Description | Pass/Fail | Notes | Tester | Date |",
                "|---|---|---|---|---|---|",
                "| PTT-01 | Basic flow | — | — | — | — |",
                "| PTT-02 | Another flow | PASS | works | ryan | 2026-04-19 |",
                "| RT-01 | Runtime flow | - | - | - | - |",
            ]
        ),
        encoding="utf-8",
    )

    summary = module._matrix_summary(matrix)

    assert summary["exists"] is True
    assert summary["scenario_count"] == 3
    assert summary["pending_count"] == 2


def test_prefill_markdown_includes_scope_and_follow_up() -> None:
    module = _load_module()
    md = module._prefill_markdown(
        ts_utc="2026-04-19T00:00:00+00:00",
        machine={
            "hostname": "testbox",
            "os": "Windows 11",
            "platform": "Windows-11-10.0.26100-SP0",
            "python": "3.12.3",
            "python_executable": "C:/Users/Ryan/Guppy/.venv/Scripts/python.exe",
            "branch": "main",
        },
        audio={
            "available": True,
            "device_count": 7,
            "default_input_index": 1,
            "default_output_index": 4,
            "default_input_name": "Mic A",
            "default_output_name": "Speaker B",
            "error": "",
        },
        provider_snapshot={
            "libraries": {"openai": "1.0.0"},
            "smoke_results": {"openrouter": {"ok": True}},
        },
        ollama_snapshot={
            "missing_models": [],
            "ping_results": {"guppy-code:latest": {"ok": True}},
        },
        voice_matrix={"exists": True, "scenario_count": 10, "pending_count": 9},
        runtime_matrix={"exists": True, "scenario_count": 6, "pending_count": 6},
    )

    assert "Voice + Runtime Matrix Prefill Report" in md
    assert "does not mark manual pass/fail rows as complete" in md
    assert "testbox" in md
    assert "Provider Runtime Snapshot | READY" in md
    assert "Ollama Runtime Snapshot | READY" in md
    assert "Manual Follow-Up Still Required" in md