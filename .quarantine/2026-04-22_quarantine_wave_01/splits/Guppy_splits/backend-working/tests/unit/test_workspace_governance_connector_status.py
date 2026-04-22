from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from src.guppy.workspace_governance import (
    build_connector_guidance,
    build_connector_status,
    token_path_for_gmail_account,
)

_TEST_TEMP_ROOT = Path(".tmp/dev-workflow/unittest-temp")


@contextmanager
def _workspace_tempdir():
    _TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = _TEST_TEMP_ROOT / f"case-{uuid4().hex[:10]}"
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_token_path_for_gmail_account_normalizes_alias() -> None:
    expected = Path.home() / ".guppy_gmail_token_sales.json"
    assert token_path_for_gmail_account(" Sales ") == expected


def test_build_connector_guidance_preserves_selection_and_optional_secret_messages() -> None:
    provider_needed = build_connector_guidance(
        {
            "id": "crm",
            "label": "CRM",
            "auth_kind": "provider_secret",
            "auth_state": "missing",
            "providers": [{"id": "hubspot"}],
            "accounts": [],
            "secret_fields": ["HUBSPOT_API_KEY"],
        },
        provider="missing",
    )
    account_needed = build_connector_guidance(
        {
            "id": "gmail",
            "label": "Gmail",
            "auth_kind": "oauth_file_token",
            "auth_state": "ready",
            "providers": [],
            "accounts": [{"id": "main"}, {"id": "sales"}],
            "secret_fields": [],
        }
    )
    youtube_optional = build_connector_guidance(
        {
            "id": "youtube",
            "label": "YouTube",
            "auth_kind": "api_key",
            "auth_state": "optional",
            "providers": [],
            "accounts": [],
            "secret_fields": ["YOUTUBE_API_KEY"],
        }
    )

    assert provider_needed["result_code"] == "provider_selection_needed"
    assert "choose a CRM provider" in provider_needed["next_step"]
    assert account_needed["result_code"] == "account_selection_needed"
    assert "choose which Gmail account" in account_needed["next_step"]
    assert youtube_optional["result_code"] == "ready"
    assert "Workspaces" in youtube_optional["next_step"]


def test_build_connector_status_gmail_uses_single_account_ready_guidance() -> None:
    with _workspace_tempdir() as tmp_path:
        credentials_path = tmp_path / "gmail_credentials.json"
        credentials_path.write_text("{}", encoding="utf-8")
        (tmp_path / ".guppy_gmail_token_main.json").write_text("token", encoding="utf-8")

        with patch("src.guppy.workspace_governance.connector_status._home_path", return_value=tmp_path), patch(
            "src.guppy.workspace_governance.connector_status._gmail_accounts",
            return_value=[{"id": "main", "label": "Main inbox"}],
        ), patch.dict("os.environ", {"GMAIL_CREDENTIALS_PATH": str(credentials_path)}, clear=False):
            status = build_connector_status("gmail")

    assert status["auth_state"] == "ready"
    assert status["result_code"] == "ready"
    assert status["accounts"][0]["label"] == "Main inbox"
    assert status["accounts"][0]["endpoint_prefixes"] == ["connector://gmail/main", "connector://gmail"]
    assert "Workspaces" in status["next_step"]


def test_build_connector_status_gmail_multi_account_requires_selection_until_account_is_named() -> None:
    with _workspace_tempdir() as tmp_path:
        credentials_path = tmp_path / "gmail_credentials.json"
        credentials_path.write_text("{}", encoding="utf-8")
        (tmp_path / ".guppy_gmail_token_main.json").write_text("token", encoding="utf-8")
        (tmp_path / ".guppy_gmail_token_sales.json").write_text("token", encoding="utf-8")

        with patch("src.guppy.workspace_governance.connector_status._home_path", return_value=tmp_path), patch(
            "src.guppy.workspace_governance.connector_status._gmail_accounts",
            return_value=[{"id": "main", "label": "Main"}, {"id": "sales", "label": "Sales"}],
        ), patch.dict("os.environ", {"GMAIL_CREDENTIALS_PATH": str(credentials_path)}, clear=False):
            unselected = build_connector_status("gmail")
            selected = build_connector_status("gmail", account_id="sales")

    assert unselected["auth_state"] == "ready"
    assert unselected["result_code"] == "account_selection_needed"
    assert "choose which Gmail account" in unselected["next_step"]
    assert selected["result_code"] == "ready"
    assert "Sales" in selected["next_step"]


