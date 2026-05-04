"""Unit tests for the xLAM structured extraction helper.

Covers:
  - xlam_extract returns parsed tool_call dicts from a mock HTTP response
  - xlam_extract returns [] gracefully when xLAM is offline (ConnectError)
  - xlam_extract returns [] on HTTP error
  - xlam_extract returns [] on malformed JSON response
  - extract_contacts normalises tool call results to contact dicts
  - extract_contacts returns [] when xLAM offline (falls back gracefully)
"""
from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_xlam_response(tool_calls: list[dict]):
    """Build a mock httpx response with the given tool_calls."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls,
            }
        }]
    }
    return mock_resp


# ── 1. xlam_extract — happy path ──────────────────────────────────────────────

class TestXlamExtract:
    def test_returns_parsed_tool_calls(self):
        from src.guppy.inference.xlam_extractor import xlam_extract

        fake_tool_calls = [{
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "save_contact",
                "arguments": json.dumps({"name": "Alice Smith", "company": "Acme", "email": "alice@acme.com"}),
            },
        }]

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=_mock_xlam_response(fake_tool_calls))

        with patch("src.guppy.inference.xlam_extractor.httpx.AsyncClient", return_value=mock_client):
            results = _run(xlam_extract("Find contacts on this page", []))

        assert len(results) == 1
        assert results[0]["name"] == "save_contact"
        assert results[0]["arguments"]["name"] == "Alice Smith"

    def test_multiple_tool_calls_returned(self):
        from src.guppy.inference.xlam_extractor import xlam_extract

        fake_tool_calls = [
            {"id": "c1", "type": "function", "function": {"name": "save_contact",
                "arguments": json.dumps({"name": "Alice"})}},
            {"id": "c2", "type": "function", "function": {"name": "save_contact",
                "arguments": json.dumps({"name": "Bob"})}},
        ]

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=_mock_xlam_response(fake_tool_calls))

        with patch("src.guppy.inference.xlam_extractor.httpx.AsyncClient", return_value=mock_client):
            results = _run(xlam_extract("Find contacts", []))

        assert len(results) == 2
        names = {r["arguments"]["name"] for r in results}
        assert names == {"Alice", "Bob"}


# ── 2. xlam_extract — error paths ─────────────────────────────────────────────

class TestXlamExtractErrors:
    def test_connect_error_returns_empty_list(self):
        import httpx
        from src.guppy.inference.xlam_extractor import xlam_extract

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("src.guppy.inference.xlam_extractor.httpx.AsyncClient", return_value=mock_client):
            results = _run(xlam_extract("anything", []))

        assert results == []

    def test_http_status_error_returns_empty_list(self):
        from src.guppy.inference.xlam_extractor import xlam_extract

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 503")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("src.guppy.inference.xlam_extractor.httpx.AsyncClient", return_value=mock_client):
            results = _run(xlam_extract("anything", []))

        assert results == []

    def test_empty_choices_returns_empty_list(self):
        from src.guppy.inference.xlam_extractor import xlam_extract

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"choices": []}
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("src.guppy.inference.xlam_extractor.httpx.AsyncClient", return_value=mock_client):
            results = _run(xlam_extract("anything", []))

        assert results == []

    def test_malformed_args_json_skipped(self):
        from src.guppy.inference.xlam_extractor import xlam_extract

        fake_tool_calls = [
            {"id": "c1", "type": "function", "function": {"name": "save_contact", "arguments": "NOT JSON"}},
            {"id": "c2", "type": "function", "function": {"name": "save_contact",
                "arguments": json.dumps({"name": "Valid"})}},
        ]

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=_mock_xlam_response(fake_tool_calls))

        with patch("src.guppy.inference.xlam_extractor.httpx.AsyncClient", return_value=mock_client):
            results = _run(xlam_extract("anything", []))

        # Only the valid one survives
        assert len(results) == 1
        assert results[0]["arguments"]["name"] == "Valid"


# ── 3. extract_contacts ────────────────────────────────────────────────────────

class TestExtractContacts:
    def test_contact_normalised_correctly(self):
        from src.guppy.inference.xlam_extractor import extract_contacts

        fake_tool_calls = [{
            "id": "c1", "type": "function",
            "function": {
                "name": "save_contact",
                "arguments": json.dumps({
                    "name":    "Jane Doe",
                    "company": "TechCorp",
                    "email":   "jane@techcorp.com",
                    "phone":   "555-1234",
                    "title":   "CEO",
                    "notes":   "Interested in enterprise plan",
                }),
            },
        }]

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=_mock_xlam_response(fake_tool_calls))

        with patch("src.guppy.inference.xlam_extractor.httpx.AsyncClient", return_value=mock_client):
            contacts = _run(extract_contacts("raw page text"))

        assert len(contacts) == 1
        c = contacts[0]
        assert c["name"] == "Jane Doe"
        assert c["company"] == "TechCorp"
        assert c["email"] == "jane@techcorp.com"
        assert c["phone"] == "555-1234"
        assert "CEO" in c["notes"]

    def test_xlam_offline_returns_empty_list(self):
        import httpx
        from src.guppy.inference.xlam_extractor import extract_contacts

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("offline"))

        with patch("src.guppy.inference.xlam_extractor.httpx.AsyncClient", return_value=mock_client):
            contacts = _run(extract_contacts("some scraped text"))

        assert contacts == []

    def test_empty_text_returns_empty_list(self):
        from src.guppy.inference.xlam_extractor import extract_contacts
        contacts = _run(extract_contacts("   "))
        assert contacts == []

    def test_notes_joins_title_and_notes(self):
        from src.guppy.inference.xlam_extractor import extract_contacts

        fake_tool_calls = [{
            "id": "c1", "type": "function",
            "function": {
                "name": "save_contact",
                "arguments": json.dumps({
                    "name": "Bob", "title": "CTO", "notes": "Loves Python",
                }),
            },
        }]

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=_mock_xlam_response(fake_tool_calls))

        with patch("src.guppy.inference.xlam_extractor.httpx.AsyncClient", return_value=mock_client):
            contacts = _run(extract_contacts("text"))

        assert "CTO" in contacts[0]["notes"]
        assert "Loves Python" in contacts[0]["notes"]
