"""Provider registry for guided onboarding (PL-C4).

Centralises display metadata, secret field lists, verify support, and
"what to do next" guidance for every connector Guppy knows about.
No business logic — pure data + accessors.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderEntry:
    id: str
    label: str
    description: str
    secret_fields: list[str]
    verify_supported: bool
    next_step_hint: str
    doc_url: str = ""


PROVIDER_REGISTRY: dict[str, ProviderEntry] = {
    "gmail": ProviderEntry(
        id="gmail",
        label="Gmail",
        description="Read, send, and search your email inside Guppy.",
        secret_fields=[],
        verify_supported=True,
        next_step_hint="Try asking Guppy to check your inbox or draft a reply.",
    ),
    "calendar": ProviderEntry(
        id="calendar",
        label="Google Calendar",
        description="See upcoming events and manage your schedule without leaving the app.",
        secret_fields=[],
        verify_supported=True,
        next_step_hint="Ask Guppy what's on your calendar this week.",
    ),
    "spotify": ProviderEntry(
        id="spotify",
        label="Spotify",
        description="Play music and control Spotify playback with voice or text commands.",
        secret_fields=["SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REDIRECT_URI"],
        verify_supported=True,
        next_step_hint='Say "Play something relaxing" to try Spotify now.',
    ),
    "youtube": ProviderEntry(
        id="youtube",
        label="YouTube",
        description="Search YouTube and open videos — API key gives richer results but is optional.",
        secret_fields=["YOUTUBE_API_KEY"],
        verify_supported=True,
        next_step_hint='Ask Guppy to find a YouTube video on any topic.',
    ),
    "crm": ProviderEntry(
        id="crm",
        label="CRM",
        description="Connect HubSpot, Salesforce, GoHighLevel, or Zoho to manage contacts and deals.",
        secret_fields=[
            "HUBSPOT_API_KEY",
            "SALESFORCE_ACCESS_TOKEN",
            "SALESFORCE_INSTANCE_URL",
            "GOHIGHLEVEL_API_KEY",
            "ZOHO_ACCESS_TOKEN",
        ],
        verify_supported=True,
        next_step_hint="Try asking Guppy to look up a contact or log a note.",
    ),
    "voip": ProviderEntry(
        id="voip",
        label="VoIP / Calling",
        description="Place outbound calls through Twilio — enter your account credentials to enable.",
        secret_fields=["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"],
        verify_supported=True,
        next_step_hint="Ask Guppy to place a test call to confirm the setup.",
    ),
}


def get_provider(provider_id: str) -> ProviderEntry | None:
    """Return the ProviderEntry for *provider_id*, or None if unknown."""
    return PROVIDER_REGISTRY.get(str(provider_id or "").strip().lower())


def list_providers() -> list[ProviderEntry]:
    """Return all registered providers in stable insertion order."""
    return list(PROVIDER_REGISTRY.values())


def get_next_step(provider_id: str, *, is_connected: bool) -> str:
    """Return a plain-language next-step hint for the given provider.

    When not connected the hint tells the user how to connect; when
    connected it surfaces the ``next_step_hint`` from the registry.
    """
    entry = get_provider(provider_id)
    if entry is None:
        return ""
    if not is_connected:
        if entry.secret_fields:
            return f"Add your {entry.label} credentials in Settings to get started."
        return f"Open Settings > Connectors and sign in to {entry.label}."
    return entry.next_step_hint
