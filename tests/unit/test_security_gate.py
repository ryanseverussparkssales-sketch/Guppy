"""Unit tests for the explicit Guppy security gate.

Tests verify:
- run_security_gate() returns the expected dict shape
- format_gate_report() returns a non-empty string
- build_posture check passes on a clean (secret-free) runtime directory
- network_boundary check is non-blocking across environments
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.guppy.launcher_application import security_gate
from src.guppy.launcher_application.security_gate import (
    run_security_gate,
    format_gate_report,
    SECURITY_GATE_CHECKS,
    _check_build_posture,
    _check_network_boundary,
    _check_secret_storage,
)


# ── run_security_gate() shape ─────────────────────────────────────────────────

class TestRunSecurityGateShape:
    def test_run_security_gate_returns_dict(self):
        """Spec-named: gate result is a dict with passed/failed/warnings/launch_ready."""
        result = run_security_gate()
        assert isinstance(result, dict)
        for key in ("passed", "failed", "warnings", "launch_ready"):
            assert key in result

    def test_returns_dict_with_required_keys(self):
        result = run_security_gate()
        assert isinstance(result, dict)
        assert "passed" in result
        assert "failed" in result
        assert "warnings" in result
        assert "launch_ready" in result

    def test_passed_and_failed_are_lists(self):
        result = run_security_gate()
        assert isinstance(result["passed"], list)
        assert isinstance(result["failed"], list)

    def test_launch_ready_is_bool(self):
        result = run_security_gate()
        assert isinstance(result["launch_ready"], bool)

    def test_launch_ready_reflects_failed_list(self):
        result = run_security_gate()
        expected = len(result["failed"]) == 0
        assert result["launch_ready"] == expected

    def test_all_check_names_appear_in_result(self):
        result = run_security_gate()
        all_names = {n for n, _ in result["passed"]} | {n for n, _ in result["failed"]}
        for check in SECURITY_GATE_CHECKS:
            assert check.name in all_names, f"Check {check.name!r} missing from gate result"


# ── format_gate_report() ──────────────────────────────────────────────────────

class TestFormatGateReport:
    def test_format_gate_report_returns_string(self):
        """Spec-named: format_gate_report() returns a non-empty string."""
        report = format_gate_report()
        assert isinstance(report, str)
        assert len(report) > 0

    def test_returns_non_empty_string(self):
        report = format_gate_report()
        assert isinstance(report, str)
        assert len(report) > 0

    def test_contains_header(self):
        report = format_gate_report()
        assert "Security Gate Report" in report

    def test_accepts_pre_computed_result(self):
        result = run_security_gate()
        report = format_gate_report(result)
        assert isinstance(report, str)
        assert len(report) > 0

    def test_launch_ready_reflected_in_report(self):
        # Force a fully-passing result
        result = {"passed": [("x", "ok")], "failed": [], "warnings": [], "launch_ready": True}
        report = format_gate_report(result)
        assert "YES" in report

    def test_failed_checks_show_fail_marker(self):
        result = {"passed": [], "failed": [("bad_check", "reason")], "warnings": [], "launch_ready": False}
        report = format_gate_report(result)
        assert "[FAIL]" in report
        assert "bad_check" in report


# ── build_posture check ───────────────────────────────────────────────────────

class TestBuildPostureCheck:
    def test_passes_when_runtime_dir_absent(self, tmp_path):
        absent = tmp_path / "nonexistent_runtime"
        with patch.object(security_gate, "_RUNTIME", absent):
            ok, detail = _check_build_posture()
        assert ok is True
        assert "not exist" in detail or "No plaintext" in detail

    def test_build_posture_check_passes_on_clean_runtime(self, tmp_path):
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        (runtime / "hub.lock").write_text("{}", encoding="utf-8")
        (runtime / "launcher.lock").write_text("{}", encoding="utf-8")
        with patch.object(security_gate, "_RUNTIME", runtime):
            ok, detail = _check_build_posture()
        assert ok is True
        assert "No plaintext" in detail

    def test_fails_when_env_file_present(self, tmp_path):
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        (runtime / ".env").write_text("SECRET=oops", encoding="utf-8")
        with patch.object(security_gate, "_RUNTIME", runtime):
            ok, detail = _check_build_posture()
        assert ok is False
        assert ".env" in detail

    def test_fails_when_pem_file_present(self, tmp_path):
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        (runtime / "server.pem").write_text("-----BEGIN CERTIFICATE-----", encoding="utf-8")
        with patch.object(security_gate, "_RUNTIME", runtime):
            ok, detail = _check_build_posture()
        assert ok is False


# ── network_boundary check is non-blocking ────────────────────────────────────

class TestSecretStorageCheck:
    def test_secret_storage_check_flags_degraded_backend(self):
        with patch.object(security_gate.secret_store, "_KEYRING_AVAILABLE", False), patch.object(
            security_gate.secret_store,
            "_KEYRING_BACKEND_NAME",
            "PlaintextKeyring",
        ):
            ok, detail = _check_secret_storage()
        assert ok is False
        assert "degraded backend" in detail


class TestNetworkBoundaryNonBlocking:
    def test_network_boundary_check_is_non_blocking(self, tmp_path):
        """Spec-named test: verifies the check doesn't raise on any environment."""
        absent_root = tmp_path / "totally_empty"
        absent_root.mkdir()
        with patch.object(security_gate, "_ROOT", absent_root):
            try:
                ok, detail = _check_network_boundary()
            except Exception as exc:
                pytest.fail(f"_check_network_boundary raised: {exc}")
        assert isinstance(ok, bool)
        assert isinstance(detail, str)

    def test_does_not_raise_when_file_missing(self, tmp_path):
        absent_root = tmp_path / "fake_root"
        absent_root.mkdir()
        with patch.object(security_gate, "_ROOT", absent_root):
            try:
                ok, detail = _check_network_boundary()
            except Exception as exc:
                pytest.fail(f"_check_network_boundary raised: {exc}")
        assert isinstance(ok, bool)
        assert isinstance(detail, str)

    def test_returns_false_with_detail_on_missing_file(self, tmp_path):
        with patch.object(security_gate, "_ROOT", tmp_path):
            ok, detail = _check_network_boundary()
        assert ok is False
        assert len(detail) > 0

    def test_passes_on_server_with_localhost_bind(self, tmp_path):
        api_dir = tmp_path / "src" / "guppy" / "api"
        api_dir.mkdir(parents=True)
        srv = api_dir / "server_runtime.py"
        srv.write_text('HOST = "127.0.0.1"\nPORT = 8081\n', encoding="utf-8")
        with patch.object(security_gate, "_ROOT", tmp_path):
            ok, detail = _check_network_boundary()
        assert ok is True
        assert "127.0.0.1" in detail

    def test_fails_on_server_with_open_bind(self, tmp_path):
        api_dir = tmp_path / "src" / "guppy" / "api"
        api_dir.mkdir(parents=True)
        srv = api_dir / "server_runtime.py"
        srv.write_text('HOST = "0.0.0.0"\nPORT = 8081\n', encoding="utf-8")
        with patch.object(security_gate, "_ROOT", tmp_path):
            ok, detail = _check_network_boundary()
        assert ok is False
        assert "0.0.0.0" in detail
