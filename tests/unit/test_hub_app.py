from __future__ import annotations

from src.guppy.apps import hub_app as compat_hub_app
from src.guppy.hub import app as canonical_hub_app
from src.guppy.launcher_application.launcher_api_runtime_control import probe_api_runtime_label


def test_hub_app_shim_aligns_canonical_api_status_probe() -> None:
    assert compat_hub_app.main is canonical_hub_app.main
    assert canonical_hub_app.check_api_server is probe_api_runtime_label
