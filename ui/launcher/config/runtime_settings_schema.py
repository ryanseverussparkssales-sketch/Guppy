"""
runtime_settings_schema.py

Lane: TR54-C4
Responsibilities:
  - Central schema definition for all runtime settings fields
  - Explicit field ownership (which component/connector owns each field)
  - Validation at field set/get time
  - No per-component schemas — one registry, one contract
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class FieldType(Enum):
    SECRET = "secret"
    STRING = "string"
    INT = "int"
    BOOL = "bool"
    SELECT = "select"
    LIST = "list"


class FieldOwner(Enum):
    LAUNCHER = "launcher"
    CONNECTOR_GMAIL = "connector:gmail"
    CONNECTOR_CALENDAR = "connector:calendar"
    CONNECTOR_SPOTIFY = "connector:spotify"
    CONNECTOR_YOUTUBE = "connector:youtube"
    CONNECTOR_CRM = "connector:crm"
    CONNECTOR_VOIP = "connector:voip"
    INSTANCE = "instance"
    WORKSPACE = "workspace"
    VOICE = "voice"
    MODEL = "model"


@dataclass
class FieldDefinition:
    key: str
    field_type: FieldType
    owner: FieldOwner
    label: str
    required: bool = False
    help_text: str = ""
    validation_pattern: str = ""
    default_value: Any = None
    choices: list[str] = field(default_factory=list)

    def validate(self, value: Any) -> tuple[bool, str]:
        if value is None or value == "":
            if self.required:
                return False, f"'{self.label}' is required."
            return True, ""

        if self.field_type == FieldType.INT:
            try:
                int(value)
            except (TypeError, ValueError):
                return False, f"'{self.label}' must be an integer."

        if self.field_type == FieldType.BOOL:
            if not isinstance(value, bool):
                return False, f"'{self.label}' must be true or false."

        if self.field_type == FieldType.SELECT and self.choices:
            if str(value) not in self.choices:
                return False, f"'{self.label}' must be one of: {', '.join(self.choices)}."

        if self.validation_pattern:
            if not re.fullmatch(self.validation_pattern, str(value)):
                return False, f"'{self.label}' does not match the expected format."

        return True, ""

    def coerce(self, value: Any) -> Any:
        if value is None:
            return self.default_value
        if self.field_type == FieldType.INT:
            try:
                return int(value)
            except (TypeError, ValueError):
                return self.default_value
        if self.field_type == FieldType.BOOL:
            if isinstance(value, bool):
                return value
            return str(value).lower() in ("true", "1", "yes")
        return value


_SCHEMA: dict[str, FieldDefinition] = {
    # Launcher
    "launcher.instance_name": FieldDefinition(
        key="launcher.instance_name",
        field_type=FieldType.STRING,
        owner=FieldOwner.LAUNCHER,
        label="Instance name",
        required=True,
        default_value="guppy-primary",
    ),
    "launcher.dev_mode": FieldDefinition(
        key="launcher.dev_mode",
        field_type=FieldType.BOOL,
        owner=FieldOwner.LAUNCHER,
        label="Dev mode",
        default_value=False,
    ),
    "launcher.startup_timeout_ms": FieldDefinition(
        key="launcher.startup_timeout_ms",
        field_type=FieldType.INT,
        owner=FieldOwner.LAUNCHER,
        label="Startup timeout (ms)",
        default_value=3000,
    ),
    # Voice
    "voice.provider": FieldDefinition(
        key="voice.provider",
        field_type=FieldType.SELECT,
        owner=FieldOwner.VOICE,
        label="Voice provider",
        choices=["system", "elevenlabs", "openai"],
        default_value="system",
    ),
    "voice.enabled": FieldDefinition(
        key="voice.enabled",
        field_type=FieldType.BOOL,
        owner=FieldOwner.VOICE,
        label="Voice enabled",
        default_value=False,
    ),
    # Connectors — Gmail
    "connector.gmail.account_id": FieldDefinition(
        key="connector.gmail.account_id",
        field_type=FieldType.STRING,
        owner=FieldOwner.CONNECTOR_GMAIL,
        label="Gmail account",
    ),
    "connector.gmail.secret_key": FieldDefinition(
        key="connector.gmail.secret_key",
        field_type=FieldType.SELECT,
        owner=FieldOwner.CONNECTOR_GMAIL,
        label="Gmail secret field",
    ),
    # Connectors — Calendar
    "connector.calendar.account_id": FieldDefinition(
        key="connector.calendar.account_id",
        field_type=FieldType.STRING,
        owner=FieldOwner.CONNECTOR_CALENDAR,
        label="Calendar account",
    ),
    # Connectors — Spotify
    "connector.spotify.account_id": FieldDefinition(
        key="connector.spotify.account_id",
        field_type=FieldType.STRING,
        owner=FieldOwner.CONNECTOR_SPOTIFY,
        label="Spotify account",
    ),
    # Connectors — CRM
    "connector.crm.account_id": FieldDefinition(
        key="connector.crm.account_id",
        field_type=FieldType.STRING,
        owner=FieldOwner.CONNECTOR_CRM,
        label="CRM account",
    ),
    # Connectors — VoIP
    "connector.voip.account_id": FieldDefinition(
        key="connector.voip.account_id",
        field_type=FieldType.STRING,
        owner=FieldOwner.CONNECTOR_VOIP,
        label="VoIP account",
    ),
    # Model
    "model.default": FieldDefinition(
        key="model.default",
        field_type=FieldType.SELECT,
        owner=FieldOwner.MODEL,
        label="Default model",
        choices=["guppy-fast", "guppy", "guppy-code", "guppy-teach"],
        default_value="guppy-fast",
    ),
}


class RuntimeSettingsSchema:
    """Central registry of runtime settings field definitions."""

    def get(self, key: str) -> Optional[FieldDefinition]:
        return _SCHEMA.get(key)

    def all_fields(self) -> list[FieldDefinition]:
        return list(_SCHEMA.values())

    def fields_for_owner(self, owner: FieldOwner) -> list[FieldDefinition]:
        return [f for f in _SCHEMA.values() if f.owner == owner]

    def validate(self, key: str, value: Any) -> tuple[bool, str]:
        defn = _SCHEMA.get(key)
        if defn is None:
            return False, f"Unknown settings key: '{key}'."
        return defn.validate(value)

    def coerce(self, key: str, value: Any) -> Any:
        defn = _SCHEMA.get(key)
        if defn is None:
            return value
        return defn.coerce(value)

    def default_value(self, key: str) -> Any:
        defn = _SCHEMA.get(key)
        return defn.default_value if defn is not None else None

    def is_secret(self, key: str) -> bool:
        defn = _SCHEMA.get(key)
        return defn is not None and defn.field_type == FieldType.SECRET

    def owner_for(self, key: str) -> Optional[FieldOwner]:
        defn = _SCHEMA.get(key)
        return defn.owner if defn is not None else None


_schema = RuntimeSettingsSchema()


def get_schema() -> RuntimeSettingsSchema:
    return _schema
