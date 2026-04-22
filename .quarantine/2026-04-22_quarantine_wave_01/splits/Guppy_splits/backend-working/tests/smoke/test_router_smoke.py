from __future__ import annotations

import inspect
from pathlib import Path


def test_router_imports_and_instantiates() -> None:
    from src.guppy.inference.router import get_router

    router = get_router()
    assert router is not None
    assert hasattr(router, "anthropic_available")
    assert hasattr(router, "HAIKU_TIMEOUT_SMART")


def test_router_required_methods_exist() -> None:
    from src.guppy.inference.router import get_router

    router = get_router()
    for method in (
        "query_smart",
        "_classify_task",
        "query_haiku",
        "query_sonnet",
        "query_local",
    ):
        assert hasattr(router, method), f"Missing router method: {method}"


def test_router_classifier_cases() -> None:
    from src.guppy.inference.router import get_router

    router = get_router()
    cases = [
        ("What time is it?", "simple"),
        ("Build a REST API", "complex"),
        ("Explain machine learning", "teaching"),
        ("Remind me to call John", "simple"),
        ("Debug this memory leak", "complex"),
        ("Help me understand OAuth", "teaching"),
    ]
    for text, expected in cases:
        assert router._classify_task(text) == expected


def test_query_smart_signature() -> None:
    from src.guppy.inference.router import get_router

    router = get_router()
    params = list(inspect.signature(router.query_smart).parameters.keys())
    for expected in ("system_prompt", "user_text", "tools", "messages"):
        assert expected in params


def test_merlin_core_smoke_imports() -> None:
    from src.guppy.merlin.core import MERLIN_SYSTEM

    assert "Socratic" in MERLIN_SYSTEM


def test_docs_smoke_contracts() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    roadmap = (repo_root / "ROADMAP.md").read_text(encoding="utf-8")
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "discoverability pointer" in roadmap
    assert "Do not add active priorities" in roadmap
    assert "Guppy" in readme
