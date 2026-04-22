from __future__ import annotations

from src.guppy.workspace_governance import machine_auth


class _FakeSecretStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get_secret(self, key: str, fallback: str = "") -> str:
        return self.values.get(key, fallback)

    def set_secret(self, key: str, value: str) -> bool:
        self.values[key] = value
        return True

    def delete_secret(self, key: str) -> bool:
        return self.values.pop(key, None) is not None


def test_keyring_key_uses_connector_prefix() -> None:
    assert machine_auth.keyring_key("YOUTUBE_API_KEY") == "connector_secret:YOUTUBE_API_KEY"


def test_read_machine_secret_prefers_keyring_then_env(monkeypatch) -> None:
    store = _FakeSecretStore()
    store.values[machine_auth.keyring_key("CRM_TOKEN")] = "keyring-value"
    monkeypatch.setattr(machine_auth, "_SECRET_STORE_AVAILABLE", True)
    monkeypatch.setattr(machine_auth, "_secret_store", store)
    monkeypatch.setenv("CRM_TOKEN", "env-value")

    assert machine_auth.read_machine_secret("CRM_TOKEN") == "keyring-value"
    assert machine_auth.secret_source("CRM_TOKEN") == "mixed"


def test_read_machine_secret_falls_back_to_env_when_backend_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(machine_auth, "_SECRET_STORE_AVAILABLE", False)
    monkeypatch.setattr(machine_auth, "_secret_store", None)
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "env-client-id")

    assert machine_auth.read_machine_secret("SPOTIFY_CLIENT_ID") == "env-client-id"
    assert machine_auth.secret_source("SPOTIFY_CLIENT_ID") == "env"


def test_write_and_clear_machine_secret_use_secret_store(monkeypatch) -> None:
    store = _FakeSecretStore()
    monkeypatch.setattr(machine_auth, "_SECRET_STORE_AVAILABLE", True)
    monkeypatch.setattr(machine_auth, "_secret_store", store)

    assert machine_auth.write_machine_secret("TWILIO_AUTH_TOKEN", "super-secret") is True
    assert store.values[machine_auth.keyring_key("TWILIO_AUTH_TOKEN")] == "super-secret"
    assert machine_auth.clear_machine_secret("TWILIO_AUTH_TOKEN") is True
    assert machine_auth.read_machine_secret("TWILIO_AUTH_TOKEN") == ""


def test_merge_secret_sources_and_secret_status_cover_ready_partial_and_missing(monkeypatch) -> None:
    store = _FakeSecretStore()
    monkeypatch.setattr(machine_auth, "_SECRET_STORE_AVAILABLE", True)
    monkeypatch.setattr(machine_auth, "_secret_store", store)
    monkeypatch.setenv("FIELD_ENV", "present")
    store.values[machine_auth.keyring_key("FIELD_KEYRING")] = "present"

    ready = machine_auth.secret_status(["FIELD_ENV", "FIELD_KEYRING"])
    partial = machine_auth.secret_status(["FIELD_ENV", "FIELD_MISSING"])
    missing = machine_auth.secret_status(["FIELD_MISSING"])

    assert machine_auth.merge_secret_sources(["env", "", "keyring"]) == "mixed"
    assert ready["auth_state"] == "ready"
    assert ready["storage_posture"] == "mixed_env"
    assert "keyring-first storage" in str(ready["storage_warning"]).lower()
    assert "degraded environment fallback" in str(ready["storage_warning"]).lower()
    assert partial["auth_state"] == "partial"
    assert partial["field_sources"]["FIELD_ENV"] == "env"
    assert partial["field_sources"]["FIELD_MISSING"] == "none"
    assert partial["storage_posture"] == "env_only"
    assert "degraded environment fallback" in str(partial["storage_warning"]).lower()
    assert missing["auth_state"] == "missing"
    assert missing["storage_posture"] == "none"