def test_build_connector_status_calendar_partial_oauth_uses_host_auth_incomplete_guidance() -> None:
    with _workspace_tempdir() as tmp_path:
        credentials_path = tmp_path / "google_calendar_credentials.json"
        credentials_path.write_text("{}", encoding="utf-8")

        with patch("src.guppy.workspace_governance.connector_status._home_path", return_value=tmp_path), patch.dict(
            "os.environ",
            {"GOOGLE_CALENDAR_CREDENTIALS_PATH": str(credentials_path)},
            clear=False,
        ):
            status = build_connector_status("calendar")

    assert status["auth_state"] == "partial"
    assert status["source"] == "file"
    assert status["accounts"][0]["id"] == "primary"
    assert status["result_code"] == "host_auth_incomplete"
    assert "reconnect Calendar" in status["next_step"]


def test_build_connector_status_spotify_and_youtube_preserve_readiness_shapes() -> None:
    with _workspace_tempdir() as tmp_path:
        (tmp_path / ".guppy_spotify_token").write_text("token", encoding="utf-8")

        def fake_secret(key: str, *, fallback: str | None = None) -> str:
            values = {
                "SPOTIFY_CLIENT_ID": "spotify-client-id",
                "SPOTIFY_CLIENT_SECRET": "spotify-client-secret",
                "YOUTUBE_API_KEY": "",
            }
            return values.get(key, fallback or "")

        def fake_source(key: str) -> str:
            return {
                "SPOTIFY_CLIENT_ID": "keyring",
                "SPOTIFY_CLIENT_SECRET": "keyring",
                "YOUTUBE_API_KEY": "none",
            }.get(key, "none")

        with patch("src.guppy.workspace_governance.connector_status._home_path", return_value=tmp_path), patch(
            "src.guppy.workspace_governance.connector_status.read_machine_secret",
            side_effect=fake_secret,
        ), patch(
            "src.guppy.workspace_governance.connector_status.secret_source",
            side_effect=fake_source,
        ):
            spotify = build_connector_status("spotify")
            youtube = build_connector_status("youtube")

    assert spotify["auth_state"] == "ready"
    assert spotify["source"] == "mixed"
    assert spotify["secret_fields"] == [
        "SPOTIFY_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET",
        "SPOTIFY_REDIRECT_URI",
    ]
    assert youtube["auth_state"] == "optional"
    assert youtube["result_code"] == "ready"
    assert youtube["auth_detail"] == "YouTube API key is missing; fallback scraping may still work."


def test_build_connector_status_uses_provider_family_payload_for_crm() -> None:
    with patch(
        "src.guppy.workspace_governance.connector_status.build_crm_status",
        return_value={
            "auth_state": "ready",
            "auth_detail": "Salesforce provider credentials are configured.",
            "source": "keyring",
            "accounts": [],
            "providers": [{"id": "salesforce", "label": "Salesforce", "auth_state": "ready", "result_code": "ready"}],
            "secret_fields": ["SALESFORCE_ACCESS_TOKEN", "SALESFORCE_INSTANCE_URL"],
            "scope_telemetry": {"endpoint_prefixes": ["connector://crm/salesforce"], "action_ids": ["contact_write"], "summary": "CRM ready"},
        },
    ):
        status = build_connector_status("crm", provider="salesforce")

    assert status["label"] == "CRM"
    assert status["auth_state"] == "ready"
    assert status["source"] == "keyring"
    assert status["providers"][0]["id"] == "salesforce"
    assert status["result_code"] == "ready"
