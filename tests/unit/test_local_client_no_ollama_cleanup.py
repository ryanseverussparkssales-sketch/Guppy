import asyncio
import urllib.error

import pytest

from src.guppy.inference import local_client
from src.guppy.inference.provider_registry import ProviderRegistry


def _reset_local_client_state() -> None:
    local_client._auto_cache["backend"] = None
    local_client._auto_cache["expires_at"] = 0.0
    local_client._probe_cache.clear()
    local_client._models_cache.clear()
    local_client._circuit_breakers.clear()


def test_auto_probe_falls_back_to_registered_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_local_client_state()
    monkeypatch.setenv("GUPPY_LOCAL_RUNTIME_BACKEND", "auto")
    probed_urls: list[str] = []

    def fail_urlopen(req, timeout=None):  # type: ignore[no-untyped-def]
        probed_urls.append(req.full_url)
        raise urllib.error.URLError("down")

    monkeypatch.setattr(local_client.urllib.request, "urlopen", fail_urlopen)

    backend = local_client.active_backend()

    assert backend == local_client._DEFAULT_BACKEND
    assert backend in local_client._BACKENDS
    assert all(name in local_client._BACKENDS for name in local_client._AUTO_PROBE_ORDER)
    assert probed_urls
    assert all("11434" not in url for url in probed_urls)


@pytest.mark.parametrize("configured_backend", ["ollama", "lmstudio", "missing"])
def test_removed_or_unknown_backend_config_uses_registered_default(
    monkeypatch: pytest.MonkeyPatch,
    configured_backend: str,
) -> None:
    _reset_local_client_state()
    monkeypatch.setenv("GUPPY_LOCAL_RUNTIME_BACKEND", configured_backend)

    backend = local_client.active_backend()

    assert backend == local_client._DEFAULT_BACKEND
    assert backend in local_client._BACKENDS


@pytest.mark.parametrize("backend", ["ollama", "lmstudio"])
def test_explicit_removed_backend_chat_does_not_keyerror(
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
) -> None:
    _reset_local_client_state()

    def fail_urlopen(req, timeout=None):  # type: ignore[no-untyped-def]
        raise urllib.error.URLError("down")

    monkeypatch.setattr(local_client.urllib.request, "urlopen", fail_urlopen)

    result = local_client.local_chat(
        "guppy",
        [{"role": "user", "content": "hi"}],
        backend=backend,
        max_retries=0,
        timeout=1,
    )

    assert result is None


def test_provider_registry_local_provider_uses_registered_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _reset_local_client_state()
    monkeypatch.setenv("GUPPY_LOCAL_RUNTIME_BACKEND", "ollama")

    registry = ProviderRegistry(settings_db=tmp_path / "providers.sqlite3")
    client = asyncio.run(registry.get_client("local"))

    assert client is not None
    assert client.backend == local_client._DEFAULT_BACKEND
    assert client.backend in local_client._BACKENDS
    assert client.backend != "ollama"
