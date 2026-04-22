from src.guppy.api._server_fragment_models import InstanceConnectorBindingRequest
from src.guppy.workspace_governance import validate_connector_binding_request


def _request(**overrides):
    payload = {
        "enabled": True,
        "account_id": "acct-1",
        "provider": "hubspot",
        "action_allow": ["contact_write"],
        "action_block": [],
        "endpoint_allow": ["connector://crm/hubspot"],
        "endpoint_block": [],
        "note": "ok",
    }
    payload.update(overrides)
    return InstanceConnectorBindingRequest(**payload)


def test_rejects_unknown_connector() -> None:
    err, payload = validate_connector_binding_request("unknown", _request())
    assert err == "unknown connector: unknown"
    assert payload == {}


def test_rejects_unknown_provider_for_connector() -> None:
    err, payload = validate_connector_binding_request("crm", _request(provider="unknown"))
    assert err == "unknown provider 'unknown' for connector 'crm'"
    assert payload == {}


def test_rejects_action_overlap() -> None:
    err, payload = validate_connector_binding_request(
        "crm",
        _request(action_allow=["contact_write"], action_block=["contact_write"]),
    )
    assert err == "action_allow and action_block overlap: contact_write"
    assert payload == {}


def test_rejects_unsupported_actions() -> None:
    err, payload = validate_connector_binding_request("crm", _request(action_allow=["call"]))
    assert err == "unsupported connector actions: call"
    assert payload == {}


def test_rejects_empty_endpoint_filters() -> None:
    err, payload = validate_connector_binding_request("crm", _request(endpoint_allow=[" "]))
    assert err == "endpoint filters cannot contain empty values"
    assert payload == {}


def test_normalizes_valid_request() -> None:
    err, payload = validate_connector_binding_request(
        "crm",
        _request(
            provider="HUBSPOT",
            action_allow=["contact_write", "CONTACT_WRITE", "opportunity_write"],
            action_block=[],
            endpoint_allow=[" connector://crm/hubspot "],
            note=" note ",
        ),
    )
    assert err is None
    assert payload["provider"] == "hubspot"
    assert payload["action_allow"] == ["contact_write", "opportunity_write"]
    assert payload["action_block"] == []
    assert payload["endpoint_allow"] == ["connector://crm/hubspot"]
    assert payload["note"] == "note"
