"""Unit test configuration.

- Forces mock-local AI backend so no unit test reaches a live provider.
- Clears auth env vars so tests that don't supply tokens aren't blocked by
  leaked secrets from adjacent test files.

Tests that specifically validate auth (test_wave2_auth.py) temporarily
re-set these vars inside their own ``patch.dict`` context managers.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _unit_test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate unit tests from the live environment."""
    # Never call a live AI provider.
    with patch("api.routes.chat._select_backend", return_value="mock-local"):
        # Auth secrets: cleared so verify_token / verify_turnstile bypass by
        # default.  wave2_auth tests override these with patch.dict().
        monkeypatch.delenv("GUPPY_JWT_SECRET", raising=False)
        monkeypatch.delenv("GUPPY_TURNSTILE_SECRET", raising=False)
        yield
