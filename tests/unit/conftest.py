"""Unit test configuration.

- Forces mock-local AI backend so no unit test reaches a live provider.
- Clears auth env vars so tests that don't supply tokens aren't blocked by
  leaked secrets from adjacent test files.

Tests that specifically validate auth (test_wave2_auth.py) temporarily
re-set these vars inside their own ``patch.dict`` context managers.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _unit_test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate unit tests from the live environment."""
    # Auth secrets: cleared so verify_token / verify_turnstile bypass by default.
    # Tests that specifically validate auth re-set these vars inside patch.dict() context managers.
    monkeypatch.delenv("GUPPY_JWT_SECRET", raising=False)
    monkeypatch.delenv("GUPPY_TURNSTILE_SECRET", raising=False)

    # Note: Voice module tests (test_stt_providers.py, etc.) do not need API backend patching.
    # Only auth-specific tests (test_wave2_auth.py) require patching api.routes.chat.
    # To keep this fixture lightweight, skip API patching here.
    # If future tests need API mocking, use @patch() decorator directly on those test functions.

    yield
