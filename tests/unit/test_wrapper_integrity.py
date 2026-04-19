from pathlib import Path

from tools import check_wrapper_integrity


def test_wrapper_integrity_passes() -> None:
    assert check_wrapper_integrity.main() == 0


def test_validate_wrapper_requires_single_main_call(tmp_path: Path) -> None:
    wrapper = tmp_path / "guppy_launcher.py"
    wrapper.write_text(
        "\n".join(
            [
                '"""Compatibility wrapper for launcher entrypoint."""',
                "from __future__ import annotations",
                "from src.guppy.apps.launcher_app import main",
                "",
                'if __name__ == "__main__":',
                "    raise SystemExit(main())",
                "    main()",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    errors = check_wrapper_integrity._validate_wrapper(  # pylint: disable=protected-access
        wrapper,
        "from src.guppy.apps.launcher_app import main",
    )
    assert "must call main() exactly once" in "\n".join(errors)


def test_validate_shim_requires_canonical_run_module(tmp_path: Path) -> None:
    shim = tmp_path / "guppy_api.py"
    shim.write_text(
        "\n".join(
            [
                '"""Compatibility shim - canonical implementation in src.guppy.api.server."""',
                "from __future__ import annotations",
                "import importlib as _il, runpy as _rp, sys as _sys",
                "",
                'if __name__ == "__main__":',
                '    _rp.run_module("src.guppy.api.other", run_name="__main__", alter_sys=True)',
                "else:",
                '    _sys.modules[__name__] = _il.import_module("src.guppy.api.server")',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    errors = check_wrapper_integrity._validate_shim(shim, "src.guppy.api.server")  # pylint: disable=protected-access
    assert "missing run_module(\"src.guppy.api.server\", ...)" in "\n".join(errors)
