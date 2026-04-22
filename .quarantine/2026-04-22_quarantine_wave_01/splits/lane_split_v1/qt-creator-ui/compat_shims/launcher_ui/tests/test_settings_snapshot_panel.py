from __future__ import annotations

from pathlib import Path

from ui.launcher.views import settings_snapshot_panel as panel


class _Label:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self._style = ""

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def setStyleSheet(self, style: str) -> None:
        self._style = style

    def styleSheet(self) -> str:
        return self._style


class _Owner:
    def __init__(self) -> None:
        self._windows_ops = {
            "runtime": "Local AI Runtime: local ai runtime: ollama | live backend: ollama | status: ready",
        }
        self._recovery_status = _Label()
        self._last_recovery_lbl = _Label()
        self._health_lbl = _Label()
        self._voice_lbl = _Label()
        self._route_health_lbl = _Label()
        self._resource_lbl = _Label()
        self._windows_install_lbl = _Label()
        self._windows_runtime_lbl = _Label()
        self._windows_paths_lbl = _Label()
        self._windows_repair_lbl = _Label()
        self._windows_update_lbl = _Label()
        self._windows_diagnostics_lbl = _Label()
        self._windows_entry_lbl = _Label()
        self._windows_next_lbl = _Label()
        self._windows_service_lbl = _Label()
        self._windows_change_lbl = _Label()
        self._windows_gate_lbl = _Label()
        self._windows_gate_fix_lbl = _Label()
        self._windows_handoff_lbl = _Label()
        self._automation_workspace_lbl = _Label()
        self._automation_queue_lbl = _Label()
        self._automation_staged_lbl = _Label()
        self._automation_result_lbl = _Label()
        self._automation_approval_lbl = _Label()
        self._automation_report_lbl = _Label()
        self._automation_evidence_lbl = _Label()
        self._automation_stress_lbl = _Label()
        self._automation_recent_lbl = _Label()
        self._automation_validation_lbl = _Label()
        self._automation_status_lbl = _Label("keep current status")

    def _configured_local_runtime_backend(self) -> str:
        return "ollama"


def test_refresh_windows_ops_snapshot_preserves_existing_runtime_line(monkeypatch) -> None:
    owner = _Owner()

    monkeypatch.setattr(
        panel,
        "presenter_build_windows_ops_snapshot",
        lambda root, *, configured_backend, launcher_python: {
            "install": "Ollama CLI: found | Packager: ready",
            "runtime": "",
            "next": "Next step: ready",
        },
    )

    panel.refresh_windows_ops_snapshot(owner, root=Path("."))

    assert owner._windows_ops["runtime"].endswith("status: ready")
    assert "connected and ready" in owner._windows_runtime_lbl.text().lower()
    assert "ollama" in owner._windows_install_lbl.text().lower()


def test_apply_status_snapshot_updates_system_labels_and_runtime_surface(monkeypatch) -> None:
    owner = _Owner()

    monkeypatch.setattr(
        panel,
        "presenter_build_windows_ops_snapshot",
        lambda root, *, configured_backend, launcher_python: {
            "install": "Ollama CLI: found | Supervisor script: ready",
            "runtime": "",
            "next": "Next step: unavailable",
        },
    )

    panel.apply_status_snapshot(
        owner,
        {
            "status": "healthy",
            "startup_readiness": {"overall": "GO"},
            "voice_tts_backend": "edge",
            "voice_stt_backend": "whisper",
            "resource_envelope": {"state": "ok", "message": "headroom stable"},
        },
        root=Path("."),
    )

    assert "API health: HEALTHY" in owner._health_lbl.text()
    assert "tts=edge" in owner._voice_lbl.text()
    assert "headroom stable" in owner._resource_lbl.text()
    assert "Why the next route was chosen:" in owner._route_health_lbl.text()
    assert "local ai health:" in owner._windows_runtime_lbl.text().lower()


def test_apply_automation_snapshot_keeps_existing_status_when_payload_has_no_status() -> None:
    owner = _Owner()

    panel.apply_automation_snapshot(
        owner,
        {
            "workspace": "Workspace step: active=builder-collab | preferred=builder-collab",
            "evidence_pack_path": "runtime/user_test_evidence.md",
            "status": "",
        },
    )

    assert owner._automation_workspace_lbl.text() == "Workspace step: active=builder-collab | preferred=builder-collab"
    assert owner._automation_evidence_lbl.text() == "Evidence pack: runtime/user_test_evidence.md"
    assert owner._automation_status_lbl.text() == "keep current status"
